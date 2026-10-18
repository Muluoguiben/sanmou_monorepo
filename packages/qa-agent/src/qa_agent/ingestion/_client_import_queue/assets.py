from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .models import ClientImportQueueItem
from .utils import (
    _build_decoded_audit_index,
    _csv_ints,
    _decoded_hero_priority,
    _float_value,
    _hero_id_from_entry,
    _int_dict,
    _lua_crypto_priority,
    _luascript_priority,
    _prefixed_counts,
    _primary_domain,
    _skill_ids_from_entry,
    _slug,
    _str_list,
    _unique_strs,
)


def _client_resource_surface_gap_scan_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    ns_groups = [item for item in evidence.get("ns_bundle_groups") or [] if isinstance(item, dict)]
    high_value_groups = [
        str(item.get("group"))
        for item in ns_groups
        if str(item.get("group") or "").lower()
        in {
            "luascripts.ns",
            "building.ns",
            "mapres.ns",
            "sprite.ns",
            "sharedassets.ns",
        }
    ]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "resource-surface inventory only"),
        str(conclusion.get("strongest_negative_signal") or "resource bundles are not decoded"),
        str(conclusion.get("search_policy") or "build a sanitized .ns bundle index first"),
        "client resource-surface scan is not publishable gameplay knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="client-resource-surface-gap-ns-bundle-index",
            queue_type="client_resource_surface_gap_scan_target",
            priority=106,
            readiness="static_inventory_target",
            domain="resource_bundle",
            topic="NSLG client .ns resource surface gap and bundle index",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "build a sanitized .ns bundle index",
                "classify .ns headers before attempting payload decode",
            ],
            counts={
                **counts,
                "ns_bundle_group_count": len(ns_groups),
                "high_value_ns_group_count": len(high_value_groups),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "client-resource-surface-gap-scan"),
                "round": evidence.get("round"),
                "resource_surface_gap_identified": conclusion.get(
                    "resource_surface_gap_identified"
                ),
                "resource_cache_bundle_root_found": conclusion.get(
                    "resource_cache_bundle_root_found"
                ),
                "luascripts_ns_found": conclusion.get("luascripts_ns_found"),
                "map_resource_ns_found": conclusion.get("map_resource_ns_found"),
                "decoded_game_knowledge_recovered": conclusion.get(
                    "decoded_game_knowledge_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
                "high_value_ns_groups": high_value_groups,
            },
        )
    ]


def _ns_bundle_format_index_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    priority_records = [
        item for item in evidence.get("priority_records") or [] if isinstance(item, dict)
    ]
    high_value_records = [
        str(item.get("rel_path") or "")
        for item in priority_records
        if str(item.get("asset_group") or "").lower()
        in {
            "luascripts.ns",
            "building.ns",
            "mapres.ns",
            "sprite.ns",
            "sharedassets.ns",
        }
    ]
    blockers = [
        str(conclusion.get("strongest_current_signal") or ".ns format index only"),
        str(
            conclusion.get("strongest_negative_signal")
            or "protected CAB metadata remains unreadable"
        ),
        str(
            conclusion.get("search_policy")
            or "recover protected SerializedFile metadata transform"
        ),
        ".ns bundle format index is not publishable gameplay knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="ns-bundle-format-index-protected-metadata-transform",
            queue_type="ns_bundle_format_index_target",
            priority=107,
            readiness="static_index_target",
            domain="resource_bundle",
            topic="NSLG .ns UnityFS/CAB protected metadata format index",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "recover protected SerializedFile metadata transform",
                "route decoded bundle families into LuaScripts, building, map, UI, and sprite extractors",
            ],
            counts={
                **counts,
                "priority_bundle_count": len(priority_records),
                "high_value_priority_bundle_count": len(high_value_records),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": str(evidence.get("source_id") or "ns-bundle-format-index"),
                "round": evidence.get("round"),
                "ns_bundle_index_built": conclusion.get("ns_bundle_index_built"),
                "unityfs_envelope_parseable": conclusion.get("unityfs_envelope_parseable"),
                "block_info_index_parseable": conclusion.get("block_info_index_parseable"),
                "first_block_decompression_supported": conclusion.get(
                    "first_block_decompression_supported"
                ),
                "serialized_header_parseable": conclusion.get("serialized_header_parseable"),
                "protected_serialized_metadata_present": conclusion.get(
                    "protected_serialized_metadata_present"
                ),
                "all_indexed_bundles_look_protected": conclusion.get(
                    "all_indexed_bundles_look_protected"
                ),
                "decoded_game_knowledge_recovered": conclusion.get(
                    "decoded_game_knowledge_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
                "high_value_priority_bundles": high_value_records,
            },
        )
    ]


