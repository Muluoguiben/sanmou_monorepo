from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.ingestion.client_import_queue import build_client_import_queue


class ClientImportQueueTests(unittest.TestCase):
    def _write_fixture_artifacts(self, root: Path) -> None:
        raw_dir = root / "ingestion" / "raw" / "client_packages"
        staging_dir = root / "ingestion" / "staging" / "client_decoded"
        raw_dir.mkdir(parents=True)
        staging_dir.mkdir(parents=True)

        (raw_dir / "nslg-client-evidence-bundle-round137.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "nslg.client_evidence_bundle.v1",
                    "source_id": "fixture-bundle",
                    "client_version": {"app_version": "1.29.0"},
                    "import_readiness": {
                        "safe_for_publish": False,
                        "normalized_staging_entries": 1,
                        "decoder_target_artifacts": [
                            "luascripts_textasset_catalog",
                            "luascripts_crypto_evidence",
                            "luascripts_payload_cipher_profile",
                            "luascripts_payload_variant_corpus",
                            "textasset_payload_owner_trace",
                            "serialized_textasset_layout_probe",
                            "serialized_textasset_path_resolution",
                            "resolved_payload_native_anchor_scan",
                            "textasset_xlua_boundary_ledger",
                            "ns_bundle_format_index",
                            "nep2_luascripts_static_evidence",
                            "gameassembly_route_trace",
                            "nep2_init_luascripts_bridge",
                            "native_loadbuffer_boundary_trace",
                            "runtime_init_metadata_route",
                            "runtime_init_registry_probe",
                            "gameassembly_codegen_module_probe",
                            "gameassembly_registration_anchor_probe",
                            "gameassembly_registration_layout_probe",
                            "gameassembly_registration_pair_context_probe",
                            "gameassembly_initializer_dispatch_trace",
                            "gameassembly_function_pointer_table_probe",
                            "gameassembly_metadata_registration_candidate_taxonomy",
                            "gameassembly_global_metadata_owner_probe",
                            "nep2_vector_candidate_provenance",
                            "global_metadata_transform_probe",
                            "global_metadata_loader_mutation_scan",
                            "gameassembly_resolver_candidate_trace",
                            "gameassembly_resolver_caller_payload_trace",
                        ],
                    },
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-client-resource-surface-gap-scan-round133.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "nslg.client_resource_surface_gap_scan.v1",
                    "source_id": "client-resource-surface-gap-scan-round133",
                    "source_url": "local-nslg-client-install-resource-surface",
                    "source_site": "nslg_client_install_static_inventory",
                    "round": 190,
                    "counts": {
                        "total_files_seen": 677,
                        "safe_file_count": 556,
                        "aggregate_only_file_count": 76,
                        "sensitive_or_runtime_file_count": 45,
                        "ns_bundle_count": 369,
                        "ns_total_bytes": 7197259176,
                        "safe_magic_sample_count": 2,
                        "publishable_knowledge_entries": 0,
                    },
                    "ns_bundle_groups": [
                        {"group": "luascripts.ns", "file_count": 1},
                        {"group": "building.ns", "file_count": 1},
                        {"group": "mapres.ns", "file_count": 1},
                    ],
                    "route_conclusion": {
                        "resource_surface_gap_identified": True,
                        "resource_cache_bundle_root_found": True,
                        "luascripts_ns_found": True,
                        "map_resource_ns_found": True,
                        "decoded_game_knowledge_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "resource cache contains .ns bundles",
                        "strongest_negative_signal": "no bundle decode yet",
                        "search_policy": "prioritize .ns bundle index",
                    },
                    "evidence_refs": ["NSLG_CLIENT_RESOURCE_SURFACE:round190:summary"],
                    "next_static_targets": ["build sanitized .ns bundle index"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-ns-bundle-format-index-round136.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "nslg.ns_bundle_format_index.v1",
                    "source_id": "ns-bundle-format-index-round136",
                    "source_url": "local-nslg-client-ns-bundle-format-index",
                    "source_site": "nslg_client_ns_bundle_static_format_index",
                    "round": 191,
                    "counts": {
                        "bundle_count": 369,
                        "unityfs_parse_ok_count": 369,
                        "block_info_parse_ok_count": 369,
                        "first_block_decompress_ok_count": 369,
                        "serialized_header_parse_ok_count": 369,
                        "protected_serialized_metadata_count": 369,
                        "cab_only_bundle_count": 63,
                        "cab_plus_ress_bundle_count": 306,
                        "publishable_knowledge_entries": 0,
                    },
                    "format_groups": [{"asset_group": "luascripts.ns", "bundle_count": 1}],
                    "cab_block2_groups": [{"metadata_block2_hex": "c5", "bundle_count": 32}],
                    "priority_records": [
                        {
                            "rel_path": "luascripts.ns",
                            "asset_group": "luascripts.ns",
                            "priority_rank": 1,
                            "protected_metadata_likely": True,
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:bundle:luascripts",
                        },
                        {
                            "rel_path": "building.ns",
                            "asset_group": "building.ns",
                            "priority_rank": 2,
                            "protected_metadata_likely": True,
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:bundle:building",
                        },
                    ],
                    "route_conclusion": {
                        "ns_bundle_index_built": True,
                        "unityfs_envelope_parseable": True,
                        "block_info_index_parseable": True,
                        "first_block_decompression_supported": True,
                        "serialized_header_parseable": True,
                        "protected_serialized_metadata_present": True,
                        "all_indexed_bundles_look_protected": True,
                        "decoded_game_knowledge_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "parseable UnityFS envelopes",
                        "strongest_negative_signal": "CAB metadata remains protected",
                        "search_policy": "target protected metadata transform",
                    },
                    "evidence_refs": ["NSLG_NS_BUNDLE_FORMAT_INDEX:round191:summary"],
                    "next_static_targets": ["recover protected metadata transform"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (staging_dir / "nslg-hero-readable-export-round29-normalized.yaml").write_text(
            yaml.safe_dump(
                [
                    {
                        "metadata": {
                            "source_site": "nslg_client_decode",
                            "source_captured_at": "2026-05-16T00:00:00Z",
                            "review_status": "normalized",
                        },
                        "entry": {
                            "id": "client-decoded-hero-1000",
                            "domain": "hero",
                            "entry_kind": "hero_profile",
                            "topic": "曹操",
                            "aliases": ["caocao"],
                            "source_ref": "NSLG_CLIENT_DECODED:round29:heroID=1000",
                            "confidence": 0.72,
                            "related_topics": ["乱世奸雄", "20890"],
                            "structured_data": {
                                "notes": [
                                    "client_hero_id=1000",
                                    "decoded_skill_slots=skillId=100001,name=乱世奸雄; skillId=20890",
                                ]
                            },
                        },
                    }
                ],
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (staging_dir / "nslg-hero-readable-export-round29-audit.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "hero-readable-export-round29",
                    "hero_coverage": {
                        "unmapped_heroes": [],
                        "low_confidence_mappings": [],
                    },
                    "skill_coverage": {
                        "unmapped_skill_ids": [20890],
                        "low_confidence_mappings": [],
                    },
                    "next_review_actions": ["review decoded skill ids"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-luascripts-textassets-round31-catalog.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "luascripts-textasset-round31",
                    "high_value_stems": ["heros"],
                    "records": [
                        {
                            "evidence_ref": "NSLG_LUASCRIPT_TEXTASSET:round31:heros:0x1",
                            "asset_path": "Assets/Bundles/LuaScripts/Data/Scenario1/heros.bytes",
                            "stem": "heros",
                            "scenario": "Scenario1",
                            "kb_domains": ["hero"],
                            "script_len": 100,
                            "sha1": "aaa",
                            "extraction_status": "obfuscated_binary_pending_decoder",
                            "extracted_artifact": "threads/artifacts/heros.bytes.bin",
                        }
                    ],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-luascripts-crypto-evidence-round32.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "luascripts-crypto-round32",
                    "binary_string_hits": [{"binary_name": "GameAssembly.dll"}],
                    "payload_block_samples": [{"file_name": "heros.bytes.bin"}],
                    "payload_status_counts": {"high_entropy_16byte_aligned": 1},
                    "next_decoder_targets": ["GameAssembly xluaL_loadbuffer / TextAsset::get_bytes call path"],
                    "limitations": ["static evidence only"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-luascripts-payload-cipher-profile-round49.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "luascripts-payload-cipher-profile-round49",
                    "round": 162,
                    "payload_profile_count": 1,
                    "payload_profiles": [
                        {
                            "file_name": "heros.bytes.bin",
                            "stem": "heros",
                            "size_bytes": 23232,
                            "status": "high_entropy_16byte_aligned",
                        }
                    ],
                    "cross_file_block_profile": {
                        "cross_file_shared_16byte_block_count": 0,
                    },
                    "simple_transform_summary": {
                        "payload_count": 1,
                        "direct_plaintext_term_file_count": 0,
                    },
                    "xor_crib_probe_summary": {
                        "single_byte_xor_plaintext_like_count": 0,
                        "crib_xor_plaintext_like_count": 0,
                    },
                    "route_conclusion": {
                        "lua_payload_decoder_recovered": False,
                        "simple_compression_ruled_out": True,
                        "single_byte_or_crib_xor_ruled_out": True,
                        "ecb_like_shared_block_signal": False,
                        "strongest_current_signal": "payloads are high entropy",
                        "strongest_negative_signal": "payload decoder is not recovered",
                        "search_policy": "locate native buffer owner",
                    },
                    "evidence_refs": [
                        "NSLG_LUASCRIPT_CIPHER_PROFILE:round49:payload:heros.bytes.bin"
                    ],
                    "next_decoder_targets": ["locate native buffer owner"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-luascripts-payload-variant-corpus-round79.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "luascripts-payload-variant-corpus-round79",
                    "round": 172,
                    "corpus_summary": {
                        "relevant_record_count": 104,
                        "payload_variant_count": 932,
                        "stem_count": 16,
                        "scenario_count": 23,
                        "unique_ciphertext_hash_count": 52,
                        "duplicate_ciphertext_hash_group_count": 40,
                    },
                    "stem_summaries": [
                        {"stem": "heros", "variant_count": 1},
                        {"stem": "skills", "variant_count": 1},
                    ],
                    "block_sharing_summary": {
                        "cross_cipher_shared_16byte_block_count": 55,
                    },
                    "offset_skip_probe_summary": {
                        "decompression_success_count": 0,
                        "plaintext_hit_count": 0,
                        "high_printable_candidate_count": 0,
                    },
                    "evidence_refs": [
                        "NSLG_LUASCRIPT_VARIANT_CORPUS:round79:stem:heros"
                    ],
                    "route_conclusion": {
                        "lua_payload_decoder_recovered": False,
                        "duplicate_ciphertext_present": True,
                        "cross_cipher_shared_16byte_block_signal": True,
                        "simple_offset_skip_route_ruled_out": True,
                        "safe_for_publish": False,
                        "strongest_current_signal": "expanded corpus",
                        "strongest_negative_signal": "no plaintext layout",
                        "search_policy": "continue with native buffer owner tracing",
                    },
                    "next_decoder_targets": ["locate native buffer owner"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-textasset-payload-owner-trace-round82.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "textasset-payload-owner-trace-round82",
                    "round": 173,
                    "counts": {
                        "module_count": 4,
                        "term_count": 315,
                        "term_hit_count": 706,
                        "exact_asset_path_or_stem_hit_count": 0,
                        "code_ref_count": 0,
                        "candidate_function_count": 0,
                        "payload_owner_candidate_count": 0,
                        "route_candidate_count": 0,
                    },
                    "route_conclusion": {
                        "textasset_payload_owner_proven": False,
                        "textasset_payload_owner_candidate_found": False,
                        "exact_asset_path_or_stem_native_hit_found": False,
                        "native_code_refs_to_textasset_terms_found": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_positive_signal": "native strings only",
                        "strongest_negative_signal": "payload owner is not proven",
                        "search_policy": "recover payload-buffer provenance",
                    },
                    "evidence_refs": [
                        "NSLG_TEXTASSET_PAYLOAD_OWNER:round82:summary"
                    ],
                    "next_static_targets": ["recover SerializedFile object layout"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-serialized-textasset-layout-round85.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "serialized-textasset-layout-round85",
                    "round": 174,
                    "counts": {
                        "relevant_record_count": 104,
                        "match_count": 932,
                        "valid_layout_count": 932,
                        "unique_object_offset_count": 52,
                        "unique_payload_hash_count": 52,
                        "duplicate_object_offset_group_count": 40,
                    },
                    "route_conclusion": {
                        "serialized_textasset_object_layout_confirmed": True,
                        "static_payload_offsets_and_lengths_confirmed": True,
                        "path_id_to_exact_object_offset_resolved": False,
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "layout confirmed",
                        "strongest_negative_signal": "path_id unresolved",
                        "search_policy": "parse SerializedFile tables",
                    },
                    "evidence_refs": [
                        "NSLG_SERIALIZED_TEXTASSET_LAYOUT:round85:stem:heros"
                    ],
                    "next_static_targets": ["parse SerializedFile object table"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-serialized-textasset-path-resolution-round88.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "serialized-textasset-path-resolution-round88",
                    "round": 175,
                    "counts": {
                        "relevant_record_count": 104,
                        "container_record_valid_count": 104,
                        "resolved_record_count": 104,
                        "unresolved_record_count": 0,
                        "ambiguous_record_count": 0,
                        "unique_path_id_count": 104,
                        "unique_resolved_object_offset_count": 16,
                        "unique_resolved_payload_sha1_count": 16,
                    },
                    "route_conclusion": {
                        "path_id_to_exact_object_offset_resolved": True,
                        "serialized_textasset_object_layout_confirmed": True,
                        "container_path_records_verified": True,
                        "catalog_payload_sha1_resolution_confirmed": True,
                        "metadata_object_table_independently_decrypted": False,
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "path_id resolved",
                        "strongest_negative_signal": "decoder not recovered",
                        "search_policy": "use resolved offsets",
                    },
                    "evidence_refs": [
                        "NSLG_SERIALIZED_TEXTASSET_PATH_RESOLUTION:round88:0x1:0x7b"
                    ],
                    "next_static_targets": ["recover decoder using resolved offsets"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-resolved-payload-native-anchor-scan-round91.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "resolved-payload-native-anchor-scan-round91",
                    "round": 176,
                    "counts": {
                        "anchor_count": 368,
                        "strong_anchor_count": 272,
                        "weak_anchor_count": 96,
                        "present_module_count": 4,
                        "native_strong_anchor_hit_count_capped": 0,
                        "native_weak_anchor_hit_count_capped": 990,
                        "native_strong_anchor_cooccurrence_count": 0,
                    },
                    "route_conclusion": {
                        "resolved_path_id_object_offset_anchor_available": True,
                        "cab_control_anchors_verified": True,
                        "native_exact_strong_anchor_found": False,
                        "native_strong_anchor_cooccurrence_found": False,
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "CAB anchors verified",
                        "strongest_negative_signal": "no native strong anchors",
                        "search_policy": "continue boundary-focused owner analysis",
                    },
                    "evidence_refs": [
                        "NSLG_RESOLVED_PAYLOAD_NATIVE_ANCHOR:round91:module:GameAssembly.dll"
                    ],
                    "next_static_targets": ["boundary-focused disassembly"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-textasset-xlua-boundary-ledger-round94.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "textasset-xlua-boundary-ledger-round94",
                    "round": 177,
                    "counts": {
                        "route_record_count": 6,
                        "closed_negative_route_count": 4,
                        "blocked_route_count": 1,
                        "next_viable_route_count": 1,
                        "proven_payload_owner_route_count": 0,
                        "exact_anchor_native_hit_count": 0,
                    },
                    "route_status_counts": {
                        "closed_negative": 4,
                        "blocked_pending_metadata": 1,
                        "next_viable_target": 1,
                    },
                    "route_records": [
                        {
                            "route_id": "resolved_payload_native_exact_anchor_scan",
                            "status": "closed_negative",
                        },
                        {
                            "route_id": "protected_metadata_method_ownership_or_boundary_control_flow",
                            "status": "next_viable_target",
                        },
                    ],
                    "route_conclusion": {
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "gameassembly_static_xlua_import_route_closed": True,
                        "resolver_direct_caller_route_closed": True,
                        "exact_native_anchor_route_closed": True,
                        "protected_metadata_method_ownership_recovered": False,
                        "next_viable_route": "protected_metadata_method_ownership_or_boundary_control_flow",
                        "safe_for_publish": False,
                        "strongest_current_signal": "closed routes constrain next search",
                        "strongest_negative_signal": "payload owner is not proven",
                        "search_policy": "continue method ownership recovery",
                    },
                    "evidence_refs": [
                        "NSLG_TEXTASSET_XLUA_BOUNDARY_LEDGER:round177:summary"
                    ],
                    "next_static_targets": ["recover protected metadata method ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-luascripts-evidence-round34.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-luascripts-round34",
                    "binary_name": "NEP2.dll",
                    "sha256": "bbb",
                    "init_luascripts_occurrences": [{"rva": "0x88135e"}],
                    "pointer_refs_to_init_luascripts": 0,
                    "candidate_string_count": 4,
                    "selected_candidate_strings": ["InitLuaScriptsScan", "luaL_loadbuffer"],
                    "xref_count": 1,
                    "xrefs": [{"string": "O3P1P1_1P2P3WAES", "ref_rva": "0x3f4a"}],
                    "string_chunk_registrations": [{"chunk_text": "WAES"}],
                    "next_static_targets": ["trace CGameProtector::InitLuaScriptsScan call sites"],
                    "limitations": ["decryptor body not proven"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-route-trace-round43.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-route-trace-round43",
                    "binary_name": "GameAssembly.dll",
                    "artifact_count": 2,
                    "route_signal_record_count": 0,
                    "total_target_strings": 12,
                    "total_code_refs": 1,
                    "total_function_refs": 1,
                    "route_conclusion": {
                        "textasset_loadbuffer_bridge_proven": False,
                        "strongest_current_signal": "TextAsset and xlua strings are present but no bridge was proven",
                        "search_policy": "keep as decoder routing evidence",
                    },
                    "records": [
                        {
                            "evidence_ref": "NSLG_GAMEASSEMBLY_TRACE:round43:round=160:kind=textasset_loadbuffer_correlation",
                            "round": 160,
                            "artifact_kind": "textasset_loadbuffer_correlation",
                            "route_signal_function_count": 0,
                        }
                    ],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-init-bridge-round46.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-init-bridge-round46",
                    "binary_name": "NEP2.dll",
                    "round": 161,
                    "counts": {
                        "bridge_record_count": 4,
                        "candidate_function_count": 13,
                        "candidate_with_file_import_count": 1,
                    },
                    "bridge_records": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_BRIDGE:round46:bridge:0x881320",
                            "rva": "0x881320",
                        }
                    ],
                    "candidate_functions": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_BRIDGE:round46:candidate:0x4040",
                            "function_rva": "0x4040",
                        }
                    ],
                    "evidence_refs": [
                        "NSLG_NEP2_INIT_BRIDGE:round46:bridge:0x881320",
                        "NSLG_NEP2_INIT_BRIDGE:round46:candidate:0x4040",
                    ],
                    "route_conclusion": {
                        "bridge_metadata_confirmed": True,
                        "decryptor_body_proven": False,
                        "file_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "strongest_current_signal": "InitLuaScriptsScan metadata bridge is real",
                        "strongest_negative_signal": "payload decoder is not proven",
                        "search_policy": "continue with provenance-backed decoder targets only",
                    },
                    "next_static_targets": ["trace InitLuaScriptsScan"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-native-loadbuffer-boundary-round52.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "native-loadbuffer-boundary-round52",
                    "round": 163,
                    "counts": {
                        "module_count": 4,
                        "loadbuffer_export_signal_count": 3,
                        "boundary_import_call_count": 224,
                    },
                    "module_records": [
                        {
                            "evidence_ref": "NSLG_NATIVE_BOUNDARY:round52:module:GameAssembly.dll",
                            "module": "GameAssembly.dll",
                        },
                        {
                            "evidence_ref": "NSLG_NATIVE_BOUNDARY:round52:module:xlua.dll",
                            "module": "xlua.dll",
                        },
                    ],
                    "evidence_refs": [
                        "NSLG_NATIVE_BOUNDARY:round52:module:GameAssembly.dll",
                        "NSLG_NATIVE_BOUNDARY:round52:module:xlua.dll",
                    ],
                    "route_conclusion": {
                        "native_loadbuffer_export_present": True,
                        "gameassembly_static_xlua_import_present": False,
                        "gameassembly_to_xlua_static_bridge_proven": False,
                        "textasset_to_loadbuffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "strongest_current_signal": "xLua loadbuffer exports are present",
                        "strongest_negative_signal": "TextAsset owner is not proven",
                        "search_policy": "continue with provenance-backed tracing",
                    },
                    "next_static_targets": ["trace RuntimeInitializeOnLoad metadata"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-runtime-init-metadata-route-round55.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "runtime-init-metadata-route-round55",
                    "round": 164,
                    "counts": {
                        "runtime_initialize_anchor_count": 1,
                        "global_metadata_file_size": 21182776,
                        "global_metadata_plaintext_needle_hit_count": 0,
                        "native_boundary_loadbuffer_export_signal_count": 3,
                    },
                    "evidence_refs": [
                        "NSLG_RUNTIME_INIT_ROUTE:round55:anchor:initluaenv"
                    ],
                    "route_conclusion": {
                        "runtime_init_anchor_known": True,
                        "runtime_initialize_onloads_file_present": False,
                        "global_metadata_protected_wrapper_confirmed": True,
                        "protected_global_metadata_decoded": False,
                        "init_lua_env_method_address_recovered": False,
                        "textasset_to_loadbuffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "strongest_current_signal": "InitLuaEnv is known",
                        "strongest_blocker": "metadata is protected",
                        "search_policy": "recover method ownership",
                    },
                    "next_static_targets": ["recover protected metadata"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-runtime-init-registry-probe-round97.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "runtime-init-registry-probe-round97",
                    "round": 178,
                    "counts": {
                        "runtime_initialize_entry_count": 12,
                        "runtime_initialize_init_lua_env_entry_count": 1,
                        "registry_address_or_token_field_count": 0,
                        "modules_with_init_lua_env_hits": 0,
                        "modules_with_runtime_init_json_hits": 1,
                        "unityplayer_runtime_json_code_ref_count": 1,
                    },
                    "evidence_refs": ["NSLG_RUNTIME_INIT_REGISTRY:round97:summary"],
                    "route_conclusion": {
                        "runtime_initialize_registry_present": True,
                        "init_lua_env_declared_in_registry": True,
                        "registry_contains_native_method_address_or_token": False,
                        "unityplayer_runtime_json_loader_xrefs_found": True,
                        "init_lua_env_native_method_address_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "textasset_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "registry declares InitLuaEnv",
                        "strongest_negative_signal": "registry has no native address",
                        "search_policy": "continue protected metadata ownership",
                    },
                    "next_static_targets": ["recover protected metadata ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-codegen-module-probe-round100.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-codegen-module-probe-round100",
                    "round": 179,
                    "counts": {
                        "codegen_module_candidate_count": 95,
                        "codegen_module_run_count": 4,
                        "largest_codegen_module_run_count": 49,
                        "assembly_csharp_module_count": 2,
                        "assembly_csharp_method_pointer_count": 30078,
                        "assembly_csharp_method_pointer_text_count": 29351,
                        "assembly_csharp_method_pointer_null_count": 727,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "assembly_csharp_modules": [
                        {
                            "module_name": "Assembly-CSharp.dll",
                            "method_pointer_count": 30078,
                            "method_pointer_table_rva": "0x50b9840",
                        }
                    ],
                    "codegen_module_runs": [
                        {
                            "start_ref_rva": "0x50a2840",
                            "module_count": 49,
                            "contains_assembly_csharp": True,
                        }
                    ],
                    "evidence_refs": ["NSLG_CODEGEN_MODULE:round100:summary"],
                    "route_conclusion": {
                        "assembly_csharp_codegen_module_found": True,
                        "assembly_csharp_method_pointer_table_found": True,
                        "codegen_module_array_found": True,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "Assembly-CSharp CodeGenModule method pointer table found",
                        "strongest_negative_signal": "protected metadata still blocks method names",
                        "search_policy": "recover metadata registration ownership before naming method pointers",
                    },
                    "next_static_targets": ["recover metadata registration ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-registration-anchor-probe-round103.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-registration-anchor-probe-round103",
                    "round": 180,
                    "counts": {
                        "codegen_modules_field_candidate_count": 1,
                        "declared_codegen_module_count": 98,
                        "parsed_codegen_module_count": 98,
                        "nonzero_method_module_count": 96,
                        "assembly_csharp_index": 5,
                        "assembly_csharp_method_pointer_count": 30078,
                        "registration_anchor_code_ref_count": 0,
                        "metadata_registration_candidate_count": 0,
                        "method_index_to_pointer_map_recovered": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "module_array_summary": {
                        "assembly_csharp_index": 5,
                        "assembly_csharp_method_pointer_count": 30078,
                        "assembly_csharp_method_pointer_table_rva": "0x50b9840",
                    },
                    "evidence_refs": [
                        "NSLG_REGISTRATION_ANCHOR:round180:codegen-modules-field"
                    ],
                    "route_conclusion": {
                        "codegen_registration_anchor_found": True,
                        "full_codegen_module_array_recovered": True,
                        "assembly_csharp_module_index_found": True,
                        "codegen_registration_callsite_recovered": False,
                        "metadata_registration_candidate_recovered": False,
                        "method_index_to_pointer_map_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "CodeGenModules field found",
                        "strongest_negative_signal": "MetadataRegistration pairing missing",
                        "search_policy": "recover registration pairing",
                    },
                    "limitations": ["registration-side static evidence only"],
                    "next_static_targets": ["recover registration pairing"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-registration-layout-probe-round106.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-registration-layout-probe-round106",
                    "round": 181,
                    "counts": {
                        "code_registration_start_candidate_count": 1,
                        "primary_code_registration_start_rva": 70461232,
                        "code_registration_count_pointer_pair_count": 6,
                        "code_registration_pointer_only_field_count": 9,
                        "codegen_modules_field_offset": 120,
                        "known_codegen_modules_count": 98,
                        "layout_field_row_count": 18,
                        "registration_code_ref_count": 0,
                        "registration_raw_va_ref_count": 7,
                        "metadata_registration_candidate_count": 5,
                        "metadata_registration_paired_by_callsite": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "primary_code_registration_layout": {
                        "candidate_start_rva": "0x4332730",
                        "candidate_end_rva": "0x43327b8",
                        "codegen_modules_field_offsets": {
                            "count_offset": "0x78",
                            "pointer_offset": "0x80",
                            "array_rva": "0x50a2840",
                        },
                    },
                    "registration_xref_summary": {
                        "available": True,
                        "code_ref_count": 0,
                        "raw_va_ref_count": 7,
                    },
                    "metadata_registration_candidate_scan": {
                        "candidate_count": 5,
                        "scan_policy": "weak/unpaired candidates only",
                    },
                    "evidence_refs": [
                        "NSLG_REGISTRATION_LAYOUT:round181:code-registration-start"
                    ],
                    "route_conclusion": {
                        "code_registration_layout_refined": True,
                        "round180_owner_inference_corrected": True,
                        "codegen_modules_field_offset_confirmed": True,
                        "registration_callsite_recovered": False,
                        "metadata_registration_candidate_recovered": True,
                        "metadata_registration_paired_by_callsite": False,
                        "method_index_to_pointer_map_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "CodeRegistration layout refined",
                        "strongest_negative_signal": "MetadataRegistration pairing missing",
                        "search_policy": "require callsite pair",
                    },
                    "limitations": ["registration-layout static evidence only"],
                    "next_static_targets": ["recover registration callsite"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-registration-pair-context-probe-round109.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-registration-pair-context-probe-round109",
                    "round": 182,
                    "counts": {
                        "registration_target_count": 10,
                        "metadata_target_count": 12,
                        "raw_registration_ref_count": 7,
                        "raw_code_registration_start_ref_count": 0,
                        "raw_metadata_candidate_ref_count": 25,
                        "registration_code_ref_count": 0,
                        "metadata_candidate_code_ref_count": 0,
                        "paired_neighborhood_count": 0,
                        "call_argument_pair_window_count": 0,
                        "metadata_ref_family_cluster_count": 17,
                        "registration_pair_recovered": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "evidence_refs": [
                        "NSLG_REGISTRATION_PAIR_CONTEXT:round182:pair-neighborhood-scan"
                    ],
                    "route_conclusion": {
                        "registration_pair_recovered": False,
                        "metadata_registration_paired_by_callsite": False,
                        "metadata_candidate_family_refs_found": True,
                        "direct_code_registration_start_ref_found": False,
                        "call_argument_pair_window_found": False,
                        "pair_neighborhood_found": False,
                        "method_index_to_pointer_map_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "metadata candidate family refs",
                        "strongest_negative_signal": "no direct pair context",
                        "search_policy": "pivot away from direct pair xrefs",
                    },
                    "limitations": ["pair-context static evidence only"],
                    "next_static_targets": ["recover metadata ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-initializer-dispatch-trace-round112.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-initializer-dispatch-trace-round112",
                    "round": 183,
                    "counts": {
                        "instruction_count": 16265170,
                        "function_row_count": 290472,
                        "registration_anchor_ref_function_count": 0,
                        "metadata_candidate_ref_function_count": 0,
                        "global_metadata_string_ref_function_count": 2,
                        "entry_to_registration_path_found": 0,
                        "entry_to_metadata_candidate_path_found": 0,
                        "entry_to_global_metadata_path_found": 0,
                        "nonexec_pointer_hit_count": 0,
                        "dispatcher_candidate_count": 24,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "evidence_refs": [
                        "NSLG_INITIALIZER_DISPATCH_TRACE:round183:bounded-callgraph-paths"
                    ],
                    "route_conclusion": {
                        "initializer_dispatcher_route_recovered": False,
                        "registration_ownership_recovered": False,
                        "metadata_registration_paired_by_dispatch_trace": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "safe_for_publish": False,
                        "summary": "bounded direct-call trace is negative",
                    },
                    "limitations": ["initializer-dispatch static evidence only"],
                    "next_static_targets": ["recover protected metadata ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-function-pointer-table-probe-round115.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-function-pointer-table-probe-round115",
                    "round": 184,
                    "counts": {
                        "function_pointer_hit_count": 342009,
                        "known_method_table_count": 96,
                        "known_code_registration_field_table_count": 6,
                        "known_codegen_method_table_hit_count": 133465,
                        "known_code_registration_field_hit_count": 172773,
                        "outside_known_table_hit_count": 35771,
                        "relevant_function_pointer_hit_count": 22,
                        "outside_known_table_relevant_hit_count": 0,
                        "global_metadata_function_pointer_hit_count": 0,
                        "dispatcher_pointer_hit_count": 22,
                        "dispatcher_pointer_hits_outside_known_tables": 0,
                        "initializer_candidate_table_count": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "route_conclusion": {
                        "function_pointer_tables_scanned": True,
                        "dispatcher_pointer_hits_classified_as_known_il2cpp_tables": True,
                        "global_metadata_function_pointer_hits_found": False,
                        "outside_known_table_relevant_pointer_hits_found": False,
                        "independent_initializer_table_candidate_found": False,
                        "initializer_table_route_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "safe_for_publish": False,
                        "interpretation": "dispatcher hits classify as known IL2CPP tables",
                    },
                    "limitations": ["function-pointer-table static evidence only"],
                    "next_static_targets": ["recover protected metadata ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (
            raw_dir
            / "nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml"
        ).write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-metadata-registration-candidate-taxonomy-round118",
                    "round": 185,
                    "counts": {
                        "metadata_candidate_window_count": 58879,
                        "exact_ref_candidate_count": 12,
                        "exact_ref_non_tiny_candidate_count": 0,
                        "exact_ref_max_count": 15,
                        "high_count_candidate_count": 182,
                        "strong_high_count_candidate_count": 169,
                        "referenced_high_count_candidate_count": 0,
                        "shifted_window_cluster_count": 6,
                        "metadata_ref_family_cluster_count": 17,
                        "metadata_registration_owner_recovered": 0,
                        "protected_metadata_method_ownership_recovered": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "route_conclusion": {
                        "metadata_candidate_taxonomy_completed": True,
                        "exact_ref_metadata_candidates_are_tiny_count_family": True,
                        "high_count_metadata_like_candidates_found": True,
                        "high_count_candidates_have_exact_refs": False,
                        "metadata_registration_owner_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "exact refs point to tiny-count families",
                        "strongest_negative_signal": "high-count windows are unreferenced",
                        "search_policy": "require decoded metadata or proven owner",
                    },
                    "limitations": ["metadata taxonomy static evidence only"],
                    "next_static_targets": ["recover protected metadata ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-global-metadata-transform-probe-round64.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "global-metadata-transform-probe-round64",
                    "round": 167,
                    "counts": {
                        "global_metadata_file_size": 21182776,
                        "protected_size_mod_16": 0,
                        "transform_candidate_count": 1314,
                        "needle_hit_candidate_count": 0,
                        "best_header_valid_pair_count": 0,
                    },
                    "evidence_refs": [
                        "NSLG_GLOBAL_METADATA_TRANSFORM:round64:transform-probe"
                    ],
                    "route_conclusion": {
                        "protected_wrapper_confirmed": True,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "safe_for_publish": False,
                        "verdict": ["bounded transform probe did not recover metadata"],
                    },
                    "next_static_targets": ["pivot to loader mutation point"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-global-metadata-loader-scan-round67.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "global-metadata-loader-mutation-scan-round67",
                    "round": 168,
                    "counts": {
                        "binary_count": 4,
                        "candidate_count": 554,
                        "full_loader_mutation_candidate_count": 0,
                        "file_16_candidate_count": 2,
                        "metadata_ref_candidate_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_GLOBAL_METADATA_LOADER:round67:summary"
                    ],
                    "route_conclusion": {
                        "full_loader_mutation_candidate_found": False,
                        "file_api_16byte_candidates_found": True,
                        "metadata_reference_candidates_found": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "textasset_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "Top file+16 route candidate is NEP2.dll 0xd410",
                        "strongest_negative_signal": "No full loader-mutation gate was found",
                        "search_policy": "Deep-slice top NEP2 file+16 candidates",
                    },
                    "next_static_targets": ["Deep-slice NEP2.dll 0xd410"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-global-metadata-loader-deep-slice-round70.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-global-metadata-loader-deep-slice-round70",
                    "round": 169,
                    "target_rvas": ["0xd410", "0xd870"],
                    "counts": {
                        "target_count": 2,
                        "closed_target_count": 2,
                        "read_or_mapping_target_count": 0,
                        "metadata_ref_target_count": 0,
                        "directory_walker_target_count": 1,
                        "file_status_helper_target_count": 1,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_METADATA_LOADER_DEEP_SLICE:round70:summary"
                    ],
                    "route_conclusion": {
                        "targets_closed_as_metadata_loader_candidates": True,
                        "global_metadata_loader_proven": False,
                        "file_buffer_owner_proven": False,
                        "metadata_wrapper_or_string_provenance_found": False,
                        "read_or_mapping_proven": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "filesystem helper signatures",
                        "strongest_negative_signal": "no ReadFile or metadata refs",
                        "search_policy": "pivot to read owners",
                    },
                    "next_static_targets": ["prioritize actual ReadFile owners"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-read-mapping-owner-scan-round73.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-read-mapping-owner-scan-round73",
                    "round": 170,
                    "counts": {
                        "read_mapping_owner_count": 2,
                        "readfile_owner_count": 0,
                        "mapview_owner_count": 0,
                        "create_file_mapping_owner_count": 0,
                        "get_file_size_owner_count": 2,
                        "metadata_provenance_owner_count": 0,
                        "luascripts_provenance_owner_count": 0,
                        "protected_payload_signal_owner_count": 0,
                        "provenance_linked_owner_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_READ_MAPPING_OWNER:round73:summary"
                    ],
                    "route_conclusion": {
                        "actual_read_mapping_owners_found": True,
                        "metadata_linked_read_mapping_owner_found": False,
                        "global_metadata_loader_proven": False,
                        "file_buffer_owner_proven": False,
                        "metadata_wrapper_or_string_provenance_found": False,
                        "luascripts_or_init_scan_provenance_found": False,
                        "protected_payload_signal_found": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "actual GetFileSize owners found",
                        "strongest_negative_signal": "no metadata/LuaScripts provenance",
                        "search_policy": "pivot to data-reference ownership",
                    },
                    "next_static_targets": ["pivot to NEP2 InitLuaScriptsScan data ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-init-data-owner-scan-round76.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-init-data-owner-scan-round76",
                    "round": 171,
                    "counts": {
                        "focus_target_count": 90,
                        "data_reference_count": 255,
                        "data_ref_owner_function_count": 0,
                        "bridge_record_window_count": 4,
                        "bridge_record_with_code_pointer_count": 2,
                        "inspected_function_count": 13,
                        "payload_owner_candidate_count": 0,
                        "partial_provenance_function_count": 1,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_INIT_DATA_OWNER:round76:summary"
                    ],
                    "route_conclusion": {
                        "init_luascripts_bridge_metadata_confirmed": True,
                        "data_reference_owners_found": False,
                        "bridge_record_code_pointers_found": True,
                        "payload_owner_candidate_found": False,
                        "file_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "global_metadata_loader_proven": False,
                        "plaintext_metadata_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "bridge records resolve to support pointers",
                        "strongest_negative_signal": "no payload-owner candidate",
                        "search_policy": "treat as routing evidence only",
                    },
                    "next_static_targets": ["prioritize TextAsset/LuaScripts payload decoder"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-vector-candidate-provenance-round121.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-vector-candidate-provenance-round121",
                    "round": 186,
                    "counts": {
                        "target_count": 17,
                        "vector_candidate_count": 9,
                        "provenance_linked_target_count": 1,
                        "provenance_linked_vector_candidate_count": 0,
                        "keyword_ref_target_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_VECTOR_PROVENANCE:round121:summary"
                    ],
                    "route_conclusion": {
                        "vector_candidate_provenance_link_found": False,
                        "read_mapping_to_vector_path_found": False,
                        "read_mapping_to_file_helper_path_found": True,
                        "metadata_or_luascripts_keyword_link_found": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "file helper path only",
                        "strongest_negative_signal": "vector helpers remain unlinked",
                        "search_policy": "recover payload-owner provenance",
                    },
                    "next_static_targets": ["recover payload-owner provenance"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-vector-wrapper-owner-probe-round130.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-vector-wrapper-owner-probe-round130",
                    "round": 189,
                    "counts": {
                        "vector_target_count": 11,
                        "wrapper_function_count": 13,
                        "direct_vector_wrapper_count": 12,
                        "vector_call_edge_count": 59,
                        "wrapper_with_keyword_ref_count": 0,
                        "wrapper_with_read_mapping_import_count": 0,
                        "wrapper_with_provenance_path_count": 0,
                        "vector_wrapper_owner_candidate_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_VECTOR_WRAPPER_OWNER:round130:summary"
                    ],
                    "route_conclusion": {
                        "vector_wrapper_owner_candidate_found": False,
                        "vector_wrapper_payload_owner_proven": False,
                        "read_mapping_to_vector_wrapper_path_found": False,
                        "read_mapping_import_in_vector_wrapper_found": False,
                        "file_helper_to_vector_wrapper_bridge_found": False,
                        "metadata_or_luascripts_keyword_link_found": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "vector wrappers remain unlinked",
                        "strongest_negative_signal": "no payload owner signal",
                        "search_policy": "demote isolated vector-wrapper clusters",
                    },
                    "next_static_targets": ["recover payload-owner provenance"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-file-helper-caller-provenance-round124.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-file-helper-caller-provenance-round124",
                    "round": 187,
                    "counts": {
                        "target_count": 24,
                        "helper_seed_target_count": 3,
                        "caller_path_to_helper_count": 4,
                        "payload_keyword_ref_function_count": 0,
                        "createfile_import_function_count": 1,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_FILE_HELPER_CALLER:round124:summary"
                    ],
                    "route_conclusion": {
                        "file_helper_payload_owner_proven": False,
                        "read_mapping_to_file_helper_path_found": True,
                        "metadata_or_luascripts_keyword_link_found": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "file helper context has no payload refs",
                        "strongest_negative_signal": "no payload path terms",
                        "search_policy": "treat 0xda90 as generic helper",
                    },
                    "next_static_targets": ["pivot to GameAssembly metadata route"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-global-metadata-owner-probe-round127.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "nslg.gameassembly_global_metadata_owner_probe.v1",
                    "source_id": "gameassembly-global-metadata-owner-probe-round127",
                    "source_url": "local-nslg-client-gameassembly-global-metadata-owner-probe",
                    "source_site": "nslg_client_gameassembly_global_metadata_owner_probe",
                    "round": 188,
                    "counts": {
                        "target_count": 2,
                        "seed_function_count": 2,
                        "metadata_string_ref_function_count": 2,
                        "file_or_mapping_import_function_count": 0,
                        "metadata_candidate_ref_function_count": 0,
                        "loader_owner_candidate_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
                    "route_conclusion": {
                        "global_metadata_owner_candidate_found": False,
                        "global_metadata_string_refs_confirmed": True,
                        "file_or_mapping_api_link_found": False,
                        "metadata_registration_candidate_link_found": False,
                        "metadata_registration_owner_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "global-metadata string refs only",
                        "strongest_negative_signal": "no loader owner context",
                        "search_policy": "do not promote string refs alone",
                    },
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_GLOBAL_METADATA_OWNER:round127:summary"
                    ],
                    "limitations": ["static global-metadata owner probe only"],
                    "next_static_targets": ["recover protected metadata ownership"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-resolver-trace-round58.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-resolver-trace-round58",
                    "round": 165,
                    "target": {
                        "resolver_candidate_rva": "0x5ccc30",
                        "candidate_found": True,
                    },
                    "counts": {
                        "resolver_candidate_direct_callsite_count": 2948,
                        "caller_keyword_ref_function_count": 28,
                    },
                    "notable_caller_functions": [
                        {"function": {"begin": "0xc78b0"}, "counts": {"keyword_refs": 1}}
                    ],
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_RESOLVER_TRACE:round58:candidate:0x5ccc30"
                    ],
                    "route_conclusion": {
                        "resolver_candidate_function_found": True,
                        "descriptor_resolver_pattern_supported": True,
                        "candidate_has_payload_owner_signal": False,
                        "method_ownership_recovered": False,
                        "textasset_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "strongest_current_signal": "descriptor resolver routing",
                        "strongest_negative_signal": "payload owner is not proven",
                        "search_policy": "keep as resolver evidence",
                    },
                    "next_static_targets": ["recover protected metadata"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-gameassembly-resolver-caller-trace-round61.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "gameassembly-resolver-caller-trace-round61",
                    "round": 166,
                    "target": {
                        "resolver_candidate_rva": "0x5ccc30",
                        "search_scope": "all direct rel32 caller functions with pdata coverage",
                    },
                    "counts": {
                        "resolver_candidate_direct_callsite_count": 2948,
                        "unique_direct_caller_function_count": 2870,
                        "caller_with_xlua_api_ref_count": 150,
                        "caller_with_textasset_ref_count": 0,
                        "payload_owner_candidate_count": 0,
                    },
                    "category_counts": {"xlua_api": 150},
                    "classification_counts": {
                        "no_payload_signal": 2720,
                        "xlua_descriptor_only": 150,
                    },
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_RESOLVER_CALLER_TRACE:round61:target:0x5ccc30"
                    ],
                    "route_conclusion": {
                        "all_direct_resolver_callers_scanned": True,
                        "resolver_layer_has_payload_owner_candidate": False,
                        "textasset_payload_owner_proven": False,
                        "file_buffer_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "strongest_current_signal": "descriptor-only callers",
                        "strongest_negative_signal": "no payload owner candidate",
                        "search_policy": "recover metadata ownership",
                    },
                    "next_static_targets": ["recover protected metadata"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_queue_sorts_review_and_decoder_work_without_publish_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_fixture_artifacts(root)
            queue = build_client_import_queue(
                repo_root=root,
                source_id="fixture-queue",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(queue.schema_version, "nslg.client_import_queue.v1")
        self.assertEqual(queue.source_id, "fixture-queue")
        self.assertEqual(queue.client_version["app_version"], "1.29.0")
        self.assertFalse(queue.publish_readiness["safe_for_publish"])
        self.assertFalse(queue.publish_readiness["auto_publish_allowed"])
        self.assertEqual(queue.queue_type_counts["client_resource_surface_gap_scan_target"], 1)
        self.assertEqual(queue.queue_type_counts["ns_bundle_format_index_target"], 1)
        self.assertEqual(queue.queue_type_counts["decoded_hero_review"], 1)
        self.assertEqual(queue.queue_type_counts["luascripts_decoder_target"], 1)
        self.assertEqual(queue.queue_type_counts["lua_crypto_decoder_target"], 1)
        self.assertNotIn("luascripts_payload_cipher_profile_target", queue.queue_type_counts)
        self.assertEqual(queue.queue_type_counts["luascripts_payload_variant_corpus_target"], 1)
        self.assertNotIn("textasset_payload_owner_trace_target", queue.queue_type_counts)
        self.assertNotIn("serialized_textasset_layout_probe_target", queue.queue_type_counts)
        self.assertNotIn("serialized_textasset_path_resolution_target", queue.queue_type_counts)
        self.assertNotIn("resolved_payload_native_anchor_scan_target", queue.queue_type_counts)
        self.assertEqual(queue.queue_type_counts["textasset_xlua_boundary_ledger_target"], 1)
        self.assertEqual(queue.queue_type_counts["nep2_static_trace_target"], 1)
        self.assertEqual(queue.queue_type_counts["gameassembly_static_trace_target"], 1)
        self.assertEqual(queue.queue_type_counts["nep2_init_bridge_trace_target"], 1)
        self.assertEqual(queue.queue_type_counts["native_loadbuffer_boundary_trace_target"], 1)
        self.assertNotIn("runtime_init_metadata_route_target", queue.queue_type_counts)
        self.assertNotIn("runtime_init_registry_probe_target", queue.queue_type_counts)
        self.assertNotIn("gameassembly_codegen_module_probe_target", queue.queue_type_counts)
        self.assertNotIn("gameassembly_registration_anchor_probe_target", queue.queue_type_counts)
        self.assertNotIn("gameassembly_registration_layout_probe_target", queue.queue_type_counts)
        self.assertEqual(queue.queue_type_counts["gameassembly_registration_pair_context_probe_target"], 1)
        self.assertEqual(queue.queue_type_counts["gameassembly_initializer_dispatch_trace_target"], 1)
        self.assertEqual(queue.queue_type_counts["gameassembly_function_pointer_table_probe_target"], 1)
        self.assertEqual(
            queue.queue_type_counts["gameassembly_metadata_registration_candidate_taxonomy_target"],
            1,
        )
        self.assertEqual(queue.queue_type_counts["gameassembly_global_metadata_owner_probe_target"], 1)
        self.assertEqual(queue.queue_type_counts["global_metadata_transform_probe_target"], 1)
        self.assertNotIn("global_metadata_loader_scan_target", queue.queue_type_counts)
        self.assertNotIn("nep2_metadata_loader_deep_slice_target", queue.queue_type_counts)
        self.assertNotIn("nep2_read_mapping_owner_scan_target", queue.queue_type_counts)
        self.assertEqual(queue.queue_type_counts["nep2_init_data_owner_scan_target"], 1)
        self.assertEqual(queue.queue_type_counts["nep2_vector_candidate_provenance_target"], 1)
        self.assertEqual(queue.queue_type_counts["nep2_vector_wrapper_owner_probe_target"], 1)
        self.assertEqual(queue.queue_type_counts["nep2_file_helper_caller_provenance_target"], 1)
        self.assertEqual(queue.queue_type_counts["gameassembly_resolver_trace_target"], 1)
        self.assertEqual(queue.queue_type_counts["gameassembly_resolver_caller_trace_target"], 1)

        resource_item = next(
            item
            for item in queue.items
            if item.queue_type == "client_resource_surface_gap_scan_target"
        )
        self.assertEqual(resource_item.readiness, "static_inventory_target")
        self.assertTrue(resource_item.metadata["resource_surface_gap_identified"])
        self.assertTrue(resource_item.metadata["luascripts_ns_found"])
        self.assertEqual(resource_item.counts["ns_bundle_count"], 369)

        ns_index_item = next(
            item for item in queue.items if item.queue_type == "ns_bundle_format_index_target"
        )
        self.assertEqual(ns_index_item.readiness, "static_index_target")
        self.assertTrue(ns_index_item.metadata["all_indexed_bundles_look_protected"])
        self.assertEqual(ns_index_item.counts["protected_serialized_metadata_count"], 369)
        self.assertIn("luascripts.ns", ns_index_item.metadata["high_value_priority_bundles"])

        hero_item = next(item for item in queue.items if item.queue_type == "decoded_hero_review")
        self.assertEqual(hero_item.readiness, "needs_manual_review")
        self.assertIn("NSLG_CLIENT_DECODED:round29:heroID=1000", hero_item.evidence_refs)
        self.assertTrue(any("20890" in blocker for blocker in hero_item.blockers))

        luascripts_item = next(
            item for item in queue.items if item.queue_type == "luascripts_decoder_target"
        )
        self.assertEqual(luascripts_item.topic, "heros")
        self.assertEqual(luascripts_item.readiness, "blocked_pending_decoder")
        self.assertEqual(luascripts_item.metadata["sample_extracted_artifacts"][0], "threads/artifacts/heros.bytes.bin")

        gameassembly_item = next(
            item for item in queue.items if item.queue_type == "gameassembly_static_trace_target"
        )
        self.assertEqual(gameassembly_item.readiness, "static_trace_target")
        self.assertFalse(gameassembly_item.metadata["textasset_loadbuffer_bridge_proven"])

        variant_item = next(
            item
            for item in queue.items
            if item.queue_type == "luascripts_payload_variant_corpus_target"
        )
        self.assertEqual(variant_item.readiness, "blocked_pending_decoder")
        self.assertTrue(variant_item.metadata["simple_offset_skip_route_ruled_out"])
        self.assertFalse(variant_item.metadata["lua_payload_decoder_recovered"])
        self.assertEqual(variant_item.counts["payload_variant_count"], 932)

        boundary_item = next(
            item
            for item in queue.items
            if item.queue_type == "textasset_xlua_boundary_ledger_target"
        )
        self.assertEqual(boundary_item.readiness, "static_trace_target")
        self.assertEqual(boundary_item.counts["closed_negative_route_count"], 4)
        self.assertEqual(
            boundary_item.metadata["next_viable_route"],
            "protected_metadata_method_ownership_or_boundary_control_flow",
        )
        self.assertTrue(boundary_item.metadata["exact_native_anchor_route_closed"])

        bridge_item = next(
            item for item in queue.items if item.queue_type == "nep2_init_bridge_trace_target"
        )
        self.assertEqual(bridge_item.readiness, "static_trace_target")
        self.assertFalse(bridge_item.metadata["decryptor_body_proven"])

        native_item = next(
            item for item in queue.items if item.queue_type == "native_loadbuffer_boundary_trace_target"
        )
        self.assertEqual(native_item.readiness, "static_trace_target")
        self.assertFalse(native_item.metadata["textasset_to_loadbuffer_owner_proven"])
        self.assertEqual(native_item.counts["loadbuffer_export_signal_count"], 3)

        pair_context_item = next(
            item
            for item in queue.items
            if item.queue_type == "gameassembly_registration_pair_context_probe_target"
        )
        self.assertEqual(pair_context_item.readiness, "static_trace_target")
        self.assertFalse(pair_context_item.metadata["registration_pair_recovered"])
        self.assertTrue(pair_context_item.metadata["metadata_candidate_family_refs_found"])
        self.assertFalse(pair_context_item.metadata["direct_code_registration_start_ref_found"])
        self.assertFalse(pair_context_item.metadata["init_lua_env_method_pointer_recovered"])
        self.assertEqual(pair_context_item.counts["raw_metadata_candidate_ref_count"], 25)
        self.assertEqual(pair_context_item.counts["paired_neighborhood_count"], 0)

        initializer_item = next(
            item
            for item in queue.items
            if item.queue_type == "gameassembly_initializer_dispatch_trace_target"
        )
        self.assertEqual(initializer_item.readiness, "static_trace_target")
        self.assertFalse(initializer_item.metadata["initializer_dispatcher_route_recovered"])
        self.assertFalse(initializer_item.metadata["init_lua_env_method_pointer_recovered"])
        self.assertEqual(initializer_item.counts["global_metadata_string_ref_function_count"], 2)
        self.assertEqual(initializer_item.counts["registration_anchor_ref_function_count"], 0)

        function_pointer_item = next(
            item
            for item in queue.items
            if item.queue_type == "gameassembly_function_pointer_table_probe_target"
        )
        self.assertEqual(function_pointer_item.readiness, "static_trace_target")
        self.assertTrue(
            function_pointer_item.metadata["dispatcher_pointer_hits_classified_as_known_il2cpp_tables"]
        )
        self.assertFalse(function_pointer_item.metadata["initializer_table_route_recovered"])
        self.assertEqual(function_pointer_item.counts["dispatcher_pointer_hit_count"], 22)
        self.assertEqual(function_pointer_item.counts["dispatcher_pointer_hits_outside_known_tables"], 0)

        metadata_taxonomy_item = next(
            item
            for item in queue.items
            if item.queue_type == "gameassembly_metadata_registration_candidate_taxonomy_target"
        )
        self.assertEqual(metadata_taxonomy_item.readiness, "static_trace_target")
        self.assertTrue(
            metadata_taxonomy_item.metadata[
                "exact_ref_metadata_candidates_are_tiny_count_family"
            ]
        )
        self.assertFalse(metadata_taxonomy_item.metadata["high_count_candidates_have_exact_refs"])
        self.assertEqual(metadata_taxonomy_item.counts["exact_ref_non_tiny_candidate_count"], 0)
        self.assertEqual(metadata_taxonomy_item.counts["referenced_high_count_candidate_count"], 0)

        global_metadata_owner_item = next(
            item
            for item in queue.items
            if item.queue_type == "gameassembly_global_metadata_owner_probe_target"
        )
        self.assertEqual(global_metadata_owner_item.readiness, "static_trace_target")
        self.assertTrue(global_metadata_owner_item.metadata["global_metadata_string_refs_confirmed"])
        self.assertFalse(global_metadata_owner_item.metadata["global_metadata_owner_candidate_found"])
        self.assertFalse(global_metadata_owner_item.metadata["file_or_mapping_api_link_found"])
        self.assertEqual(global_metadata_owner_item.counts["loader_owner_candidate_count"], 0)

        metadata_probe_item = next(
            item for item in queue.items if item.queue_type == "global_metadata_transform_probe_target"
        )
        self.assertEqual(metadata_probe_item.readiness, "static_trace_target")
        self.assertFalse(metadata_probe_item.metadata["plaintext_metadata_recovered"])
        self.assertEqual(metadata_probe_item.counts["transform_candidate_count"], 1314)

        init_data_item = next(
            item
            for item in queue.items
            if item.queue_type == "nep2_init_data_owner_scan_target"
        )
        self.assertEqual(init_data_item.readiness, "static_trace_target")
        self.assertTrue(init_data_item.metadata["bridge_record_code_pointers_found"])
        self.assertFalse(init_data_item.metadata["payload_owner_candidate_found"])
        self.assertFalse(init_data_item.metadata["plaintext_metadata_recovered"])
        self.assertEqual(init_data_item.counts["inspected_function_count"], 13)

        vector_item = next(
            item
            for item in queue.items
            if item.queue_type == "nep2_vector_candidate_provenance_target"
        )
        self.assertEqual(vector_item.readiness, "static_trace_target")
        self.assertFalse(vector_item.metadata["read_mapping_to_vector_path_found"])
        self.assertTrue(vector_item.metadata["read_mapping_to_file_helper_path_found"])
        self.assertEqual(vector_item.counts["provenance_linked_vector_candidate_count"], 0)

        wrapper_item = next(
            item
            for item in queue.items
            if item.queue_type == "nep2_vector_wrapper_owner_probe_target"
        )
        self.assertEqual(wrapper_item.readiness, "static_trace_target")
        self.assertFalse(wrapper_item.metadata["vector_wrapper_payload_owner_proven"])
        self.assertFalse(wrapper_item.metadata["read_mapping_to_vector_wrapper_path_found"])
        self.assertEqual(wrapper_item.counts["vector_wrapper_owner_candidate_count"], 0)

        file_helper_item = next(
            item
            for item in queue.items
            if item.queue_type == "nep2_file_helper_caller_provenance_target"
        )
        self.assertEqual(file_helper_item.readiness, "static_trace_target")
        self.assertFalse(file_helper_item.metadata["file_helper_payload_owner_proven"])
        self.assertTrue(file_helper_item.metadata["read_mapping_to_file_helper_path_found"])
        self.assertEqual(file_helper_item.counts["payload_keyword_ref_function_count"], 0)

        resolver_item = next(
            item for item in queue.items if item.queue_type == "gameassembly_resolver_trace_target"
        )
        self.assertEqual(resolver_item.readiness, "static_trace_target")
        self.assertTrue(resolver_item.metadata["descriptor_resolver_pattern_supported"])
        self.assertFalse(resolver_item.metadata["textasset_payload_owner_proven"])
        self.assertEqual(resolver_item.counts["resolver_candidate_direct_callsite_count"], 2948)

        resolver_caller_item = next(
            item for item in queue.items if item.queue_type == "gameassembly_resolver_caller_trace_target"
        )
        self.assertEqual(resolver_caller_item.readiness, "static_trace_target")
        self.assertFalse(resolver_caller_item.metadata["resolver_layer_has_payload_owner_candidate"])
        self.assertFalse(resolver_caller_item.metadata["textasset_payload_owner_proven"])
        self.assertEqual(resolver_caller_item.counts["payload_owner_candidate_count"], 0)

    def test_cli_writes_yaml_queue(self) -> None:
        from qa_agent.app.build_client_import_queue import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_fixture_artifacts(root)
            output_path = root / "queue.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "build_client_import_queue",
                    "--repo-root",
                    str(root),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-queue",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.client_import_queue.v1")
        self.assertEqual(data["source_id"], "fixture-queue")
        self.assertEqual(data["queue_item_count"], 23)
        self.assertFalse(data["publish_readiness"]["safe_for_publish"])
        self.assertEqual(summary["queue_item_count"], 23)
        self.assertEqual(summary["queue_type_counts"]["decoded_hero_review"], 1)


if __name__ == "__main__":
    unittest.main()
