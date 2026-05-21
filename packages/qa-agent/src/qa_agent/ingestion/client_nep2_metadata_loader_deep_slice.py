from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.nep2_global_metadata_loader_deep_slice.v1"
SOURCE_SITE = "nslg_client_nep2_global_metadata_loader_deep_slice"
SOURCE_URL = "local-nslg-client-nep2-global-metadata-loader-deep-slice"


class Nep2MetadataLoaderInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class Nep2MetadataLoaderDeepSliceReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[Nep2MetadataLoaderInputArtifact] = Field(default_factory=list)
    target_rvas: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    verdict_counts: dict[str, int] = Field(default_factory=dict)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_nep2_metadata_loader_deep_slice_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> Nep2MetadataLoaderDeepSliceReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return Nep2MetadataLoaderDeepSliceReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        target_rvas=[str(item) for item in data.get("target_rvas") or []],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        verdict_counts=_int_dict(_safe_map(data.get("verdict_counts"))),
        targets=[
            _target_summary(item)
            for item in data.get("targets") or []
            if isinstance(item, dict)
        ],
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static NEP2 deep-slice only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, hashes, target RVAs, counts, and sanitized summaries are stored",
            "closed helper functions are negative decoder-routing evidence and must not be promoted as gameplay knowledge",
            "metadata recovery requires file-buffer ownership plus standard IL2CPP header pairs and readable Assembly-CSharp/NSLGame strings",
        ],
    )


def write_nep2_metadata_loader_deep_slice_report(
    report: Nep2MetadataLoaderDeepSliceReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> Nep2MetadataLoaderInputArtifact:
    file_name = str(raw.get("file_name") or "unknown").replace("\\", "/")
    return Nep2MetadataLoaderInputArtifact(
        file_name=Path(file_name).name,
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _target_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_rva": str(raw.get("target_rva") or ""),
        "function": _safe_map(raw.get("function")),
        "verdict": str(raw.get("verdict") or ""),
        "counts": _int_dict(_safe_map(raw.get("counts"))),
        "imports_seen": [str(item) for item in raw.get("imports_seen") or []],
        "has_read_or_mapping_import": bool(raw.get("has_read_or_mapping_import")),
        "has_metadata_string_or_constant_ref": bool(
            raw.get("has_metadata_string_or_constant_ref")
        ),
        "directory_walker_signature": bool(raw.get("directory_walker_signature")),
        "file_status_helper_signature": bool(raw.get("file_status_helper_signature")),
        "string_refs": [_string_ref(item) for item in raw.get("string_refs") or []][:24],
        "metadata_keyword_hits": [
            _safe_map(item) for item in raw.get("metadata_keyword_hits") or []
        ][:24],
        "metadata_string_refs": [
            _safe_map(item) for item in raw.get("metadata_string_refs") or []
        ][:24],
        "constants": [_safe_map(item) for item in raw.get("constants") or []][:48],
        "size_accumulator_events": [
            _event_summary(item) for item in raw.get("size_accumulator_events") or []
        ][:12],
        "import_events": [_event_summary(item) for item in raw.get("import_events") or []][:24],
        "direct_callers": [_edge_summary(item) for item in raw.get("direct_callers") or []][:24],
        "direct_callees": [_safe_map(item) for item in raw.get("direct_callees") or []][:24],
        "data_pointer_refs": [
            _safe_map(item) for item in raw.get("data_pointer_refs") or []
        ][:24],
        "evidence_ref": str(raw.get("evidence_ref") or ""),
    }


def _string_ref(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    target = raw.get("target") if isinstance(raw.get("target"), dict) else {}
    return {
        "from_rva": raw.get("from_rva"),
        "text": raw.get("text"),
        "target": {
            "rva": target.get("rva"),
            "section": target.get("section"),
            "ascii": target.get("ascii"),
            "utf16le": target.get("utf16le"),
        },
    }


def _event_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("rva", "import", "class", "text", "label", "value"):
        if key in raw:
            out[key] = raw.get(key)
    if raw.get("context"):
        out["context"] = [str(item) for item in raw.get("context") or []][:16]
    return out


def _edge_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "site": raw.get("site"),
        "caller": _safe_map(raw.get("caller")),
        "callee": _safe_map(raw.get("callee")),
        "target_rva": raw.get("target_rva"),
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