def _decoded_hero_review_items(
    staging_entries: list[Any],
    audit: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    index = _build_decoded_audit_index(audit)
    review_actions = _str_list(audit.get("next_review_actions"))[:5]
    items: list[ClientImportQueueItem] = []
    for raw in staging_entries:
        if not isinstance(raw, dict):
            continue
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        entry = raw.get("entry") if isinstance(raw.get("entry"), dict) else {}
        entry_id = str(entry.get("id") or "client-decoded-hero")
        topic = str(entry.get("topic") or entry_id)
        source_ref = str(entry.get("source_ref") or "")
        review_status = str(metadata.get("review_status") or "unknown")
        confidence = _float_value(entry.get("confidence"))
        hero_id = _hero_id_from_entry(entry)
        skill_ids = _skill_ids_from_entry(entry)

        blockers = []
        if review_status != "reviewed":
            blockers.append(f"review_status={review_status}; manual review is required")
        if hero_id in index["unmapped_hero_ids"]:
            blockers.append(f"hero_id={hero_id} is not mapped to a canonical KB hero name")
        if hero_id in index["low_confidence_heroes"]:
            item = index["low_confidence_heroes"][hero_id]
            blockers.append(
                "hero_id="
                f"{hero_id} mapping confidence {item.get('confidence')} requires manual confirmation"
            )
        unmapped_skills = sorted(index["unmapped_skill_ids"].intersection(skill_ids))
        if unmapped_skills:
            blockers.append(f"unmapped decoded skill ids: {_csv_ints(unmapped_skills)}")
        low_confidence_skills = sorted(index["low_confidence_skills"].keys() & skill_ids)
        if low_confidence_skills:
            blockers.append(f"low-confidence decoded skill ids: {_csv_ints(low_confidence_skills)}")
        if not source_ref:
            blockers.append("missing source_ref")

        priority = _decoded_hero_priority(
            confidence=confidence,
            review_status=review_status,
            has_unmapped_hero=hero_id in index["unmapped_hero_ids"],
            unmapped_skill_count=len(unmapped_skills),
            low_confidence_mapping_count=(
                int(hero_id in index["low_confidence_heroes"]) + len(low_confidence_skills)
            ),
        )
        readiness = "reviewed_import_candidate" if review_status == "reviewed" else "needs_manual_review"
        items.append(
            ClientImportQueueItem(
                queue_id=f"decoded-hero-review-{hero_id or _slug(entry_id)}",
                queue_type="decoded_hero_review",
                priority=priority,
                readiness=readiness,
                domain=str(entry.get("domain") or "hero"),
                topic=topic,
                source_artifact=source_artifact,
                source_ref=source_ref or None,
                evidence_refs=[source_ref] if source_ref else [],
                blockers=_unique_strs(blockers),
                next_actions=review_actions
                or [
                    "confirm Chinese name, skill IDs, and field semantics",
                    "promote review_status to reviewed only after manual validation",
                ],
                counts={
                    "skill_id_count": len(skill_ids),
                    "unmapped_skill_id_count": len(unmapped_skills),
                    "blocker_count": len(_unique_strs(blockers)),
                    "confidence_milli": int(confidence * 1000),
                },
                metadata={
                    "entry_id": entry_id,
                    "hero_id": hero_id,
                    "review_status": review_status,
                    "aliases": _str_list(entry.get("aliases"))[:8],
                    "related_topics": _str_list(entry.get("related_topics"))[:8],
                    "skill_ids": skill_ids,
                    "source_site": metadata.get("source_site"),
                    "source_captured_at": metadata.get("source_captured_at"),
                },
            )
        )
    return items


def _luascripts_decoder_items(
    catalog: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    records = [item for item in catalog.get("records") or [] if isinstance(item, dict)]
    high_value_stems = set(_str_list(catalog.get("high_value_stems")))
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record.get("stem") or "unknown")].append(record)

    items: list[ClientImportQueueItem] = []
    for stem, stem_records in sorted(grouped.items()):
        domains = sorted({domain for record in stem_records for domain in _str_list(record.get("kb_domains"))})
        statuses = Counter(str(record.get("extraction_status") or "unknown") for record in stem_records)
        evidence_refs = [
            str(record.get("evidence_ref")) for record in stem_records if record.get("evidence_ref")
        ]
        scenarios = sorted({str(record.get("scenario")) for record in stem_records if record.get("scenario")})
        script_lengths = [
            int(record.get("script_len") or 0)
            for record in stem_records
            if isinstance(record.get("script_len"), int)
        ]
        blocked = statuses.get("obfuscated_binary_pending_decoder", 0) > 0
        blockers = []
        if blocked:
            blockers.append("TextAsset payloads remain obfuscated_binary_pending_decoder")
        blockers.append("catalog metadata is not publishable game knowledge by itself")
        priority = _luascript_priority(stem=stem, domains=domains, record_count=len(stem_records))
        readiness = "blocked_pending_decoder" if blocked else "decoded_payload_review_required"
        items.append(
            ClientImportQueueItem(
                queue_id=f"luascripts-decoder-{_slug(stem)}",
                queue_type="luascripts_decoder_target",
                priority=priority,
                readiness=readiness,
                domain=_primary_domain(domains),
                topic=stem,
                source_artifact=source_artifact,
                evidence_refs=evidence_refs[:24],
                blockers=_unique_strs(blockers),
                next_actions=[
                    f"recover decoder path for LuaScripts stem `{stem}`",
                    "validate decoded payload semantics before staging any knowledge facts",
                    "stage readable records with TextAsset evidence_ref as source_ref",
                ],
                counts={
                    "record_count": len(stem_records),
                    "scenario_count": len(scenarios),
                    "unique_sha1_count": len(
                        {str(record.get("sha1")) for record in stem_records if record.get("sha1")}
                    ),
                    "max_script_len": max(script_lengths) if script_lengths else 0,
                    "blocker_count": len(blockers),
                    **_prefixed_counts("status", statuses),
                },
                metadata={
                    "source_id": catalog.get("source_id"),
                    "stem": stem,
                    "high_value_stem": stem in high_value_stems,
                    "domains": domains,
                    "scenarios": scenarios[:16],
                    "sample_asset_paths": [
                        str(record.get("asset_path"))
                        for record in stem_records[:5]
                        if record.get("asset_path")
                    ],
                    "sample_extracted_artifacts": [
                        str(record.get("extracted_artifact"))
                        for record in stem_records[:5]
                        if record.get("extracted_artifact")
                    ],
                },
            )
        )
    return items


