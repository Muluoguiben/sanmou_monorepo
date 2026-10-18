"""Bounded fixed-source checks of the already-frozen E0 review plan."""
import builtins
import copy
from datetime import date, datetime, timezone
import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("qe0_frozen_public_controls",
    Path(__file__).with_name("qa-e0-prep-independent-probes.py"))
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class SupplementalPreparationProbes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prep = public.load_product()

    def test_verify_has_no_filesystem_write_env_read_provider_or_network(self):
        path_open, builtin_open = Path.open, builtins.open
        def guard_name_mode(name, mode):
            if not isinstance(name, int):
                self.assertFalse(Path(name).name.startswith(".env"), "credential/config file read")
            self.assertFalse(any(letter in mode for letter in "wax+"), "verify attempted a file write")
        def guarded_path(path, mode="r", *args, **kwargs):
            guard_name_mode(path, mode)
            return path_open(path, mode, *args, **kwargs)
        def guarded_builtin(name, mode="r", *args, **kwargs):
            guard_name_mode(name, mode)
            return builtin_open(name, mode, *args, **kwargs)
        with patch.object(Path, "open", guarded_path), patch.object(builtins, "open", guarded_builtin), \
             patch.object(Path, "mkdir", side_effect=AssertionError("verify mkdir")), \
             patch("socket.socket.connect", side_effect=AssertionError("network")), \
             patch("socket.create_connection", side_effect=AssertionError("network")), \
             patch("qa_agent.chat.llm_client.build_llm_client", side_effect=AssertionError("provider")):
            report = self.prep.verify()
        self.assertEqual(report["provider_calls"], 0)
        self.assertEqual(report["human_reviewed_labels"], 0)
        self.assertIs(report["human_gold"], False)
        self.assertIs(report["independent_holdout"], False)
        self.assertIsNone(report["quality_threshold"])

    def test_changed_source_seal_before_completion_is_rejected(self):
        with patch.object(self.prep, "_seal", side_effect=[{"synthetic": "before"}, {"synthetic": "after"}]):
            with self.assertRaisesRegex(ValueError, "input_drift_during_verification"):
                self.prep.verify()

    def test_foreign_loaded_module_origin_is_rejected(self):
        import qa_agent.index.search_index as index
        original = index.__spec__.origin
        with patch.object(index.__spec__, "origin", str(public.ROOT / "data/agent_runs/foreign-search-index.py")):
            with self.assertRaisesRegex(ValueError, "source mismatch"):
                self.prep.verify()
        self.assertEqual(index.__spec__.origin, original)

    def test_raw_date_json_representation_is_explicit_and_preserves_other_types(self):
        raw = {"day": date(2020, 1, 2), "time": datetime(2020, 1, 2, 3, 4, tzinfo=timezone.utc),
            "nested": [True, 3, 1.5, None, {"unknown": "保留"}]}
        before = copy.deepcopy(raw)
        actual = self.prep._raw_json(raw)
        self.assertEqual(actual, {"day": "2020-01-02", "time": "2020-01-02T03:04:00+00:00",
            "nested": [True, 3, 1.5, None, {"unknown": "保留"}]})
        self.assertIs(actual["nested"][0], True)
        self.assertIs(type(actual["nested"][1]), int)
        self.assertIs(type(actual["nested"][2]), float)
        actual["nested"][-1]["unknown"] = "modified copy"
        self.assertEqual(raw, before)
        cyclic = []
        cyclic.append(cyclic)
        for value in (cyclic, {1: "key"}, {"object": object()}, {"bytes": b"x"}, {"number": float("nan")}):
            with self.subTest(kind=type(value).__name__), self.assertRaises(ValueError):
                self.prep._raw_json(value)

    def test_invalid_prepare_count_precedes_verified_source_loading(self):
        target = public.scratch() / "never-created"
        with patch.object(self.prep, "_load_verified", side_effect=AssertionError("source read before count")) as load:
            for count in (True, 1.0, "1", 0, -1, 201):
                with self.subTest(count=repr(count)), self.assertRaises(ValueError):
                    self.prep.prepare(target, count=count)
            load.assert_not_called()
        self.assertFalse(target.exists())

    def test_real_authorized_output_control_and_symlink_parent_refusal(self):
        parent = public.scratch()
        actual = parent / "actual"
        actual.mkdir()
        direct = actual / "never-created"
        self.assertEqual(self.prep._output_root(direct), direct)
        alias = parent / "alias"
        alias.symlink_to(actual, target_is_directory=True)
        with self.assertRaisesRegex(ValueError, "symlink_or_reparse"):
            self.prep._output_root(alias / "never-created")
        self.assertFalse(direct.exists())

    def test_second_file_fsync_failure_keeps_partial_output_and_original_error(self):
        target = public.scratch() / "partial"
        value = public.bundle(self.prep, [public.record("aaa")])
        original, failure = os.fsync, OSError("synthetic-second-file-fsync")
        calls = []
        def fsync(fd):
            calls.append(fd)
            if len(calls) == 2:
                raise failure
            return original(fd)
        with patch.object(self.prep.os, "fsync", side_effect=fsync):
            with self.assertRaises(OSError) as caught:
                self.prep._write_bundle(target, value, revalidate=lambda: None)
        self.assertIs(caught.exception, failure)
        self.assertTrue((target / "review-tasks.json").exists())
        self.assertTrue((target / "REVIEW.md").exists())
        self.assertFalse((target / "manifest.json").exists())
        before = public.files(target)
        with self.assertRaises((ValueError, OSError)):
            self.prep._write_bundle(target, value, revalidate=lambda: None)
        self.assertEqual(public.files(target), before)

    def test_pending_manifest_tamper_cannot_commit_complete_marker(self):
        target = public.scratch() / "partial"
        value = public.bundle(self.prep, [public.record("aaa")])
        observed = []
        def revalidate():
            pending = target / "manifest.pending.json"
            if pending.exists():
                observed.append(True)
                pending.write_text('{"human_gold":true}\n', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "written_material_drift"):
            self.prep._write_bundle(target, value, revalidate=revalidate)
        self.assertTrue(observed)
        self.assertFalse((target / "manifest.json").exists())
        self.assertEqual((target / "manifest.pending.json").read_text(encoding="utf-8"), '{"human_gold":true}\n')


if __name__ == "__main__":
    unittest.main(verbosity=2)
