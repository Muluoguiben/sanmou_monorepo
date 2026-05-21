from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_function_pointer_table_probe.v1"
SOURCE_SITE = "nslg_client_gameassembly_function_pointer_table_probe"
SOURCE_URL = "local-nslg-client-gameassembly-function-pointer-table-probe"


class FunctionPointerTableInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class FunctionPointerTableProbeReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[FunctionPointerTableInputArtifact] = Field(default_factory=list)
    gameassembly_summary: dict[str, Any] = Field(default_factory=dict)
    scan_policy: dict[str, Any] = Field(default_factory=dict)
    known_method_pointer_tables: dict[str, Any] = Field(default_factory=dict)
    known_code_registration_field_tables: dict[str, Any] = Field(default_factory=dict)
    target_function_summary: dict[str, Any] = Field(default_factory=dict)
    scan_summary: dict[str, Any] = Field(default_factory=dict)
    codegen_method_table_stats: list[dict[str, Any]] = Field(default_factory=list)
    code_registration_field_table_stats: list[dict[str, Any]] = Field(default_factory=list)
    relevant_function_pointer_hits: list[dict[str, Any]] = Field(default_factory=list)
    outside_known_table_runs: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_function_pointer_table_probe_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> FunctionPointerTableProbeReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return FunctionPointerTableProbeReport(
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
        scan_policy=_scan_policy(_safe_map(data.get("scan_policy"))),
        known_method_pointer_tables=_known_method_pointer_tables(
            _safe_map(data.get("known_method_pointer_tables"))
        ),
        known_code_registration_field_tables=_known_code_registration_field_tables(
            _safe_map(data.get("known_code_registration_field_tables"))
        ),
        target_function_summary=_target_function_summary(
            _safe_map(data.get("target_function_summary"))
        ),
        scan_summary=_scan_summary(_safe_map(data.get("scan_summary"))),
        codegen_method_table_stats=[
            _codegen_method_table_stat(item)
            for item in data.get("codegen_method_table_stats") or []
            if isinstance(item, dict)
        ][:32],
        code_registration_field_table_stats=[
            _code_registration_field_table_stat(item)
            for item in data.get("code_registration_field_table_stats") or []
            if isinstance(item, dict)
        ][:16],
        relevant_function_pointer_hits=[
            _relevant_hit(item)
            for item in data.get("relevant_function_pointer_hits") or []
            if isinstance(item, dict)
        ][:80],
        outside_known_table_runs=[
            _outside_run(item)
            for item in data.get("outside_known_table_runs") or []
            if isinstance(item, dict)
        ][:32],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly function pointer table probe only; no live instrumentation, account data, or online protocol data is included",
            "known IL2CPP table membership is not method-name ownership",
            "InitLuaEnv remains unresolved until decoded metadata or proven metadata-registration ownership exists",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_function_pointer_table_probe_report(
    report: FunctionPointerTableProbeReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> FunctionPointerTableInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return FunctionPointerTableInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _gameassembly_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_name": str(raw.get("file_name") or ""),
        "size_bytes": int(raw.get("size_bytes") or 0),
        "sha256": str(raw.get("sha256") or ""),
        "image_base": str(raw.get("image_base") or ""),
        "entry_rva": str(raw.get("entry_rva") or ""),
        "section_count": int(raw.get("section_count") or 0),
        "pdata_function_count": int(raw.get("pdata_function_count") or 0),
    }


def _scan_policy(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "sections": [str(item) for item in raw.get("sections") or []],
        "slot_width": int(raw.get("slot_width") or 0),
        "recognized_encodings": [str(item) for item in raw.get("recognized_encodings") or []],
        "recognized_target": str(raw.get("recognized_target") or ""),
        "known_method_table_source": str(raw.get("known_method_table_source") or ""),
        "known_code_registration_field_source": str(
            raw.get("known_code_registration_field_source") or ""
        ),
    }


def _known_method_pointer_tables(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "table_count": int(raw.get("table_count") or 0),
        "total_declared_method_pointer_count": int(
            raw.get("total_declared_method_pointer_count") or 0
        ),
        "sample": [_simple_map(item) for item in raw.get("sample") or [] if isinstance(item, dict)][:24],
    }


def _known_code_registration_field_tables(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "table_count": int(raw.get("table_count") or 0),
        "total_declared_pointer_count": int(raw.get("total_declared_pointer_count") or 0),
        "sample": [_simple_map(item) for item in raw.get("sample") or [] if isinstance(item, dict)][:16],
    }


def _target_function_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_function_count": int(raw.get("target_function_count") or 0),
        "by_category": _int_dict(_safe_map(raw.get("by_category"))),
        "targets": [_simple_map(item) for item in raw.get("targets") or [] if isinstance(item, dict)][:64],
    }


