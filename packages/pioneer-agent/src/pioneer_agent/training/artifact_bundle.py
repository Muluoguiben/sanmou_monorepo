"""Local, bounded, content-verified training handoff bundles (no transport).

V1 is deliberately flat: manifest.json and listed JSON payload files only.
Imports return a verified in-memory snapshot and never modify source files.
Runtime provenance is a declaration, not proof of fresh on-policy sampling.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import math
import os
from pathlib import Path
import re
import stat
from typing import Annotated, Literal, Mapping

from pydantic import Field, ValidationError, model_validator
from sanmou_common.policy_contracts import PolicyRequest, SealedJson

from .contracts import (
    ArtifactRef, BatchIdentity, Bit, Digest, FrozenModel, Index, Name, ProjectionRequest, ProjectionResult,
)
from .projection import TrainingProjector

MANIFEST_NAME = "manifest.json"
PayloadKind = Literal["projection", "context", "tokens", "bootstrap_context", "bootstrap_state", "bootstrap_observation"]
_FILE_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,122}\.json\Z")
_VERSION_FIELDS = ("batch_id", "behavior_policy_revision", "critic_revision", "reference_revision",
                   "tokenizer_revision", "template_revision", "sampling_revision")


class BundleValidationError(ValueError):
    """The handoff package cannot be trusted or is outside its bounded format."""


class BundleLimits(FrozenModel):
    max_files: Annotated[int, Field(gt=0)] = 256
    max_manifest_bytes: Annotated[int, Field(gt=0)] = 256_000
    max_file_bytes: Annotated[int, Field(gt=0)] = 8_000_000
    max_total_bytes: Annotated[int, Field(gt=0)] = 64_000_000
    max_json_nodes: Annotated[int, Field(gt=0)] = 250_000
    max_json_depth: Annotated[int, Field(gt=0)] = 64


class BundleFile(FrozenModel):
    relative_path: Name
    artifact_id: Name
    kind: PayloadKind
    owner_projection_id: Name
    decision_id: Name | None = None
    invocation_id: Name | None = None
    sha256: Digest
    byte_length: Index
    media_type: Literal["application/json"] = "application/json"

    @model_validator(mode="after")
    def safe_flat_name_and_owner(self):
        if not _FILE_NAME.fullmatch(self.relative_path) or self.relative_path.casefold() == MANIFEST_NAME:
            raise ValueError("v1 payload paths must be safe, flat JSON filenames")
        step_owned = self.kind in {"context", "tokens"}
        if step_owned != (self.decision_id is not None and self.invocation_id is not None):
            raise ValueError("context/token files require exact decision and invocation owners")
        if not step_owned and (self.decision_id is not None or self.invocation_id is not None):
            raise ValueError("non-step files cannot claim a decision owner")
        if self.kind == "projection" and self.owner_projection_id != self.artifact_id:
            raise ValueError("projection file must own itself")
        return self


class BundleManifest(FrozenModel):
    schema_version: Literal["sanmou-training-bundle-v1"] = "sanmou-training-bundle-v1"
    projection_version: Literal["ppo-token-gae-v1"] = "ppo-token-gae-v1"
    source_kind: Literal["synthetic", "runtime"]
    batch_id: Name
    behavior_policy_revision: Name
    critic_revision: Name
    reference_revision: Name
    tokenizer_revision: Name
    template_revision: Name
    sampling_revision: Name
    files: tuple[BundleFile, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def unique_inventory(self):
        if len({f.relative_path.casefold() for f in self.files}) != len(self.files):
            raise ValueError("bundle contains duplicate or case-colliding filenames")
        if len({f.artifact_id for f in self.files}) != len(self.files):
            raise ValueError("bundle contains duplicate artifact identities")
        projection_ids = {f.artifact_id for f in self.files if f.kind == "projection"}
        if not projection_ids or any(f.owner_projection_id not in projection_ids for f in self.files):
            raise ValueError("every file must belong to a listed projection")
        return self


class TokenPayload(FrozenModel):
    """Original token payload, excluding artifact_ref to avoid a self-hash."""
    schema_version: Literal["sanmou-policy-tokens-v1"] = "sanmou-policy-tokens-v1"
    input_token_ids: tuple[Index, ...]
    response_token_ids: tuple[Index, ...]
    attention_mask: tuple[Bit, ...]
    position_ids: tuple[Index, ...]
    response_origins: tuple[Literal["policy", "tool", "environment", "template", "padding"], ...]
    policy_token_mask: tuple[Bit, ...]
    value_alignment_version: Literal["dense-last-attended-prefix-v1"] = "dense-last-attended-prefix-v1"


class BootstrapContextPayload(FrozenModel):
    """A next-state critic input, explicitly not a sent policy invocation."""
    schema_version: Literal["sanmou-bootstrap-context-v1"] = "sanmou-bootstrap-context-v1"
    identity: BatchIdentity
    cutoff_decision_index: Index
    builder_version: Name
    source_cutoff: Name
    state_artifact: ArtifactRef
    observation_artifact: ArtifactRef
    messages: SealedJson
    tools: SealedJson
    input_token_ids: tuple[Index, ...] = Field(min_length=1)
    attention_mask: tuple[Bit, ...]
    position_ids: tuple[Index, ...]

    @model_validator(mode="after")
    def actual_input_layout(self):
        if len(self.input_token_ids) != len(self.attention_mask) or len(self.input_token_ids) != len(self.position_ids):
            raise ValueError("bootstrap input arrays must describe the same actual context")
        if not any(self.attention_mask) or not isinstance(self.messages.value(), list) or not self.messages.value():
            raise ValueError("bootstrap requires actual nonempty messages and attended input")
        if not isinstance(self.tools.value(), list):
            raise ValueError("bootstrap tools must be an explicit array")
        return self


class BootstrapSourcePayload(FrozenModel):
    """Identity-bound sealed source; content truth remains the capture boundary's duty."""
    schema_version: Literal["sanmou-bootstrap-source-v1"] = "sanmou-bootstrap-source-v1"
    source_kind: Literal["state", "observation"]
    identity: BatchIdentity
    cutoff_decision_index: Index
    content: SealedJson

    @model_validator(mode="after")
    def source_is_structured(self):
        if not isinstance(self.content.value(), dict):
            raise ValueError("bootstrap state/observation source must be a sealed object")
        return self


