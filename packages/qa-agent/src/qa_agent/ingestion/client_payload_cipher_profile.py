from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.luascripts_payload_cipher_profile.v1"
SOURCE_SITE = "nslg_client_luascripts_cipher_profile"
SOURCE_URL = "local-nslg-client-luascripts-cipher-profile"


class LuaScriptsPayloadProfile(BaseModel):
    evidence_ref: str = Field(min_length=1)
    file_name: str = Field(min_length=1)
    stem: str = Field(min_length=1)
    asset_path: str = ""
    size_bytes: int = Field(ge=0)
    size_mod_16: int = Field(ge=0)
    sha1: str = ""
    sha256: str = ""
    entropy: float = 0.0
    printable_score: float = 0.0
    block_count_16: int = 0
    duplicate_16byte_blocks: int = 0
    unique_16byte_blocks: int = 0
    compression_magic: str = "none"
    best_single_byte_xor: dict[str, Any] = Field(default_factory=dict)
    direct_term_hits: dict[str, int] = Field(default_factory=dict)
    status: str = Field(min_length=1)


class LuaScriptsPayloadCipherProfileReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[dict[str, Any]] = Field(default_factory=list)
    catalog_summary: dict[str, Any] = Field(default_factory=dict)
    payload_profile_count: int = 0
    payload_status_counts: dict[str, int] = Field(default_factory=dict)
    payload_profiles: list[LuaScriptsPayloadProfile] = Field(default_factory=list)
    cross_file_block_profile: dict[str, Any] = Field(default_factory=dict)
    simple_transform_summary: dict[str, Any] = Field(default_factory=dict)
    xor_crib_probe_summary: dict[str, Any] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    next_decoder_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    evidence_refs: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_luascripts_payload_cipher_profile_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> LuaScriptsPayloadCipherProfileReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    profiles = [
        _payload_profile(item, source_id=source_id)
        for item in data.get("payload_profiles") or []
        if isinstance(item, dict)
    ]
    evidence_refs = [profile.evidence_ref for profile in profiles]
    return LuaScriptsPayloadCipherProfileReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=_input_artifacts(data.get("input_artifacts") or []),
        catalog_summary=data.get("catalog_summary") if isinstance(data.get("catalog_summary"), dict) else {},
        payload_profile_count=len(profiles),
        payload_status_counts=dict(sorted(Counter(profile.status for profile in profiles).items())),
        payload_profiles=profiles,
        cross_file_block_profile=_intish_map(data.get("cross_file_block_profile") or {}),
        simple_transform_summary=_intish_map(data.get("simple_transform_summary") or {}),
        xor_crib_probe_summary=_intish_map(data.get("xor_crib_probe_summary") or {}),
        route_conclusion=data.get("route_conclusion") if isinstance(data.get("route_conclusion"), dict) else {},
        next_decoder_targets=[str(item) for item in data.get("next_decoder_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        evidence_refs=evidence_refs,
        guardrails=[
            "offline/static payload evidence only; no live instrumentation or online protocol data is included",
            "payload profiles are decoder planning evidence, not reviewed game knowledge",
            "external absolute paths are not persisted; payload file names, hashes, and evidence refs are stored",
            "do not promote any fact until readable LuaScripts payloads are decoded and manually reviewed",
        ],
    )


def write_luascripts_payload_cipher_profile_report(
    report: LuaScriptsPayloadCipherProfileReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _payload_profile(raw: dict[str, Any], *, source_id: str) -> LuaScriptsPayloadProfile:
    file_name = Path(str(raw.get("file_name") or "")).name
    return LuaScriptsPayloadProfile(
        evidence_ref=f"NSLG_LUASCRIPT_CIPHER_PROFILE:{source_id}:payload:{file_name}",
        file_name=file_name,
        stem=str(raw.get("stem") or file_name.split(".", 1)[0] or "unknown"),
        asset_path=str(raw.get("asset_path") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        size_mod_16=int(raw.get("size_mod_16") or 0),
        sha1=str(raw.get("sha1") or ""),
        sha256=str(raw.get("sha256") or ""),
        entropy=float(raw.get("entropy") or 0.0),
        printable_score=float(raw.get("printable_score") or 0.0),
        block_count_16=int(raw.get("block_count_16") or 0),
        duplicate_16byte_blocks=int(raw.get("duplicate_16byte_blocks") or 0),
        unique_16byte_blocks=int(raw.get("unique_16byte_blocks") or 0),
        compression_magic=str(raw.get("compression_magic") or "none"),
        best_single_byte_xor=(
            raw.get("best_single_byte_xor")
            if isinstance(raw.get("best_single_byte_xor"), dict)
            else {}
        ),
        direct_term_hits=_int_dict(raw.get("direct_term_hits") or {}),
        status=str(raw.get("status") or "unknown"),
    )


def _input_artifacts(raw_items: list[Any]) -> list[dict[str, Any]]:
    artifacts = []
    for raw in raw_items:
        if not isinstance(raw, dict):
            continue
        artifacts.append(
            {
                "file_name": Path(str(raw.get("file_name") or "")).name,
                "sha256": str(raw.get("sha256") or ""),
            }
        )
    return artifacts


def _intish_map(value: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    cleaned: dict[str, Any] = {}
    for key, raw in value.items():
        if isinstance(raw, dict):
            cleaned[str(key)] = _intish_map(raw)
        elif isinstance(raw, list):
            cleaned[str(key)] = raw
        else:
            cleaned[str(key)] = raw
    return cleaned


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(raw or 0) for key, raw in value.items()}
