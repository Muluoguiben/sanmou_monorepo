#!/usr/bin/env python3
"""Validate an SV1 manifest offline; a valid file is never a GPU acceptance result."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path, PurePosixPath
import re
import sys


SCHEMA_VERSION = "sanmou-serving-manifest-v1"
SHA256 = re.compile(r"[0-9a-f]{64}\Z")
REVISION = re.compile(r"[0-9a-f]{40}\Z")
IMAGE = re.compile(r"[a-z0-9][a-z0-9./:_-]*@sha256:[0-9a-f]{64}\Z")
VERSION = re.compile(r"[0-9]+(?:\.[0-9]+)+(?:[a-zA-Z0-9.+_-]*)\Z")
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}\Z")
PARSER = re.compile(r"[a-z0-9][a-z0-9_-]*\Z")


class ManifestError(ValueError):
    """A manifest is incomplete or violates the single-GPU deployment contract."""


def artifact_digest(files: dict[str, str]) -> str:
    """Hash the sorted path -> SHA256 inventory, not a fabricated weight hash."""
    raw = json.dumps(files, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _object(value: object, keys: set[str], path: str) -> dict:
    if not isinstance(value, dict) or set(value) != keys:
        # Do not echo unknown fields or values: they may contain a pasted secret.
        raise ManifestError(f"{path}: missing or unsupported fields")
    return value


def _pattern(value: object, pattern: re.Pattern, path: str) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        raise ManifestError(f"{path}: required pinned value is missing or invalid")


def _hash(value: object, path: str, pattern: re.Pattern = SHA256) -> None:
    _pattern(value, pattern, path)
    if len(set(value)) == 1:
        raise ManifestError(f"{path}: placeholder hash is not accepted")


def _integer(value: object, low: int, high: int, path: str) -> None:
    if type(value) is not int or not low <= value <= high:
        raise ManifestError(f"{path}: integer outside allowed range")


def validate_manifest(data: object) -> dict:
    """Validate structure and declared pins only; do not read files or use network/GPU."""
    manifest = _object(data, {
        "schema_version", "deployment_id", "policy_version", "prompt_sha256", "input_schema_version",
        "engine", "model", "runtime", "sampling", "validation",
    }, "manifest")
    if manifest["schema_version"] != SCHEMA_VERSION:
        raise ManifestError("schema_version: unsupported schema")
    for field in ("deployment_id", "policy_version", "input_schema_version"):
        _pattern(manifest[field], IDENTIFIER, field)
    if manifest["input_schema_version"] != "policy-service-v1":
        raise ManifestError("input_schema_version: expected policy-service-v1 envelope")
    _hash(manifest["prompt_sha256"], "prompt_sha256")

    engine = _object(manifest["engine"], {"name", "image", "version", "dependencies"}, "engine")
    if engine["name"] != "sglang":
        raise ManifestError("engine.name: only sglang is supported")
    _pattern(engine["image"], IMAGE, "engine.image")
    if ":latest@" in engine["image"]:
        raise ManifestError("engine.image: latest is not a release pin")
    _hash(engine["image"].split("@sha256:")[1], "engine.image.digest")
    _pattern(engine["version"], VERSION, "engine.version")
    dependencies = _object(engine["dependencies"], {"torch", "transformers"}, "engine.dependencies")
    for name, version in dependencies.items():
        _pattern(version, VERSION, f"engine.dependencies.{name}")

    model = _object(manifest["model"], {
        "id", "revision", "artifact_kind", "artifact_sha256", "files", "adapter", "merge",
    }, "model")
    if model["id"] != "Qwen/Qwen3.5-9B":
        raise ManifestError("model.id: this demo requires Qwen/Qwen3.5-9B")
    _hash(model["revision"], "model.revision", REVISION)
    _hash(model["artifact_sha256"], "model.artifact_sha256")
    files = model["files"]
    required = {"config.json", "tokenizer.json", "tokenizer_config.json", "chat_template.jinja"}
    if not isinstance(files, dict) or not required <= set(files):
        raise ManifestError("model.files: config, tokenizer and explicit chat template are required")
    for name, digest in files.items():
        if (not isinstance(name, str) or not re.fullmatch(r"[A-Za-z0-9_./-]+", name)
                or not PurePosixPath(name).parts
                or PurePosixPath(name).is_absolute() or ".." in PurePosixPath(name).parts
                or str(PurePosixPath(name)) != name):
            raise ManifestError("model.files: artifact paths must be normalized relative paths")
        _hash(digest, "model.files digest")
    if not any(name.endswith(".safetensors") for name in files):
        raise ManifestError("model.files: at least one safetensors weight file is required")
    if artifact_digest(files) != model["artifact_sha256"]:
        raise ManifestError("model.artifact_sha256: inventory digest mismatch")
    if model["artifact_kind"] == "base":
        if model["adapter"] is not None or model["merge"] is not None:
            raise ManifestError("model: base artifact cannot contain adapter or merge metadata")
    elif model["artifact_kind"] == "merged_sft":
        adapter = _object(model["adapter"], {"id", "revision", "sha256"}, "model.adapter")
        _pattern(adapter["id"], IDENTIFIER, "model.adapter.id")
        _hash(adapter["revision"], "model.adapter.revision", REVISION)
        _hash(adapter["sha256"], "model.adapter.sha256")
        merge = _object(model["merge"], {"method", "version", "code_sha256"}, "model.merge")
        _pattern(merge["method"], IDENTIFIER, "model.merge.method")
        _pattern(merge["version"], VERSION, "model.merge.version")
        _hash(merge["code_sha256"], "model.merge.code_sha256")
    else:
        raise ManifestError("model.artifact_kind: expected base or merged_sft")

    runtime = _object(manifest["runtime"], {
        "gpu_count", "tensor_parallel_size", "replicas", "dtype", "language_model_only", "quantization",
        "context_length", "host", "port", "tool_call_parser", "reasoning_parser",
        "api_key_file", "admin_api_key_file",
    }, "runtime")
    for name in ("gpu_count", "tensor_parallel_size", "replicas"):
        _integer(runtime[name], 1, 1, f"runtime.{name}")
    if runtime["dtype"] != "bfloat16" or runtime["quantization"] is not None:
        raise ManifestError("runtime: BF16 without quantization is required")
    if runtime["language_model_only"] is not False:
        raise ManifestError(
            "runtime.language_model_only: Qwen text requests use the original checkpoint; "
            "language-only loading has not been validated"
        )
    _integer(runtime["context_length"], 1, 1048576, "runtime.context_length")
    _integer(runtime["port"], 1024, 65535, "runtime.port")
    if runtime["host"] != "0.0.0.0":
        raise ManifestError("runtime.host: container listens on 0.0.0.0; publish host port to loopback only")
    for name in ("tool_call_parser", "reasoning_parser"):
        _pattern(runtime[name], PARSER, f"runtime.{name}")
        if runtime[name] == "auto" or (name == "tool_call_parser" and runtime[name] == "none"):
            raise ManifestError(f"runtime.{name}: explicit parser selection is required")
    for name, expected in (
        ("api_key_file", "/run/secrets/sanmou-api-key"),
        ("admin_api_key_file", "/run/secrets/sanmou-admin-api-key"),
    ):
        if runtime[name] != expected:
            raise ManifestError(f"runtime.{name}: expected runtime secret file reference")

    sampling = _object(manifest["sampling"], {
        "temperature", "top_p", "top_k", "max_new_tokens", "seed",
    }, "sampling")
    for name, minimum, maximum in (("temperature", 0, 2), ("top_p", 0, 1)):
        value = sampling[name]
        if type(value) not in (int, float) or not math.isfinite(value) or not minimum <= value <= maximum:
            raise ManifestError(f"sampling.{name}: invalid finite number")
    if sampling["top_p"] == 0:
        raise ManifestError("sampling.top_p: must be greater than zero")
    _integer(sampling["top_k"], -1, 1000000, "sampling.top_k")
    if sampling["top_k"] == 0:
        raise ManifestError("sampling.top_k: use -1 or a positive value")
    _integer(sampling["max_new_tokens"], 1, runtime["context_length"], "sampling.max_new_tokens")
    _integer(sampling["seed"], 0, 2**31 - 1, "sampling.seed")

    validation = _object(manifest["validation"], {"gpu_status", "gpu_report"}, "validation")
    if validation["gpu_status"] != "not_run" or validation["gpu_report"] is not None:
        raise ManifestError("validation: offline preparation cannot certify GPU acceptance")
    return manifest


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ManifestError("JSON: duplicate field")
        result[key] = value
    return result


def load_manifest(path: Path) -> dict:
    try:
        with path.open(encoding="utf-8") as source:
            data = json.load(source, object_pairs_hook=_unique_object)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ManifestError("manifest: cannot read valid UTF-8 JSON") from exc
    return validate_manifest(data)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--print-image", action="store_true", help="print only the validated pinned base image")
    args = parser.parse_args(argv)
    try:
        manifest = load_manifest(args.manifest)
    except ManifestError as exc:
        print(f"manifest rejected: {exc}", file=sys.stderr)
        return 2
    if args.print_image:
        print(manifest["engine"]["image"])
    else:
        print(json.dumps({"manifest_valid": True, "gpu_validated": False,
                          "vision_tower_status": "not_inspected",
                          "deployment_id": manifest["deployment_id"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
