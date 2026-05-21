from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field


SCHEMA_VERSION = "nslg.client_evidence_bundle.v1"


DEFAULT_PACKAGE_MANIFEST = Path("ingestion/raw/client_packages/nslg-pc-1.29.0-manifest.yaml")
DEFAULT_CLIENT_RESOURCE_SURFACE_GAP_SCAN = Path(
    "ingestion/raw/client_packages/nslg-client-resource-surface-gap-scan-round133.yaml"
)
DEFAULT_NS_BUNDLE_FORMAT_INDEX = Path(
    "ingestion/raw/client_packages/nslg-ns-bundle-format-index-round136.yaml"
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
DEFAULT_NEP2_PROVENANCE_CLOSURES = Path(
    "ingestion/raw/client_packages/nslg-nep2-provenance-closures-round40.yaml"
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
DEFAULT_DECODED_HERO_AUDIT = Path(
    "ingestion/staging/client_decoded/nslg-hero-readable-export-round29-audit.yaml"
)


class ClientEvidenceArtifact(BaseModel):
    artifact_id: str = Field(min_length=1)
    artifact_type: str = Field(min_length=1)
    path: str = Field(min_length=1)
    source_id: str | None = None
    source_site: str | None = None
    source_url: str | None = None
    status: str = Field(min_length=1)
    publish_readiness: str = Field(min_length=1)
    knowledge_domains: list[str] = Field(default_factory=list)
    counts: dict[str, int] = Field(default_factory=dict)
    version_info: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: list[str] = Field(default_factory=list)
    blockers: list[str] = Field(default_factory=list)
    next_actions: list[str] = Field(default_factory=list)


class ClientEvidenceBundle(BaseModel):
    schema_version: str = SCHEMA_VERSION
    source_id: str = Field(min_length=1)
    generated_at: datetime
    source_type: str = "nslg_client_offline_evidence_bundle"
    client_version: dict[str, Any] = Field(default_factory=dict)
    artifact_count: int = 0
    artifact_status_counts: dict[str, int] = Field(default_factory=dict)
    knowledge_domain_counts: dict[str, int] = Field(default_factory=dict)
    evidence_ref_count: int = 0
    import_readiness: dict[str, Any] = Field(default_factory=dict)
    artifacts: list[ClientEvidenceArtifact] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


def build_client_evidence_bundle(
    *,
    repo_root: Path,
    source_id: str = "nslg-client-offline-bundle",
    package_manifest_path: Path | None = None,
    client_resource_surface_gap_scan_path: Path | None = None,
    ns_bundle_format_index_path: Path | None = None,
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
    nep2_provenance_closures_path: Path | None = None,
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
    decoded_hero_audit_path: Path | None = None,
    generated_at: datetime | None = None,
) -> ClientEvidenceBundle:
    repo_root = repo_root.resolve()
    generated_at = generated_at or datetime.now(timezone.utc)
    path_specs = [
        (
            package_manifest_path or repo_root / DEFAULT_PACKAGE_MANIFEST,
            _package_manifest_artifact,
        ),
        (
            client_resource_surface_gap_scan_path
            or repo_root / DEFAULT_CLIENT_RESOURCE_SURFACE_GAP_SCAN,
            _client_resource_surface_gap_scan_artifact,
        ),
        (
            ns_bundle_format_index_path or repo_root / DEFAULT_NS_BUNDLE_FORMAT_INDEX,
            _ns_bundle_format_index_artifact,
        ),
        (
            luascripts_catalog_path or repo_root / DEFAULT_LUASCRIPTS_CATALOG,
            _luascripts_catalog_artifact,
        ),
        (
            lua_crypto_evidence_path or repo_root / DEFAULT_LUA_CRYPTO_EVIDENCE,
            _lua_crypto_artifact,
        ),
        (
            luascripts_cipher_profile_path or repo_root / DEFAULT_LUASCRIPTS_CIPHER_PROFILE,
            _luascripts_cipher_profile_artifact,
        ),
        (
            luascripts_variant_corpus_path or repo_root / DEFAULT_LUASCRIPTS_VARIANT_CORPUS,
            _luascripts_variant_corpus_artifact,
        ),
        (
            textasset_payload_owner_trace_path
            or repo_root / DEFAULT_TEXTASSET_PAYLOAD_OWNER_TRACE,
            _textasset_payload_owner_trace_artifact,
        ),
        (
            serialized_textasset_layout_path
            or repo_root / DEFAULT_SERIALIZED_TEXTASSET_LAYOUT,
            _serialized_textasset_layout_artifact,
        ),
        (
            serialized_textasset_resolution_path
            or repo_root / DEFAULT_SERIALIZED_TEXTASSET_RESOLUTION,
            _serialized_textasset_resolution_artifact,
        ),
        (
            resolved_payload_native_anchor_scan_path
            or repo_root / DEFAULT_RESOLVED_PAYLOAD_NATIVE_ANCHOR_SCAN,
            _resolved_payload_native_anchor_scan_artifact,
        ),
        (
            textasset_xlua_boundary_ledger_path
            or repo_root / DEFAULT_TEXTASSET_XLUA_BOUNDARY_LEDGER,
            _textasset_xlua_boundary_ledger_artifact,
        ),
        (
            nep2_luascripts_evidence_path or repo_root / DEFAULT_NEP2_LUASCRIPTS_EVIDENCE,
            _nep2_artifact,
        ),
        (
            nep2_provenance_closures_path or repo_root / DEFAULT_NEP2_PROVENANCE_CLOSURES,
            _nep2_provenance_artifact,
        ),
        (
            gameassembly_route_trace_path or repo_root / DEFAULT_GAMEASSEMBLY_ROUTE_TRACE,
            _gameassembly_route_trace_artifact,
        ),
        (
            nep2_init_bridge_path or repo_root / DEFAULT_NEP2_INIT_BRIDGE,
            _nep2_init_bridge_artifact,
        ),
        (
            native_boundary_trace_path or repo_root / DEFAULT_NATIVE_BOUNDARY_TRACE,
            _native_boundary_trace_artifact,
        ),
        (
            runtime_init_route_path or repo_root / DEFAULT_RUNTIME_INIT_ROUTE,
            _runtime_init_route_artifact,
        ),
        (
            runtime_init_registry_probe_path
            or repo_root / DEFAULT_RUNTIME_INIT_REGISTRY_PROBE,
            _runtime_init_registry_probe_artifact,
        ),
        (
            gameassembly_codegen_module_probe_path
            or repo_root / DEFAULT_GAMEASSEMBLY_CODEGEN_MODULE_PROBE,
            _gameassembly_codegen_module_probe_artifact,
        ),
        (
            gameassembly_registration_anchor_probe_path
            or repo_root / DEFAULT_GAMEASSEMBLY_REGISTRATION_ANCHOR_PROBE,
            _gameassembly_registration_anchor_probe_artifact,
        ),
        (
            gameassembly_registration_layout_probe_path
            or repo_root / DEFAULT_GAMEASSEMBLY_REGISTRATION_LAYOUT_PROBE,
            _gameassembly_registration_layout_probe_artifact,
        ),
        (
            gameassembly_registration_pair_context_probe_path
            or repo_root / DEFAULT_GAMEASSEMBLY_REGISTRATION_PAIR_CONTEXT_PROBE,
            _gameassembly_registration_pair_context_probe_artifact,
        ),
        (
            gameassembly_initializer_dispatch_trace_path
            or repo_root / DEFAULT_GAMEASSEMBLY_INITIALIZER_DISPATCH_TRACE,
            _gameassembly_initializer_dispatch_trace_artifact,
        ),
        (
            gameassembly_function_pointer_table_probe_path
            or repo_root / DEFAULT_GAMEASSEMBLY_FUNCTION_POINTER_TABLE_PROBE,
            _gameassembly_function_pointer_table_probe_artifact,
        ),
        (
            gameassembly_metadata_registration_candidate_taxonomy_path
            or repo_root / DEFAULT_GAMEASSEMBLY_METADATA_REGISTRATION_CANDIDATE_TAXONOMY,
            _gameassembly_metadata_registration_candidate_taxonomy_artifact,
        ),
        (
            gameassembly_global_metadata_owner_probe_path
            or repo_root / DEFAULT_GAMEASSEMBLY_GLOBAL_METADATA_OWNER_PROBE,
            _gameassembly_global_metadata_owner_probe_artifact,
        ),
        (
            global_metadata_transform_probe_path
            or repo_root / DEFAULT_GLOBAL_METADATA_TRANSFORM_PROBE,
            _global_metadata_transform_probe_artifact,
        ),
        (
            global_metadata_loader_scan_path
            or repo_root / DEFAULT_GLOBAL_METADATA_LOADER_SCAN,
            _global_metadata_loader_scan_artifact,
        ),
        (
            nep2_metadata_loader_deep_slice_path
            or repo_root / DEFAULT_NEP2_METADATA_LOADER_DEEP_SLICE,
            _nep2_metadata_loader_deep_slice_artifact,
        ),
        (
            nep2_read_mapping_owner_scan_path
            or repo_root / DEFAULT_NEP2_READ_MAPPING_OWNER_SCAN,
            _nep2_read_mapping_owner_scan_artifact,
        ),
        (
            nep2_init_data_owner_scan_path
            or repo_root / DEFAULT_NEP2_INIT_DATA_OWNER_SCAN,
            _nep2_init_data_owner_scan_artifact,
        ),
        (
            nep2_vector_candidate_provenance_path
            or repo_root / DEFAULT_NEP2_VECTOR_CANDIDATE_PROVENANCE,
            _nep2_vector_candidate_provenance_artifact,
        ),
        (
            nep2_vector_wrapper_owner_probe_path
            or repo_root / DEFAULT_NEP2_VECTOR_WRAPPER_OWNER_PROBE,
            _nep2_vector_wrapper_owner_probe_artifact,
        ),
        (
            nep2_file_helper_caller_provenance_path
            or repo_root / DEFAULT_NEP2_FILE_HELPER_CALLER_PROVENANCE,
            _nep2_file_helper_caller_provenance_artifact,
        ),
        (
            gameassembly_resolver_trace_path or repo_root / DEFAULT_GAMEASSEMBLY_RESOLVER_TRACE,
            _gameassembly_resolver_trace_artifact,
        ),
        (
            gameassembly_resolver_caller_trace_path
            or repo_root / DEFAULT_GAMEASSEMBLY_RESOLVER_CALLER_TRACE,
            _gameassembly_resolver_caller_trace_artifact,
        ),
        (
            decoded_hero_audit_path or repo_root / DEFAULT_DECODED_HERO_AUDIT,
            _decoded_hero_audit_artifact,
        ),
    ]

    artifacts: list[ClientEvidenceArtifact] = []
    for path, factory in path_specs:
        if not path.exists():
            artifacts.append(_missing_artifact(path, repo_root))
            continue
        artifacts.append(factory(path, repo_root))

    status_counts = Counter(artifact.status for artifact in artifacts)
    domain_counts: Counter[str] = Counter()
    evidence_refs: set[str] = set()
    for artifact in artifacts:
        domain_counts.update(artifact.knowledge_domains)
        evidence_refs.update(artifact.evidence_refs)

    client_version = _client_version_from_artifacts(artifacts)
    import_readiness = _build_import_readiness(artifacts)
    return ClientEvidenceBundle(
        source_id=source_id,
        generated_at=generated_at,
        client_version=client_version,
        artifact_count=len(artifacts),
        artifact_status_counts=dict(sorted(status_counts.items())),
        knowledge_domain_counts=dict(sorted(domain_counts.items())),
        evidence_ref_count=len(evidence_refs),
        import_readiness=import_readiness,
        artifacts=artifacts,
        guardrails=[
            "offline evidence only; no account credentials, tokens, online protocol, or live instrumentation data is included",
            "normalized client-decoded staging entries must remain blocked until manual review",
            "LuaScripts and NEP2 evidence are decoder targets until readable payloads are recovered and semantically validated",
            "artifact paths are repo-relative and safe to move across machines",
        ],
    )


def write_client_evidence_bundle(bundle: ClientEvidenceBundle, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.safe_dump(bundle.model_dump(mode="json"), allow_unicode=True, sort_keys=False),
        encoding="utf-8",
    )


def _package_manifest_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    files = [item for item in data.get("files", []) if isinstance(item, dict)]
    value_counts = Counter(str(item.get("knowledge_value") or "unknown") for item in files)
    type_counts = Counter(str(item.get("detected_type") or "unknown") for item in files)
    version_info = data.get("version_info") or {}
    evidence_refs = [
        str(item.get("source_ref"))
        for item in files
        if item.get("source_ref")
        and str(item.get("knowledge_value") or "") != "low_third_party_runtime"
    ]
    return ClientEvidenceArtifact(
        artifact_id="client_package_manifest",
        artifact_type="client_package_inventory",
        path=_portable_path(path, repo_root),
        source_id=f"client-package-{_version_label(version_info)}",
        source_site="nslg_client_install",
        source_url="local-nslg-client-install",
        status="evidence_inventory",
        publish_readiness="routing_input_not_publishable",
        knowledge_domains=["version_tracking", "asset_inventory", "binary_anchor"],
        counts={
            "total_files_seen": int(data.get("total_files_seen") or 0),
            "included_files": int(data.get("included_files") or 0),
            "skipped_files": int(data.get("skipped_files") or 0),
            **_prefixed_counts("knowledge_value", value_counts),
            **_prefixed_counts("detected_type", type_counts),
        },
        version_info=version_info,
        evidence_refs=evidence_refs[:160],
        blockers=[
            "file inventory identifies candidate assets and binaries but is not semantic game knowledge",
            "runtime/log/database files are intentionally skipped by default",
        ],
        next_actions=[
            "route asset_bundle_candidate records into domain-specific decoders",
            "use reverse_engineering_anchor binaries for offline static symbol and transform tracing",
        ],
    )


def _client_resource_surface_gap_scan_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    ns_groups = [item for item in data.get("ns_bundle_groups") or [] if isinstance(item, dict)]
    magic_samples = [
        item for item in data.get("safe_magic_samples") or [] if isinstance(item, dict)
    ]
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    evidence_refs.extend(str(item.get("evidence_ref")) for item in ns_groups if item.get("evidence_ref"))
    evidence_refs.extend(
        str(item.get("evidence_ref")) for item in magic_samples if item.get("evidence_ref")
    )
    return ClientEvidenceArtifact(
        artifact_id="client_resource_surface_gap_scan",
        artifact_type="client_resource_surface_gap_inventory",
        path=_portable_path(path, repo_root),
        source_id=data.get("source_id"),
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="resource_surface_gap_inventory",
        publish_readiness="routing_input_not_publishable",
        knowledge_domains=[
            "asset_inventory",
            "resource_bundle",
            "lua_scripts",
            "map",
            "building",
        ],
        counts={
            **counts,
            "ns_bundle_group_count": len(ns_groups),
            "safe_magic_sample_count": len(magic_samples),
        },
        version_info={
            "round": data.get("round"),
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
        },
        evidence_refs=evidence_refs[:200],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "resource surface inventory only"),
            str(conclusion.get("strongest_negative_signal") or "resource bundles are not decoded"),
            str(conclusion.get("search_policy") or "build a resource bundle decoder first"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _ns_bundle_format_index_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    format_groups = [item for item in data.get("format_groups") or [] if isinstance(item, dict)]
    block2_groups = [
        item for item in data.get("cab_block2_groups") or [] if isinstance(item, dict)
    ]
    priority_records = [
        item for item in data.get("priority_records") or [] if isinstance(item, dict)
    ]
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    evidence_refs.extend(
        str(item.get("evidence_ref")) for item in format_groups if item.get("evidence_ref")
    )
    evidence_refs.extend(
        str(item.get("evidence_ref")) for item in block2_groups if item.get("evidence_ref")
    )
    evidence_refs.extend(
        str(item.get("evidence_ref")) for item in priority_records if item.get("evidence_ref")
    )
    high_value_records = [
        item
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
    return ClientEvidenceArtifact(
        artifact_id="ns_bundle_format_index",
        artifact_type="unityfs_ns_bundle_format_index",
        path=_portable_path(path, repo_root),
        source_id=data.get("source_id"),
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="resource_bundle_format_index",
        publish_readiness="not_publishable_decoder_target",
        knowledge_domains=[
            "asset_inventory",
            "resource_bundle",
            "unityfs",
            "serialized_file",
            "decoder_routing",
            "protector",
            "lua_scripts",
            "map",
            "building",
        ],
        counts={
            **counts,
            "format_group_count": len(format_groups),
            "cab_block2_group_count": len(block2_groups),
            "priority_bundle_count": len(priority_records),
            "high_value_priority_bundle_count": len(high_value_records),
        },
        version_info={
            "round": data.get("round"),
            "engine_version": "2022.3.61f2"
            if counts.get("engine_version:2022.3.61f2")
            else None,
            "ns_bundle_index_built": conclusion.get("ns_bundle_index_built"),
            "unityfs_envelope_parseable": conclusion.get("unityfs_envelope_parseable"),
            "first_block_decompression_supported": conclusion.get(
                "first_block_decompression_supported"
            ),
            "serialized_header_parseable": conclusion.get("serialized_header_parseable"),
            "all_indexed_bundles_look_protected": conclusion.get(
                "all_indexed_bundles_look_protected"
            ),
            "decoded_game_knowledge_recovered": conclusion.get(
                "decoded_game_knowledge_recovered"
            ),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:240],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "UnityFS bundle index only"),
            str(
                conclusion.get("strongest_negative_signal")
                or "protected SerializedFile metadata remains unreadable"
            ),
            str(
                conclusion.get("search_policy")
                or "recover protected metadata transform before knowledge promotion"
            ),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _luascripts_catalog_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    records = [item for item in data.get("records", []) if isinstance(item, dict)]
    status_counts = _int_dict(data.get("extraction_status_counts") or {})
    domain_counts = _int_dict(data.get("kb_domain_counts") or {})
    evidence_refs = [str(item.get("evidence_ref")) for item in records if item.get("evidence_ref")]
    blocked = status_counts.get("obfuscated_binary_pending_decoder", 0) > 0
    return ClientEvidenceArtifact(
        artifact_id="luascripts_textasset_catalog",
        artifact_type="unity_textasset_catalog",
        path=_portable_path(path, repo_root),
        source_id=data.get("source_id"),
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="decoder_target_pending" if blocked else "decoded_textasset_catalog",
        publish_readiness="blocked_pending_decoder" if blocked else "review_required",
        knowledge_domains=sorted(domain_counts) or ["unknown"],
        counts={
            "total_container_entries": int(data.get("total_container_entries") or 0),
            "total_data_entries": int(data.get("total_data_entries") or 0),
            "cataloged_records": int(data.get("cataloged_records") or 0),
            "unique_stems": int(data.get("unique_stems") or 0),
            "high_value_stems": len(data.get("high_value_stems") or []),
            **_prefixed_counts("domain", Counter(domain_counts)),
            **_prefixed_counts("extraction_status", Counter(status_counts)),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            "cataloged LuaScripts TextAsset payloads are not readable game knowledge until decoded",
            "high-value stems need decoder validation before any facts are promoted",
        ],
        next_actions=[
            "prioritize high-value stems for protected LuaScripts decoding",
            "after decoding, stage domain facts with source_ref per TextAsset evidence_ref",
        ],
    )


def _lua_crypto_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    payload_counts = _int_dict(data.get("payload_status_counts") or {})
    binary_hits = data.get("binary_string_hits") or []
    payload_samples = data.get("payload_block_samples") or []
    return ClientEvidenceArtifact(
        artifact_id="luascripts_crypto_evidence",
        artifact_type="payload_transform_evidence",
        path=_portable_path(path, repo_root),
        source_id=data.get("source_id"),
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="decoder_target_pending",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "protector", "binary_transform"],
        counts={
            "binary_string_hit_summaries": len(binary_hits),
            "payload_block_samples": len(payload_samples),
            "runtime_initialize_lua_entries": len(data.get("runtime_initialize_lua_entries") or []),
            "skipped_runtime_patch_samples": int(data.get("skipped_runtime_patch_samples") or 0),
            **_prefixed_counts("payload_status", Counter(payload_counts)),
        },
        evidence_refs=[
            f"NSLG_LUA_CRYPTO:{data.get('source_id')}:{item.get('binary_name')}"
            for item in binary_hits
            if isinstance(item, dict) and item.get("binary_name")
        ]
        + [
            f"NSLG_LUA_CRYPTO:{data.get('source_id')}:payload:{item.get('file_name')}"
            for item in payload_samples
            if isinstance(item, dict) and item.get("file_name")
        ],
        blockers=data.get("limitations") or [],
        next_actions=data.get("next_decoder_targets") or [],
    )


def _luascripts_cipher_profile_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    simple = data.get("simple_transform_summary") or {}
    cross_file = data.get("cross_file_block_profile") or {}
    xor_summary = data.get("xor_crib_probe_summary") or {}
    records = [item for item in data.get("payload_profiles") or [] if isinstance(item, dict)]
    status_counts = _int_dict(data.get("payload_status_counts") or {})
    return ClientEvidenceArtifact(
        artifact_id="luascripts_payload_cipher_profile",
        artifact_type="payload_cipher_profile_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="decoder_target_pending",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "binary_transform", "decoder_routing"],
        counts={
            "payload_profile_count": int(data.get("payload_profile_count") or 0),
            "payload_count": int(simple.get("payload_count") or 0),
            "cross_file_shared_16byte_block_count": int(
                cross_file.get("cross_file_shared_16byte_block_count") or 0
            ),
            "duplicate_first_block_count": int(cross_file.get("duplicate_first_block_count") or 0),
            "single_byte_xor_plaintext_like_count": int(
                xor_summary.get("single_byte_xor_plaintext_like_count") or 0
            ),
            "crib_xor_plaintext_like_count": int(
                xor_summary.get("crib_xor_plaintext_like_count") or 0
            ),
            "direct_plaintext_term_file_count": int(simple.get("direct_plaintext_term_file_count") or 0),
            **_prefixed_counts("payload_status", Counter(status_counts)),
        },
        version_info={
            "round": data.get("round"),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "simple_compression_ruled_out": conclusion.get("simple_compression_ruled_out"),
            "single_byte_or_crib_xor_ruled_out": conclusion.get(
                "single_byte_or_crib_xor_ruled_out"
            ),
            "ecb_like_shared_block_signal": conclusion.get("ecb_like_shared_block_signal"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "static payload profile only"),
            str(conclusion.get("strongest_negative_signal") or "payload decoder is not recovered"),
            str(conclusion.get("search_policy") or "recover readable payload decoder before publishing"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_decoder_targets") or []],
    )


def _luascripts_variant_corpus_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    corpus = data.get("corpus_summary") or {}
    block = data.get("block_sharing_summary") or {}
    skip = data.get("offset_skip_probe_summary") or {}
    conclusion = data.get("route_conclusion") or {}
    stem_summaries = [
        item for item in data.get("stem_summaries") or [] if isinstance(item, dict)
    ]
    return ClientEvidenceArtifact(
        artifact_id="luascripts_payload_variant_corpus",
        artifact_type="payload_variant_corpus_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="decoder_target_pending",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "binary_transform", "decoder_routing", "decoder_eval"],
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
            "stem_summary_count": len(stem_summaries),
        },
        version_info={
            "round": data.get("round"),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "duplicate_ciphertext_present": conclusion.get("duplicate_ciphertext_present"),
            "cross_cipher_shared_16byte_block_signal": conclusion.get(
                "cross_cipher_shared_16byte_block_signal"
            ),
            "simple_offset_skip_route_ruled_out": conclusion.get(
                "simple_offset_skip_route_ruled_out"
            ),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "expanded encrypted payload corpus only"),
            str(conclusion.get("strongest_negative_signal") or "payload decoder is not recovered"),
            str(conclusion.get("search_policy") or "recover readable payload decoder before publishing"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_decoder_targets") or []],
    )


def _textasset_payload_owner_trace_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    modules = [item for item in data.get("module_records") or [] if isinstance(item, dict)]
    return ClientEvidenceArtifact(
        artifact_id="textasset_payload_owner_trace",
        artifact_type="textasset_payload_owner_route_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "asset_bundle", "native_binary", "decoder_routing"],
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
            "module_record_count": len(modules),
        },
        version_info={
            "round": data.get("round"),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:160],
        blockers=[
            str(conclusion.get("strongest_positive_signal") or "static TextAsset route evidence only"),
            str(conclusion.get("strongest_negative_signal") or "payload owner is not proven"),
            str(conclusion.get("search_policy") or "require payload-buffer provenance before promotion"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _serialized_textasset_layout_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    stems = [item for item in data.get("stem_summaries") or [] if isinstance(item, dict)]
    groups = [item for item in data.get("object_layout_groups") or [] if isinstance(item, dict)]
    return ClientEvidenceArtifact(
        artifact_id="serialized_textasset_layout_probe",
        artifact_type="serialized_textasset_layout_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "asset_bundle", "serialized_file", "decoder_eval"],
        counts={
            "relevant_record_count": int(counts.get("relevant_record_count") or 0),
            "match_count": int(counts.get("match_count") or 0),
            "valid_layout_count": int(counts.get("valid_layout_count") or 0),
            "invalid_layout_count": int(counts.get("invalid_layout_count") or 0),
            "name_stem_match_count": int(counts.get("name_stem_match_count") or 0),
            "unique_object_offset_count": int(counts.get("unique_object_offset_count") or 0),
            "unique_payload_hash_count": int(counts.get("unique_payload_hash_count") or 0),
            "unique_stem_count": int(counts.get("unique_stem_count") or 0),
            "duplicate_object_offset_group_count": int(
                counts.get("duplicate_object_offset_group_count") or 0
            ),
            "stem_summary_count": len(stems),
            "object_layout_group_count": len(groups),
        },
        version_info={
            "round": data.get("round"),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "serialized TextAsset layout evidence only"),
            str(conclusion.get("strongest_negative_signal") or "path_id to exact object offset is not resolved"),
            str(conclusion.get("search_policy") or "parse SerializedFile tables before decoder promotion"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _serialized_textasset_resolution_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    records = [item for item in data.get("resolved_records") or [] if isinstance(item, dict)]
    groups = [item for item in data.get("resolved_object_groups") or [] if isinstance(item, dict)]
    return ClientEvidenceArtifact(
        artifact_id="serialized_textasset_path_resolution",
        artifact_type="serialized_textasset_path_resolution_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "asset_bundle", "serialized_file", "decoder_eval"],
        counts={
            "relevant_record_count": int(counts.get("relevant_record_count") or 0),
            "container_record_valid_count": int(
                counts.get("container_record_valid_count") or 0
            ),
            "container_record_invalid_count": int(
                counts.get("container_record_invalid_count") or 0
            ),
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
            "resolved_record_sample_count": len(records),
            "resolved_object_group_count": len(groups),
        },
        version_info={
            "round": data.get("round"),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:256],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "path_id/object_offset resolution evidence only"),
            str(conclusion.get("strongest_negative_signal") or "payload decoder is not recovered"),
            str(conclusion.get("search_policy") or "use resolved object offsets for decoder recovery"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _resolved_payload_native_anchor_scan_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    modules = [item for item in data.get("module_records") or [] if isinstance(item, dict)]
    return ClientEvidenceArtifact(
        artifact_id="resolved_payload_native_anchor_scan",
        artifact_type="resolved_payload_native_anchor_scan_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "native_binary", "decoder_eval", "payload_owner"],
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
            "module_record_count": len(modules),
        },
        version_info={
            "round": data.get("round"),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:64],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "resolved native anchor scan evidence only"),
            str(conclusion.get("strongest_negative_signal") or "native payload-buffer owner is not proven"),
            str(conclusion.get("search_policy") or "continue boundary-focused owner analysis"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _textasset_xlua_boundary_ledger_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    records = [item for item in data.get("route_records") or [] if isinstance(item, dict)]
    return ClientEvidenceArtifact(
        artifact_id="textasset_xlua_boundary_ledger",
        artifact_type="textasset_xlua_boundary_route_ledger",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "textasset", "xlua", "payload_owner", "decoder_routing"],
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
            "native_loadbuffer_boundary_candidate_count": int(
                counts.get("native_loadbuffer_boundary_candidate_count") or 0
            ),
            "gameassembly_resolver_payload_owner_candidate_count": int(
                counts.get("gameassembly_resolver_payload_owner_candidate_count") or 0
            ),
            "exact_anchor_native_hit_count": int(counts.get("exact_anchor_native_hit_count") or 0),
            "route_records": len(records),
        },
        version_info={
            "round": data.get("round"),
            "native_payload_buffer_owner_proven": conclusion.get(
                "native_payload_buffer_owner_proven"
            ),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
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
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "TextAsset/xLua boundary ledger only"),
            str(conclusion.get("strongest_negative_signal") or "native payload-buffer owner is not proven"),
            str(conclusion.get("search_policy") or "continue with method ownership or proven buffer-flow evidence"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _nep2_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    init_refs = [
        f"NSLG_NEP2_LUASCRIPTS:{source_id}:InitLuaScriptsScan:{item.get('rva')}"
        for item in data.get("init_luascripts_occurrences") or []
        if isinstance(item, dict) and item.get("rva")
    ]
    xref_refs = [
        f"NSLG_NEP2_LUASCRIPTS:{source_id}:xref:{item.get('string')}:{item.get('ref_rva')}"
        for item in data.get("xrefs") or []
        if isinstance(item, dict) and item.get("ref_rva")
    ]
    return ClientEvidenceArtifact(
        artifact_id="nep2_luascripts_static_evidence",
        artifact_type="native_protector_static_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "protector", "native_binary"],
        counts={
            "size_bytes": int(data.get("size_bytes") or 0),
            "init_luascripts_occurrences": len(data.get("init_luascripts_occurrences") or []),
            "pointer_refs_to_init_luascripts": int(data.get("pointer_refs_to_init_luascripts") or 0),
            "candidate_string_count": int(data.get("candidate_string_count") or 0),
            "selected_candidate_strings": len(data.get("selected_candidate_strings") or []),
            "xref_count": int(data.get("xref_count") or 0),
            "string_chunk_registrations": len(data.get("string_chunk_registrations") or []),
        },
        evidence_refs=(init_refs + xref_refs)[:160],
        blockers=data.get("limitations") or [],
        next_actions=data.get("next_static_targets") or [],
    )


def _nep2_provenance_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    records = [item for item in data.get("records") or [] if isinstance(item, dict)]
    route_conclusion = data.get("route_conclusion") or {}
    closure_counts = _int_dict(data.get("closure_status_counts") or {})
    verdict_counts = _int_dict(data.get("target_verdict_counts") or {})
    pointer_counts = _int_dict(data.get("pointer_ref_classification_counts") or {})
    round_range = data.get("round_range") or {}
    evidence_refs = [
        str(item.get("evidence_ref")) for item in records if item.get("evidence_ref")
    ]
    next_target = data.get("next_unclosed_shape_lead")
    next_actions = [
        "treat closed NEP2 RVAs as negative routing evidence and avoid broad shape-only rescans",
        "continue only when a candidate has caller/callee provenance, keyword/import ownership, or file-buffer/asset owner evidence",
    ]
    if next_target:
        next_actions.append(f"next unclosed NEP2 shape lead from external analysis log: {next_target}")
    return ClientEvidenceArtifact(
        artifact_id="nep2_provenance_closure_batch",
        artifact_type="native_protector_negative_provenance",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="negative_provenance_route_closure",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "protector", "native_binary", "decoder_routing"],
        counts={
            "artifact_count": int(data.get("artifact_count") or 0),
            "closed_rvas": len(data.get("closed_rvas") or []),
            "round_min": int(round_range.get("min") or 0),
            "round_max": int(round_range.get("max") or 0),
            **_prefixed_counts("closure_status", Counter(closure_counts)),
            **_prefixed_counts("target_verdict", Counter(verdict_counts)),
            **_prefixed_counts("pointer_ref_classification", Counter(pointer_counts)),
        },
        version_info={
            "binary_name": data.get("binary_name"),
            "next_unclosed_shape_lead": next_target,
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(route_conclusion.get("strongest_negative_signal") or "closed routes are negative static evidence"),
            str(route_conclusion.get("search_policy") or "continue with provenance-backed candidates only"),
        ],
        next_actions=next_actions,
    )


def _gameassembly_route_trace_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    records = [item for item in data.get("records") or [] if isinstance(item, dict)]
    route_conclusion = data.get("route_conclusion") or {}
    status_counts = _int_dict(data.get("status_counts") or {})
    kind_counts = _int_dict(data.get("artifact_kind_counts") or {})
    round_range = data.get("round_range") or {}
    evidence_refs = [str(item.get("evidence_ref")) for item in records if item.get("evidence_ref")]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_route_trace",
        artifact_type="gameassembly_static_route_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "native_binary", "decoder_routing", "asset_bundle", "metadata"],
        counts={
            "artifact_count": int(data.get("artifact_count") or 0),
            "route_signal_record_count": int(data.get("route_signal_record_count") or 0),
            "total_target_strings": int(data.get("total_target_strings") or 0),
            "total_code_refs": int(data.get("total_code_refs") or 0),
            "total_function_refs": int(data.get("total_function_refs") or 0),
            "round_min": int(round_range.get("min") or 0),
            "round_max": int(round_range.get("max") or 0),
            **_prefixed_counts("status", Counter(status_counts)),
            **_prefixed_counts("artifact_kind", Counter(kind_counts)),
        },
        version_info={
            "binary_name": data.get("binary_name"),
            "textasset_loadbuffer_bridge_proven": route_conclusion.get(
                "textasset_loadbuffer_bridge_proven"
            ),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(route_conclusion.get("strongest_current_signal") or "static route evidence only"),
            str(route_conclusion.get("search_policy") or "recover readable payload decoder before publishing"),
        ],
        next_actions=[
            "use GameAssembly traces as decoder routing evidence, not game knowledge",
            "recover TextAsset/LuaScripts payload decoder before staging facts",
            "prefer NEP2 InitLuaScriptsScan or runtime-independent TextAsset payload decoder recovery next",
        ],
    )


def _nep2_init_bridge_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    records = [item for item in data.get("bridge_records") or [] if isinstance(item, dict)]
    candidates = [item for item in data.get("candidate_functions") or [] if isinstance(item, dict)]
    conclusion = data.get("route_conclusion") or {}
    status_counts = _int_dict(data.get("status_counts") or {})
    verdict_counts = _int_dict(data.get("candidate_verdict_counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="nep2_init_luascripts_bridge",
        artifact_type="native_protector_init_bridge_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "protector", "native_binary", "decoder_routing"],
        counts={
            **_int_dict(data.get("counts") or {}),
            "bridge_records": len(records),
            "candidate_functions": len(candidates),
            **_prefixed_counts("bridge_status", Counter(status_counts)),
            **_prefixed_counts("candidate_verdict", Counter(verdict_counts)),
        },
        version_info={
            "binary_name": data.get("binary_name"),
            "round": data.get("round"),
            "bridge_metadata_confirmed": conclusion.get("bridge_metadata_confirmed"),
            "decryptor_body_proven": conclusion.get("decryptor_body_proven"),
            "file_buffer_owner_proven": conclusion.get("file_buffer_owner_proven"),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "static bridge metadata only"),
            str(conclusion.get("strongest_negative_signal") or "payload decoder is not proven"),
            str(conclusion.get("search_policy") or "continue with provenance-backed decoder targets only"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _native_boundary_trace_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    records = [item for item in data.get("module_records") or [] if isinstance(item, dict)]
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="native_loadbuffer_boundary_trace",
        artifact_type="native_loadbuffer_boundary_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "native_binary", "decoder_routing", "binary_transform"],
        counts={
            **counts,
            "module_records": len(records),
        },
        version_info={
            "round": data.get("round"),
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
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "static native boundary evidence only"),
            str(conclusion.get("strongest_negative_signal") or "TextAsset to loadbuffer owner is not proven"),
            str(conclusion.get("search_policy") or "continue with provenance-backed buffer-owner tracing only"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _runtime_init_route_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="runtime_init_metadata_route",
        artifact_type="runtime_init_metadata_route_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "metadata", "native_binary", "decoder_routing"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "runtime_init_anchor_known": conclusion.get("runtime_init_anchor_known"),
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
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "runtime init route evidence only"),
            str(conclusion.get("strongest_blocker") or "metadata/method ownership is not recovered"),
            str(conclusion.get("search_policy") or "recover method ownership before decoder promotion"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _runtime_init_registry_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    modules = [item for item in data.get("module_records") or [] if isinstance(item, dict)]
    registry = data.get("registry_summary") or {}
    refs = data.get("unityplayer_runtime_json_xrefs") or {}
    return ClientEvidenceArtifact(
        artifact_id="runtime_init_registry_probe",
        artifact_type="runtime_init_registry_probe_evidence",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "metadata", "runtime_init", "native_binary", "decoder_routing"],
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
            "modules_with_init_lua_env_hits": int(counts.get("modules_with_init_lua_env_hits") or 0),
            "modules_with_runtime_init_json_hits": int(
                counts.get("modules_with_runtime_init_json_hits") or 0
            ),
            "unityplayer_runtime_json_code_ref_count": int(
                counts.get("unityplayer_runtime_json_code_ref_count") or 0
            ),
            "module_record_count": len(modules),
            "registry_entry_count": len(registry.get("entries") or []),
            "unityplayer_ref_count": int(refs.get("code_ref_count") or 0),
        },
        version_info={
            "round": data.get("round"),
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
            "textasset_payload_owner_proven": conclusion.get("textasset_payload_owner_proven"),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "runtime-init registry evidence only"),
            str(conclusion.get("strongest_negative_signal") or "native method address is not recovered"),
            str(conclusion.get("search_policy") or "continue with protected metadata or registration ownership"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_codegen_module_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    modules = [item for item in data.get("assembly_csharp_modules") or [] if isinstance(item, dict)]
    runs = [item for item in data.get("codegen_module_runs") or [] if isinstance(item, dict)]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_codegen_module_probe",
        artifact_type="gameassembly_il2cpp_codegen_module_probe",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing", "lua_scripts"],
        counts={
            "codegen_module_candidate_count": int(counts.get("codegen_module_candidate_count") or 0),
            "codegen_module_run_count": int(counts.get("codegen_module_run_count") or 0),
            "largest_codegen_module_run_count": int(
                counts.get("largest_codegen_module_run_count") or 0
            ),
            "assembly_csharp_module_count": int(counts.get("assembly_csharp_module_count") or 0),
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
            "assembly_csharp_module_records": len(modules),
            "codegen_module_runs": len(runs),
        },
        version_info={
            "round": data.get("round"),
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
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "GameAssembly CodeGenModule probe is static registration evidence only"),
            str(conclusion.get("strongest_negative_signal") or "method names remain blocked by protected metadata"),
            str(conclusion.get("search_policy") or "recover metadata registration ownership before naming method pointers"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_registration_anchor_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    summary = data.get("module_array_summary") or {}
    blockers = [
        str(
            conclusion.get("strongest_current_signal")
            or "CodeRegistration-side CodeGenModules anchor is static routing evidence only"
        ),
        str(
            conclusion.get("strongest_negative_signal")
            or "MetadataRegistration pairing is not recovered"
        ),
        str(
            conclusion.get("search_policy")
            or "recover registration callsite and metadata registration ownership"
        ),
    ] + [str(item) for item in data.get("limitations") or []]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_registration_anchor_probe",
        artifact_type="gameassembly_il2cpp_registration_anchor_probe",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing", "lua_scripts"],
        counts={
            "codegen_modules_field_candidate_count": int(
                counts.get("codegen_modules_field_candidate_count") or 0
            ),
            "declared_codegen_module_count": int(
                counts.get("declared_codegen_module_count") or 0
            ),
            "parsed_codegen_module_count": int(counts.get("parsed_codegen_module_count") or 0),
            "nonzero_method_module_count": int(counts.get("nonzero_method_module_count") or 0),
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
        },
        version_info={
            "round": data.get("round"),
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
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=blockers,
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_registration_layout_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    layout = data.get("primary_code_registration_layout") or {}
    offsets = layout.get("codegen_modules_field_offsets") or {}
    blockers = [
        str(
            conclusion.get("strongest_current_signal")
            or "CodeRegistration-like layout is refined to an exact local start"
        ),
        str(
            conclusion.get("strongest_negative_signal")
            or "registration callsite and MetadataRegistration pairing are not recovered"
        ),
        str(
            conclusion.get("search_policy")
            or "require callsite pairing or decoded metadata before naming method pointers"
        ),
    ] + [str(item) for item in data.get("limitations") or []]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_registration_layout_probe",
        artifact_type="gameassembly_il2cpp_registration_layout_probe",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing", "lua_scripts"],
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
            "known_codegen_modules_count": int(counts.get("known_codegen_modules_count") or 0),
            "layout_field_row_count": int(counts.get("layout_field_row_count") or 0),
            "registration_code_ref_count": int(counts.get("registration_code_ref_count") or 0),
            "registration_raw_va_ref_count": int(counts.get("registration_raw_va_ref_count") or 0),
            "metadata_registration_candidate_count": int(
                counts.get("metadata_registration_candidate_count") or 0
            ),
            "metadata_registration_paired_by_callsite": int(
                counts.get("metadata_registration_paired_by_callsite") or 0
            ),
            "init_lua_env_method_pointer_recovered": int(
                counts.get("init_lua_env_method_pointer_recovered") or 0
            ),
        },
        version_info={
            "round": data.get("round"),
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
            "codegen_modules_count_offset": offsets.get("count_offset"),
            "codegen_modules_pointer_offset": offsets.get("pointer_offset"),
            "codegen_modules_array_rva": offsets.get("array_rva"),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=blockers,
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_registration_pair_context_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    blockers = [
        str(
            conclusion.get("strongest_current_signal")
            or "MetadataRegistration-like candidates have data-family refs only"
        ),
        str(
            conclusion.get("strongest_negative_signal")
            or "direct CodeRegistration/MetadataRegistration pairing is not recovered"
        ),
        str(
            conclusion.get("search_policy")
            or "pivot from direct pointer-pair xrefs to metadata ownership or initializer trace"
        ),
    ] + [str(item) for item in data.get("limitations") or []]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_registration_pair_context_probe",
        artifact_type="gameassembly_il2cpp_registration_pair_context_probe",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing", "lua_scripts"],
        counts={
            "registration_target_count": int(counts.get("registration_target_count") or 0),
            "metadata_target_count": int(counts.get("metadata_target_count") or 0),
            "raw_registration_ref_count": int(counts.get("raw_registration_ref_count") or 0),
            "raw_code_registration_start_ref_count": int(
                counts.get("raw_code_registration_start_ref_count") or 0
            ),
            "raw_metadata_candidate_ref_count": int(
                counts.get("raw_metadata_candidate_ref_count") or 0
            ),
            "registration_code_ref_count": int(counts.get("registration_code_ref_count") or 0),
            "metadata_candidate_code_ref_count": int(
                counts.get("metadata_candidate_code_ref_count") or 0
            ),
            "paired_neighborhood_count": int(counts.get("paired_neighborhood_count") or 0),
            "call_argument_pair_window_count": int(
                counts.get("call_argument_pair_window_count") or 0
            ),
            "metadata_ref_family_cluster_count": int(
                counts.get("metadata_ref_family_cluster_count") or 0
            ),
            "registration_pair_recovered": int(counts.get("registration_pair_recovered") or 0),
            "init_lua_env_method_pointer_recovered": int(
                counts.get("init_lua_env_method_pointer_recovered") or 0
            ),
        },
        version_info={
            "round": data.get("round"),
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
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=blockers,
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_initializer_dispatch_trace_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    blockers = [
        str(
            conclusion.get("summary")
            or "bounded direct-call dispatcher trace did not recover a registration/metadata owner"
        ),
        "registration and metadata ownership remain unresolved",
        "initializer dispatch trace evidence is not publishable game knowledge",
    ] + [str(item) for item in data.get("limitations") or []]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_initializer_dispatch_trace",
        artifact_type="gameassembly_il2cpp_initializer_dispatch_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing", "lua_scripts"],
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
        },
        version_info={
            "round": data.get("round"),
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
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=blockers,
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_function_pointer_table_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    blockers = [
        str(
            conclusion.get("interpretation")
            or "function pointer table probe did not recover InitLuaEnv ownership"
        ),
        "dispatcher pointer hits classify as known IL2CPP tables, not standalone initializer ownership",
        "function pointer table evidence is not publishable game knowledge",
    ] + [str(item) for item in data.get("limitations") or []]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_function_pointer_table_probe",
        artifact_type="gameassembly_il2cpp_function_pointer_table_probe",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing", "lua_scripts"],
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
            "dispatcher_pointer_hit_count": int(counts.get("dispatcher_pointer_hit_count") or 0),
            "dispatcher_pointer_hits_outside_known_tables": int(
                counts.get("dispatcher_pointer_hits_outside_known_tables") or 0
            ),
            "initializer_candidate_table_count": int(
                counts.get("initializer_candidate_table_count") or 0
            ),
            "init_lua_env_method_pointer_recovered": int(
                counts.get("init_lua_env_method_pointer_recovered") or 0
            ),
        },
        version_info={
            "round": data.get("round"),
            "function_pointer_tables_scanned": conclusion.get("function_pointer_tables_scanned"),
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
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=blockers,
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_metadata_registration_candidate_taxonomy_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    counts = _int_dict(data.get("counts") or {})
    conclusion = data.get("route_conclusion") or {}
    blockers = [
        str(conclusion.get("strongest_current_signal") or "tiny-count candidate family evidence"),
        str(conclusion.get("strongest_negative_signal") or "metadata owner remains unresolved"),
        str(conclusion.get("search_policy") or "require decoded metadata or proven owner"),
        "MetadataRegistration candidate taxonomy is not publishable game knowledge",
    ] + [str(item) for item in data.get("limitations") or []]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_metadata_registration_candidate_taxonomy",
        artifact_type="gameassembly_metadata_registration_candidate_taxonomy",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing"],
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
            "protected_metadata_method_ownership_recovered": int(
                counts.get("protected_metadata_method_ownership_recovered") or 0
            ),
            "init_lua_env_method_pointer_recovered": int(
                counts.get("init_lua_env_method_pointer_recovered") or 0
            ),
        },
        version_info={
            "round": data.get("round"),
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
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:80],
        blockers=blockers,
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_global_metadata_owner_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    owner_found = bool(conclusion.get("global_metadata_owner_candidate_found"))
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_global_metadata_owner_probe",
        artifact_type="gameassembly_global_metadata_owner_probe_static_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed" if owner_found else "negative_provenance_route_closure",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "il2cpp", "decoder_routing"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "target_count": counts.get("target_count"),
            "seed_function_count": counts.get("seed_function_count"),
            "metadata_string_ref_function_count": counts.get(
                "metadata_string_ref_function_count"
            ),
            "file_or_mapping_import_function_count": counts.get(
                "file_or_mapping_import_function_count"
            ),
            "metadata_candidate_ref_function_count": counts.get(
                "metadata_candidate_ref_function_count"
            ),
            "loader_owner_candidate_count": counts.get("loader_owner_candidate_count"),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "global-metadata string refs are route evidence only"),
            str(conclusion.get("strongest_negative_signal") or "global-metadata owner remains unresolved"),
            str(conclusion.get("search_policy") or "require file-buffer ownership or decoded metadata before promotion"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _global_metadata_transform_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="global_metadata_transform_probe",
        artifact_type="global_metadata_transform_negative_probe",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "binary_transform", "decoder_routing"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "protected_wrapper_confirmed": conclusion.get("protected_wrapper_confirmed"),
            "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
            "init_lua_env_method_ownership_recovered": conclusion.get(
                "init_lua_env_method_ownership_recovered"
            ),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            "global-metadata.dat file-only transform probe did not recover plaintext metadata",
            "InitLuaEnv method ownership is still unrecovered",
        ]
        + [str(item) for item in conclusion.get("verdict") or []]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _global_metadata_loader_scan_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="global_metadata_loader_mutation_scan",
        artifact_type="global_metadata_loader_mutation_static_scan",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "binary_transform", "decoder_routing", "protector"],
        counts=counts,
        version_info={
            "round": data.get("round"),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "loader mutation scan is static routing evidence only"),
            str(conclusion.get("strongest_negative_signal") or "full loader-mutation gate was not found"),
            str(conclusion.get("search_policy") or "require metadata wrapper or payload-buffer provenance before promotion"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _nep2_metadata_loader_deep_slice_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="nep2_global_metadata_loader_deep_slice",
        artifact_type="nep2_global_metadata_loader_candidate_deep_slice",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="negative_provenance_route_closure"
        if conclusion.get("targets_closed_as_metadata_loader_candidates")
        else "static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "binary_transform", "decoder_routing", "protector"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "target_rvas": data.get("target_rvas") or [],
            "targets_closed_as_metadata_loader_candidates": conclusion.get(
                "targets_closed_as_metadata_loader_candidates"
            ),
            "global_metadata_loader_proven": conclusion.get("global_metadata_loader_proven"),
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
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "NEP2 loader deep-slice is static routing evidence only"),
            str(conclusion.get("strongest_negative_signal") or "metadata loader was not proven"),
            str(conclusion.get("search_policy") or "continue with provenance-backed read/mapping owners only"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _nep2_read_mapping_owner_scan_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    provenance_linked = bool(conclusion.get("metadata_linked_read_mapping_owner_found"))
    return ClientEvidenceArtifact(
        artifact_id="nep2_read_mapping_owner_scan",
        artifact_type="nep2_read_mapping_owner_static_scan",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed" if provenance_linked else "negative_provenance_route_closure",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "native_binary", "binary_transform", "decoder_routing", "protector"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "actual_read_mapping_owners_found": conclusion.get(
                "actual_read_mapping_owners_found"
            ),
            "metadata_linked_read_mapping_owner_found": conclusion.get(
                "metadata_linked_read_mapping_owner_found"
            ),
            "global_metadata_loader_proven": conclusion.get("global_metadata_loader_proven"),
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
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "NEP2 read/mapping owner scan is static routing evidence only"),
            str(conclusion.get("strongest_negative_signal") or "metadata-linked read/mapping owner was not proven"),
            str(conclusion.get("search_policy") or "continue only with provenance-backed read/mapping owners"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _nep2_init_data_owner_scan_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    payload_candidate = bool(conclusion.get("payload_owner_candidate_found"))
    return ClientEvidenceArtifact(
        artifact_id="nep2_init_data_owner_scan",
        artifact_type="nep2_init_luascripts_data_owner_scan",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed" if payload_candidate else "negative_provenance_route_closure",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "lua_scripts", "native_binary", "decoder_routing", "protector"],
        counts=counts,
        version_info={
            "round": data.get("round"),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "global_metadata_loader_proven": conclusion.get("global_metadata_loader_proven"),
            "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "NEP2 init data-owner scan is static routing evidence only"),
            str(conclusion.get("strongest_negative_signal") or "payload owner was not proven"),
            str(conclusion.get("search_policy") or "continue only with payload-proven owner tracing"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _nep2_vector_candidate_provenance_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    vector_linked = bool(conclusion.get("vector_candidate_provenance_link_found"))
    return ClientEvidenceArtifact(
        artifact_id="nep2_vector_candidate_provenance",
        artifact_type="nep2_vector_candidate_provenance_static_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed" if vector_linked else "negative_provenance_route_closure",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "lua_scripts", "native_binary", "decoder_routing", "protector"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "target_count": counts.get("target_count"),
            "vector_candidate_count": counts.get("vector_candidate_count"),
            "provenance_linked_target_count": counts.get("provenance_linked_target_count"),
            "provenance_linked_vector_candidate_count": counts.get(
                "provenance_linked_vector_candidate_count"
            ),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "NEP2 vector candidate provenance trace is static routing evidence only"),
            str(conclusion.get("strongest_negative_signal") or "vector/helper route lacks payload-buffer provenance"),
            str(conclusion.get("search_policy") or "promote only provenance-linked vector helpers"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _nep2_vector_wrapper_owner_probe_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    owner_found = bool(conclusion.get("vector_wrapper_owner_candidate_found"))
    return ClientEvidenceArtifact(
        artifact_id="nep2_vector_wrapper_owner_probe",
        artifact_type="nep2_vector_wrapper_owner_probe_static_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed" if owner_found else "negative_provenance_route_closure",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "lua_scripts", "native_binary", "decoder_routing", "protector"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "vector_target_count": counts.get("vector_target_count"),
            "wrapper_function_count": counts.get("wrapper_function_count"),
            "direct_vector_wrapper_count": counts.get("direct_vector_wrapper_count"),
            "vector_call_edge_count": counts.get("vector_call_edge_count"),
            "vector_wrapper_owner_candidate_count": counts.get(
                "vector_wrapper_owner_candidate_count"
            ),
            "wrapper_with_keyword_ref_count": counts.get("wrapper_with_keyword_ref_count"),
            "wrapper_with_read_mapping_import_count": counts.get(
                "wrapper_with_read_mapping_import_count"
            ),
            "wrapper_with_provenance_path_count": counts.get(
                "wrapper_with_provenance_path_count"
            ),
            "vector_wrapper_payload_owner_proven": conclusion.get(
                "vector_wrapper_payload_owner_proven"
            ),
            "read_mapping_to_vector_wrapper_path_found": conclusion.get(
                "read_mapping_to_vector_wrapper_path_found"
            ),
            "metadata_or_luascripts_keyword_link_found": conclusion.get(
                "metadata_or_luascripts_keyword_link_found"
            ),
            "protected_metadata_method_ownership_recovered": conclusion.get(
                "protected_metadata_method_ownership_recovered"
            ),
            "plaintext_metadata_recovered": conclusion.get("plaintext_metadata_recovered"),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "NEP2 vector-wrapper owner probe is static routing evidence only"),
            str(conclusion.get("strongest_negative_signal") or "vector-wrapper route lacks payload-buffer provenance"),
            str(conclusion.get("search_policy") or "demote isolated vector-wrapper clusters"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _nep2_file_helper_caller_provenance_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    owner_proven = bool(conclusion.get("file_helper_payload_owner_proven"))
    return ClientEvidenceArtifact(
        artifact_id="nep2_file_helper_caller_provenance",
        artifact_type="nep2_file_helper_caller_provenance_static_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed" if owner_proven else "negative_provenance_route_closure",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["metadata", "lua_scripts", "native_binary", "decoder_routing", "protector"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "target_count": counts.get("target_count"),
            "helper_seed_target_count": counts.get("helper_seed_target_count"),
            "caller_path_to_helper_count": counts.get("caller_path_to_helper_count"),
            "payload_keyword_ref_function_count": counts.get(
                "payload_keyword_ref_function_count"
            ),
            "createfile_import_function_count": counts.get(
                "createfile_import_function_count"
            ),
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
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
            "safe_for_publish": conclusion.get("safe_for_publish"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "NEP2 file-helper caller provenance trace is static routing evidence only"),
            str(conclusion.get("strongest_negative_signal") or "file-helper route lacks payload-buffer provenance"),
            str(conclusion.get("search_policy") or "treat file helper as generic unless payload owner is recovered"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_resolver_trace_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    notable_callers = [
        item for item in data.get("notable_caller_functions") or [] if isinstance(item, dict)
    ]
    target = data.get("target") or {}
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_resolver_candidate_trace",
        artifact_type="gameassembly_resolver_descriptor_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "metadata", "native_binary", "decoder_routing"],
        counts={
            **counts,
            "notable_caller_functions": len(notable_callers),
        },
        version_info={
            "round": data.get("round"),
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
            "textasset_payload_owner_proven": conclusion.get("textasset_payload_owner_proven"),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "GameAssembly resolver trace evidence only"),
            str(conclusion.get("strongest_negative_signal") or "payload ownership is not proven"),
            str(conclusion.get("search_policy") or "recover payload-buffer ownership before decoder promotion"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _gameassembly_resolver_caller_trace_artifact(
    path: Path,
    repo_root: Path,
) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    source_id = data.get("source_id")
    conclusion = data.get("route_conclusion") or {}
    counts = _int_dict(data.get("counts") or {})
    target = data.get("target") or {}
    evidence_refs = [str(item) for item in data.get("evidence_refs") or [] if item]
    return ClientEvidenceArtifact(
        artifact_id="gameassembly_resolver_caller_payload_trace",
        artifact_type="gameassembly_resolver_caller_payload_owner_trace",
        path=_portable_path(path, repo_root),
        source_id=source_id,
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="static_trace_seed",
        publish_readiness="not_publishable_static_evidence",
        knowledge_domains=["lua_scripts", "metadata", "native_binary", "decoder_routing"],
        counts=counts,
        version_info={
            "round": data.get("round"),
            "resolver_candidate_rva": target.get("resolver_candidate_rva"),
            "all_direct_resolver_callers_scanned": conclusion.get(
                "all_direct_resolver_callers_scanned"
            ),
            "resolver_layer_has_payload_owner_candidate": conclusion.get(
                "resolver_layer_has_payload_owner_candidate"
            ),
            "textasset_payload_owner_proven": conclusion.get("textasset_payload_owner_proven"),
            "file_buffer_payload_owner_proven": conclusion.get(
                "file_buffer_payload_owner_proven"
            ),
            "lua_payload_decoder_recovered": conclusion.get("lua_payload_decoder_recovered"),
        },
        evidence_refs=evidence_refs[:160],
        blockers=[
            str(conclusion.get("strongest_current_signal") or "GameAssembly resolver caller trace evidence only"),
            str(conclusion.get("strongest_negative_signal") or "payload owner is not proven"),
            str(conclusion.get("search_policy") or "recover payload-buffer ownership before decoder promotion"),
        ]
        + [str(item) for item in data.get("limitations") or []],
        next_actions=[str(item) for item in data.get("next_static_targets") or []],
    )


def _decoded_hero_audit_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    data = _load_yaml(path)
    staging = data.get("staging") or {}
    hero_coverage = data.get("hero_coverage") or {}
    skill_coverage = data.get("skill_coverage") or {}
    validation = data.get("knowledge_validation") or {}
    security_scan = data.get("security_scan") or {}
    review_blockers = [str(item) for item in data.get("review_blockers") or []]
    return ClientEvidenceArtifact(
        artifact_id="decoded_hero_audit",
        artifact_type="client_decoded_staging_audit",
        path=_portable_path(path, repo_root),
        source_id=data.get("source_id"),
        source_site=data.get("source_site"),
        source_url=data.get("source_url"),
        status="normalized_staging_blocked",
        publish_readiness="blocked_until_reviewed",
        knowledge_domains=["hero", "skill"],
        counts={
            "candidate_entries": int(staging.get("candidate_entries") or 0),
            "skipped_non_static_records": int(staging.get("skipped_non_static_records") or 0),
            "mapped_heroes": int(hero_coverage.get("mapped_heroes") or 0),
            "unmapped_heroes": len(hero_coverage.get("unmapped_heroes") or []),
            "mapped_skill_ids": int(skill_coverage.get("mapped_skill_ids") or 0),
            "unmapped_skill_ids": len(skill_coverage.get("unmapped_skill_ids") or []),
            "knowledge_entries_loaded": int(validation.get("knowledge_entries_loaded") or 0),
            "sensitive_markers_found": len(security_scan.get("sensitive_markers_found") or []),
            "review_blockers": len(review_blockers),
        },
        evidence_refs=[str(item) for item in data.get("evidence_refs") or []][:160],
        blockers=review_blockers,
        next_actions=[str(item) for item in data.get("next_review_actions") or []],
    )


def _missing_artifact(path: Path, repo_root: Path) -> ClientEvidenceArtifact:
    return ClientEvidenceArtifact(
        artifact_id=f"missing:{path.name}",
        artifact_type="missing_expected_artifact",
        path=_portable_path(path, repo_root),
        status="missing",
        publish_readiness="blocked_missing_artifact",
        blockers=[f"expected artifact not found: {_portable_path(path, repo_root)}"],
        next_actions=["rebuild the missing offline client evidence artifact"],
    )


def _build_import_readiness(artifacts: list[ClientEvidenceArtifact]) -> dict[str, Any]:
    normalized = sum(
        artifact.counts.get("candidate_entries", 0)
        for artifact in artifacts
        if artifact.status == "normalized_staging_blocked"
    )
    missing = [artifact.artifact_id for artifact in artifacts if artifact.status == "missing"]
    decoder_targets = [
        artifact.artifact_id
        for artifact in artifacts
        if artifact.status
        in {"decoder_target_pending", "static_trace_seed", "resource_bundle_format_index"}
    ]
    blockers = [blocker for artifact in artifacts for blocker in artifact.blockers]
    ready = not missing and normalized == 0 and not decoder_targets and not blockers
    return {
        "safe_for_publish": ready,
        "publishable_knowledge_entries": 0,
        "normalized_staging_entries": normalized,
        "missing_artifacts": missing,
        "decoder_target_artifacts": decoder_targets,
        "blocker_count": len(blockers),
        "reason": (
            "all client artifacts are reviewed and publishable"
            if ready
            else "client evidence still contains normalized staging, decoder targets, missing artifacts, or review blockers"
        ),
    }


def _client_version_from_artifacts(artifacts: list[ClientEvidenceArtifact]) -> dict[str, Any]:
    for artifact in artifacts:
        if artifact.artifact_id != "client_package_manifest":
            continue
        version_info = artifact.version_info or {}
        manifest = version_info.get("manifest") or {}
        package_info = version_info.get("pc_package_info") or {}
        return {
            "app_version": manifest.get("m_AppVersion"),
            "global_bundle_version": manifest.get("m_GlobalBundleVersion"),
            "streaming_assets_global_bundle_version": manifest.get(
                "m_StreamingAssetsGlobalBundleVersion"
            ),
            "app_git_version": manifest.get("m_AppGitVersion"),
            "global_bundle_git_version": manifest.get("m_GlobalBundleGitVersion"),
            "pc_package_info": package_info,
        }
    return {}


def _version_label(version_info: dict[str, Any]) -> str:
    manifest = version_info.get("manifest") or {}
    return str(manifest.get("m_AppVersion") or "unknown")


def _load_yaml(path: Path) -> dict[str, Any]:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else {}


def _portable_path(path: Path, repo_root: Path) -> str:
    try:
        return path.resolve().relative_to(repo_root).as_posix()
    except ValueError:
        return path.name


def _int_dict(value: dict[str, Any]) -> dict[str, int]:
    return {str(key): int(raw or 0) for key, raw in value.items()}


def _prefixed_counts(prefix: str, counts: Counter[str]) -> dict[str, int]:
    return {f"{prefix}:{key}": int(value) for key, value in sorted(counts.items())}
