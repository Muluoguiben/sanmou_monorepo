from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_resolver_caller_trace.v1"
SOURCE_SITE = "nslg_client_gameassembly_resolver_caller_trace"
SOURCE_URL = "local-nslg-client-gameassembly-resolver-caller-trace"


class GameAssemblyResolverCallerInputArtifact(BaseModel):
    role: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class GameAssemblyResolverCallerTraceReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[GameAssemblyResolverCallerInputArtifact] = Field(
        default_factory=list
    )
    target: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    category_counts: dict[str, int] = Field(default_factory=dict)
    classification_counts: dict[str, int] = Field(default_factory=dict)
    payload_owner_candidates: list[dict[str, Any]] = Field(default_factory=list)
    payload_label_callers: list[dict[str, Any]] = Field(default_factory=list)
    owner_signal_callers: list[dict[str, Any]] = Field(default_factory=list)
    xlua_descriptor_only_samples: list[dict[str, Any]] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_gameassembly_resolver_caller_trace_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> GameAssemblyResolverCallerTraceReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    input_artifacts = [
        _input_artifact(item)
        for item in data.get("input_artifacts") or []
        if isinstance(item, dict)
    ]
    return GameAssemblyResolverCallerTraceReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=input_artifacts,
        target=_safe_map(data.get("target")),
        counts=_int_dict(data.get("counts") or {}),
        category_counts=_int_dict(data.get("category_counts") or {}),
        classification_counts=_int_dict(data.get("classification_counts") or {}),
        payload_owner_candidates=_list_of_maps(data.get("payload_owner_candidates")),
        payload_label_callers=_list_of_maps(data.get("payload_label_callers")),
        owner_signal_callers=_list_of_maps(data.get("owner_signal_callers")),
        xlua_descriptor_only_samples=_list_of_maps(data.get("xlua_descriptor_only_samples")),
        route_conclusion=_safe_map(data.get("route_conclusion")),
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        guardrails=[
            "offline/static resolver-caller trace only; no live instrumentation, account data, or online protocol data is included",
            "input artifact paths are not persisted; only file names, hashes, RVAs, and sanitized counts are stored",
            "descriptor-only caller evidence must not be promoted as gameplay knowledge",
            "payload-buffer provenance is required before decoder promotion",
        ],
    )


def write_gameassembly_resolver_caller_trace_report(
    report: GameAssemblyResolverCallerTraceReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> GameAssemblyResolverCallerInputArtifact:
    return GameAssemblyResolverCallerInputArtifact(
        role=str(raw.get("role") or "unknown"),
        file_name=Path(str(raw.get("file_name") or "unknown")).name,
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _list_of_maps(value: Any) -> list[dict[str, Any]]:
    return [item for item in value or [] if isinstance(item, dict)]


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = int(raw or 0)
        except (TypeError, ValueError):
            continue
    return out