class VerifiedProjection(FrozenModel):
    artifact_id: Name
    request: ProjectionRequest
    result: ProjectionResult


class VerifiedBundle(FrozenModel):
    bundle_digest: Digest
    manifest_sha256: Digest
    source_kind: Literal["synthetic", "runtime"]
    manifest: BundleManifest
    projections: tuple[VerifiedProjection, ...]
    # A hash-valid bundle cannot authenticate a game run or behavior sampler.
    on_policy_runtime_evidence: Literal[False] = False
    remote_transfer_verified: Literal[False] = False
    ms5_ready: Literal[False] = False


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _json_checked(raw: bytes, limits: BundleLimits):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BundleValidationError("duplicate JSON object key")
            result[key] = value
        return result

    def nonfinite(_):
        raise BundleValidationError("non-finite JSON number")

    try:
        value = json.loads(raw, object_pairs_hook=pairs, parse_constant=nonfinite)
    except (ValueError, UnicodeDecodeError, RecursionError) as exc:
        raise BundleValidationError("invalid JSON payload") from exc
    stack = [(value, 0)]
    nodes = 0
    while stack:
        item, depth = stack.pop()
        nodes += 1
        if nodes > limits.max_json_nodes or depth > limits.max_json_depth:
            raise BundleValidationError("JSON structural limit exceeded")
        if isinstance(item, dict):
            stack.extend((child, depth + 1) for child in item.values())
        elif isinstance(item, list):
            stack.extend((child, depth + 1) for child in item)
        elif isinstance(item, float) and not math.isfinite(item):
            raise BundleValidationError("non-finite JSON number")
    return value