def _scan_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "function_pointer_hit_count": int(raw.get("function_pointer_hit_count") or 0),
        "pointer_run_count": int(raw.get("pointer_run_count") or 0),
        "relevant_function_pointer_hit_count": int(
            raw.get("relevant_function_pointer_hit_count") or 0
        ),
        "outside_known_tables_relevant_hit_count": int(
            raw.get("outside_known_tables_relevant_hit_count") or 0
        ),
        "outside_known_tables_sampled_run_count": int(
            raw.get("outside_known_tables_sampled_run_count") or 0
        ),
        "section_counts": _int_dict(_safe_map(raw.get("section_counts"))),
        "encoding_counts": _int_dict(_safe_map(raw.get("encoding_counts"))),
        "target_category_counts": _int_dict(_safe_map(raw.get("target_category_counts"))),
    }


def _codegen_method_table_stat(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "module_name": str(raw.get("module_name") or ""),
        "module_index": int(raw.get("module_index") or 0),
        "method_pointer_table_rva": str(raw.get("method_pointer_table_rva") or ""),
        "method_pointer_count": int(raw.get("method_pointer_count") or 0),
        "function_pointer_hit_count": int(raw.get("function_pointer_hit_count") or 0),
        "relevant_target_hit_count": int(raw.get("relevant_target_hit_count") or 0),
        "target_category_counts": _int_dict(_safe_map(raw.get("target_category_counts"))),
        "relevant_hits": [
            _relevant_hit(item) for item in raw.get("relevant_hits") or [] if isinstance(item, dict)
        ][:16],
    }


def _code_registration_field_table_stat(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "field_offset": str(raw.get("field_offset") or ""),
        "pointer_table_rva": str(raw.get("pointer_table_rva") or ""),
        "declared_count": int(raw.get("declared_count") or 0),
        "function_pointer_hit_count": int(raw.get("function_pointer_hit_count") or 0),
        "relevant_target_hit_count": int(raw.get("relevant_target_hit_count") or 0),
        "target_category_counts": _int_dict(_safe_map(raw.get("target_category_counts"))),
        "known_field": str(raw.get("known_field") or ""),
        "relevant_hits": [
            _relevant_hit(item) for item in raw.get("relevant_hits") or [] if isinstance(item, dict)
        ][:16],
    }


def _relevant_hit(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot_rva": str(raw.get("slot_rva") or ""),
        "slot_section": str(raw.get("slot_section") or ""),
        "target_rva": str(raw.get("target_rva") or ""),
        "target_label": str(raw.get("target_label") or ""),
        "target_category": str(raw.get("target_category") or ""),
        "known_method_table_module": str(raw.get("known_method_table_module") or ""),
        "known_method_table_index": _optional_int(raw.get("known_method_table_index")),
        "known_code_registration_field": str(raw.get("known_code_registration_field") or ""),
        "known_code_registration_index": _optional_int(raw.get("known_code_registration_index")),
    }


def _outside_run(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": str(raw.get("section") or ""),
        "start_rva": str(raw.get("start_rva") or ""),
        "end_rva": str(raw.get("end_rva") or ""),
        "hit_count": int(raw.get("hit_count") or 0),
        "candidate_kind": str(raw.get("candidate_kind") or ""),
        "target_category_counts": _int_dict(_safe_map(raw.get("target_category_counts"))),
        "target_labels": [str(item) for item in raw.get("target_labels") or []],
    }


def _counts(raw_counts: dict[str, Any], conclusion: dict[str, Any]) -> dict[str, int]:
    counts = _int_dict(raw_counts)
    counts["publishable_knowledge_entries"] = int(
        conclusion.get("publishable_knowledge_entries") or 0
    )
    return counts


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _simple_map(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            out[str(key)] = value
    return out


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


def _optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
