from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_registration_layout_probe.v1"
SOURCE_SITE = "nslg_client_gameassembly_registration_layout_probe"
SOURCE_URL = "local-nslg-client-gameassembly-registration-layout-probe"


class RegistrationLayoutInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class RegistrationLayoutReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[RegistrationLayoutInputArtifact] = Field(default_factory=list)
    round180_anchor: dict[str, Any] = Field(default_factory=dict)
    code_registration_start_candidates: list[dict[str, Any]] = Field(default_factory=list)
    primary_code_registration_layout: dict[str, Any] = Field(default_factory=dict)
    registration_xref_summary: dict[str, Any] = Field(default_factory=dict)
    metadata_registration_candidate_scan: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_registration_layout_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> RegistrationLayoutReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return RegistrationLayoutReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        round180_anchor=_round180_anchor_summary(_safe_map(data.get("round180_anchor"))),
        code_registration_start_candidates=[
            _code_registration_candidate(item)
            for item in data.get("code_registration_start_candidates") or []
            if isinstance(item, dict)
        ][:8],
        primary_code_registration_layout=_primary_layout_summary(
            _safe_map(data.get("primary_code_registration_layout"))
        ),
        registration_xref_summary=_xref_summary(_safe_map(data.get("registration_xref_summary"))),
        metadata_registration_candidate_scan=_metadata_candidate_scan(
            _safe_map(data.get("metadata_registration_candidate_scan"))
        ),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly registration layout probe only; no live instrumentation, account data, or online protocol data is included",
            "the 0x4332730 CodeRegistration-like start is a layout anchor, not a method-name mapping",
            "MetadataRegistration-like windows remain weak/unpaired candidates until a callsite or decoded metadata proves ownership",
            "InitLuaEnv ownership remains blocked until metadata-registration pairing or decoded metadata exists",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_registration_layout_report(report: RegistrationLayoutReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> RegistrationLayoutInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return RegistrationLayoutInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _round180_anchor_summary(raw: dict[str, Any]) -> dict[str, Any]:
    anchor = _safe_map(raw.get("registration_anchor"))
    counts = _int_dict(_safe_map(raw.get("counts")))
    return {
        "registration_anchor": {
            "codegen_modules_pointer_ref_rva": str(anchor.get("codegen_modules_pointer_ref_rva") or ""),
            "codegen_modules_count_field_rva": str(anchor.get("codegen_modules_count_field_rva") or ""),
            "declared_codegen_module_count": int(anchor.get("declared_codegen_module_count") or 0),
            "codegen_modules_array_rva": str(anchor.get("codegen_modules_array_rva") or ""),
            "field_owner_candidate_rva": str(anchor.get("field_owner_candidate_rva") or ""),
            "field_owner_note": str(anchor.get("field_owner_note") or ""),
        },
        "counts": counts,
    }


def _code_registration_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_start_rva": str(raw.get("candidate_start_rva") or ""),
        "candidate_start_section": str(raw.get("candidate_start_section") or ""),
        "score": int(raw.get("score") or 0),
        "count_pointer_pair_count": int(raw.get("count_pointer_pair_count") or 0),
        "nonzero_count_pointer_pair_count": int(
            raw.get("nonzero_count_pointer_pair_count") or 0
        ),
        "pointer_only_field_count": int(raw.get("pointer_only_field_count") or 0),
        "codegen_modules_count_field_offset": str(
            raw.get("codegen_modules_count_field_offset") or ""
        ),
        "codegen_modules_pointer_field_offset": str(
            raw.get("codegen_modules_pointer_field_offset") or ""
        ),
        "codegen_modules_count_field_rva": str(raw.get("codegen_modules_count_field_rva") or ""),
        "codegen_modules_pointer_field_rva": str(
            raw.get("codegen_modules_pointer_field_rva") or ""
        ),
        "codegen_modules_array_rva": str(raw.get("codegen_modules_array_rva") or ""),
        "sample_fields": [
            _field_row(item)
            for item in raw.get("sample_fields") or []
            if isinstance(item, dict)
        ][:18],
    }


