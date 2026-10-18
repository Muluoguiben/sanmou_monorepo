from __future__ import annotations

from typing import Any

from .models import ClientImportQueueItem
from .utils import (
    _int_dict,
    _nep2_priority,
    _slug,
    _str_list,
    _unique_strs,
)


def _nep2_static_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    targets = _str_list(evidence.get("next_static_targets"))
    if not targets:
        return []
    source_id = str(evidence.get("source_id") or "nep2-luascripts")
    init_refs = [
        f"NSLG_NEP2_LUASCRIPTS:{source_id}:InitLuaScriptsScan:{item.get('rva')}"
        for item in evidence.get("init_luascripts_occurrences") or []
        if isinstance(item, dict) and item.get("rva")
    ]
    xref_refs = [
        f"NSLG_NEP2_LUASCRIPTS:{source_id}:xref:{item.get('string')}:{item.get('ref_rva')}"
        for item in evidence.get("xrefs") or []
        if isinstance(item, dict) and item.get("ref_rva")
    ]
    evidence_refs = (init_refs + xref_refs)[:24]
    for_string = _str_list(evidence.get("selected_candidate_strings"))[:16]
    items: list[ClientImportQueueItem] = []
    for index, target in enumerate(targets, start=1):
        blockers = _str_list(evidence.get("limitations"))
        blockers.append("static NEP2 evidence does not prove the decryptor body yet")
        items.append(
            ClientImportQueueItem(
                queue_id=f"nep2-static-trace-{index}-{_slug(target)}",
                queue_type="nep2_static_trace_target",
                priority=_nep2_priority(target),
                readiness="static_trace_target",
                domain="protector",
                topic=target,
                source_artifact=source_artifact,
                evidence_refs=evidence_refs,
                blockers=_unique_strs(blockers),
                next_actions=[target],
                counts={
                    "init_luascripts_occurrences": len(evidence.get("init_luascripts_occurrences") or []),
                    "pointer_refs_to_init_luascripts": int(
                        evidence.get("pointer_refs_to_init_luascripts") or 0
                    ),
                    "candidate_string_count": int(evidence.get("candidate_string_count") or 0),
                    "xref_count": int(evidence.get("xref_count") or 0),
                    "string_chunk_registrations": len(evidence.get("string_chunk_registrations") or []),
                    "blocker_count": len(_unique_strs(blockers)),
                },
                metadata={
                    "source_id": source_id,
                    "binary_name": evidence.get("binary_name"),
                    "sha256": evidence.get("sha256"),
                    "selected_candidate_strings": for_string,
                },
            )
        )
    return items


def _gameassembly_static_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    records = [item for item in evidence.get("records") or [] if isinstance(item, dict)]
    if not records:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-route-trace")
    conclusion = evidence.get("route_conclusion") or {}
    evidence_refs = [str(item.get("evidence_ref")) for item in records if item.get("evidence_ref")]
    route_signal_records = [
        item for item in records if int(item.get("route_signal_function_count") or 0) > 0
    ]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "static GameAssembly route evidence only"),
        str(conclusion.get("search_policy") or "recover readable payload decoder before publishing"),
    ]
    if not route_signal_records:
        blockers.append("no static TextAsset/get_bytes -> xluaL_loadbuffer bridge has been proven")
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-static-trace-textasset-loadbuffer-route",
            queue_type="gameassembly_static_trace_target",
            priority=97,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="GameAssembly TextAsset::get_bytes / xluaL_loadbuffer route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=[
                "use GameAssembly route traces as decoder planning evidence only",
                "recover a runtime-independent TextAsset/LuaScripts payload decoder before staging facts",
                "prioritize NEP2 InitLuaScriptsScan if GameAssembly remains wrapper-only",
            ],
            counts={
                "artifact_count": int(evidence.get("artifact_count") or 0),
                "route_signal_record_count": int(evidence.get("route_signal_record_count") or 0),
                "total_target_strings": int(evidence.get("total_target_strings") or 0),
                "total_code_refs": int(evidence.get("total_code_refs") or 0),
                "total_function_refs": int(evidence.get("total_function_refs") or 0),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "binary_name": evidence.get("binary_name"),
                "textasset_loadbuffer_bridge_proven": conclusion.get(
                    "textasset_loadbuffer_bridge_proven"
                ),
                "artifact_kinds": sorted(
                    {str(item.get("artifact_kind")) for item in records if item.get("artifact_kind")}
                ),
            },
        )
    ]


