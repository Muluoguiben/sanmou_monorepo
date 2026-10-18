from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

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

