"""Bounded E0 preparation checks; synthetic inputs never become human labels."""
from __future__ import annotations

import copy
from datetime import date, datetime, timezone
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import tempfile
import unittest
from unittest.mock import patch

from qa_agent.knowledge.models import KnowledgeEntry


PACKAGE = Path(__file__).resolve().parents[1]
REPOSITORY = PACKAGE.parents[1]
FIXTURE = PACKAGE / "tests/fixtures/quality_eval/e0_review_prep_v1/synthetic.json"
SPEC = importlib.util.spec_from_file_location(
    "prepare_e0_review", PACKAGE / "scripts/prepare_e0_review.py")
prep = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prep)

IDENTITY = {
    "split": "review_queue", "review_status": "unreviewed", "human_gold": False,
    "independent_holdout": False, "execution_authority": "none", "executable": False,
}
REVIEW_FIELDS = {
    "human_question", "answerability", "correct_evidence_ids", "required_facts",
    "forbidden_extrapolations", "applicability", "notes", "reviewer", "reviewed_at",
}


def records():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
    if fixture["synthetic"] is not True:
        raise AssertionError("test fixture must remain synthetic")
    result = []
    for index, raw in enumerate(fixture["entries"]):
        source = json.dumps(raw, ensure_ascii=False, sort_keys=True, allow_nan=False)
        result.append({
            "source_path": f"knowledge_sources/synthetic-{raw['id']}.yaml",
            "record_index": index,
            "source_text_sha256": hashlib.sha256(source.encode("utf-8")).hexdigest(),
            "raw_record": copy.deepcopy(raw),
            "entry": KnowledgeEntry.model_validate(raw).model_dump(mode="json"),
        })
    return result


def build(items=None, count=6, queries=None, evidence=None):
    return prep._build_tasks(
        records() if items is None else items, count=count,
        development_queries=[] if queries is None else queries,
        development_evidence_ids=[] if evidence is None else evidence)


def bundle():
    items = records()
    result = build(items)
    return {
        "protocol": "qa-e0-review-prep/v1", **IDENTITY, "quality_threshold": None,
        "upstream": {"synthetic_test_input": True,
                     "script_sha256": hashlib.sha256(Path(SPEC.origin).read_bytes()).hexdigest()},
        "selection": result["selection"], "tasks": result["tasks"],
        "sources": [{"source_path": r["source_path"],
                     "source_text_sha256": r["source_text_sha256"]} for r in items],
    }