def _nep2_init_bridge_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    records = [item for item in evidence.get("bridge_records") or [] if isinstance(item, dict)]
    if not records:
        return []
    source_id = str(evidence.get("source_id") or "nep2-init-bridge")
    conclusion = evidence.get("route_conclusion") or {}
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "static NEP2 bridge metadata only"),
        str(conclusion.get("strongest_negative_signal") or "payload decoder is not proven"),
        str(conclusion.get("search_policy") or "continue with provenance-backed decoder targets only"),
        "InitLuaScriptsScan RTTI/lambda bridge metadata is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="nep2-init-bridge-trace-initluascriptsscan",
            queue_type="nep2_init_bridge_trace_target",
            priority=99,
            readiness="static_trace_target",
            domain="protector",
            topic="NEP2 InitLuaScriptsScan metadata bridge / LuaScripts payload decoder route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "trace InitLuaScriptsScan only when file-buffer or asset-owner evidence is present",
                "recover a runtime-independent LuaScripts payload decoder before staging facts",
            ],
            counts={
                **_int_dict(evidence.get("counts") or {}),
                "bridge_records": len(records),
                "candidate_functions": len(evidence.get("candidate_functions") or []),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "binary_name": evidence.get("binary_name"),
                "round": evidence.get("round"),
                "bridge_metadata_confirmed": conclusion.get("bridge_metadata_confirmed"),
                "decryptor_body_proven": conclusion.get("decryptor_body_proven"),
                "file_buffer_owner_proven": conclusion.get("file_buffer_owner_proven"),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "bridge_rvas": [str(item.get("rva")) for item in records[:12] if item.get("rva")],
            },
        )
    ]


def _native_boundary_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    modules = [item for item in evidence.get("module_records") or [] if isinstance(item, dict)]
    if not modules:
        return []
    source_id = str(evidence.get("source_id") or "native-loadbuffer-boundary")
    conclusion = evidence.get("route_conclusion") or {}
    counts = _int_dict(evidence.get("counts") or {})
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "static native boundary evidence only"),
        str(conclusion.get("strongest_negative_signal") or "TextAsset to loadbuffer owner is not proven"),
        str(conclusion.get("search_policy") or "continue with provenance-backed buffer-owner tracing only"),
        "native loadbuffer boundary trace is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="native-loadbuffer-boundary-trace-textasset-xlua-owner",
            queue_type="native_loadbuffer_boundary_trace_target",
            priority=100,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="Native TextAsset bytes / xLua loadbuffer boundary trace",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "trace runtime registration tables for InitLuaEnv without live attach",
                "recover TextAsset bytes buffer ownership before xLua loadbuffer",
            ],
            counts={
                **counts,
                "module_records": len(modules),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "module_names": [str(item.get("module")) for item in modules[:12]],
                "native_loadbuffer_export_present": conclusion.get(
                    "native_loadbuffer_export_present"
                ),
                "gameassembly_static_xlua_import_present": conclusion.get(
                    "gameassembly_static_xlua_import_present"
                ),
                "gameassembly_to_xlua_static_bridge_proven": conclusion.get(
                    "gameassembly_to_xlua_static_bridge_proven"
                ),
                "textasset_to_loadbuffer_owner_proven": conclusion.get(
                    "textasset_to_loadbuffer_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            },
        )
    ]


