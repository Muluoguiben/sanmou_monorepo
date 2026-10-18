from __future__ import annotations

from typing import Any

from .models import ClientImportQueueItem
from .utils import (
    _int_dict,
    _str_list,
    _unique_strs,
)


def _gameassembly_function_pointer_table_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-function-pointer-table-probe")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(
            conclusion.get("interpretation")
            or "function pointer table probe did not recover InitLuaEnv ownership"
        ),
        "dispatcher pointers classify as known IL2CPP tables, not standalone initializer ownership",
        "GameAssembly function pointer table evidence is not publishable game knowledge",
    ] + _str_list(evidence.get("limitations"))
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-function-pointer-table-known-table-route",
            queue_type="gameassembly_function_pointer_table_probe_target",
            priority=115,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly function pointer table / indirect initializer route closure",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "treat dispatcher pointer hits as known-table evidence, not method ownership",
                "recover protected global-metadata method-definition ownership",
                "inspect only outside-known-table pointer runs if they gain metadata or registration signal",
            ],
            counts={
                "function_pointer_hit_count": int(counts.get("function_pointer_hit_count") or 0),
                "known_method_table_count": int(counts.get("known_method_table_count") or 0),
                "known_code_registration_field_table_count": int(
                    counts.get("known_code_registration_field_table_count") or 0
                ),
                "known_codegen_method_table_hit_count": int(
                    counts.get("known_codegen_method_table_hit_count") or 0
                ),
                "known_code_registration_field_hit_count": int(
                    counts.get("known_code_registration_field_hit_count") or 0
                ),
                "outside_known_table_hit_count": int(
                    counts.get("outside_known_table_hit_count") or 0
                ),
                "relevant_function_pointer_hit_count": int(
                    counts.get("relevant_function_pointer_hit_count") or 0
                ),
                "outside_known_table_relevant_hit_count": int(
                    counts.get("outside_known_table_relevant_hit_count") or 0
                ),
                "global_metadata_function_pointer_hit_count": int(
                    counts.get("global_metadata_function_pointer_hit_count") or 0
                ),
                "dispatcher_pointer_hit_count": int(
                    counts.get("dispatcher_pointer_hit_count") or 0
                ),
                "dispatcher_pointer_hits_outside_known_tables": int(
                    counts.get("dispatcher_pointer_hits_outside_known_tables") or 0
                ),
                "initializer_candidate_table_count": int(
                    counts.get("initializer_candidate_table_count") or 0
                ),
                "init_lua_env_method_pointer_recovered": int(
                    counts.get("init_lua_env_method_pointer_recovered") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "function_pointer_tables_scanned": conclusion.get(
                    "function_pointer_tables_scanned"
                ),
                "dispatcher_pointer_hits_classified_as_known_il2cpp_tables": conclusion.get(
                    "dispatcher_pointer_hits_classified_as_known_il2cpp_tables"
                ),
                "global_metadata_function_pointer_hits_found": conclusion.get(
                    "global_metadata_function_pointer_hits_found"
                ),
                "outside_known_table_relevant_pointer_hits_found": conclusion.get(
                    "outside_known_table_relevant_pointer_hits_found"
                ),
                "independent_initializer_table_candidate_found": conclusion.get(
                    "independent_initializer_table_candidate_found"
                ),
                "initializer_table_route_recovered": conclusion.get(
                    "initializer_table_route_recovered"
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


def _gameassembly_metadata_registration_candidate_taxonomy_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    source_id = str(
        evidence.get("source_id") or "gameassembly-metadata-registration-candidate-taxonomy"
    )
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(
            conclusion.get("strongest_current_signal")
            or "exact-ref metadata candidates are tiny-count family evidence"
        ),
        str(
            conclusion.get("strongest_negative_signal")
            or "metadata owner and InitLuaEnv pointer remain unresolved"
        ),
        str(
            conclusion.get("search_policy")
            or "require decoded metadata or a proven owner before method mapping"
        ),
        "GameAssembly MetadataRegistration candidate taxonomy is not publishable game knowledge",
    ] + _str_list(evidence.get("limitations"))
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-metadata-registration-candidate-taxonomy-owner-route",
            queue_type="gameassembly_metadata_registration_candidate_taxonomy_target",
            priority=116,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly MetadataRegistration candidate taxonomy / protected metadata ownership route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "demote tiny-count exact-ref candidates as weak routing evidence",
                "require decoded metadata or a proven MetadataRegistration owner before method mapping",
                "continue toward protected global-metadata method-definition ownership",
            ],
            counts={
                "metadata_candidate_window_count": int(
                    counts.get("metadata_candidate_window_count") or 0
                ),
                "exact_ref_candidate_count": int(counts.get("exact_ref_candidate_count") or 0),
                "exact_ref_non_tiny_candidate_count": int(
                    counts.get("exact_ref_non_tiny_candidate_count") or 0
                ),
                "exact_ref_max_count": int(counts.get("exact_ref_max_count") or 0),
                "high_count_candidate_count": int(counts.get("high_count_candidate_count") or 0),
                "strong_high_count_candidate_count": int(
                    counts.get("strong_high_count_candidate_count") or 0
                ),
                "referenced_high_count_candidate_count": int(
                    counts.get("referenced_high_count_candidate_count") or 0
                ),
                "shifted_window_cluster_count": int(
                    counts.get("shifted_window_cluster_count") or 0
                ),
                "metadata_ref_family_cluster_count": int(
                    counts.get("metadata_ref_family_cluster_count") or 0
                ),
                "metadata_registration_owner_recovered": int(
                    counts.get("metadata_registration_owner_recovered") or 0
                ),
                "init_lua_env_method_pointer_recovered": int(
                    counts.get("init_lua_env_method_pointer_recovered") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "metadata_candidate_taxonomy_completed": conclusion.get(
                    "metadata_candidate_taxonomy_completed"
                ),
                "exact_ref_metadata_candidates_are_tiny_count_family": conclusion.get(
                    "exact_ref_metadata_candidates_are_tiny_count_family"
                ),
                "high_count_metadata_like_candidates_found": conclusion.get(
                    "high_count_metadata_like_candidates_found"
                ),
                "high_count_candidates_have_exact_refs": conclusion.get(
                    "high_count_candidates_have_exact_refs"
                ),
                "metadata_registration_owner_recovered": conclusion.get(
                    "metadata_registration_owner_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "init_lua_env_method_pointer_recovered": conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _gameassembly_global_metadata_owner_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "global-metadata string refs are route evidence only"),
        str(conclusion.get("strongest_negative_signal") or "global-metadata owner remains unresolved"),
        str(conclusion.get("search_policy") or "require file-buffer ownership or decoded metadata before promotion"),
        "GameAssembly global-metadata owner probe is not publishable game knowledge",
    ] + _str_list(evidence.get("limitations"))
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-global-metadata-owner-route-closure",
            queue_type="gameassembly_global_metadata_owner_probe_target",
            priority=112,
            readiness="static_trace_target",
            domain="metadata",
            topic="GameAssembly global-metadata.dat string-ref owner route closure",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "do not promote global-metadata string refs alone as loader ownership",
                "recover protected metadata method-definition ownership or a proven file-buffer owner",
                "use decoded metadata or MetadataRegistration ownership before mapping InitLuaEnv",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(
                    evidence.get("source_id") or "gameassembly-global-metadata-owner-probe"
                ),
                "round": evidence.get("round"),
                "global_metadata_owner_candidate_found": conclusion.get(
                    "global_metadata_owner_candidate_found"
                ),
                "global_metadata_string_refs_confirmed": conclusion.get(
                    "global_metadata_string_refs_confirmed"
                ),
                "file_or_mapping_api_link_found": conclusion.get(
                    "file_or_mapping_api_link_found"
                ),
                "metadata_registration_candidate_link_found": conclusion.get(
                    "metadata_registration_candidate_link_found"
                ),
                "metadata_registration_owner_recovered": conclusion.get(
                    "metadata_registration_owner_recovered"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "init_lua_env_method_pointer_recovered": conclusion.get(
                    "init_lua_env_method_pointer_recovered"
                ),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _global_metadata_transform_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        "global-metadata.dat file-only bounded transforms did not recover plaintext metadata",
        "InitLuaEnv method ownership remains blocked until loader mutation point or protected metadata is recovered",
        "global metadata transform probe is not publishable game knowledge",
    ] + [str(item) for item in conclusion.get("verdict") or []]
    return [
        ClientImportQueueItem(
            queue_id="global-metadata-transform-probe-loader-mutation-route",
            queue_type="global_metadata_transform_probe_target",
            priority=103,
            readiness="static_trace_target",
            domain="metadata",
            topic="protected global-metadata.dat transform probe / loader mutation route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "pivot from file-only transforms to the loader mutation point",
                "trace file API plus 16-byte loop functions that consume global-metadata.dat +8 payload",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "global-metadata-transform-probe"),
                "round": evidence.get("round"),
                "protected_wrapper_confirmed": conclusion.get("protected_wrapper_confirmed"),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "init_lua_env_method_ownership_recovered": conclusion.get(
                    "init_lua_env_method_ownership_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _global_metadata_loader_scan_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_deep_slice: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    deep_conclusion = (
        resolved_by_deep_slice.get("route_conclusion")
        if isinstance(resolved_by_deep_slice, dict)
        else {}
    ) or {}
    if deep_conclusion.get("targets_closed_as_metadata_loader_candidates"):
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "global metadata loader scan is routing evidence only"),
        str(conclusion.get("strongest_negative_signal") or "no full loader-mutation gate candidate was found"),
        str(conclusion.get("search_policy") or "require metadata wrapper or payload-buffer provenance before promotion"),
        "global metadata loader-mutation scan is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="global-metadata-loader-mutation-scan-deep-slice",
            queue_type="global_metadata_loader_scan_target",
            priority=104,
            readiness="static_trace_target",
            domain="metadata",
            topic="global-metadata.dat loader mutation provenance scan",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "deep-slice NEP2 file+16 candidates for path and buffer ownership",
                "require standard IL2CPP header pairs plus readable strings before metadata recovery promotion",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "global-metadata-loader-scan"),
                "round": evidence.get("round"),
                "full_loader_mutation_candidate_found": conclusion.get(
                    "full_loader_mutation_candidate_found"
                ),
                "file_api_16byte_candidates_found": conclusion.get(
                    "file_api_16byte_candidates_found"
                ),
                "metadata_reference_candidates_found": conclusion.get(
                    "metadata_reference_candidates_found"
                ),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "init_lua_env_method_ownership_recovered": conclusion.get(
                    "init_lua_env_method_ownership_recovered"
                ),
                "textasset_payload_owner_proven": conclusion.get(
                    "textasset_payload_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _nep2_metadata_loader_deep_slice_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_read_mapping_scan: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    read_mapping_conclusion = (
        resolved_by_read_mapping_scan.get("route_conclusion")
        if isinstance(resolved_by_read_mapping_scan, dict)
        else {}
    ) or {}
    if read_mapping_conclusion.get("actual_read_mapping_owners_found"):
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "NEP2 metadata loader deep-slice is static evidence only"),
        str(conclusion.get("strongest_negative_signal") or "metadata loader was not proven"),
        str(conclusion.get("search_policy") or "continue with provenance-backed read/mapping owners only"),
        "NEP2 global metadata loader deep-slice is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="nep2-global-metadata-loader-deep-slice-pivot",
            queue_type="nep2_metadata_loader_deep_slice_target",
            priority=104,
            readiness="static_trace_target",
            domain="metadata",
            topic="NEP2 0xd410/0xd870 metadata-loader closure and ReadFile owner pivot",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "prioritize actual ReadFile/MapViewOfFile owners instead of directory enumeration helpers",
                "require file-buffer ownership before promoting metadata loader recovery",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "nep2-metadata-loader-deep-slice"),
                "round": evidence.get("round"),
                "target_rvas": evidence.get("target_rvas") or [],
                "targets_closed_as_metadata_loader_candidates": conclusion.get(
                    "targets_closed_as_metadata_loader_candidates"
                ),
                "global_metadata_loader_proven": conclusion.get(
                    "global_metadata_loader_proven"
                ),
                "file_buffer_owner_proven": conclusion.get("file_buffer_owner_proven"),
                "metadata_wrapper_or_string_provenance_found": conclusion.get(
                    "metadata_wrapper_or_string_provenance_found"
                ),
                "read_or_mapping_proven": conclusion.get("read_or_mapping_proven"),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "init_lua_env_method_ownership_recovered": conclusion.get(
                    "init_lua_env_method_ownership_recovered"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _nep2_read_mapping_owner_scan_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_init_data_owner_scan: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    init_data_counts = (
        resolved_by_init_data_owner_scan.get("counts")
        if isinstance(resolved_by_init_data_owner_scan, dict)
        else {}
    ) or {}
    if init_data_counts.get("inspected_function_count"):
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "NEP2 read/mapping owner scan is static evidence only"),
        str(conclusion.get("strongest_negative_signal") or "metadata-linked read/mapping owner was not proven"),
        str(conclusion.get("search_policy") or "continue only with provenance-backed read/mapping owners"),
        "NEP2 read/mapping owner scan is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="nep2-read-mapping-owner-scan-pivot",
            queue_type="nep2_read_mapping_owner_scan_target",
            priority=104,
            readiness="static_trace_target",
            domain="metadata",
            topic="NEP2 actual ReadFile/MapViewOfFile/GetFileSize owner provenance scan",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "deep-slice only provenance-linked read/mapping owners",
                "pivot to NEP2 InitLuaScriptsScan / CGameProtector data ownership if no provenance-linked owner exists",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "nep2-read-mapping-owner-scan"),
                "round": evidence.get("round"),
                "actual_read_mapping_owners_found": conclusion.get(
                    "actual_read_mapping_owners_found"
                ),
                "metadata_linked_read_mapping_owner_found": conclusion.get(
                    "metadata_linked_read_mapping_owner_found"
                ),
                "global_metadata_loader_proven": conclusion.get(
                    "global_metadata_loader_proven"
                ),
                "file_buffer_owner_proven": conclusion.get("file_buffer_owner_proven"),
                "metadata_wrapper_or_string_provenance_found": conclusion.get(
                    "metadata_wrapper_or_string_provenance_found"
                ),
                "luascripts_or_init_scan_provenance_found": conclusion.get(
                    "luascripts_or_init_scan_provenance_found"
                ),
                "protected_payload_signal_found": conclusion.get(
                    "protected_payload_signal_found"
                ),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "init_lua_env_method_ownership_recovered": conclusion.get(
                    "init_lua_env_method_ownership_recovered"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _nep2_init_data_owner_scan_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "NEP2 init data-owner scan is static evidence only"),
        str(conclusion.get("strongest_negative_signal") or "payload owner was not proven"),
        str(conclusion.get("search_policy") or "continue only with payload-proven owner tracing"),
        "NEP2 InitLuaScriptsScan/CGameProtector data-owner scan is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="nep2-init-data-owner-scan-pivot",
            queue_type="nep2_init_data_owner_scan_target",
            priority=104,
            readiness="static_trace_target",
            domain="protector",
            topic="NEP2 InitLuaScriptsScan / CGameProtector data-reference ownership scan",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "deep-slice only if payload provenance can be attached",
                "prioritize TextAsset/LuaScripts payload decoder recovery when RTTI data ownership stays negative",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "nep2-init-data-owner-scan"),
                "round": evidence.get("round"),
                "init_luascripts_bridge_metadata_confirmed": conclusion.get(
                    "init_luascripts_bridge_metadata_confirmed"
                ),
                "data_reference_owners_found": conclusion.get("data_reference_owners_found"),
                "bridge_record_code_pointers_found": conclusion.get(
                    "bridge_record_code_pointers_found"
                ),
                "payload_owner_candidate_found": conclusion.get(
                    "payload_owner_candidate_found"
                ),
                "file_buffer_owner_proven": conclusion.get("file_buffer_owner_proven"),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "global_metadata_loader_proven": conclusion.get(
                    "global_metadata_loader_proven"
                ),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _nep2_vector_candidate_provenance_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "NEP2 vector candidate provenance trace is static evidence only"),
        str(conclusion.get("strongest_negative_signal") or "selected vector helpers lack payload-buffer provenance"),
        str(conclusion.get("search_policy") or "promote only provenance-linked vector helpers"),
        "NEP2 vector/helper candidate provenance is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="nep2-vector-candidate-provenance-payload-owner-pivot",
            queue_type="nep2_vector_candidate_provenance_target",
            priority=105,
            readiness="static_trace_target",
            domain="metadata",
            topic="NEP2 vector/helper candidate provenance and payload-owner pivot",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "demote isolated vector helpers unless payload-buffer provenance is attached",
                "recover TextAsset/LuaScripts or global-metadata payload owner before decoder promotion",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "nep2-vector-candidate-provenance"),
                "round": evidence.get("round"),
                "vector_candidate_provenance_link_found": conclusion.get(
                    "vector_candidate_provenance_link_found"
                ),
                "read_mapping_to_vector_path_found": conclusion.get(
                    "read_mapping_to_vector_path_found"
                ),
                "read_mapping_to_file_helper_path_found": conclusion.get(
                    "read_mapping_to_file_helper_path_found"
                ),
                "metadata_or_luascripts_keyword_link_found": conclusion.get(
                    "metadata_or_luascripts_keyword_link_found"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _nep2_vector_wrapper_owner_probe_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "NEP2 vector-wrapper owner probe is static evidence only"),
        str(conclusion.get("strongest_negative_signal") or "vector-wrapper route lacks payload-buffer provenance"),
        str(conclusion.get("search_policy") or "demote isolated vector-wrapper clusters"),
        "NEP2 vector-wrapper owner probe is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="nep2-vector-wrapper-owner-probe-route-closure",
            queue_type="nep2_vector_wrapper_owner_probe_target",
            priority=105,
            readiness="static_trace_target",
            domain="metadata",
            topic="NEP2 vector-wrapper owner probe route closure",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "avoid isolated vector-wrapper work until payload-buffer provenance is attached",
                "recover TextAsset/LuaScripts or global-metadata payload owner before decoder promotion",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "nep2-vector-wrapper-owner-probe"),
                "round": evidence.get("round"),
                "vector_wrapper_owner_candidate_found": conclusion.get(
                    "vector_wrapper_owner_candidate_found"
                ),
                "vector_wrapper_payload_owner_proven": conclusion.get(
                    "vector_wrapper_payload_owner_proven"
                ),
                "read_mapping_to_vector_wrapper_path_found": conclusion.get(
                    "read_mapping_to_vector_wrapper_path_found"
                ),
                "read_mapping_import_in_vector_wrapper_found": conclusion.get(
                    "read_mapping_import_in_vector_wrapper_found"
                ),
                "file_helper_to_vector_wrapper_bridge_found": conclusion.get(
                    "file_helper_to_vector_wrapper_bridge_found"
                ),
                "metadata_or_luascripts_keyword_link_found": conclusion.get(
                    "metadata_or_luascripts_keyword_link_found"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _nep2_file_helper_caller_provenance_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "NEP2 file-helper caller provenance trace is static evidence only"),
        str(conclusion.get("strongest_negative_signal") or "file-helper context lacks payload-buffer provenance"),
        str(conclusion.get("search_policy") or "treat file helper as generic unless payload owner is recovered"),
        "NEP2 file-helper caller provenance is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="nep2-file-helper-caller-provenance-route-closure",
            queue_type="nep2_file_helper_caller_provenance_target",
            priority=104,
            readiness="static_trace_target",
            domain="metadata",
            topic="NEP2 file-helper caller provenance route closure",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "keep 0xda90/0xd720 demoted unless a payload-path caller is recovered",
                "continue with GameAssembly MetadataRegistration or protected global-metadata ownership routes",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(
                    evidence.get("source_id") or "nep2-file-helper-caller-provenance"
                ),
                "round": evidence.get("round"),
                "file_helper_payload_owner_proven": conclusion.get(
                    "file_helper_payload_owner_proven"
                ),
                "read_mapping_to_file_helper_path_found": conclusion.get(
                    "read_mapping_to_file_helper_path_found"
                ),
                "metadata_or_luascripts_keyword_link_found": conclusion.get(
                    "metadata_or_luascripts_keyword_link_found"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _gameassembly_resolver_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    target = evidence.get("target") or {}
    counts = _int_dict(evidence.get("counts") or {})
    if not target and not counts:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-resolver-trace")
    conclusion = evidence.get("route_conclusion") or {}
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    notable_callers = [
        item for item in evidence.get("notable_caller_functions") or [] if isinstance(item, dict)
    ]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "GameAssembly resolver trace evidence only"),
        str(conclusion.get("strongest_negative_signal") or "payload owner is not proven"),
        str(conclusion.get("search_policy") or "recover method or payload ownership before decoder promotion"),
        "GameAssembly resolver candidate trace is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-resolver-trace-0x5ccc30",
            queue_type="gameassembly_resolver_trace_target",
            priority=101,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="GameAssembly 0x5ccc30 xLua API descriptor resolver / payload owner route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "trace descriptor callers only when they prove TextAsset payload-buffer ownership",
                "recover protected global-metadata before promoting method ownership",
            ],
            counts={
                **counts,
                "notable_caller_functions": len(notable_callers),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "resolver_candidate_rva": target.get("resolver_candidate_rva"),
                "resolver_candidate_function_found": conclusion.get(
                    "resolver_candidate_function_found"
                ),
                "descriptor_resolver_pattern_supported": conclusion.get(
                    "descriptor_resolver_pattern_supported"
                ),
                "candidate_has_payload_owner_signal": conclusion.get(
                    "candidate_has_payload_owner_signal"
                ),
                "method_ownership_recovered": conclusion.get("method_ownership_recovered"),
                "textasset_payload_owner_proven": conclusion.get(
                    "textasset_payload_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            },
        )
    ]