def _lua_crypto_decoder_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    targets = _str_list(evidence.get("next_decoder_targets"))
    if not targets:
        return []
    source_id = str(evidence.get("source_id") or "lua-crypto")
    evidence_refs = [
        f"NSLG_LUA_CRYPTO:{source_id}:{item.get('binary_name')}"
        for item in evidence.get("binary_string_hits") or []
        if isinstance(item, dict) and item.get("binary_name")
    ] + [
        f"NSLG_LUA_CRYPTO:{source_id}:payload:{item.get('file_name')}"
        for item in evidence.get("payload_block_samples") or []
        if isinstance(item, dict) and item.get("file_name")
    ]
    payload_status_counts = Counter(
        {
            str(key): int(value or 0)
            for key, value in (evidence.get("payload_status_counts") or {}).items()
        }
    )
    binary_names = [
        str(item.get("binary_name"))
        for item in evidence.get("binary_string_hits") or []
        if isinstance(item, dict) and item.get("binary_name")
    ]
    payload_names = [
        str(item.get("file_name"))
        for item in evidence.get("payload_block_samples") or []
        if isinstance(item, dict) and item.get("file_name")
    ]

    items: list[ClientImportQueueItem] = []
    for index, target in enumerate(targets, start=1):
        blockers = _str_list(evidence.get("limitations"))
        blockers.append("static crypto evidence does not decode LuaScripts payloads")
        items.append(
            ClientImportQueueItem(
                queue_id=f"lua-crypto-decoder-{index}-{_slug(target)}",
                queue_type="lua_crypto_decoder_target",
                priority=_lua_crypto_priority(target),
                readiness="blocked_pending_decoder",
                domain="lua_scripts",
                topic=target,
                source_artifact=source_artifact,
                evidence_refs=evidence_refs[:24],
                blockers=_unique_strs(blockers),
                next_actions=[target],
                counts={
                    "binary_string_hit_summaries": len(binary_names),
                    "payload_block_samples": len(payload_names),
                    "runtime_initialize_lua_entries": len(
                        evidence.get("runtime_initialize_lua_entries") or []
                    ),
                    "blocker_count": len(_unique_strs(blockers)),
                    **_prefixed_counts("payload_status", payload_status_counts),
                },
                metadata={
                    "source_id": source_id,
                    "binary_names": binary_names,
                    "sample_payloads": payload_names[:12],
                    "sanitized_conclusions": _str_list(evidence.get("sanitized_conclusions"))[:6],
                },
            )
        )
    return items


