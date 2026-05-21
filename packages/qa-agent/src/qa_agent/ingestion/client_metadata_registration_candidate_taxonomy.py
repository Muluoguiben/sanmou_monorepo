from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_metadata_registration_candidate_taxonomy.v1"
SOURCE_SITE = "nslg_client_gameassembly_metadata_registration_candidate_taxonomy"
SOURCE_URL = "local-nslg-client-gameassembly-metadata-registration-candidate-taxonomy"


class MetadataRegistrationTaxonomyInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class MetadataRegistrationCandidateTaxonomyReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[MetadataRegistrationTaxonomyInputArtifact] = Field(default_factory=list)
    gameassembly_summary: dict[str, Any] = Field(default_factory=dict)
    scan_policy: dict[str, Any] = Field(default_factory=dict)
    round181_top_candidate_summary: dict[str, Any] = Field(default_factory=dict)
    round182_raw_ref_summary: dict[str, Any] = Field(default_factory=dict)
    metadata_ref_family_summary: dict[str, Any] = Field(default_factory=dict)
    shifted_window_summary: dict[str, Any] = Field(default_factory=dict)
    exact_ref_candidate_summary: dict[str, Any] = Field(default_factory=dict)
    high_count_candidate_summary: dict[str, Any] = Field(default_factory=dict)
    exact_ref_candidates: list[dict[str, Any]] = Field(default_factory=list)
    high_count_candidates: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_metadata_registration_candidate_taxonomy_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> MetadataRegistrationCandidateTaxonomyReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return MetadataRegistrationCandidateTaxonomyReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        gameassembly_summary=_simple_map(_safe_map(data.get("gameassembly_summary"))),
        scan_policy=_simple_map(_safe_map(data.get("scan_policy"))),
        round181_top_candidate_summary=_simple_map(
            _safe_map(data.get("round181_top_candidate_summary"))
        ),
        round182_raw_ref_summary=_simple_map(_safe_map(data.get("round182_raw_ref_summary"))),
        metadata_ref_family_summary=_simple_map(
            _safe_map(data.get("metadata_ref_family_summary"))
        ),
        shifted_window_summary=_simple_map(_safe_map(data.get("shifted_window_summary"))),
        exact_ref_candidate_summary=_simple_map(
            _safe_map(data.get("exact_ref_candidate_summary"))
        ),
        high_count_candidate_summary=_simple_map(
            _safe_map(data.get("high_count_candidate_summary"))
        ),
        exact_ref_candidates=[
            _candidate(item)
            for item in data.get("exact_ref_candidates") or []
            if isinstance(item, dict)
        ][:24],
        high_count_candidates=[
            _candidate(item)
            for item in data.get("high_count_candidates") or []
            if isinstance(item, dict)
        ][:32],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly MetadataRegistration candidate taxonomy only; no live instrumentation, account data, or online protocol data is included",
            "exact raw references to tiny-count candidate families are routing evidence, not MetadataRegistration ownership",
            "high-count windows without exact refs or a callsite remain weak scan leads",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_metadata_registration_candidate_taxonomy_report(
    report: MetadataRegistrationCandidateTaxonomyReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> MetadataRegistrationTaxonomyInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return MetadataRegistrationTaxonomyInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_rva": str(raw.get("candidate_rva") or ""),
        "pair_count": int(raw.get("pair_count") or 0),
        "tiny_count_pair_count": int(raw.get("tiny_count_pair_count") or 0),
        "medium_count_pair_count": int(raw.get("medium_count_pair_count") or 0),
        "high_count_pair_count": int(raw.get("high_count_pair_count") or 0),
        "max_count": int(raw.get("max_count") or 0),
        "sum_count": int(raw.get("sum_count") or 0),
        "raw_ref_count": int(raw.get("raw_ref_count") or 0),
        "pointer_section_counts": _int_dict(_safe_map(raw.get("pointer_section_counts"))),
        "sample_target_section_counts": _int_dict(
            _safe_map(raw.get("sample_target_section_counts"))
        ),
        "valid_sample_pointer_count": int(raw.get("valid_sample_pointer_count") or 0),
        "plausibility": str(raw.get("plausibility") or ""),
        "raw_refs": [
            _simple_map(item) for item in raw.get("raw_refs") or [] if isinstance(item, dict)
        ][:8],
        "field_counts": [int(item or 0) for item in raw.get("field_counts") or []][:16],
        "pointer_rvas": [str(item) for item in raw.get("pointer_rvas") or []][:16],
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
        if isinstance(value, dict):
            out[str(key)] = _simple_map(value)
        elif isinstance(value, list):
            out[str(key)] = [
                _simple_map(item) if isinstance(item, dict) else item for item in value
            ]
        else:
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
