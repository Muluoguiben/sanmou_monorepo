from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.runtime_init_registry_probe.v1"
SOURCE_SITE = "nslg_client_runtime_init_registry_probe"
SOURCE_URL = "local-nslg-client-runtime-init-registry-probe"


class RuntimeInitRegistryInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class RuntimeInitRegistryEntry(BaseModel):
    index: int = 0
    assembly_name: str = ""
    namespace: str = ""
    class_name: str = ""
    method_name: str = ""
    load_types: int = 0
    is_unity_class: bool = False


class RuntimeInitRegistryModuleRecord(BaseModel):
    module: str = Field(min_length=1)
    present: bool = False
    size_bytes: int = 0
    sha256: str = ""
    string_hits: dict[str, dict[str, Any]] = Field(default_factory=dict)
    pe_summary: dict[str, Any] = Field(default_factory=dict)


class RuntimeInitRegistryProbeReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[RuntimeInitRegistryInputArtifact] = Field(default_factory=list)
    registry_summary: dict[str, Any] = Field(default_factory=dict)
    module_records: list[RuntimeInitRegistryModuleRecord] = Field(default_factory=list)
    unityplayer_runtime_json_xrefs: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_runtime_init_registry_probe_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> RuntimeInitRegistryProbeReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    registry = _registry_summary(_safe_map(data.get("registry_summary")))
    conclusion = _safe_map(data.get("route_conclusion"))
    return RuntimeInitRegistryProbeReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        registry_summary=registry,
        module_records=[
            _module_record(item)
            for item in data.get("module_records") or []
            if isinstance(item, dict)
        ],
        unityplayer_runtime_json_xrefs=_unity_refs(
            _safe_map(data.get("unityplayer_runtime_json_xrefs"))
        ),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static runtime-init registry probe only; no live instrumentation, account data, or online protocol data is included",
            "registry entries contain managed names and loadTypes only unless address/token fields are explicitly present",
            "method ownership must come from protected metadata or IL2CPP registration evidence, not registry names alone",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_runtime_init_registry_probe_report(
    report: RuntimeInitRegistryProbeReport,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> RuntimeInitRegistryInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return RuntimeInitRegistryInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _registry_summary(raw: dict[str, Any]) -> dict[str, Any]:
    entries = [
        RuntimeInitRegistryEntry(
            index=int(item.get("index") or 0),
            assembly_name=str(item.get("assembly_name") or ""),
            namespace=str(item.get("namespace") or ""),
            class_name=str(item.get("class_name") or ""),
            method_name=str(item.get("method_name") or ""),
            load_types=int(item.get("load_types") or 0),
            is_unity_class=bool(item.get("is_unity_class")),
        ).model_dump(mode="json")
        for item in raw.get("entries") or []
        if isinstance(item, dict)
    ]
    init_entries = [
        RuntimeInitRegistryEntry(
            index=int(item.get("index") or 0),
            assembly_name=str(item.get("assembly_name") or ""),
            namespace=str(item.get("namespace") or ""),
            class_name=str(item.get("class_name") or ""),
            method_name=str(item.get("method_name") or ""),
            load_types=int(item.get("load_types") or 0),
            is_unity_class=bool(item.get("is_unity_class")),
        ).model_dump(mode="json")
        for item in raw.get("init_lua_env_entries") or []
        if isinstance(item, dict)
    ]
    return {
        "file_name": Path(str(raw.get("file_name") or "RuntimeInitializeOnLoads.json")).name,
        "present": bool(raw.get("present")),
        "size_bytes": int(raw.get("size_bytes") or 0),
        "sha256": str(raw.get("sha256") or ""),
        "entry_count": int(raw.get("entry_count") or 0),
        "unity_class_entry_count": int(raw.get("unity_class_entry_count") or 0),
        "non_unity_class_entry_count": int(raw.get("non_unity_class_entry_count") or 0),
        "load_type_counts": _int_dict(_safe_map(raw.get("load_type_counts"))),
        "entries": entries[:64],
        "init_lua_env_entries": init_entries[:8],
        "address_or_token_field_count": int(raw.get("address_or_token_field_count") or 0),
        "address_or_token_fields": [str(item) for item in raw.get("address_or_token_fields") or []],
        "schema_fields": [str(item) for item in raw.get("schema_fields") or []],
    }


def _module_record(raw: dict[str, Any]) -> RuntimeInitRegistryModuleRecord:
    hits: dict[str, dict[str, Any]] = {}
    for key, value in _safe_map(raw.get("string_hits")).items():
        if not isinstance(value, dict):
            continue
        hits[str(key)] = {
            "count_capped": int(value.get("count_capped") or 0),
            "sample_file_offsets_hex": [
                str(item) for item in value.get("sample_file_offsets_hex") or []
            ][:8],
        }
    return RuntimeInitRegistryModuleRecord(
        module=str(raw.get("module") or "unknown"),
        present=bool(raw.get("present")),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        string_hits=hits,
        pe_summary=_safe_map(raw.get("pe_summary")),
    )


def _unity_refs(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "module": str(raw.get("module") or "UnityPlayer.dll"),
        "string_hit_count": int(raw.get("string_hit_count") or 0),
        "code_ref_count": int(raw.get("code_ref_count") or 0),
        "refs": [
            {
                "ref_rva": str(item.get("ref_rva") or ""),
                "target_rva": str(item.get("target_rva") or ""),
                "section": str(item.get("section") or ""),
                "function_begin": str(item.get("function_begin") or ""),
                "function_end": str(item.get("function_end") or ""),
            }
            for item in raw.get("refs") or []
            if isinstance(item, dict)
        ][:32],
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