def _runtime_init_route_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_registry_probe: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    conclusion = evidence.get("route_conclusion") or {}
    counts = _int_dict(evidence.get("counts") or {})
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    if not conclusion and not counts:
        return []
    registry_conclusion = (
        resolved_by_registry_probe.get("route_conclusion")
        if isinstance(resolved_by_registry_probe, dict)
        else {}
    ) or {}
    if (
        registry_conclusion.get("init_lua_env_declared_in_registry") is True
        and registry_conclusion.get("registry_contains_native_method_address_or_token") is False
    ):
        return []
    blockers = [
        str(conclusion.get("strongest_current_signal") or "runtime init route evidence only"),
        str(conclusion.get("strongest_blocker") or "metadata/method ownership is not recovered"),
        str(conclusion.get("search_policy") or "recover method ownership before decoder promotion"),
        "runtime init metadata route is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="runtime-init-metadata-route-initluaenv",
            queue_type="runtime_init_metadata_route_target",
            priority=100,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="RuntimeInitializeOnLoad InitLuaEnv / protected metadata route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "recover protected global-metadata method ownership",
                "map InitLuaEnv to native IL2CPP method address before decoder tracing",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "runtime-init-metadata-route"),
                "round": evidence.get("round"),
                "runtime_init_anchor_known": conclusion.get("runtime_init_anchor_known"),
                "runtime_initialize_onloads_file_present": conclusion.get(
                    "runtime_initialize_onloads_file_present"
                ),
                "global_metadata_protected_wrapper_confirmed": conclusion.get(
                    "global_metadata_protected_wrapper_confirmed"
                ),
                "protected_global_metadata_decoded": conclusion.get(
                    "protected_global_metadata_decoded"
                ),
                "init_lua_env_method_address_recovered": conclusion.get(
                    "init_lua_env_method_address_recovered"
                ),
                "textasset_to_loadbuffer_owner_proven": conclusion.get(
                    "textasset_to_loadbuffer_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            },
        )
    ]


def _runtime_init_registry_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_codegen_module_probe: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    codegen_conclusion = (
        resolved_by_codegen_module_probe.get("route_conclusion")
        if isinstance(resolved_by_codegen_module_probe, dict)
        else {}
    ) or {}
    if codegen_conclusion.get("assembly_csharp_codegen_module_found") is True:
        return []
    source_id = str(evidence.get("source_id") or "runtime-init-registry-probe")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "runtime-init registry evidence only"),
        str(conclusion.get("strongest_negative_signal") or "native method address is not recovered"),
        str(conclusion.get("search_policy") or "continue with protected metadata or registration ownership"),
        "RuntimeInitializeOnLoads registry evidence is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="runtime-init-registry-probe-method-ownership",
            queue_type="runtime_init_registry_probe_target",
            priority=109,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="RuntimeInitializeOnLoads InitLuaEnv method ownership route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "recover protected metadata/method ownership for InitLuaEnv",
                "map NSLGame.Patcher.GameUpdater.InitLuaEnv through IL2CPP registration structures",
                "re-check TextAsset.get_bytes and xLua loadbuffer only after method ownership exists",
            ],
            counts={
                "runtime_initialize_entry_count": int(
                    counts.get("runtime_initialize_entry_count") or 0
                ),
                "runtime_initialize_init_lua_env_entry_count": int(
                    counts.get("runtime_initialize_init_lua_env_entry_count") or 0
                ),
                "registry_address_or_token_field_count": int(
                    counts.get("registry_address_or_token_field_count") or 0
                ),
                "unityplayer_runtime_json_code_ref_count": int(
                    counts.get("unityplayer_runtime_json_code_ref_count") or 0
                ),
                "modules_with_init_lua_env_hits": int(
                    counts.get("modules_with_init_lua_env_hits") or 0
                ),
                "modules_with_runtime_init_json_hits": int(
                    counts.get("modules_with_runtime_init_json_hits") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "runtime_initialize_registry_present": conclusion.get(
                    "runtime_initialize_registry_present"
                ),
                "init_lua_env_declared_in_registry": conclusion.get(
                    "init_lua_env_declared_in_registry"
                ),
                "registry_contains_native_method_address_or_token": conclusion.get(
                    "registry_contains_native_method_address_or_token"
                ),
                "unityplayer_runtime_json_loader_xrefs_found": conclusion.get(
                    "unityplayer_runtime_json_loader_xrefs_found"
                ),
                "init_lua_env_native_method_address_recovered": conclusion.get(
                    "init_lua_env_native_method_address_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "textasset_payload_owner_proven": conclusion.get(
                    "textasset_payload_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
            },
        )
    ]