def _parse(model, raw: bytes, limits: BundleLimits):
    decoded = _json_checked(raw, limits)
    try:
        parsed = model.model_validate_json(raw)
    except (ValidationError, ValueError) as exc:
        raise BundleValidationError(f"invalid {model.__name__} schema") from exc
    # Bundle files are complete serialized records. A missing field must not be
    # silently recreated from a DTO default (especially ready/version/masks).
    pending = [(decoded, parsed.model_dump(mode="json"))]
    while pending:
        actual, expected = pending.pop()
        if isinstance(expected, dict):
            if not isinstance(actual, dict) or set(actual) != set(expected):
                raise BundleValidationError(f"incomplete serialized {model.__name__} fields")
            pending.extend((actual[key], value) for key, value in expected.items())
        elif isinstance(expected, list):
            if not isinstance(actual, list) or len(actual) != len(expected):
                raise BundleValidationError(f"incomplete serialized {model.__name__} arrays")
            pending.extend(zip(actual, expected))
    return parsed


def _manifest(raw: bytes, limits: BundleLimits) -> BundleManifest:
    if len(raw) > limits.max_manifest_bytes:
        raise BundleValidationError("manifest byte limit exceeded")
    manifest = _parse(BundleManifest, raw, limits)
    if len(manifest.files) > limits.max_files:
        raise BundleValidationError("file count limit exceeded")
    if any(f.byte_length > limits.max_file_bytes for f in manifest.files):
        raise BundleValidationError("declared payload byte limit exceeded")
    if len(raw) + sum(f.byte_length for f in manifest.files) > limits.max_total_bytes:
        raise BundleValidationError("bundle byte limit exceeded")
    return manifest


