"""Offline deployment guard checks; synthetic pins do not prove GPU compatibility."""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location(
    "sanmou_serving_manifest", ROOT / "scripts/model-serving/validate_manifest.py"
)
validator = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(validator)
LAUNCH_SPEC = importlib.util.spec_from_file_location(
    "sanmou_serving_launch", ROOT / "deploy/model-serving/launch.py"
)
launcher = importlib.util.module_from_spec(LAUNCH_SPEC)
with patch.dict(sys.modules, {"validate_manifest": validator}):
    LAUNCH_SPEC.loader.exec_module(launcher)


def digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def fixture() -> dict:
    data = json.loads((ROOT / "deploy/model-serving/manifest.example.json").read_text())
    data.update(deployment_id="test-only-deployment", policy_version="test-only-policy",
                prompt_sha256=digest("synthetic-prompt"))
    data["engine"].update(image="registry.invalid/sglang@sha256:" + digest("image"), version="0.0.1")
    data["engine"]["dependencies"] = {"torch": "0.0.1", "transformers": "0.0.1"}
    data["model"]["revision"] = hashlib.sha1(b"synthetic-test-revision").hexdigest()
    data["model"]["files"] = {name: digest(name) for name in data["model"]["files"]}
    data["model"]["artifact_sha256"] = validator.artifact_digest(data["model"]["files"])
    data["runtime"].update(tool_call_parser="qwen", reasoning_parser="qwen3")
    return data