class PrepareE0ReviewTests(unittest.TestCase):
    def assert_unreviewed(self, value):
        for field, expected in IDENTITY.items():
            self.assertEqual(value[field], expected, field)
        if "human_review" in value:
            self.assertEqual(set(value["human_review"]), REVIEW_FIELDS)
            self.assertTrue(all(v is None for v in value["human_review"].values()))

    def test_verify_is_offline_and_does_not_upgrade_review_identity(self):
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), patch(
                "socket.create_connection", side_effect=AssertionError("network forbidden")), patch(
                "qa_agent.chat.llm_client.build_llm_client", side_effect=AssertionError("provider forbidden")):
            report = prep.verify()
        self.assertIsInstance(report, dict)
        self.assertEqual(report["protocol"], "qa-e0-review-prep/v1")
        self.assertEqual(report["provider_calls"], 0)
        self.assertEqual(report["human_reviewed_labels"], 0)
        self.assertEqual(report["execution_authority"], "none")
        self.assertIs(report["executable"], False)
        self.assertIs(report["human_gold"], False)
        self.assertIs(report["independent_holdout"], False)
        self.assertIsNone(report["quality_threshold"])

    def test_canonical_json_is_stable_utf8_and_rejects_nonfinite_numbers(self):
        self.assertEqual(prep._canonical({"乙": [1, None], "a": 2}),
                         '{"a":2,"乙":[1,null]}')
        self.assertEqual(prep._canonical({"a": 2, "乙": [1, None]}),
                         prep._canonical({"乙": [1, None], "a": 2}))
        for value in (float("nan"), float("inf"), -float("inf")):
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                prep._canonical({"number": value})

    def test_raw_json_preserves_dates_and_rejects_unsupported_data(self):
        raw = {"day": date(2026, 10, 18),
               "nested": [{"time": datetime(2026, 10, 18, 12, 30, tzinfo=timezone.utc)}]}
        actual = prep._raw_json(raw)
        self.assertEqual(actual, {"day": "2026-10-18",
                                 "nested": [{"time": "2026-10-18T12:30:00+00:00"}]})
        actual["nested"][0]["time"] = "changed"
        self.assertIsInstance(raw["nested"][0]["time"], datetime)
        for value in ({1: "non-string-key"}, {"bad": object()}, {"bad": {1, 2}},
                      {"bad": b"bytes"}, {"bad": float("nan")}, {"bad": float("inf")}):
            with self.subTest(type=type(next(iter(value.values()))).__name__), self.assertRaises(
                    (ValueError, TypeError)):
                prep._raw_json(value)

    def test_domain_round_robin_and_ids_are_deterministic(self):
        inputs = records()
        before = copy.deepcopy(inputs)
        first, second = build(inputs), build(list(reversed(inputs)))
        self.assertEqual(inputs, before)
        self.assertEqual(prep._canonical(first), prep._canonical(second))
        self.assertEqual([t["anchor_entry_id"] for t in first["tasks"]],
                         ["hero-a", "resource-a", "skill-a", "solution-a", "status-a", "hero-b"])
        self.assertEqual(len({t["task_id"] for t in first["tasks"]}), 6)
        self.assertIn("domain-id-round-robin/v1", prep._canonical(first["selection"]))

    def test_count_must_be_bounded_real_integer_and_never_silently_shortened(self):
        for count in (True, False, 0, -1, 201, "2", 2.0, None, 7):
            with self.subTest(count=count), self.assertRaises((ValueError, TypeError)):
                build(count=count)

    def test_duplicate_ids_are_rejected_before_exclusion(self):
        items = records()
        items.append(copy.deepcopy(items[0]))
        with self.assertRaises((ValueError, TypeError)):
            build(items, count=1, evidence=["hero-a"])

    def test_development_evidence_and_proposed_question_duplicates_are_excluded(self):
        first = build(count=1)["tasks"][0]
        by_id = build(count=1, evidence=[first["anchor_entry_id"]])
        self.assertNotEqual(by_id["tasks"][0]["anchor_entry_id"], first["anchor_entry_id"])
        by_query = build(count=1, queries=[first["proposed_question"]])
        self.assertNotEqual(by_query["tasks"][0]["proposed_question"], first["proposed_question"])
        self.assertIn(first["anchor_entry_id"], prep._canonical(by_id["selection"]))
        self.assertIn(first["anchor_entry_id"], prep._canonical(by_query["selection"]))

    def test_one_hop_candidates_retain_conflicting_and_related_records(self):
        task = build(count=1)["tasks"][0]
        self.assertEqual(task["anchor_entry_id"], "hero-a")
        self.assertEqual(task["candidate_entry_ids"], ["hero-a", "hero-b", "skill-a"])
        self.assertEqual([r["entry"]["id"] for r in task["candidate_entries"]],
                         task["candidate_entry_ids"])
        self.assertNotIn("status-a", task["candidate_entry_ids"])
        self.assertEqual(task["conflict_assessment"], "unassessed")

    def test_complete_raw_and_structured_qualifiers_are_not_summarized(self):
        source = {r["entry"]["id"]: r for r in records()}
        for task in build()["tasks"]:
            for candidate in task["candidate_entries"]:
                original = source[candidate["entry"]["id"]]
                for key in ("entry", "raw_record", "source_path", "record_index", "source_text_sha256"):
                    self.assertEqual(candidate[key], original[key], key)
        hero = source["hero-a"]["entry"]["structured_data"]
        self.assertEqual(len(hero["signature_skills"]), 4)
        self.assertEqual(len(hero["notes"]), 3)
        self.assertEqual(len(source["solution-a"]["entry"]["structured_data"]["season_tags"]), 3)

    def test_raw_metadata_cannot_promote_identity_or_prefill_human_answers(self):
        items = records()
        items[0]["raw_record"].update({
            "human_gold": True, "independent_holdout": True, "review_status": "human-reviewed",
            "execution_authority": "forged", "executable": True, "task_id": "FORGED-ID",
            "human_review": {"reviewer": "FORGED-REVIEWER", "answerability": "answerable"},
        })
        result = build(items)
        self.assertIn("FORGED-REVIEWER", prep._canonical(result))
        for task in result["tasks"]:
            self.assert_unreviewed(task)
            self.assertEqual(task["question_origin"], "template/developer-proposed")
            self.assertEqual(task["conflict_assessment"], "unassessed")
            self.assertNotEqual(task["task_id"], "FORGED-ID")
            self.assertNotIn("answer_sha256", task)
            self.assertNotIn("claim_annotation", task)
            self.assertIsNone(task["human_review"]["applicability"])

    def test_review_rendering_escapes_untrusted_html_links_and_fences(self):
        value = bundle()
        payload = '</pre><script>alert("synthetic")</script>\n![evil](https://invalid.example/)\n```\n# forged'
        value["tasks"][0]["candidate_entries"][0]["raw_record"]["untrusted"] = payload
        rendered = prep._render_review(value)
        self.assertNotIn("</pre><script>", rendered)
        self.assertNotIn('<script>alert("synthetic")</script>', rendered)
        self.assertIn("synthetic", rendered)
        fences = list(re.finditer(r"(?m)^(`{3,})(?:json)?\s*$", rendered))
        self.assertEqual(len(fences), 2)
        self.assertEqual(fences[0].group(1), fences[1].group(1))
        self.assertGreater(len(fences[0].group(1)), 3)
        encoded = rendered[fences[0].end():fences[1].start()].strip()
        self.assertEqual(json.loads(html.unescape(encoded)), value)

    def test_review_instructions_keep_hash_bound_material_immutable(self):
        rendered = prep._render_review(bundle())
        for phrase in ("不可变", "独立答复副本", "不导入", "不批准", "human-responses.json"):
            self.assertIn(phrase, rendered)

    def test_output_root_rejects_forbidden_paths_without_boundary_mock(self):
        paths = [PACKAGE / "src" / "e0-forbidden", PACKAGE / "knowledge_sources" / "e0-forbidden",
                 REPOSITORY / ".git" / "e0-forbidden", PACKAGE,
                 REPOSITORY.parent / "e0-forbidden-outside-repository",
                 REPOSITORY / "data/agent_runs/../../packages/e0-forbidden"]
        for path in paths:
            with self.subTest(path=str(path)), self.assertRaises((ValueError, OSError)):
                prep._output_root(Path(path))

    def test_writer_rejects_promoted_identity_or_prefilled_answers_before_io(self):
        mutations = (
            lambda value: value.__setitem__("human_gold", True),
            lambda value: value.__setitem__("independent_holdout", True),
            lambda value: value["tasks"][0].__setitem__("review_status", "human-reviewed"),
            lambda value: value["tasks"][0].__setitem__("executable", True),
            lambda value: value["tasks"][0]["human_review"].__setitem__("answerability", "answerable"),
        )
        for index, mutate in enumerate(mutations):
            value = bundle()
            mutate(value)
            with self.subTest(index=index), patch.object(prep, "_output_root") as boundary:
                with self.assertRaises((ValueError, TypeError)):
                    prep._write_bundle(PACKAGE / "unused-test-output", value, revalidate=lambda: None)
                boundary.assert_not_called()

    def test_writer_is_reproducible_and_commits_manifest_after_revalidation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outputs = [root / "first", root / "second"]
            for output in outputs:
                validation_calls = []
                def revalidate():
                    validation_calls.append(output.exists())
                    if not output.exists():
                        return
                    self.assertTrue((output / "review-tasks.json").is_file())
                    self.assertTrue((output / "REVIEW.md").is_file())
                    self.assertTrue((output / "manifest.pending.json").is_file())
                    self.assertFalse((output / "manifest.json").exists())
                with patch.object(prep, "_output_root", return_value=output):
                    result = prep._write_bundle(output, bundle(), revalidate=revalidate)
                self.assertEqual(validation_calls, [False, True])
                manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                self.assertEqual(result["manifest"], manifest)
                for name in ("review-tasks.json", "REVIEW.md"):
                    raw = (output / name).read_bytes()
                    raw.decode("utf-8")
                    self.assertNotIn(b"\r", raw)
                    self.assertEqual(manifest["artifact_sha256"][name], hashlib.sha256(raw).hexdigest())
                self.assertEqual((output / "manifest.pending.json").read_bytes(),
                                 (output / "manifest.json").read_bytes())
            for name in ("review-tasks.json", "REVIEW.md", "manifest.pending.json", "manifest.json"):
                self.assertEqual((outputs[0] / name).read_bytes(), (outputs[1] / name).read_bytes())

    def test_existing_directory_or_file_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for kind in ("directory", "file"):
                output = root / kind
                if kind == "directory":
                    output.mkdir()
                    sentinel = output / "sentinel.txt"
                else:
                    sentinel = output
                sentinel.write_text("unchanged", encoding="utf-8", newline="\n")
                with patch.object(prep, "_output_root", return_value=output), self.assertRaises(
                        (ValueError, OSError)):
                    prep._write_bundle(output, bundle(), revalidate=lambda: None)
                self.assertEqual(sentinel.read_text(encoding="utf-8"), "unchanged")

    def test_fsync_failure_preserves_partial_files_without_complete_manifest(self):
        original_fsync = os.fsync
        for fail_at in (1, 3):
            with self.subTest(fail_at=fail_at), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "partial"
                count = 0
                def fail_fsync(fd):
                    nonlocal count
                    count += 1
                    if count == fail_at:
                        raise OSError("synthetic fsync failure")
                    return original_fsync(fd)
                with patch.object(prep, "_output_root", return_value=output), patch.object(
                        prep.os, "fsync", side_effect=fail_fsync), self.assertRaises(OSError):
                    prep._write_bundle(output, bundle(), revalidate=lambda: None)
                self.assertTrue(output.is_dir())
                self.assertTrue((output / "review-tasks.json").exists())
                self.assertFalse((output / "manifest.json").exists())
                before = {p.name: p.read_bytes() for p in output.iterdir()}
                with patch.object(prep, "_output_root", return_value=output), self.assertRaises(
                        (ValueError, OSError)):
                    prep._write_bundle(output, bundle(), revalidate=lambda: None)
                self.assertEqual({p.name: p.read_bytes() for p in output.iterdir()}, before)

    def test_link_failure_keeps_pending_and_never_publishes_complete_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "link-failure"
            with patch.object(prep, "_output_root", return_value=output), patch.object(
                    prep.os, "link", side_effect=OSError("synthetic link failure")), self.assertRaises(OSError):
                prep._write_bundle(output, bundle(), revalidate=lambda: None)
            self.assertTrue((output / "manifest.pending.json").is_file())
            self.assertTrue((output / "review-tasks.json").is_file())
            self.assertTrue((output / "REVIEW.md").is_file())
            self.assertFalse((output / "manifest.json").exists())

    def test_revalidation_failure_cannot_commit_partial_bundle(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "drift"
            def reject_drift():
                if not output.exists():
                    return
                self.assertTrue((output / "manifest.pending.json").exists())
                raise ValueError("synthetic source drift")
            with patch.object(prep, "_output_root", return_value=output), self.assertRaises(ValueError):
                prep._write_bundle(output, bundle(), revalidate=reject_drift)
            self.assertTrue((output / "manifest.pending.json").exists())
            self.assertFalse((output / "manifest.json").exists())

    def test_post_revalidation_artifact_readback_detects_tampering(self):
        for name in ("review-tasks.json", "REVIEW.md"):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as temporary:
                output = Path(temporary) / "tampered"
                def tamper():
                    if output.exists():
                        (output / name).write_text("synthetic changed bytes\n", encoding="utf-8", newline="\n")
                with patch.object(prep, "_output_root", return_value=output), self.assertRaises(
                        (ValueError, OSError)):
                    prep._write_bundle(output, bundle(), revalidate=tamper)
                self.assertTrue((output / "manifest.pending.json").exists())
                self.assertFalse((output / "manifest.json").exists())


if __name__ == "__main__":
    unittest.main()