def _gameassembly_codegen_module_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_registration_anchor_probe: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    registration_conclusion = (
        resolved_by_registration_anchor_probe.get("route_conclusion")
        if isinstance(resolved_by_registration_anchor_probe, dict)
        else {}
    ) or {}
    if registration_conclusion.get("codegen_registration_anchor_found") is True:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-codegen-module-probe")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "GameAssembly CodeGenModule probe is static registration evidence only"),
        str(conclusion.get("strongest_negative_signal") or "method names remain blocked by protected metadata"),
        str(conclusion.get("search_policy") or "recover metadata registration ownership before naming method pointers"),
        "GameAssembly CodeGenModule evidence is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-codegen-module-method-ownership",
            queue_type="gameassembly_codegen_module_probe_target",
            priority=110,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly Assembly-CSharp CodeGenModule / method pointer registration route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "recover protected metadata string and method-definition tables",
                "map Assembly-CSharp method indices to method pointer table entries",
                "validate InitLuaEnv ownership before TextAsset/xLua handoff tracing",
            ],
            counts={
                "codegen_module_candidate_count": int(
                    counts.get("codegen_module_candidate_count") or 0
                ),
                "codegen_module_run_count": int(counts.get("codegen_module_run_count") or 0),
                "largest_codegen_module_run_count": int(
                    counts.get("largest_codegen_module_run_count") or 0
                ),
                "assembly_csharp_method_pointer_count": int(
                    counts.get("assembly_csharp_method_pointer_count") or 0
                ),
                "assembly_csharp_method_pointer_text_count": int(
                    counts.get("assembly_csharp_method_pointer_text_count") or 0
                ),
                "assembly_csharp_method_pointer_null_count": int(
                    counts.get("assembly_csharp_method_pointer_null_count") or 0
                ),
                "init_lua_env_method_pointer_recovered": int(
                    counts.get("init_lua_env_method_pointer_recovered") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "assembly_csharp_codegen_module_found": conclusion.get(
                    "assembly_csharp_codegen_module_found"
                ),
                "assembly_csharp_method_pointer_table_found": conclusion.get(
                    "assembly_csharp_method_pointer_table_found"
                ),
                "codegen_module_array_found": conclusion.get("codegen_module_array_found"),
                "init_lua_env_method_pointer_recovered": conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _gameassembly_registration_anchor_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_registration_layout_probe: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    layout_conclusion = (
        resolved_by_registration_layout_probe.get("route_conclusion")
        if isinstance(resolved_by_registration_layout_probe, dict)
        else {}
    ) or {}
    if layout_conclusion.get("code_registration_layout_refined") is True:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-registration-anchor-probe")
    summary = evidence.get("module_array_summary") or {}
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(
            conclusion.get("strongest_current_signal")
            or "CodeRegistration-side CodeGenModules anchor is available"
        ),
        str(
            conclusion.get("strongest_negative_signal")
            or "MetadataRegistration pairing is not recovered"
        ),
        str(
            conclusion.get("search_policy")
            or "recover registration callsite and MetadataRegistration ownership"
        ),
        "GameAssembly registration anchor evidence is not publishable game knowledge",
    ] + _str_list(evidence.get("limitations"))
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-registration-anchor-metadata-registration-map",
            queue_type="gameassembly_registration_anchor_probe_target",
            priority=111,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly CodeRegistration CodeGenModules anchor / MetadataRegistration pairing route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "recover CodeRegistration and MetadataRegistration registration callsite pairing",
                "map Assembly-CSharp method indices to method pointer table entries",
                "validate InitLuaEnv ownership before TextAsset/xLua handoff tracing",
            ],
            counts={
                "declared_codegen_module_count": int(
                    counts.get("declared_codegen_module_count") or 0
                ),
                "parsed_codegen_module_count": int(counts.get("parsed_codegen_module_count") or 0),
                "nonzero_method_module_count": int(
                    counts.get("nonzero_method_module_count") or 0
                ),
                "assembly_csharp_index": int(counts.get("assembly_csharp_index") or 0),
                "assembly_csharp_method_pointer_count": int(
                    counts.get("assembly_csharp_method_pointer_count") or 0
                ),
                "registration_anchor_code_ref_count": int(
                    counts.get("registration_anchor_code_ref_count") or 0
                ),
                "metadata_registration_candidate_count": int(
                    counts.get("metadata_registration_candidate_count") or 0
                ),
                "method_index_to_pointer_map_recovered": int(
                    counts.get("method_index_to_pointer_map_recovered") or 0
                ),
                "init_lua_env_method_pointer_recovered": int(
                    counts.get("init_lua_env_method_pointer_recovered") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "codegen_registration_anchor_found": conclusion.get(
                    "codegen_registration_anchor_found"
                ),
                "full_codegen_module_array_recovered": conclusion.get(
                    "full_codegen_module_array_recovered"
                ),
                "assembly_csharp_module_index_found": conclusion.get(
                    "assembly_csharp_module_index_found"
                ),
                "codegen_registration_callsite_recovered": conclusion.get(
                    "codegen_registration_callsite_recovered"
                ),
                "metadata_registration_candidate_recovered": conclusion.get(
                    "metadata_registration_candidate_recovered"
                ),
                "method_index_to_pointer_map_recovered": conclusion.get(
                    "method_index_to_pointer_map_recovered"
                ),
                "init_lua_env_method_pointer_recovered": conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
                "assembly_csharp_method_pointer_table_rva": summary.get(
                    "assembly_csharp_method_pointer_table_rva"
                ),
            },
        )
    ]


