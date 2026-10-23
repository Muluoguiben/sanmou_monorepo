#!/usr/bin/env python3
"""Fail closed before handing a pinned, local-only configuration to SGLang."""

from __future__ import annotations

import hashlib
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import sys
import tempfile

from validate_manifest import ManifestError, load_manifest, validate_manifest


def verify_artifacts(manifest: dict, root: Path) -> None:
    """Check every mounted file against the manifest, including all model shards."""
    if root.is_symlink() or not root.is_dir():
        raise ManifestError("model mount: expected a directory, not a symlink")
    actual = set()
    for path in root.rglob("*"):
        if path.is_symlink():
            raise ManifestError("model mount: materialize snapshot files before mounting")
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
        elif not path.is_dir():
            raise ManifestError("model mount: unsupported file type")
    if actual != set(manifest["model"]["files"]):
        raise ManifestError("model mount: file inventory does not match manifest")
    for name, expected in manifest["model"]["files"].items():
        digest = hashlib.sha256()
        with (root / name).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ManifestError("model mount: file content hash mismatch")
    # The dtype flag alone cannot make a quantized checkpoint an unquantized one.
    try:
        config = json.loads((root / "config.json").read_text(encoding="utf-8"))
    except (ValueError, UnicodeError) as exc:
        raise ManifestError("model config: invalid JSON") from exc
    def has_quantization(value: object) -> bool:
        if isinstance(value, dict):
            return (value.get("quantization_config") is not None
                    or any(has_quantization(item) for item in value.values()))
        if isinstance(value, list):
            return any(has_quantization(item) for item in value)
        return False

    if not isinstance(config, dict) or has_quantization(config):
        raise ManifestError("model config: quantized checkpoint is outside this demo")


def server_config(manifest: dict) -> dict:
    """Translate deployment fields to documented native SGLang server settings."""
    validate_manifest(manifest)
    runtime = manifest["runtime"]
    config = {
        "model-path": "/model",
        "tokenizer-path": "/model",
        "chat-template": "/model/chat_template.jinja",
        "served-model-name": manifest["policy_version"],
        "dtype": "bfloat16",
        # SGLang 0.5.22 rejects Qwen3.5 in its language-model-only allowlist.
        # Load the original checkpoint; reject non-text inputs at admission.
        # Omit the unsupported bool flag entirely, including a false spelling.
        "limit-mm-data-per-request": {"image": 0, "video": 0, "audio": 0},
        # Native warmup sends an image for Qwen's multimodal architecture,
        # which the text admission profile correctly rejects. A caller must
        # complete its own authenticated text generation before marking ready.
        "skip-server-warmup": True,
        "load-format": "safetensors",
        "tensor-parallel-size": 1,
        "data-parallel-size": 1,
        "context-length": runtime["context_length"],
        "host": runtime["host"],
        "port": runtime["port"],
        "tool-call-parser": runtime["tool_call_parser"],
        "log-level": "warning",
        "log-requests": False,
        "trust-remote-code": False,
    }
    if runtime["reasoning_parser"] != "none":
        config["reasoning-parser"] = runtime["reasoning_parser"]
    return config


def _read_secret(path: str) -> str:
    # These paths are fixed by validation. Do not include file contents in errors.
    value = Path(path).read_text(encoding="utf-8").strip()
    if len(value) < 16 or any(character.isspace() for character in value):
        raise ManifestError("runtime secret: expected a nonempty key of at least 16 characters")
    return value


def write_runtime_config(config: dict, directory: Path = Path("/run/sanmou-runtime")) -> str:
    # SGLang's config parser requires a .yaml/.yml suffix; JSON content is YAML.
    descriptor, path = tempfile.mkstemp(prefix="sglang-", suffix=".yaml", dir=directory)
    with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
        json.dump(config, stream)
    return path


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        print("usage: launch.py /run/sanmou/manifest.json", file=sys.stderr)
        return 2
    try:
        manifest = load_manifest(Path(args[0]))
        if os.environ.get("SANMOU_BASE_IMAGE") != manifest["engine"]["image"]:
            raise ManifestError("container base image does not match manifest")
        expected_versions = {"sglang": manifest["engine"]["version"],
                             **manifest["engine"]["dependencies"]}
        for package, expected in expected_versions.items():
            if version(package) != expected:
                raise ManifestError("container package version does not match manifest")
        verify_artifacts(manifest, Path("/model"))
        config = server_config(manifest)
        config["api-key"] = _read_secret(manifest["runtime"]["api_key_file"])
        config["admin-api-key"] = _read_secret(manifest["runtime"]["admin_api_key_file"])
        if config["api-key"] == config["admin-api-key"]:
            raise ManifestError("runtime secrets: use separate inference and administrative keys")
        # JSON is YAML-compatible. The 0600 file lives on the container tmpfs;
        # credentials never appear in image layers, stdout or OS command arguments.
        path = write_runtime_config(config)
        os.execv(sys.executable, [sys.executable, "-m", "sglang.launch_server", "--config", path])
    except (ManifestError, PackageNotFoundError) as exc:
        print(f"serving launch rejected: {exc}", file=sys.stderr)
        return 2
    except (OSError, UnicodeError):
        print("serving launch rejected: required mount or runtime file is unavailable", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
