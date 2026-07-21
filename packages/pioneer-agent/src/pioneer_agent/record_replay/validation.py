"""Dependency-free validation shared by WSL and standalone Windows entrypoints."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import stat
from typing import Any, NamedTuple
import unicodedata
from uuid import UUID


class RegularFileIdentity(NamedTuple):
    """Stable facts observed while a regular file descriptor was pinned."""

    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int
    sha256: str


class BoundedFileRead(NamedTuple):
    payload: bytes
    identity: RegularFileIdentity


def read_bounded_regular_file(
    path: Path,
    *,
    max_bytes: int,
    label: str,
) -> BoundedFileRead:
    """Read a non-linked regular file through one descriptor with a hard cap.

    Component checks and the final path lookup are repeated after the read.  This
    closes ordinary leaf replacement and in-place rewrite races, but it is not a
    platform-specific, handle-pinned walk of every parent directory.
    """

    if max_bytes < 0:
        raise ValueError("file size limit cannot be negative")
    _reject_linked_path_components(path, label=label)
    flags = os.O_RDONLY
    if hasattr(os, "O_BINARY"):
        flags |= os.O_BINARY
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    try:
        descriptor = os.open(path, flags)
    except OSError as exc:
        raise ValueError(f"{label} is unreadable") from exc
    try:
        before = os.fstat(descriptor)
        _validate_opened_regular_file(before, max_bytes=max_bytes, label=label)

        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining > 0:
            chunk = os.read(descriptor, min(remaining, 65_536))
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        payload = b"".join(chunks)
        if len(payload) > max_bytes:
            raise ValueError(f"{label} exceeds the fixed size limit")

        after = os.fstat(descriptor)
        if _descriptor_metadata_fingerprint(after) != _descriptor_metadata_fingerprint(
            before
        ):
            raise ValueError(f"{label} changed while it was read")
        if len(payload) != after.st_size:
            raise ValueError(f"{label} changed while it was read")

        _reject_linked_path_components(path, label=label)
        try:
            current = os.stat(path, follow_symlinks=False)
        except OSError as exc:
            raise ValueError(f"{label} changed while it was read") from exc
        _validate_opened_regular_file(current, max_bytes=max_bytes, label=label)
        if _path_binding_fingerprint(current) != _path_binding_fingerprint(after):
            raise ValueError(f"{label} changed while it was read")

        identity = RegularFileIdentity(
            device=after.st_dev,
            inode=after.st_ino,
            size=after.st_size,
            modified_ns=after.st_mtime_ns,
            changed_ns=after.st_ctime_ns,
            sha256=hashlib.sha256(payload).hexdigest(),
        )
        return BoundedFileRead(payload=payload, identity=identity)
    finally:
        os.close(descriptor)


def load_strict_json_bytes(payload: bytes) -> Any:
    """Decode one RFC-compatible JSON value without ambiguous extensions."""

    def reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError(f"duplicate JSON key: {key}")
            value[key] = item
        return value

    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON value is forbidden: {value}")

    return json.loads(
        payload.decode("utf-8"),
        object_pairs_hook=reject_duplicate_pairs,
        parse_constant=reject_constant,
    )


def reject_linked_path_components(path: Path, *, label: str) -> None:
    """Reject symlinks and Windows reparse points in every existing component."""

    _reject_linked_path_components(path, label=label)


def _reject_linked_path_components(path: Path, *, label: str) -> None:
    absolute = path.absolute()
    current = Path(absolute.anchor)
    parts = absolute.parts[1:] if absolute.anchor else absolute.parts
    for index, part in enumerate(parts):
        current /= part
        try:
            metadata = os.lstat(current)
        except OSError as exc:
            raise ValueError(f"{label} path is unreadable") from exc
        is_reparse_point = bool(
            getattr(metadata, "st_file_attributes", 0)
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
        if stat.S_ISLNK(metadata.st_mode) or is_reparse_point:
            raise ValueError(f"{label} path cannot contain symlinks or reparse points")
        if index < len(parts) - 1 and not stat.S_ISDIR(metadata.st_mode):
            raise ValueError(f"{label} parent must be a directory")


def _validate_opened_regular_file(
    metadata: os.stat_result,
    *,
    max_bytes: int,
    label: str,
) -> None:
    is_reparse_point = bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )
    if not stat.S_ISREG(metadata.st_mode) or is_reparse_point:
        raise ValueError(f"{label} must be a non-reparse regular file")
    if metadata.st_nlink != 1:
        raise ValueError(f"{label} must not be hard-linked")
    if metadata.st_size > max_bytes:
        raise ValueError(f"{label} exceeds the fixed size limit")


def _descriptor_metadata_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    """Metadata that must remain exact on the same open descriptor."""

    return _stable_file_fingerprint(metadata) + (
        metadata.st_ctime_ns,
    )


def _path_binding_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    """Metadata used to bind a final path lookup back to the open handle.

    Windows can report slightly different ``st_ctime_ns`` values for ``fstat``
    and ``stat(path)`` on an unchanged file.  Descriptor-to-descriptor checks
    still include ctime; only this cross-API comparison omits it on Windows.
    """

    fingerprint = _stable_file_fingerprint(metadata)
    if os.name != "nt":
        fingerprint += (metadata.st_ctime_ns,)
    return fingerprint


def _stable_file_fingerprint(metadata: os.stat_result) -> tuple[int, ...]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mode,
        metadata.st_nlink,
        metadata.st_size,
        metadata.st_mtime_ns,
    )


def validate_workflow_name(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 120:
        raise ValueError("workflow_name must contain between 1 and 120 characters")
    if value.strip() != value or not value:
        raise ValueError("workflow_name must be trimmed and non-empty")
    if len(value.splitlines()) != 1 or any(
        unicodedata.category(character).startswith("C") for character in value
    ):
        raise ValueError("workflow_name cannot be multiline or contain control characters")
    return value


def validate_canonical_uuid(value: str, *, field_name: str) -> str:
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be a canonical UUID")
    try:
        parsed = UUID(value)
    except (ValueError, AttributeError) as exc:
        raise ValueError(f"{field_name} must be a canonical UUID") from exc
    if str(parsed) != value:
        raise ValueError(f"{field_name} must be a canonical lowercase UUID")
    return value


def validate_identifier(value: str, *, field_name: str, max_length: int = 80) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= max_length
        or re.fullmatch(r"[a-z0-9][a-z0-9._-]*", value) is None
    ):
        raise ValueError(
            f"{field_name} must be a lowercase ASCII identifier of at most {max_length} characters"
        )
    return value


def validate_reviewer_id(value: str) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= 80
        or value.strip() != value
        or re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._@-]*", value) is None
    ):
        raise ValueError("reviewer id contains unsupported characters")
    return value


def validate_annotation_text(
    value: str,
    *,
    field_name: str,
    max_length: int = 500,
) -> str:
    if (
        not isinstance(value, str)
        or not 1 <= len(value) <= max_length
        or value.strip() != value
        or len(value.splitlines()) != 1
        or any(unicodedata.category(character).startswith("C") for character in value)
    ):
        raise ValueError(
            f"{field_name} must be trimmed single-line text of at most {max_length} characters"
        )
    return value


def validate_unique_strings(values: list[str], *, field_name: str) -> list[str]:
    if len(values) != len(set(values)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return values
