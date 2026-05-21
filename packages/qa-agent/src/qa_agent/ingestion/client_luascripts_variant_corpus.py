from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.luascripts_payload_variant_corpus.v1"
SOURCE_SITE = "nslg_client_luascripts_variant_corpus"
SOURCE_URL = "local-nslg-client-luascripts-payload-variant-corpus"


class LuaScriptsVariantInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    sha256: str = ""


class LuaScriptsStemVariantSummary(BaseModel):
    stem: str = Field(min_length=1)
    record_count: int = Field(ge=0)
    variant_count: int = Field(ge=0)
    unique_ciphertext_hash_count: int = Field(ge=0)
    duplicate_ciphertext_hash_group_count: int = Field(ge=0)
    duplicate_ciphertext_variant_count: int = Field(ge=0)
    entropy_avg: float = 0.0
    printable_score_4k_avg: float = 0.0
    direct_plaintext_term_variant_count: int = Field(ge=0)
    sample_scenarios: list[str] = Field(default_factory=list)
    sample_paths: list[str] = Field(default_factory=list)


class LuaScriptsPayloadVariantCorpusReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[LuaScriptsVariantInputArtifact] = Field(default_factory=list)
    corpus_summary: dict[str, int | bool] = Field(default_factory=dict)
    stem_summaries: list[LuaScriptsStemVariantSummary] = Field(default_factory=list)
    duplicate_ciphertext_groups: list[dict[str, Any]] = Field(default_factory=list)
    block_sharing_summary: dict[str, Any] = Field(default_factory=dict)
    offset_skip_probe_summary: dict[str, Any] = Field(default_factory=dict)
    same_length_hamming_summary: list[dict[str, Any]] = Field(default_factory=list)
    prior_route_context: dict[str, Any] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    next_decoder_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_luascripts_payload_variant_corpus_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> LuaScriptsPayloadVariantCorpusReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    return LuaScriptsPayloadVariantCorpusReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        corpus_summary=_int_bool_map(data.get("corpus_summary") or {}),
        stem_summaries=[
            _stem_summary(item)
            for item in data.get("stem_summaries") or []
            if isinstance(item, dict)
        ][:80],
        duplicate_ciphertext_groups=[
            _duplicate_group(item)
            for item in data.get("duplicate_ciphertext_groups") or []
            if isinstance(item, dict)
        ][:40],
        block_sharing_summary=_safe_map(data.get("block_sharing_summary")),
        offset_skip_probe_summary=_offset_skip_summary(data.get("offset_skip_probe_summary")),
        same_length_hamming_summary=[
            _safe_map(item)
            for item in data.get("same_length_hamming_summary") or []
            if isinstance(item, dict)
        ][:40],
        prior_route_context=_safe_map(data.get("prior_route_context")),
        route_conclusion=_safe_map(data.get("route_conclusion")),
        next_decoder_targets=[str(item) for item in data.get("next_decoder_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []],
        guardrails=[
            "offline/static LuaScripts payload corpus evidence only; no live instrumentation, account data, or online protocol data is included",
            "absolute local paths are not persisted; only file names, asset-bundle paths, offsets, counts, and hashes are stored",
            "expanded encrypted payload corpus is decoder planning/eval evidence, not reviewed game knowledge",
            "no decoded LuaScripts gameplay configuration is promoted from this artifact",
        ],
    )


def write_luascripts_payload_variant_corpus_report(
    report: LuaScriptsPayloadVariantCorpusReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> LuaScriptsVariantInputArtifact:
    file_name = str(raw.get("file_name") or "unknown").replace("\\", "/")
    return LuaScriptsVariantInputArtifact(
        file_name=Path(file_name).name,
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
    )


def _stem_summary(raw: dict[str, Any]) -> LuaScriptsStemVariantSummary:
    return LuaScriptsStemVariantSummary(
        stem=str(raw.get("stem") or "unknown"),
        record_count=int(raw.get("record_count") or 0),
        variant_count=int(raw.get("variant_count") or 0),
        unique_ciphertext_hash_count=int(raw.get("unique_ciphertext_hash_count") or 0),
        duplicate_ciphertext_hash_group_count=int(
            raw.get("duplicate_ciphertext_hash_group_count") or 0
        ),
        duplicate_ciphertext_variant_count=int(
            raw.get("duplicate_ciphertext_variant_count") or 0
        ),
        entropy_avg=float(raw.get("entropy_avg") or 0.0),
        printable_score_4k_avg=float(raw.get("printable_score_4k_avg") or 0.0),
        direct_plaintext_term_variant_count=int(
            raw.get("direct_plaintext_term_variant_count") or 0
        ),
        sample_scenarios=[str(item) for item in raw.get("sample_scenarios") or []][:16],
        sample_paths=[
            _asset_path(str(item)) for item in raw.get("sample_paths") or []
        ][:16],
    )


def _duplicate_group(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "sha256": str(raw.get("sha256") or ""),
        "variant_count": int(raw.get("variant_count") or 0),
        "stems": [str(item) for item in raw.get("stems") or []],
        "script_lens": [int(item or 0) for item in raw.get("script_lens") or []],
        "first_block_hex": str(raw.get("first_block_hex") or ""),
        "last_block_hex": str(raw.get("last_block_hex") or ""),
        "sample_refs": [
            _sample_ref(item)
            for item in raw.get("sample_refs") or []
            if isinstance(item, dict)
        ][:8],
    }


def _sample_ref(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "path": _asset_path(str(raw.get("path") or "")),
        "match_index": int(raw.get("match_index") or 0),
        "payload_offset": int(raw.get("payload_offset") or 0),
        "scenario": str(raw.get("scenario") or ""),
    }


def _offset_skip_summary(value: Any) -> dict[str, Any]:
    raw = _safe_map(value)
    return {
        "skips_tested": [int(item or 0) for item in raw.get("skips_tested") or []],
        "variant_count": int(raw.get("variant_count") or 0),
        "decompression_success_count": int(raw.get("decompression_success_count") or 0),
        "plaintext_hit_count": int(raw.get("plaintext_hit_count") or 0),
        "high_printable_candidate_count": int(raw.get("high_printable_candidate_count") or 0),
        "decompression_successes": [
            _safe_map(item)
            for item in raw.get("decompression_successes") or []
            if isinstance(item, dict)
        ][:16],
        "plaintext_hits": [
            _safe_map(item)
            for item in raw.get("plaintext_hits") or []
            if isinstance(item, dict)
        ][:16],
        "best_printable_samples": [
            _safe_map(item)
            for item in raw.get("best_printable_samples") or []
            if isinstance(item, dict)
        ][:16],
    }


def _int_bool_map(value: Any) -> dict[str, int | bool]:
    cleaned: dict[str, int | bool] = {}
    if not isinstance(value, dict):
        return cleaned
    for key, raw in value.items():
        if isinstance(raw, bool):
            cleaned[str(key)] = raw
        elif isinstance(raw, int):
            cleaned[str(key)] = raw
        elif isinstance(raw, float):
            cleaned[str(key)] = int(raw)
        elif raw is None:
            cleaned[str(key)] = 0
        else:
            try:
                cleaned[str(key)] = int(raw)
            except (TypeError, ValueError):
                continue
    return cleaned


def _asset_path(value: str) -> str:
    normalized = value.replace("\\", "/")
    if "Assets/" in normalized:
        return normalized[normalized.index("Assets/") :]
    return Path(normalized).name


def _safe_map(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}
