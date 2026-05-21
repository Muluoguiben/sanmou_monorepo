from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.nep2_init_data_owner_scan.v1"
SOURCE_SITE = "nslg_client_nep2_init_data_owner_scan"
SOURCE_URL = "local-nslg-client-nep2-init-data-owner-scan"


class Nep2InitDataInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class Nep2InitDataOwnerScanReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    binary_name: str = "NEP2.dll"
    input_artifacts: list[Nep2InitDataInputArtifact] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    target_kind_counts: dict[str, int] = Field(default_factory=dict)
    data_ref_section_counts: dict[str, int] = Field(default_factory=dict)
    candidate_verdict_counts: dict[str, int] = Field(default_factory=dict)
    data_reference_samples: list[dict[str, Any]] = Field(default_factory=list)
    bridge_record_windows: list[dict[str, Any]] = Field(default_factory=list)
    inspected_functions: list[dict[str, Any]] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_nep2_init_data_owner_scan_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> Nep2InitDataOwnerScanReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return Nep2InitDataOwnerScanReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        binary_name=Path(str(data.get("binary_name") or "NEP2.dll").replace("\\", "/")).name,
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        target_kind_counts=_int_dict(_safe_map(data.get("target_kind_counts"))),
        data_ref_section_counts=_int_dict(_safe_map(data.get("data_ref_section_counts"))),
        candidate_verdict_counts=_int_dict(_safe_map(data.get("candidate_verdict_counts"))),
        data_reference_samples=[
            _data_ref_summary(item) for item in data.get("data_reference_samples") or []
        ][:80],
        bridge_record_windows=[
            _bridge_window_summary(item) for item in data.get("bridge_record_windows") or []
        ][:24],
        inspected_functions=[
            _function_summary(item) for item in data.get("inspected_functions") or []
        ][:24],
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static NEP2 data-reference scan only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, hashes, RVAs, counts, and sanitized summaries are stored",
            "RTTI/type descriptor/code-pointer adjacency is routing evidence only, not payload-buffer ownership proof",
            "no decoded LuaScripts/global-metadata/gameplay configuration is promoted from this artifact",
        ],
    )


def write_nep2_init_data_owner_scan_report(
    report: Nep2InitDataOwnerScanReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> Nep2InitDataInputArtifact:
    file_name = str(raw.get("file_name") or "unknown").replace("\\", "/")
    return Nep2InitDataInputArtifact(
        file_name=Path(file_name).name,
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _data_ref_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "kind": raw.get("kind"),
        "section": raw.get("section"),
        "at_rva": raw.get("at_rva"),
        "target_rva": raw.get("target_rva"),
        "target_labels": [str(item) for item in raw.get("target_labels") or []][:4],
        "target_kinds": [str(item) for item in raw.get("target_kinds") or []],
        "owner_function": _safe_map(raw.get("owner_function")),
    }


def _bridge_window_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "center_rva": raw.get("center_rva"),
        "label": raw.get("label"),
        "section": raw.get("section"),
        "code_pointer_count": int(raw.get("code_pointer_count") or 0),
        "data_pointer_count": int(raw.get("data_pointer_count") or 0),
        "string_ref_count": int(raw.get("string_ref_count") or 0),
        "code_pointer_samples": [
            _safe_map(item) for item in raw.get("code_pointer_samples") or []
        ][:16],
        "data_pointer_samples": [
            _safe_map(item) for item in raw.get("data_pointer_samples") or []
        ][:16],
        "string_ref_samples": [
            _safe_map(item) for item in raw.get("string_ref_samples") or []
        ][:16],
    }


def _function_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "evidence_ref": str(raw.get("evidence_ref") or ""),
        "function": _safe_map(raw.get("function")),
        "source": str(raw.get("source") or ""),
        "verdict": str(raw.get("verdict") or ""),
        "score": int(raw.get("score") or 0),
        "counts": _int_dict(_safe_map(raw.get("counts"))),
        "file_import_names": [str(item) for item in raw.get("file_import_names") or []],
        "payload_keyword_refs": [
            str(item) for item in raw.get("payload_keyword_refs") or []
        ],
        "bridge_keyword_refs": [
            str(item) for item in raw.get("bridge_keyword_refs") or []
        ],
        "has_16byte_or_loop_signal": bool(raw.get("has_16byte_or_loop_signal")),
        "imports": [_event_summary(item) for item in raw.get("imports") or []][:24],
        "keyword_refs": [
            _safe_map(item) for item in raw.get("keyword_refs") or []
        ][:24],
        "constants": [_safe_map(item) for item in raw.get("constants") or []][:24],
        "direct_callers": [
            _safe_map(item) for item in raw.get("direct_callers") or []
        ][:24],
        "direct_callees": [
            _safe_map(item) for item in raw.get("direct_callees") or []
        ][:24],
        "interesting_instructions": [
            str(item) for item in raw.get("interesting_instructions") or []
        ][:48],
    }


def _event_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("rva", "import", "import_name", "text", "label", "value"):
        if key in raw:
            out[key] = raw.get(key)
    if raw.get("context"):
        out["context"] = [str(item) for item in raw.get("context") or []][:16]
    return out


def _counts(raw_counts: dict[str, Any], conclusion: dict[str, Any]) -> dict[str, int]:
    counts = _int_dict(raw_counts)
    counts["publishable_knowledge_entries"] = int(
        conclusion.get("publishable_knowledge_entries") or 0
    )
    return counts


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(raw or 0) for key, raw in value.items()}
