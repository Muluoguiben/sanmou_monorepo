from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.textasset_payload_owner_trace.v1"
SOURCE_SITE = "nslg_client_textasset_payload_owner_trace"
SOURCE_URL = "local-nslg-client-textasset-payload-owner-trace"


class TextAssetPayloadOwnerInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    sha256: str = ""
    missing: bool = False


class TextAssetPayloadOwnerTraceReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[TextAssetPayloadOwnerInputArtifact] = Field(default_factory=list)
    prior_context: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    term_kind_counts: dict[str, int] = Field(default_factory=dict)
    module_records: list[dict[str, Any]] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_textasset_payload_owner_trace_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> TextAssetPayloadOwnerTraceReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return TextAssetPayloadOwnerTraceReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        prior_context=_safe_map(data.get("prior_context")),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        term_kind_counts=_int_dict(_safe_map(data.get("term_kind_counts"))),
        module_records=[
            _module_summary(item) for item in data.get("module_records") or []
        ][:12],
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:160],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static PE and extracted CAB metadata scan only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, module names, RVAs, sanitized asset paths/stems, counts, and summaries are stored",
            "TextAsset/LuaScripts string or code-reference ownership is route evidence only, not payload-buffer ownership proof",
            "no decoded LuaScripts/gameplay configuration is promoted from this artifact",
        ],
    )


def write_textasset_payload_owner_trace_report(
    report: TextAssetPayloadOwnerTraceReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> TextAssetPayloadOwnerInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return TextAssetPayloadOwnerInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _module_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "module": Path(str(raw.get("module") or "unknown").replace("\\", "/")).name,
        "counts": _int_dict(_safe_map(raw.get("counts"))),
        "term_kind_counts": _int_dict(_safe_map(raw.get("term_kind_counts"))),
        "term_encoding_counts": _int_dict(_safe_map(raw.get("term_encoding_counts"))),
        "term_hit_samples": [
            _term_hit_summary(item) for item in raw.get("term_hit_samples") or []
        ][:40],
        "code_ref_samples": [
            _code_ref_summary(item) for item in raw.get("code_ref_samples") or []
        ][:40],
        "candidate_functions": [
            _candidate_summary(item) for item in raw.get("candidate_functions") or []
        ][:24],
    }


def _term_hit_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "kind": str(raw.get("kind") or ""),
        "value": str(raw.get("value") or ""),
        "encoding": str(raw.get("encoding") or ""),
        "rva": str(raw.get("rva") or ""),
        "section": str(raw.get("section") or ""),
    }


def _code_ref_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "site": str(raw.get("site") or ""),
        "owner_function": _safe_map(raw.get("owner_function")),
        "ref_kind": str(raw.get("ref_kind") or ""),
        "target_rva": str(raw.get("target_rva") or ""),
        "target_kind": str(raw.get("target_kind") or ""),
        "target_value": str(raw.get("target_value") or ""),
        "target_encoding": str(raw.get("target_encoding") or ""),
    }


def _candidate_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "evidence_ref": str(raw.get("evidence_ref") or ""),
        "function": _safe_map(raw.get("function")),
        "verdict": str(raw.get("verdict") or ""),
        "score": int(raw.get("score") or 0),
        "target_kind_counts": _int_dict(_safe_map(raw.get("target_kind_counts"))),
        "target_values": [str(item) for item in raw.get("target_values") or []][:24],
        "code_ref_count": int(raw.get("code_ref_count") or 0),
        "import_names": [str(item) for item in raw.get("import_names") or []][:32],
        "import_class_counts": _int_dict(_safe_map(raw.get("import_class_counts"))),
        "crypto_mnemonics": [str(item) for item in raw.get("crypto_mnemonics") or []],
        "logic_mnemonics": _int_dict(_safe_map(raw.get("logic_mnemonics"))),
        "interesting_imms": _int_dict(_safe_map(raw.get("interesting_imms"))),
        "memory_write_count": int(raw.get("memory_write_count") or 0),
        "loop_or_branch_count": int(raw.get("loop_or_branch_count") or 0),
        "has_exact_asset_provenance": bool(raw.get("has_exact_asset_provenance")),
        "has_luascripts_route_ref": bool(raw.get("has_luascripts_route_ref")),
        "has_textasset_route_ref": bool(raw.get("has_textasset_route_ref")),
        "has_memory_or_copy_signal": bool(raw.get("has_memory_or_copy_signal")),
        "has_file_import_signal": bool(raw.get("has_file_import_signal")),
        "has_dynamic_loader_signal": bool(raw.get("has_dynamic_loader_signal")),
        "has_crypto_signal": bool(raw.get("has_crypto_signal")),
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
