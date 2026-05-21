from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_codegen_module_probe.v1"
SOURCE_SITE = "nslg_client_gameassembly_codegen_module_probe"
SOURCE_URL = "local-nslg-client-gameassembly-codegen-module-probe"


class CodeGenModuleInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class CodeGenPointerTableStats(BaseModel):
    scanned_count: int = 0
    text_pointer_count: int = 0
    null_pointer_count: int = 0
    other_pointer_count: int = 0
    sample_size: int = 0
    sample_text_pointer_count: int = 0
    sample_null_pointer_count: int = 0
    sample_other_pointer_count: int = 0
    sample_entries: list[dict[str, Any]] = Field(default_factory=list)


class CodeGenModuleRecord(BaseModel):
    module_name: str = Field(min_length=1)
    struct_rva: str = ""
    ref_rva: str = ""
    method_pointer_count: int = 0
    method_pointer_table_rva: str = ""
    method_pointer_table_section: str = ""
    adjustor_thunk_count: int = 0
    adjustor_thunk_table_rva: str = ""
    invoker_indices_rva: str = ""
    reverse_pinvoke_wrapper_count: int = 0
    rgctx_ranges_count: int = 0
    rgctxs_count: int = 0
    method_pointer_table_stats: CodeGenPointerTableStats = Field(
        default_factory=CodeGenPointerTableStats
    )


class CodeGenModuleRun(BaseModel):
    start_ref_rva: str = ""
    end_ref_rva: str = ""
    module_count: int = 0
    first_module: str = ""
    last_module: str = ""
    contains_assembly_csharp: bool = False
    contains_assembly_csharp_firstpass: bool = False
    sample_modules: list[str] = Field(default_factory=list)


class CodeGenModuleProbeReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[CodeGenModuleInputArtifact] = Field(default_factory=list)
    gameassembly_summary: dict[str, Any] = Field(default_factory=dict)
    codegen_module_summary: dict[str, Any] = Field(default_factory=dict)
    assembly_csharp_modules: list[CodeGenModuleRecord] = Field(default_factory=list)
    codegen_module_runs: list[CodeGenModuleRun] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_codegen_module_probe_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> CodeGenModuleProbeReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return CodeGenModuleProbeReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        gameassembly_summary=_gameassembly_summary(_safe_map(data.get("gameassembly_summary"))),
        codegen_module_summary=_safe_map(data.get("codegen_module_summary")),
        assembly_csharp_modules=[
            _module_record(item)
            for item in data.get("assembly_csharp_modules") or []
            if isinstance(item, dict)
        ],
        codegen_module_runs=[
            _module_run(item)
            for item in data.get("codegen_module_runs") or []
            if isinstance(item, dict)
        ],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly CodeGenModule probe only; no live instrumentation, account data, or online protocol data is included",
            "method pointer tables are registration-side anchors, not decoded method names",
            "InitLuaEnv ownership requires decoded metadata or metadata-registration evidence before a pointer can be named",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_codegen_module_probe_report(
    report: CodeGenModuleProbeReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> CodeGenModuleInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return CodeGenModuleInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _gameassembly_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_name": Path(str(raw.get("file_name") or "GameAssembly.dll")).name,
        "size_bytes": int(raw.get("size_bytes") or 0),
        "sha256": str(raw.get("sha256") or ""),
        "image_base_hex": str(raw.get("image_base_hex") or ""),
        "section_count": int(raw.get("section_count") or 0),
        "pdata_function_count": int(raw.get("pdata_function_count") or 0),
        "sections": [
            {
                "name": str(item.get("name") or ""),
                "virtual_address_hex": str(item.get("virtual_address_hex") or ""),
                "virtual_size": int(item.get("virtual_size") or 0),
                "raw_size": int(item.get("raw_size") or 0),
            }
            for item in raw.get("sections") or []
            if isinstance(item, dict)
        ][:16],
    }


def _module_record(raw: dict[str, Any]) -> CodeGenModuleRecord:
    return CodeGenModuleRecord(
        module_name=str(raw.get("module_name") or "unknown"),
        struct_rva=str(raw.get("struct_rva") or ""),
        ref_rva=str(raw.get("ref_rva") or ""),
        method_pointer_count=int(raw.get("method_pointer_count") or 0),
        method_pointer_table_rva=str(raw.get("method_pointer_table_rva") or ""),
        method_pointer_table_section=str(raw.get("method_pointer_table_section") or ""),
        adjustor_thunk_count=int(raw.get("adjustor_thunk_count") or 0),
        adjustor_thunk_table_rva=str(raw.get("adjustor_thunk_table_rva") or ""),
        invoker_indices_rva=str(raw.get("invoker_indices_rva") or ""),
        reverse_pinvoke_wrapper_count=int(raw.get("reverse_pinvoke_wrapper_count") or 0),
        rgctx_ranges_count=int(raw.get("rgctx_ranges_count") or 0),
        rgctxs_count=int(raw.get("rgctxs_count") or 0),
        method_pointer_table_stats=_pointer_stats(
            _safe_map(raw.get("method_pointer_table_stats"))
        ),
    )


def _pointer_stats(raw: dict[str, Any]) -> CodeGenPointerTableStats:
    return CodeGenPointerTableStats(
        scanned_count=int(raw.get("scanned_count") or 0),
        text_pointer_count=int(raw.get("text_pointer_count") or 0),
        null_pointer_count=int(raw.get("null_pointer_count") or 0),
        other_pointer_count=int(raw.get("other_pointer_count") or 0),
        sample_size=int(raw.get("sample_size") or 0),
        sample_text_pointer_count=int(raw.get("sample_text_pointer_count") or 0),
        sample_null_pointer_count=int(raw.get("sample_null_pointer_count") or 0),
        sample_other_pointer_count=int(raw.get("sample_other_pointer_count") or 0),
        sample_entries=[
            {
                "index": int(item.get("index") or 0),
                "pointer_rva": str(item.get("pointer_rva") or ""),
                "section": str(item.get("section") or ""),
                "is_null": bool(item.get("is_null")),
            }
            for item in raw.get("sample_entries") or []
            if isinstance(item, dict)
        ][:24],
    )


def _module_run(raw: dict[str, Any]) -> CodeGenModuleRun:
    return CodeGenModuleRun(
        start_ref_rva=str(raw.get("start_ref_rva") or ""),
        end_ref_rva=str(raw.get("end_ref_rva") or ""),
        module_count=int(raw.get("module_count") or 0),
        first_module=str(raw.get("first_module") or ""),
        last_module=str(raw.get("last_module") or ""),
        contains_assembly_csharp=bool(raw.get("contains_assembly_csharp")),
        contains_assembly_csharp_firstpass=bool(raw.get("contains_assembly_csharp_firstpass")),
        sample_modules=[str(item) for item in raw.get("sample_modules") or []][:16],
    )


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
