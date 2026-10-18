from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .assets import (
    _client_resource_surface_gap_scan_items,
    _decoded_hero_review_items,
    _lua_crypto_decoder_items,
    _luascripts_cipher_profile_items,
    _luascripts_decoder_items,
    _luascripts_variant_corpus_items,
    _ns_bundle_format_index_items,
    _resolved_payload_native_anchor_scan_items,
    _serialized_textasset_layout_items,
    _serialized_textasset_resolution_items,
    _textasset_payload_owner_trace_items,
    _textasset_xlua_boundary_ledger_items,
)
from .models import (
    DEFAULT_CLIENT_RESOURCE_SURFACE_GAP_SCAN,
    DEFAULT_DECODED_HERO_AUDIT,
    DEFAULT_EVIDENCE_BUNDLE,
    DEFAULT_GAMEASSEMBLY_CODEGEN_MODULE_PROBE,
    DEFAULT_GAMEASSEMBLY_FUNCTION_POINTER_TABLE_PROBE,
    DEFAULT_GAMEASSEMBLY_GLOBAL_METADATA_OWNER_PROBE,
    DEFAULT_GAMEASSEMBLY_INITIALIZER_DISPATCH_TRACE,
    DEFAULT_GAMEASSEMBLY_METADATA_REGISTRATION_CANDIDATE_TAXONOMY,
    DEFAULT_GAMEASSEMBLY_REGISTRATION_ANCHOR_PROBE,
    DEFAULT_GAMEASSEMBLY_REGISTRATION_LAYOUT_PROBE,
    DEFAULT_GAMEASSEMBLY_REGISTRATION_PAIR_CONTEXT_PROBE,
    DEFAULT_GAMEASSEMBLY_RESOLVER_CALLER_TRACE,
    DEFAULT_GAMEASSEMBLY_RESOLVER_TRACE,
    DEFAULT_GAMEASSEMBLY_ROUTE_TRACE,
    DEFAULT_GLOBAL_METADATA_LOADER_SCAN,
    DEFAULT_GLOBAL_METADATA_TRANSFORM_PROBE,
    DEFAULT_LUASCRIPTS_CATALOG,
    DEFAULT_LUASCRIPTS_CIPHER_PROFILE,
    DEFAULT_LUASCRIPTS_VARIANT_CORPUS,
    DEFAULT_LUA_CRYPTO_EVIDENCE,
    DEFAULT_NATIVE_BOUNDARY_TRACE,
    DEFAULT_NEP2_FILE_HELPER_CALLER_PROVENANCE,
    DEFAULT_NEP2_INIT_BRIDGE,
    DEFAULT_NEP2_INIT_DATA_OWNER_SCAN,
    DEFAULT_NEP2_LUASCRIPTS_EVIDENCE,
    DEFAULT_NEP2_METADATA_LOADER_DEEP_SLICE,
    DEFAULT_NEP2_READ_MAPPING_OWNER_SCAN,
    DEFAULT_NEP2_VECTOR_CANDIDATE_PROVENANCE,
    DEFAULT_NEP2_VECTOR_WRAPPER_OWNER_PROBE,
    DEFAULT_NORMALIZED_STAGING,
    DEFAULT_NS_BUNDLE_FORMAT_INDEX,
    DEFAULT_RESOLVED_PAYLOAD_NATIVE_ANCHOR_SCAN,
    DEFAULT_RUNTIME_INIT_REGISTRY_PROBE,
    DEFAULT_RUNTIME_INIT_ROUTE,
    DEFAULT_SERIALIZED_TEXTASSET_LAYOUT,
    DEFAULT_SERIALIZED_TEXTASSET_RESOLUTION,
    DEFAULT_TEXTASSET_PAYLOAD_OWNER_TRACE,
    DEFAULT_TEXTASSET_XLUA_BOUNDARY_LEDGER,
    ClientImportQueue,
    ClientImportQueueItem,
)
from .native_metadata import (
    _gameassembly_function_pointer_table_probe_items,
    _gameassembly_global_metadata_owner_probe_items,
    _gameassembly_metadata_registration_candidate_taxonomy_items,
    _gameassembly_resolver_caller_trace_items,
    _gameassembly_resolver_trace_items,
    _global_metadata_loader_scan_items,
    _global_metadata_transform_probe_items,
    _nep2_file_helper_caller_provenance_items,
    _nep2_init_data_owner_scan_items,
    _nep2_metadata_loader_deep_slice_items,
    _nep2_read_mapping_owner_scan_items,
    _nep2_vector_candidate_provenance_items,
    _nep2_vector_wrapper_owner_probe_items,
)
from .native_runtime import (
    _gameassembly_codegen_module_probe_items,
    _gameassembly_initializer_dispatch_trace_items,
    _gameassembly_registration_anchor_probe_items,
    _gameassembly_registration_layout_probe_items,
    _gameassembly_registration_pair_context_probe_items,
    _gameassembly_static_trace_items,
    _native_boundary_trace_items,
    _nep2_init_bridge_trace_items,
    _nep2_static_trace_items,
    _runtime_init_registry_probe_items,
    _runtime_init_route_items,
)
from .utils import (
    _build_publish_readiness,
    _client_version,
    _input_path,
    _load_yaml_list,
    _load_yaml_map,
    _missing_input_item,
    _portable_path,
)


