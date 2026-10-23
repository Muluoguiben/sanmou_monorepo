"""Deployment and HTTP policy configuration must address the same served alias."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from sanmou_common.policy_contracts import PolicyManifest
from test_serving_manifest import ROOT, fixture, validator


SPEC = importlib.util.spec_from_file_location("make_policy_manifest", ROOT / "scripts/model-serving/make_policy_manifest.py")
bridge = importlib.util.module_from_spec(SPEC)
with patch.dict("sys.modules", {"validate_manifest": validator}):
    SPEC.loader.exec_module(bridge)


class PolicyManifestBridgeTests(unittest.TestCase):
    def test_alias_and_artifact_hashes_match_native_deployment(self):
        deployment = fixture()
        before = json.dumps(deployment)
        result = bridge.make_policy_manifest(deployment)
        self.assertEqual(result.model, deployment["policy_version"])
        self.assertTrue(result.policy_id.startswith(deployment["policy_version"] + "@sha256:"))
        self.assertNotEqual(result.model, deployment["model"]["id"])
        self.assertEqual(result.checkpoint_revision, "sha256:" + deployment["model"]["artifact_sha256"])
        self.assertEqual(result.tokenizer_revision, "sha256:" + deployment["model"]["files"]["tokenizer.json"])
        self.assertEqual(result.adapter_revision, "none")
        self.assertEqual(PolicyManifest.model_validate_json(result.model_dump_json()), result)
        self.assertEqual(json.dumps(deployment), before)
        self.assertEqual(deployment["validation"]["gpu_status"], "not_run")

    def test_sampling_defaults_are_explicit_and_request_budget_is_not_a_sampling_override(self):
        result = bridge.make_policy_manifest(fixture())
        self.assertEqual(result.sampling.value(), {"temperature": 0.0, "top_p": 1.0, "top_k": -1,
            "seed": 0, "min_p": 0.0, "repetition_penalty": 1.0, "frequency_penalty": 0.0,
            "presence_penalty": 0.0, "stop": None})
        self.assertNotIn("max_tokens", result.sampling.value())

    def test_merged_adapter_is_bound_and_input_changes_change_digest(self):
        deployment = fixture()
        original = bridge.make_policy_manifest(deployment)
        deployment["model"].update(artifact_kind="merged_sft", adapter={"id": "fixture", "revision": hashlib.sha1(b"fixture-adapter").hexdigest(),
            "sha256": hashlib.sha256(b"adapter").hexdigest()}, merge={"method": "peft", "version": "1.0.0",
            "code_sha256": hashlib.sha256(b"code").hexdigest()})
        merged = bridge.make_policy_manifest(deployment)
        self.assertNotEqual(merged.sha256, original.sha256)
        self.assertTrue(merged.adapter_revision.startswith("sha256:"))

    def test_engine_or_parser_change_invalidates_policy_binding_without_changing_served_alias(self):
        for target, key, value in (("engine", "version", "0.0.2"),
                                   ("runtime", "tool_call_parser", "another_parser")):
            with self.subTest(target=target):
                deployment = fixture()
                before = bridge.make_policy_manifest(deployment)
                deployment[target][key] = value
                after = bridge.make_policy_manifest(deployment)
                self.assertEqual(before.model, after.model)
                self.assertNotEqual(before.policy_id, after.policy_id)
                self.assertNotEqual(before.sha256, after.sha256)

    def test_cli_never_overwrites_and_incomplete_example_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory)/"deployment.json", Path(directory)/"policy.json"
            source.write_text(json.dumps(fixture()))
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                self.assertEqual(bridge.main([str(source), "--output", str(output)]), 0)
                before = output.read_bytes()
                self.assertEqual(bridge.main([str(source), "--output", str(output)]), 2)
                self.assertEqual(bridge.main([str(ROOT / "deploy/model-serving/manifest.example.json")]), 2)
            self.assertEqual(output.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
