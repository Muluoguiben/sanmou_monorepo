from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SOURCE_SITE = "nslg_client_luascripts"
SOURCE_URL = "local-nslg-client-luascripts"


class LuaScriptTextAssetRecord(BaseModel):
    evidence_ref: str = Field(min_length=1)
    asset_path: str = Field(min_length=1)
    stem: str = Field(min_length=1)
    scenario: str | None = None
    asset_group: str | None = None
    kb_domains: list[str] = Field(default_factory=list)
    path_id_hex: str | None = None
    script_len: int | None = Field(default=None, ge=0)
    sha1: str | None = None
    printable_score: float | None = None
    extraction_status: str
    decoder_attempts: list[dict[str, Any]] = Field(default_factory=list)
    extracted_artifact: str | None = None


class LuaScriptsTextAssetCatalog(BaseModel):
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    bundle_name: str | None = None
    total_container_entries: int = 0
    total_data_entries: int = 0
    cataloged_records: int = 0
    unique_stems: int = 0
    scenarios: list[str] = Field(default_factory=list)
    kb_domain_counts: dict[str, int] = Field(default_factory=dict)
    extraction_status_counts: dict[str, int] = Field(default_factory=dict)
    high_value_stems: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    records: list[LuaScriptTextAssetRecord] = Field(default_factory=list)


def load_luascripts_extract_summary(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_luascripts_textasset_catalog(
    summary: dict[str, Any],
    *,
    source_id: str,
    generated_at: datetime | None = None,
) -> LuaScriptsTextAssetCatalog:
    generated_at = generated_at or datetime.now(timezone.utc)
    records = [
        _record_from_raw(raw, source_id=source_id)
        for raw in summary.get("relevant_records", [])
        if isinstance(raw, dict)
    ]
    domain_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    scenarios = set()
    for record in records:
        domain_counts.update(record.kb_domains)
        status_counts[record.extraction_status] += 1
        if record.scenario:
            scenarios.add(record.scenario)
    return LuaScriptsTextAssetCatalog(
        source_id=source_id,
        generated_at=generated_at,
        bundle_name=_safe_basename(summary.get("cab") or "luascripts.ns"),
        total_container_entries=int(summary.get("container_luascripts_bytes_entries") or 0),
        total_data_entries=int(summary.get("data_entries") or 0),
        cataloged_records=len(records),
        unique_stems=len({record.stem for record in records}),
        scenarios=sorted(scenarios),
        kb_domain_counts=dict(sorted(domain_counts.items())),
        extraction_status_counts=dict(sorted(status_counts.items())),
        high_value_stems=_high_value_stems(records),
        limitations=[
            "catalog records are sanitized metadata from offline Unity TextAsset extraction, not reviewed knowledge entries",
            "payload samples are currently obfuscated or encrypted binary unless extraction_status says otherwise",
            "catalog intentionally omits absolute local install paths and runtime-cache paths",
        ],
        records=records,
    )


def write_luascripts_textasset_catalog(catalog: LuaScriptsTextAssetCatalog, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(catalog.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _record_from_raw(raw: dict[str, Any], *, source_id: str) -> LuaScriptTextAssetRecord:
    asset_path = str(raw.get("path") or "")
    stem = str(raw.get("stem") or Path(asset_path).stem)
    attempts = _decoder_attempts(raw)
    return LuaScriptTextAssetRecord(
        evidence_ref=f"NSLG_LUASCRIPT_TEXTASSET:{source_id}:{stem}:{raw.get('path_id_hex')}",
        asset_path=asset_path,
        stem=stem,
        scenario=_scenario_from_asset_path(asset_path),
        asset_group=_asset_group_from_asset_path(asset_path),
        kb_domains=_kb_domains_for_asset(stem, asset_path),
        path_id_hex=raw.get("path_id_hex"),
        script_len=raw.get("script_len"),
        sha1=raw.get("sha1"),
        printable_score=raw.get("printable_score"),
        extraction_status=_extraction_status(raw, attempts),
        decoder_attempts=attempts,
        extracted_artifact=_sanitize_extracted_path(raw.get("extracted_path")),
    )


def _decoder_attempts(raw: dict[str, Any]) -> list[dict[str, Any]]:
    attempts = []
    for attempt in raw.get("decompress_attempts") or []:
        if not isinstance(attempt, dict):
            continue
        attempts.append(
            {
                "name": attempt.get("name"),
                "ok": bool(attempt.get("ok")),
                "error_type": _error_type(attempt.get("error")),
            }
        )
    return attempts


def _extraction_status(raw: dict[str, Any], attempts: list[dict[str, Any]]) -> str:
    if any(attempt.get("ok") for attempt in attempts):
        return "decoded_by_generic_decompressor"
    score = raw.get("printable_score")
    if isinstance(score, int | float) and score >= 0.7:
        return "plain_text_candidate"
    return "obfuscated_binary_pending_decoder"


def _scenario_from_asset_path(asset_path: str) -> str | None:
    for part in asset_path.replace("\\", "/").split("/"):
        if part.startswith("Scenario"):
            return part
    return None


def _asset_group_from_asset_path(asset_path: str) -> str | None:
    parts = asset_path.replace("\\", "/").split("/")
    for index, part in enumerate(parts):
        if part.startswith("Scenario") and index + 1 < len(parts) - 1:
            return parts[index + 1]
    return None


def _kb_domains_for_asset(stem: str, asset_path: str) -> list[str]:
    text = f"{stem} {asset_path}".lower()
    stem_text = stem.lower()
    domains = []
    rules = [
        ("hero", ["hero", "heros", "custom_hero"]),
        ("skill", ["skill", "buff", "talent", "warbook"]),
        ("building", ["building", "scene_building"]),
        ("combat", ["battle", "army", "formation", "fightprop", "gvg", "pve"]),
        ("map", ["map_", "terrain", "resource", "city_relation"]),
        ("chapter_task", ["task", "rookie", "guide", "achievement"]),
        ("story_plot", ["story", "plot"]),
        ("season", ["season", "scenario_season"]),
        ("economy_item", ["item", "drop", "money", "shop", "package", "pay"]),
        ("system_text", ["mail", "message", "newsticker", "grammar"]),
    ]
    for domain, needles in rules:
        search_text = stem_text if domain == "season" else text
        if any(needle in search_text for needle in needles):
            domains.append(domain)
    return domains or ["unknown"]


def _high_value_stems(records: list[LuaScriptTextAssetRecord]) -> list[str]:
    priority_domains = {"hero", "skill", "building", "combat", "map", "chapter_task", "story_plot", "season"}
    stems = {
        record.stem
        for record in records
        if priority_domains.intersection(record.kb_domains)
    }
    return sorted(stems)


def _sanitize_extracted_path(value: Any) -> str | None:
    if not value:
        return None
    path = str(value).replace("\\", "/")
    marker = "threads/artifacts/"
    if marker in path:
        return path[path.index(marker) :]
    return Path(path).name


def _safe_basename(value: Any) -> str | None:
    if not value:
        return None
    return str(value).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _error_type(error: Any) -> str | None:
    if not error:
        return None
    text = str(error)
    return text.split(":", 1)[0]
