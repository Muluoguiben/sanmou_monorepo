#!/usr/bin/env python3
"""Bind checked local native artifacts to a policy; never certify a live GPU.

The collector reads files and installed metadata. Validation/building from a
saved receipt only checks its structure and hashes, not the current process.
No credentials, network calls, model imports, or CUDA calls are used here.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import stat
import sys

from sanmou_common.policy_contracts import PolicyManifest, SealedJson, canonical_json, decode_json
from pioneer_agent.adapters.policy_http import _validate_sampling


SCHEMA = "sanmou-native-runtime-v1"
NATIVE_PROFILE = "sglang-chat-text-no-thinking-v1"
MODEL_ID = "Qwen/Qwen3.5-9B"
MODEL_REVISION = "c202236235762e1c871ad0ccb60c8ee5ba337b9a"
# Canonical SHA of the 13-file inventory reviewed in the previous Colab run.
APPROVED_FILES_SHA256 = "99b9436a621d009d9d0945d072a0eb0a4afe5f451b37ef60734b0a7b95677876"
ENGINE_REVISION = "baa9befa381511cd4d56f83980951e5a45fffc6d"
ENGINE_FILES = {
    "sglang/srt/entrypoints/openai/protocol.py": {
        "sha256": "765061a9ed7190b6318592721aa44a4b1d4258feaa321b4ed1c0bb239362e87e", "bytes": 83613},
    "sglang/srt/entrypoints/openai/serving_chat.py": {
        "sha256": "de02cd317a4208c7357f6860644e1a7d114cc3a3c55affa68829ab06bd2322c0", "bytes": 138492},
    "sglang/srt/layers/sampler.py": {
        "sha256": "98a36e61762f5b1b1ae06666c5a42f126e8bca1cec7d5b5fa63b32f9ebe75c1d", "bytes": 45240},
}
LOCK_PATH = "docs/test-reports/2026-10-24/colab-native/requirements-py312.lock"
MODEL_FILES_PATH = "docs/test-reports/2026-10-24/colab-native/model-files.json"
REQUIRED_SOURCE_FILES = {
    "packages/pioneer-agent/src/pioneer_agent/agent_harness/__init__.py",
    "packages/pioneer-agent/src/pioneer_agent/mcp_server/__init__.py",
    "packages/sanmou-common/src/sanmou_common/policy_contracts.py",
    "packages/pioneer-agent/src/pioneer_agent/adapters/policy_http.py",
    "packages/pioneer-agent/src/pioneer_agent/adapters/policy_service.py",
    "packages/pioneer-agent/src/pioneer_agent/app/policy_gateway.py",
    "packages/pioneer-agent/src/pioneer_agent/agent_harness/run_budget.py",
    "packages/pioneer-agent/src/pioneer_agent/agent_harness/task_contracts.py",
    "scripts/model-serving/native_runtime_manifest.py",
    "scripts/model-serving/live_gateway_roundtrip.py",
    "scripts/model-serving/live_gateway_scenario.json",
    "scripts/model-serving/colab_gateway_bootstrap.py",
    LOCK_PATH,
    MODEL_FILES_PATH,
}
DEPENDENCIES = (
    "sglang", "torch", "transformers", "triton", "flashinfer-python", "sglang-kernel",
    "tokenizers", "safetensors", "cuda-python", "cuda-bindings", "nvidia-cuda-nvcc",
    "nvidia-nvvm", "nvidia-nvjitlink", "outlines-core", "xgrammar", "httpx",
    "fastapi", "pydantic", "uvicorn",
)
CHECKS = {
    "model_files": "checked_against_reviewed_inventory",
    "public_config": "file_read_and_hashed",
    "dependencies": "installed_metadata_matches_exported_lock",
    "source": "exported_files_match_inventory",
    "engine_source": "installed_files_match_release_source",
    "vision_tower_status": "not_inspected",
    "gpu_acceptance": "not_run",
    "docker_acceptance": "not_applicable",
    "live_service_attested": False,
    "ppo_eligible": False,
}
SHA = re.compile(r"[0-9a-f]{64}\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)+(?:[a-zA-Z0-9.+_-]*)\Z")
PRIVATE_NAME_RE = re.compile(r"(?:^|[/_.-])(?:secrets?|credentials|private[-_]key|api[-_]key)(?:[._/-]|$)", re.I)
CONFIG_REQUIRED = {
    "model-path", "served-model-name", "host", "port", "dtype", "context-length",
    "mem-fraction-static", "max-running-requests", "chunked-prefill-size",
    "cuda-graph-backend-decode", "cuda-graph-backend-prefill", "tool-call-parser",
    "reasoning-parser", "log-level", "limit-mm-data-per-request", "skip-server-warmup",
}
CONFIG_OPTIONAL = {
    "tokenizer-path", "chat-template", "load-format", "tensor-parallel-size",
    "data-parallel-size", "attention-backend", "mamba-backend", "linear-attn-backend",
    "mamba-radix-cache-strategy", "page-size", "disable-overlap-schedule",
    "log-requests", "trust-remote-code", "weight-version", "mm-preprocess-cache-size-mb",
    "default-chat-template-kwargs",
}


class NativeReceiptError(ValueError):
    """Stable, input-redacted validation error."""


def _digest(value: object) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def _require(ok: bool, message: str) -> None:
    if not ok:
        raise NativeReceiptError(message)


def _object(value: object, keys: set[str], label: str) -> dict:
    _require(type(value) is dict and set(value) == keys, label + ": missing or unsupported fields")
    return value


def _hash(value: object, label: str, pattern: re.Pattern = SHA) -> None:
    _require(type(value) is str and bool(pattern.fullmatch(value)) and len(set(value)) > 1,
             label + ": invalid digest")


def _relative(value: object) -> str:
    _require(type(value) is str and bool(re.fullmatch(r"[A-Za-z0-9_./-]+", value)), "invalid artifact path")
    path = PurePosixPath(value)
    _require(bool(path.parts) and not path.is_absolute() and str(path) == value
             and all(part not in (".", "..") and not part.startswith(".") for part in path.parts),
             "invalid artifact path")
    return value


def _artifact(value: object) -> dict:
    result = _object(value, {"sha256", "bytes"}, "artifact")
    _hash(result["sha256"], "artifact")
    _require(type(result["bytes"]) is int and result["bytes"] >= 0, "artifact: invalid byte length")
    return result


def _inventory(value: object) -> dict:
    _require(type(value) is dict and bool(value), "file inventory must not be empty")
    for name, record in value.items():
        _relative(name)
        _artifact(record)
    return value


def forbidden_source_name(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return (bool(PRIVATE_NAME_RE.search(name)) or any(
        part.startswith(".") or part.lower() in {"__pycache__", "id_rsa", "id_ed25519", "id_ecdsa",
                                                  "credentials", "credentials.json", "secrets.json"}
        or part.lower().endswith((".pem", ".key", ".p12", ".pfx", ".pyc", ".pyo"))
        for part in parts))


def _source_inventory(value: object) -> dict:
    result = _object(value, {"schema", "source_commit", "files"}, "source inventory")
    _require(result["schema"] == "sanmou-colab-source-inventory-v1", "unsupported source inventory")
    _hash(result["source_commit"], "source commit", COMMIT)
    files = _inventory(result["files"])
    _require(REQUIRED_SOURCE_FILES | {LOCK_PATH} <= set(files), "source inventory omits required files")
    for name in files:
        _require(not forbidden_source_name(name), "source inventory contains a private artifact")
        _require(name.startswith(("packages/sanmou-common/src/", "packages/pioneer-agent/src/",
                                  "scripts/model-serving/")) or name in {
            LOCK_PATH, "docs/test-reports/2026-10-24/colab-native/model-files.json",
            "docs/test-reports/2026-10-24/colab-native/model-revision-proof.json",
        }, "source inventory contains an unsupported path")
    return result


def _integer(value: object, minimum: int, maximum: int) -> None:
    _require(type(value) is int and minimum <= value <= maximum, "invalid integer setting")


def _public_config(value: object) -> dict:
    # Never strip secrets silently: a private runtime config is not an input.
    _require(type(value) is dict and CONFIG_REQUIRED <= set(value)
             and set(value) <= CONFIG_REQUIRED | CONFIG_OPTIONAL,
             "public config: missing or unsupported fields (private config is forbidden)")
    root = value["model-path"]
    _require(type(root) is str and root.startswith("/") and ".." not in PurePosixPath(root).parts
             and str(PurePosixPath(root)) == root, "public config: invalid model directory")
    alias = value["served-model-name"]
    _require(type(alias) is str and bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", alias)),
             "public config: invalid served alias")
    _require(value["host"] == "127.0.0.1" and value["dtype"] == "bfloat16", "native profile requires loopback BF16")
    _integer(value["port"], 1024, 65535)
    _integer(value["context-length"], 1, 262144)
    _integer(value["max-running-requests"], 1, 16)
    _integer(value["chunked-prefill-size"], 1, value["context-length"])
    fraction = value["mem-fraction-static"]
    _require(type(fraction) in (float, int) and 0 < fraction < 1, "invalid memory fraction")
    _require(value["cuda-graph-backend-decode"] == value["cuda-graph-backend-prefill"] == "disabled",
             "native first-run profile disables both CUDA graph phases")
    _require(value["tool-call-parser"] == "qwen3_coder" and value["reasoning-parser"] == "qwen3",
             "native profile requires the reviewed Qwen parsers")
    _require(value["log-level"] == "warning" and value["skip-server-warmup"] is True,
             "native profile requires warning logs and explicit text warmup")
    limits = _object(value["limit-mm-data-per-request"], {"image", "video", "audio"}, "media limits")
    _require(all(type(item) is int and item == 0 for item in limits.values()), "native profile accepts text only")
    for name in ("tokenizer-path", "chat-template"):
        if name in value:
            _require(value[name] == (root if name == "tokenizer-path" else root + "/chat_template.jinja"),
                     "public config points outside the checked model")
    for name in ("tensor-parallel-size", "data-parallel-size", "page-size"):
        if name in value:
            _integer(value[name], 1, 1)
    for name in ("log-requests", "trust-remote-code"):
        if name in value:
            _require(value[name] is False, "unsafe native profile boolean")
    exact = {"load-format": "safetensors", "mamba-backend": "triton", "linear-attn-backend": "triton",
             "mamba-radix-cache-strategy": "no_buffer", "disable-overlap-schedule": True,
             "mm-preprocess-cache-size-mb": 0, "default-chat-template-kwargs": {"enable_thinking": False}}
    for name, expected in exact.items():
        if name in value:
            _require(type(value[name]) is type(expected) and value[name] == expected, "unsupported native setting")
    if "default-chat-template-kwargs" in value:
        _require(value["default-chat-template-kwargs"]["enable_thinking"] is False, "invalid thinking setting")
    if "attention-backend" in value:
        _require(value["attention-backend"] in ("flashinfer", "triton"), "unsupported A100 attention backend")
    if "weight-version" in value:
        _require(value["weight-version"] == alias, "weight-version must match the bound alias")
    return value


def validate_native_runtime_receipt(receipt: dict) -> dict:
    """Check a saved receipt, without asserting that its runtime is still live."""
    try:
        value = decode_json(canonical_json(receipt))
        _object(value, {"schema_version", "runtime_kind", "native_profile", "model", "public_config",
                        "public_config_sha256", "public_config_artifact", "python_version", "dependencies",
                        "source", "engine_source", "sampling", "prompt_sha256", "checks"}, "receipt")
        _require(value["schema_version"] == SCHEMA and value["runtime_kind"] == "native"
                 and value["native_profile"] == NATIVE_PROFILE, "unsupported native receipt")
        model = _object(value["model"], {"id", "revision", "files", "files_sha256", "expected_inventory_artifact"}, "model")
        _require(model["id"] == MODEL_ID and model["revision"] == MODEL_REVISION, "unreviewed model revision")
        files = _inventory(model["files"])
        _require(_digest(files) == model["files_sha256"] == APPROVED_FILES_SHA256,
                 "model inventory differs from the reviewed baseline")
        _artifact(model["expected_inventory_artifact"])
        _public_config(value["public_config"])
        _require(_digest(value["public_config"]) == value["public_config_sha256"], "public config hash mismatch")
        _artifact(value["public_config_artifact"])
        _require(type(value["python_version"]) is str and bool(re.fullmatch(r"3\.12\.\d+", value["python_version"])),
                 "native profile requires Python 3.12")
        dependencies = _object(value["dependencies"], set(DEPENDENCIES), "dependencies")
        for version in dependencies.values():
            _require(type(version) is str and bool(VERSION.fullmatch(version)), "invalid installed version")
        _require(dependencies["sglang"] == "0.5.22", "unreviewed SGLang version")
        source = _object(value["source"], {"source_kind", "inventory", "inventory_sha256", "inventory_artifact"}, "source")
        _require(source["source_kind"] == "exported_snapshot", "unsupported source kind")
        _source_inventory(source["inventory"])
        _require(_digest(source["inventory"]) == source["inventory_sha256"], "source inventory hash mismatch")
        _artifact(source["inventory_artifact"])
        engine = _object(value["engine_source"], {"source_commit", "files"}, "engine source")
        _require(engine["source_commit"] == ENGINE_REVISION and engine["files"] == ENGINE_FILES,
                 "SGLang source differs from the reviewed release")
        _validate_sampling(value["sampling"])
        _hash(value["prompt_sha256"], "prompt")
        _require(value["checks"] == CHECKS and type(value["checks"]) is dict
                 and all(type(value["checks"][key]) is type(expected) for key, expected in CHECKS.items()),
                 "receipt cannot claim live GPU, Docker or PPO acceptance")
        return value
    except NativeReceiptError:
        raise
    except (KeyError, TypeError, ValueError):
        raise NativeReceiptError("invalid native receipt") from None


def build_native_policy_manifest(receipt: dict) -> PolicyManifest:
    value = validate_native_runtime_receipt(receipt)
    files = value["model"]["files"]
    alias = value["public_config"]["served-model-name"]
    return PolicyManifest(
        policy_id=alias + "@native-sha256:" + _digest(value), model=alias,
        checkpoint_revision="sha256:" + value["model"]["files_sha256"], adapter_revision="none",
        tokenizer_revision="sha256:" + _digest({name: files[name] for name in (
            "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt")}),
        chat_template_revision="sha256:" + files["chat_template.jinja"]["sha256"],
        prompt_revision="sha256:" + value["prompt_sha256"], sampling=SealedJson.from_value(value["sampling"]),
        model_context_limit=value["public_config"]["context-length"],
    )


def _open_parent(path: Path) -> tuple[int, str]:
    absolute = path.absolute()
    _require(".." not in absolute.parts, "invalid local path")
    descriptor = os.open(absolute.anchor, os.O_RDONLY | os.O_DIRECTORY)
    try:
        for part in absolute.parts[1:-1]:
            next_fd = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_fd
        return descriptor, absolute.name
    except BaseException:
        os.close(descriptor)
        raise


def _read_file(path: Path, *, keep_bytes: bool = False) -> tuple[dict, bytes | None]:
    # Pin all directory components and the final regular file; do not follow
    # symlinks/hardlinks or reopen the pathname between stat and hashing.
    descriptor, name = _open_parent(path)
    try:
        file_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=descriptor)
        with os.fdopen(file_fd, "rb") as stream:
            before = os.fstat(stream.fileno())
            _require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, "artifact must be a regular private copy")
            _require(not keep_bytes or before.st_size <= 16 * 1024 * 1024, "metadata artifact exceeds byte limit")
            digest, total, parts = hashlib.sha256(), 0, []
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
                total += len(chunk)
                if keep_bytes:
                    _require(total <= 16 * 1024 * 1024, "metadata artifact exceeds byte limit")
                    parts.append(chunk)
            after = os.fstat(stream.fileno())
            visible = os.stat(name, dir_fd=descriptor, follow_symlinks=False)
            identity = lambda item: (item.st_dev, item.st_ino, item.st_size, item.st_mtime_ns, item.st_ctime_ns)
            _require(identity(before) == identity(after) == identity(visible) and total == before.st_size,
                     "artifact changed during collection")
            return {"sha256": digest.hexdigest(), "bytes": total}, b"".join(parts) if keep_bytes else None
    finally:
        os.close(descriptor)


def _read_json(path: Path) -> tuple[object, dict]:
    _require(path.suffix == ".json", "metadata input must be an explicit JSON file")
    artifact, raw = _read_file(path, keep_bytes=True)
    return decode_json(raw), artifact


def _verify_files(root: Path, files: dict, *, exact: bool = False) -> None:
    _require(root.is_dir() and not root.is_symlink(), "missing artifact directory")
    if exact:
        # The provisioner materializes the reviewed 13 files in a clean model
        # directory; download caches belong in a different directory.
        actual = set()
        for path in root.iterdir():
            _require(not path.is_symlink() and path.is_file(), "model directory must contain only ordinary files")
            actual.add(path.name)
        _require(actual == set(files), "model directory inventory mismatch")
    for name, expected in files.items():
        actual, _ = _read_file(root / name)
        _require(actual == expected, "artifact content differs from expected inventory")


def _installed_dependencies(source_root: Path, expected_lock: dict) -> dict:
    actual_lock, raw = _read_file(source_root / LOCK_PATH, keep_bytes=True)
    _require(actual_lock == expected_lock, "dependency lock changed during collection")
    lock = {}
    for line in raw.decode("utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)==([^\s;]+)", line)
        _require(match is not None, "exported lock contains unsupported requirement syntax")
        name = re.sub(r"[-_.]+", "-", match[1]).lower()
        _require(name not in lock, "duplicate lock requirement")
        lock[name] = match[2]
    installed = {name: metadata.version(name) for name in DEPENDENCIES}
    _require(all(lock.get(name) == installed[name] for name in DEPENDENCIES),
             "installed key dependencies differ from exported lock")
    return installed


def collect_native_runtime_receipt(*, model_dir: Path, runtime_config: Path, expected_model_files: Path,
                                   prompt_sha256: str, sampling: dict, source_root: Path,
                                   source_inventory: Path) -> dict:
    """Read and compare local artifacts. This function never contacts a server."""
    model_files, expected_artifact = _read_json(expected_model_files)
    _inventory(model_files)
    _require(_digest(model_files) == APPROVED_FILES_SHA256, "expected model inventory is not the reviewed baseline")
    _verify_files(model_dir, model_files, exact=True)
    config, config_artifact = _read_json(runtime_config)
    _public_config(config)
    _require(Path(config["model-path"]).absolute() == model_dir.absolute(), "public config uses a different model directory")
    inventory, inventory_artifact = _read_json(source_inventory)
    _source_inventory(inventory)
    _verify_files(source_root, inventory["files"])
    dependencies = _installed_dependencies(source_root, inventory["files"][LOCK_PATH])
    distribution = metadata.distribution("sglang")
    _require(distribution.version == "0.5.22", "unreviewed installed SGLang version")
    for name, expected in ENGINE_FILES.items():
        actual, _ = _read_file(Path(distribution.locate_file(name)))
        _require(actual == expected, "installed SGLang source does not match release")
    return validate_native_runtime_receipt({
        "schema_version": SCHEMA, "runtime_kind": "native", "native_profile": NATIVE_PROFILE,
        "model": {"id": MODEL_ID, "revision": MODEL_REVISION, "files": model_files,
                  "files_sha256": _digest(model_files), "expected_inventory_artifact": expected_artifact},
        "public_config": config, "public_config_sha256": _digest(config), "public_config_artifact": config_artifact,
        "python_version": platform.python_version(), "dependencies": dependencies,
        "source": {"source_kind": "exported_snapshot", "inventory": inventory,
                   "inventory_sha256": _digest(inventory), "inventory_artifact": inventory_artifact},
        "engine_source": {"source_commit": ENGINE_REVISION, "files": ENGINE_FILES},
        "sampling": sampling, "prompt_sha256": prompt_sha256, "checks": CHECKS,
    })


def write_native_bundle(output: Path, receipt: dict) -> PolicyManifest:
    checked = validate_native_runtime_receipt(receipt)
    manifest = build_native_policy_manifest(checked)
    files = {"runtime-receipt.json": canonical_json(checked) + b"\n",
             "policy-manifest.json": (manifest.model_dump_json(indent=2) + "\n").encode()}
    index = {"schema_version": "sanmou-native-binding-bundle-v1", "manifest_sha256": manifest.sha256,
             "files": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                       for name, raw in files.items()}, "complete": True}
    # Flush the private pending index before publishing its final name. A
    # failed flush/fsync must not leave an apparently completed bundle.
    pending_name = ".bundle-index.pending"
    parent_fd, output_name = _open_parent(output)
    descriptor = None
    try:
        parent_stat = os.fstat(parent_fd)
        _require(parent_stat.st_uid == os.geteuid() and not parent_stat.st_mode & 0o022,
                 "output parent must be owned by this user and not writable by group or others")
        os.mkdir(output_name, mode=0o700, dir_fd=parent_fd)
        created = os.stat(output_name, dir_fd=parent_fd, follow_symlinks=False)
        descriptor = os.open(output_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
        pinned = os.fstat(descriptor)
        _require((created.st_dev, created.st_ino) == (pinned.st_dev, pinned.st_ino), "output directory changed")
        _require(pinned.st_uid == os.geteuid() and not pinned.st_mode & 0o077
                 and not os.listdir(descriptor), "new output directory is not empty and private")
        for name, raw in {**files, pending_name: canonical_json(index) + b"\n"}.items():
            if name == pending_name:
                _require(set(os.listdir(descriptor)) == set(files), "output directory contains unexpected files")
            file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=descriptor)
            with os.fdopen(file_fd, "wb") as stream:
                stream.write(raw)
                stream.flush()
                os.fsync(stream.fileno())
        visible = os.stat(output_name, dir_fd=parent_fd, follow_symlinks=False)
        _require((created.st_dev, created.st_ino) == (visible.st_dev, visible.st_ino), "output directory changed")
        current_parent, _ = _open_parent(output)
        try:
            current, original = os.fstat(current_parent), os.fstat(parent_fd)
            _require((current.st_dev, current.st_ino) == (original.st_dev, original.st_ino), "output parent changed")
            _require(current.st_uid == os.geteuid() and not current.st_mode & 0o022,
                     "output parent permissions changed")
        finally:
            os.close(current_parent)
        _require(set(os.listdir(descriptor)) == set(files) | {pending_name}, "unexpected files before publication")
        # No-clobber publication is the last operation that can fail after
        # checking/writing. Keep the task-created pending file; do not perform
        # a cleanup that could fail after publishing the completion marker.
        os.link(pending_name, "bundle-index.json", src_dir_fd=descriptor, dst_dir_fd=descriptor,
                follow_symlinks=False)
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent_fd)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("model-dir", "runtime-config", "expected-model-files", "sampling", "source-root", "source-inventory", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--prompt-sha256", required=True)
    args = parser.parse_args(argv)
    try:
        _require(not args.output.exists() and not args.output.is_symlink(), "output already exists")
        sampling, _ = _read_json(args.sampling)
        receipt = collect_native_runtime_receipt(
            model_dir=args.model_dir, runtime_config=args.runtime_config, expected_model_files=args.expected_model_files,
            prompt_sha256=args.prompt_sha256, sampling=sampling, source_root=args.source_root,
            source_inventory=args.source_inventory,
        )
        manifest = write_native_bundle(args.output, receipt)
        print(json.dumps({"manifest_sha256": manifest.sha256, "binding": "local_native_artifacts_checked",
                          "gpu_validated": False, "docker_validated": False, "ppo_eligible": False}))
        return 0
    except (ValueError, TypeError, OSError, metadata.PackageNotFoundError):
        print("native binding rejected: incomplete, mismatched or unavailable local artifacts", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
