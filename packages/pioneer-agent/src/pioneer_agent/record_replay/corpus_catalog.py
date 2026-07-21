"""Canonical, read-only corpus audit for Record & Replay datasets.

The catalog closes two narrowly scoped gaps left by a single dataset audit:
exact identity leakage across registries and content-addressed lineage inside one
configured development-artifact root.  It still does not expose holdout oracle
labels, prove human capture provenance, run an image model, or grant authority.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path, PurePosixPath
import stat
from typing import Any, Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StrictBool,
    ValidationError,
    field_validator,
    model_validator,
)

from pioneer_agent.record_replay.dataset_registry import (
    AuditedDatasetRegistry,
    DatasetRiskClass,
    SplitStatus,
    audit_dataset_registry_bundle,
)
from pioneer_agent.record_replay.validation import (
    load_strict_json_bytes,
    read_bounded_regular_file,
    reject_linked_path_components,
    validate_canonical_uuid,
    validate_identifier,
    validate_unique_strings,
)


CORPUS_CATALOG_SCHEMA_VERSION = 1
MAX_CATALOG_BYTES = 1_048_576
MAX_DEVELOPMENT_ARTIFACT_BYTES = 67_108_864
MAX_TOTAL_DEVELOPMENT_ARTIFACT_BYTES = 268_435_456
MAX_CATALOG_RAW_EVENTS_BYTES = 536_870_912
MAX_CATALOG_RAW_FRAME_BYTES = 2_147_483_648
MAX_CATALOG_SESSIONS = 4_096
MAX_CATALOG_REGISTRIES = 128
MAX_CATALOG_ARTIFACTS = 512
MAX_INVENTORY_FILES = 1_024
MAX_INVENTORY_DEPTH = 12
SHA256_PATTERN = r"^[0-9a-f]{64}$"

CatalogStatus = Literal["collecting", "frozen", "retired"]


class CatalogRegistryReference(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dataset_id: str
    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)

    @field_validator("dataset_id")
    @classmethod
    def _dataset_id(cls, value: str) -> str:
        return validate_identifier(value, field_name="dataset_id", max_length=120)

    @field_validator("path")
    @classmethod
    def _registry_path(cls, value: str) -> str:
        value = _validate_relative_file_path(value, field_name="registry path")
        if PurePosixPath(value).suffix != ".json":
            raise ValueError("registry path must name a JSON file")
        return value


class DevelopmentLineageArtifact(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    artifact_id: str
    path: str
    sha256: str = Field(pattern=SHA256_PATTERN)
    source_session_ids: list[str] = Field(default_factory=list)
    dependency_artifact_ids: list[str] = Field(default_factory=list)

    @field_validator("artifact_id")
    @classmethod
    def _artifact_id(cls, value: str) -> str:
        return validate_identifier(value, field_name="artifact_id", max_length=120)

    @field_validator("path")
    @classmethod
    def _artifact_path(cls, value: str) -> str:
        return _validate_relative_file_path(
            value, field_name="development artifact path"
        )

    @field_validator("source_session_ids")
    @classmethod
    def _source_sessions(cls, values: list[str]) -> list[str]:
        checked = [
            validate_canonical_uuid(value, field_name="source_session_id")
            for value in values
        ]
        return validate_unique_strings(checked, field_name="source_session_ids")

    @field_validator("dependency_artifact_ids")
    @classmethod
    def _dependencies(cls, values: list[str]) -> list[str]:
        checked = [
            validate_identifier(
                value, field_name="dependency_artifact_id", max_length=120
            )
            for value in values
        ]
        return validate_unique_strings(
            checked, field_name="dependency_artifact_ids"
        )

    @model_validator(mode="after")
    def _has_lineage_and_no_self_dependency(self) -> DevelopmentLineageArtifact:
        if not self.source_session_ids and not self.dependency_artifact_ids:
            raise ValueError(
                "development artifact requires a source session or artifact dependency"
            )
        if self.artifact_id in self.dependency_artifact_ids:
            raise ValueError("development artifact cannot depend on itself")
        return self


class CorpusCatalog(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal[1] = CORPUS_CATALOG_SCHEMA_VERSION
    artifact_type: Literal["record_replay_corpus_catalog"] = (
        "record_replay_corpus_catalog"
    )
    corpus_id: str
    catalog_id: str
    catalog_status: CatalogStatus = "collecting"
    registry_inventory_policy: Literal["closed_root_all_regular_files"] = (
        "closed_root_all_regular_files"
    )
    development_artifact_inventory_policy: Literal[
        "closed_root_all_regular_files"
    ] = "closed_root_all_regular_files"
    registries: list[CatalogRegistryReference] = Field(
        min_length=1, max_length=MAX_CATALOG_REGISTRIES
    )
    development_artifacts: list[DevelopmentLineageArtifact] = Field(
        default_factory=list, max_length=MAX_CATALOG_ARTIFACTS
    )
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False

    @field_validator("corpus_id", "catalog_id")
    @classmethod
    def _identifier(cls, value: str, info: Any) -> str:
        return validate_identifier(value, field_name=info.field_name, max_length=120)

    @field_validator("schema_version", mode="before")
    @classmethod
    def _strict_schema_version(cls, value: object) -> object:
        if type(value) is not int or value != CORPUS_CATALOG_SCHEMA_VERSION:
            raise ValueError("schema_version must be integer 1")
        return value

    @field_validator(
        "live_dispatch_allowed",
        "safe_for_live_replay",
        "terminal_source_eligible",
        "closure_eligible",
        "knowledge_publication_allowed",
        mode="before",
    )
    @classmethod
    def _strict_false_safety_flag(cls, value: object, info: Any) -> object:
        if value is not False:
            raise ValueError(f"{info.field_name} must be boolean false")
        return value

    @model_validator(mode="after")
    def _references_are_unique(self) -> CorpusCatalog:
        _require_unique(
            [entry.dataset_id for entry in self.registries],
            label="catalog dataset id",
        )
        _require_unique(
            [entry.path for entry in self.registries], label="catalog registry path"
        )
        _require_unique(
            [entry.sha256 for entry in self.registries],
            label="catalog registry SHA256",
        )
        _require_unique(
            [entry.artifact_id for entry in self.development_artifacts],
            label="development artifact id",
        )
        _require_unique(
            [entry.path for entry in self.development_artifacts],
            label="development artifact path",
        )
        _require_unique(
            [entry.sha256 for entry in self.development_artifacts],
            label="development artifact SHA256",
        )
        return self


class CatalogDatasetSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    dataset_id: str
    workflow_id: str
    risk_class: DatasetRiskClass
    split_status: SplitStatus
    session_count: int = Field(ge=0)
    coverage_ready: StrictBool


class CorpusCatalogAuditReport(BaseModel):
    """Scoped corpus proof that remains categorically non-executable."""

    model_config = ConfigDict(extra="forbid", strict=True)

    status: Literal["valid"] = "valid"
    catalog_sha256: str = Field(pattern=SHA256_PATTERN)
    corpus_id: str
    catalog_id: str
    catalog_status: CatalogStatus
    registry_count: int = Field(ge=1)
    session_count: int = Field(ge=0)
    development_artifact_count: int = Field(ge=0)
    integrity_valid: Literal[True] = True
    registry_internal_leak_free: Literal[True] = True
    cross_registry_exact_leak_free: Literal[True] = True
    corpus_catalog_verified: Literal[True] = True
    registry_inventory_closed: Literal[True] = True
    development_artifact_inventory_closed: Literal[True] = True
    development_lineage_verified: Literal[True] = True
    development_lineage_scope: Literal[
        "configured_closed_artifacts_root"
    ] = "configured_closed_artifacts_root"
    holdout_contamination_detected: Literal[False] = False
    holdout_oracle_verified: Literal[False] = False
    human_capture_provenance_verified: Literal[False] = False
    visual_near_duplicate_checked: Literal[False] = False
    structured_start_state_verified: Literal[False] = False
    filesystem_race_hardened: Literal[False] = False
    image_model_exercised: Literal[False] = False
    independent_eval_ready: Literal[False] = False
    coverage_scope: Literal["provisional_policy_floor_only"] = (
        "provisional_policy_floor_only"
    )
    coverage_ready: StrictBool
    dataset_summaries: list[CatalogDatasetSummary]
    blockers: list[str]
    execution_authority: Literal["none"] = "none"
    live_dispatch_allowed: Literal[False] = False
    safe_for_live_replay: Literal[False] = False
    manual_promotion_required: Literal[True] = True
    terminal_source_eligible: Literal[False] = False
    closure_eligible: Literal[False] = False
    knowledge_publication_allowed: Literal[False] = False


@dataclass(frozen=True)
class LoadedCorpusCatalog:
    path: Path
    sha256: str
    catalog: CorpusCatalog


@dataclass(frozen=True)
class _InventoryIdentity:
    device: int
    inode: int
    mode: int
    size: int
    modified_ns: int
    changed_ns: int


def load_corpus_catalog(path: Path) -> LoadedCorpusCatalog:
    read = read_bounded_regular_file(
        path, max_bytes=MAX_CATALOG_BYTES, label="corpus catalog"
    )
    try:
        value = load_strict_json_bytes(read.payload)
        catalog = CorpusCatalog.model_validate(value)
    except (UnicodeDecodeError, ValueError, ValidationError) as exc:
        raise ValueError("corpus catalog is invalid") from exc
    return LoadedCorpusCatalog(
        path=path.resolve(strict=True),
        sha256=read.identity.sha256,
        catalog=catalog,
    )


def audit_corpus_catalog(
    catalog_path: Path,
    *,
    registries_root: Path,
    sessions_root: Path,
    reviews_root: Path,
    artifacts_root: Path,
) -> CorpusCatalogAuditReport:
    """Audit a closed registry inventory and a closed development-artifact DAG."""

    loaded = load_corpus_catalog(catalog_path)
    catalog = loaded.catalog
    registries_root = _resolve_directory_root(
        registries_root, label="registries root"
    )
    artifacts_root = _resolve_directory_root(
        artifacts_root, label="development artifacts root"
    )
    registry_inventory_before = _snapshot_closed_root(registries_root)
    artifact_inventory_before = _snapshot_closed_root(artifacts_root)
    expected_registry_paths = {entry.path for entry in catalog.registries}
    expected_artifact_paths = {
        entry.path for entry in catalog.development_artifacts
    }
    _require_closed_inventory(
        registry_inventory_before,
        expected_registry_paths,
        label="registry inventory",
    )
    _require_closed_inventory(
        artifact_inventory_before,
        expected_artifact_paths,
        label="development artifact inventory",
    )

    audited_registries: list[AuditedDatasetRegistry] = []
    dataset_summaries: list[CatalogDatasetSummary] = []
    session_splits: dict[str, str] = {}
    declared_artifact_sources: dict[str, set[str]] = {}
    workflow_contracts: dict[str, tuple[str, str]] = {}
    total_session_events_bytes = 0
    total_session_frame_bytes = 0
    exact_identities: dict[str, dict[str, str]] = {
        "session id": {},
        "events SHA256": {},
        "capture group": {},
        "annotation id": {},
        "annotation SHA256": {},
        "encoded frame SHA256": {},
        "source PNG SHA256": {},
    }

    for reference in catalog.registries:
        registry_path = _safe_existing_child(registries_root, reference.path)
        audited = audit_dataset_registry_bundle(
            registry_path,
            sessions_root=sessions_root,
            reviews_root=reviews_root,
            max_corpus_events_bytes=(
                MAX_CATALOG_RAW_EVENTS_BYTES - total_session_events_bytes
            ),
            max_corpus_frame_bytes=(
                MAX_CATALOG_RAW_FRAME_BYTES - total_session_frame_bytes
            ),
        )
        total_session_events_bytes += audited.events_bytes
        total_session_frame_bytes += audited.frame_bytes
        if audited.loaded_registry.sha256 != reference.sha256:
            raise ValueError("catalog registry SHA256 does not match the registry")
        registry = audited.loaded_registry.registry
        if registry.dataset_id != reference.dataset_id:
            raise ValueError("catalog dataset id does not match the registry")
        if registry.corpus_id != catalog.corpus_id:
            raise ValueError("catalog corpus id does not match a registry")
        contract_key = (
            registry.risk_class,
            registry.countable_semantic_contract.model_dump_json(),
        )
        previous_contract = workflow_contracts.setdefault(
            registry.workflow_id, contract_key
        )
        if previous_contract != contract_key:
            raise ValueError("one workflow has conflicting semantic contracts")

        for identity in audited.session_identities:
            owner = f"{registry.dataset_id}/{identity.session_id}"
            _claim_cross_unique(
                exact_identities["session id"],
                identity.session_id,
                owner,
                label="session id",
            )
            _claim_cross_unique(
                exact_identities["events SHA256"],
                identity.source_events_sha256,
                owner,
                label="events SHA256",
            )
            _claim_cross_unique(
                exact_identities["capture group"],
                identity.capture_group_id,
                owner,
                label="capture group",
            )
            _claim_cross_unique(
                exact_identities["annotation id"],
                identity.annotation_id,
                owner,
                label="annotation id",
            )
            _claim_cross_unique(
                exact_identities["annotation SHA256"],
                identity.annotation_sha256,
                owner,
                label="annotation SHA256",
            )
            for digest in identity.encoded_frame_sha256s:
                _claim_cross_unique(
                    exact_identities["encoded frame SHA256"],
                    digest,
                    owner,
                    label="encoded frame SHA256",
                )
            for digest in identity.source_png_sha256s:
                _claim_cross_unique(
                    exact_identities["source PNG SHA256"],
                    digest,
                    owner,
                    label="source PNG SHA256",
                )
            session_splits[identity.session_id] = identity.split
            if len(session_splits) > MAX_CATALOG_SESSIONS:
                raise ValueError("corpus catalog exceeds its session-count limit")

        for artifact in registry.development_artifacts:
            declared_artifact_sources.setdefault(artifact.artifact_id, set()).update(
                artifact.source_session_ids
            )
        audited_registries.append(audited)
        dataset_summaries.append(
            CatalogDatasetSummary(
                dataset_id=registry.dataset_id,
                workflow_id=registry.workflow_id,
                risk_class=registry.risk_class,
                split_status=registry.split_status,
                session_count=len(audited.session_identities),
                coverage_ready=audited.report.coverage_ready,
            )
        )

    artifacts_by_id = {
        artifact.artifact_id: artifact for artifact in catalog.development_artifacts
    }
    if set(declared_artifact_sources) - set(artifacts_by_id):
        raise ValueError(
            "a registry development artifact is missing from the corpus catalog"
        )
    total_artifact_bytes = 0
    seen_artifact_hashes: dict[str, str] = {}
    for artifact in catalog.development_artifacts:
        artifact_path = _safe_existing_child(artifacts_root, artifact.path)
        remaining = MAX_TOTAL_DEVELOPMENT_ARTIFACT_BYTES - total_artifact_bytes
        if remaining < 0:
            raise ValueError("development artifact corpus exceeds its size limit")
        read = read_bounded_regular_file(
            artifact_path,
            max_bytes=min(MAX_DEVELOPMENT_ARTIFACT_BYTES, remaining),
            label="development artifact",
        )
        total_artifact_bytes += len(read.payload)
        if read.identity.sha256 != artifact.sha256:
            raise ValueError(
                "catalog development artifact SHA256 does not match the file"
            )
        _claim_cross_unique(
            seen_artifact_hashes,
            artifact.sha256,
            artifact.artifact_id,
            label="development artifact SHA256",
        )
        if set(artifact.source_session_ids) != declared_artifact_sources.get(
            artifact.artifact_id, set()
        ):
            raise ValueError(
                "catalog artifact source sessions do not match registry declarations"
            )
        for session_id in artifact.source_session_ids:
            split = session_splits.get(session_id)
            if split is None:
                raise ValueError(
                    "development artifact references a session outside the catalog"
                )
            if split == "holdout":
                raise ValueError("holdout session cannot feed a development artifact")
        for dependency_id in artifact.dependency_artifact_ids:
            if dependency_id not in artifacts_by_id:
                raise ValueError(
                    "development artifact dependency is missing from the catalog"
                )

    _verify_lineage_dag(artifacts_by_id)
    if registry_inventory_before != _snapshot_closed_root(registries_root):
        raise ValueError("registry inventory changed while the catalog was audited")
    if artifact_inventory_before != _snapshot_closed_root(artifacts_root):
        raise ValueError(
            "development artifact inventory changed while the catalog was audited"
        )

    all_dataset_coverage_ready = all(
        audited.report.coverage_ready for audited in audited_registries
    )
    coverage_ready = catalog.catalog_status == "frozen" and all_dataset_coverage_ready
    blockers = _catalog_blockers(
        catalog=catalog,
        audited_registries=audited_registries,
    )
    return CorpusCatalogAuditReport(
        catalog_sha256=loaded.sha256,
        corpus_id=catalog.corpus_id,
        catalog_id=catalog.catalog_id,
        catalog_status=catalog.catalog_status,
        registry_count=len(audited_registries),
        session_count=len(session_splits),
        development_artifact_count=len(catalog.development_artifacts),
        coverage_ready=coverage_ready,
        dataset_summaries=sorted(
            dataset_summaries, key=lambda summary: summary.dataset_id
        ),
        blockers=blockers,
    )


def _catalog_blockers(
    *,
    catalog: CorpusCatalog,
    audited_registries: list[AuditedDatasetRegistry],
) -> list[str]:
    blockers: list[str] = []
    if catalog.catalog_status == "collecting":
        blockers.append("corpus_catalog_is_still_collecting")
    elif catalog.catalog_status == "retired":
        blockers.append("corpus_catalog_is_retired")
    blockers.extend(
        f"dataset_coverage_not_ready:{audited.loaded_registry.registry.dataset_id}"
        for audited in audited_registries
        if not audited.report.coverage_ready
    )
    blockers.extend(
        [
            "holdout_oracle_unverified",
            "human_capture_provenance_unverified",
            "visual_near_duplicate_unchecked",
            "structured_start_state_unverified",
            "filesystem_parent_walk_not_handle_pinned",
            "image_model_not_exercised",
        ]
    )
    return blockers


def _verify_lineage_dag(
    artifacts_by_id: dict[str, DevelopmentLineageArtifact],
) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(artifact_id: str) -> None:
        if artifact_id in visited:
            return
        if artifact_id in visiting:
            raise ValueError("development artifact lineage contains a cycle")
        visiting.add(artifact_id)
        for dependency_id in artifacts_by_id[artifact_id].dependency_artifact_ids:
            visit(dependency_id)
        visiting.remove(artifact_id)
        visited.add(artifact_id)

    for artifact_id in artifacts_by_id:
        visit(artifact_id)


def _claim_cross_unique(
    seen: dict[str, str],
    key: str,
    owner: str,
    *,
    label: str,
) -> None:
    previous = seen.get(key)
    if previous is not None and previous != owner:
        raise ValueError(
            f"duplicate {label} across corpus entries: {previous}, {owner}"
        )
    seen[key] = owner


def _require_unique(values: list[str], *, label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"duplicate {label}")


def _resolve_directory_root(path: Path, *, label: str) -> Path:
    reject_linked_path_components(path, label=label)
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"{label} does not exist") from exc
    if not resolved.is_dir():
        raise ValueError(f"{label} is not a directory")
    return resolved


def _validate_relative_file_path(value: str, *, field_name: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 240
        or "\\" in value
        or ":" in value
        or any(ord(character) < 32 for character in value)
    ):
        raise ValueError(f"{field_name} must be a safe relative POSIX path")
    parsed = PurePosixPath(value)
    if (
        parsed.is_absolute()
        or str(parsed) != value
        or not parsed.parts
        or any(part in {"", ".", ".."} for part in parsed.parts)
    ):
        raise ValueError(f"{field_name} must stay beneath its configured root")
    for part in parsed.parts:
        if (
            part[0] in {" ", "."}
            or part[-1] in {" ", "."}
            or any(
                not (
                    character.isascii()
                    and (character.isalnum() or character in "._-")
                )
                for character in part
            )
        ):
            raise ValueError(f"{field_name} contains unsupported characters")
    return value


def _safe_existing_child(root: Path, relative: str) -> Path:
    _validate_relative_file_path(relative, field_name="catalog artifact path")
    candidate = root.joinpath(*PurePosixPath(relative).parts)
    reject_linked_path_components(candidate, label="catalog artifact")
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise ValueError("catalog artifact does not exist") from exc
    if resolved == root or root not in resolved.parents or not resolved.is_file():
        raise ValueError("catalog artifact must be a regular file beneath its root")
    return resolved


def _snapshot_closed_root(root: Path) -> dict[str, _InventoryIdentity]:
    inventory: dict[str, _InventoryIdentity] = {}
    stack: list[tuple[Path, PurePosixPath, int]] = [(root, PurePosixPath(), 0)]
    while stack:
        current, relative_parent, depth = stack.pop()
        if depth > MAX_INVENTORY_DEPTH:
            raise ValueError("closed inventory exceeds its directory depth limit")
        try:
            entries = sorted(os.scandir(current), key=lambda entry: entry.name)
        except OSError as exc:
            raise ValueError("closed inventory is unreadable") from exc
        for entry in entries:
            relative = relative_parent / entry.name
            relative_value = relative.as_posix()
            _validate_relative_file_path(
                relative_value, field_name="closed inventory path"
            )
            try:
                metadata = entry.stat(follow_symlinks=False)
            except OSError as exc:
                raise ValueError("closed inventory entry is unreadable") from exc
            is_reparse_point = bool(
                getattr(metadata, "st_file_attributes", 0)
                & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
            )
            if entry.is_symlink() or is_reparse_point:
                raise ValueError("closed inventory cannot contain linked entries")
            if stat.S_ISDIR(metadata.st_mode):
                stack.append((Path(entry.path), relative, depth + 1))
                continue
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_nlink != 1:
                raise ValueError(
                    "closed inventory may contain only non-linked regular files"
                )
            inventory[relative_value] = _InventoryIdentity(
                device=metadata.st_dev,
                inode=metadata.st_ino,
                mode=metadata.st_mode,
                size=metadata.st_size,
                modified_ns=metadata.st_mtime_ns,
                changed_ns=metadata.st_ctime_ns,
            )
            if len(inventory) > MAX_INVENTORY_FILES:
                raise ValueError("closed inventory exceeds its file-count limit")
    return inventory


def _require_closed_inventory(
    inventory: dict[str, _InventoryIdentity],
    expected_paths: set[str],
    *,
    label: str,
) -> None:
    if set(inventory) != expected_paths:
        raise ValueError(f"{label} does not exactly match the corpus catalog")
