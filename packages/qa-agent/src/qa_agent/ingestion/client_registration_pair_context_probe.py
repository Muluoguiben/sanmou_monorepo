from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_registration_pair_context_probe.v1"
SOURCE_SITE = "nslg_client_gameassembly_registration_pair_context_probe"
SOURCE_URL = "local-nslg-client-gameassembly-registration-pair-context-probe"


class RegistrationPairInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class RegistrationPairContextReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[RegistrationPairInputArtifact] = Field(default_factory=list)
    round181_layout_anchor: dict[str, int] = Field(default_factory=dict)
    registration_targets: list[dict[str, Any]] = Field(default_factory=list)
    metadata_targets: list[dict[str, Any]] = Field(default_factory=list)
    raw_registration_ref_summary: dict[str, Any] = Field(default_factory=dict)
    raw_metadata_ref_summary: dict[str, Any] = Field(default_factory=dict)
    code_ref_summary: dict[str, Any] = Field(default_factory=dict)
    pair_neighborhood_scan: dict[str, Any] = Field(default_factory=dict)
    call_argument_window_scan: dict[str, Any] = Field(default_factory=dict)
    metadata_ref_families: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_registration_pair_context_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> RegistrationPairContextReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return RegistrationPairContextReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        round181_layout_anchor=_int_dict(_safe_map(data.get("round181_layout_anchor"))),
        registration_targets=[
            _target(item) for item in data.get("registration_targets") or [] if isinstance(item, dict)
        ][:16],
        metadata_targets=[
            _target(item) for item in data.get("metadata_targets") or [] if isinstance(item, dict)
        ][:16],
        raw_registration_ref_summary=_ref_summary(
            _safe_map(data.get("raw_registration_ref_summary"))
        ),
        raw_metadata_ref_summary=_ref_summary(_safe_map(data.get("raw_metadata_ref_summary"))),
        code_ref_summary=_code_ref_summary(_safe_map(data.get("code_ref_summary"))),
        pair_neighborhood_scan=_pair_scan(_safe_map(data.get("pair_neighborhood_scan"))),
        call_argument_window_scan=_call_window_scan(
            _safe_map(data.get("call_argument_window_scan"))
        ),
        metadata_ref_families=_metadata_ref_families(
            _safe_map(data.get("metadata_ref_families"))
        ),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly registration pair-context probe only; no live instrumentation, account data, or online protocol data is included",
            "direct pointer-pair xref evidence is negative in this artifact; absence of static refs does not prove runtime values cannot be constructed dynamically",
            "MetadataRegistration-like candidates remain weak data-family candidates until a callsite or decoded metadata proves ownership",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_registration_pair_context_report(
    report: RegistrationPairContextReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> RegistrationPairInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return RegistrationPairInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _target(raw: dict[str, Any]) -> dict[str, Any]:
    out = {
        "label": str(raw.get("label") or ""),
        "rva": str(raw.get("rva") or ""),
        "role": str(raw.get("role") or ""),
    }
    for key in ("rank", "score", "count_pointer_pair_count"):
        if key in raw:
            out[key] = int(raw.get(key) or 0)
    return out


def _ref_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_count": int(raw.get("target_count") or 0),
        "raw_ref_count": int(raw.get("raw_ref_count") or 0),
        "section_counts": _int_dict(_safe_map(raw.get("section_counts"))),
        "target_role_counts": _int_dict(_safe_map(raw.get("target_role_counts"))),
        "target_ref_counts": _int_dict(_safe_map(raw.get("target_ref_counts"))),
        "refs": [_ref(item) for item in raw.get("refs") or [] if isinstance(item, dict)][:80],
    }


def _ref(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "target_label": str(raw.get("target_label") or ""),
        "target_role": str(raw.get("target_role") or ""),
        "target_rva": str(raw.get("target_rva") or ""),
        "ref_rva": str(raw.get("ref_rva") or ""),
        "ref_section": str(raw.get("ref_section") or ""),
    }


def _code_ref_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "searched_target_count": int(raw.get("searched_target_count") or 0),
        "code_ref_count": int(raw.get("code_ref_count") or 0),
        "registration_code_ref_count": int(raw.get("registration_code_ref_count") or 0),
        "metadata_candidate_code_ref_count": int(
            raw.get("metadata_candidate_code_ref_count") or 0
        ),
        "refs": [
            {
                "site_rva": str(item.get("site_rva") or ""),
                "target_label": str(item.get("target_label") or ""),
                "target_role": str(item.get("target_role") or ""),
                "target_rva": str(item.get("target_rva") or ""),
                "mnemonic": str(item.get("mnemonic") or ""),
                "op_str": str(item.get("op_str") or ""),
            }
            for item in raw.get("refs") or []
            if isinstance(item, dict)
        ][:40],
    }


def _pair_scan(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "window_size_bytes": int(raw.get("window_size_bytes") or 0),
        "paired_neighborhood_count": int(raw.get("paired_neighborhood_count") or 0),
        "neighborhoods": [
            {
                "window_rva": str(item.get("window_rva") or ""),
                "window_section": str(item.get("window_section") or ""),
                "registration_ref_count": len(item.get("registration_refs") or []),
                "metadata_ref_count": len(item.get("metadata_refs") or []),
            }
            for item in raw.get("neighborhoods") or []
            if isinstance(item, dict)
        ][:40],
    }


def _call_window_scan(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(raw.get("available")),
        "candidate_window_count": int(raw.get("candidate_window_count") or 0),
        "windows": [
            {
                "call_site_rva": str(item.get("call_site_rva") or ""),
                "call_op_str": str(item.get("call_op_str") or ""),
            }
            for item in raw.get("windows") or []
            if isinstance(item, dict)
        ][:40],
    }


def _metadata_ref_families(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "family_cluster_count": int(raw.get("family_cluster_count") or 0),
        "clusters": [
            {
                "section": str(item.get("section") or ""),
                "start_rva": str(item.get("start_rva") or ""),
                "end_rva": str(item.get("end_rva") or ""),
                "ref_count": int(item.get("ref_count") or 0),
                "unique_target_count": int(item.get("unique_target_count") or 0),
                "target_labels": [str(label) for label in item.get("target_labels") or []][:24],
            }
            for item in raw.get("clusters") or []
            if isinstance(item, dict)
        ][:24],
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
