from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.client_resource_surface_gap_scan.v1"
SOURCE_SITE = "nslg_client_install_static_inventory"
SOURCE_URL = "local-nslg-client-install-resource-surface"


class ResourceRootGroup(BaseModel):
    root: str = Field(min_length=1)
    classification: str = Field(min_length=1)
    file_count: int = 0
    total_bytes: int = 0
    extension_counts: dict[str, int] = Field(default_factory=dict)
    sample_rel_paths: list[str] = Field(default_factory=list)


class ResourceMagicSample(BaseModel):
    rel_path: str = Field(min_length=1)
    size: int = 0
    suffix: str = ""
    classification_reason: str = ""
    magic_hex: str = ""
    magic_ascii: str = ""
    evidence_ref: str = Field(min_length=1)


class NsBundleGroup(BaseModel):
    group: str = Field(min_length=1)
    file_count: int = 0
    total_bytes: int = 0
    largest_file_bytes: int = 0
    sample_files: list[dict[str, Any]] = Field(default_factory=list)
    evidence_ref: str = Field(min_length=1)


class ClientResourceSurfaceGapScanReport(BaseModel):
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
    root_groups: list[ResourceRootGroup] = Field(default_factory=list)
    safe_magic_samples: list[ResourceMagicSample] = Field(default_factory=list)
    ns_bundle_groups: list[NsBundleGroup] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_client_resource_surface_gap_scan_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> ClientResourceSurfaceGapScanReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return ClientResourceSurfaceGapScanReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input=_sanitize_map(_safe_map(data.get("input"))),
        scan_policy=_sanitize_map(_safe_map(data.get("scan_policy"))),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        root_groups=[
            _root_group(item) for item in data.get("root_groups") or [] if isinstance(item, dict)
        ],
        safe_magic_samples=[
            _magic_sample(item)
            for item in data.get("safe_magic_samples") or []
            if isinstance(item, dict)
        ][:120],
        ns_bundle_groups=[
            _ns_group(item)
            for item in data.get("ns_bundle_groups") or []
            if isinstance(item, dict)
        ][:80],
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or [] if item],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static resource-surface inventory only; no live instrumentation, account data, credentials, or online protocol data is included",
            "resource-cache files are represented by metadata, first-byte magic samples, counts, and repo-portable relative paths only",
            "LocalPersistentData outside assets/bundles remains aggregate-only or skipped",
            "no decoded gameplay knowledge is promoted from this artifact",
        ],
    )


def write_client_resource_surface_gap_scan_report(
    report: ClientResourceSurfaceGapScanReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _root_group(raw: dict[str, Any]) -> ResourceRootGroup:
    return ResourceRootGroup(
        root=_portable_rel(str(raw.get("root") or "unknown")),
        classification=str(raw.get("classification") or "unknown"),
        file_count=int(raw.get("file_count") or 0),
        total_bytes=int(raw.get("total_bytes") or 0),
        extension_counts=_int_dict(_safe_map(raw.get("extension_counts"))),
        sample_rel_paths=[_portable_rel(str(item)) for item in raw.get("sample_rel_paths") or []],
    )


def _magic_sample(raw: dict[str, Any]) -> ResourceMagicSample:
    return ResourceMagicSample(
        rel_path=_portable_rel(str(raw.get("rel_path") or "unknown")),
        size=int(raw.get("size") or 0),
        suffix=str(raw.get("suffix") or ""),
        classification_reason=str(raw.get("classification_reason") or ""),
        magic_hex=str(raw.get("magic_hex") or "")[:128],
        magic_ascii=str(raw.get("magic_ascii") or "")[:64],
        evidence_ref=str(raw.get("evidence_ref") or "NSLG_CLIENT_RESOURCE_SURFACE:missing"),
    )


def _ns_group(raw: dict[str, Any]) -> NsBundleGroup:
    samples = []
    for item in raw.get("sample_files") or []:
        if not isinstance(item, dict):
            continue
        sample = _sanitize_map(item)
        if sample.get("rel_path"):
            sample["rel_path"] = _portable_rel(str(sample["rel_path"]))
        if sample.get("magic_hex_prefix"):
            sample["magic_hex_prefix"] = str(sample["magic_hex_prefix"])[:32]
        samples.append(sample)
    return NsBundleGroup(
        group=str(raw.get("group") or "unknown"),
        file_count=int(raw.get("file_count") or 0),
        total_bytes=int(raw.get("total_bytes") or 0),
        largest_file_bytes=int(raw.get("largest_file_bytes") or 0),
        sample_files=samples[:16],
        evidence_ref=str(raw.get("evidence_ref") or "NSLG_CLIENT_RESOURCE_SURFACE:missing"),
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
    for anchor in ("LocalPersistentData", "com.bilibili.nslg_Data"):
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
