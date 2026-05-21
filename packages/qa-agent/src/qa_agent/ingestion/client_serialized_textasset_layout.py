from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.serialized_textasset_layout.v1"
SOURCE_SITE = "nslg_client_serialized_textasset_layout_probe"
SOURCE_URL = "local-nslg-client-serialized-textasset-layout-probe"


class SerializedTextAssetInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class SerializedTextAssetStemSummary(BaseModel):
    stem: str = Field(min_length=1)
    record_count: int = 0
    match_count: int = 0
    valid_layout_count: int = 0
    name_stem_match_count: int = 0
    unique_object_offset_count: int = 0
    unique_payload_hash_count: int = 0
    repeated_object_offset_group_count: int = 0
    script_len_counts: list[dict[str, int]] = Field(default_factory=list)
    scenario_count: int = 0
    sample_scenarios: list[str] = Field(default_factory=list)
    sample_paths: list[str] = Field(default_factory=list)


class SerializedTextAssetLayoutReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[SerializedTextAssetInputArtifact] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    path_record_summary: dict[str, Any] = Field(default_factory=dict)
    stem_summaries: list[SerializedTextAssetStemSummary] = Field(default_factory=list)
    object_layout_groups: list[dict[str, Any]] = Field(default_factory=list)
    prior_route_context: dict[str, Any] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_serialized_textasset_layout_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> SerializedTextAssetLayoutReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return SerializedTextAssetLayoutReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        path_record_summary=_path_record_summary(_safe_map(data.get("path_record_summary"))),
        stem_summaries=[
            _stem_summary(item) for item in data.get("stem_summaries") or [] if isinstance(item, dict)
        ][:64],
        object_layout_groups=[
            _object_group_summary(item)
            for item in data.get("object_layout_groups") or []
            if isinstance(item, dict)
        ][:96],
        prior_route_context=_safe_map(data.get("prior_route_context")),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:160],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static extracted CAB and Round31 catalog probe only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only sanitized asset paths, path_ids, offsets, lengths, counts, and hashes are stored",
            "serialized TextAsset layout confirmation is not a native decoder or payload-buffer owner proof",
            "encrypted payload bytes remain blocked until decoder recovery and manual semantic review",
        ],
    )


def write_serialized_textasset_layout_report(
    report: SerializedTextAssetLayoutReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> SerializedTextAssetInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return SerializedTextAssetInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _stem_summary(raw: dict[str, Any]) -> SerializedTextAssetStemSummary:
    return SerializedTextAssetStemSummary(
        stem=str(raw.get("stem") or "unknown"),
        record_count=int(raw.get("record_count") or 0),
        match_count=int(raw.get("match_count") or 0),
        valid_layout_count=int(raw.get("valid_layout_count") or 0),
        name_stem_match_count=int(raw.get("name_stem_match_count") or 0),
        unique_object_offset_count=int(raw.get("unique_object_offset_count") or 0),
        unique_payload_hash_count=int(raw.get("unique_payload_hash_count") or 0),
        repeated_object_offset_group_count=int(
            raw.get("repeated_object_offset_group_count") or 0
        ),
        script_len_counts=[
            _int_dict(item) for item in raw.get("script_len_counts") or [] if isinstance(item, dict)
        ],
        scenario_count=int(raw.get("scenario_count") or 0),
        sample_scenarios=[str(item) for item in raw.get("sample_scenarios") or []][:16],
        sample_paths=[str(item) for item in raw.get("sample_paths") or []][:12],
    )


def _object_group_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "object_offset": int(raw.get("object_offset") or 0),
        "object_offset_hex": str(raw.get("object_offset_hex") or ""),
        "stem": str(raw.get("stem") or ""),
        "parsed_name": str(raw.get("parsed_name") or ""),
        "parsed_name_len": int(raw.get("parsed_name_len") or 0),
        "payload_offset": int(raw.get("payload_offset") or 0),
        "payload_offset_hex": str(raw.get("payload_offset_hex") or ""),
        "script_len": int(raw.get("script_len") or 0),
        "layout_valid": bool(raw.get("layout_valid")),
        "match_count": int(raw.get("match_count") or 0),
        "path_count": int(raw.get("path_count") or 0),
        "path_id_count": int(raw.get("path_id_count") or 0),
        "scenario_count": int(raw.get("scenario_count") or 0),
        "payload_sha256": str(raw.get("payload_sha256") or ""),
        "payload_hash_count": int(raw.get("payload_hash_count") or 0),
        "sample_paths": [str(item) for item in raw.get("sample_paths") or []][:8],
        "sample_path_ids": [str(item) for item in raw.get("sample_path_ids") or []][:8],
        "sample_scenarios": [str(item) for item in raw.get("sample_scenarios") or []][:16],
        "payload_first16_hex": str(raw.get("payload_first16_hex") or ""),
        "payload_last16_hex": str(raw.get("payload_last16_hex") or ""),
    }


def _path_record_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "record_count": int(raw.get("record_count") or 0),
        "unique_path_count": int(raw.get("unique_path_count") or 0),
        "unique_path_id_count": int(raw.get("unique_path_id_count") or 0),
        "preload_size_counts": [
            _int_dict(item)
            for item in raw.get("preload_size_counts") or []
            if isinstance(item, dict)
        ],
        "path_record_offset_min": int(raw.get("path_record_offset_min") or 0),
        "path_record_offset_max": int(raw.get("path_record_offset_max") or 0),
        "sample_paths": [str(item) for item in raw.get("sample_paths") or []][:16],
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
    return {str(key): int(raw or 0) for key, raw in value.items()}
