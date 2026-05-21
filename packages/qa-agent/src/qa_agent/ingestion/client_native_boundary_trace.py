from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.native_loadbuffer_boundary_trace.v1"
SOURCE_SITE = "nslg_client_native_boundary_trace"
SOURCE_URL = "local-nslg-client-native-loadbuffer-boundary"


class NativeBoundaryModuleRecord(BaseModel):
    evidence_ref: str = Field(min_length=1)
    module: str = Field(min_length=1)
    binary_sha256: str = ""
    size_bytes: int = Field(ge=0)
    import_count: int = 0
    target_import_count: int = 0
    export_count: int = 0
    target_export_count: int = 0
    keyword_hit_count: int = 0
    keyword_data_ref_count: int = 0
    import_call_count: int = 0
    inspected_function_count: int = 0
    boundary_signal_count: int = 0
    boundary_signal_kinds: dict[str, int] = Field(default_factory=dict)
    route_flags: dict[str, Any] = Field(default_factory=dict)


class NativeLoadbufferBoundaryTraceReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    summary: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    module_records: list[NativeBoundaryModuleRecord] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_native_loadbuffer_boundary_trace_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> NativeLoadbufferBoundaryTraceReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    modules = [
        _module_record(item, source_id=source_id)
        for item in data.get("module_records") or []
        if isinstance(item, dict) and not item.get("missing")
    ]
    return NativeLoadbufferBoundaryTraceReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        summary=[str(item) for item in data.get("summary") or []],
        counts=_int_dict(data.get("counts") or {}),
        module_records=modules,
        route_conclusion=data.get("route_conclusion")
        if isinstance(data.get("route_conclusion"), dict)
        else {},
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=[record.evidence_ref for record in modules],
        guardrails=[
            "offline/static native boundary evidence only; no live instrumentation, account data, or online protocol data is included",
            "module paths are not persisted; only module names, hashes, counts, and evidence refs are stored",
            "this artifact is decoder-routing evidence and must not be promoted as game knowledge",
            "continue only from provenance-backed file-buffer, asset-owner, or runtime-init metadata leads",
        ],
    )


def write_native_loadbuffer_boundary_trace_report(
    report: NativeLoadbufferBoundaryTraceReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _module_record(raw: dict[str, Any], *, source_id: str) -> NativeBoundaryModuleRecord:
    module = Path(str(raw.get("module") or "unknown")).name
    signal_counts = Counter(
        str(item.get("kind") or "unknown")
        for item in raw.get("boundary_signals") or []
        if isinstance(item, dict)
    )
    target_imports = raw.get("target_imports") or []
    target_exports = raw.get("target_exports") or []
    has_xlua_import = any(
        _contains_any(str(item.get("name") or ""), ("xlua", "lua", "loadbuffer"))
        for item in target_imports
        if isinstance(item, dict)
    )
    has_loadbuffer_export = any(
        _contains_any(str(item.get("name") or ""), ("loadbuffer",))
        for item in target_exports
        if isinstance(item, dict)
    )
    return NativeBoundaryModuleRecord(
        evidence_ref=f"NSLG_NATIVE_BOUNDARY:{source_id}:module:{module}",
        module=module,
        binary_sha256=str(raw.get("binary_sha256") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        import_count=int(raw.get("import_count") or 0),
        target_import_count=int(raw.get("target_import_count") or 0),
        export_count=int(raw.get("export_count") or 0),
        target_export_count=int(raw.get("target_export_count") or 0),
        keyword_hit_count=int(raw.get("keyword_hit_count") or 0),
        keyword_data_ref_count=int(raw.get("keyword_data_ref_count") or 0),
        import_call_count=int(raw.get("import_call_count") or 0),
        inspected_function_count=int(raw.get("inspected_function_count") or 0),
        boundary_signal_count=int(raw.get("boundary_signal_count") or 0),
        boundary_signal_kinds=dict(sorted(signal_counts.items())),
        route_flags={
            "has_xlua_or_loadbuffer_import": has_xlua_import,
            "has_loadbuffer_export": has_loadbuffer_export,
        },
    )


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    low = text.lower()
    return any(token in low for token in tokens)


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    out: dict[str, int] = {}
    for key, raw in value.items():
        try:
            out[str(key)] = int(raw or 0)
        except (TypeError, ValueError):
            continue
    return out
