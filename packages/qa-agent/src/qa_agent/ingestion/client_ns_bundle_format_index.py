from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.ns_bundle_format_index.v1"
SOURCE_SITE = "nslg_client_ns_bundle_static_format_index"
SOURCE_URL = "local-nslg-client-ns-bundle-format-index"


class NsBundleFormatGroup(BaseModel):
    asset_group: str = Field(min_length=1)
    bundle_count: int = 0
    total_bytes: int = 0
    parse_ok_count: int = 0
    protected_metadata_count: int = 0
    directory_shapes: dict[str, int] = Field(default_factory=dict)
    sample_rel_paths: list[str] = Field(default_factory=list)
    evidence_ref: str = Field(min_length=1)


class NsBundleCabBlock2Group(BaseModel):
    metadata_block2_hex: str = Field(min_length=1)
    bundle_count: int = 0
    asset_group_counts: dict[str, int] = Field(default_factory=dict)
    sample_rel_paths: list[str] = Field(default_factory=list)
    evidence_ref: str = Field(min_length=1)


class NsBundlePriorityRecord(BaseModel):
    rel_path: str = Field(min_length=1)
    asset_group: str = Field(min_length=1)
    priority_rank: int = 0
    size_bytes: int = 0
    directory_shape: str = ""
    block_count: int = 0
    directory_node_count: int = 0
    serialized_version: int = 0
    metadata_size: int = 0
    data_offset: int = 0
    metadata_block1_sha1: str = ""
    metadata_block2_sha1: str = ""
    protected_metadata_likely: bool = False
    evidence_ref: str = Field(min_length=1)


class NsBundleFormatIndexReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input: dict[str, Any] = Field(default_factory=dict)
    scan_policy: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    format_groups: list[NsBundleFormatGroup] = Field(default_factory=list)
    cab_block2_groups: list[NsBundleCabBlock2Group] = Field(default_factory=list)
    priority_records: list[NsBundlePriorityRecord] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_ns_bundle_format_index_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> NsBundleFormatIndexReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return NsBundleFormatIndexReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input=_sanitize_map(_safe_map(data.get("input"))),
        scan_policy=_sanitize_map(_safe_map(data.get("scan_policy"))),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        format_groups=[
            _format_group(item)
            for item in data.get("format_groups") or []
            if isinstance(item, dict)
        ][:120],
        cab_block2_groups=[
            _cab_block2_group(item)
            for item in data.get("cab_block2_groups") or []
            if isinstance(item, dict)
        ][:120],
        priority_records=[
            _priority_record(item)
            for item in data.get("priority_records") or []
            if isinstance(item, dict)
        ][:120],
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or [] if item],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static .ns UnityFS format index only; no live instrumentation, account data, credentials, or online protocol data is included",
            "bundle payload bytes are not exported; records contain sanitized counts, hashes, relative paths, and short header fingerprints",
            "all indexed bundles remain protected SerializedFile decoder targets, not publishable gameplay knowledge",
        ],
    )


def write_ns_bundle_format_index_report(
    report: NsBundleFormatIndexReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _format_group(raw: dict[str, Any]) -> NsBundleFormatGroup:
    return NsBundleFormatGroup(
        asset_group=str(raw.get("asset_group") or "unknown"),
        bundle_count=int(raw.get("bundle_count") or 0),
        total_bytes=int(raw.get("total_bytes") or 0),
        parse_ok_count=int(raw.get("parse_ok_count") or 0),
        protected_metadata_count=int(raw.get("protected_metadata_count") or 0),
        directory_shapes=_int_dict(_safe_map(raw.get("directory_shapes"))),
        sample_rel_paths=[_portable_rel(str(item)) for item in raw.get("sample_rel_paths") or []],
        evidence_ref=str(raw.get("evidence_ref") or "NSLG_NS_BUNDLE_FORMAT_INDEX:missing"),
    )


def _cab_block2_group(raw: dict[str, Any]) -> NsBundleCabBlock2Group:
    return NsBundleCabBlock2Group(
        metadata_block2_hex=str(raw.get("metadata_block2_hex") or ""),
        bundle_count=int(raw.get("bundle_count") or 0),
        asset_group_counts=_int_dict(_safe_map(raw.get("asset_group_counts"))),
        sample_rel_paths=[_portable_rel(str(item)) for item in raw.get("sample_rel_paths") or []],
        evidence_ref=str(raw.get("evidence_ref") or "NSLG_NS_BUNDLE_FORMAT_INDEX:missing"),
    )


def _priority_record(raw: dict[str, Any]) -> NsBundlePriorityRecord:
    return NsBundlePriorityRecord(
        rel_path=_portable_rel(str(raw.get("rel_path") or "unknown")),
        asset_group=str(raw.get("asset_group") or "unknown"),
        priority_rank=int(raw.get("priority_rank") or 0),
        size_bytes=int(raw.get("size_bytes") or 0),
        directory_shape=str(raw.get("directory_shape") or ""),
        block_count=int(raw.get("block_count") or 0),
        directory_node_count=int(raw.get("directory_node_count") or 0),
        serialized_version=int(raw.get("serialized_version") or 0),
        metadata_size=int(raw.get("metadata_size") or 0),
        data_offset=int(raw.get("data_offset") or 0),
        metadata_block1_sha1=str(raw.get("metadata_block1_sha1") or ""),
        metadata_block2_sha1=str(raw.get("metadata_block2_sha1") or ""),
        protected_metadata_likely=bool(raw.get("protected_metadata_likely")),
        evidence_ref=str(raw.get("evidence_ref") or "NSLG_NS_BUNDLE_FORMAT_INDEX:missing"),
    )


def _counts(raw_counts: dict[str, Any], conclusion: dict[str, Any]) -> dict[str, int]:
    counts = _int_dict(raw_counts)
    counts["publishable_knowledge_entries"] = int(
        conclusion.get("publishable_knowledge_entries") or 0
    )
    return counts


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _sanitize_map(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in raw.items():
        if isinstance(value, dict):
            out[str(key)] = _sanitize_map(value)
        elif isinstance(value, list):
            out[str(key)] = [
                _sanitize_map(item) if isinstance(item, dict) else _sanitize_scalar(item)
                for item in value
            ]
        else:
            out[str(key)] = _sanitize_scalar(value)
    return out


def _sanitize_scalar(value: Any) -> Any:
    if isinstance(value, str):
        return _portable_rel(value)
    return value


def _portable_rel(value: str) -> str:
    normalized = value.replace("\\", "/")
    parts = [part for part in normalized.split("/") if part and part not in {".", ".."}]
    for anchor in ("LocalPersistentData", "com.bilibili.nslg_Data", "assets/bundles"):
        if anchor in parts:
            return "/".join(parts[parts.index(anchor) :])
    if parts and parts[0].endswith(":"):
        parts = parts[1:]
    return "/".join(parts)


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