def _luascripts_cipher_profile_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_variant_corpus: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    profiles = [item for item in evidence.get("payload_profiles") or [] if isinstance(item, dict)]
    variant_corpus = (
        resolved_by_variant_corpus.get("corpus_summary")
        if isinstance(resolved_by_variant_corpus, dict)
        else {}
    )
    if isinstance(variant_corpus, dict) and variant_corpus.get("payload_variant_count"):
        return []
    if not profiles:
        return []
    source_id = str(evidence.get("source_id") or "luascripts-payload-cipher-profile")
    conclusion = evidence.get("route_conclusion") or {}
    simple = evidence.get("simple_transform_summary") or {}
    cross_file = evidence.get("cross_file_block_profile") or {}
    xor_summary = evidence.get("xor_crib_probe_summary") or {}
    blockers = [
        str(conclusion.get("strongest_current_signal") or "static payload profile only"),
        str(conclusion.get("strongest_negative_signal") or "payload decoder is not recovered"),
        str(conclusion.get("search_policy") or "recover readable payload decoder before publishing"),
        "payload cipher profile is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="luascripts-payload-cipher-profile-decoder-route",
            queue_type="luascripts_payload_cipher_profile_target",
            priority=98,
            readiness="blocked_pending_decoder",
            domain="lua_scripts",
            topic="LuaScripts payload cipher profile / decoder boundary route",
            source_artifact=source_artifact,
            evidence_refs=[str(item) for item in evidence.get("evidence_refs") or []][:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_decoder_targets"))
            or ["locate the native buffer owner before xLua loadbuffer"],
            counts={
                "payload_profile_count": int(evidence.get("payload_profile_count") or 0),
                "payload_count": int(simple.get("payload_count") or 0),
                "cross_file_shared_16byte_block_count": int(
                    cross_file.get("cross_file_shared_16byte_block_count") or 0
                ),
                "single_byte_xor_plaintext_like_count": int(
                    xor_summary.get("single_byte_xor_plaintext_like_count") or 0
                ),
                "crib_xor_plaintext_like_count": int(
                    xor_summary.get("crib_xor_plaintext_like_count") or 0
                ),
                "direct_plaintext_term_file_count": int(
                    simple.get("direct_plaintext_term_file_count") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "simple_compression_ruled_out": conclusion.get("simple_compression_ruled_out"),
                "single_byte_or_crib_xor_ruled_out": conclusion.get(
                    "single_byte_or_crib_xor_ruled_out"
                ),
                "ecb_like_shared_block_signal": conclusion.get("ecb_like_shared_block_signal"),
                "sample_payloads": [str(item.get("file_name")) for item in profiles[:12]],
            },
        )
    ]


def _luascripts_variant_corpus_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    corpus = evidence.get("corpus_summary") or {}
    if not corpus.get("payload_variant_count"):
        return []
    source_id = str(evidence.get("source_id") or "luascripts-payload-variant-corpus")
    conclusion = evidence.get("route_conclusion") or {}
    block = evidence.get("block_sharing_summary") or {}
    skip = evidence.get("offset_skip_probe_summary") or {}
    stem_summaries = [
        item for item in evidence.get("stem_summaries") or [] if isinstance(item, dict)
    ]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "expanded encrypted payload corpus only"),
        str(conclusion.get("strongest_negative_signal") or "payload decoder is not recovered"),
        str(conclusion.get("search_policy") or "recover readable payload decoder before publishing"),
        "LuaScripts payload variant corpus is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="luascripts-payload-variant-corpus-decoder-route",
            queue_type="luascripts_payload_variant_corpus_target",
            priority=103,
            readiness="blocked_pending_decoder",
            domain="lua_scripts",
            topic="LuaScripts payload variant corpus / decoder validation route",
            source_artifact=source_artifact,
            evidence_refs=[str(item) for item in evidence.get("evidence_refs") or []][:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_decoder_targets"))
            or ["locate the native TextAsset script-buffer owner before xLua loadbuffer"],
            counts={
                "payload_variant_count": int(corpus.get("payload_variant_count") or 0),
                "relevant_record_count": int(corpus.get("relevant_record_count") or 0),
                "stem_count": int(corpus.get("stem_count") or 0),
                "scenario_count": int(corpus.get("scenario_count") or 0),
                "unique_ciphertext_hash_count": int(
                    corpus.get("unique_ciphertext_hash_count") or 0
                ),
                "duplicate_ciphertext_hash_group_count": int(
                    corpus.get("duplicate_ciphertext_hash_group_count") or 0
                ),
                "cross_cipher_shared_16byte_block_count": int(
                    block.get("cross_cipher_shared_16byte_block_count") or 0
                ),
                "offset_skip_decompression_success_count": int(
                    skip.get("decompression_success_count") or 0
                ),
                "offset_skip_plaintext_hit_count": int(skip.get("plaintext_hit_count") or 0),
                "high_printable_candidate_count": int(
                    skip.get("high_printable_candidate_count") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
                "duplicate_ciphertext_present": conclusion.get("duplicate_ciphertext_present"),
                "cross_cipher_shared_16byte_block_signal": conclusion.get(
                    "cross_cipher_shared_16byte_block_signal"
                ),
                "simple_offset_skip_route_ruled_out": conclusion.get(
                    "simple_offset_skip_route_ruled_out"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
                "sample_stems": [str(item.get("stem")) for item in stem_summaries[:12]],
            },
        )
    ]


def _textasset_payload_owner_trace_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_serialized_layout: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    layout_conclusion = (
        resolved_by_serialized_layout.get("route_conclusion")
        if isinstance(resolved_by_serialized_layout, dict)
        else {}
    ) or {}
    if layout_conclusion.get("serialized_textasset_object_layout_confirmed"):
        return []
    source_id = str(evidence.get("source_id") or "textasset-payload-owner-trace")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_positive_signal") or "static TextAsset route evidence only"),
        str(conclusion.get("strongest_negative_signal") or "payload owner is not proven"),
        str(conclusion.get("search_policy") or "require payload-buffer provenance before promotion"),
        "TextAsset payload owner trace is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="textasset-payload-owner-trace-buffer-provenance",
            queue_type="textasset_payload_owner_trace_target",
            priority=104,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="TextAsset/LuaScripts payload buffer owner provenance route",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "shift from broad string provenance to SerializedFile object layout or managed metadata recovery",
                "require concrete payload pointer plus length provenance before decoder promotion",
            ],
            counts={
                "module_count": int(counts.get("module_count") or 0),
                "term_count": int(counts.get("term_count") or 0),
                "term_hit_count": int(counts.get("term_hit_count") or 0),
                "exact_asset_path_or_stem_hit_count": int(
                    counts.get("exact_asset_path_or_stem_hit_count") or 0
                ),
                "code_ref_count": int(counts.get("code_ref_count") or 0),
                "candidate_function_count": int(counts.get("candidate_function_count") or 0),
                "payload_owner_candidate_count": int(
                    counts.get("payload_owner_candidate_count") or 0
                ),
                "route_candidate_count": int(counts.get("route_candidate_count") or 0),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "textasset_payload_owner_proven": conclusion.get(
                    "textasset_payload_owner_proven"
                ),
                "textasset_payload_owner_candidate_found": conclusion.get(
                    "textasset_payload_owner_candidate_found"
                ),
                "exact_asset_path_or_stem_native_hit_found": conclusion.get(
                    "exact_asset_path_or_stem_native_hit_found"
                ),
                "native_code_refs_to_textasset_terms_found": conclusion.get(
                    "native_code_refs_to_textasset_terms_found"
                ),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _serialized_textasset_layout_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_path_resolution: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    resolution_conclusion = (
        resolved_by_path_resolution.get("route_conclusion")
        if isinstance(resolved_by_path_resolution, dict)
        else {}
    ) or {}
    if resolution_conclusion.get("path_id_to_exact_object_offset_resolved") is True:
        return []
    source_id = str(evidence.get("source_id") or "serialized-textasset-layout")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "serialized TextAsset layout evidence only"),
        str(conclusion.get("strongest_negative_signal") or "path_id to exact object offset is not resolved"),
        str(conclusion.get("search_policy") or "parse SerializedFile tables before decoder promotion"),
        "Serialized TextAsset layout evidence is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="serialized-textasset-layout-pathid-object-table",
            queue_type="serialized_textasset_layout_probe_target",
            priority=105,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="SerializedFile TextAsset object/preload/container table resolution",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "parse the SerializedFile object table and preload table",
                "resolve each AssetBundle path_id to one exact TextAsset object offset",
            ],
            counts={
                "relevant_record_count": int(counts.get("relevant_record_count") or 0),
                "match_count": int(counts.get("match_count") or 0),
                "valid_layout_count": int(counts.get("valid_layout_count") or 0),
                "unique_object_offset_count": int(counts.get("unique_object_offset_count") or 0),
                "unique_payload_hash_count": int(counts.get("unique_payload_hash_count") or 0),
                "duplicate_object_offset_group_count": int(
                    counts.get("duplicate_object_offset_group_count") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "serialized_textasset_object_layout_confirmed": conclusion.get(
                    "serialized_textasset_object_layout_confirmed"
                ),
                "static_payload_offsets_and_lengths_confirmed": conclusion.get(
                    "static_payload_offsets_and_lengths_confirmed"
                ),
                "path_id_to_exact_object_offset_resolved": conclusion.get(
                    "path_id_to_exact_object_offset_resolved"
                ),
                "native_payload_buffer_owner_proven": conclusion.get(
                    "native_payload_buffer_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _serialized_textasset_resolution_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_native_anchor_scan: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    anchor_conclusion = (
        resolved_by_native_anchor_scan.get("route_conclusion")
        if isinstance(resolved_by_native_anchor_scan, dict)
        else {}
    ) or {}
    if anchor_conclusion.get("native_exact_strong_anchor_found") is False:
        return []
    source_id = str(evidence.get("source_id") or "serialized-textasset-resolution")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "path_id/object_offset resolution evidence only"),
        str(conclusion.get("strongest_negative_signal") or "payload decoder is not recovered"),
        str(conclusion.get("search_policy") or "use resolved object offsets for decoder recovery"),
        "Serialized TextAsset path_id/object_offset resolution is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="serialized-textasset-path-resolution-decoder-anchor",
            queue_type="serialized_textasset_path_resolution_target",
            priority=106,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="Resolved LuaScripts path_id/object_offset decoder anchors",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "use resolved object offsets and payload offsets as decoder validation anchors",
                "recover native TextAsset script-buffer ownership",
                "recover LuaScripts payload decoder before staging facts",
            ],
            counts={
                "relevant_record_count": int(counts.get("relevant_record_count") or 0),
                "resolved_record_count": int(counts.get("resolved_record_count") or 0),
                "unresolved_record_count": int(counts.get("unresolved_record_count") or 0),
                "ambiguous_record_count": int(counts.get("ambiguous_record_count") or 0),
                "unique_path_id_count": int(counts.get("unique_path_id_count") or 0),
                "unique_resolved_object_offset_count": int(
                    counts.get("unique_resolved_object_offset_count") or 0
                ),
                "unique_resolved_payload_sha1_count": int(
                    counts.get("unique_resolved_payload_sha1_count") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "path_id_to_exact_object_offset_resolved": conclusion.get(
                    "path_id_to_exact_object_offset_resolved"
                ),
                "serialized_textasset_object_layout_confirmed": conclusion.get(
                    "serialized_textasset_object_layout_confirmed"
                ),
                "container_path_records_verified": conclusion.get(
                    "container_path_records_verified"
                ),
                "catalog_payload_sha1_resolution_confirmed": conclusion.get(
                    "catalog_payload_sha1_resolution_confirmed"
                ),
                "metadata_object_table_independently_decrypted": conclusion.get(
                    "metadata_object_table_independently_decrypted"
                ),
                "native_payload_buffer_owner_proven": conclusion.get(
                    "native_payload_buffer_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _resolved_payload_native_anchor_scan_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
    resolved_by_boundary_ledger: dict[str, Any] | None = None,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    ledger_conclusion = (
        resolved_by_boundary_ledger.get("route_conclusion")
        if isinstance(resolved_by_boundary_ledger, dict)
        else {}
    ) or {}
    if ledger_conclusion.get("exact_native_anchor_route_closed") is True:
        return []
    source_id = str(evidence.get("source_id") or "resolved-payload-native-anchor-scan")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "resolved native anchor scan evidence only"),
        str(conclusion.get("strongest_negative_signal") or "native payload-buffer owner is not proven"),
        str(conclusion.get("search_policy") or "continue boundary-focused owner analysis"),
        "Resolved native anchor scan is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="resolved-payload-native-anchor-boundary-owner-trace",
            queue_type="resolved_payload_native_anchor_scan_target",
            priority=107,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="Resolved payload anchors for native owner boundary trace",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=_str_list(evidence.get("next_static_targets"))
            or [
                "use resolved payload offsets for boundary-focused disassembly",
                "recover native TextAsset script-buffer ownership",
                "recover LuaScripts payload decoder before staging facts",
            ],
            counts={
                "anchor_count": int(counts.get("anchor_count") or 0),
                "strong_anchor_count": int(counts.get("strong_anchor_count") or 0),
                "weak_anchor_count": int(counts.get("weak_anchor_count") or 0),
                "present_module_count": int(counts.get("present_module_count") or 0),
                "native_strong_anchor_hit_count_capped": int(
                    counts.get("native_strong_anchor_hit_count_capped") or 0
                ),
                "native_weak_anchor_hit_count_capped": int(
                    counts.get("native_weak_anchor_hit_count_capped") or 0
                ),
                "native_strong_anchor_cooccurrence_count": int(
                    counts.get("native_strong_anchor_cooccurrence_count") or 0
                ),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "resolved_path_id_object_offset_anchor_available": conclusion.get(
                    "resolved_path_id_object_offset_anchor_available"
                ),
                "cab_control_anchors_verified": conclusion.get("cab_control_anchors_verified"),
                "native_exact_strong_anchor_found": conclusion.get(
                    "native_exact_strong_anchor_found"
                ),
                "native_strong_anchor_cooccurrence_found": conclusion.get(
                    "native_strong_anchor_cooccurrence_found"
                ),
                "native_payload_buffer_owner_proven": conclusion.get(
                    "native_payload_buffer_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "safe_for_publish": conclusion.get("safe_for_publish"),
            },
        )
    ]


def _textasset_xlua_boundary_ledger_items(
    evidence: dict[str, Any],
    *,
    source_artifact: str,
) -> list[ClientImportQueueItem]:
    counts = _int_dict(evidence.get("counts") or {})
    conclusion = evidence.get("route_conclusion") or {}
    if not counts and not conclusion:
        return []
    source_id = str(evidence.get("source_id") or "textasset-xlua-boundary-ledger")
    evidence_refs = [str(item) for item in evidence.get("evidence_refs") or [] if item]
    records = [item for item in evidence.get("route_records") or [] if isinstance(item, dict)]
    next_actions = _str_list(evidence.get("next_static_targets")) or [
        "recover protected metadata/method ownership for InitLuaEnv and TextAsset script-buffer APIs",
        "trace boundary-focused control-flow only after payload-buffer owner evidence appears",
        "use resolved payload offsets and lengths as validation anchors, not broad native search constants",
    ]
    blockers = [
        str(conclusion.get("strongest_current_signal") or "TextAsset/xLua boundary ledger only"),
        str(conclusion.get("strongest_negative_signal") or "native payload-buffer owner is not proven"),
        str(conclusion.get("search_policy") or "continue with method ownership or proven buffer-flow evidence"),
        "TextAsset/xLua boundary ledger is not publishable game knowledge",
    ]
    return [
        ClientImportQueueItem(
            queue_id="textasset-xlua-boundary-ledger-method-owner-route",
            queue_type="textasset_xlua_boundary_ledger_target",
            priority=108,
            readiness="static_trace_target",
            domain="lua_scripts",
            topic="TextAsset/xLua boundary route ledger and method-owner recovery target",
            source_artifact=source_artifact,
            evidence_refs=evidence_refs[:24],
            blockers=_unique_strs(blockers),
            next_actions=next_actions,
            counts={
                "route_record_count": int(counts.get("route_record_count") or 0),
                "closed_negative_route_count": int(
                    counts.get("closed_negative_route_count") or 0
                ),
                "blocked_route_count": int(counts.get("blocked_route_count") or 0),
                "next_viable_route_count": int(counts.get("next_viable_route_count") or 0),
                "proven_payload_owner_route_count": int(
                    counts.get("proven_payload_owner_route_count") or 0
                ),
                "exact_anchor_native_hit_count": int(
                    counts.get("exact_anchor_native_hit_count") or 0
                ),
                "record_count": len(records),
                "blocker_count": len(_unique_strs(blockers)),
            },
            metadata={
                "source_id": source_id,
                "round": evidence.get("round"),
                "native_payload_buffer_owner_proven": conclusion.get(
                    "native_payload_buffer_owner_proven"
                ),
                "lua_payload_decoder_recovered": conclusion.get(
                    "lua_payload_decoder_recovered"
                ),
                "gameassembly_static_xlua_import_route_closed": conclusion.get(
                    "gameassembly_static_xlua_import_route_closed"
                ),
                "resolver_direct_caller_route_closed": conclusion.get(
                    "resolver_direct_caller_route_closed"
                ),
                "exact_native_anchor_route_closed": conclusion.get(
                    "exact_native_anchor_route_closed"
                ),
                "protected_metadata_method_ownership_recovered": conclusion.get(
                    "protected_metadata_method_ownership_recovered"
                ),
                "next_viable_route": conclusion.get("next_viable_route"),
                "route_status_counts": _int_dict(evidence.get("route_status_counts") or {}),
            },
        )
    ]