def _verify_payloads(manifest: BundleManifest, manifest_raw: bytes,
                     payloads: Mapping[str, bytes], limits: BundleLimits) -> VerifiedBundle:
    if set(payloads) != {f.relative_path for f in manifest.files}:
        raise BundleValidationError("bundle inventory has missing or extra payloads")
    by_id = {f.artifact_id: f for f in manifest.files}
    for entry in manifest.files:
        raw = payloads[entry.relative_path]
        if type(raw) is not bytes or len(raw) != entry.byte_length or _sha(raw) != entry.sha256:
            raise BundleValidationError(f"payload hash or length mismatch: {entry.relative_path}")
        _json_checked(raw, limits)

    requests = {}
    for entry in manifest.files:
        if entry.kind != "projection":
            continue
        req = _parse(ProjectionRequest, payloads[entry.relative_path], limits)
        if any(getattr(req.identity, key) != getattr(manifest, key) for key in _VERSION_FIELDS):
            raise BundleValidationError("projection batch or frozen versions do not match manifest")
        requests[entry.artifact_id] = req
    identities = [(r.identity.role_session_id, r.identity.episode_id, r.identity.learning_segment_id)
                  for r in requests.values()]
    if len(set(identities)) != len(identities):
        raise BundleValidationError("duplicate projection segment identity")

    # Each episode contributes one ordered chain. IDs can be locally reused by
    # a different episode, but cannot duplicate or fork its own learning rows.
    episode_groups = {}
    for owner, req in requests.items():
        key = (req.identity.role_session_id, req.identity.episode_id)
        episode_groups.setdefault(key, []).append((owner, req))
    for members in episode_groups.values():
        if sum(req.prefix is None for _, req in members) != 1:
            raise BundleValidationError("each episode requires exactly one root and trusted continuation prefixes")
        decisions, invocations, indices = set(), set(), set()
        for _, req in members:
            for step in req.steps:
                if step.decision_id in decisions or step.invocation_id in invocations or step.decision_index in indices:
                    raise BundleValidationError("episode projections contain duplicate decisions/invocations or overlapping indices")
                decisions.add(step.decision_id)
                invocations.add(step.invocation_id)
                indices.add(step.decision_index)

    referenced = set(requests)
    def verify_ref(ref, owner, kind, decision=None, invocation=None):
        entry = by_id.get(ref.artifact_id)
        if entry is None:
            raise BundleValidationError("required referenced artifact is missing")
        if (entry.owner_projection_id, entry.kind, entry.decision_id, entry.invocation_id) != (
            owner, kind, decision, invocation
        ):
            raise BundleValidationError("artifact owner, kind or invocation does not match reference")
        if not ref.ready or (ref.sha256, ref.byte_length) != (entry.sha256, entry.byte_length):
            raise BundleValidationError("artifact reference does not match verified original bytes")
        referenced.add(entry.artifact_id)
        return payloads[entry.relative_path]

    episode_context_identity = {}
    for owner, req in requests.items():
        for step in req.steps:
            raw = verify_ref(step.context_artifact, owner, "context", step.decision_id, step.invocation_id)
            try:
                context = PolicyRequest.from_wire(_json_checked(raw, limits))
            except (ValidationError, ValueError, TypeError, KeyError) as exc:
                raise BundleValidationError("context must be an original policy-service-v1 request") from exc
            if context.payload != raw:
                raise BundleValidationError("policy context bytes must match the canonical sent request")
            if (context.episode_id, context.decision_id, context.invocation_id, context.binding_ref,
                context.context_id, context.manifest.sha256, context.manifest.tokenizer_revision,
                context.manifest.chat_template_revision, context.manifest.sampling.sha256) != (
                step.identity.episode_id, step.decision_id, step.invocation_id, step.identity.role_session_id,
                step.context_artifact.artifact_id, step.identity.behavior_policy_revision,
                step.identity.tokenizer_revision, step.identity.template_revision, step.identity.sampling_revision
            ):
                raise BundleValidationError("actual policy context identity or frozen policy versions differ")
            episode_key = (step.identity.role_session_id, step.identity.episode_id)
            task_identity = (context.run_id, context.task_ref)
            if episode_context_identity.setdefault(episode_key, task_identity) != task_identity:
                raise BundleValidationError("policy context run_id or task_ref changed within an episode")
            if step.tokens is not None:
                raw = verify_ref(step.tokens.artifact_ref, owner, "tokens", step.decision_id, step.invocation_id)
                tokens = _parse(TokenPayload, raw, limits)
                if tokens.model_dump(exclude={"schema_version"}) != step.tokens.model_dump(exclude={"artifact_ref"}):
                    raise BundleValidationError("original token payload differs from projection token layout")
        if req.bootstrap is not None:
            for kind, ref in (("state", req.bootstrap.next_state_artifact),
                              ("observation", req.bootstrap.next_observation_artifact)):
                raw = verify_ref(ref, owner, f"bootstrap_{kind}")
                source = _parse(BootstrapSourcePayload, raw, limits)
                if (source.source_kind, source.identity, source.cutoff_decision_index) != (
                    kind, req.bootstrap.identity, req.bootstrap.cutoff_decision_index
                ):
                    raise BundleValidationError("bootstrap source identity or cutoff differs")
            raw = verify_ref(req.bootstrap.next_context_artifact, owner, "bootstrap_context")
            context = _parse(BootstrapContextPayload, raw, limits)
            boundary = req.bootstrap
            if (context.identity, context.cutoff_decision_index, context.builder_version, context.source_cutoff,
                context.state_artifact, context.observation_artifact) != (
                boundary.identity, boundary.cutoff_decision_index, boundary.builder_version, boundary.source_cutoff,
                boundary.next_state_artifact, boundary.next_observation_artifact
            ):
                raise BundleValidationError("bootstrap context identity, cutoff or source artifacts differ")
    if referenced != set(by_id):
        raise BundleValidationError("bundle contains unreferenced artifact files")

    # A prefix is accepted only by recomputing the earlier included projection;
    # a caller-supplied cumulative count or self-declared hash is insufficient.
    by_request_digest = {req.digest(): owner for owner, req in requests.items()}
    if len(by_request_digest) != len(requests):
        raise BundleValidationError("duplicate projection content")
    completed = {}
    pending = dict(requests)
    prefix_children = set()
    for req in requests.values():
        if req.prefix is not None:
            if req.prefix.source_projection_sha256 in prefix_children:
                raise BundleValidationError("episode prefix lineage forks into multiple continuations")
            prefix_children.add(req.prefix.source_projection_sha256)
    projector = TrainingProjector()
    while pending:
        advanced = False
        for owner, req in tuple(pending.items()):
            if req.prefix is not None:
                previous = by_request_digest.get(req.prefix.source_projection_sha256)
                if previous is None:
                    raise BundleValidationError("prefix source projection is absent from bundle")
                if previous not in completed:
                    continue
                if req.prefix != completed[previous].result.next_prefix:
                    raise BundleValidationError("prefix counts or receipts differ from recomputed source")
                if (requests[previous].identity.role_session_id, requests[previous].identity.episode_id) != (
                    req.identity.role_session_id, req.identity.episode_id
                ):
                    raise BundleValidationError("prefix cannot link different episodes")
            result = projector.build(req)
            completed[owner] = VerifiedProjection(artifact_id=owner, request=req, result=result)
            del pending[owner]
            advanced = True
        if not advanced:
            raise BundleValidationError("cyclic or unresolved prefix lineage")
    return VerifiedBundle(
        bundle_digest=manifest.digest(), manifest_sha256=_sha(manifest_raw),
        source_kind=manifest.source_kind, manifest=manifest,
        projections=tuple(completed[key] for key in sorted(completed)),
    )


