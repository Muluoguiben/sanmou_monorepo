"""Native binding checks; fixture receipts are synthetic, never GPU evidence."""
from __future__ import annotations

from contextlib import ExitStack, redirect_stderr, redirect_stdout
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sanmou_common.policy_contracts import PolicyManifest, canonical_json, decode_json


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("native_binding_for_test", ROOT / "scripts/model-serving/native_runtime_manifest.py")
native = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(native)
EVIDENCE = ROOT / "docs/test-reports/2026-10-24/colab-native"


def artifact(raw: bytes) -> dict:
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def make_receipt_fixture() -> dict:
    """A schema-valid synthetic receipt for other CPU-only protocol tests."""
    model_raw = (EVIDENCE / "model-files.json").read_bytes()
    model = decode_json(model_raw)
    config = decode_json((EVIDENCE / "launch-public-3.json").read_bytes())
    config["model-path"] = "/content/synthetic-native-test/model"
    source_inventory = {"schema": "sanmou-colab-source-inventory-v1",
                        "source_commit": hashlib.sha1(b"synthetic-source").hexdigest(),
                        "files": {name: artifact(name.encode()) for name in native.REQUIRED_SOURCE_FILES | {native.LOCK_PATH}}}
    lock = {line.split("==")[0].lower().replace("_", "-"): line.split("==")[1]
            for line in (EVIDENCE / "requirements-py312.lock").read_text().splitlines() if "==" in line}
    return {
        "schema_version": native.SCHEMA, "runtime_kind": "native", "native_profile": native.NATIVE_PROFILE,
        "model": {"id": native.MODEL_ID, "revision": native.MODEL_REVISION, "files": model,
                  "files_sha256": native._digest(model), "expected_inventory_artifact": artifact(model_raw)},
        "public_config": config, "public_config_sha256": native._digest(config),
        "public_config_artifact": artifact(canonical_json(config)), "python_version": "3.12.12",
        "dependencies": {name: lock[name] for name in native.DEPENDENCIES},
        "source": {"source_kind": "exported_snapshot", "inventory": source_inventory,
                   "inventory_sha256": native._digest(source_inventory), "inventory_artifact": artifact(canonical_json(source_inventory))},
        "engine_source": {"source_commit": native.ENGINE_REVISION, "files": decode_json(canonical_json(native.ENGINE_FILES))},
        "sampling": {"temperature": 0.0, "top_p": 1.0, "top_k": -1, "min_p": 0.0,
                     "repetition_penalty": 1.0, "frequency_penalty": 0.0, "presence_penalty": 0.0, "seed": 0, "stop": None},
        "prompt_sha256": hashlib.sha256(b"synthetic prompt and tools").hexdigest(),
        "checks": dict(native.CHECKS),
    }


