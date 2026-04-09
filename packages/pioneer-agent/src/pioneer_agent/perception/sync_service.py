from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta, RuntimeState
from pioneer_agent.core.runtime_state_io import (
    RUNTIME_STATE_TOP_LEVEL_FIELDS,
    RuntimeStateRecord,
    load_runtime_state_record,
)


@dataclass
class SyncSummary:
    mode: str
    domains_refreshed: list[str]
    warnings: list[str]
    source_path: str | None = None
    captured_at: str | None = None
    record_index: int | None = None
    non_empty_state: bool = False


class StateSyncService:
    def __init__(self, input_path: Path | None = None) -> None:
        self.input_path = input_path.resolve() if input_path is not None else None

    def full_sync(self) -> tuple[RuntimeState, SyncSummary]:
        if self.input_path is None:
            return self._empty_result("Perception input path not configured.")

        if not self.input_path.exists():
            return self._empty_result(f"Perception input not found: {self.input_path}")

        try:
            record = self._load_record(self.input_path)
        except (OSError, ValueError, IndexError, json.JSONDecodeError) as exc:
            return self._empty_result(f"Failed to load perception input: {exc}")

        captured_at = self._get_captured_at(record.metadata)
        enriched_state = self._attach_default_field_meta(record.state, record, captured_at)
        domains_refreshed = self._get_domains_refreshed(enriched_state, record.metadata)
        warnings = [str(item) for item in record.metadata.get("warnings", []) if str(item).strip()]
        non_empty_state = self._is_non_empty_state(enriched_state)
        if not non_empty_state:
            warnings.append("Loaded runtime state is empty.")

        return enriched_state, SyncSummary(
            mode="full_sync",
            domains_refreshed=domains_refreshed,
            warnings=warnings,
            source_path=str(record.source_path) if record.source_path else None,
            captured_at=captured_at,
            record_index=record.record_index,
            non_empty_state=non_empty_state,
        )

    def _load_record(self, path: Path) -> RuntimeStateRecord:
        if path.is_dir():
            return self._load_record_from_directory(path)
        return load_runtime_state_record(path)

    def _load_record_from_directory(self, directory: Path) -> RuntimeStateRecord:
        state_payload: dict[str, Any] = {}
        domains_refreshed: list[str] = []

        for field_name in RUNTIME_STATE_TOP_LEVEL_FIELDS:
            if field_name == "field_meta":
                continue
            domain_file = directory / f"{field_name}.json"
            if not domain_file.exists():
                continue
            state_payload[field_name] = json.loads(domain_file.read_text(encoding="utf-8"))
            domains_refreshed.append(field_name)

        if domains_refreshed:
            metadata: dict[str, Any] = {"domains_refreshed": domains_refreshed}
            captured_at = self._find_directory_capture_time(directory, domains_refreshed)
            if captured_at is not None:
                metadata["captured_at"] = captured_at
            return RuntimeStateRecord(
                state=RuntimeState(**state_payload),
                metadata=metadata,
                record_index=None,
                source_path=directory.resolve(),
            )

        candidate_files = sorted(
            [
                child
                for child in directory.iterdir()
                if child.is_file() and child.suffix.lower() in {".json", ".jsonl"}
            ],
            key=lambda child: child.stat().st_mtime,
            reverse=True,
        )
        if not candidate_files:
            raise ValueError(f"No JSON or JSONL perception files found in directory: {directory}")

        record = load_runtime_state_record(candidate_files[0])
        record.metadata.setdefault("warnings", []).append(
            f"Directory sync selected latest file: {candidate_files[0].name}"
        )
        return record

    @staticmethod
    def _find_directory_capture_time(directory: Path, domains_refreshed: list[str]) -> str | None:
        timestamps: list[datetime] = []
        for field_name in domains_refreshed:
            domain_file = directory / f"{field_name}.json"
            if not domain_file.exists():
                continue
            timestamps.append(datetime.fromtimestamp(domain_file.stat().st_mtime))
        if not timestamps:
            return None
        return max(timestamps).isoformat()

    @staticmethod
    def _get_captured_at(metadata: dict[str, Any]) -> str | None:
        for key in ("captured_at", "created_at", "observed_at"):
            value = metadata.get(key)
            if isinstance(value, str) and value.strip():
                return value
        return None

    @staticmethod
    def _attach_default_field_meta(
        state: RuntimeState,
        record: RuntimeStateRecord,
        captured_at: str | None,
    ) -> RuntimeState:
        field_meta = dict(state.field_meta)
        resolved_time = StateSyncService._parse_datetime(captured_at)
        source_label = record.metadata.get("source") or (
            record.source_path.name if record.source_path is not None else "perception_input"
        )

        for field_name in RUNTIME_STATE_TOP_LEVEL_FIELDS:
            if field_name == "field_meta" or field_name in field_meta:
                continue
            value = getattr(state, field_name)
            if not StateSyncService._has_value(value):
                continue
            field_meta[field_name] = FieldMeta(
                value="loaded",
                confidence=0.8,
                source=str(source_label),
                updated_at=resolved_time,
            )

        return state.model_copy(update={"field_meta": field_meta})

    @staticmethod
    def _get_domains_refreshed(state: RuntimeState, metadata: dict[str, Any]) -> list[str]:
        explicit_domains = metadata.get("domains_refreshed")
        if isinstance(explicit_domains, list) and explicit_domains:
            return [str(item) for item in explicit_domains]

        refreshed: list[str] = []
        for field_name in RUNTIME_STATE_TOP_LEVEL_FIELDS:
            if field_name == "field_meta":
                continue
            if StateSyncService._has_value(getattr(state, field_name)):
                refreshed.append(field_name)
        return refreshed

    @staticmethod
    def _is_non_empty_state(state: RuntimeState) -> bool:
        return any(
            StateSyncService._has_value(getattr(state, field_name))
            for field_name in RUNTIME_STATE_TOP_LEVEL_FIELDS
            if field_name != "field_meta"
        )

    @staticmethod
    def _has_value(value: Any) -> bool:
        if isinstance(value, (list, dict, str, tuple, set)):
            return bool(value)
        return value is not None

    @staticmethod
    def _parse_datetime(value: str | None) -> datetime | None:
        if not value:
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _empty_result(warning: str) -> tuple[RuntimeState, SyncSummary]:
        return RuntimeState(), SyncSummary(
            mode="full_sync",
            domains_refreshed=[],
            warnings=[warning],
            non_empty_state=False,
        )