def _secure_platform():
    if (not all(hasattr(os, key) for key in ("O_NOFOLLOW", "O_DIRECTORY", "O_NONBLOCK"))
            or os.open not in os.supports_dir_fd or os.stat not in os.supports_dir_fd
            or os.mkdir not in os.supports_dir_fd or os.scandir not in os.supports_fd):
        raise BundleValidationError("secure bundle IO requires nofollow and descriptor-relative filesystem APIs")


def _absolute_parts(path) -> tuple[str, ...]:
    raw = os.fspath(path)
    if not isinstance(raw, str) or not raw.startswith("/") or "\x00" in raw:
        raise BundleValidationError("bundle location must be an absolute local path")
    parts = tuple(raw.split("/")[1:])
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise BundleValidationError("bundle location contains unresolved path components")
    return parts


def _directory_flags():
    return os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


@contextmanager
def _open_directory(path):
    _secure_platform()
    parts = _absolute_parts(path)
    fd = os.open("/", _directory_flags())
    try:
        for part in parts:
            child = os.open(part, _directory_flags(), dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def _signature(info):
    return (info.st_dev, info.st_ino, info.st_mode, info.st_nlink,
            info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _inventory(root_fd, max_entries):
    names = set()
    with os.scandir(root_fd) as entries:
        for entry in entries:
            names.add(entry.name)
            if len(names) > max_entries:
                raise BundleValidationError("directory entry limit exceeded")
            info = entry.stat(follow_symlinks=False)
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise BundleValidationError("directory has a non-regular or linked entry")
    return names


def _read_file(root_fd, name: str, max_bytes: int):
    fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=root_fd)
    try:
        before = os.fstat(fd)
        if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1:
            raise BundleValidationError("payload must be a single-link regular file")
        if before.st_size > max_bytes:
            raise BundleValidationError("file byte limit exceeded")
        chunks = []
        remaining = max_bytes + 1
        while remaining:
            chunk = os.read(fd, min(remaining, 64 * 1024))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        raw = b"".join(chunks)
        after = os.fstat(fd)
        named = os.stat(name, dir_fd=root_fd, follow_symlinks=False)
        if len(raw) > max_bytes or len(raw) != before.st_size or _signature(before) != _signature(after) or _signature(before) != _signature(named):
            raise BundleValidationError("file changed during bounded read")
        return raw, _signature(after)
    finally:
        os.close(fd)


def import_bundle(path: str | Path, *, limits: BundleLimits | None = None) -> VerifiedBundle:
    """Read and verify once; repeat imports return the same content identity."""
    limits = BundleLimits.model_validate(limits or BundleLimits())
    try:
        with _open_directory(path) as root_fd:
            root_before = _signature(os.fstat(root_fd))
            manifest_raw, manifest_stat = _read_file(root_fd, MANIFEST_NAME, limits.max_manifest_bytes)
            manifest = _manifest(manifest_raw, limits)
            expected = {MANIFEST_NAME, *(f.relative_path for f in manifest.files)}
            if _inventory(root_fd, limits.max_files + 1) != expected:
                raise BundleValidationError("bundle directory has missing or extra entries")
            payloads, signatures = {}, {MANIFEST_NAME: manifest_stat}
            for entry in manifest.files:
                raw, signature = _read_file(root_fd, entry.relative_path, min(entry.byte_length, limits.max_file_bytes))
                payloads[entry.relative_path] = raw
                signatures[entry.relative_path] = signature
            result = _verify_payloads(manifest, manifest_raw, payloads, limits)
            if _inventory(root_fd, limits.max_files + 1) != expected or _signature(os.fstat(root_fd)) != root_before:
                raise BundleValidationError("bundle directory changed during validation")
            for name, signature in signatures.items():
                if _signature(os.stat(name, dir_fd=root_fd, follow_symlinks=False)) != signature:
                    raise BundleValidationError("bundle file changed during validation")
            with _open_directory(path) as current_fd:
                if _signature(os.fstat(current_fd)) != root_before:
                    raise BundleValidationError("bundle directory was replaced during validation")
            return result
    except OSError as exc:
        raise BundleValidationError(f"unsafe or unavailable bundle filesystem entry: {exc.errno}") from exc


def _write_new(root_fd, name: str, raw: bytes):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=root_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise BundleValidationError("export destination is not a new single-link regular file")
        view = memoryview(raw)
        while view:
            count = os.write(fd, view)
            if count <= 0:
                raise BundleValidationError("incomplete bundle write")
            view = view[count:]
        os.fsync(fd)
    finally:
        os.close(fd)


def export_bundle(destination: str | Path, manifest: BundleManifest, payloads: Mapping[str, bytes],
                  *, limits: BundleLimits | None = None) -> VerifiedBundle:
    """Create a new directory, write originals unchanged, publish manifest last.

The existing parent directory must be trusted and present. Failure leaves the
new task directory for inspection; this module never deletes or overwrites it.
"""
    limits = BundleLimits.model_validate(limits or BundleLimits())
    manifest = BundleManifest.model_validate(manifest)
    manifest_raw = manifest.model_dump_json().encode("utf-8")
    manifest = _manifest(manifest_raw, limits)
    # Copy the mapping before any writes; bytes themselves are immutable.
    payloads = dict(payloads)
    _verify_payloads(manifest, manifest_raw, payloads, limits)
    parts = _absolute_parts(destination)
    if len(parts) < 2:
        raise BundleValidationError("export requires an existing non-root parent directory")
    parent = "/" + "/".join(parts[:-1])
    name = parts[-1]
    try:
        with _open_directory(parent) as parent_fd:
            os.mkdir(name, mode=0o700, dir_fd=parent_fd)
            created = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
            root_fd = os.open(name, _directory_flags(), dir_fd=parent_fd)
            try:
                if _signature(created) != _signature(os.fstat(root_fd)) or _inventory(root_fd, 0):
                    raise BundleValidationError("new export directory was replaced or populated")
                for entry in manifest.files:
                    _write_new(root_fd, entry.relative_path, payloads[entry.relative_path])
                # Check persisted originals before publishing the completion marker.
                for entry in manifest.files:
                    raw, _ = _read_file(root_fd, entry.relative_path, entry.byte_length)
                    if raw != payloads[entry.relative_path]:
                        raise BundleValidationError("exported original differs from supplied bytes")
                _write_new(root_fd, MANIFEST_NAME, manifest_raw)
                os.fsync(root_fd)
                os.fsync(parent_fd)
            finally:
                os.close(root_fd)
        return import_bundle(destination, limits=limits)
    except OSError as exc:
        raise BundleValidationError(f"bundle export requires a new safe directory: {exc.errno}") from exc