def _primary_layout_summary(raw: dict[str, Any]) -> dict[str, Any]:
    offsets = _safe_map(raw.get("codegen_modules_field_offsets"))
    return {
        "candidate_start_rva": str(raw.get("candidate_start_rva") or ""),
        "candidate_start_va": str(raw.get("candidate_start_va") or ""),
        "candidate_end_rva": str(raw.get("candidate_end_rva") or ""),
        "codegen_modules_field_offsets": {
            "count_offset": str(offsets.get("count_offset") or ""),
            "pointer_offset": str(offsets.get("pointer_offset") or ""),
            "count_rva": str(offsets.get("count_rva") or ""),
            "pointer_rva": str(offsets.get("pointer_rva") or ""),
            "array_rva": str(offsets.get("array_rva") or ""),
        },
        "field_rows": [
            _field_row(item)
            for item in raw.get("field_rows") or []
            if isinstance(item, dict)
        ][:24],
    }


def _field_row(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "offset": str(raw.get("offset") or ""),
        "rva": str(raw.get("rva") or ""),
        "qword": raw.get("qword") if isinstance(raw.get("qword"), int) else str(raw.get("qword") or ""),
        "points_to_section": str(raw.get("points_to_section") or ""),
        "points_to_rva": str(raw.get("points_to_rva") or ""),
        "next_qword": (
            raw.get("next_qword")
            if isinstance(raw.get("next_qword"), int)
            else str(raw.get("next_qword") or "")
        ),
        "next_points_to_section": str(raw.get("next_points_to_section") or ""),
        "next_points_to_rva": str(raw.get("next_points_to_rva") or ""),
        "looks_like_count_pointer_pair": bool(raw.get("looks_like_count_pointer_pair")),
        "looks_like_pointer_only": bool(raw.get("looks_like_pointer_only")),
        "known_field": str(raw.get("known_field") or ""),
        "pointer_sample": [
            _pointer_sample(item)
            for item in raw.get("pointer_sample") or []
            if isinstance(item, dict)
        ][:4],
    }


def _pointer_sample(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "index": int(raw.get("index") or 0),
        "value": str(raw.get("value") or ""),
        "target_section": str(raw.get("target_section") or ""),
        "target_rva": str(raw.get("target_rva") or ""),
    }


def _xref_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(raw.get("available")),
        "searched_target_count": int(raw.get("searched_target_count") or 0),
        "code_ref_count": int(raw.get("code_ref_count") or 0),
        "raw_va_ref_count": int(raw.get("raw_va_ref_count") or 0),
        "code_refs": [
            {
                "site_rva": str(item.get("site_rva") or ""),
                "target_label": str(item.get("target_label") or ""),
                "target_rva": str(item.get("target_rva") or ""),
                "mnemonic": str(item.get("mnemonic") or ""),
                "op_str": str(item.get("op_str") or ""),
            }
            for item in raw.get("code_refs") or []
            if isinstance(item, dict)
        ][:40],
        "raw_va_refs": [
            {
                "target_label": str(item.get("target_label") or ""),
                "target_rva": str(item.get("target_rva") or ""),
                "ref_rva": str(item.get("ref_rva") or ""),
                "ref_section": str(item.get("ref_section") or ""),
            }
            for item in raw.get("raw_va_refs") or []
            if isinstance(item, dict)
        ][:40],
        "search_note": str(raw.get("search_note") or ""),
    }


def _metadata_candidate_scan(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_count": int(raw.get("candidate_count") or 0),
        "top_candidates": [
            _metadata_candidate(item)
            for item in raw.get("top_candidates") or []
            if isinstance(item, dict)
        ][:12],
        "scan_policy": "weak/unpaired MetadataRegistration-like windows only; require registration callsite or decoded metadata before promotion",
    }


def _metadata_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    section_counts = _safe_map(raw.get("pointer_section_counts"))
    return {
        "candidate_rva": str(raw.get("candidate_rva") or ""),
        "score": int(raw.get("score") or 0),
        "count_pointer_pair_count": int(raw.get("count_pointer_pair_count") or 0),
        "pointer_section_counts": _int_dict(section_counts),
        "sample_text_pointer_count": int(raw.get("sample_text_pointer_count") or 0),
        "sample_data_pointer_count": int(raw.get("sample_data_pointer_count") or 0),
        "fields": [
            _metadata_candidate_field(item)
            for item in raw.get("fields") or []
            if isinstance(item, dict)
        ][:6],
    }


def _metadata_candidate_field(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "offset": str(raw.get("offset") or ""),
        "count": int(raw.get("count") or 0),
        "pointer_rva": str(raw.get("pointer_rva") or ""),
        "pointer_section": str(raw.get("pointer_section") or ""),
        "sample": [
            _pointer_sample(item)
            for item in raw.get("sample") or []
            if isinstance(item, dict)
        ][:4],
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