def _gameassembly_resolver_caller_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    target = evidence.get("target") or {}
    counts = _int_dict(evidence.get("counts") or {})
    if not target and not counts:
        return []
    source_id = str(evidence.get("source_id") or "gameassembly-resolver-caller-trace")
    conclusion = evidence.get("route_conclusion") or {}
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "GameAssembly resolver caller trace evidence only"),
        str(conclusion.get("strongest_negative_signal") or "payload owner is not proven"),
        str(conclusion.get("search_policy") or "recover payload owner before decoder promotion"),
        "GameAssembly resolver caller payload trace is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="gameassembly-resolver-caller-payload-owner-trace",
            queue_type="gameassembly_resolver_caller_trace_target",
            priority=102,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="GameAssembly 0x5ccc30 direct caller payload-owner negative route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "recover protected global-metadata for InitLuaEnv method ownership",
                "stop chasing descriptor-only resolver callers without payload ownership",
            ],
            counts={
                **counts,
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "resolver_candidate_rva": target.get("resolver_candidate_rva"),
                "all_direct_resolver_callers_scanned": conclusion.get(
                    "all_direct_resolver_callers_scanned"
                ),
                "resolver_layer_has_payload_owner_candidate": conclusion.get(
                    "resolver_layer_has_payload_owner_candidate"
                ),
                "textasset_payload_owner_proven": conclusion.get(
                    "textasset_payload_owner_proven"
                ),
                "file_buffer_payload_owner_proven": conclusion.get(
                    "file_buffer_payload_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            },
        )
    ]
