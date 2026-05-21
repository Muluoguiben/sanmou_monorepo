from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.nep2_provenance_closure_batch.v1"
SOURCE_SITE = "nslg_client_nep2_provenance"
SOURCE_URL = "local-nslg-client-nep2-provenance"

_ROUND_RE = re.compile(r"_round(\d+)\.json$")
_NEXT_RVA_RE = re.compile(
    r"(?:next highest|next unclosed)[^\n`]*`(0x[0-9a-fA-F]+)`",
    re.IGNORECASE,
)


class Nep2ProvenanceClosureRecord(BaseModel):
    evidence_ref: str = Field(min_length=1)
    round: int = Field(ge=0)
    target_rva: str = Field(min_length=1)
    function: dict[str, str] = Field(default_factory=dict)
    artifact_files: list[str] = Field(default_factory=list)
    closure_status: str = Field(min_length=1)
    strong_provenance_found: bool = False
    target_verdict: str | None = None
    pointer_ref_classification: str | None = None
    pointer_ref_count: int = 0
    pointer_owner_signal_count: int = 0
    direct_caller_count: int = 0
    direct_callee_count: int = 0
    selected_node_count: int = 0
    interesting_node_count: int = 0
    path_counts: dict[str, int] = Field(default_factory=dict)
    instruction_counts: dict[str, int] = Field(default_factory=dict)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class Nep2ProvenanceClosureBatch(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    binary_name: str = "NEP2.dll"
    artifact_count: int = 0
    round_range: dict[str, int | None] = Field(default_factory=dict)
    closure_status_counts: dict[str, int] = Field(default_factory=dict)
    target_verdict_counts: dict[str, int] = Field(default_factory=dict)
    pointer_ref_classification_counts: dict[str, int] = Field(default_factory=dict)
    closed_rvas: list[str] = Field(default_factory=list)
    next_unclosed_shape_lead: str | None = None
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    records: list[Nep2ProvenanceClosureRecord] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_nep2_provenance_closure_batch(
    *,
    input_dir: Path,
    source_id: str,
    analysis_log_path: Path | None = None,
    generated_at: datetime | None = None,
) -> Nep2ProvenanceClosureBatch:
    generated_at = generated_at or datetime.now(timezone.utc)
    records = [
        _record_from_json(path, source_id=source_id)
        for path in sorted(input_dir.glob("nep2_*_provenance_closure_round*.json"), key=_round_sort_key)
    ]
    records = [record for record in records if record is not None]
    closure_counts = Counter(record.closure_status for record in records)
    verdict_counts = Counter(record.target_verdict or "unknown" for record in records)
    pointer_counts = Counter(record.pointer_ref_classification or "unknown" for record in records)
    rounds = [record.round for record in records]
    closed_rvas = [
        record.target_rva
        for record in records
        if record.closure_status == "closed_no_file_buffer_provenance"
    ]
    next_target = _next_unclosed_shape_lead(analysis_log_path) if analysis_log_path else None
    return Nep2ProvenanceClosureBatch(
        source_id=source_id,
        generated_at=generated_at,
        artifact_count=len(records),
        round_range={"min": min(rounds) if rounds else None, "max": max(rounds) if rounds else None},
        closure_status_counts=dict(sorted(closure_counts.items())),
        target_verdict_counts=dict(sorted(verdict_counts.items())),
        pointer_ref_classification_counts=dict(sorted(pointer_counts.items())),
        closed_rvas=closed_rvas,
        next_unclosed_shape_lead=next_target,
        route_conclusion=_route_conclusion(records, next_target),
        records=records,
        guardrails=[
            "offline/static provenance closure only; no live instrumentation or online protocol data is included",
            "external artifact absolute paths are not persisted; only artifact filenames and evidence refs are stored",
            "closed RVA records are negative evidence for decoder search routing, not game knowledge entries",
            "do not promote any item into knowledge_sources until readable payloads are decoded and reviewed",
        ],
    )


def write_nep2_provenance_closure_batch(
    batch: Nep2ProvenanceClosureBatch,
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
) -> Nep2ProvenanceClosureRecord | None:
    data = json.loads(path.read_text(encoding="utf-8"))
    round_number = _round_number(path)
    if round_number is None:
        raw_round = data.get("round")
        round_number = int(raw_round) if isinstance(raw_round, int) else 0
    target = data.get("target") or {}
    target_rva = str(target.get("rva") or "")
    if not target_rva:
        return None

    function = target.get("function") if isinstance(target.get("function"), dict) else {}
    inspected = data.get("target_inspected") or {}
    provenance = data.get("provenance") or {}
    paths = data.get("paths") or {}
    path_counts = {key: len(value or []) for key, value in paths.items() if isinstance(value, list)}
    interesting = provenance.get("interesting") if isinstance(provenance.get("interesting"), list) else []
    strong_provenance = _strong_provenance_found(data, interesting, path_counts)
    closure_status = (
        "needs_review_provenance_signal"
        if strong_provenance or interesting or any(path_counts.values())
        else "closed_no_file_buffer_provenance"
    )
    artifact_files = _artifact_filenames(path)
    blockers = _blockers_for_record(data, closure_status)
    next_actions = _str_list(data.get("next"))
    return Nep2ProvenanceClosureRecord(
        evidence_ref=f"NSLG_NEP2_PROVENANCE:{source_id}:round={round_number}:rva={target_rva}",
        round=round_number,
        target_rva=target_rva,
        function={str(key): str(value) for key, value in function.items()},
        artifact_files=artifact_files,
        closure_status=closure_status,
        strong_provenance_found=strong_provenance,
        target_verdict=inspected.get("verdict"),
        pointer_ref_classification=data.get("pointer_ref_classification"),
        pointer_ref_count=len(data.get("pointer_refs") or []),
        pointer_owner_signal_count=int(data.get("pointer_owner_signal_count") or 0),
        direct_caller_count=int(target.get("direct_caller_count") or 0),
        direct_callee_count=int(target.get("direct_callee_count") or 0),
        selected_node_count=int((data.get("selected_nodes") or {}).get("node_count") or 0),
        interesting_node_count=len(interesting),
        path_counts=path_counts,
        instruction_counts={
            str(key): int(value or 0)
            for key, value in (inspected.get("counts") or {}).items()
            if isinstance(value, int)
        },
        blockers=blockers,
        next_actions=next_actions,
    )


def _route_conclusion(
    records: list[Nep2ProvenanceClosureRecord],
    next_target: str | None,
) -> dict[str, Any]:
    closed = [record for record in records if record.closure_status == "closed_no_file_buffer_provenance"]
    needs_review = [
        record for record in records if record.closure_status == "needs_review_provenance_signal"
    ]
    return {
        "closed_shape_only_leads": len(closed),
        "needs_review_signal_leads": len(needs_review),
        "strongest_negative_signal": (
            "bounded caller/callee and pointer-ref provenance found no CAB, SerializedFile, "
            "global-metadata, AssetBundle, LuaScripts payload, keyword/import, or file-buffer owner path"
        ),
        "search_policy": (
            "stop broad shape-only scanning; continue only with caller/callee provenance, "
            "keyword/import ownership, or file-buffer/asset owner evidence"
        ),
        "next_unclosed_shape_lead": next_target,
        "safe_for_publish": False,
        "publishable_knowledge_entries": 0,
    }


def _blockers_for_record(data: dict[str, Any], closure_status: str) -> list[str]:
    if closure_status == "needs_review_provenance_signal":
        return ["provenance signal found; manual reverse-engineering review required"]
    interpretation = _str_list(data.get("interpretation"))
    if interpretation:
        return interpretation[:4]
    return [
        "no CAB/Serialized/global-metadata/AssetBundle/file-buffer provenance reaches target",
        "shape-only byte/table/vector loop candidate is not a protector-quality lead",
    ]


def _artifact_filenames(path: Path) -> list[str]:
    names = [path.name]
    for suffix in [".md", ".asm"]:
        peer = path.with_suffix(suffix)
        if peer.exists():
            names.append(peer.name)
    return names


def _strong_provenance_found(
    data: dict[str, Any],
    interesting: list[Any],
    path_counts: dict[str, int],
) -> bool:
    for line in _str_list(data.get("summary")):
        if line.lower().startswith("strong provenance found:"):
            return line.rsplit(":", 1)[-1].strip().lower() == "true"
    return bool(interesting or any(path_counts.values()))


def _next_unclosed_shape_lead(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    text = path.read_text(encoding="utf-8", errors="replace")
    matches = _NEXT_RVA_RE.findall(text)
    return matches[-1].lower() if matches else None


def _round_sort_key(path: Path) -> tuple[int, str]:
    round_number = _round_number(path)
    return (round_number if round_number is not None else 0, path.name)


def _round_number(path: Path) -> int | None:
    match = _ROUND_RE.search(path.name)
    return int(match.group(1)) if match else None


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item)]
