from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_initializer_dispatch_trace.v1"
SOURCE_SITE = "nslg_client_gameassembly_initializer_dispatch_trace"
SOURCE_URL = "local-nslg-client-gameassembly-initializer-dispatch-trace"


class InitializerDispatchInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class InitializerDispatchTraceReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[InitializerDispatchInputArtifact] = Field(default_factory=list)
    gameassembly: dict[str, Any] = Field(default_factory=dict)
    target_summary: dict[str, Any] = Field(default_factory=dict)
    roots: dict[str, Any] = Field(default_factory=dict)
    scan_counts: dict[str, int] = Field(default_factory=dict)
    goal_function_summary: dict[str, Any] = Field(default_factory=dict)
    bounded_path_report: dict[str, Any] = Field(default_factory=dict)
    nonexec_function_pointer_hits: dict[str, Any] = Field(default_factory=dict)
    dispatcher_candidates: list[dict[str, Any]] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_initializer_dispatch_trace_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> InitializerDispatchTraceReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return InitializerDispatchTraceReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        gameassembly=_gameassembly(_safe_map(data.get("gameassembly"))),
        target_summary=_target_summary(_safe_map(data.get("target_summary"))),
        roots=_roots(_safe_map(data.get("roots"))),
        scan_counts=_int_dict(_safe_map(data.get("scan_counts"))),
        goal_function_summary=_goal_function_summary(
            _safe_map(data.get("goal_function_summary"))
        ),
        bounded_path_report=_bounded_path_report(_safe_map(data.get("bounded_path_report"))),
        nonexec_function_pointer_hits=_nonexec_pointer_hits(
            _safe_map(data.get("nonexec_function_pointer_hits"))
        ),
        dispatcher_candidates=[
            _dispatcher_candidate(item)
            for item in data.get("dispatcher_candidates") or []
            if isinstance(item, dict)
        ][:24],
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly initializer dispatch trace only; no live instrumentation, account data, or online protocol data is included",
            "bounded direct-call trace is not proof of indirect runtime dispatch absence",
            "registration and metadata ownership remain unresolved until decoded metadata or proven init table ownership exists",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_initializer_dispatch_trace_report(
    report: InitializerDispatchTraceReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> InitializerDispatchInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return InitializerDispatchInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _gameassembly(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "file_name": str(raw.get("file_name") or ""),
        "size_bytes": int(raw.get("size_bytes") or 0),
        "sha256": str(raw.get("sha256") or ""),
        "entry_rva": str(raw.get("entry_rva") or ""),
        "pdata_function_count": int(raw.get("pdata_function_count") or 0),
        "export_count": int(raw.get("export_count") or 0),
    }


def _target_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_count": int(raw.get("target_count") or 0),
        "by_category": _int_dict(_safe_map(raw.get("by_category"))),
        "sample": [
            {
                "label": str(item.get("label") or ""),
                "category": str(item.get("category") or ""),
                "start": str(item.get("start") or ""),
                "end": str(item.get("end") or ""),
            }
            for item in raw.get("sample") or []
            if isinstance(item, dict)
        ][:32],
    }


def _roots(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "root_count": int(raw.get("root_count") or 0),
        "items": [
            {
                "label": str(item.get("label") or ""),
                "kind": str(item.get("kind") or ""),
                "rva": str(item.get("rva") or ""),
                "function": _function(_safe_map(item.get("function"))),
            }
            for item in raw.get("items") or []
            if isinstance(item, dict)
        ][:32],
    }


def _function(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "begin": str(raw.get("begin") or ""),
        "end": str(raw.get("end") or ""),
        "size": str(raw.get("size") or ""),
    }


def _goal_function_summary(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in (
        "registration_anchor_ref_functions",
        "metadata_candidate_ref_functions",
        "global_metadata_string_ref_functions",
    ):
        out[key] = [
            _goal_function(item) for item in raw.get(key) or [] if isinstance(item, dict)
        ][:16]
        out[f"{key}_count"] = int(raw.get(f"{key}_count") or len(out[key]))
    return out


def _goal_function(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "function": _function(_safe_map(raw.get("function"))),
        "instruction_count": int(raw.get("instruction_count") or 0),
        "direct_callee_count": int(raw.get("direct_callee_count") or 0),
        "direct_caller_count": int(raw.get("direct_caller_count") or 0),
        "indirect_branch_count": int(raw.get("indirect_branch_count") or 0),
        "target_ref_counts": _int_dict(_safe_map(raw.get("target_ref_counts"))),
        "target_ref_label_counts": _int_dict(_safe_map(raw.get("target_ref_label_counts"))),
        "target_refs": [
            {
                "insn_rva": str(item.get("insn_rva") or ""),
                "target_rva": str(item.get("target_rva") or ""),
                "mnemonic": str(item.get("mnemonic") or ""),
                "op_str": str(item.get("op_str") or ""),
                "target": {
                    "label": str((_safe_map(item.get("target"))).get("label") or ""),
                    "category": str((_safe_map(item.get("target"))).get("category") or ""),
                },
            }
            for item in raw.get("target_refs") or []
            if isinstance(item, dict)
        ][:12],
    }


def _bounded_path_report(raw: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key in (
        "registration_anchor_ref",
        "metadata_candidate_ref",
        "global_metadata_string_ref",
    ):
        item = _safe_map(raw.get(key))
        out[key] = {
            "goal_function_count": int(item.get("goal_function_count") or 0),
            "bounded_forward_path": _path(_safe_map(item.get("bounded_forward_path"))),
            "bounded_reverse_paths": [
                _path(path)
                for path in item.get("bounded_reverse_paths") or []
                if isinstance(path, dict)
            ][:16],
        }
    return out


def _path(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "found": bool(raw.get("found")),
        "depth": int(raw.get("depth")) if raw.get("depth") is not None else None,
        "path": [str(item) for item in raw.get("path") or []][:32],
    }


def _nonexec_pointer_hits(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "target_function_count": int(raw.get("target_function_count") or 0),
        "hit_count": int(raw.get("hit_count") or 0),
        "hits": [
            {
                "ref_rva": str(item.get("ref_rva") or ""),
                "ref_section": str(item.get("ref_section") or ""),
                "target_rva": str(item.get("target_rva") or ""),
                "target_label": str(item.get("target_label") or ""),
            }
            for item in raw.get("hits") or []
            if isinstance(item, dict)
        ][:80],
    }


def _dispatcher_candidate(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "function": _function(_safe_map(raw.get("function"))),
        "score": int(raw.get("score") or 0),
        "reasons": [str(item) for item in raw.get("reasons") or []][:12],
        "direct_callee_count": int(raw.get("direct_callee_count") or 0),
        "direct_caller_count": int(raw.get("direct_caller_count") or 0),
        "indirect_branch_count": int(raw.get("indirect_branch_count") or 0),
        "target_ref_counts": _int_dict(_safe_map(raw.get("target_ref_counts"))),
        "interesting_import_calls": _int_dict(_safe_map(raw.get("interesting_import_calls"))),
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
