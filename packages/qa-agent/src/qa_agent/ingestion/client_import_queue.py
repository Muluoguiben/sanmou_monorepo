from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
import re
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.client_import_queue.v1"

DEFAULT_EVIDENCE_BUNDLE = Path(
    "ingestion/raw/client_packages/nslg-client-evidence-bundle-round137.yaml"
)
DEFAULT_CLIENT_RESOURCE_SURFACE_GAP_SCAN = Path(
    "ingestion/raw/client_packages/nslg-client-resource-surface-gap-scan-round133.yaml"
)
DEFAULT_NS_BUNDLE_FORMAT_INDEX = Path(
    "ingestion/raw/client_packages/nslg-ns-bundle-format-index-round136.yaml"
)
DEFAULT_NORMALIZED_STAGING = Path(
    "ingestion/staging/client_decoded/nslg-hero-readable-export-round29-normalized.yaml"
)
DEFAULT_DECODED_HERO_AUDIT = Path(
    "ingestion/staging/client_decoded/nslg-hero-readable-export-round29-audit.yaml"
)
DEFAULT_LUASCRIPTS_CATALOG = Path(
    "ingestion/raw/client_packages/nslg-luascripts-textassets-round31-catalog.yaml"
)
DEFAULT_LUA_CRYPTO_EVIDENCE = Path(
    "ingestion/raw/client_packages/nslg-luascripts-crypto-evidence-round32.yaml"
)
DEFAULT_LUASCRIPTS_CIPHER_PROFILE = Path(
    "ingestion/raw/client_packages/nslg-luascripts-payload-cipher-profile-round49.yaml"
)
DEFAULT_LUASCRIPTS_VARIANT_CORPUS = Path(
    "ingestion/raw/client_packages/nslg-luascripts-payload-variant-corpus-round79.yaml"
)
DEFAULT_TEXTASSET_PAYLOAD_OWNER_TRACE = Path(
    "ingestion/raw/client_packages/nslg-textasset-payload-owner-trace-round82.yaml"
)
DEFAULT_SERIALIZED_TEXTASSET_LAYOUT = Path(
    "ingestion/raw/client_packages/nslg-serialized-textasset-layout-round85.yaml"
)
DEFAULT_SERIALIZED_TEXTASSET_RESOLUTION = Path(
    "ingestion/raw/client_packages/nslg-serialized-textasset-path-resolution-round88.yaml"
)
DEFAULT_RESOLVED_PAYLOAD_NATIVE_ANCHOR_SCAN = Path(
    "ingestion/raw/client_packages/nslg-resolved-payload-native-anchor-scan-round91.yaml"
)
DEFAULT_TEXTASSET_XLUA_BOUNDARY_LEDGER = Path(
    "ingestion/raw/client_packages/nslg-textasset-xlua-boundary-ledger-round94.yaml"
)
DEFAULT_NEP2_LUASCRIPTS_EVIDENCE = Path(
    "ingestion/raw/client_packages/nslg-nep2-luascripts-evidence-round34.yaml"
)
DEFAULT_GAMEASSEMBLY_ROUTE_TRACE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-route-trace-round43.yaml"
)
DEFAULT_NEP2_INIT_BRIDGE = Path(
    "ingestion/raw/client_packages/nslg-nep2-init-bridge-round46.yaml"
)
DEFAULT_NATIVE_BOUNDARY_TRACE = Path(
    "ingestion/raw/client_packages/nslg-native-loadbuffer-boundary-round52.yaml"
)
DEFAULT_RUNTIME_INIT_ROUTE = Path(
    "ingestion/raw/client_packages/nslg-runtime-init-metadata-route-round55.yaml"
)
DEFAULT_RUNTIME_INIT_REGISTRY_PROBE = Path(
    "ingestion/raw/client_packages/nslg-runtime-init-registry-probe-round97.yaml"
)
DEFAULT_GAMEASSEMBLY_CODEGEN_MODULE_PROBE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-codegen-module-probe-round100.yaml"
)
DEFAULT_GAMEASSEMBLY_REGISTRATION_ANCHOR_PROBE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-registration-anchor-probe-round103.yaml"
)
DEFAULT_GAMEASSEMBLY_REGISTRATION_LAYOUT_PROBE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-registration-layout-probe-round106.yaml"
)
DEFAULT_GAMEASSEMBLY_REGISTRATION_PAIR_CONTEXT_PROBE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-registration-pair-context-probe-round109.yaml"
)
DEFAULT_GAMEASSEMBLY_INITIALIZER_DISPATCH_TRACE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-initializer-dispatch-trace-round112.yaml"
)
DEFAULT_GAMEASSEMBLY_FUNCTION_POINTER_TABLE_PROBE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-function-pointer-table-probe-round115.yaml"
)
DEFAULT_GAMEASSEMBLY_METADATA_REGISTRATION_CANDIDATE_TAXONOMY = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-metadata-registration-candidate-taxonomy-round118.yaml"
)
DEFAULT_GAMEASSEMBLY_GLOBAL_METADATA_OWNER_PROBE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-global-metadata-owner-probe-round127.yaml"
)
DEFAULT_GLOBAL_METADATA_TRANSFORM_PROBE = Path(
    "ingestion/raw/client_packages/nslg-global-metadata-transform-probe-round64.yaml"
)
DEFAULT_GLOBAL_METADATA_LOADER_SCAN = Path(
    "ingestion/raw/client_packages/nslg-global-metadata-loader-scan-round67.yaml"
)
DEFAULT_NEP2_METADATA_LOADER_DEEP_SLICE = Path(
    "ingestion/raw/client_packages/nslg-nep2-global-metadata-loader-deep-slice-round70.yaml"
)
DEFAULT_NEP2_READ_MAPPING_OWNER_SCAN = Path(
    "ingestion/raw/client_packages/nslg-nep2-read-mapping-owner-scan-round73.yaml"
)
DEFAULT_NEP2_INIT_DATA_OWNER_SCAN = Path(
    "ingestion/raw/client_packages/nslg-nep2-init-data-owner-scan-round76.yaml"
)
DEFAULT_NEP2_VECTOR_CANDIDATE_PROVENANCE = Path(
    "ingestion/raw/client_packages/nslg-nep2-vector-candidate-provenance-round121.yaml"
)
DEFAULT_NEP2_VECTOR_WRAPPER_OWNER_PROBE = Path(
    "ingestion/raw/client_packages/nslg-nep2-vector-wrapper-owner-probe-round130.yaml"
)
DEFAULT_NEP2_FILE_HELPER_CALLER_PROVENANCE = Path(
    "ingestion/raw/client_packages/nslg-nep2-file-helper-caller-provenance-round124.yaml"
)
DEFAULT_GAMEASSEMBLY_RESOLVER_TRACE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-resolver-trace-round58.yaml"
)
DEFAULT_GAMEASSEMBLY_RESOLVER_CALLER_TRACE = Path(
    "ingestion/raw/client_packages/nslg-gameassembly-resolver-caller-trace-round61.yaml"
)

