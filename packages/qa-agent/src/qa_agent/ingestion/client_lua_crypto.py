from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SOURCE_SITE = "nslg_client_lua_crypto"
SOURCE_URL = "local-nslg-client-lua-crypto"


class BinaryStringHitSummary(BaseModel):
    binary_name: str = Field(min_length=1)
    size_bytes: int | None = Field(default=None, ge=0)
    term_hit_counts: dict[str, int] = Field(default_factory=dict)
    selected_context_strings: list[str] = Field(default_factory=list)


class PayloadBlockSample(BaseModel):
    file_name: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    size_mod_16: int = Field(ge=0)
    entropy: float
    unique_byte_values: int = Field(ge=0)
    block_count_16: int = Field(ge=0)
    duplicate_16byte_blocks: int = Field(ge=0)
    first_block_hex: str
    last_block_hex: str


class RuntimeInitializeLuaEntry(BaseModel):
    assembly_name: str
    namespace: str
    class_name: str
    method_name: str
    load_types: int | None = None


class LuaCryptoEvidenceReport(BaseModel):
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    binary_string_hits: list[BinaryStringHitSummary] = Field(default_factory=list)
    payload_block_samples: list[PayloadBlockSample] = Field(default_factory=list)
    payload_status_counts: dict[str, int] = Field(default_factory=dict)
    runtime_initialize_lua_entries: list[RuntimeInitializeLuaEntry] = Field(default_factory=list)
    il2cpp_dumper_probe: dict[str, str] = Field(default_factory=dict)
    skipped_runtime_patch_samples: int = 0
    sanitized_conclusions: list[str] = Field(default_factory=list)
    next_decoder_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def load_lua_crypto_evidence(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_lua_crypto_evidence_report(
    evidence: dict[str, Any],
    *,
    source_id: str,
    generated_at: datetime | None = None,
) -> LuaCryptoEvidenceReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    payload_samples = [_payload_sample(item) for item in evidence.get("payload_block_analysis", [])]
    return LuaCryptoEvidenceReport(
        source_id=source_id,
        generated_at=generated_at,
        binary_string_hits=[_binary_hit_summary(item) for item in evidence.get("binary_string_scan", [])],
        payload_block_samples=payload_samples,
        payload_status_counts=_payload_status_counts(payload_samples),
        runtime_initialize_lua_entries=[
            _runtime_lua_entry(item) for item in evidence.get("runtime_initialize_lua_entries", [])
        ],
        il2cpp_dumper_probe=_il2cpp_probe(evidence.get("il2cpp_dumper_probe") or {}),
        skipped_runtime_patch_samples=len(evidence.get("lua_patch_block_analysis") or []),
        sanitized_conclusions=_sanitize_conclusions(evidence.get("conclusions") or []),
        next_decoder_targets=[
            "GameAssembly xluaL_loadbuffer / TextAsset::get_bytes call path",
            "NSLGame.Patcher.GameUpdater.InitLuaEnv runtime initialize entry",
            "global-metadata.dat protection/deobfuscation needed before normal IL2CPP symbol recovery",
            "16-byte-aligned LuaScripts payload block transform",
        ],
        limitations=[
            "this report is sanitized reverse-engineering evidence, not decoded game knowledge",
            "runtime lua patch samples were counted but not persisted because they are local runtime cache artifacts",
            "no live instrumentation or online protocol data is included",
        ],
    )


def write_lua_crypto_evidence_report(report: LuaCryptoEvidenceReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _binary_hit_summary(raw: dict[str, Any]) -> BinaryStringHitSummary:
    term_hits = raw.get("term_hits") or {}
    return BinaryStringHitSummary(
        binary_name=_binary_name(raw.get("file")),
        size_bytes=raw.get("size"),
        term_hit_counts={key: len(value or []) for key, value in sorted(term_hits.items())},
        selected_context_strings=_selected_context_strings(raw.get("context_strings") or []),
    )


def _payload_sample(raw: dict[str, Any]) -> PayloadBlockSample:
    return PayloadBlockSample(
        file_name=Path(str(raw.get("file") or "")).name,
        size_bytes=int(raw.get("size") or 0),
        size_mod_16=int(raw.get("size_mod_16") or 0),
        entropy=float(raw.get("entropy") or 0.0),
        unique_byte_values=int(raw.get("unique_byte_values") or 0),
        block_count_16=int(raw.get("block_count_16") or 0),
        duplicate_16byte_blocks=int(raw.get("duplicate_16byte_blocks") or 0),
        first_block_hex=str(raw.get("first_block_hex") or ""),
        last_block_hex=str(raw.get("last_block_hex") or ""),
    )


def _runtime_lua_entry(raw: dict[str, Any]) -> RuntimeInitializeLuaEntry:
    return RuntimeInitializeLuaEntry(
        assembly_name=str(raw.get("assemblyName") or ""),
        namespace=str(raw.get("nameSpace") or ""),
        class_name=str(raw.get("className") or ""),
        method_name=str(raw.get("methodName") or ""),
        load_types=raw.get("loadTypes"),
    )


def _il2cpp_probe(raw: dict[str, Any]) -> dict[str, str]:
    return {
        "result": str(raw.get("result") or ""),
        "evidence": _sanitize_text(str(raw.get("evidence") or "")),
    }


def _payload_status_counts(samples: list[PayloadBlockSample]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for sample in samples:
        if sample.size_mod_16 == 0 and sample.entropy >= 7.8 and sample.duplicate_16byte_blocks == 0:
            counts["high_entropy_16byte_aligned"] += 1
        else:
            counts["needs_manual_review"] += 1
    return dict(sorted(counts.items()))


def _selected_context_strings(items: list[dict[str, Any]]) -> list[str]:
    selected = []
    needles = ["xlua", "luaL_loadbuffer", "TextAsset", "client_crypt", "AES", "RC4", "LuaJIT"]
    for item in items:
        value = str(item.get("string") or "")
        if not value or _looks_local_path(value):
            continue
        if any(needle.lower() in value.lower() for needle in needles):
            selected.append(value)
    return list(dict.fromkeys(selected))[:24]


def _sanitize_conclusions(values: list[Any]) -> list[str]:
    return [_sanitize_text(str(value)) for value in values if str(value).strip()]


def _sanitize_text(value: str) -> str:
    text = value.replace("\\", "/")
    text = text.replace("/mnt/d/bilibili Game/NSLG/NSLG Game/", "<NSLG_GAME>/")
    text = text.replace("D:/bilibili Game/NSLG/NSLG Game/", "<NSLG_GAME>/")
    return text


def _binary_name(value: Any) -> str:
    if not value:
        return "unknown"
    return str(value).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _looks_local_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return ":/" in normalized or normalized.startswith("/mnt/")
