from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.nep2_vector_candidate_provenance.v1"
SOURCE_SITE = "nslg_client_nep2_vector_candidate_provenance"
SOURCE_URL = "local-nslg-client-nep2-vector-candidate-provenance"


class Nep2VectorCandidateInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class Nep2VectorCandidateProvenanceReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[Nep2VectorCandidateInputArtifact] = Field(default_factory=list)
    nep2_file: dict[str, Any] = Field(default_factory=dict)
    selection_policy: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_nep2_vector_candidate_provenance_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> Nep2VectorCandidateProvenanceReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return Nep2VectorCandidateProvenanceReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        nep2_file=_file_summary(_safe_map(data.get("nep2_file"))),
        selection_policy=_simple_map(_safe_map(data.get("selection_policy"))),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        targets=[_target_summary(item) for item in data.get("targets") or []][:32],
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static NEP2 callgraph and function-feature scan only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, hashes, RVAs, counts, and sanitized summaries are stored",
            "vector/16-byte/helper features are route evidence only and require payload-buffer provenance before decoder promotion",
            "no decoded global-metadata, LuaScripts payload, or gameplay knowledge is promoted from this artifact",
        ],
    )


def write_nep2_vector_candidate_provenance_report(
    report: Nep2VectorCandidateProvenanceReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> Nep2VectorCandidateInputArtifact:
    file_name = str(raw.get("file_name") or "unknown").replace("\\", "/")
    return Nep2VectorCandidateInputArtifact(
        file_name=Path(file_name).name,
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _file_summary(raw: dict[str, Any]) -> dict[str, Any]:
    out = _simple_map(raw)
    if out.get("file_name"):
        out["file_name"] = Path(str(out["file_name"]).replace("\\", "/")).name
    return out


def _target_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "target_rva": str(raw.get("target_rva") or ""),
        "function": _safe_map(raw.get("function")),
        "verdict": str(raw.get("verdict") or ""),
        "selection": _simple_map(_safe_map(raw.get("selection"))),
        "counts": _int_dict(_safe_map(raw.get("counts"))),
        "imports": [_event_summary(item) for item in raw.get("imports") or []][:24],
        "keyword_refs": [_keyword_summary(item) for item in raw.get("keyword_refs") or []][:24],
        "constants": [_simple_map(_safe_map(item)) for item in raw.get("constants") or []][:32],
        "large_immediates": [
            _simple_map(_safe_map(item)) for item in raw.get("large_immediates") or []
        ][:16],
        "direct_call_count": len(raw.get("direct_calls") or []),
        "direct_calls": [
            _simple_map(_safe_map(item)) for item in raw.get("direct_calls") or []
        ][:24],
        "direct_caller_count": int(raw.get("direct_caller_count") or 0),
        "direct_callee_count": int(raw.get("direct_callee_count") or 0),
        "direct_callers": [
            _simple_map(_safe_map(item)) for item in raw.get("direct_callers") or []
        ][:24],
        "direct_callees": [
            _simple_map(_safe_map(item)) for item in raw.get("direct_callees") or []
        ][:24],
        "provenance_linked": bool(raw.get("provenance_linked")),
        "provenance_paths": [
            _simple_map(_safe_map(item)) for item in raw.get("provenance_paths") or []
        ][:8],
        "evidence_ref": str(raw.get("evidence_ref") or ""),
    }


def _event_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("rva", "import", "import_name", "class", "text"):
        if key in raw:
            out[key] = raw.get(key)
    return out


def _keyword_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "rva": raw.get("rva"),
        "target_rva": raw.get("target_rva"),
        "terms": [str(item) for item in raw.get("terms") or []],
        "text": raw.get("text"),
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