class NativeRuntimeManifestTests(unittest.TestCase):
    def test_reviewed_model_anchor_matches_archived_inventory(self):
        self.assertEqual(native._digest(decode_json((EVIDENCE / "model-files.json").read_bytes())), native.APPROVED_FILES_SHA256)

    def test_valid_receipt_builds_detached_native_manifest(self):
        receipt = make_receipt_fixture()
        original = canonical_json(receipt)
        checked = native.validate_native_runtime_receipt(receipt)
        manifest = native.build_native_policy_manifest(receipt)
        self.assertEqual(manifest.model, receipt["public_config"]["served-model-name"])
        self.assertIn("@native-sha256:", manifest.policy_id)
        self.assertEqual(manifest.prompt_revision, "sha256:" + receipt["prompt_sha256"])
        self.assertEqual(manifest.checkpoint_revision, "sha256:" + native.APPROVED_FILES_SHA256)
        self.assertEqual(manifest.sampling.value(), receipt["sampling"])
        self.assertEqual(PolicyManifest.model_validate_json(manifest.model_dump_json()), manifest)
        checked["public_config"]["port"] = 9999
        self.assertEqual(canonical_json(receipt), original)
        self.assertFalse(receipt["checks"]["live_service_attested"])
        self.assertFalse(receipt["checks"]["ppo_eligible"])

    def test_binding_changes_with_config_dependency_source_sampling_and_prompt(self):
        original = native.build_native_policy_manifest(make_receipt_fixture())
        for kind in ("config", "dependency", "source", "sampling", "prompt"):
            with self.subTest(kind=kind):
                receipt = make_receipt_fixture()
                if kind == "config":
                    receipt["public_config"]["port"] += 1
                    receipt["public_config_sha256"] = native._digest(receipt["public_config"])
                    receipt["public_config_artifact"] = artifact(canonical_json(receipt["public_config"]))
                elif kind == "dependency":
                    receipt["dependencies"]["httpx"] = "99.0.0"
                elif kind == "source":
                    receipt["source"]["inventory"]["source_commit"] = hashlib.sha1(b"other source").hexdigest()
                    receipt["source"]["inventory_sha256"] = native._digest(receipt["source"]["inventory"])
                elif kind == "sampling":
                    receipt["sampling"]["seed"] = 99
                else:
                    receipt["prompt_sha256"] = hashlib.sha256(b"other prompt").hexdigest()
                changed = native.build_native_policy_manifest(receipt)
                self.assertEqual(original.model, changed.model)
                self.assertNotEqual(original.sha256, changed.sha256)

    def test_private_or_unsealed_public_config_is_rejected(self):
        for key, value in (("api-key", "private-value-must-not-echo"), ("admin-api-key", "private"),
                           ("api_key_file", "/tmp/private.key"), ("env", {"TOKEN": "private"}),
                           ("language-model-only", True), ("extra", True)):
            with self.subTest(key=key):
                receipt = make_receipt_fixture()
                receipt["public_config"][key] = value
                receipt["public_config_sha256"] = native._digest(receipt["public_config"])
                with self.assertRaises(native.NativeReceiptError) as caught:
                    native.validate_native_runtime_receipt(receipt)
                self.assertNotIn("private-value", str(caught.exception))

    def test_unsafe_config_values_are_rejected(self):
        cases = {"host": "0.0.0.0", "dtype": "auto", "skip-server-warmup": False,
                 "tool-call-parser": "qwen", "context-length": True,
                 "limit-mm-data-per-request": {"image": 1, "video": 0, "audio": 0},
                 "tokenizer-path": "/outside/tokenizer", "log-requests": True,
                 "default-chat-template-kwargs": {"enable_thinking": 0}}
        for key, value in cases.items():
            with self.subTest(key=key):
                receipt = make_receipt_fixture()
                receipt["public_config"][key] = value
                receipt["public_config_sha256"] = native._digest(receipt["public_config"])
                with self.assertRaises(native.NativeReceiptError):
                    native.validate_native_runtime_receipt(receipt)

    def test_hashes_types_required_fields_and_acceptance_are_not_claimable(self):
        cases = [
            (("runtime_kind",), "docker"), (("python_version",), "3.13.15"),
            (("model", "revision"), "main"), (("model", "files_sha256"), "a" * 64),
            (("model", "files", "config.json", "bytes"), 1),
            (("public_config_sha256",), "b" * 64), (("dependencies", "sglang"), "0.5.21"),
            (("source", "inventory_sha256"), "c" * 64), (("source", "source_kind"), "git_checkout_verified"),
            (("source", "inventory", "source_commit"), "0" * 40),
            (("engine_source", "files", "sglang/srt/layers/sampler.py", "sha256"), "d" * 64),
            (("checks", "gpu_acceptance"), "passed"), (("checks", "ppo_eligible"), True),
            (("checks", "ppo_eligible"), 0), (("checks", "docker_acceptance"), "passed"),
            (("checks", "model_files"), "declared"), (("checks", "live_service_attested"), True),
            (("sampling", "seed"), True), (("sampling", "temperature"), float("nan")),
        ]
        for path, value in cases:
            with self.subTest(path=path):
                receipt = make_receipt_fixture()
                target = receipt
                for key in path[:-1]:
                    target = target[key]
                target[path[-1]] = value
                with self.assertRaises(native.NativeReceiptError):
                    native.validate_native_runtime_receipt(receipt)
        for group, key in (("dependencies", "httpx"), ("sampling", "min_p"), ("checks", "source")):
            receipt = make_receipt_fixture()
            del receipt[group][key]
            with self.assertRaises(native.NativeReceiptError):
                native.validate_native_runtime_receipt(receipt)

    def test_source_inventory_cannot_include_credentials_or_escape(self):
        for path in ("../escape", "/absolute", "scripts/model-serving/.env", "scripts/model-serving/private-key.json",
                     "scripts/model-serving/id_ed25519", "scripts/model-serving/certificate.p12",
                     "scripts/model-serving/__pycache__/cached.pyc"):
            receipt = make_receipt_fixture()
            inventory = receipt["source"]["inventory"]
            inventory["files"][path] = artifact(b"private")
            receipt["source"]["inventory_sha256"] = native._digest(inventory)
            with self.assertRaises(native.NativeReceiptError):
                native.validate_native_runtime_receipt(receipt)

    def test_source_inventory_requires_gateway_contract_and_lock(self):
        receipt = make_receipt_fixture()
        inventory = receipt["source"]["inventory"]
        del inventory["files"][native.LOCK_PATH]
        receipt["source"]["inventory_sha256"] = native._digest(inventory)
        with self.assertRaises(native.NativeReceiptError):
            native.validate_native_runtime_receipt(receipt)

    def test_bundle_is_create_only_and_roundtrips_exact_manifest(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-native-binding-test-")).resolve()
        output = root / "binding"
        manifest = native.write_native_bundle(output, make_receipt_fixture())
        receipt = decode_json((output / "runtime-receipt.json").read_bytes())
        saved = PolicyManifest.model_validate_json((output / "policy-manifest.json").read_bytes())
        self.assertEqual(native.build_native_policy_manifest(receipt).sha256, saved.sha256)
        self.assertEqual(manifest.sha256, saved.sha256)
        index = decode_json((output / "bundle-index.json").read_bytes())
        for name, expected in index["files"].items():
            self.assertEqual(artifact((output / name).read_bytes()), expected)
        before = {path.name: path.read_bytes() for path in output.iterdir()}
        with self.assertRaises(FileExistsError):
            native.write_native_bundle(output, make_receipt_fixture())
        self.assertEqual({path.name: path.read_bytes() for path in output.iterdir()}, before)

    def test_local_reader_refuses_symlink_hardlink_and_duplicate_json(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-native-binding-test-")).resolve()
        original = root / "original"
        original.write_bytes(b"{}")
        link = root / "symlink"
        link.symlink_to(original)
        with self.assertRaises(OSError):
            native._read_file(link)
        os.link(original, root / "hardlink")
        with self.assertRaises(native.NativeReceiptError):
            native._read_file(original)
        duplicate = root / "duplicate.json"
        duplicate.write_text('{"x":1,"x":2}')
        with self.assertRaises(ValueError):
            native._read_json(duplicate)

    def test_partial_bundle_has_no_complete_index(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-native-binding-test-")).resolve()
        original_open = native.os.open
        def fail_manifest(path, *args, **kwargs):
            if path == "policy-manifest.json":
                raise OSError("synthetic write failure")
            return original_open(path, *args, **kwargs)
        with patch.object(native.os, "open", side_effect=fail_manifest):
            with self.assertRaises(OSError):
                native.write_native_bundle(root / "binding", make_receipt_fixture())
        self.assertFalse((root / "binding/bundle-index.json").exists())

    def test_index_fsync_failure_does_not_publish_completion_marker(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-native-binding-test-")).resolve()
        original_fsync = native.os.fsync
        calls = 0
        def fail_last_fsync(descriptor):
            nonlocal calls
            calls += 1
            original_fsync(descriptor)
            if calls == 3:
                raise OSError("synthetic fsync failure after index bytes were written")
        with patch.object(native.os, "fsync", side_effect=fail_last_fsync):
            with self.assertRaises(OSError):
                native.write_native_bundle(root / "binding", make_receipt_fixture())
        self.assertEqual(calls, 3)
        pending = decode_json((root / "binding/.bundle-index.pending").read_bytes())
        self.assertTrue(pending["complete"])
        self.assertFalse((root / "binding/bundle-index.json").exists())

    def test_bundle_refuses_a_symlink_parent(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-native-binding-test-")).resolve()
        destination = root / "destination"
        destination.mkdir()
        (root / "alias").symlink_to(destination, target_is_directory=True)
        with self.assertRaises(OSError):
            native.write_native_bundle(root / "alias/new-binding", make_receipt_fixture())
        self.assertEqual(list(destination.iterdir()), [])

    def test_bundle_refuses_group_or_other_writable_parent(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-native-binding-test-")).resolve()
        root.chmod(0o777)
        with self.assertRaises(native.NativeReceiptError):
            native.write_native_bundle(root / "binding", make_receipt_fixture())
        self.assertFalse((root / "binding").exists())

    def test_bundle_refuses_preexisting_directory_substitution(self):
        root = Path(tempfile.mkdtemp(prefix="sanmou-native-binding-test-")).resolve()
        prior = root / "prior"
        prior.mkdir(mode=0o700)
        (prior / "sentinel").write_text("preserve existing material")
        original_mkdir = native.os.mkdir
        def substitute(path, *args, **kwargs):
            original_mkdir(path, *args, **kwargs)
            if path == "binding":
                descriptor = kwargs["dir_fd"]
                os.rename("binding", "retained-new-directory", src_dir_fd=descriptor, dst_dir_fd=descriptor)
                os.rename("prior", "binding", src_dir_fd=descriptor, dst_dir_fd=descriptor)
        with patch.object(native.os, "mkdir", side_effect=substitute):
            with self.assertRaisesRegex(native.NativeReceiptError, "not empty"):
                native.write_native_bundle(root / "binding", make_receipt_fixture())
        self.assertEqual({path.name for path in (root / "binding").iterdir()}, {"sentinel"})
        self.assertEqual((root / "binding/sentinel").read_text(), "preserve existing material")

    def test_metadata_reader_rejects_env_path_without_opening_it(self):
        with patch.object(native, "_read_file") as read:
            with self.assertRaises(native.NativeReceiptError):
                native._read_json(Path("/unused/.env"))
            read.assert_not_called()


class NativeCollectorTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix="sanmou-native-collector-test-")).resolve()
        self.model = self.root / "model"
        self.model.mkdir()
        self.receipt = make_receipt_fixture()
        self.files = {}
        for name in self.receipt["model"]["files"]:
            raw = name.encode()
            (self.model / name).write_bytes(raw)
            self.files[name] = artifact(raw)
        self.expected = self.root / "model-files.json"
        self.expected.write_bytes(canonical_json(self.files))
        self.config = self.receipt["public_config"]
        self.config["model-path"] = str(self.model)
        self.config_path = self.root / "public.json"
        self.config_path.write_bytes(canonical_json(self.config))
        self.source = self.root / "source"
        inventory = self.receipt["source"]["inventory"]
        for name in inventory["files"]:
            path = self.source / name
            path.parent.mkdir(parents=True, exist_ok=True)
            raw = name.encode()
            if name == native.LOCK_PATH:
                raw = "\n".join(name + "==" + version for name, version in self.receipt["dependencies"].items()).encode()
            path.write_bytes(raw)
            inventory["files"][name] = artifact(raw)
        self.inventory_path = self.root / "source-inventory.json"
        self.inventory_path.write_bytes(canonical_json(inventory))
        self.engine_root = self.root / "site-packages"
        self.engine_files = {}
        for name in native.ENGINE_FILES:
            path = self.engine_root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(name.encode())
            self.engine_files[name] = artifact(name.encode())
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch.object(native, "APPROVED_FILES_SHA256", native._digest(self.files)))
        self.stack.enter_context(patch.object(native, "ENGINE_FILES", self.engine_files))
        self.stack.enter_context(patch.object(native.platform, "python_version", return_value="3.12.12"))
        self.stack.enter_context(patch.object(native.metadata, "version", side_effect=self.receipt["dependencies"].__getitem__))
        self.stack.enter_context(patch.object(native.metadata, "distribution", return_value=SimpleNamespace(
            version="0.5.22", locate_file=lambda name: self.engine_root / name)))

    def collect(self):
        return native.collect_native_runtime_receipt(
            model_dir=self.model, runtime_config=self.config_path, expected_model_files=self.expected,
            prompt_sha256=self.receipt["prompt_sha256"], sampling=self.receipt["sampling"],
            source_root=self.source, source_inventory=self.inventory_path)

    def test_collector_reads_actual_bytes_without_git_or_gpu(self):
        result = self.collect()
        self.assertEqual(result["model"]["files"], self.files)
        self.assertEqual(result["public_config_artifact"], artifact(self.config_path.read_bytes()))
        self.assertEqual(result["source"]["source_kind"], "exported_snapshot")
        self.assertFalse((self.source / ".git").exists())
        self.assertEqual(result["checks"], native.CHECKS)

    def test_changed_model_is_rejected_instead_of_believing_expected_hash(self):
        (self.model / "config.json").write_bytes(b"changed")
        with self.assertRaises(native.NativeReceiptError):
            self.collect()

    def test_extra_model_file_is_rejected(self):
        (self.model / "extra.safetensors").write_bytes(b"extra")
        with self.assertRaises(native.NativeReceiptError):
            self.collect()

    def test_changed_source_is_rejected(self):
        (self.source / "packages/sanmou-common/src/sanmou_common/policy_contracts.py").write_bytes(b"changed")
        with self.assertRaises(native.NativeReceiptError):
            self.collect()

    def test_changed_installed_sglang_source_is_rejected(self):
        (self.engine_root / "sglang/srt/layers/sampler.py").write_bytes(b"changed")
        with self.assertRaises(native.NativeReceiptError):
            self.collect()

    def test_metadata_version_must_match_exported_lock(self):
        with patch.object(native.metadata, "version", return_value="999.0.0"):
            with self.assertRaises(native.NativeReceiptError):
                self.collect()

    def test_lock_reread_is_checked_against_source_inventory(self):
        expected = self.receipt["source"]["inventory"]["files"][native.LOCK_PATH]
        (self.source / native.LOCK_PATH).write_text("torch==999.0.0\n")
        with self.assertRaisesRegex(native.NativeReceiptError, "lock changed"):
            native._installed_dependencies(self.source, expected)

    def test_cli_collects_then_writes_and_does_not_clobber(self):
        sampling = self.root / "sampling.json"
        sampling.write_bytes(canonical_json(self.receipt["sampling"]))
        output = self.root / "new-binding"
        args = ["--model-dir", str(self.model), "--runtime-config", str(self.config_path),
                "--expected-model-files", str(self.expected), "--prompt-sha256", self.receipt["prompt_sha256"],
                "--sampling", str(sampling), "--source-root", str(self.source),
                "--source-inventory", str(self.inventory_path), "--output", str(output)]
        with redirect_stdout(io.StringIO()) as out, redirect_stderr(io.StringIO()):
            self.assertEqual(native.main(args), 0)
            before = (output / "runtime-receipt.json").read_bytes()
            self.assertEqual(native.main(args), 2)
        self.assertEqual(before, (output / "runtime-receipt.json").read_bytes())
        self.assertFalse(json.loads(out.getvalue())["gpu_validated"])


if __name__ == "__main__":
    unittest.main()
