from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.serialized_textasset_path_resolution.v1"
SOURCE_SITE = "nslg_client_serialized_textasset_path_resolution"
SOURCE_URL = "local-nslg-client-serialized-textasset-path-resolution"


class SerializedTextAssetResolutionInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class SerializedTextAssetResolvedRecord(BaseModel):
    path: str = Field(min_length=1)
    stem: str = Field(min_length=1)
    scenario: str = ""
    path_id_hex: str = Field(min_length=1)
    preload_index: int = 0
    preload_size: int = 0
    file_id: int = 0
    container_record_offset_hex: str = ""
    container_valid: bool = False
    candidate_count: int = 0
    resolved: bool = False
    resolved_object_offset_hex: str | None = None
    resolved_payload_offset_hex: str | None = None
    resolved_script_len: int | None = None
    resolved_payload_sha1: str | None = None
    resolved_payload_sha256: str | None = None


class SerializedTextAssetResolutionReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[SerializedTextAssetResolutionInputArtifact] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    stem_summaries: list[dict[str, Any]] = Field(default_factory=list)
    resolved_object_groups: list[dict[str, Any]] = Field(default_factory=list)
    resolved_records: list[SerializedTextAssetResolvedRecord] = Field(default_factory=list)
    prior_route_context: dict[str, Any] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_serialized_textasset_resolution_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> SerializedTextAssetResolutionReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return SerializedTextAssetResolutionReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        stem_summaries=[
            _stem_summary(item)
            for item in data.get("stem_summaries") or []
            if isinstance(item, dict)
        ][:64],
        resolved_object_groups=[
            _object_group_summary(item)
            for item in data.get("resolved_object_groups") or []
            if isinstance(item, dict)
        ][:96],
        resolved_records=[
            _resolved_record(item)
            for item in data.get("resolved_records") or []
            if isinstance(item, dict)
        ][:256],
        prior_route_context=_safe_map(data.get("prior_route_context")),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:256],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static extracted CAB and catalog evidence only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only sanitized asset paths, path_ids, offsets, lengths, counts, and hashes are stored",
            "path_id/object_offset resolution is decoder-route evidence, not reviewed gameplay knowledge",
            "encrypted payload bytes remain blocked until decoder recovery and manual semantic review",
        ],
    )


def write_serialized_textasset_resolution_report(
    report: SerializedTextAssetResolutionReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> SerializedTextAssetResolutionInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return SerializedTextAssetResolutionInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _resolved_record(raw: dict[str, Any]) -> SerializedTextAssetResolvedRecord:
    return SerializedTextAssetResolvedRecord(
        path=str(raw.get("path") or ""),
        stem=str(raw.get("stem") or "unknown"),
        scenario=str(raw.get("scenario") or ""),
        path_id_hex=str(raw.get("path_id_hex") or ""),
        preload_index=int(raw.get("preload_index") or 0),
        preload_size=int(raw.get("preload_size") or 0),
        file_id=int(raw.get("file_id") or 0),
        container_record_offset_hex=str(raw.get("container_record_offset_hex") or ""),
        container_valid=bool(raw.get("container_valid")),
        candidate_count=int(raw.get("candidate_count") or 0),
        resolved=bool(raw.get("resolved")),
        resolved_object_offset_hex=_optional_str(raw.get("resolved_object_offset_hex")),
        resolved_payload_offset_hex=_optional_str(raw.get("resolved_payload_offset_hex")),
        resolved_script_len=_optional_int(raw.get("resolved_script_len")),
        resolved_payload_sha1=_optional_str(raw.get("resolved_payload_sha1")),
        resolved_payload_sha256=_optional_str(raw.get("resolved_payload_sha256")),
    )


def _stem_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "stem": str(raw.get("stem") or "unknown"),
        "record_count": int(raw.get("record_count") or 0),
        "resolved_record_count": int(raw.get("resolved_record_count") or 0),
        "unique_resolved_object_offset_count": int(
            raw.get("unique_resolved_object_offset_count") or 0
        ),
        "scenario_count": int(raw.get("scenario_count") or 0),
        "script_len_counts": [
            _int_dict(item) for item in raw.get("script_len_counts") or [] if isinstance(item, dict)
        ],
        "sample_scenarios": [str(item) for item in raw.get("sample_scenarios") or []][:16],
        "sample_paths": [str(item) for item in raw.get("sample_paths") or []][:12],
    }


def _object_group_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "object_offset": int(raw.get("object_offset") or 0),
        "object_offset_hex": str(raw.get("object_offset_hex") or ""),
        "payload_offset": int(raw.get("payload_offset") or 0),
        "payload_offset_hex": str(raw.get("payload_offset_hex") or ""),
        "stem": str(raw.get("stem") or ""),
        "script_len": int(raw.get("script_len") or 0),
        "payload_sha1": str(raw.get("payload_sha1") or ""),
        "payload_sha256": str(raw.get("payload_sha256") or ""),
        "path_count": int(raw.get("path_count") or 0),
        "path_id_count": int(raw.get("path_id_count") or 0),
        "scenario_count": int(raw.get("scenario_count") or 0),
        "sample_paths": [str(item) for item in raw.get("sample_paths") or []][:8],
        "sample_path_ids": [str(item) for item in raw.get("sample_path_ids") or []][:8],
        "sample_scenarios": [str(item) for item in raw.get("sample_scenarios") or []][:16],
    }


def _counts(raw_counts: dict[str, Any], conclusion: dict[str, Any]) -> dict[str, int]:
    counts = _int_dict(raw_counts)
    counts["publishable_knowledge_entries"] = int(
        conclusion.get("publishable_knowledge_entries") or 0
    )
    return counts


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, raw in value.items():
        if isinstance(raw, bool):
            out[str(key)] = int(raw)
        elif isinstance(raw, (int, float, str)):
            try:
                out[str(key)] = int(raw or 0)
            except ValueError:
                continue
    return out


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    return str(value)


def _optional_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)
