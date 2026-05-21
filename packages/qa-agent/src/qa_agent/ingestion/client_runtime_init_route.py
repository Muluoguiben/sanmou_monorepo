from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.runtime_init_metadata_route.v1"
SOURCE_SITE = "nslg_client_runtime_init_metadata_route"
SOURCE_URL = "local-nslg-client-runtime-init-metadata-route"


class RuntimeInitInputArtifact(BaseModel):
    role: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class RuntimeInitMetadataRouteReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[RuntimeInitInputArtifact] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    runtime_initialize_anchor: dict[str, Any] = Field(default_factory=dict)
    runtime_hook_targets: dict[str, Any] = Field(default_factory=dict)
    global_metadata_wrapper: dict[str, Any] = Field(default_factory=dict)
    metadata_xref_closure: dict[str, Any] = Field(default_factory=dict)
    textasset_route: dict[str, Any] = Field(default_factory=dict)
    nep2_init_bridge: dict[str, Any] = Field(default_factory=dict)
    native_boundary: dict[str, Any] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_runtime_init_metadata_route_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> RuntimeInitMetadataRouteReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    input_artifacts = [
        _input_artifact(item)
        for item in data.get("input_artifacts") or []
        if isinstance(item, dict)
    ]
    return RuntimeInitMetadataRouteReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=input_artifacts,
        counts=_int_dict(data.get("counts") or {}),
        runtime_initialize_anchor=_safe_map(data.get("runtime_initialize_anchor")),
        runtime_hook_targets=_safe_map(data.get("runtime_hook_targets")),
        global_metadata_wrapper=_safe_map(data.get("global_metadata_wrapper")),
        metadata_xref_closure=_safe_map(data.get("metadata_xref_closure")),
        textasset_route=_safe_map(data.get("textasset_route")),
        nep2_init_bridge=_safe_map(data.get("nep2_init_bridge")),
        native_boundary=_safe_map(data.get("native_boundary")),
        route_conclusion=_safe_map(data.get("route_conclusion")),
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        guardrails=[
            "offline/static route summary only; no live instrumentation, account data, or online protocol data is included",
            "input artifact paths are not persisted; only file names, hashes, and sanitized counts are stored",
            "this artifact is decoder-planning evidence and must not be promoted as gameplay knowledge",
            "global-metadata method ownership or payload-buffer provenance is required before decoder promotion",
        ],
    )


def write_runtime_init_metadata_route_report(
    report: RuntimeInitMetadataRouteReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> RuntimeInitInputArtifact:
    return RuntimeInitInputArtifact(
        role=str(raw.get("role") or "unknown"),
        file_name=Path(str(raw.get("file_name") or "unknown")).name,
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = int(raw or 0)
        except (TypeError, ValueError):
            continue
    return out