_HERO_ID_RE = re.compile(r"heroID=(\d+)")
_CLIENT_HERO_ID_RE = re.compile(r"client_hero_id=(\d+)")
_SKILL_ID_RE = re.compile(r"skillId=(\d+)")


class ClientImportQueueItem(BaseModel):
    queue_id: str = Field(min_length=1)
    queue_type: str = Field(min_length=1)
    priority: int = Field(default=0)
    readiness: str = Field(min_length=1)
    domain: str = Field(min_length=1)
    topic: str = Field(min_length=1)
    source_artifact: str = Field(min_length=1)
    source_ref: str | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ClientImportQueue(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    generated_at: datetime
    source_type: str = "nslg_client_import_queue"
    client_version: dict[str, Any] = Field(default_factory=dict)
    queue_item_count: int = 0
    queue_type_counts: dict[str, int] = Field(default_factory=dict)
    readiness_counts: dict[str, int] = Field(default_factory=dict)
    domain_counts: dict[str, int] = Field(default_factory=dict)
    publish_readiness: dict[str, Any] = Field(default_factory=dict)
    items: list[ClientImportQueueItem] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


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


def _missing_input_item(path: Path, repo_root: Path, *, queue_type: str) -> ClientImportQueueItem:
    portable = _portable_path(path, repo_root)
    return ClientImportQueueItem(
        queue_id=f"missing-input-{_slug(portable)}",
        queue_type=queue_type,
        priority=10,
        readiness="blocked_missing_artifact",
        domain="evidence_inventory",
        topic=portable,
        source_artifact=portable,
        blockers=[f"expected client evidence artifact is missing: {portable}"],
        next_actions=["rebuild the missing offline client evidence artifact"],
        counts={"blocker_count": 1},
    )


def _build_publish_readiness(
    items: list[ClientImportQueueItem],
    evidence_bundle: dict[str, Any],
) -> dict[str, Any]:
    import_readiness = evidence_bundle.get("import_readiness") or {}
    publishable_now = [
        item for item in items if item.readiness in {"reviewed_import_candidate", "ready_for_import"}
    ]
    return {
        "safe_for_publish": False,
        "auto_publish_allowed": False,
        "publishable_now_count": len(publishable_now),
        "queue_blocker_count": sum(len(item.blockers) for item in items),
        "upstream_bundle_safe_for_publish": bool(import_readiness.get("safe_for_publish")),
        "reason": (
            "client import queue is a review and decoder planning artifact; no entry is promoted automatically"
        ),
    }


def _build_decoded_audit_index(audit: dict[str, Any]) -> dict[str, Any]:
    hero_coverage = audit.get("hero_coverage") or {}
    skill_coverage = audit.get("skill_coverage") or {}
    return {
        "unmapped_hero_ids": {
            int(item.get("hero_id"))
            for item in hero_coverage.get("unmapped_heroes") or []
            if isinstance(item, dict) and isinstance(item.get("hero_id"), int)
        },
        "low_confidence_heroes": {
            int(item.get("hero_id")): item
            for item in hero_coverage.get("low_confidence_mappings") or []
            if isinstance(item, dict) and isinstance(item.get("hero_id"), int)
        },
        "unmapped_skill_ids": {
            int(item)
            for item in skill_coverage.get("unmapped_skill_ids") or []
            if isinstance(item, int)
        },
        "low_confidence_skills": {
            int(item.get("skill_id")): item
            for item in skill_coverage.get("low_confidence_mappings") or []
            if isinstance(item, dict) and isinstance(item.get("skill_id"), int)
        },
    }


def _decoded_hero_priority(
    *,
    confidence: float,
    review_status: str,
    has_unmapped_hero: bool,
    unmapped_skill_count: int,
    low_confidence_mapping_count: int,
) -> int:
    priority = 78
    if confidence >= 0.9:
        priority += 6
    elif confidence < 0.75:
        priority -= 8
    if review_status != "reviewed":
        priority -= 4
    if has_unmapped_hero:
        priority -= 18
    priority -= min(unmapped_skill_count, 4) * 3
    priority -= min(low_confidence_mapping_count, 3) * 4
    return max(priority, 20)


def _luascript_priority(*, stem: str, domains: list[str], record_count: int) -> int:
    domain_scores = {
        "hero": 92,
        "skill": 90,
        "combat": 86,
        "building": 84,
        "map": 82,
        "chapter_task": 80,
        "story_plot": 76,
        "season": 74,
        "economy_item": 68,
        "system_text": 64,
        "unknown": 40,
    }
    priority = max((domain_scores.get(domain, 50) for domain in domains), default=40)
    if stem in {"heros", "skills", "warbook", "custom_hero"}:
        priority += 5
    return min(priority + min(record_count, 8), 99)


def _lua_crypto_priority(target: str) -> int:
    text = target.lower()
    if "xlual_loadbuffer" in text or "textasset::get_bytes" in text:
        return 98
    if "metadata" in text:
        return 95
    if "16-byte" in text or "block transform" in text:
        return 92
    return 88


def _nep2_priority(target: str) -> int:
    text = target.lower()
    if "initluascriptsscan" in text:
        return 99
    if "lua" in text and "loadbuffer" in text:
        return 96
    if "0x180021240" in text or "string-decode" in text:
        return 90
    return 86


def _primary_domain(domains: list[str]) -> str:
    order = [
        "hero",
        "skill",
        "combat",
        "building",
        "map",
        "chapter_task",
        "story_plot",
        "season",
    ]
    for domain in order:
        if domain in domains:
            return domain
    return domains[0] if domains else "unknown"


def _hero_id_from_entry(entry: dict[str, Any]) -> int | None:
    source_ref = str(entry.get("source_ref") or "")
    match = _HERO_ID_RE.search(source_ref)
    if match:
        return int(match.group(1))
    structured = entry.get("structured_data") if isinstance(entry.get("structured_data"), dict) else {}
    for note in _str_list(structured.get("notes")):
        match = _CLIENT_HERO_ID_RE.search(note)
        if match:
            return int(match.group(1))
    entry_id = str(entry.get("id") or "")
    tail = entry_id.rsplit("-", 1)[-1]
    return int(tail) if tail.isdigit() else None


def _skill_ids_from_entry(entry: dict[str, Any]) -> set[int]:
    ids: set[int] = set()
    structured = entry.get("structured_data") if isinstance(entry.get("structured_data"), dict) else {}
    for note in _str_list(structured.get("notes")):
        ids.update(int(match.group(1)) for match in _SKILL_ID_RE.finditer(note))
    for topic in _str_list(entry.get("related_topics")):
        if topic.isdigit():
            ids.add(int(topic))
    return ids


def _client_version(bundle: dict[str, Any]) -> dict[str, Any]:
    version = bundle.get("client_version")
    return version if isinstance(version, dict) else {}


def _input_path(repo_root: Path, path: Path | None, default: Path) -> Path:
    selected = path or default
    return selected if selected.is_absolute() else repo_root / selected


def _load_yaml_map(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _load_yaml_list(path: Path) -> list[Any]:
    if not path.exists():
        return []
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def _portable_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.name


def _str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if item is not None and str(item)]


def _float_value(value: Any) -> float:
    if isinstance(value, int | float):
        return float(value)
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return 0.0


def _csv_ints(values: list[int]) -> str:
    return ", ".join(str(value) for value in values)


def _slug(value: str) -> str:
    slug = re.sub(r"[^0-9A-Za-z]+", "-", value).strip("-").lower()
    return slug or "item"


def _unique_strs(values: list[str]) -> list[str]:
    return list(dict.fromkeys(value for value in values if value))


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(raw or 0) for key, raw in value.items()}


def _prefixed_counts(prefix: str, counts: Counter[str]) -> dict[str, int]:
    return {f"{prefix}:{key}": int(value) for key, value in sorted(counts.items())}
