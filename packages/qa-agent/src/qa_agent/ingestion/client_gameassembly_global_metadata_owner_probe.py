from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_global_metadata_owner_probe.v1"
SOURCE_SITE = "nslg_client_gameassembly_global_metadata_owner_probe"
SOURCE_URL = "local-nslg-client-gameassembly-global-metadata-owner-probe"


class GameAssemblyGlobalMetadataOwnerInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    sha256: str = ""
    missing: bool = False


class GameAssemblyGlobalMetadataOwnerProbeReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[GameAssemblyGlobalMetadataOwnerInputArtifact] = Field(
        default_factory=list
    )
    gameassembly_summary: dict[str, Any] = Field(default_factory=dict)
    selection_policy: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    targets: list[dict[str, Any]] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_gameassembly_global_metadata_owner_probe_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> GameAssemblyGlobalMetadataOwnerProbeReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return GameAssemblyGlobalMetadataOwnerProbeReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        gameassembly_summary=_file_summary(_safe_map(data.get("gameassembly_summary"))),
        selection_policy=_simple_map(_safe_map(data.get("selection_policy"))),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        targets=[_target_summary(item) for item in data.get("targets") or []][:40],
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly direct-call context scan only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, hashes, RVAs, counts, and sanitized summaries are stored",
            "global-metadata string references are route evidence only until file-buffer ownership or decoded metadata validates the owner",
            "no decoded protected metadata, LuaScripts payload, or gameplay knowledge is promoted from this artifact",
        ],
    )


def write_gameassembly_global_metadata_owner_probe_report(
    report: GameAssemblyGlobalMetadataOwnerProbeReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> GameAssemblyGlobalMetadataOwnerInputArtifact:
    file_name = str(raw.get("file_name") or "unknown").replace("\\", "/")
    return GameAssemblyGlobalMetadataOwnerInputArtifact(
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
        "contexts": [_context_summary(item) for item in raw.get("contexts") or []][:12],
        "verdict": str(raw.get("verdict") or ""),
        "counts": _int_dict(_safe_map(raw.get("counts"))),
        "imports": [_event_summary(item) for item in raw.get("imports") or []][:24],
        "metadata_string_refs": [
            _string_ref_summary(item) for item in raw.get("metadata_string_refs") or []
        ][:24],
        "metadata_candidate_refs": [
            _candidate_ref_summary(item)
            for item in raw.get("metadata_candidate_refs") or []
        ][:24],
        "constants": [_event_summary(item) for item in raw.get("constants") or []][:24],
        "direct_caller_count": int(raw.get("direct_caller_count") or 0),
        "direct_callee_count": int(raw.get("direct_callee_count") or 0),
        "evidence_ref": str(raw.get("evidence_ref") or ""),
    }


def _context_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "seed_rva": raw.get("seed_rva"),
        "seed_label": raw.get("seed_label"),
        "role": raw.get("role"),
        "depth": int(raw.get("depth") or 0),
        "path_length": int(raw.get("path_length") or 0),
    }


def _event_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    out: dict[str, Any] = {}
    for key in ("rva", "target_rva", "import", "import_name", "class", "value", "label", "text"):
        if key in raw:
            out[key] = raw.get(key)
    return out


def _string_ref_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "rva": raw.get("rva"),
        "target_rva": raw.get("target_rva"),
        "terms": [str(item) for item in raw.get("terms") or []],
        "text": raw.get("text"),
    }


def _candidate_ref_summary(raw: Any) -> dict[str, Any]:
    if not isinstance(raw, dict):
        return {}
    return {
        "rva": raw.get("rva"),
        "target_rva": raw.get("target_rva"),
        "matches": [_simple_map(item) for item in raw.get("matches") or [] if isinstance(item, dict)][:12],
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
