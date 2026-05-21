from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SOURCE_SITE = "nslg_client_nep2_luascripts"
SOURCE_URL = "local-nslg-client-nep2-luascripts"

TARGET_STRING_KEYWORDS = [
    "InitLuaScriptsScan",
    "InitConfigsDispatch",
    "InitKernelMemScan",
    "LuaJitLuaSrcLuaSrcEncrytedLuacCompiled",
    "luaL_loadbuffer",
    "CryptDecrypt",
    "VirtualProtect",
    "luaFindFileWithGivenDirByMD5",
    "luaFindFileWithGivenDirByText",
    "luaFindSpecifiedFileByHash0rText",
    "WAES",
    "decrypt",
    "LUABOX",
    "protected",
]


class Nep2InitLuaOccurrence(BaseModel):
    rva: str
    section: str
    selected_ascii: list[str] = Field(default_factory=list)


class Nep2LuaXref(BaseModel):
    string: str
    ref_rva: str
    ref_section: str
    instruction: str


class Nep2StringChunkRegistration(BaseModel):
    source_string: str
    ref_rva: str
    descriptor_rva: str | None = None
    chunk_offset: int | None = None
    chunk_length: int | None = None
    chunk_text: str | None = None
    target_helper: str | None = None


class Nep2LuaScriptsEvidenceReport(BaseModel):
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    binary_name: str = "NEP2.dll"
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    init_luascripts_occurrences: list[Nep2InitLuaOccurrence] = Field(default_factory=list)
    pointer_refs_to_init_luascripts: int = 0
    candidate_string_count: int = 0
    selected_candidate_strings: list[str] = Field(default_factory=list)
    xref_count: int = 0
    xrefs: list[Nep2LuaXref] = Field(default_factory=list)
    string_chunk_registrations: list[Nep2StringChunkRegistration] = Field(default_factory=list)
    interpretation: dict[str, str] = Field(default_factory=dict)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)


def load_nep2_luascripts_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_nep2_luascripts_evidence_report(
    candidate_scan: dict[str, Any],
    init_scan: dict[str, Any],
    *,
    source_id: str,
) -> Nep2LuaScriptsEvidenceReport:
    file_info = candidate_scan.get("file") or init_scan.get("file") or {}
    return Nep2LuaScriptsEvidenceReport(
        source_id=source_id,
        binary_name=_binary_name(file_info.get("path")) or "NEP2.dll",
        size_bytes=file_info.get("size"),
        sha256=file_info.get("sha256"),
        init_luascripts_occurrences=[
            _init_occurrence(item) for item in init_scan.get("init_luascripts_occurrences", [])
        ],
        pointer_refs_to_init_luascripts=len(init_scan.get("pointer_refs_to_init_luascripts") or []),
        candidate_string_count=int(candidate_scan.get("interesting_string_count") or 0),
        selected_candidate_strings=_selected_candidate_strings(
            candidate_scan.get("interesting_import_or_symbol_strings") or []
        ),
        xref_count=int(candidate_scan.get("xref_count") or 0),
        xrefs=[_xref(item) for item in candidate_scan.get("xrefs", [])],
        string_chunk_registrations=[
            item
            for item in (_chunk_registration(raw) for raw in candidate_scan.get("xrefs", []))
            if item is not None
        ],
        interpretation={
            "candidate_scan": str((candidate_scan.get("interpretation") or {}).get("summary") or ""),
            "init_scan": str((init_scan.get("interpretation") or {}).get("summary") or ""),
            "next_step": str((init_scan.get("interpretation") or {}).get("next_step") or ""),
        },
        next_static_targets=[
            "trace CGameProtector::InitLuaScriptsScan call sites or data-table consumers",
            "inspect xrefs around LuaJitLuaSrcLuaSrcEncrytedLuacCompiled and luaL_loadbuffer strings",
            "follow NEP2 string-decode helper at xref windows that call 0x180021240",
            "check whether NEP2 hands decrypted LuaScripts bytes to xlua or writes decoded payloads",
        ],
        limitations=[
            "this report is sanitized static evidence only; it does not prove the decryptor body yet",
            "direct pointer refs to InitLuaScriptsScan were not found in the round34 scan",
            "no live instrumentation or online protocol data is included",
        ],
    )


