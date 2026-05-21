from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_import_queue import (
    build_client_import_queue,
    write_client_import_queue,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a review/decoder queue for sanitized offline NSLG client evidence."
    )
    parser.add_argument("--repo-root", default=".", help="qa-agent package root.")
    parser.add_argument("--output", required=True, help="YAML queue output path.")
    parser.add_argument("--source-id", default="nslg-client-import-queue")
    parser.add_argument("--evidence-bundle", default=None)
    parser.add_argument("--client-resource-surface-gap-scan", default=None)
    parser.add_argument("--ns-bundle-format-index", default=None)
    parser.add_argument("--normalized-staging", default=None)
    parser.add_argument("--decoded-hero-audit", default=None)
    parser.add_argument("--luascripts-catalog", default=None)
    parser.add_argument("--lua-crypto-evidence", default=None)
    parser.add_argument("--luascripts-cipher-profile", default=None)
    parser.add_argument("--luascripts-variant-corpus", default=None)
    parser.add_argument("--textasset-payload-owner-trace", default=None)
    parser.add_argument("--serialized-textasset-layout", default=None)
    parser.add_argument("--serialized-textasset-resolution", default=None)
    parser.add_argument("--resolved-payload-native-anchor-scan", default=None)
    parser.add_argument("--textasset-xlua-boundary-ledger", default=None)
    parser.add_argument("--nep2-luascripts-evidence", default=None)
    parser.add_argument("--gameassembly-route-trace", default=None)
    parser.add_argument("--nep2-init-bridge", default=None)
    parser.add_argument("--native-boundary-trace", default=None)
    parser.add_argument("--runtime-init-route", default=None)
    parser.add_argument("--runtime-init-registry-probe", default=None)
    parser.add_argument("--gameassembly-codegen-module-probe", default=None)
    parser.add_argument("--gameassembly-registration-anchor-probe", default=None)
    parser.add_argument("--gameassembly-registration-layout-probe", default=None)
    parser.add_argument("--gameassembly-registration-pair-context-probe", default=None)
    parser.add_argument("--gameassembly-initializer-dispatch-trace", default=None)
    parser.add_argument("--gameassembly-function-pointer-table-probe", default=None)
    parser.add_argument("--gameassembly-metadata-registration-candidate-taxonomy", default=None)
    parser.add_argument("--gameassembly-global-metadata-owner-probe", default=None)
    parser.add_argument("--global-metadata-transform-probe", default=None)
    parser.add_argument("--global-metadata-loader-scan", default=None)
    parser.add_argument("--nep2-metadata-loader-deep-slice", default=None)
    parser.add_argument("--nep2-read-mapping-owner-scan", default=None)
    parser.add_argument("--nep2-init-data-owner-scan", default=None)
    parser.add_argument("--nep2-vector-candidate-provenance", default=None)
    parser.add_argument("--nep2-vector-wrapper-owner-probe", default=None)
    parser.add_argument("--nep2-file-helper-caller-provenance", default=None)
    parser.add_argument("--gameassembly-resolver-trace", default=None)
    parser.add_argument("--gameassembly-resolver-caller-trace", default=None)
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    queue = build_client_import_queue(
        repo_root=Path(args.repo_root),
        source_id=args.source_id,
        evidence_bundle_path=Path(args.evidence_bundle) if args.evidence_bundle else None,
        client_resource_surface_gap_scan_path=(
            Path(args.client_resource_surface_gap_scan)
            if args.client_resource_surface_gap_scan
            else None
        ),
        ns_bundle_format_index_path=(
            Path(args.ns_bundle_format_index) if args.ns_bundle_format_index else None
        ),
        normalized_staging_path=Path(args.normalized_staging) if args.normalized_staging else None,
        decoded_hero_audit_path=Path(args.decoded_hero_audit)
        if args.decoded_hero_audit
        else None,
        luascripts_catalog_path=Path(args.luascripts_catalog) if args.luascripts_catalog else None,
        lua_crypto_evidence_path=Path(args.lua_crypto_evidence)
        if args.lua_crypto_evidence
        else None,
        luascripts_cipher_profile_path=(
            Path(args.luascripts_cipher_profile) if args.luascripts_cipher_profile else None
        ),
        luascripts_variant_corpus_path=(
            Path(args.luascripts_variant_corpus) if args.luascripts_variant_corpus else None
        ),
        textasset_payload_owner_trace_path=(
            Path(args.textasset_payload_owner_trace)
            if args.textasset_payload_owner_trace
            else None
        ),
        serialized_textasset_layout_path=(
            Path(args.serialized_textasset_layout)
            if args.serialized_textasset_layout
            else None
        ),
        serialized_textasset_resolution_path=(
            Path(args.serialized_textasset_resolution)
            if args.serialized_textasset_resolution
            else None
        ),
        resolved_payload_native_anchor_scan_path=(
            Path(args.resolved_payload_native_anchor_scan)
            if args.resolved_payload_native_anchor_scan
            else None
        ),
        textasset_xlua_boundary_ledger_path=(
            Path(args.textasset_xlua_boundary_ledger)
            if args.textasset_xlua_boundary_ledger
            else None
        ),
        nep2_luascripts_evidence_path=Path(args.nep2_luascripts_evidence)
        if args.nep2_luascripts_evidence
        else None,
        gameassembly_route_trace_path=Path(args.gameassembly_route_trace)
        if args.gameassembly_route_trace
        else None,
        nep2_init_bridge_path=Path(args.nep2_init_bridge) if args.nep2_init_bridge else None,
        native_boundary_trace_path=(
            Path(args.native_boundary_trace) if args.native_boundary_trace else None
        ),
        runtime_init_route_path=Path(args.runtime_init_route)
        if args.runtime_init_route
        else None,
        runtime_init_registry_probe_path=(
            Path(args.runtime_init_registry_probe)
            if args.runtime_init_registry_probe
            else None
        ),
        gameassembly_codegen_module_probe_path=(
            Path(args.gameassembly_codegen_module_probe)
            if args.gameassembly_codegen_module_probe
            else None
        ),
        gameassembly_registration_anchor_probe_path=(
            Path(args.gameassembly_registration_anchor_probe)
            if args.gameassembly_registration_anchor_probe
            else None
        ),
        gameassembly_registration_layout_probe_path=(
            Path(args.gameassembly_registration_layout_probe)
            if args.gameassembly_registration_layout_probe
            else None
        ),
        gameassembly_registration_pair_context_probe_path=(
            Path(args.gameassembly_registration_pair_context_probe)
            if args.gameassembly_registration_pair_context_probe
            else None
        ),
        gameassembly_initializer_dispatch_trace_path=(
            Path(args.gameassembly_initializer_dispatch_trace)
            if args.gameassembly_initializer_dispatch_trace
            else None
        ),
        gameassembly_function_pointer_table_probe_path=(
            Path(args.gameassembly_function_pointer_table_probe)
            if args.gameassembly_function_pointer_table_probe
            else None
        ),
        gameassembly_metadata_registration_candidate_taxonomy_path=(
            Path(args.gameassembly_metadata_registration_candidate_taxonomy)
            if args.gameassembly_metadata_registration_candidate_taxonomy
            else None
        ),
        gameassembly_global_metadata_owner_probe_path=(
            Path(args.gameassembly_global_metadata_owner_probe)
            if args.gameassembly_global_metadata_owner_probe
            else None
        ),
        global_metadata_transform_probe_path=(
            Path(args.global_metadata_transform_probe)
            if args.global_metadata_transform_probe
            else None
        ),
        global_metadata_loader_scan_path=(
            Path(args.global_metadata_loader_scan) if args.global_metadata_loader_scan else None
        ),
        nep2_metadata_loader_deep_slice_path=(
            Path(args.nep2_metadata_loader_deep_slice)
            if args.nep2_metadata_loader_deep_slice
            else None
        ),
        nep2_read_mapping_owner_scan_path=(
            Path(args.nep2_read_mapping_owner_scan)
            if args.nep2_read_mapping_owner_scan
            else None
        ),
        nep2_init_data_owner_scan_path=(
            Path(args.nep2_init_data_owner_scan)
            if args.nep2_init_data_owner_scan
            else None
        ),
        nep2_vector_candidate_provenance_path=(
            Path(args.nep2_vector_candidate_provenance)
            if args.nep2_vector_candidate_provenance
            else None
        ),
        nep2_vector_wrapper_owner_probe_path=(
            Path(args.nep2_vector_wrapper_owner_probe)
            if args.nep2_vector_wrapper_owner_probe
            else None
        ),
        nep2_file_helper_caller_provenance_path=(
            Path(args.nep2_file_helper_caller_provenance)
            if args.nep2_file_helper_caller_provenance
            else None
        ),
        gameassembly_resolver_trace_path=Path(args.gameassembly_resolver_trace)
        if args.gameassembly_resolver_trace
        else None,
        gameassembly_resolver_caller_trace_path=Path(args.gameassembly_resolver_caller_trace)
        if args.gameassembly_resolver_caller_trace
        else None,
    )
    write_client_import_queue(queue, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": queue.source_id,
                "queue_item_count": queue.queue_item_count,
                "queue_type_counts": queue.queue_type_counts,
                "readiness_counts": queue.readiness_counts,
                "safe_for_publish": queue.publish_readiness.get("safe_for_publish"),
                "auto_publish_allowed": queue.publish_readiness.get("auto_publish_allowed"),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