class ServingManifestTests(unittest.TestCase):
    def test_example_is_deliberately_incomplete(self):
        with self.assertRaises(validator.ManifestError):
            validator.load_manifest(ROOT / "deploy/model-serving/manifest.example.json")

    def test_complete_synthetic_manifest_has_no_gpu_acceptance(self):
        manifest = validator.validate_manifest(fixture())
        self.assertEqual(manifest["validation"], {"gpu_status": "not_run", "gpu_report": None})

    def test_invalid_mutations_are_rejected(self):
        cases = [
            (("schema_version",), "old"),
            (("deployment_id",), None),
            (("input_schema_version",), "native-sglang"),
            (("engine", "image"), "sglang:latest"),
            (("engine", "image"), "sglang:latest@sha256:" + digest("image")),
            (("engine", "image"), "sglang@sha256:" + "0" * 64),
            (("engine", "version"), "latest"),
            (("engine", "dependencies", "torch"), None),
            (("model", "revision"), "main"),
            (("model", "revision"), "0" * 40),
            (("model", "artifact_sha256"), digest("wrong inventory")),
            (("runtime", "gpu_count"), 2),
            (("runtime", "gpu_count"), True),
            (("runtime", "tensor_parallel_size"), 2),
            (("runtime", "replicas"), 2),
            (("runtime", "dtype"), "auto"),
            (("runtime", "language_model_only"), False),
            (("runtime", "quantization"), "fp8"),
            (("runtime", "context_length"), 0),
            (("runtime", "port"), 80),
            (("runtime", "tool_call_parser"), "auto"),
            (("runtime", "reasoning_parser"), "auto"),
            (("runtime", "api_key_file"), "inline-secret"),
            (("sampling", "temperature"), float("nan")),
            (("sampling", "top_p"), 0),
            (("sampling", "top_k"), 0),
            (("sampling", "max_new_tokens"), 100000),
            (("sampling", "seed"), True),
            (("validation", "gpu_status"), "passed"),
        ]
        for keys, value in cases:
            with self.subTest(keys=keys, value=value):
                data = fixture()
                target = data
                for key in keys[:-1]:
                    target = target[key]
                target[keys[-1]] = value
                with self.assertRaises(validator.ManifestError):
                    validator.validate_manifest(data)

    def test_missing_fields_and_unknown_secret_fields_fail_without_echo(self):
        for group in (None, "engine", "runtime", "sampling", "model", "validation"):
            with self.subTest(group=group):
                data = fixture()
                target = data if group is None else data[group]
                target["unexpected-secret-field"] = "private-value-do-not-print"
                with self.assertRaises(validator.ManifestError) as caught:
                    validator.validate_manifest(data)
                self.assertNotIn("private-value", str(caught.exception))
        data = fixture()
        del data["runtime"]["dtype"]
        with self.assertRaises(validator.ManifestError):
            validator.validate_manifest(data)

    def test_model_inventory_rejects_missing_files_and_unsafe_paths(self):
        for path in ("../outside", "/absolute", "x//y", "x/./y", ".", "x\\y", "x\nq"):
            with self.subTest(path=path):
                data = fixture()
                data["model"]["files"][path] = digest("x")
                data["model"]["artifact_sha256"] = validator.artifact_digest(data["model"]["files"])
                with self.assertRaises(validator.ManifestError):
                    validator.validate_manifest(data)
        for name in ("config.json", "tokenizer.json", "chat_template.jinja", "model.safetensors"):
            with self.subTest(missing=name):
                data = fixture()
                del data["model"]["files"][name]
                data["model"]["artifact_sha256"] = validator.artifact_digest(data["model"]["files"])
                with self.assertRaises(validator.ManifestError):
                    validator.validate_manifest(data)

    def test_merged_artifact_requires_complete_provenance(self):
        data = fixture()
        data["model"]["artifact_kind"] = "merged_sft"
        with self.assertRaises(validator.ManifestError):
            validator.validate_manifest(data)
        data["model"]["adapter"] = {"id": "test-only-adapter", "revision": data["model"]["revision"],
                                    "sha256": digest("adapter")}
        data["model"]["merge"] = {"method": "peft-merge", "version": "0.0.1", "code_sha256": digest("merge")}
        self.assertEqual(validator.validate_manifest(data)["model"]["artifact_kind"], "merged_sft")
        data["model"]["artifact_kind"] = "base"
        with self.assertRaises(validator.ManifestError):
            validator.validate_manifest(data)

    def test_duplicate_json_fields_are_rejected(self):
        with patch.object(Path, "open", return_value=io.StringIO('{"x":1,"x":2}')):
            with self.assertRaisesRegex(validator.ManifestError, "duplicate"):
                validator.load_manifest(Path("unused"))

    def test_cli_returns_failure_for_incomplete_example(self):
        with contextlib.redirect_stderr(io.StringIO()) as errors:
            result = validator.main([str(ROOT / "deploy/model-serving/manifest.example.json")])
        self.assertEqual(result, 2)
        self.assertIn("manifest rejected", errors.getvalue())

    def test_cli_success_explicitly_excludes_gpu_evidence(self):
        with patch.object(validator, "load_manifest", return_value=fixture()):
            with contextlib.redirect_stdout(io.StringIO()) as output:
                self.assertEqual(validator.main(["unused"]), 0)
        self.assertFalse(json.loads(output.getvalue())["gpu_validated"])

    def test_native_server_configuration_is_not_policy_envelope(self):
        config = launcher.server_config(fixture())
        self.assertEqual(config["model-path"], "/model")
        self.assertEqual(config["dtype"], "bfloat16")
        self.assertTrue(config["language-model-only"])
        self.assertEqual(config["tensor-parallel-size"], 1)
        self.assertEqual(config["data-parallel-size"], 1)
        self.assertEqual(config["served-model-name"], "test-only-policy")
        self.assertFalse(config["trust-remote-code"])
        self.assertFalse(config["log-requests"])
        self.assertNotIn("api-key", config)
        self.assertNotIn("schema_version", config)

    def test_launch_rejects_image_mismatch_before_reading_secrets(self):
        with patch.object(launcher, "load_manifest", return_value=fixture()):
            with patch.dict("os.environ", {"SANMOU_BASE_IMAGE": "wrong"}):
                with patch.object(launcher, "_read_secret") as secret:
                    with contextlib.redirect_stderr(io.StringIO()):
                        self.assertEqual(launcher.main(["unused"]), 2)
                    secret.assert_not_called()

    def test_launch_rejects_dependency_mismatch_before_reading_model(self):
        data = fixture()
        with patch.object(launcher, "load_manifest", return_value=data):
            with patch.dict("os.environ", {"SANMOU_BASE_IMAGE": data["engine"]["image"]}):
                with patch.object(launcher, "version", return_value="9.9.9"):
                    with patch.object(launcher, "verify_artifacts") as verify:
                        with contextlib.redirect_stderr(io.StringIO()):
                            self.assertEqual(launcher.main(["unused"]), 2)
                        verify.assert_not_called()

    def test_runtime_config_uses_private_yaml_file(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-serving-test-"))
        path = Path(launcher.write_runtime_config({"api-key": "synthetic-test-secret"}, root))
        self.assertEqual(path.suffix, ".yaml")
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(json.loads(path.read_text()), {"api-key": "synthetic-test-secret"})

    def test_launch_does_not_put_secrets_in_process_arguments(self):
        data = fixture()
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(launcher, "load_manifest", return_value=data))
            stack.enter_context(patch.dict("os.environ", {"SANMOU_BASE_IMAGE": data["engine"]["image"]}))
            stack.enter_context(patch.object(launcher, "version", return_value="0.0.1"))
            stack.enter_context(patch.object(launcher, "verify_artifacts"))
            stack.enter_context(patch.object(launcher, "_read_secret", side_effect=[
                "synthetic-inference-key", "synthetic-administrative-key",
            ]))
            writer = stack.enter_context(patch.object(launcher, "write_runtime_config",
                                                      return_value="/run/sanmou-runtime/test.yaml"))
            execute = stack.enter_context(patch.object(launcher.os, "execv"))
            self.assertEqual(launcher.main(["unused"]), 0)
        self.assertEqual(writer.call_args.args[0]["api-key"], "synthetic-inference-key")
        self.assertEqual(execute.call_args.args[1], [
            sys.executable, "-m", "sglang.launch_server", "--config", "/run/sanmou-runtime/test.yaml",
        ])

    def test_mounted_files_are_hashed_and_quantized_config_rejected(self):
        # Retain this tiny generated directory; no deletion or cleanup touches user data.
        root = Path(tempfile.mkdtemp(prefix="sanmou-serving-test-"))
        data = fixture()
        for name in data["model"]["files"]:
            (root / name).write_text("{}" if name == "config.json" else name)
        data["model"]["files"]["config.json"] = digest("{}")
        launcher.verify_artifacts(data, root)
        (root / "model.safetensors").write_text("changed")
        with self.assertRaisesRegex(validator.ManifestError, "hash mismatch"):
            launcher.verify_artifacts(data, root)
        (root / "model.safetensors").write_text("model.safetensors")
        quantized = '{"text_config":{"quantization_config":{"method":"fp8"}}}'
        (root / "config.json").write_text(quantized)
        data["model"]["files"]["config.json"] = digest(quantized)
        with self.assertRaisesRegex(validator.ManifestError, "quantized"):
            launcher.verify_artifacts(data, root)

    def test_inventory_and_symlink_mismatches_are_rejected(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-serving-test-"))
        with self.assertRaisesRegex(validator.ManifestError, "inventory"):
            launcher.verify_artifacts(fixture(), root)
        (root / "link").symlink_to(root / "absent")
        with self.assertRaisesRegex(validator.ManifestError, "materialize"):
            launcher.verify_artifacts(fixture(), root)


if __name__ == "__main__":
    unittest.main()
