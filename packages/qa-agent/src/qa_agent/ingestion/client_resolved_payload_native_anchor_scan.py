from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.resolved_payload_native_anchor_scan.v1"
SOURCE_SITE = "nslg_client_resolved_payload_native_anchor_scan"
SOURCE_URL = "local-nslg-client-resolved-payload-native-anchor-scan"


class ResolvedPayloadNativeAnchorInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class ResolvedPayloadNativeAnchorModuleRecord(BaseModel):
    module: str = Field(min_length=1)
    missing: bool = False
    size_bytes: int = 0
    anchor_hit_count_capped: int = 0
    strong_anchor_hit_count_capped: int = 0
    weak_anchor_hit_count_capped: int = 0
    cooccurrence_count: int = 0
    strong_cooccurrence_count: int = 0
    anchor_kind_hit_counts: dict[str, int] = Field(default_factory=dict)
    section_hit_counts: dict[str, int] = Field(default_factory=dict)
    hit_samples: list[dict[str, Any]] = Field(default_factory=list)
    cooccurrence_samples: list[dict[str, Any]] = Field(default_factory=list)


class ResolvedPayloadNativeAnchorScanReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[ResolvedPayloadNativeAnchorInputArtifact] = Field(default_factory=list)
    anchor_summary: dict[str, Any] = Field(default_factory=dict)
    cab_control: dict[str, Any] = Field(default_factory=dict)
    module_records: list[ResolvedPayloadNativeAnchorModuleRecord] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    prior_route_context: dict[str, Any] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_resolved_payload_native_anchor_scan_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> ResolvedPayloadNativeAnchorScanReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return ResolvedPayloadNativeAnchorScanReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        anchor_summary=_safe_map(data.get("anchor_summary")),
        cab_control=_cab_control(_safe_map(data.get("cab_control"))),
        module_records=[
            _module_record(item)
            for item in data.get("module_records") or []
            if isinstance(item, dict)
        ],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        prior_route_context=_safe_map(data.get("prior_route_context")),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:64],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static native anchor scan only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only sanitized module names, RVAs, offsets, counts, and hashes are stored",
            "isolated 4-byte numeric hits are weak noise unless co-located with a strong anchor",
            "native anchor absence is route evidence, not decoded gameplay knowledge",
        ],
    )


def write_resolved_payload_native_anchor_scan_report(
    report: ResolvedPayloadNativeAnchorScanReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> ResolvedPayloadNativeAnchorInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return ResolvedPayloadNativeAnchorInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _module_record(raw: dict[str, Any]) -> ResolvedPayloadNativeAnchorModuleRecord:
    return ResolvedPayloadNativeAnchorModuleRecord(
        module=str(raw.get("module") or "unknown"),
        missing=bool(raw.get("missing")),
        size_bytes=int(raw.get("size_bytes") or 0),
        anchor_hit_count_capped=int(raw.get("anchor_hit_count_capped") or 0),
        strong_anchor_hit_count_capped=int(raw.get("strong_anchor_hit_count_capped") or 0),
        weak_anchor_hit_count_capped=int(raw.get("weak_anchor_hit_count_capped") or 0),
        cooccurrence_count=int(raw.get("cooccurrence_count") or 0),
        strong_cooccurrence_count=int(raw.get("strong_cooccurrence_count") or 0),
        anchor_kind_hit_counts=_int_dict(_safe_map(raw.get("anchor_kind_hit_counts"))),
        section_hit_counts=_int_dict(_safe_map(raw.get("section_hit_counts"))),
        hit_samples=[
            _sample_hit(item) for item in raw.get("hit_samples") or [] if isinstance(item, dict)
        ][:32],
        cooccurrence_samples=[
            _sample_cooccurrence(item)
            for item in raw.get("cooccurrence_samples") or []
            if isinstance(item, dict)
        ][:24],
    )


def _sample_hit(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_offset_hex": str(raw.get("file_offset_hex") or ""),
        "rva": str(raw.get("rva") or ""),
        "section": str(raw.get("section") or ""),
        "kind": str(raw.get("kind") or ""),
        "strength": str(raw.get("strength") or ""),
        "sample_labels": [str(item) for item in raw.get("sample_labels") or []][:4],
    }


def _sample_cooccurrence(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "section": str(raw.get("section") or ""),
        "window_start_file_offset_hex": str(raw.get("window_start_file_offset_hex") or ""),
        "anchor_count": int(raw.get("anchor_count") or 0),
        "kinds": [str(item) for item in raw.get("kinds") or []][:12],
        "strengths": [str(item) for item in raw.get("strengths") or []][:4],
        "has_strong_anchor": bool(raw.get("has_strong_anchor")),
        "sample_rvas": [str(item) for item in raw.get("sample_rvas") or [] if item][:8],
    }


def _cab_control(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "anchor_kind_with_hits_count": int(raw.get("anchor_kind_with_hits_count") or 0),
        "anchor_kind_hit_counts": _int_dict(_safe_map(raw.get("anchor_kind_hit_counts"))),
        "strong_anchor_hit_count_capped": int(raw.get("strong_anchor_hit_count_capped") or 0),
        "weak_anchor_hit_count_capped": int(raw.get("weak_anchor_hit_count_capped") or 0),
        "sample_hits": [
            {
                "kind": str(item.get("kind") or ""),
                "strength": str(item.get("strength") or ""),
                "hit_count_capped": int(item.get("hit_count_capped") or 0),
                "sample_offsets_hex": [
                    str(offset) for offset in item.get("sample_offsets_hex") or []
                ][:6],
                "sample_labels": [str(label) for label in item.get("sample_labels") or []][:4],
            }
            for item in raw.get("sample_hits") or []
            if isinstance(item, dict)
        ][:32],
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