def build_client_import_queue(
    *,
    repo_root: Path,
    source_id: str = "nslg-client-import-queue",
    evidence_bundle_path: Path | None = None,
    client_resource_surface_gap_scan_path: Path | None = None,
    ns_bundle_format_index_path: Path | None = None,
    normalized_staging_path: Path | None = None,
    decoded_hero_audit_path: Path | None = None,
    luascripts_catalog_path: Path | None = None,
    lua_crypto_evidence_path: Path | None = None,
    luascripts_cipher_profile_path: Path | None = None,
    luascripts_variant_corpus_path: Path | None = None,
    textasset_payload_owner_trace_path: Path | None = None,
    serialized_textasset_layout_path: Path | None = None,
    serialized_textasset_resolution_path: Path | None = None,
    resolved_payload_native_anchor_scan_path: Path | None = None,
    textasset_xlua_boundary_ledger_path: Path | None = None,
    nep2_luascripts_evidence_path: Path | None = None,
    gameassembly_route_trace_path: Path | None = None,
    nep2_init_bridge_path: Path | None = None,
    native_boundary_trace_path: Path | None = None,
    runtime_init_route_path: Path | None = None,
    runtime_init_registry_probe_path: Path | None = None,
    gameassembly_codegen_module_probe_path: Path | None = None,
    gameassembly_registration_anchor_probe_path: Path | None = None,
    gameassembly_registration_layout_probe_path: Path | None = None,
    gameassembly_registration_pair_context_probe_path: Path | None = None,
    gameassembly_initializer_dispatch_trace_path: Path | None = None,
    gameassembly_function_pointer_table_probe_path: Path | None = None,
    gameassembly_metadata_registration_candidate_taxonomy_path: Path | None = None,
    gameassembly_global_metadata_owner_probe_path: Path | None = None,
    global_metadata_transform_probe_path: Path | None = None,
    global_metadata_loader_scan_path: Path | None = None,
    nep2_metadata_loader_deep_slice_path: Path | None = None,
    nep2_read_mapping_owner_scan_path: Path | None = None,
    nep2_init_data_owner_scan_path: Path | None = None,
    nep2_vector_candidate_provenance_path: Path | None = None,
    nep2_vector_wrapper_owner_probe_path: Path | None = None,
    nep2_file_helper_caller_provenance_path: Path | None = None,
    gameassembly_resolver_trace_path: Path | None = None,
    gameassembly_resolver_caller_trace_path: Path | None = None,
    generated_at: datetime | None = None,
) -> ClientImportQueue:
    repo_root = repo_root.resolve()
    generated_at = generated_at or datetime.now(timezone.utc)

    evidence_bundle_path = _input_path(repo_root, evidence_bundle_path, DEFAULT_EVIDENCE_BUNDLE)
    client_resource_surface_gap_scan_path = _input_path(
        repo_root,
        client_resource_surface_gap_scan_path,
        DEFAULT_CLIENT_RESOURCE_SURFACE_GAP_SCAN,
    )
    ns_bundle_format_index_path = _input_path(
        repo_root,
        ns_bundle_format_index_path,
        DEFAULT_NS_BUNDLE_FORMAT_INDEX,
    )
    normalized_staging_path = _input_path(
        repo_root, normalized_staging_path, DEFAULT_NORMALIZED_STAGING
    )
    decoded_hero_audit_path = _input_path(
        repo_root, decoded_hero_audit_path, DEFAULT_DECODED_HERO_AUDIT
    )
    luascripts_catalog_path = _input_path(repo_root, luascripts_catalog_path, DEFAULT_LUASCRIPTS_CATALOG)
    lua_crypto_evidence_path = _input_path(
        repo_root, lua_crypto_evidence_path, DEFAULT_LUA_CRYPTO_EVIDENCE
    )
    luascripts_cipher_profile_path = _input_path(
        repo_root, luascripts_cipher_profile_path, DEFAULT_LUASCRIPTS_CIPHER_PROFILE
    )
    luascripts_variant_corpus_path = _input_path(
        repo_root, luascripts_variant_corpus_path, DEFAULT_LUASCRIPTS_VARIANT_CORPUS
    )
    textasset_payload_owner_trace_path = _input_path(
        repo_root, textasset_payload_owner_trace_path, DEFAULT_TEXTASSET_PAYLOAD_OWNER_TRACE
    )
    serialized_textasset_layout_path = _input_path(
        repo_root, serialized_textasset_layout_path, DEFAULT_SERIALIZED_TEXTASSET_LAYOUT
    )
    serialized_textasset_resolution_path = _input_path(
        repo_root,
        serialized_textasset_resolution_path,
        DEFAULT_SERIALIZED_TEXTASSET_RESOLUTION,
    )
    resolved_payload_native_anchor_scan_path = _input_path(
        repo_root,
        resolved_payload_native_anchor_scan_path,
        DEFAULT_RESOLVED_PAYLOAD_NATIVE_ANCHOR_SCAN,
    )
    textasset_xlua_boundary_ledger_path = _input_path(
        repo_root,
        textasset_xlua_boundary_ledger_path,
        DEFAULT_TEXTASSET_XLUA_BOUNDARY_LEDGER,
    )
    nep2_luascripts_evidence_path = _input_path(
        repo_root, nep2_luascripts_evidence_path, DEFAULT_NEP2_LUASCRIPTS_EVIDENCE
    )
    gameassembly_route_trace_path = _input_path(
        repo_root, gameassembly_route_trace_path, DEFAULT_GAMEASSEMBLY_ROUTE_TRACE
    )
    nep2_init_bridge_path = _input_path(
        repo_root, nep2_init_bridge_path, DEFAULT_NEP2_INIT_BRIDGE
    )
    native_boundary_trace_path = _input_path(
        repo_root, native_boundary_trace_path, DEFAULT_NATIVE_BOUNDARY_TRACE
    )
    runtime_init_route_path = _input_path(
        repo_root, runtime_init_route_path, DEFAULT_RUNTIME_INIT_ROUTE
    )
    runtime_init_registry_probe_path = _input_path(
        repo_root,
        runtime_init_registry_probe_path,
        DEFAULT_RUNTIME_INIT_REGISTRY_PROBE,
    )
    gameassembly_codegen_module_probe_path = _input_path(
        repo_root,
        gameassembly_codegen_module_probe_path,
        DEFAULT_GAMEASSEMBLY_CODEGEN_MODULE_PROBE,
    )
    gameassembly_registration_anchor_probe_path = _input_path(
        repo_root,
        gameassembly_registration_anchor_probe_path,
        DEFAULT_GAMEASSEMBLY_REGISTRATION_ANCHOR_PROBE,
    )
    gameassembly_registration_layout_probe_path = _input_path(
        repo_root,
        gameassembly_registration_layout_probe_path,
        DEFAULT_GAMEASSEMBLY_REGISTRATION_LAYOUT_PROBE,
    )
    gameassembly_registration_pair_context_probe_path = _input_path(
        repo_root,
        gameassembly_registration_pair_context_probe_path,
        DEFAULT_GAMEASSEMBLY_REGISTRATION_PAIR_CONTEXT_PROBE,
    )
    gameassembly_initializer_dispatch_trace_path = _input_path(
        repo_root,
        gameassembly_initializer_dispatch_trace_path,
        DEFAULT_GAMEASSEMBLY_INITIALIZER_DISPATCH_TRACE,
    )
    gameassembly_function_pointer_table_probe_path = _input_path(
        repo_root,
        gameassembly_function_pointer_table_probe_path,
        DEFAULT_GAMEASSEMBLY_FUNCTION_POINTER_TABLE_PROBE,
    )
    gameassembly_metadata_registration_candidate_taxonomy_path = _input_path(
        repo_root,
        gameassembly_metadata_registration_candidate_taxonomy_path,
        DEFAULT_GAMEASSEMBLY_METADATA_REGISTRATION_CANDIDATE_TAXONOMY,
    )
    gameassembly_global_metadata_owner_probe_path = _input_path(
        repo_root,
        gameassembly_global_metadata_owner_probe_path,
        DEFAULT_GAMEASSEMBLY_GLOBAL_METADATA_OWNER_PROBE,
    )
    global_metadata_transform_probe_path = _input_path(
        repo_root,
        global_metadata_transform_probe_path,
        DEFAULT_GLOBAL_METADATA_TRANSFORM_PROBE,
    )
    global_metadata_loader_scan_path = _input_path(
        repo_root,
        global_metadata_loader_scan_path,
        DEFAULT_GLOBAL_METADATA_LOADER_SCAN,
    )
    nep2_metadata_loader_deep_slice_path = _input_path(
        repo_root,
        nep2_metadata_loader_deep_slice_path,
        DEFAULT_NEP2_METADATA_LOADER_DEEP_SLICE,
    )
    nep2_read_mapping_owner_scan_path = _input_path(
        repo_root,
        nep2_read_mapping_owner_scan_path,
        DEFAULT_NEP2_READ_MAPPING_OWNER_SCAN,
    )
    nep2_init_data_owner_scan_path = _input_path(
        repo_root,
        nep2_init_data_owner_scan_path,
        DEFAULT_NEP2_INIT_DATA_OWNER_SCAN,
    )
    nep2_vector_candidate_provenance_path = _input_path(
        repo_root,
        nep2_vector_candidate_provenance_path,
        DEFAULT_NEP2_VECTOR_CANDIDATE_PROVENANCE,
    )
    nep2_vector_wrapper_owner_probe_path = _input_path(
        repo_root,
        nep2_vector_wrapper_owner_probe_path,
        DEFAULT_NEP2_VECTOR_WRAPPER_OWNER_PROBE,
    )
    nep2_file_helper_caller_provenance_path = _input_path(
        repo_root,
        nep2_file_helper_caller_provenance_path,
        DEFAULT_NEP2_FILE_HELPER_CALLER_PROVENANCE,
    )
    gameassembly_resolver_trace_path = _input_path(
        repo_root, gameassembly_resolver_trace_path, DEFAULT_GAMEASSEMBLY_RESOLVER_TRACE
    )
    gameassembly_resolver_caller_trace_path = _input_path(
        repo_root,
        gameassembly_resolver_caller_trace_path,
        DEFAULT_GAMEASSEMBLY_RESOLVER_CALLER_TRACE,
    )

    evidence_bundle = _load_yaml_map(evidence_bundle_path)
    client_resource_surface_gap_scan = _load_yaml_map(client_resource_surface_gap_scan_path)
    ns_bundle_format_index = _load_yaml_map(ns_bundle_format_index_path)
    decoded_hero_audit = _load_yaml_map(decoded_hero_audit_path)
    normalized_staging = _load_yaml_list(normalized_staging_path)
    luascripts_catalog = _load_yaml_map(luascripts_catalog_path)
    lua_crypto_evidence = _load_yaml_map(lua_crypto_evidence_path)
    luascripts_cipher_profile = _load_yaml_map(luascripts_cipher_profile_path)
    luascripts_variant_corpus = _load_yaml_map(luascripts_variant_corpus_path)
    textasset_payload_owner_trace = _load_yaml_map(textasset_payload_owner_trace_path)
    serialized_textasset_layout = _load_yaml_map(serialized_textasset_layout_path)
    serialized_textasset_resolution = _load_yaml_map(serialized_textasset_resolution_path)
    resolved_payload_native_anchor_scan = _load_yaml_map(
        resolved_payload_native_anchor_scan_path
    )
    textasset_xlua_boundary_ledger = _load_yaml_map(textasset_xlua_boundary_ledger_path)
    nep2_luascripts_evidence = _load_yaml_map(nep2_luascripts_evidence_path)
    gameassembly_route_trace = _load_yaml_map(gameassembly_route_trace_path)
    nep2_init_bridge = _load_yaml_map(nep2_init_bridge_path)
    native_boundary_trace = _load_yaml_map(native_boundary_trace_path)
    runtime_init_route = _load_yaml_map(runtime_init_route_path)
    runtime_init_registry_probe = _load_yaml_map(runtime_init_registry_probe_path)
    gameassembly_codegen_module_probe = _load_yaml_map(gameassembly_codegen_module_probe_path)
    gameassembly_registration_anchor_probe = _load_yaml_map(
        gameassembly_registration_anchor_probe_path
    )
    gameassembly_registration_layout_probe = _load_yaml_map(
        gameassembly_registration_layout_probe_path
    )
    gameassembly_registration_pair_context_probe = _load_yaml_map(
        gameassembly_registration_pair_context_probe_path
    )
    gameassembly_initializer_dispatch_trace = _load_yaml_map(
        gameassembly_initializer_dispatch_trace_path
    )
    gameassembly_function_pointer_table_probe = _load_yaml_map(
        gameassembly_function_pointer_table_probe_path
    )
    gameassembly_metadata_registration_candidate_taxonomy = _load_yaml_map(
        gameassembly_metadata_registration_candidate_taxonomy_path
    )
    gameassembly_global_metadata_owner_probe = _load_yaml_map(
        gameassembly_global_metadata_owner_probe_path
    )
    global_metadata_transform_probe = _load_yaml_map(global_metadata_transform_probe_path)
    global_metadata_loader_scan = _load_yaml_map(global_metadata_loader_scan_path)
    nep2_metadata_loader_deep_slice = _load_yaml_map(nep2_metadata_loader_deep_slice_path)
    nep2_read_mapping_owner_scan = _load_yaml_map(nep2_read_mapping_owner_scan_path)
    nep2_init_data_owner_scan = _load_yaml_map(nep2_init_data_owner_scan_path)
    nep2_vector_candidate_provenance = _load_yaml_map(
        nep2_vector_candidate_provenance_path
    )
    nep2_vector_wrapper_owner_probe = _load_yaml_map(
        nep2_vector_wrapper_owner_probe_path
    )
    nep2_file_helper_caller_provenance = _load_yaml_map(
        nep2_file_helper_caller_provenance_path
    )
    gameassembly_resolver_trace = _load_yaml_map(gameassembly_resolver_trace_path)
    gameassembly_resolver_caller_trace = _load_yaml_map(gameassembly_resolver_caller_trace_path)

    items: list[ClientImportQueueItem] = []
    items.extend(
        _client_resource_surface_gap_scan_items(
            client_resource_surface_gap_scan,
            source_artifact=_portable_path(client_resource_surface_gap_scan_path, repo_root),
        )
    )
    items.extend(
        _ns_bundle_format_index_items(
            ns_bundle_format_index,
            source_artifact=_portable_path(ns_bundle_format_index_path, repo_root),
        )
    )
    items.extend(
        _decoded_hero_review_items(
            normalized_staging,
            decoded_hero_audit,
            source_artifact=_portable_path(normalized_staging_path, repo_root),
        )
    )
    items.extend(
        _luascripts_decoder_items(
            luascripts_catalog,
            source_artifact=_portable_path(luascripts_catalog_path, repo_root),
        )
    )
    items.extend(
        _lua_crypto_decoder_items(
            lua_crypto_evidence,
            source_artifact=_portable_path(lua_crypto_evidence_path, repo_root),
        )
    )
    items.extend(
        _luascripts_cipher_profile_items(
            luascripts_cipher_profile,
            source_artifact=_portable_path(luascripts_cipher_profile_path, repo_root),
            resolved_by_variant_corpus=luascripts_variant_corpus,
        )
    )
    items.extend(
        _luascripts_variant_corpus_items(
            luascripts_variant_corpus,
            source_artifact=_portable_path(luascripts_variant_corpus_path, repo_root),
        )
    )
    items.extend(
        _textasset_payload_owner_trace_items(
            textasset_payload_owner_trace,
            source_artifact=_portable_path(textasset_payload_owner_trace_path, repo_root),
            resolved_by_serialized_layout=serialized_textasset_layout,
        )
    )
    items.extend(
        _serialized_textasset_layout_items(
            serialized_textasset_layout,
            source_artifact=_portable_path(serialized_textasset_layout_path, repo_root),
            resolved_by_path_resolution=serialized_textasset_resolution,
        )
    )
    items.extend(
        _serialized_textasset_resolution_items(
            serialized_textasset_resolution,
            source_artifact=_portable_path(serialized_textasset_resolution_path, repo_root),
            resolved_by_native_anchor_scan=resolved_payload_native_anchor_scan,
        )
    )
    items.extend(
        _resolved_payload_native_anchor_scan_items(
            resolved_payload_native_anchor_scan,
            source_artifact=_portable_path(resolved_payload_native_anchor_scan_path, repo_root),
            resolved_by_boundary_ledger=textasset_xlua_boundary_ledger,
        )
    )
    items.extend(
        _textasset_xlua_boundary_ledger_items(
            textasset_xlua_boundary_ledger,
            source_artifact=_portable_path(textasset_xlua_boundary_ledger_path, repo_root),
        )
    )
    items.extend(
        _nep2_static_trace_items(
            nep2_luascripts_evidence,
            source_artifact=_portable_path(nep2_luascripts_evidence_path, repo_root),
        )
    )
    items.extend(
        _gameassembly_static_trace_items(
            gameassembly_route_trace,
            source_artifact=_portable_path(gameassembly_route_trace_path, repo_root),
        )
    )
    items.extend(
        _nep2_init_bridge_trace_items(
            nep2_init_bridge,
            source_artifact=_portable_path(nep2_init_bridge_path, repo_root),
        )
    )
    items.extend(
        _native_boundary_trace_items(
            native_boundary_trace,
            source_artifact=_portable_path(native_boundary_trace_path, repo_root),
        )
    )
    items.extend(
        _runtime_init_route_items(
            runtime_init_route,
            source_artifact=_portable_path(runtime_init_route_path, repo_root),
            resolved_by_registry_probe=runtime_init_registry_probe,
        )
    )
    items.extend(
        _runtime_init_registry_probe_items(
            runtime_init_registry_probe,
            source_artifact=_portable_path(runtime_init_registry_probe_path, repo_root),
            resolved_by_codegen_module_probe=gameassembly_codegen_module_probe,
        )
    )
    items.extend(
        _gameassembly_codegen_module_probe_items(
            gameassembly_codegen_module_probe,
            source_artifact=_portable_path(gameassembly_codegen_module_probe_path, repo_root),
            resolved_by_registration_anchor_probe=gameassembly_registration_anchor_probe,
        )
    )
    items.extend(
        _gameassembly_registration_anchor_probe_items(
            gameassembly_registration_anchor_probe,
            source_artifact=_portable_path(
                gameassembly_registration_anchor_probe_path,
                repo_root,
            ),
            resolved_by_registration_layout_probe=gameassembly_registration_layout_probe,
        )
    )
    items.extend(
        _gameassembly_registration_layout_probe_items(
            gameassembly_registration_layout_probe,
            source_artifact=_portable_path(
                gameassembly_registration_layout_probe_path,
                repo_root,
            ),
            resolved_by_registration_pair_context_probe=gameassembly_registration_pair_context_probe,
        )
    )
    items.extend(
        _gameassembly_registration_pair_context_probe_items(
            gameassembly_registration_pair_context_probe,
            source_artifact=_portable_path(
                gameassembly_registration_pair_context_probe_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _gameassembly_initializer_dispatch_trace_items(
            gameassembly_initializer_dispatch_trace,
            source_artifact=_portable_path(
                gameassembly_initializer_dispatch_trace_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _gameassembly_function_pointer_table_probe_items(
            gameassembly_function_pointer_table_probe,
            source_artifact=_portable_path(
                gameassembly_function_pointer_table_probe_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _gameassembly_metadata_registration_candidate_taxonomy_items(
            gameassembly_metadata_registration_candidate_taxonomy,
            source_artifact=_portable_path(
                gameassembly_metadata_registration_candidate_taxonomy_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _gameassembly_global_metadata_owner_probe_items(
            gameassembly_global_metadata_owner_probe,
            source_artifact=_portable_path(
                gameassembly_global_metadata_owner_probe_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _global_metadata_transform_probe_items(
            global_metadata_transform_probe,
            source_artifact=_portable_path(global_metadata_transform_probe_path, repo_root),
        )
    )
    items.extend(
        _global_metadata_loader_scan_items(
            global_metadata_loader_scan,
            source_artifact=_portable_path(global_metadata_loader_scan_path, repo_root),
            resolved_by_deep_slice=nep2_metadata_loader_deep_slice,
        )
    )
    items.extend(
        _nep2_metadata_loader_deep_slice_items(
            nep2_metadata_loader_deep_slice,
            source_artifact=_portable_path(nep2_metadata_loader_deep_slice_path, repo_root),
            resolved_by_read_mapping_scan=nep2_read_mapping_owner_scan,
        )
    )
    items.extend(
        _nep2_read_mapping_owner_scan_items(
            nep2_read_mapping_owner_scan,
            source_artifact=_portable_path(nep2_read_mapping_owner_scan_path, repo_root),
            resolved_by_init_data_owner_scan=nep2_init_data_owner_scan,
        )
    )
    items.extend(
        _nep2_init_data_owner_scan_items(
            nep2_init_data_owner_scan,
            source_artifact=_portable_path(nep2_init_data_owner_scan_path, repo_root),
        )
    )
    items.extend(
        _nep2_vector_candidate_provenance_items(
            nep2_vector_candidate_provenance,
            source_artifact=_portable_path(
                nep2_vector_candidate_provenance_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _nep2_vector_wrapper_owner_probe_items(
            nep2_vector_wrapper_owner_probe,
            source_artifact=_portable_path(
                nep2_vector_wrapper_owner_probe_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _nep2_file_helper_caller_provenance_items(
            nep2_file_helper_caller_provenance,
            source_artifact=_portable_path(
                nep2_file_helper_caller_provenance_path,
                repo_root,
            ),
        )
    )
    items.extend(
        _gameassembly_resolver_trace_items(
            gameassembly_resolver_trace,
            source_artifact=_portable_path(gameassembly_resolver_trace_path, repo_root),
        )
    )
    items.extend(
        _gameassembly_resolver_caller_trace_items(
            gameassembly_resolver_caller_trace,
            source_artifact=_portable_path(gameassembly_resolver_caller_trace_path, repo_root),
        )
    )

    for path, data, queue_type in [
        (evidence_bundle_path, evidence_bundle, "missing_evidence_bundle"),
        (
            client_resource_surface_gap_scan_path,
            client_resource_surface_gap_scan,
            "missing_client_resource_surface_gap_scan",
        ),
        (
            ns_bundle_format_index_path,
            ns_bundle_format_index,
            "missing_ns_bundle_format_index",
        ),
        (decoded_hero_audit_path, decoded_hero_audit, "missing_decoded_hero_audit"),
        (normalized_staging_path, normalized_staging, "missing_normalized_staging"),
        (luascripts_catalog_path, luascripts_catalog, "missing_luascripts_catalog"),
        (lua_crypto_evidence_path, lua_crypto_evidence, "missing_lua_crypto_evidence"),
        (
            luascripts_cipher_profile_path,
            luascripts_cipher_profile,
            "missing_luascripts_cipher_profile",
        ),
        (
            luascripts_variant_corpus_path,
            luascripts_variant_corpus,
            "missing_luascripts_variant_corpus",
        ),
        (
            textasset_payload_owner_trace_path,
            textasset_payload_owner_trace,
            "missing_textasset_payload_owner_trace",
        ),
        (
            serialized_textasset_layout_path,
            serialized_textasset_layout,
            "missing_serialized_textasset_layout",
        ),
        (
            serialized_textasset_resolution_path,
            serialized_textasset_resolution,
            "missing_serialized_textasset_resolution",
        ),
        (
            resolved_payload_native_anchor_scan_path,
            resolved_payload_native_anchor_scan,
            "missing_resolved_payload_native_anchor_scan",
        ),
        (
            textasset_xlua_boundary_ledger_path,
            textasset_xlua_boundary_ledger,
            "missing_textasset_xlua_boundary_ledger",
        ),
        (nep2_luascripts_evidence_path, nep2_luascripts_evidence, "missing_nep2_evidence"),
        (gameassembly_route_trace_path, gameassembly_route_trace, "missing_gameassembly_trace"),
        (nep2_init_bridge_path, nep2_init_bridge, "missing_nep2_init_bridge"),
        (native_boundary_trace_path, native_boundary_trace, "missing_native_boundary_trace"),
        (runtime_init_route_path, runtime_init_route, "missing_runtime_init_route"),
        (
            runtime_init_registry_probe_path,
            runtime_init_registry_probe,
            "missing_runtime_init_registry_probe",
        ),
        (
            gameassembly_codegen_module_probe_path,
            gameassembly_codegen_module_probe,
            "missing_gameassembly_codegen_module_probe",
        ),
        (
            gameassembly_registration_anchor_probe_path,
            gameassembly_registration_anchor_probe,
            "missing_gameassembly_registration_anchor_probe",
        ),
        (
            gameassembly_registration_layout_probe_path,
            gameassembly_registration_layout_probe,
            "missing_gameassembly_registration_layout_probe",
        ),
        (
            gameassembly_registration_pair_context_probe_path,
            gameassembly_registration_pair_context_probe,
            "missing_gameassembly_registration_pair_context_probe",
        ),
        (
            gameassembly_initializer_dispatch_trace_path,
            gameassembly_initializer_dispatch_trace,
            "missing_gameassembly_initializer_dispatch_trace",
        ),
        (
            gameassembly_function_pointer_table_probe_path,
            gameassembly_function_pointer_table_probe,
            "missing_gameassembly_function_pointer_table_probe",
        ),
        (
            gameassembly_metadata_registration_candidate_taxonomy_path,
            gameassembly_metadata_registration_candidate_taxonomy,
            "missing_gameassembly_metadata_registration_candidate_taxonomy",
        ),
        (
            global_metadata_transform_probe_path,
            global_metadata_transform_probe,
            "missing_global_metadata_transform_probe",
        ),
        (
            global_metadata_loader_scan_path,
            global_metadata_loader_scan,
            "missing_global_metadata_loader_scan",
        ),
        (
            nep2_metadata_loader_deep_slice_path,
            nep2_metadata_loader_deep_slice,
            "missing_nep2_metadata_loader_deep_slice",
        ),
        (
            nep2_read_mapping_owner_scan_path,
            nep2_read_mapping_owner_scan,
            "missing_nep2_read_mapping_owner_scan",
        ),
        (
            nep2_init_data_owner_scan_path,
            nep2_init_data_owner_scan,
            "missing_nep2_init_data_owner_scan",
        ),
        (
            nep2_vector_candidate_provenance_path,
            nep2_vector_candidate_provenance,
            "missing_nep2_vector_candidate_provenance",
        ),
        (
            nep2_vector_wrapper_owner_probe_path,
            nep2_vector_wrapper_owner_probe,
            "missing_nep2_vector_wrapper_owner_probe",
        ),
        (
            nep2_file_helper_caller_provenance_path,
            nep2_file_helper_caller_provenance,
            "missing_nep2_file_helper_caller_provenance",
        ),
        (
            gameassembly_resolver_trace_path,
            gameassembly_resolver_trace,
            "missing_gameassembly_resolver_trace",
        ),
        (
            gameassembly_resolver_caller_trace_path,
            gameassembly_resolver_caller_trace,
            "missing_gameassembly_resolver_caller_trace",
        ),
    ]:
        if not path.exists() or not data:
            items.append(_missing_input_item(path, repo_root, queue_type=queue_type))

    items = sorted(items, key=lambda item: (-item.priority, item.queue_type, item.queue_id))
    queue_type_counts = Counter(item.queue_type for item in items)
    readiness_counts = Counter(item.readiness for item in items)
    domain_counts = Counter(item.domain for item in items)
    publish_readiness = _build_publish_readiness(items, evidence_bundle)

    return ClientImportQueue(
        source_id=source_id,
        generated_at=generated_at,
        client_version=_client_version(evidence_bundle),
        queue_item_count=len(items),
        queue_type_counts=dict(sorted(queue_type_counts.items())),
        readiness_counts=dict(sorted(readiness_counts.items())),
        domain_counts=dict(sorted(domain_counts.items())),
        publish_readiness=publish_readiness,
        items=items,
        guardrails=[
            "offline/static evidence only; no account credentials, tokens, online protocol, or live instrumentation data is included",
            "the import queue is planning material, not a publish command",
            "normalized decoded hero entries require manual review before knowledge_sources promotion",
            "LuaScripts, Lua crypto, and NEP2 items remain decoder/static-trace targets until readable payloads are recovered",
            "all source_artifact values are repo-relative and sanitized",
        ],
    )


def write_client_import_queue(queue: ClientImportQueue, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(queue.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )
