from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_route_trace_batch.v1"
SOURCE_SITE = "nslg_client_gameassembly_trace"
SOURCE_URL = "local-nslg-client-gameassembly-trace"

_ROUND_RE = re.compile(r"_round(\d+)\.json$")
_KNOWN_ARTIFACT_NAMES = (
    "gameassembly_anchor_trace_round42.json",
    "gameassembly_global_metadata_trace_round71.json",
    "gameassembly_global_metadata_xref_function_triage_round105.json",
    "gameassembly_metadata_assetbundle_xrefs_round123.json",
    "gameassembly_assetbundle_neighborhood_round124.json",
    "gameassembly_textasset_loadbuffer_correlation_round160.json",
)


class GameAssemblyRouteTraceRecord(BaseModel):
    evidence_ref: str = Field(min_length=1)
    round: int = Field(ge=0)
    artifact_kind: str = Field(min_length=1)
    artifact_files: list[str] = Field(default_factory=list)
    status: str = Field(min_length=1)
    publish_readiness: str = Field(min_length=1)
    slice: str | None = None
    binary_name: str = "GameAssembly.dll"
    binary_sha256: str | None = None
    target_string_count: int = 0
    code_ref_count: int = 0
    function_ref_count: int = 0
    route_signal_function_count: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    target_strings: list[dict[str, Any]] = Field(default_factory=list)
    focus_functions: list[dict[str, Any]] = Field(default_factory=list)
    verdict: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class GameAssemblyRouteTraceBatch(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    binary_name: str = "GameAssembly.dll"
    artifact_count: int = 0
    round_range: dict[str, int | None] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    artifact_kind_counts: dict[str, int] = Field(default_factory=dict)
    route_signal_record_count: int = 0
    total_target_strings: int = 0
    total_code_refs: int = 0
    total_function_refs: int = 0
    evidence_refs: list[str] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    records: list[GameAssemblyRouteTraceRecord] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_gameassembly_route_trace_batch(
    *,
    input_dir: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> GameAssemblyRouteTraceBatch:
    generated_at = generated_at or datetime.now(timezone.utc)
    paths = [
        input_dir / name
        for name in _KNOWN_ARTIFACT_NAMES
        if (input_dir / name).exists()
    ]
    records = [_record_from_json(path, source_id=source_id) for path in paths]
    records = [record for record in records if record is not None]
    rounds = [record.round for record in records]
    status_counts = Counter(record.status for record in records)
    kind_counts = Counter(record.artifact_kind for record in records)
    route_signal_records = [
        record for record in records if record.route_signal_function_count > 0
    ]
    evidence_refs = [record.evidence_ref for record in records]
    total_target_strings = sum(record.target_string_count for record in records)
    total_code_refs = sum(record.code_ref_count for record in records)
    total_function_refs = sum(record.function_ref_count for record in records)
    return GameAssemblyRouteTraceBatch(
        source_id=source_id,
        generated_at=generated_at,
        artifact_count=len(records),
        round_range={"min": min(rounds) if rounds else None, "max": max(rounds) if rounds else None},
        status_counts=dict(sorted(status_counts.items())),
        artifact_kind_counts=dict(sorted(kind_counts.items())),
        route_signal_record_count=len(route_signal_records),
        total_target_strings=total_target_strings,
        total_code_refs=total_code_refs,
        total_function_refs=total_function_refs,
        evidence_refs=evidence_refs,
        route_conclusion=_route_conclusion(records),
        records=records,
        guardrails=[
            "offline/static GameAssembly evidence only; no live instrumentation or online protocol data is included",
            "external absolute paths are not persisted; only artifact filenames, RVAs, hashes, and evidence refs are stored",
            "GameAssembly route traces are decoder planning evidence, not reviewed game knowledge",
            "do not promote any fact until readable TextAsset/LuaScripts payloads are decoded and manually reviewed",
        ],
    )


def write_gameassembly_route_trace_batch(
    batch: GameAssemblyRouteTraceBatch,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(batch.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _record_from_json(
    path: Path,
    *,
    source_id: str,
) -> GameAssemblyRouteTraceRecord | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    round_number = _round_number(path)
    if round_number is None:
        raw_round = data.get("round")
        round_number = int(raw_round) if isinstance(raw_round, int) else 0
    artifact_kind = _artifact_kind(path)
    counts = _counts_for_artifact(data, artifact_kind)
    route_signal_count = counts.get("route_signal_function_count", 0)
    target_string_count = counts.get("target_string_count", 0)
    code_ref_count = counts.get("code_ref_count", 0)
    function_ref_count = counts.get("function_ref_count", 0)
    status = (
        "needs_review_route_signal"
        if route_signal_count > 0
        else _status_for_artifact(artifact_kind, data)
    )
    return GameAssemblyRouteTraceRecord(
        evidence_ref=f"NSLG_GAMEASSEMBLY_TRACE:{source_id}:round={round_number}:kind={artifact_kind}",
        round=round_number,
        artifact_kind=artifact_kind,
        artifact_files=_artifact_filenames(path),
        status=status,
        publish_readiness="not_publishable_static_evidence",
        slice=str(data.get("slice") or ""),
        binary_sha256=_binary_sha256(data),
        target_string_count=target_string_count,
        code_ref_count=code_ref_count,
        function_ref_count=function_ref_count,
        route_signal_function_count=route_signal_count,
        counts=counts,
        target_strings=_target_strings(data)[:24],
        focus_functions=_focus_functions(data)[:24],
        verdict=_verdict_lines(data),
        blockers=_blockers_for_artifact(data, artifact_kind, route_signal_count),
        next_actions=_next_actions(data, artifact_kind),
    )


def _route_conclusion(records: list[GameAssemblyRouteTraceRecord]) -> dict[str, Any]:
    route_signal_records = [record for record in records if record.route_signal_function_count > 0]
    textasset = next(
        (record for record in records if record.artifact_kind == "textasset_loadbuffer_correlation"),
        None,
    )
    return {
        "route_signal_records": len(route_signal_records),
        "textasset_loadbuffer_bridge_proven": bool(
            textasset and textasset.route_signal_function_count > 0
        ),
        "strongest_current_signal": (
            "static GameAssembly string inventory confirms TextAsset::get_bytes and xluaL_loadbuffer names, "
            "but current exact-ref scan does not prove a bridge between them"
        ),
        "search_policy": (
            "keep GameAssembly as decoder routing evidence; prioritize NEP2 InitLuaScriptsScan or a "
            "runtime-independent TextAsset payload decoder before promoting any knowledge"
        ),
        "safe_for_publish": False,
        "publishable_knowledge_entries": 0,
    }


def _artifact_kind(path: Path) -> str:
    name = path.name
    if "textasset_loadbuffer_correlation" in name:
        return "textasset_loadbuffer_correlation"
    if "anchor_trace" in name:
        return "xlua_global_metadata_anchor_trace"
    if "global_metadata_trace" in name:
        return "global_metadata_trace"
    if "global_metadata_xref_function_triage" in name:
        return "global_metadata_xref_function_triage"
    if "metadata_assetbundle_xrefs" in name:
        return "metadata_assetbundle_xrefs"
    if "assetbundle_neighborhood" in name:
        return "assetbundle_neighborhood"
    return "gameassembly_static_trace"


def _status_for_artifact(artifact_kind: str, data: dict[str, Any]) -> str:
    if artifact_kind in {
        "textasset_loadbuffer_correlation",
        "global_metadata_xref_function_triage",
        "assetbundle_neighborhood",
    }:
        return "negative_route_correlation"
    if _verdict_lines(data) or _focus_functions(data):
        return "static_trace_seed"
    return "evidence_inventory"


def _counts_for_artifact(data: dict[str, Any], artifact_kind: str) -> dict[str, int]:
    counts = _int_dict(data.get("counts") or {})
    if artifact_kind == "textasset_loadbuffer_correlation":
        return counts
    if artifact_kind == "xlua_global_metadata_anchor_trace":
        return {
            "pdata_function_count": int(data.get("pdata_function_count") or 0),
            "watched_string_count": len(data.get("watched_string_rvas") or {}),
            "hit_count": len(data.get("hits") or []),
            "target_string_count": len(data.get("watched_string_rvas") or {}),
            "code_ref_count": len(data.get("hits") or []),
            "function_ref_count": len(
                {
                    str((hit.get("containing_function") or {}).get("begin"))
                    for hit in data.get("hits") or []
                    if isinstance(hit, dict)
                }
            ),
            "route_signal_function_count": 0,
        }
    if artifact_kind == "global_metadata_trace":
        global_metadata = data.get("global_metadata") or {}
        return {
            "keyword_hits": len(data.get("keyword_hits") or []),
            "data_refs_to_keyword_strings": len(data.get("data_refs_to_keyword_strings") or []),
            "code_refs": len(data.get("code_refs") or []),
            "top_xref_candidates": len(data.get("top_xref_candidates") or []),
            "top_block_candidates": len(data.get("top_block_candidates") or []),
            "global_metadata_size": int(global_metadata.get("size") or 0),
            "target_string_count": len(data.get("keyword_hits") or []),
            "code_ref_count": len(data.get("code_refs") or []),
            "function_ref_count": len(data.get("top_xref_candidates") or []),
            "route_signal_function_count": 0,
        }
    if artifact_kind == "global_metadata_xref_function_triage":
        return {
            "focus_functions": len(data.get("focus_functions") or []),
            "direct_callers": len(data.get("direct_callers") or []),
            "direct_caller_summaries": len(data.get("direct_caller_summaries") or []),
            "direct_callee_summaries": len(data.get("direct_callee_summaries") or []),
            "hard_risky_rows": len(data.get("hard_risky_rows") or []),
            "soft_16byte_rows": len(data.get("soft_16byte_rows") or []),
            "target_string_count": _count_strings(data.get("focus_functions") or []),
            "code_ref_count": len(data.get("focus_functions") or []),
            "function_ref_count": len(data.get("focus_functions") or []),
            "route_signal_function_count": len(data.get("hard_risky_rows") or []),
        }
    if artifact_kind == "metadata_assetbundle_xrefs":
        functions = data.get("ranked_functions") or data.get("functions") or []
        strings = data.get("strings") or data.get("needle_strings") or []
        return {
            "needle_strings": len(strings),
            "ranked_functions": len(functions),
            "target_string_count": len(strings),
            "code_ref_count": int(data.get("string_xref_count") or len(data.get("string_xrefs") or [])),
            "function_ref_count": len(functions),
            "route_signal_function_count": 0,
        }
    if artifact_kind == "assetbundle_neighborhood":
        targets = data.get("targets") or []
        return {
            "targets": len(targets),
            "target_string_count": len(targets),
            "code_ref_count": sum(len((target.get("callers") or [])) for target in targets if isinstance(target, dict)),
            "function_ref_count": len(targets),
            "route_signal_function_count": 0,
        }
    return {"route_signal_function_count": 0}


def _target_strings(data: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(data.get("target_strings"), list):
        return [item for item in data["target_strings"] if isinstance(item, dict)]
    if isinstance(data.get("watched_string_rvas"), dict):
        return [
            {"rva": str(rva), "label": str(label)}
            for rva, label in data["watched_string_rvas"].items()
        ]
    return []


def _focus_functions(data: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(data.get("functions"), list):
        return [item for item in data["functions"] if isinstance(item, dict)]
    if isinstance(data.get("focus_functions"), list):
        return [item for item in data["focus_functions"] if isinstance(item, dict)]
    if isinstance(data.get("targets"), list):
        return [item for item in data["targets"] if isinstance(item, dict)]
    return []


def _verdict_lines(data: dict[str, Any]) -> list[str]:
    for key in ["verdict", "summary", "interpretation"]:
        value = data.get(key)
        if isinstance(value, list):
            return [str(item) for item in value if item is not None]
    return []


def _blockers_for_artifact(
    data: dict[str, Any],
    artifact_kind: str,
    route_signal_count: int,
) -> list[str]:
    blockers = [str(item) for item in data.get("blockers") or []]
    if route_signal_count > 0:
        blockers.append("route signal found; manual reverse-engineering review required")
    if not blockers:
        blockers.extend(
            [
                "static GameAssembly route evidence is not readable game knowledge",
                f"{artifact_kind} has not produced a reviewed payload decoder",
            ]
        )
    return _unique_strs(blockers)


def _next_actions(data: dict[str, Any], artifact_kind: str) -> list[str]:
    actions = [str(item) for item in data.get("next") or []]
    next_step = data.get("next_step")
    if next_step:
        actions.append(str(next_step))
    if not actions:
        actions = [
            "use this GameAssembly trace only as decoder planning evidence",
            "recover a readable TextAsset/LuaScripts payload decoder before staging knowledge",
        ]
    if artifact_kind == "textasset_loadbuffer_correlation":
        actions.append("prefer NEP2 InitLuaScriptsScan or runtime-independent TextAsset payload decoder recovery next")
    return _unique_strs(actions)


def _binary_sha256(data: dict[str, Any]) -> str | None:
    inputs = data.get("inputs") if isinstance(data.get("inputs"), dict) else {}
    return data.get("binary_sha256") or inputs.get("binary_sha256") or inputs.get("sha256")


def _artifact_filenames(path: Path) -> list[str]:
    names = [path.name]
    for suffix in [".md", ".asm"]:
        peer = path.with_suffix(suffix)
        if peer.exists():
            names.append(peer.name)
    return names


def _round_number(path: Path) -> int | None:
    match = _ROUND_RE.search(path.name)
    return int(match.group(1)) if match else None


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(raw or 0) for key, raw in value.items() if _is_int_like(raw)}


def _is_int_like(value: Any) -> bool:
    try:
        int(value)
        return True
    except (TypeError, ValueError):
        return False


def _count_strings(values: list[Any]) -> int:
    total = 0
    for value in values:
        if isinstance(value, dict):
            total += len(value.get("strings") or [])
    return total


def _unique_strs(values: list[str]) -> list[str]:
    seen = set()
    out = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        out.append(value)
    return out