def _gameassembly_registration_layout_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_registration_pair_context_probe: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    pair_context_conclusion = (
        resolved_by_registration_pair_context_probe.get("route_conclusion")
        if isinstance(resolved_by_registration_pair_context_probe, dict)
        else {}
    ) or {}
    if "registration_pair_recovered" in pair_context_conclusion:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-registration-layout-probe")
    layout = evidence.get("primary_code_registration_layout") or {}
    offsets = layout.get("codegen_modules_field_offsets") or {}
    xref = evidence.get("registration_xref_summary") or {}
    metadata_scan = evidence.get("metadata_registration_candidate_scan") or {}
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(
            conclusion.get("strongest_current_signal")
            or "CodeRegistration-like layout start is refined"
        ),
        str(
            conclusion.get("strongest_negative_signal")
            or "registration callsite and MetadataRegistration pairing are not recovered"
        ),
        str(
            conclusion.get("search_policy")
            or "require callsite pairing or decoded metadata before naming method pointers"
        ),
        "GameAssembly registration layout evidence is not publishable game knowledge",
    ] + _str_list(evidence.get("limitations"))
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-registration-layout-metadata-registration-pairing",
            queue_type="gameassembly_registration_layout_probe_target",
            priority=112,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly CodeRegistration layout / MetadataRegistration pairing route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "use 0x4332730 as the CodeRegistration-side layout anchor",
                "recover CodeRegistration and MetadataRegistration registration callsite pairing",
                "validate InitLuaEnv ownership before TextAsset/xLua handoff tracing",
            ],
            counts={
                "code_registration_start_candidate_count": int(
                    counts.get("code_registration_start_candidate_count") or 0
                ),
                "primary_code_registration_start_rva": int(
                    counts.get("primary_code_registration_start_rva") or 0
                ),
                "code_registration_count_pointer_pair_count": int(
                    counts.get("code_registration_count_pointer_pair_count") or 0
                ),
                "code_registration_pointer_only_field_count": int(
                    counts.get("code_registration_pointer_only_field_count") or 0
                ),
                "codegen_modules_field_offset": int(
                    counts.get("codegen_modules_field_offset") or 0
                ),
                "known_codegen_modules_count": int(
                    counts.get("known_codegen_modules_count") or 0
                ),
                "layout_field_row_count": int(counts.get("layout_field_row_count") or 0),
                "registration_code_ref_count": int(
                    counts.get("registration_code_ref_count") or 0
                ),
                "registration_raw_va_ref_count": int(
                    counts.get("registration_raw_va_ref_count") or 0
                ),
                "metadata_registration_candidate_count": int(
                    counts.get("metadata_registration_candidate_count") or 0
                ),
                "metadata_registration_paired_by_callsite": int(
                    counts.get("metadata_registration_paired_by_callsite") or 0
                ),
                "init_lua_env_method_pointer_recovered": int(
                    counts.get("init_lua_env_method_pointer_recovered") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "code_registration_layout_refined": conclusion.get(
                    "code_registration_layout_refined"
                ),
                "round180_owner_inference_corrected": conclusion.get(
                    "round180_owner_inference_corrected"
                ),
                "codegen_modules_field_offset_confirmed": conclusion.get(
                    "codegen_modules_field_offset_confirmed"
                ),
                "registration_callsite_recovered": conclusion.get(
                    "registration_callsite_recovered"
                ),
                "metadata_registration_candidate_recovered": conclusion.get(
                    "metadata_registration_candidate_recovered"
                ),
                "metadata_registration_paired_by_callsite": conclusion.get(
                    "metadata_registration_paired_by_callsite"
                ),
                "method_index_to_pointer_map_recovered": conclusion.get(
                    "method_index_to_pointer_map_recovered"
                ),
                "init_lua_env_method_pointer_recovered": conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
                "candidate_start_rva": layout.get("candidate_start_rva"),
                "candidate_end_rva": layout.get("candidate_end_rva"),
                "codegen_modules_count_offset": offsets.get("count_offset"),
                "codegen_modules_pointer_offset": offsets.get("pointer_offset"),
                "codegen_modules_array_rva": offsets.get("array_rva"),
                "registration_xref_available": xref.get("available"),
                "metadata_candidate_scan_policy": metadata_scan.get("scan_policy"),
            },
        )
    ]


