from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.global_metadata_transform_probe.v1"
SOURCE_SITE = "nslg_client_global_metadata"
SOURCE_URL = "local-nslg-client-global-metadata-transform-probe"


class GlobalMetadataTransformInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class GlobalMetadataTransformProbeReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[GlobalMetadataTransformInputArtifact] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    file_summary: dict[str, Any] = Field(default_factory=dict)
    transform_probe: dict[str, Any] = Field(default_factory=dict)
    repeated_block_probe: dict[str, Any] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_global_metadata_transform_probe_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> GlobalMetadataTransformProbeReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    file_summary = _safe_map(data.get("file_summary"))
    transform_probe = _summarize_transform_probe(_safe_map(data.get("transform_probe")))
    repeated_block_probe = _safe_map(data.get("repeated_block_probe"))
    conclusion = _safe_map(data.get("conclusion"))
    return GlobalMetadataTransformProbeReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        counts=_counts(file_summary, transform_probe, repeated_block_probe, conclusion),
        file_summary=file_summary,
        transform_probe=transform_probe,
        repeated_block_probe=repeated_block_probe,
        route_conclusion=conclusion,
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        guardrails=[
            "offline/static transform probe only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, hashes, counts, and sanitized probe summaries are stored",
            "negative transform evidence is decoder-planning evidence and must not be promoted as gameplay knowledge",
            "standard IL2CPP header pairs and readable Assembly-CSharp/NSLGame strings are required before metadata recovery is accepted",
        ],
    )


def write_global_metadata_transform_probe_report(
    report: GlobalMetadataTransformProbeReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> GlobalMetadataTransformInputArtifact:
    return GlobalMetadataTransformInputArtifact(
        file_name=Path(str(raw.get("file_name") or "unknown")).name,
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _summarize_transform_probe(raw: dict[str, Any]) -> dict[str, Any]:
    best = [
        _summarize_candidate(item)
        for item in raw.get("best_header_candidates") or []
        if isinstance(item, dict)
    ]
    return {
        "candidate_count": int(raw.get("candidate_count") or 0),
        "needle_hit_candidate_count": int(raw.get("needle_hit_candidate_count") or 0),
        "tested_transform_families": [str(item) for item in raw.get("tested_transform_families") or []],
        "best_header_candidates": best[:20],
        "needle_hit_candidates": [
            _summarize_needle_candidate(item)
            for item in raw.get("needle_hit_candidates") or []
            if isinstance(item, dict)
        ][:20],
    }


def _summarize_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    model = raw.get("best_header_model") if isinstance(raw.get("best_header_model"), dict) else {}
    return {
        "name": str(raw.get("name") or ""),
        "params": raw.get("params") if isinstance(raw.get("params"), dict) else {},
        "header_score": int(raw.get("header_score") or 0),
        "model": str(model.get("model") or ""),
        "valid_pair_count": int(model.get("valid_pair_count") or 0),
        "monotonic_pair_count": int(model.get("monotonic_pair_count") or 0),
        "version_standard_int": bool(model.get("version_standard_int")),
    }


def _summarize_needle_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": str(raw.get("name") or ""),
        "params": raw.get("params") if isinstance(raw.get("params"), dict) else {},
        "needle_hit_terms": sorted(str(key) for key in (raw.get("needle_hits") or {}).keys()),
    }


def _counts(
    file_summary: dict[str, Any],
    transform_probe: dict[str, Any],
    repeated_block_probe: dict[str, Any],
    conclusion: dict[str, Any],
) -> dict[str, int]:
    block16 = _block_summary(repeated_block_probe, 16)
    best = transform_probe.get("best_header_candidates") or []
    max_valid_pairs = max((int(item.get("valid_pair_count") or 0) for item in best), default=0)
    return {
        "global_metadata_file_size": int(file_summary.get("file_size") or 0),
        "protected_size_mod_16": int(file_summary.get("protected_size_mod_16") or 0),
        "transform_candidate_count": int(transform_probe.get("candidate_count") or 0),
        "needle_hit_candidate_count": int(transform_probe.get("needle_hit_candidate_count") or 0),
        "best_header_valid_pair_count": max_valid_pairs,
        "repeated_block_duplicate_kinds_16": int(block16.get("duplicate_block_kinds") or 0),
        "repeated_block_extra_instances_16": int(block16.get("duplicate_extra_instances") or 0),
        "publishable_knowledge_entries": int(conclusion.get("publishable_knowledge_entries") or 0),
    }


def _block_summary(repeated_block_probe: dict[str, Any], block_size: int) -> dict[str, Any]:
    for item in repeated_block_probe.get("by_block_size") or []:
        if isinstance(item, dict) and int(item.get("block_size") or 0) == block_size:
            return item
    return {}


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