def write_nep2_luascripts_evidence_report(report: Nep2LuaScriptsEvidenceReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _init_occurrence(raw: dict[str, Any]) -> Nep2InitLuaOccurrence:
    selected = []
    for item in raw.get("window") or []:
        ascii_text = str(item.get("ascii") or "")
        if any(keyword in ascii_text for keyword in ["Init", "Lua", "Protector", "ThreadPool"]):
            selected.append(ascii_text)
    return Nep2InitLuaOccurrence(
        rva=str(raw.get("rva") or ""),
        section=str(raw.get("section") or ""),
        selected_ascii=list(dict.fromkeys(selected))[:16],
    )


def _selected_candidate_strings(values: list[Any]) -> list[str]:
    selected = []
    for raw in values:
        value = str(raw)
        if _looks_local_path(value):
            continue
        if any(keyword.lower() in value.lower() for keyword in TARGET_STRING_KEYWORDS):
            selected.append(value)
    return list(dict.fromkeys(selected))[:80]


def _xref(raw: dict[str, Any]) -> Nep2LuaXref:
    return Nep2LuaXref(
        string=str(raw.get("string") or ""),
        ref_rva=str(raw.get("ref_rva") or ""),
        ref_section=str(raw.get("ref_section") or ""),
        instruction=str(raw.get("instruction") or ""),
    )


def _chunk_registration(raw: dict[str, Any]) -> Nep2StringChunkRegistration | None:
    window = raw.get("window") or []
    if not window:
        return None
    ref_index = _ref_index(window, str(raw.get("ref_rva") or ""))
    if ref_index is None:
        return None
    chunk_offset = _chunk_offset(window, ref_index)
    chunk_length = _chunk_length(window, ref_index)
    target_helper = _next_call_target(window, ref_index)
    source = str(raw.get("string") or "")
    chunk_text = None
    if chunk_offset is not None and chunk_length is not None:
        chunk_text = source[chunk_offset : chunk_offset + chunk_length]
    return Nep2StringChunkRegistration(
        source_string=source,
        ref_rva=str(raw.get("ref_rva") or ""),
        descriptor_rva=_descriptor_rva(window, ref_index),
        chunk_offset=chunk_offset,
        chunk_length=chunk_length,
        chunk_text=chunk_text,
        target_helper=target_helper,
    )


def _ref_index(window: list[dict[str, Any]], ref_rva: str) -> int | None:
    for index, item in enumerate(window):
        if item.get("is_ref") is True:
            return index
    for index, item in enumerate(window):
        if str(item.get("rva") or "") == ref_rva:
            return index
    return None


def _chunk_offset(window: list[dict[str, Any]], ref_index: int) -> int | None:
    ref = window[ref_index]
    instruction = f"{ref.get('mnemonic') or ''} {ref.get('op_str') or ''}"
    if "rdx, [rip" in instruction:
        return 0
    for item in window[ref_index : min(len(window), ref_index + 3)]:
        if item.get("mnemonic") == "add" and str(item.get("op_str") or "").startswith("rax, "):
            return _parse_int(str(item.get("op_str")).split(",", 1)[1].strip())
    return None


def _chunk_length(window: list[dict[str, Any]], ref_index: int) -> int | None:
    start = max(0, ref_index - 4)
    stop = min(len(window), ref_index + 6)
    for item in window[start:stop]:
        if item.get("mnemonic") == "mov" and str(item.get("op_str") or "").startswith("r8d, "):
            return _parse_int(str(item.get("op_str")).split(",", 1)[1].strip())
    return None


def _next_call_target(window: list[dict[str, Any]], ref_index: int) -> str | None:
    for item in window[ref_index : min(len(window), ref_index + 8)]:
        if item.get("mnemonic") == "call":
            return str(item.get("op_str") or "")
    return None


def _descriptor_rva(window: list[dict[str, Any]], ref_index: int) -> str | None:
    for item in window[ref_index : min(len(window), ref_index + 8)]:
        if item.get("mnemonic") != "lea":
            continue
        op_str = str(item.get("op_str") or "")
        if not op_str.startswith("rcx, [rip + "):
            continue
        rva = _parse_int(str(item.get("rva") or ""))
        disp = _rip_disp(op_str)
        size = _instruction_size(item)
        if rva is None or disp is None or size is None:
            return None
        return hex(rva + size + disp)
    return None


def _rip_disp(op_str: str) -> int | None:
    match = re.search(r"rip\s*\+\s*(0x[0-9a-fA-F]+|\d+)", op_str)
    if not match:
        return None
    return _parse_int(match.group(1))


def _instruction_size(item: dict[str, Any]) -> int | None:
    raw = str(item.get("bytes") or "").strip()
    if not raw:
        return None
    return len(raw.split())


def _parse_int(value: str) -> int | None:
    try:
        return int(value, 0)
    except ValueError:
        return None


def _binary_name(value: Any) -> str | None:
    if not value:
        return None
    return str(value).replace("\\", "/").rstrip("/").rsplit("/", 1)[-1]


def _looks_local_path(value: str) -> bool:
    normalized = value.replace("\\", "/")
    return ":/" in normalized or normalized.startswith("/mnt/")
