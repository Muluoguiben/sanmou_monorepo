from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.gameassembly_registration_anchor_probe.v1"
SOURCE_SITE = "nslg_client_gameassembly_registration_anchor_probe"
SOURCE_URL = "local-nslg-client-gameassembly-registration-anchor-probe"


class RegistrationAnchorInputArtifact(BaseModel):
    file_name: str = Field(min_length=1)
    role: str = ""
    size_bytes: int = 0
    sha256: str = ""
    missing: bool = False


class RegistrationAnchorReport(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    source_url: str = SOURCE_URL
    source_site: str = SOURCE_SITE
    generated_at: datetime
    round: int = 0
    slice: str = ""
    input_artifacts: list[RegistrationAnchorInputArtifact] = Field(default_factory=list)
    registration_anchor: dict[str, Any] = Field(default_factory=dict)
    module_array_summary: dict[str, Any] = Field(default_factory=dict)
    code_ref_summary: dict[str, Any] = Field(default_factory=dict)
    counts: dict[str, int] = Field(default_factory=dict)
    route_conclusion: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    next_static_targets: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_registration_anchor_report(
    *,
    input_path: Path,
    source_id: str,
    generated_at: datetime | None = None,
) -> RegistrationAnchorReport:
    generated_at = generated_at or datetime.now(timezone.utc)
    data = json.loads(input_path.read_text(encoding="utf-8"))
    conclusion = _safe_map(data.get("route_conclusion"))
    return RegistrationAnchorReport(
        source_id=source_id,
        generated_at=generated_at,
        round=int(data.get("round") or 0),
        slice=str(data.get("slice") or ""),
        input_artifacts=[
            _input_artifact(item)
            for item in data.get("input_artifacts") or []
            if isinstance(item, dict)
        ],
        registration_anchor=_safe_map(data.get("registration_anchor")),
        module_array_summary=_module_array_summary(_safe_map(data.get("module_array_summary"))),
        code_ref_summary=_code_ref_summary(_safe_map(data.get("code_ref_summary"))),
        counts=_counts(_safe_map(data.get("counts")), conclusion),
        route_conclusion=conclusion,
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        next_static_targets=[str(item) for item in data.get("next_static_targets") or []],
        limitations=[str(item) for item in data.get("limitations") or []],
        guardrails=[
            "offline/static GameAssembly registration anchor probe only; no live instrumentation, account data, or online protocol data is included",
            "CodeGenModules anchors do not name methods without decoded metadata or MetadataRegistration ownership",
            "InitLuaEnv ownership remains blocked until metadata-registration pairing or decoded metadata exists",
            "route evidence is not publishable gameplay knowledge",
        ],
    )


def write_registration_anchor_report(report: RegistrationAnchorReport, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(report.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _input_artifact(raw: dict[str, Any]) -> RegistrationAnchorInputArtifact:
    file_name = str(raw.get("file_name") or raw.get("path") or "unknown").replace("\\", "/")
    return RegistrationAnchorInputArtifact(
        file_name=Path(file_name).name,
        role=str(raw.get("role") or ""),
        size_bytes=int(raw.get("size_bytes") or 0),
        sha256=str(raw.get("sha256") or ""),
        missing=bool(raw.get("missing")),
    )


def _module_array_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "declared_or_scanned_module_count": int(raw.get("declared_or_scanned_module_count") or 0),
        "parsed_module_count": int(raw.get("parsed_module_count") or 0),
        "nonzero_method_module_count": int(raw.get("nonzero_method_module_count") or 0),
        "zero_method_module_count": int(raw.get("zero_method_module_count") or 0),
        "assembly_csharp_index": int(raw.get("assembly_csharp_index") or 0),
        "assembly_csharp_struct_rva": str(raw.get("assembly_csharp_struct_rva") or ""),
        "assembly_csharp_method_pointer_count": int(
            raw.get("assembly_csharp_method_pointer_count") or 0
        ),
        "assembly_csharp_method_pointer_table_rva": str(
            raw.get("assembly_csharp_method_pointer_table_rva") or ""
        ),
        "assembly_csharp_firstpass_index": int(raw.get("assembly_csharp_firstpass_index") or 0),
        "assembly_csharp_firstpass_struct_rva": str(
            raw.get("assembly_csharp_firstpass_struct_rva") or ""
        ),
        "assembly_csharp_firstpass_method_pointer_count": int(
            raw.get("assembly_csharp_firstpass_method_pointer_count") or 0
        ),
        "sample_modules": [
            {
                "index": int(item.get("index") or 0),
                "module_name": str(item.get("module_name") or ""),
                "method_pointer_count": int(item.get("method_pointer_count") or 0),
                "method_pointer_table_rva": str(item.get("method_pointer_table_rva") or ""),
            }
            for item in raw.get("sample_modules") or []
            if isinstance(item, dict)
        ][:24],
    }


def _code_ref_summary(raw: dict[str, Any]) -> dict[str, Any]:
    return {
        "available": bool(raw.get("available")),
        "searched_target_count": int(raw.get("searched_target_count") or 0),
        "code_ref_count": int(raw.get("code_ref_count") or 0),
        "code_refs": [
            {
                "site_rva": str(item.get("site_rva") or ""),
                "target_kind": str(item.get("target_kind") or ""),
                "target_rva": str(item.get("target_rva") or ""),
                "mnemonic": str(item.get("mnemonic") or ""),
                "op_str": str(item.get("op_str") or ""),
            }
            for item in raw.get("code_refs") or []
            if isinstance(item, dict)
        ][:40],
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
