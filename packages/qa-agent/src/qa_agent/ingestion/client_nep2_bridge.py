from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.nep2_init_bridge.v1"
SOURCE_SITE = "nslg_client_nep2_init_bridge"
SOURCE_URL = "local-nslg-client-nep2-init-bridge"


class Nep2InitBridgeRecord(BaseModel):
    evidence_ref: str = Field(min_length=1)
    rva: str = Field(min_length=1)
    label: str = ""
    type_descriptor_rva: str = ""
    name_rva: str = ""
    code_pointers: list[dict[str, Any]] = Field(default_factory=list)
    status: str = Field(min_length=1)
    verdict: str = Field(min_length=1)


class Nep2InitBridgeCandidate(BaseModel):
    evidence_ref: str = Field(min_length=1)
    function_rva: str = Field(min_length=1)
    function_size: str = ""
    sources: list[str] = Field(default_factory=list)
    verdict: str = Field(min_length=1)
    score: int = 0
    counts: dict[str, int] = Field(default_factory=dict)
    file_import_names: list[str] = Field(default_factory=list)
    keyword_xref_count: int = 0
    closed_route_neighbor_count: int = 0


class Nep2InitBridgeReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    binary_name: str = "NEP2.dll"
    round: int = 0
    slice: str = ""
    input_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    summary: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    status_counts: dict[str, int] = Field(default_factory=dict)
    candidate_verdict_counts: dict[str, int] = Field(default_factory=dict)
    bridge_records: list[Nep2InitBridgeRecord] = Field(default_factory=list)
    range_summaries: list[dict[str, Any]] = Field(default_factory=list)
    constructor_enqueue_seeds: list[dict[str, Any]] = Field(default_factory=list)
    candidate_functions: list[Nep2InitBridgeCandidate] = Field(default_factory=list)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    negative_signals: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_nep2_init_bridge_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> Nep2InitBridgeReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    bridge_records = [
        _bridge_record(item) for item in data.get("bridge_records") or [] if isinstance(item, dict)
    ]
    candidates = [
        _candidate(item) for item in data.get("candidate_functions") or [] if isinstance(item, dict)
    ]
    evidence_refs = _evidence_refs(bridge_records, candidates, data)
    return Nep2InitBridgeReport(
        source_id=source_id,
        generated_at=generated_at,
        binary_name=str(data.get("binary_name") or "NEP2.dll"),
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=_input_artifacts(data.get("input_artifacts") or []),
        summary=[str(item) for item in data.get("summary") or []],
        counts=_int_dict(data.get("counts") or {}),
        status_counts=_int_dict(data.get("status_counts") or {}),
        candidate_verdict_counts=_int_dict(data.get("candidate_verdict_counts") or {}),
        bridge_records=bridge_records,
        range_summaries=[item for item in data.get("range_summaries") or [] if isinstance(item, dict)],
        constructor_enqueue_seeds=[
            item for item in data.get("constructor_enqueue_seeds") or [] if isinstance(item, dict)
        ],
        candidate_functions=candidates,
        route_conclusion=data.get("route_conclusion") if isinstance(data.get("route_conclusion"), dict) else {},
        negative_signals=[str(item) for item in data.get("negative_signals") or []],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=evidence_refs,
        guardrails=[
            "offline/static NEP2 evidence only; no live instrumentation or online protocol data is included",
            "external absolute paths are not persisted; only artifact filenames, hashes, RVAs, and evidence refs are stored",
            "InitLuaScriptsScan bridge metadata is decoder planning evidence, not reviewed game knowledge",
            "do not promote any fact until readable LuaScripts payloads are decoded and manually reviewed",
        ],
    )


def write_nep2_init_bridge_report(report: Nep2InitBridgeReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _bridge_record(raw: dict[str, Any]) -> Nep2InitBridgeRecord:
    return Nep2InitBridgeRecord(
        evidence_ref=str(raw.get("evidence_ref") or ""),
        rva=str(raw.get("rva") or ""),
        label=str(raw.get("label") or ""),
        type_descriptor_rva=str(raw.get("type_descriptor_rva") or ""),
        name_rva=str(raw.get("name_rva") or ""),
        code_pointers=[
            item for item in raw.get("code_pointers") or [] if isinstance(item, dict)
        ],
        status=str(raw.get("status") or "unknown"),
        verdict=str(raw.get("verdict") or "unknown"),
    )


def _candidate(raw: dict[str, Any]) -> Nep2InitBridgeCandidate:
    return Nep2InitBridgeCandidate(
        evidence_ref=str(raw.get("evidence_ref") or ""),
        function_rva=str(raw.get("function_rva") or ""),
        function_size=str(raw.get("function_size") or ""),
        sources=[str(item) for item in raw.get("sources") or []],
        verdict=str(raw.get("verdict") or "unknown"),
        score=int(raw.get("score") or 0),
        counts=_int_dict(raw.get("counts") or {}),
        file_import_names=[str(item) for item in raw.get("file_import_names") or []],
        keyword_xref_count=int(raw.get("keyword_xref_count") or 0),
        closed_route_neighbor_count=int(raw.get("closed_route_neighbor_count") or 0),
    )


def _input_artifacts(raw_items: list[Any]) -> list[dict[str, Any]]:
    artifacts = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        artifacts.append(
            {
                "key": str(raw.get("key") or ""),
                "file_name": Path(str(raw.get("file_name") or "")).name,
                "sha256": str(raw.get("sha256") or ""),
            }
        )
    return artifacts


def _evidence_refs(
    bridge_records: list[Nep2InitBridgeRecord],
    candidates: list[Nep2InitBridgeCandidate],
    data: dict[str, Any],
) -> list[str]:
    refs = [record.evidence_ref for record in bridge_records if record.evidence_ref]
    refs.extend(
        str(item.get("evidence_ref"))
        for item in data.get("constructor_enqueue_seeds") or []
        if isinstance(item, dict) and item.get("evidence_ref")
    )
    refs.extend(candidate.evidence_ref for candidate in candidates if candidate.evidence_ref)
    return list(dict.fromkeys(refs))


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(raw or 0) for key, raw in value.items()}
