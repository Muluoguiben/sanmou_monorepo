from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.global_metadata_loader_scan.v1"
SOURCE_SITE = "nslg_client_global_metadata_loader_mutation"
SOURCE_URL = "local-nslg-client-global-metadata-loader-mutation-scan"


class GlobalMetadataLoaderInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class GlobalMetadataLoaderScanReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[GlobalMetadataLoaderInputArtifact] = Field(default_factory=list)
    metadata_wrapper: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    binary_summaries: list[dict[str, Any]] = Field(default_factory=list)
    top_file_16_candidates: list[dict[str, Any]] = Field(default_factory=list)
    top_metadata_ref_candidates: list[dict[str, Any]] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_global_metadata_loader_scan_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> GlobalMetadataLoaderScanReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    binary_summaries = [
        _binary_summary(item)
        for item in data.get("binaries") or []
        if isinstance(item, dict)
    ]
    top_file_16 = _flatten_candidates(binary_summaries, "top_file_16_candidates")
    top_metadata_ref = _flatten_candidates(binary_summaries, "top_metadata_ref_candidates")
    return GlobalMetadataLoaderScanReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        metadata_wrapper=_safe_map(data.get("metadata_wrapper")),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        binary_summaries=binary_summaries,
        top_file_16_candidates=top_file_16[:20],
        top_metadata_ref_candidates=top_metadata_ref[:20],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        guardrails=[
            "offline/static loader-mutation scan only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, hashes, counts, and sanitized function summaries are stored",
            "function-level loader-mutation scoring is routing evidence and must not be promoted as decoded gameplay knowledge",
            "metadata recovery requires standard IL2CPP header pairs plus readable Assembly-CSharp/NSLGame strings",
        ],
    )


def write_global_metadata_loader_scan_report(
    report: GlobalMetadataLoaderScanReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> GlobalMetadataLoaderInputArtifact:
    file_name = str(raw.get("file_name") or "unknown").replace("\\", "/")
    return GlobalMetadataLoaderInputArtifact(
        file_name=Path(file_name).name,
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _binary_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "binary_name": str(raw.get("binary_name") or ""),
        "exists": bool(raw.get("exists")),
        "sha256": str(raw.get("sha256") or ""),
        "image_base": str(raw.get("image_base") or ""),
        "pdata_function_count": int(raw.get("pdata_function_count") or 0),
        "import_class_counts": _int_dict(_safe_map(raw.get("import_class_counts"))),
        "raw_metadata_hit_counts": _int_dict(_safe_map(raw.get("raw_metadata_hit_counts"))),
        "metadata_target_count": int(raw.get("metadata_target_count") or 0),
        "instruction_totals": _int_dict(_safe_map(raw.get("instruction_totals"))),
        "candidate_count": int(raw.get("candidate_count") or 0),
        "full_loader_mutation_candidate_count": int(
            raw.get("full_loader_mutation_candidate_count") or 0
        ),
        "file_16_candidate_count": int(raw.get("file_16_candidate_count") or 0),
        "metadata_ref_candidate_count": int(raw.get("metadata_ref_candidate_count") or 0),
        "top_candidates": [
            _candidate_summary(item)
            for item in raw.get("top_candidates") or []
            if isinstance(item, dict)
        ][:8],
        "top_full_loader_mutation_candidates": [
            _candidate_summary(item)
            for item in raw.get("top_full_loader_mutation_candidates") or []
            if isinstance(item, dict)
        ][:8],
        "top_file_16_candidates": [
            _candidate_summary(item)
            for item in raw.get("top_file_16_candidates") or []
            if isinstance(item, dict)
        ][:8],
        "top_metadata_ref_candidates": [
            _candidate_summary(item)
            for item in raw.get("top_metadata_ref_candidates") or []
            if isinstance(item, dict)
        ][:8],
    }


def _candidate_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "binary": str(raw.get("binary") or ""),
        "function": _safe_map(raw.get("function")),
        "score": int(raw.get("score") or 0),
        "reasons": [str(item) for item in raw.get("reasons") or []],
        "classification": _safe_map(raw.get("classification")),
        "counts": _int_dict(_safe_map(raw.get("counts"))),
        "import_refs": [_ref_summary(item) for item in raw.get("import_refs") or []][:12],
        "metadata_refs": [_ref_summary(item) for item in raw.get("metadata_refs") or []][:12],
        "constant_refs": [_ref_summary(item) for item in raw.get("constant_refs") or []][:12],
        "caller_samples": [_edge_summary(item) for item in raw.get("caller_samples") or []][:12],
        "callee_samples": [_edge_summary(item) for item in raw.get("callee_samples") or []][:12],
        "evidence_ref": str(raw.get("evidence_ref") or ""),
    }


def _ref_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    summary: dict[str, Any] = {}
    for key in ("rva", "import", "class", "label", "text", "target"):
        if key in raw:
            summary[key] = raw.get(key)
    return summary


def _edge_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "site": raw.get("site"),
        "caller": _safe_map(raw.get("caller")),
        "callee": _safe_map(raw.get("callee")),
        "target_rva": raw.get("target_rva"),
    }


def _flatten_candidates(binary_summaries: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for summary in binary_summaries:
        candidates.extend(
            item for item in summary.get(key) or [] if isinstance(item, dict)
        )
    return sorted(candidates, key=lambda item: int(item.get("score") or 0), reverse=True)


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
