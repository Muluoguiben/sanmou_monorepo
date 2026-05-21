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

from qa_agent.ingestion.client_evidence_bundle import build_client_evidence_bundle


class ClientEvidenceBundleTests(unittest.TestCase):
    def _write_fixture_artifacts(self, root: Path) -> None:
        raw_dir = root / "ingestion" / "raw" / "client_packages"
        staging_dir = root / "ingestion" / "staging" / "client_decoded"
        raw_dir.mkdir(parents=True)
        staging_dir.mkdir(parents=True)
        (raw_dir / "nslg-pc-1.29.0-manifest.yaml").write_text(
            yaml.safe_dump(
                {
                    "root_name": "NSLG Game",
                    "scanned_at": "2026-05-20T12:00:00Z",
                    "version_info": {
                        "manifest": {
                            "m_AppVersion": "1.29.0",
                            "m_GlobalBundleVersion": 129,
                            "m_AppGitVersion": "abc123",
                        }
                    },
                    "total_files_seen": 4,
                    "included_files": 3,
                    "skipped_files": 1,
                    "files": [
                        {
                            "relative_path": "GameAssembly.dll",
                            "detected_type": "native_binary",
                            "knowledge_value": "reverse_engineering_anchor",
                            "source_ref": "NSLG_CLIENT:GameAssembly.dll#sha256=aaa",
                        },
                        {
                            "relative_path": "assets/luascripts.ns",
                            "detected_type": "unity_asset_bundle",
                            "knowledge_value": "asset_bundle_candidate",
                            "source_ref": "NSLG_CLIENT:assets/luascripts.ns#sha256=bbb",
                        },
                    ],
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
                        {
                            "group": "luascripts.ns",
                            "file_count": 1,
                            "total_bytes": 33098121,
                            "largest_file_bytes": 33098121,
                            "evidence_ref": "NSLG_CLIENT_RESOURCE_SURFACE:round190:ns-group:luascripts",
                        }
                    ],
                    "safe_magic_samples": [
                        {
                            "rel_path": "LocalPersistentData/assets/bundles/luascripts.ns",
                            "size": 33098121,
                            "suffix": ".ns",
                            "evidence_ref": "NSLG_CLIENT_RESOURCE_SURFACE:round190:magic:luascripts",
                        }
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
                    "limitations": ["resource cache bundles are inventoried but not decoded"],
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
                        "engine_version:2022.3.61f2": 369,
                        "publishable_knowledge_entries": 0,
                    },
                    "format_groups": [
                        {
                            "asset_group": "luascripts.ns",
                            "bundle_count": 1,
                            "total_bytes": 33098121,
                            "parse_ok_count": 1,
                            "protected_metadata_count": 1,
                            "directory_shapes": {"cab_only": 1},
                            "sample_rel_paths": ["luascripts.ns"],
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:group:luascripts",
                        }
                    ],
                    "cab_block2_groups": [
                        {
                            "metadata_block2_hex": "c5 30 54 e1 bf c4 02 33",
                            "bundle_count": 32,
                            "asset_group_counts": {"terrain": 30},
                            "sample_rel_paths": ["terrain/demo/h0.ns"],
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:block2:terrain",
                        }
                    ],
                    "priority_records": [
                        {
                            "rel_path": "luascripts.ns",
                            "asset_group": "luascripts.ns",
                            "priority_rank": 1,
                            "size_bytes": 33098121,
                            "directory_shape": "cab_only",
                            "block_count": 257,
                            "directory_node_count": 1,
                            "protected_metadata_likely": True,
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:bundle:luascripts",
                        }
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
                    "limitations": ["format index is not decoded gameplay knowledge"],
                    "next_static_targets": ["recover protected metadata transform"],
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
                    "source_url": "local-nslg-client-luascripts",
                    "source_site": "nslg_client_luascripts",
                    "total_container_entries": 10,
                    "total_data_entries": 7,
                    "cataloged_records": 2,
                    "unique_stems": 2,
                    "kb_domain_counts": {"hero": 1, "skill": 1},
                    "extraction_status_counts": {"obfuscated_binary_pending_decoder": 2},
                    "high_value_stems": ["heros", "skills"],
                    "records": [
                        {
                            "evidence_ref": "NSLG_LUASCRIPT_TEXTASSET:round31:heros:0x1",
                            "stem": "heros",
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
                    "source_url": "local-nslg-client-lua-crypto",
                    "source_site": "nslg_client_lua_crypto",
                    "binary_string_hits": [{"binary_name": "GameAssembly.dll"}],
                    "payload_block_samples": [{"file_name": "heros.bytes.bin"}],
                    "payload_status_counts": {"high_entropy_16byte_aligned": 1},
                    "runtime_initialize_lua_entries": [{"method_name": "InitLuaEnv"}],
                    "skipped_runtime_patch_samples": 1,
                    "limitations": ["static evidence only"],
                    "next_decoder_targets": ["trace xluaL_loadbuffer"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-luascripts-payload-cipher-profile-round49.yaml").write_text(
            yaml.safe_dump(
                {
                    "schema_version": "nslg.luascripts_payload_cipher_profile.v1",
                    "source_id": "luascripts-payload-cipher-profile-round49",
                    "source_url": "local-nslg-client-luascripts-cipher-profile",
                    "source_site": "nslg_client_luascripts_cipher_profile",
                    "round": 162,
                    "payload_profile_count": 1,
                    "payload_status_counts": {"high_entropy_16byte_aligned": 1},
                    "payload_profiles": [
                        {
                            "evidence_ref": "NSLG_LUASCRIPT_CIPHER_PROFILE:round49:payload:heros.bytes.bin",
                            "file_name": "heros.bytes.bin",
                            "stem": "heros",
                            "size_bytes": 23232,
                            "status": "high_entropy_16byte_aligned",
                        }
                    ],
                    "cross_file_block_profile": {
                        "cross_file_shared_16byte_block_count": 0,
                        "duplicate_first_block_count": 0,
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
                        "safe_for_publish": False,
                        "strongest_current_signal": "payloads are high entropy",
                        "strongest_negative_signal": "payload decoder is not recovered",
                        "search_policy": "locate native buffer owner",
                    },
                    "evidence_refs": [
                        "NSLG_LUASCRIPT_CIPHER_PROFILE:round49:payload:heros.bytes.bin"
                    ],
                    "limitations": ["static payload analysis only"],
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
                    "schema_version": "nslg.luascripts_payload_variant_corpus.v1",
                    "source_id": "luascripts-payload-variant-corpus-round79",
                    "source_url": "local-nslg-client-luascripts-payload-variant-corpus",
                    "source_site": "nslg_client_luascripts_variant_corpus",
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
                        {
                            "stem": "heros",
                            "record_count": 1,
                            "variant_count": 1,
                            "unique_ciphertext_hash_count": 1,
                            "duplicate_ciphertext_hash_group_count": 0,
                            "duplicate_ciphertext_variant_count": 0,
                            "entropy_avg": 7.99,
                            "printable_score_4k_avg": 0.37,
                            "direct_plaintext_term_variant_count": 0,
                        }
                    ],
                    "block_sharing_summary": {
                        "cross_cipher_shared_16byte_block_count": 55,
                    },
                    "offset_skip_probe_summary": {
                        "decompression_success_count": 0,
                        "plaintext_hit_count": 0,
                        "high_printable_candidate_count": 0,
                    },
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
                    "evidence_refs": [
                        "NSLG_LUASCRIPT_VARIANT_CORPUS:round79:stem:heros"
                    ],
                    "limitations": ["static payload corpus only"],
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
                    "schema_version": "nslg.textasset_payload_owner_trace.v1",
                    "source_id": "textasset-payload-owner-trace-round82",
                    "source_url": "local-nslg-client-textasset-payload-owner-trace",
                    "source_site": "nslg_client_textasset_payload_owner_trace",
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
                    "module_records": [{"module": "GameAssembly.dll"}],
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
                    "limitations": ["static TextAsset route scan only"],
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
                    "schema_version": "nslg.serialized_textasset_layout.v1",
                    "source_id": "serialized-textasset-layout-round85",
                    "source_url": "local-nslg-client-serialized-textasset-layout-probe",
                    "source_site": "nslg_client_serialized_textasset_layout_probe",
                    "round": 174,
                    "counts": {
                        "relevant_record_count": 104,
                        "match_count": 932,
                        "valid_layout_count": 932,
                        "invalid_layout_count": 0,
                        "name_stem_match_count": 932,
                        "unique_object_offset_count": 52,
                        "unique_payload_hash_count": 52,
                        "unique_stem_count": 16,
                        "duplicate_object_offset_group_count": 40,
                    },
                    "stem_summaries": [{"stem": "heros", "match_count": 1}],
                    "object_layout_groups": [{"stem": "heros", "layout_valid": True}],
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
                    "limitations": ["static layout probe only"],
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
                    "schema_version": "nslg.serialized_textasset_path_resolution.v1",
                    "source_id": "serialized-textasset-path-resolution-round88",
                    "source_url": "local-nslg-client-serialized-textasset-path-resolution",
                    "source_site": "nslg_client_serialized_textasset_path_resolution",
                    "round": 175,
                    "counts": {
                        "relevant_record_count": 104,
                        "container_record_valid_count": 104,
                        "container_record_invalid_count": 0,
                        "resolved_record_count": 104,
                        "unresolved_record_count": 0,
                        "ambiguous_record_count": 0,
                        "unique_path_id_count": 104,
                        "unique_resolved_object_offset_count": 16,
                        "unique_resolved_payload_sha1_count": 16,
                    },
                    "resolved_records": [
                        {
                            "path": "Assets/Bundles/LuaScripts/Data/heros.bytes",
                            "stem": "heros",
                            "path_id_hex": "0x1",
                            "resolved": True,
                            "resolved_object_offset_hex": "0x7b",
                        }
                    ],
                    "resolved_object_groups": [{"stem": "heros", "path_count": 1}],
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
                    "limitations": ["static path resolution only"],
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
                    "schema_version": "nslg.resolved_payload_native_anchor_scan.v1",
                    "source_id": "resolved-payload-native-anchor-scan-round91",
                    "source_url": "local-nslg-client-resolved-payload-native-anchor-scan",
                    "source_site": "nslg_client_resolved_payload_native_anchor_scan",
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
                    "module_records": [{"module": "GameAssembly.dll"}],
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
                    "limitations": ["static native anchor scan only"],
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
                    "schema_version": "nslg.textasset_xlua_boundary_ledger.v1",
                    "source_id": "textasset-xlua-boundary-ledger-round94",
                    "source_url": "local-nslg-client-textasset-xlua-boundary-ledger",
                    "source_site": "nslg_client_textasset_xlua_boundary_ledger",
                    "round": 177,
                    "counts": {
                        "route_record_count": 6,
                        "closed_negative_route_count": 4,
                        "blocked_route_count": 1,
                        "next_viable_route_count": 1,
                        "proven_payload_owner_route_count": 0,
                        "native_loadbuffer_boundary_candidate_count": 1,
                        "gameassembly_resolver_payload_owner_candidate_count": 0,
                        "exact_anchor_native_hit_count": 0,
                    },
                    "route_records": [
                        {
                            "route_id": "resolved_payload_native_exact_anchor_scan",
                            "status": "closed_negative",
                        }
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
                    "limitations": ["ledger only"],
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
                    "source_url": "local-nslg-client-nep2-luascripts",
                    "source_site": "nslg_client_nep2_luascripts",
                    "size_bytes": 100,
                    "init_luascripts_occurrences": [{"rva": "0x88135e"}],
                    "pointer_refs_to_init_luascripts": 0,
                    "candidate_string_count": 4,
                    "selected_candidate_strings": ["InitLuaScriptsScan"],
                    "xref_count": 1,
                    "xrefs": [{"string": "O3P1P1_1P2P3WAES", "ref_rva": "0x3f4a"}],
                    "string_chunk_registrations": [{"chunk_text": "WAES"}],
                    "limitations": ["decryptor body not proven"],
                    "next_static_targets": ["trace InitLuaScriptsScan"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (raw_dir / "nslg-nep2-provenance-closures-round40.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "nep2-provenance-closures-round37",
                    "source_url": "local-nslg-client-nep2-provenance",
                    "source_site": "nslg_client_nep2_provenance",
                    "binary_name": "NEP2.dll",
                    "artifact_count": 2,
                    "round_range": {"min": 137, "max": 138},
                    "closure_status_counts": {"closed_no_file_buffer_provenance": 2},
                    "target_verdict_counts": {
                        "metadata/control helper; no current CAB transform proof": 1,
                        "nontrivial helper but no file/CAB provenance": 1,
                    },
                    "pointer_ref_classification_counts": {
                        "internal_rdata_tables_no_asset_owner": 1,
                        "none": 1,
                    },
                    "closed_rvas": ["0x620670", "0x678a20"],
                    "next_unclosed_shape_lead": "0x4a471a",
                    "route_conclusion": {
                        "strongest_negative_signal": "no file-buffer owner path",
                        "search_policy": "continue with provenance-backed candidates only",
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                    },
                    "records": [
                        {
                            "evidence_ref": "NSLG_NEP2_PROVENANCE:round37:round=137:rva=0x620670",
                            "round": 137,
                            "target_rva": "0x620670",
                            "closure_status": "closed_no_file_buffer_provenance",
                        }
                    ],
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
                    "source_url": "local-nslg-client-gameassembly-trace",
                    "source_site": "nslg_client_gameassembly_trace",
                    "binary_name": "GameAssembly.dll",
                    "artifact_count": 2,
                    "round_range": {"min": 42, "max": 160},
                    "status_counts": {
                        "static_trace_seed": 1,
                        "negative_route_correlation": 1,
                    },
                    "artifact_kind_counts": {
                        "xlua_global_metadata_anchor_trace": 1,
                        "textasset_loadbuffer_correlation": 1,
                    },
                    "route_signal_record_count": 0,
                    "total_target_strings": 12,
                    "total_code_refs": 1,
                    "total_function_refs": 1,
                    "route_conclusion": {
                        "textasset_loadbuffer_bridge_proven": False,
                        "strongest_current_signal": "TextAsset and xlua strings are present but no bridge was proven",
                        "search_policy": "keep as decoder routing evidence",
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                    },
                    "records": [
                        {
                            "evidence_ref": "NSLG_GAMEASSEMBLY_TRACE:round43:round=160:kind=textasset_loadbuffer_correlation",
                            "round": 160,
                            "artifact_kind": "textasset_loadbuffer_correlation",
                            "status": "negative_route_correlation",
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
                    "schema_version": "nslg.nep2_init_bridge.v1",
                    "source_id": "nep2-init-bridge-round46",
                    "source_url": "local-nslg-client-nep2-init-bridge",
                    "source_site": "nslg_client_nep2_init_bridge",
                    "binary_name": "NEP2.dll",
                    "round": 161,
                    "counts": {
                        "bridge_record_count": 4,
                        "candidate_function_count": 13,
                        "candidate_with_file_import_count": 1,
                    },
                    "status_counts": {"confirmed_rtti_lambda_metadata": 4},
                    "candidate_verdict_counts": {
                        "tiny metadata/lambda helper; no CAB transform proof": 9
                    },
                    "bridge_records": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_BRIDGE:round46:bridge:0x881320",
                            "rva": "0x881320",
                            "status": "confirmed_rtti_lambda_metadata",
                            "verdict": "metadata bridge only",
                        }
                    ],
                    "candidate_functions": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_BRIDGE:round46:candidate:0x4040",
                            "function_rva": "0x4040",
                            "verdict": "tiny metadata/lambda helper",
                            "score": 16,
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
                        "safe_for_publish": False,
                        "strongest_current_signal": "InitLuaScriptsScan metadata bridge is real",
                        "strongest_negative_signal": "payload decoder is not proven",
                        "search_policy": "continue with provenance-backed decoder targets only",
                    },
                    "limitations": ["static evidence only"],
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
                    "schema_version": "nslg.native_loadbuffer_boundary_trace.v1",
                    "source_id": "native-loadbuffer-boundary-round52",
                    "source_url": "local-nslg-client-native-loadbuffer-boundary",
                    "source_site": "nslg_client_native_boundary_trace",
                    "round": 163,
                    "counts": {
                        "module_count": 4,
                        "loadbuffer_export_signal_count": 3,
                        "boundary_import_call_count": 224,
                        "candidate_function_signal_count": 1,
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
                    "route_conclusion": {
                        "native_loadbuffer_export_present": True,
                        "gameassembly_static_xlua_import_present": False,
                        "gameassembly_to_xlua_static_bridge_proven": False,
                        "textasset_to_loadbuffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "xLua loadbuffer exports are present",
                        "strongest_negative_signal": "TextAsset owner is not proven",
                        "search_policy": "continue with provenance-backed tracing",
                    },
                    "evidence_refs": [
                        "NSLG_NATIVE_BOUNDARY:round52:module:GameAssembly.dll",
                        "NSLG_NATIVE_BOUNDARY:round52:module:xlua.dll",
                    ],
                    "limitations": ["static evidence only"],
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
                    "schema_version": "nslg.runtime_init_metadata_route.v1",
                    "source_id": "runtime-init-metadata-route-round55",
                    "source_url": "local-nslg-client-runtime-init-metadata-route",
                    "source_site": "nslg_client_runtime_init_metadata_route",
                    "round": 164,
                    "counts": {
                        "runtime_initialize_anchor_count": 1,
                        "global_metadata_file_size": 21182776,
                        "global_metadata_plaintext_needle_hit_count": 0,
                        "native_boundary_loadbuffer_export_signal_count": 3,
                    },
                    "route_conclusion": {
                        "runtime_init_anchor_known": True,
                        "global_metadata_protected_wrapper_confirmed": True,
                        "protected_global_metadata_decoded": False,
                        "init_lua_env_method_address_recovered": False,
                        "textasset_to_loadbuffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "InitLuaEnv is known",
                        "strongest_blocker": "metadata is protected",
                        "search_policy": "recover method ownership",
                    },
                    "evidence_refs": [
                        "NSLG_RUNTIME_INIT_ROUTE:round55:anchor:initluaenv"
                    ],
                    "limitations": ["static route summary only"],
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
                    "schema_version": "nslg.runtime_init_registry_probe.v1",
                    "source_id": "runtime-init-registry-probe-round97",
                    "source_url": "local-nslg-client-runtime-init-registry-probe",
                    "source_site": "nslg_client_runtime_init_registry_probe",
                    "round": 178,
                    "registry_summary": {
                        "file_name": "RuntimeInitializeOnLoads.json",
                        "present": True,
                        "entry_count": 12,
                        "entries": [{"method_name": "InitLuaEnv"}],
                        "init_lua_env_entries": [{"method_name": "InitLuaEnv"}],
                    },
                    "module_records": [{"module": "UnityPlayer.dll"}],
                    "unityplayer_runtime_json_xrefs": {"code_ref_count": 1},
                    "counts": {
                        "runtime_initialize_entry_count": 12,
                        "runtime_initialize_init_lua_env_entry_count": 1,
                        "registry_address_or_token_field_count": 0,
                        "modules_with_init_lua_env_hits": 0,
                        "modules_with_runtime_init_json_hits": 1,
                        "unityplayer_runtime_json_code_ref_count": 1,
                    },
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
                    "evidence_refs": ["NSLG_RUNTIME_INIT_REGISTRY:round97:summary"],
                    "limitations": ["registry names are not method ownership"],
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
                    "schema_version": "nslg.gameassembly_codegen_module_probe.v1",
                    "source_id": "gameassembly-codegen-module-probe-round100",
                    "source_url": "local-nslg-client-gameassembly-codegen-module-probe",
                    "source_site": "nslg_client_gameassembly_codegen_module_probe",
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
                            "struct_rva": "0x44196a0",
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
                    "evidence_refs": ["NSLG_CODEGEN_MODULE:round100:summary"],
                    "limitations": ["registration-side static evidence only"],
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
                    "schema_version": "nslg.gameassembly_registration_anchor_probe.v1",
                    "source_id": "gameassembly-registration-anchor-probe-round103",
                    "source_url": "local-nslg-client-gameassembly-registration-anchor-probe",
                    "source_site": "nslg_client_gameassembly_registration_anchor_probe",
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
                    "evidence_refs": [
                        "NSLG_REGISTRATION_ANCHOR:round180:codegen-modules-field"
                    ],
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
                    "schema_version": "nslg.gameassembly_registration_layout_probe.v1",
                    "source_id": "gameassembly-registration-layout-probe-round106",
                    "source_url": "local-nslg-client-gameassembly-registration-layout-probe",
                    "source_site": "nslg_client_gameassembly_registration_layout_probe",
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
                    "evidence_refs": [
                        "NSLG_REGISTRATION_LAYOUT:round181:code-registration-start"
                    ],
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
                    "schema_version": "nslg.gameassembly_registration_pair_context_probe.v1",
                    "source_id": "gameassembly-registration-pair-context-probe-round109",
                    "source_url": "local-nslg-client-gameassembly-registration-pair-context-probe",
                    "source_site": "nslg_client_gameassembly_registration_pair_context_probe",
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
                    "evidence_refs": [
                        "NSLG_REGISTRATION_PAIR_CONTEXT:round182:pair-neighborhood-scan"
                    ],
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
                    "schema_version": "nslg.gameassembly_initializer_dispatch_trace.v1",
                    "source_id": "gameassembly-initializer-dispatch-trace-round112",
                    "source_url": "local-nslg-client-gameassembly-initializer-dispatch-trace",
                    "source_site": "nslg_client_gameassembly_initializer_dispatch_trace",
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
                    "route_conclusion": {
                        "initializer_dispatcher_route_recovered": False,
                        "registration_ownership_recovered": False,
                        "metadata_registration_paired_by_dispatch_trace": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "safe_for_publish": False,
                        "summary": "bounded direct-call trace is negative",
                    },
                    "evidence_refs": [
                        "NSLG_INITIALIZER_DISPATCH_TRACE:round183:bounded-callgraph-paths"
                    ],
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
                    "schema_version": "nslg.gameassembly_function_pointer_table_probe.v1",
                    "source_id": "gameassembly-function-pointer-table-probe-round115",
                    "source_url": "local-nslg-client-gameassembly-function-pointer-table-probe",
                    "source_site": "nslg_client_gameassembly_function_pointer_table_probe",
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
                    "evidence_refs": [
                        "NSLG_FUNCTION_POINTER_TABLE:round184:nonexec-function-pointer-scan"
                    ],
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
                    "schema_version": "nslg.gameassembly_metadata_registration_candidate_taxonomy.v1",
                    "source_id": "gameassembly-metadata-registration-candidate-taxonomy-round118",
                    "source_url": "local-nslg-client-gameassembly-metadata-registration-candidate-taxonomy",
                    "source_site": "nslg_client_gameassembly_metadata_registration_candidate_taxonomy",
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
                    "evidence_refs": [
                        "NSLG_METADATA_TAXONOMY:round185:candidate-window-rescan"
                    ],
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
                    "schema_version": "nslg.global_metadata_transform_probe.v1",
                    "source_id": "global-metadata-transform-probe-round64",
                    "source_url": "local-nslg-client-global-metadata-transform-probe",
                    "source_site": "nslg_client_global_metadata",
                    "round": 167,
                    "counts": {
                        "global_metadata_file_size": 21182776,
                        "protected_size_mod_16": 0,
                        "transform_candidate_count": 1314,
                        "needle_hit_candidate_count": 0,
                        "best_header_valid_pair_count": 0,
                        "repeated_block_duplicate_kinds_16": 20744,
                    },
                    "route_conclusion": {
                        "protected_wrapper_confirmed": True,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "verdict": ["bounded transform probe did not recover metadata"],
                    },
                    "evidence_refs": [
                        "NSLG_GLOBAL_METADATA_TRANSFORM:round64:transform-probe"
                    ],
                    "limitations": ["static transform probe only"],
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
                    "schema_version": "nslg.global_metadata_loader_scan.v1",
                    "source_id": "global-metadata-loader-mutation-scan-round67",
                    "source_url": "local-nslg-client-global-metadata-loader-mutation-scan",
                    "source_site": "nslg_client_global_metadata_loader_mutation",
                    "round": 168,
                    "counts": {
                        "binary_count": 4,
                        "candidate_count": 554,
                        "full_loader_mutation_candidate_count": 0,
                        "file_16_candidate_count": 2,
                        "metadata_ref_candidate_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
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
                    "evidence_refs": [
                        "NSLG_GLOBAL_METADATA_LOADER:round67:summary"
                    ],
                    "limitations": ["static loader scan only"],
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
                    "schema_version": "nslg.nep2_global_metadata_loader_deep_slice.v1",
                    "source_id": "nep2-global-metadata-loader-deep-slice-round70",
                    "source_url": "local-nslg-client-nep2-global-metadata-loader-deep-slice",
                    "source_site": "nslg_client_nep2_global_metadata_loader_deep_slice",
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
                    "evidence_refs": [
                        "NSLG_NEP2_METADATA_LOADER_DEEP_SLICE:round70:summary"
                    ],
                    "limitations": ["static deep-slice only"],
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
                    "schema_version": "nslg.nep2_read_mapping_owner_scan.v1",
                    "source_id": "nep2-read-mapping-owner-scan-round73",
                    "source_url": "local-nslg-client-nep2-read-mapping-owner-scan",
                    "source_site": "nslg_client_nep2_read_mapping_owner_scan",
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
                    "evidence_refs": [
                        "NSLG_NEP2_READ_MAPPING_OWNER:round73:summary"
                    ],
                    "limitations": ["static owner scan only"],
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
                    "schema_version": "nslg.nep2_init_data_owner_scan.v1",
                    "source_id": "nep2-init-data-owner-scan-round76",
                    "source_url": "local-nslg-client-nep2-init-data-owner-scan",
                    "source_site": "nslg_client_nep2_init_data_owner_scan",
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
                    "evidence_refs": [
                        "NSLG_NEP2_INIT_DATA_OWNER:round76:summary"
                    ],
                    "limitations": ["static data-owner scan only"],
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
                    "schema_version": "nslg.nep2_vector_candidate_provenance.v1",
                    "source_id": "nep2-vector-candidate-provenance-round121",
                    "source_url": "local-nslg-client-nep2-vector-candidate-provenance",
                    "source_site": "nslg_client_nep2_vector_candidate_provenance",
                    "round": 186,
                    "counts": {
                        "target_count": 17,
                        "vector_candidate_count": 9,
                        "provenance_linked_target_count": 1,
                        "provenance_linked_vector_candidate_count": 0,
                        "keyword_ref_target_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
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
                    "evidence_refs": [
                        "NSLG_NEP2_VECTOR_PROVENANCE:round121:summary"
                    ],
                    "limitations": ["static vector provenance scan only"],
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
                    "schema_version": "nslg.nep2_vector_wrapper_owner_probe.v1",
                    "source_id": "nep2-vector-wrapper-owner-probe-round130",
                    "source_url": "local-nslg-client-nep2-vector-wrapper-owner-probe",
                    "source_site": "nslg_client_nep2_vector_wrapper_owner_probe",
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
                    "evidence_refs": [
                        "NSLG_NEP2_VECTOR_WRAPPER_OWNER:round130:summary"
                    ],
                    "limitations": ["static vector-wrapper owner probe only"],
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
                    "schema_version": "nslg.nep2_file_helper_caller_provenance.v1",
                    "source_id": "nep2-file-helper-caller-provenance-round124",
                    "source_url": "local-nslg-client-nep2-file-helper-caller-provenance",
                    "source_site": "nslg_client_nep2_file_helper_caller_provenance",
                    "round": 187,
                    "counts": {
                        "target_count": 24,
                        "helper_seed_target_count": 3,
                        "caller_path_to_helper_count": 4,
                        "payload_keyword_ref_function_count": 0,
                        "createfile_import_function_count": 1,
                        "publishable_knowledge_entries": 0,
                    },
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
                    "evidence_refs": [
                        "NSLG_NEP2_FILE_HELPER_CALLER:round124:summary"
                    ],
                    "limitations": ["static file-helper caller scan only"],
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
                    "schema_version": "nslg.gameassembly_resolver_trace.v1",
                    "source_id": "gameassembly-resolver-trace-round58",
                    "source_url": "local-nslg-client-gameassembly-resolver-trace",
                    "source_site": "nslg_client_gameassembly_resolver_trace",
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
                    "route_conclusion": {
                        "resolver_candidate_function_found": True,
                        "descriptor_resolver_pattern_supported": True,
                        "candidate_has_payload_owner_signal": False,
                        "method_ownership_recovered": False,
                        "textasset_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "descriptor resolver routing",
                        "strongest_negative_signal": "payload owner is not proven",
                        "search_policy": "keep as resolver evidence",
                    },
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_RESOLVER_TRACE:round58:candidate:0x5ccc30"
                    ],
                    "limitations": ["static resolver evidence only"],
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
                    "schema_version": "nslg.gameassembly_resolver_caller_trace.v1",
                    "source_id": "gameassembly-resolver-caller-trace-round61",
                    "source_url": "local-nslg-client-gameassembly-resolver-caller-trace",
                    "source_site": "nslg_client_gameassembly_resolver_caller_trace",
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
                    "route_conclusion": {
                        "all_direct_resolver_callers_scanned": True,
                        "resolver_layer_has_payload_owner_candidate": False,
                        "textasset_payload_owner_proven": False,
                        "file_buffer_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "descriptor-only callers",
                        "strongest_negative_signal": "no payload owner candidate",
                        "search_policy": "recover metadata ownership",
                    },
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_RESOLVER_CALLER_TRACE:round61:target:0x5ccc30"
                    ],
                    "limitations": ["static resolver caller evidence only"],
                    "next_static_targets": ["recover protected metadata"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )
        (staging_dir / "nslg-hero-readable-export-round29-audit.yaml").write_text(
            yaml.safe_dump(
                {
                    "source_id": "hero-readable-export-round29",
                    "source_url": "local-nslg-client-decoded",
                    "source_site": "nslg_client_decode",
                    "staging": {
                        "candidate_entries": 3,
                        "skipped_non_static_records": 1,
                    },
                    "hero_coverage": {"mapped_heroes": 2, "unmapped_heroes": [{"hero_id": 9}]},
                    "skill_coverage": {"mapped_skill_ids": 1, "unmapped_skill_ids": [100]},
                    "knowledge_validation": {"knowledge_entries_loaded": 8},
                    "security_scan": {"sensitive_markers_found": []},
                    "review_blockers": ["staging entries are normalized, not reviewed"],
                    "next_review_actions": ["review unmapped ids"],
                    "evidence_refs": ["NSLG_CLIENT_DECODED:round29:heroID=1"],
                },
                allow_unicode=True,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

    def test_bundle_summarizes_evidence_without_publish_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_fixture_artifacts(root)
            bundle = build_client_evidence_bundle(
                repo_root=root,
                source_id="fixture-bundle",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(bundle.source_id, "fixture-bundle")
        self.assertEqual(bundle.client_version["app_version"], "1.29.0")
        self.assertEqual(bundle.artifact_count, 38)
        self.assertFalse(bundle.import_readiness["safe_for_publish"])
        self.assertEqual(bundle.import_readiness["normalized_staging_entries"], 3)
        self.assertIn(
            "luascripts_textasset_catalog",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "luascripts_payload_cipher_profile",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "luascripts_payload_variant_corpus",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "textasset_payload_owner_trace",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "serialized_textasset_layout_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "serialized_textasset_path_resolution",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "resolved_payload_native_anchor_scan",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "textasset_xlua_boundary_ledger",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "ns_bundle_format_index",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn("decoder_routing", bundle.knowledge_domain_counts)
        self.assertIn("resource_bundle", bundle.knowledge_domain_counts)
        self.assertIn("xlua", bundle.knowledge_domain_counts)
        self.assertIn("gameassembly_route_trace", bundle.import_readiness["decoder_target_artifacts"])
        self.assertIn(
            "nep2_init_luascripts_bridge",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "native_loadbuffer_boundary_trace",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "runtime_init_metadata_route",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "runtime_init_registry_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_codegen_module_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_registration_anchor_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_registration_layout_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_registration_pair_context_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_initializer_dispatch_trace",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_function_pointer_table_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_metadata_registration_candidate_taxonomy",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "global_metadata_transform_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "global_metadata_loader_mutation_scan",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertNotIn(
            "nep2_global_metadata_loader_deep_slice",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertNotIn(
            "nep2_read_mapping_owner_scan",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertNotIn(
            "nep2_init_data_owner_scan",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertNotIn(
            "nep2_vector_candidate_provenance",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertNotIn(
            "nep2_vector_wrapper_owner_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertNotIn(
            "nep2_file_helper_caller_provenance",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertNotIn(
            "gameassembly_global_metadata_owner_probe",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_resolver_candidate_trace",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn(
            "gameassembly_resolver_caller_payload_trace",
            bundle.import_readiness["decoder_target_artifacts"],
        )
        self.assertIn("hero", bundle.knowledge_domain_counts)
        self.assertIn("runtime_init", bundle.knowledge_domain_counts)
        self.assertIn("il2cpp", bundle.knowledge_domain_counts)
        self.assertGreaterEqual(bundle.evidence_ref_count, 5)
        self.assertTrue(
            all(not artifact.path.startswith("/") for artifact in bundle.artifacts)
        )

    def test_cli_writes_yaml_bundle(self) -> None:
        from qa_agent.app.build_client_evidence_bundle import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_fixture_artifacts(root)
            output_path = root / "bundle.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "build_client_evidence_bundle",
                    "--repo-root",
                    str(root),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-bundle",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.client_evidence_bundle.v1")
        self.assertEqual(data["source_id"], "fixture-bundle")
        self.assertFalse(data["import_readiness"]["safe_for_publish"])
        self.assertEqual(summary["artifact_count"], 38)
        self.assertEqual(summary["normalized_staging_entries"], 3)


if __name__ == "__main__":
    unittest.main()
