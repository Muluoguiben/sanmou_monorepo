"""Prepare immutable, unreviewed provenance drafts from explicitly mapped Git sources.

Only reviewed-scope repository paths are readable. No source references are fetched,
no game/package archives are read, and no source, KB or review state is updated.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import date, datetime
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from qa_agent.knowledge.models import KnowledgeEntry
from qa_agent.knowledge.provenance import (
    KnowledgeProvenance, SourceCategory, audit_imports, canonical_digest, entry_digest,
)


SCRIPT = Path(__file__).resolve()
REPOSITORY = SCRIPT.parents[3]
SCRIPT_PATH = "packages/qa-agent/scripts/prepare_provenance_review.py"
PROTOCOL = "provenance-review-bundle-v1"
MAX_MAPPING_BYTES = 256 * 1024
MAX_SOURCE_BYTES = 2 * 1024 * 1024
MAX_TOTAL_SOURCE_BYTES = 8 * 1024 * 1024
MAX_RECORD_BYTES = 128 * 1024
KB_PREFIX = "packages/qa-agent/knowledge_sources/"
REA_FILES = {f"docs/research/rea/2026-10-18/data/{name}.json"
             for name in ("heroes", "skills", "gear", "fates", "mechanics", "reports")}
GUIDE_PREFIX = "packages/qa-agent/ingestion/raw/videos/"
GUIDE_RULE_PREFIX = "packages/qa-agent/ingestion/raw/rules/bilibili-"


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n").encode("utf-8")


def _json_load(raw: bytes) -> object:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(raw.decode("utf-8"), object_pairs_hook=unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON number")))


class MappingItem(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mapping_id: str = Field(min_length=1, max_length=160, pattern=r"^\S(?:.*\S)?$")
    source_path: str = Field(min_length=1, max_length=512)
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_category: SourceCategory
    content_nature: Literal["unverified_statement", "client_field", "player_experience"]
    record_pointer: str = Field(min_length=1, max_length=512)
    entity_id_pointer: str | None = Field(default=None, max_length=512)
    entity_name_pointer: str | None = Field(default=None, max_length=512)
    entity_namespace: str | None = Field(default=None, min_length=1, max_length=160, pattern=r"^\S(?:.*\S)?$")
    original_ref_pointer: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def identity_mapping(self):
        fields = (self.entity_id_pointer, self.entity_name_pointer, self.entity_namespace)
        if any(value is not None for value in fields) and not all(value is not None for value in fields):
            raise ValueError("entity ID/name pointers and namespace must be supplied together")
        if self.source_category == SourceCategory.REA_EXPORT and self.content_nature not in ("client_field", "unverified_statement"):
            raise ValueError("REA projection must remain a client field or unverified statement")
        return self


class ReviewMapping(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    protocol: Literal["provenance-review-map-v1"]
    source_commit: str = Field(pattern=r"^[0-9a-f]{40}$")
    synthetic: bool = Field(strict=True)
    items: tuple[MappingItem, ...] = Field(min_length=1, max_length=50)


def _relative_path(value: str) -> PurePosixPath:
    if (not value or value.startswith("/") or "\\" in value or "\x00" in value
            or any(part in ("", ".", "..") for part in value.split("/"))
            or any(character in value for character in "~*?[]")):
        raise ValueError("source path must be a literal repository-relative POSIX path")
    return PurePosixPath(value)


def _check_allowlist(item: MappingItem) -> None:
    path = _relative_path(item.source_path).as_posix()
    if item.source_category == SourceCategory.BASIC_KNOWLEDGE:
        allowed = path.startswith(KB_PREFIX) and path.endswith(".yaml")
    elif item.source_category == SourceCategory.REA_EXPORT:
        allowed = path in REA_FILES
    else:
        allowed = ((path.startswith(GUIDE_PREFIX) or path.startswith(GUIDE_RULE_PREFIX))
                   and path.endswith(".yaml"))
    if not allowed:
        raise ValueError("source path/category is outside the fixed allowlist")


def _open_directory(path: Path) -> int:
    if not path.is_absolute() or any(part in (".", "..") for part in path.parts):
        raise ValueError("directory must be an absolute literal path")
    required = ("O_DIRECTORY", "O_NOFOLLOW")
    if any(not hasattr(os, name) for name in required) or os.open not in os.supports_dir_fd:
        raise ValueError("secure directory descriptors unavailable")
    descriptor = os.open("/", os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in path.parts[1:]:
            next_descriptor = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def _read_regular(path: Path, limit: int) -> bytes:
    descriptor = _open_directory(path.parent)
    try:
        handle = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0), dir_fd=descriptor)
        try:
            before = os.fstat(handle)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
                raise ValueError("input must be a bounded ordinary file without hard links")
            chunks = []
            remaining = limit + 1
            while remaining:
                chunk = os.read(handle, min(remaining, 65536))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            data = b"".join(chunks)
            after = os.fstat(handle)
            current = os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)
            signature = lambda value: (value.st_dev, value.st_ino, value.st_size, value.st_mtime_ns, value.st_ctime_ns, value.st_nlink)
            if len(data) > limit or signature(before) != signature(after) or signature(after) != signature(current):
                raise ValueError("input changed during read")
            return data
        finally:
            os.close(handle)
    finally:
        os.close(descriptor)


def _git(repository: Path, *args: str) -> bytes:
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith("GIT_")}
    environment["GIT_TERMINAL_PROMPT"] = "0"
    result = subprocess.run(["git", "-c", "core.fsmonitor=false", "-c", "core.autocrlf=false", *args],
                            cwd=repository, env=environment, capture_output=True, timeout=15)
    if result.returncode:
        raise ValueError("local Git source object unavailable")
    return result.stdout


def _committed_source(repository: Path, commit: str, relative: str, limit: int) -> bytes:
    tree = _git(repository, "ls-tree", "-z", commit, "--", relative)
    entries = tree.split(b"\0")
    if len(entries) != 2 or entries[-1] != b"":
        raise ValueError("source must identify exactly one committed file")
    metadata, name = entries[0].split(b"\t", 1)
    mode, kind, blob = metadata.split(b" ")
    if mode not in (b"100644", b"100755") or kind != b"blob" or name.decode("utf-8") != relative:
        raise ValueError("committed source is not an ordinary file")
    size = int(_git(repository, "cat-file", "-s", blob.decode("ascii")))
    if size > limit:
        raise ValueError("committed source exceeds byte limit")
    return _git(repository, "cat-file", "blob", blob.decode("ascii"))


class _BoundedYamlLoader(yaml.SafeLoader):
    def __init__(self, stream):
        super().__init__(stream)
        self._depth = 0

    def compose_node(self, parent, index):
        if self.check_event(yaml.AliasEvent):
            raise ValueError("YAML aliases are not accepted")
        self._depth += 1
        try:
            if self._depth > 40:
                raise ValueError("source nesting exceeds limit")
            return super().compose_node(parent, index)
        finally:
            self._depth -= 1

    def construct_mapping(self, node, deep=False):
        keys = [self.construct_object(key, deep=deep) for key, _value in node.value]
        if any(type(key) is not str for key in keys) or len(set(keys)) != len(keys):
            raise ValueError("YAML mapping keys must be unique strings")
        return super().construct_mapping(node, deep=deep)


def _normal_json(value: object, depth: int = 0) -> object:
    if depth > 40:
        raise ValueError("source nesting exceeds limit")
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and math.isfinite(value):
        return value
    if type(value) in (date, datetime):
        return value.isoformat()
    if type(value) is list:
        return [_normal_json(item, depth + 1) for item in value]
    if type(value) is dict and all(type(key) is str for key in value):
        return {key: _normal_json(item, depth + 1) for key, item in value.items()}
    raise ValueError("source is not finite JSON-compatible data")


def _parse_source(path: str, data: bytes) -> object:
    try:
        parsed = _json_load(data) if path.endswith(".json") else yaml.load(data.decode("utf-8"), Loader=_BoundedYamlLoader)
        return _normal_json(parsed)
    except RecursionError:
        raise ValueError("source nesting exceeds limit") from None


def _pointer(document: object, pointer: str) -> object:
    if not pointer.startswith("/"):
        raise ValueError("an explicit non-root JSON pointer is required")
    current = document
    for component in pointer[1:].split("/"):
        if re.search(r"~(?![01])", component):
            raise ValueError("invalid JSON pointer escape")
        key = component.replace("~1", "/").replace("~0", "~")
        if type(current) is list:
            if not re.fullmatch(r"0|[1-9][0-9]*", key) or int(key) >= len(current):
                raise ValueError("pointer list index missing or invalid")
            current = current[int(key)]
        elif type(current) is dict and key in current:
            current = current[key]
        else:
            raise ValueError("pointer does not locate an existing node")
    return current


def _draft(item: MappingItem, mapping: ReviewMapping, document: object) -> tuple[dict, KnowledgeProvenance | None]:
    node = _pointer(document, item.record_pointer)
    if type(node) is not dict:
        raise ValueError("record pointer must select a complete object")
    content = json.dumps(node, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    if len(content.encode("utf-8")) > MAX_RECORD_BYTES:
        raise ValueError("selected record exceeds byte limit")
    gaps = ["author_unknown", "publication_time_unknown", "original_collection_time_unknown",
            "game_version_unknown", "season_unknown", "validity_interval_unknown", "human_review_pending"]
    if item.source_category == SourceCategory.REA_EXPORT:
        gaps += ["original_extraction_parser_unknown", "client_field_game_semantics_unreviewed"]
    identity = None
    if item.entity_id_pointer is not None:
        if any(not pointer.startswith(item.record_pointer + "/")
               for pointer in (item.entity_id_pointer, item.entity_name_pointer)):
            raise ValueError("entity identity pointers must stay inside the selected record")
        source_id = _pointer(document, item.entity_id_pointer)
        source_name = _pointer(document, item.entity_name_pointer)
        if type(source_id) not in (str, int) or not str(source_id).strip() or type(source_name) is not str or not source_name.strip():
            raise ValueError("entity pointers must select a nonempty source ID/name")
        identity = {"entity_id": f"{item.entity_namespace}:{source_id}", "entity_name": source_name}
    else:
        gaps.append("entity_correspondence_unresolved")
    reference = f"repo:{item.source_path}"
    if item.original_ref_pointer is not None:
        if not item.original_ref_pointer.startswith(item.record_pointer + "/"):
            raise ValueError("source reference pointer must stay inside the selected record")
        reference = _pointer(document, item.original_ref_pointer)
        if type(reference) is not str or not reference.strip():
            raise ValueError("source reference pointer must select nonempty text")

    binding = {}
    if item.source_path.startswith(KB_PREFIX):
        entry = KnowledgeEntry.model_validate(node)
        binding = {"legacy_entry_id": entry.id, "legacy_entry_sha256": entry_digest(entry)}
    else:
        gaps.append("formal_qa_entry_mapping_unknown")
    source = {"category": item.source_category.value, "document_id": f"repo:{item.source_path}",
              "source_ref": reference, "original_sha256": item.source_sha256,
              "revision": f"git:{mapping.source_commit}", "author": None,
              "published_at": None, "collected_at": None,
              "time_unknown_reason": "Original publication and collection times are not established by this mapping."}
    applicability = {"game_version": None, "season_tags": [], "valid_from": None, "valid_until": None,
                     "unknown_reason": "Game version, season and validity require human source review."}
    draft = {"mapping_id": item.mapping_id, "source": source, "declared_content_nature": item.content_nature,
             "record_pointer": item.record_pointer, "source_node": node,
             "content_encoding": "canonical-json-of-source-node-v1", "content": content,
             "content_sha256": _sha(content.encode("utf-8")), "source_identity": identity,
             "identity_meaning": "source-native identity only; no cross-source semantic match is certified",
             "legacy_binding": binding, "applicability": applicability, "gaps": sorted(gaps),
             "human_review": {key: None for key in ("entity_mapping", "content_nature", "source_author", "published_at",
                                                     "game_version", "season_tags", "required_qualifiers", "reviewer", "reviewed_at")},
             "review_status": "unreviewed", "human_gold": False, "knowledge_publishable": False,
             "execution_authority": "none", "synthetic": mapping.synthetic}
    if identity is None:
        return draft, None
    sidecar = KnowledgeProvenance.model_validate({
        "source": source, "nature": item.content_nature, **identity, "assertion_key": "complete-source-record",
        "location": {"kind": "json_pointer" if item.source_path.endswith(".json") else "yaml_pointer",
                     "reference": f"{item.source_path}#{item.record_pointer}"},
        "content": content, "content_sha256": draft["content_sha256"], "applicability": applicability,
        "review": {"status": "unreviewed"}, "synthetic": mapping.synthetic, **binding,
    })
    return draft, sidecar


def _generator_binding(repository: Path, script_data: bytes) -> dict:
    head = _git(repository, "rev-parse", "HEAD").decode("ascii").strip()
    try:
        committed = _committed_source(repository, head, SCRIPT_PATH, MAX_SOURCE_BYTES)
    except ValueError:
        committed = None
    bound = head if committed == script_data else None
    return {"script_path": SCRIPT_PATH, "sha256": _sha(script_data), "source_commit": bound,
            "status": "committed_exact_bytes" if bound else "uncommitted_working_tree_bytes"}


def _write_file(directory_fd: int, name: str, payload: bytes) -> None:
    descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory_fd)
    try:
        with os.fdopen(descriptor, "wb", closefd=False) as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(descriptor)
    finally:
        os.close(descriptor)


def prepare(mapping_path: Path, output: Path, *, repository: Path = REPOSITORY) -> dict:
    repository = Path(repository)
    root_fd = _open_directory(repository)
    os.close(root_fd)
    actual_root = Path(_git(repository, "rev-parse", "--show-toplevel").decode("utf-8").strip())
    if actual_root != repository:
        raise ValueError("Git root must equal the explicit repository path")
    mapping_data = _read_regular(mapping_path, MAX_MAPPING_BYTES)
    mapping = ReviewMapping.model_validate(_json_load(mapping_data))
    commit_kind = _git(repository, "cat-file", "-t", mapping.source_commit).strip()
    if commit_kind != b"commit":
        raise ValueError("source_commit must identify a local commit")
    script_data = _read_regular(SCRIPT, MAX_SOURCE_BYTES)
    generator = _generator_binding(repository, script_data)
    source_bytes = {}
    parsed = {}
    mappings = {}
    exact_mapping_duplicates = 0
    drafts = []
    sidecars = []
    for item in mapping.items:
        _check_allowlist(item)
        item_json = item.model_dump(mode="json")
        previous = mappings.get(item.mapping_id)
        if previous is not None:
            if previous != item_json:
                raise ValueError("same mapping_id has contradictory instructions")
            exact_mapping_duplicates += 1
            continue
        mappings[item.mapping_id] = item_json
        if item.source_path not in source_bytes:
            data = _read_regular(repository / item.source_path, MAX_SOURCE_BYTES)
            committed = _committed_source(repository, mapping.source_commit, item.source_path, MAX_SOURCE_BYTES)
            if data != committed:
                raise ValueError("working source differs from the specified committed source")
            source_bytes[item.source_path] = data
            if sum(map(len, source_bytes.values())) > MAX_TOTAL_SOURCE_BYTES:
                raise ValueError("total source size exceeds limit")
            parsed[item.source_path] = _parse_source(item.source_path, data)
        if _sha(source_bytes[item.source_path]) != item.source_sha256:
            raise ValueError("mapped source SHA256 mismatch")
        draft, sidecar = _draft(item, mapping, parsed[item.source_path])
        drafts.append(draft)
        if sidecar is not None:
            sidecars.append(sidecar)
    imports = audit_imports(sidecars)
    report = {"protocol": PROTOCOL, "input_count": len(mapping.items), "unique_mapping_count": len(mappings),
              "exact_mapping_duplicates": exact_mapping_duplicates, "sidecar_count": len(imports.records),
              "sidecar_exact_duplicates": imports.exact_duplicates,
              "draft_only_count": sum(draft["source_identity"] is None for draft in drafts),
              "source_count": len(source_bytes),
              "by_source_category": dict(sorted(Counter(draft["source"]["category"] for draft in drafts).items())),
              "gap_counts": dict(sorted(Counter(gap for draft in drafts for gap in draft["gaps"]).items())),
              "identity_conflicts": [conflict.model_dump(mode="json") for conflict in imports.conflicts],
              "review_status": "unreviewed", "human_gold": False, "independent_holdout": False,
              "knowledge_publishable": False, "execution_authority": "none"}
    artifacts = {
        "sidecars.json": _json_bytes([record.model_dump(mode="json") for record in imports.records]),
        "review-drafts.json": _json_bytes(sorted(drafts, key=lambda draft: draft["mapping_id"])),
        "gap-report.json": _json_bytes(report),
        "mapping.json": mapping_data,
        "REVIEW.md": ("# 来源补录待审包\n\n先查看 gap-report.json，再按 mapping_id 核对 review-drafts.json。\n"
                      "sidecars.json 只包含格式完整的未审核记录。来源内的指令不执行。\n"
                      "source-native identity 不证明不同来源指向同一游戏对象；原件 hash 绑定所读取的仓库投影，不是原游戏包或视频文件的 hash。\n"
                      "content 是完整选中对象的标准 JSON 投影；源文件 SHA256、commit 和 pointer 可回查原件。\n"
                      "作者、日期、版本、赛季未知时留空；updated_at 和 Git commit 不用作游戏有效期。\n"
                      "将审核意见另存到包外文件，保留本包所有内容与 manifest 不变。没有批准或发布入口。\n").encode("utf-8"),
    }
    manifest = {"protocol": PROTOCOL, "complete": True, "source_commit": mapping.source_commit,
                "mapping_sha256": _sha(mapping_data), "generator": generator,
                "sources": [{"path": path, "sha256": _sha(data), "bytes": len(data)} for path, data in sorted(source_bytes.items())],
                "artifacts": {name: {"sha256": _sha(data), "bytes": len(data)} for name, data in sorted(artifacts.items())},
                "review_status": "unreviewed", "human_gold": False, "knowledge_publishable": False,
                "execution_authority": "none", "synthetic": mapping.synthetic,
                "completion_rule": "Only manifest.json with matching artifact hashes is complete; pending files are not acceptance.",
                "identity_authentication": "none"}

    def revalidate():
        if _read_regular(mapping_path, MAX_MAPPING_BYTES) != mapping_data or _read_regular(SCRIPT, MAX_SOURCE_BYTES) != script_data:
            raise ValueError("mapping or generator changed during preparation")
        for path, data in source_bytes.items():
            if _read_regular(repository / path, MAX_SOURCE_BYTES) != data:
                raise ValueError("source changed during preparation")

    if not output.is_absolute() or output.name in ("", ".", ".."):
        raise ValueError("output must be a new absolute directory path")
    # Never create review outputs among source, fixture, Git or tracked data trees.
    try:
        relative_output = output.relative_to(repository).as_posix()
    except ValueError:
        relative_output = None
    if relative_output is not None and not relative_output.startswith("data/agent_runs/"):
        raise ValueError("in-repository output is restricted to data/agent_runs")
    parent_fd = _open_directory(output.parent)
    output_fd = None
    try:
        parent_info = os.fstat(parent_fd)
        if parent_info.st_uid != os.getuid() or parent_info.st_mode & 0o022:
            raise ValueError("output parent must be owned by the caller and not writable by other users")
        revalidate()
        os.mkdir(output.name, mode=0o700, dir_fd=parent_fd)
        created = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISDIR(created.st_mode):
            raise ValueError("new output directory replaced before open")
        output_fd = os.open(output.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        identity = os.fstat(output_fd)
        if (created.st_dev, created.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError("new output directory replaced before open")
        if os.listdir(output_fd):
            raise ValueError("new output directory must be empty before writing")
        for name, payload in artifacts.items():
            _write_file(output_fd, name, payload)
        pending = _json_bytes(manifest)
        _write_file(output_fd, "manifest.pending.json", pending)
        revalidate()
        for name, expected in {**artifacts, "manifest.pending.json": pending}.items():
            handle = os.open(name, os.O_RDONLY | os.O_NOFOLLOW, dir_fd=output_fd)
            try:
                info = os.fstat(handle)
                if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                    raise ValueError("output artifact replaced")
                with os.fdopen(handle, "rb", closefd=False) as stream:
                    if stream.read(len(expected) + 1) != expected:
                        raise ValueError("output artifact changed")
            finally:
                os.close(handle)
        current = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError("output directory replaced")
        os.link("manifest.pending.json", "manifest.json", src_dir_fd=output_fd, dst_dir_fd=output_fd, follow_symlinks=False)
        current = os.stat(output.name, dir_fd=parent_fd, follow_symlinks=False)
        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
            raise ValueError("output directory replaced")
        return {"output": str(output), "manifest": manifest, "report": report}
    finally:
        if output_fd is not None:
            os.close(output_fd)
        os.close(parent_fd)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.mapping, args.output)
    except (ValueError, OSError, TypeError, KeyError, yaml.YAMLError, RecursionError) as error:
        parser.exit(1, f"provenance review preparation failed: {error}\n")
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