def _gameassembly_registration_pair_context_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-registration-pair-context-probe")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(
            conclusion.get("strongest_current_signal")
            or "MetadataRegistration-like candidates have raw data-family references"
        ),
        str(
            conclusion.get("strongest_negative_signal")
            or "direct CodeRegistration/MetadataRegistration pointer-pair context is not recovered"
        ),
        str(
            conclusion.get("search_policy")
            or "pivot from direct pair xrefs to decoded metadata ownership or initializer trace"
        ),
        "GameAssembly registration pair-context evidence is not publishable game knowledge",
    ] + _str_list(evidence.get("limitations"))
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-registration-pair-context-metadata-ownership",
            queue_type="gameassembly_registration_pair_context_probe_target",
            priority=113,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly CodeRegistration/MetadataRegistration pair-context route closure",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "treat direct pointer-pair xref recovery as negative for this build",
                "pivot to decoded protected metadata method-definition ownership",
                "trace broader IL2CPP initialization dispatcher only if it can be bounded offline",
            ],
            counts={
                "registration_target_count": int(counts.get("registration_target_count") or 0),
                "metadata_target_count": int(counts.get("metadata_target_count") or 0),
                "raw_registration_ref_count": int(
                    counts.get("raw_registration_ref_count") or 0
                ),
                "raw_code_registration_start_ref_count": int(
                    counts.get("raw_code_registration_start_ref_count") or 0
                ),
                "raw_metadata_candidate_ref_count": int(
                    counts.get("raw_metadata_candidate_ref_count") or 0
                ),
                "registration_code_ref_count": int(
                    counts.get("registration_code_ref_count") or 0
                ),
                "metadata_candidate_code_ref_count": int(
                    counts.get("metadata_candidate_code_ref_count") or 0
                ),
                "paired_neighborhood_count": int(
                    counts.get("paired_neighborhood_count") or 0
                ),
                "call_argument_pair_window_count": int(
                    counts.get("call_argument_pair_window_count") or 0
                ),
                "metadata_ref_family_cluster_count": int(
                    counts.get("metadata_ref_family_cluster_count") or 0
                ),
                "registration_pair_recovered": int(
                    counts.get("registration_pair_recovered") or 0
                ),
                "init_lua_env_method_pointer_recovered": int(
                    counts.get("init_lua_env_method_pointer_recovered") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "registration_pair_recovered": conclusion.get("registration_pair_recovered"),
                "metadata_registration_paired_by_callsite": conclusion.get(
                    "metadata_registration_paired_by_callsite"
                ),
                "metadata_candidate_family_refs_found": conclusion.get(
                    "metadata_candidate_family_refs_found"
                ),
                "direct_code_registration_start_ref_found": conclusion.get(
                    "direct_code_registration_start_ref_found"
                ),
                "call_argument_pair_window_found": conclusion.get(
                    "call_argument_pair_window_found"
                ),
                "pair_neighborhood_found": conclusion.get("pair_neighborhood_found"),
                "method_index_to_pointer_map_recovered": conclusion.get(
                    "method_index_to_pointer_map_recovered"
                ),
                "init_lua_env_method_pointer_recovered": conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _gameassembly_initializer_dispatch_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-initializer-dispatch-trace")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(
            conclusion.get("summary")
            or "bounded direct-call dispatcher trace did not recover a registration/metadata owner"
        ),
        "no CodeRegistration or MetadataRegistration candidate owner was recovered",
        "GameAssembly initializer dispatch trace evidence is not publishable game knowledge",
    ] + _str_list(evidence.get("limitations"))
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-initializer-dispatch-indirect-owner-route",
            queue_type="gameassembly_initializer_dispatch_trace_target",
            priority=114,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly bounded initializer dispatcher route closure",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "treat bounded direct-call dispatcher trace as negative for registration pairing",
                "recover protected global-metadata method-definition ownership",
                "inspect indirect initializer tables only when ownership can be bounded offline",
            ],
            counts={
                "function_row_count": int(counts.get("function_row_count") or 0),
                "instruction_count": int(counts.get("instruction_count") or 0),
                "registration_anchor_ref_function_count": int(
                    counts.get("registration_anchor_ref_function_count") or 0
                ),
                "metadata_candidate_ref_function_count": int(
                    counts.get("metadata_candidate_ref_function_count") or 0
                ),
                "global_metadata_string_ref_function_count": int(
                    counts.get("global_metadata_string_ref_function_count") or 0
                ),
                "entry_to_registration_path_found": int(
                    counts.get("entry_to_registration_path_found") or 0
                ),
                "entry_to_metadata_candidate_path_found": int(
                    counts.get("entry_to_metadata_candidate_path_found") or 0
                ),
                "entry_to_global_metadata_path_found": int(
                    counts.get("entry_to_global_metadata_path_found") or 0
                ),
                "nonexec_pointer_hit_count": int(counts.get("nonexec_pointer_hit_count") or 0),
                "dispatcher_candidate_count": int(counts.get("dispatcher_candidate_count") or 0),
                "init_lua_env_method_pointer_recovered": int(
                    counts.get("init_lua_env_method_pointer_recovered") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "initializer_dispatcher_route_recovered": conclusion.get(
                    "initializer_dispatcher_route_recovered"
                ),
                "registration_ownership_recovered": conclusion.get(
                    "registration_ownership_recovered"
                ),
                "metadata_registration_paired_by_dispatch_trace": conclusion.get(
                    "metadata_registration_paired_by_dispatch_trace"
                ),
                "init_lua_env_method_pointer_recovered": conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]
