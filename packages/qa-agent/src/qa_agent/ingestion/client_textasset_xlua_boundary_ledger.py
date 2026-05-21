from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.textasset_xlua_boundary_ledger.v1"
SOURCE_SITE = "nslg_client_textasset_xlua_boundary_ledger"
SOURCE_URL = "local-nslg-client-textasset-xlua-boundary-ledger"


class TextAssetXluaBoundaryInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class TextAssetXluaBoundaryRouteRecord(BaseModel):
    route_id: str = Field(min_length=1)
    title: str = ""
    status: str = Field(min_length=1)
    maturity: str = ""
    source_round: int = 0
    evidence_refs: list[str] = Field(default_factory=list)
    signal_summary: list[str] = Field(default_factory=list)
    blocking_signals: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    next_actions: list[str] = Field(default_factory=list)


class TextAssetXluaBoundaryLedgerReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[TextAssetXluaBoundaryInputArtifact] = Field(default_factory=list)
    route_records: list[TextAssetXluaBoundaryRouteRecord] = Field(default_factory=list)
    route_status_counts: dict[str, int] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_textasset_xlua_boundary_ledger_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> TextAssetXluaBoundaryLedgerReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return TextAssetXluaBoundaryLedgerReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        route_records=[
            _route_record(item)
            for item in data.get("route_records") or []
            if isinstance(item, dict)
        ],
        route_status_counts=_int_dict(_safe_map(data.get("route_status_counts"))),
        counts=_counts(_safe_map(data.get("counts")), _safe_map(data.get("route_conclusion"))),
        route_conclusion=_safe_map(data.get("route_conclusion")),
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static route ledger only; no live instrumentation, account data, or online protocol data is included",
            "closed routes are negative planning evidence and must not be promoted as game knowledge",
            "absolute local paths are not persisted; only sanitized artifact names, counts, statuses, and evidence refs are stored",
            "continue with method ownership or proven buffer-flow evidence, not broad string or embedded-constant scans",
        ],
    )


def write_textasset_xlua_boundary_ledger_report(
    report: TextAssetXluaBoundaryLedgerReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> TextAssetXluaBoundaryInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return TextAssetXluaBoundaryInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _route_record(raw: dict[str, Any]) -> TextAssetXluaBoundaryRouteRecord:
    return TextAssetXluaBoundaryRouteRecord(
        route_id=str(raw.get("route_id") or "unknown"),
        title=str(raw.get("title") or ""),
        status=str(raw.get("status") or "unknown"),
        maturity=str(raw.get("maturity") or ""),
        source_round=int(raw.get("source_round") or 0),
        evidence_refs=[str(item) for item in raw.get("evidence_refs") or []][:24],
        signal_summary=[str(item) for item in raw.get("signal_summary") or []][:12],
        blocking_signals=[str(item) for item in raw.get("blocking_signals") or []][:12],
        counts=_int_dict(_safe_map(raw.get("counts"))),
        next_actions=[str(item) for item in raw.get("next_actions") or []][:12],
    )


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
