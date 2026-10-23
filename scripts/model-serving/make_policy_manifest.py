#!/usr/bin/env python3
"""Translate a complete deployment declaration into the gateway's policy manifest.

This binds configuration, not a running GPU. The native server's served-model-name
is the policy alias, whereas the deployment model.id records the base model.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

from sanmou_common.policy_contracts import PolicyManifest, SealedJson, canonical_json, decode_json
from validate_manifest import ManifestError, load_manifest, validate_manifest

NATIVE_PROFILE = "sglang-chat-text-no-thinking-v1"


def make_policy_manifest(deployment: dict) -> PolicyManifest:
    # Copy JSON before validation so neither validation nor the returned object
    # can change the caller's deployment declaration.
    deployment = validate_manifest(decode_json(canonical_json(deployment)))
    model = deployment["model"]
    parameters = deployment["sampling"]
    # These concrete settings are frozen in the resulting manifest and sent on
    # every request; native SGLang defaults are not relied upon.
    sampling = {
        "temperature": parameters["temperature"], "top_p": parameters["top_p"],
        "top_k": parameters["top_k"], "seed": parameters["seed"],
        "min_p": 0.0, "repetition_penalty": 1.0,
        "frequency_penalty": 0.0, "presence_penalty": 0.0, "stop": None,
    }
    declaration_hash = hashlib.sha256(canonical_json({
        "deployment": deployment, "native_profile": NATIVE_PROFILE,
    })).hexdigest()
    return PolicyManifest(
        policy_id=deployment["policy_version"] + "@sha256:" + declaration_hash,
        model=deployment["policy_version"],
        checkpoint_revision="sha256:" + model["artifact_sha256"],
        adapter_revision="none" if model["adapter"] is None else "sha256:" + model["adapter"]["sha256"],
        tokenizer_revision="sha256:" + model["files"]["tokenizer.json"],
        chat_template_revision="sha256:" + model["files"]["chat_template.jinja"],
        prompt_revision="sha256:" + deployment["prompt_sha256"],
        sampling=SealedJson.from_value(sampling), model_context_limit=deployment["runtime"]["context_length"],
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("deployment", type=Path)
    parser.add_argument("--output", type=Path, help="New PolicyManifest JSON file; never overwrites")
    args = parser.parse_args(argv)
    try:
        manifest = make_policy_manifest(load_manifest(args.deployment))
        text = manifest.model_dump_json(indent=2) + "\n"
        if args.output:
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(text)
            print(json.dumps({"manifest_sha256": manifest.sha256, "gpu_validated": False,
                              "binding": "declared_configuration"}))
        else:
            print(text, end="")
    except (ValueError, OSError, ManifestError):
        # Configuration errors may contain paths or user data. Do not echo input.
        print("policy manifest rejected: incomplete declaration or unavailable new output", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
