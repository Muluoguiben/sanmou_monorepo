"""Memo-only Q-E0 preparation probes: synthetic inputs, no real 50-task pack.

Freeze before implementing-source access. Private test seams were declared by
the author as signatures/schema only; the public surface remains the CLI.
"""
from __future__ import annotations

import copy
import hashlib
import html
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from uuid import uuid4

from qa_agent.knowledge.models import KnowledgeEntry

ROOT = Path(__file__).resolve().parents[3]
PACKAGE = ROOT / "packages/qa-agent"
SCRIPT = PACKAGE / "scripts/prepare_e0_review.py"
HUMAN_FIELDS = {
    "human_question", "answerability", "correct_evidence_ids", "required_facts",
    "forbidden_extrapolations", "applicability", "notes", "reviewer", "reviewed_at",
}
IDENTITY = dict(review_status="unreviewed", human_gold=False,
    independent_holdout=False, execution_authority="none", executable=False)
ENCODING = "yaml-safe-data-json/date-and-datetime-iso8601-v1"


def text_hash(text):
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def source_text(raw):
    # JSON is a YAML subset; these fixtures never touch formal KB files.
    return json.dumps({"entries": [raw]}, ensure_ascii=False, sort_keys=True,
                      allow_nan=False) + "\n"


def record(identity, domain="building", *, topic=None, aliases=(), related=(),
           facts=None, constraints=None, source_ref=None, raw_extra=None, profile=None):
    raw = dict(id=identity, domain=domain, topic=topic or "合成主题-" + identity,
        aliases=list(aliases), facts=facts or ["合成事实-" + identity],
        constraints=constraints or ["仅适用于明确条件；未知版本不得外推"],
        source_type="manual_rule", source_ref=source_ref or "synthetic:" + identity,
        updated_at="2026-10-18", confidence=0.5, related_topics=list(related), priority=1)
    if profile is not None:
        raw.update(entry_kind="hero_profile", structured_data=profile)
    raw.update(raw_extra or {})
    entry = KnowledgeEntry.model_validate(raw).model_dump(mode="json")
    return dict(source_path="knowledge_sources/synthetic-" + identity + ".yaml",
        record_index=0, source_text_sha256=text_hash(source_text(raw)),
        raw_record=raw, entry=entry)


def build(module, records, count=1, excluded=(), queries=()):
    return module._build_tasks(copy.deepcopy(records), count=count,
        development_queries=list(queries), development_evidence_ids=list(excluded))


def bundle(module, records, count=1):
    selected = build(module, records, count)
    return dict(protocol="qa-e0-review-prep/v1", split="review_queue", **IDENTITY,
        quality_threshold=None, raw_record_encoding=ENCODING,
        upstream={"script_sha256": "0" * 64, "synthetic_probe": True},
        sources={row["source_path"]: dict(text=source_text(row["raw_record"]),
            content_sha256=row["source_text_sha256"]) for row in records}, **selected)


def scratch():
    parent = Path(os.environ["TMPDIR"]).resolve()
    result = parent / ("qe0-independent-" + uuid4().hex)
    result.mkdir(exist_ok=False)
    return result


def files(path):
    return {item.name: item.read_bytes() for item in path.iterdir() if item.is_file()}


def load_product():
    if not SCRIPT.is_file():
        raise RuntimeError("requires fixed implementing source; do not run on absent baseline")
    spec = importlib.util.spec_from_file_location("qe0_preparation_under_review", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class PreparationSyntheticProbes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.product = load_product()

    def assert_identity(self, value):
        for key, expected in IDENTITY.items():
            self.assertEqual(value[key], expected, key)
            if type(expected) is bool:
                self.assertIs(value[key], expected, key)

    def test_exact_round_robin_count_after_exclusion_and_order_independence(self):
        rows = [record("b02"), record("b01"), record("c02", "combat"),
                record("c01", "combat"), record("t02", "term"), record("t01", "term")]
        first = build(self.product, rows, count=5, excluded=["b01"])
        second = build(self.product, list(reversed(rows)), count=5, excluded=["b01"])
        self.assertEqual(first, second)
        expected = ["b02", "c01", "t01", "c02", "t02"]
        self.assertEqual([task["anchor_entry_id"] for task in first["tasks"]], expected)
        self.assertEqual(first["selection"]["anchor_entry_ids"], expected)
        self.assertEqual(first["selection"]["algorithm"], "domain-id-round-robin/v1")
        self.assertEqual(first["selection"]["domain_counts"], {"building": 1, "combat": 2, "term": 2})
        self.assertEqual(first["selection"]["count"], 5)
        self.assertEqual(len({task["task_id"] for task in first["tasks"]}), 5)
        with self.assertRaises(ValueError):
            build(self.product, rows, count=6, excluded=["b01"])

    def test_strict_count_and_global_duplicate_rejection(self):
        rows = [record("aaa"), record("bbb")]
        for count in (0, -1, True, False, 1.0, "1", 201):
            with self.subTest(count=repr(count)), self.assertRaises(ValueError):
                build(self.product, rows, count=count)
        with self.assertRaises(ValueError):
            build(self.product, rows + [copy.deepcopy(rows[-1])], count=1)
        many = [record("entry-" + str(index).zfill(3)) for index in range(201)]
        self.assertEqual(len(build(self.product, many, count=200)["tasks"]), 200)

    def test_development_question_duplicate_is_excluded_before_count(self):
        rows = [record("aaa"), record("bbb")]
        question = build(self.product, rows, count=1)["tasks"][0]["proposed_question"]
        actual = build(self.product, rows, count=1, queries=[question])
        self.assertEqual(actual["tasks"][0]["anchor_entry_id"], "bbb")
        self.assertIn("aaa", actual["selection"]["excluded_development_query_anchor_ids"])
        with self.assertRaises(ValueError):
            build(self.product, rows, count=2, queries=[question])

    def test_one_hop_metadata_does_not_become_transitive_or_same_source_closure(self):
        rows = [record("a01", topic="甲", related=["乙"], source_ref="synthetic:shared"),
            record("b01", topic="乙", aliases=["丙"]), record("c01", topic="丙"),
            record("d01", topic="丁", source_ref="synthetic:shared"),
            record("e01", topic="戊", related=["甲"])]
        task = build(self.product, rows)["tasks"][0]
        self.assertEqual(task["anchor_entry_id"], "a01")
        self.assertEqual(task["candidate_entry_ids"], ["a01", "b01", "e01"])
        self.assertEqual([row["entry"]["id"] for row in task["candidate_entries"]], ["a01", "b01", "e01"])
        reasons = task["family_hints"]["candidate_match_reasons"]
        self.assertIn("related_topic_outbound", reasons["b01"])
        self.assertIn("related_topic_inbound", reasons["e01"])
        self.assertEqual(task["conflict_assessment"], "unassessed")

    def test_raw_machine_field_collision_is_preserved_separately_or_explicitly_rejected(self):
        collision = dict(task_id="FORGED", candidate_entry_ids=["FORGED"],
            review_status="human-reviewed", human_gold=True, independent_holdout=True,
            execution_authority="execute", executable=True,
            human_review={key: "FORGED" for key in HUMAN_FIELDS})
        clean = record("aaa")
        build(self.product, [clean])  # Establish a valid control before the mutation.
        row = record("aaa", raw_extra=collision)
        try:
            result = build(self.product, [row])
        except ValueError:
            return  # Contract permits an explicit unsupported-raw-field refusal.
        task = result["tasks"][0]
        self.assert_identity(task)
        self.assertNotEqual(task["task_id"], "FORGED")
        self.assertEqual(task["candidate_entry_ids"], ["aaa"])
        self.assertEqual(task["human_review"], {key: None for key in HUMAN_FIELDS})
        self.assertEqual(task["candidate_entries"][0]["raw_record"], row["raw_record"])

    def test_complete_evidence_and_raw_normalized_boundary_survive_rendering(self):
        marker = '<script>not executable</script> [link](javascript:alert(1)) ![img](https://example.invalid/x) | `````````'
        profile = dict(name="合成武将", aliases=["别名"], faction=None, rarity=None,
            troop_types=["骑", "枪"], role_tags=["前排"],
            base_attributes={"military": 1, "intelligence": None, "command": 2, "initiative": None},
            growth_attributes={"military": 1.2, "intelligence": None, "command": 0.5, "initiative": None},
            max_attributes={"military": 100, "intelligence": None, "command": 200, "initiative": None},
            signature_skills=["技能" + str(i) for i in range(8)],
            notes=["完整备注" + str(i) for i in range(9)] + [marker])
        row = record("hero-a", "hero", topic="合成武将", profile=profile,
            facts=["事实" + str(i) for i in range(12)] + [marker, "另一说法相反；需人工核对"],
            constraints=["仅 S1，条件 A 与 B 同时成立；不适用 S2", "版本未明，禁止全版本外推"],
            source_ref="synthetic source\n" + marker)
        data = bundle(self.product, [row])
        original = copy.deepcopy(data)
        task = data["tasks"][0]
        self.assert_identity(task)
        self.assertEqual(task["question_origin"], "template/developer-proposed")
        self.assertEqual(task["human_review"], {key: None for key in HUMAN_FIELDS})
        actual = task["candidate_entries"][0]
        self.assertEqual(actual["entry"], row["entry"])
        self.assertEqual(actual["raw_record"], row["raw_record"])
        self.assertRegex(actual["entry_content_sha256"], r"^[0-9a-f]{64}$")
        self.assertRegex(actual["raw_record_sha256"], r"^[0-9a-f]{64}$")
        rendered = self.product._render_review(data)
        self.assertEqual(data, original)
        self.assertNotIn("\r", rendered)
        lines = rendered.splitlines()
        complete_blocks = []
        for start, line in enumerate(lines):
            opening = re.fullmatch(r"(`{3,})(?:json)?", line)
            if not opening:
                continue
            fence = opening.group(1)
            try:
                end = next(i for i in range(start + 1, len(lines)) if lines[i] == fence)
                body = "\n".join(lines[start + 1:end])
                if json.loads(html.unescape(body)) == data:
                    complete_blocks.append((start, end, fence, body))
            except (StopIteration, ValueError):
                continue
        self.assertTrue(complete_blocks, "complete literal bundle was not preserved")
        start, end, fence, body = complete_blocks[0]
        self.assertGreater(len(fence), max((len(run) for run in re.findall(r"`+", body)), default=0))
        self.assertIn("&lt;script&gt;", body)
        self.assertEqual(json.loads(html.unescape(body)), data)
        outside = "\n".join(lines[:start] + lines[end + 1:])
        self.assertNotIn("javascript:", outside)
        self.assertNotIn("https://example.invalid", outside)
        self.assertRegex(outside, r"[\u4e00-\u9fff]")

    def test_create_only_writer_is_deterministic_and_final_is_pending_hardlink(self):
        data = bundle(self.product, [record("aaa"), record("bbb", "combat")], count=2)
        parent = scratch()
        targets = [parent / "first", parent / "second"]
        for target in targets:
            self.product._write_bundle(target, copy.deepcopy(data), revalidate=lambda: None)
            self.assertEqual(json.loads((target / "review-tasks.json").read_text(encoding="utf-8")), data)
            manifest = json.loads((target / "manifest.json").read_text(encoding="utf-8"))
            encoded = json.dumps(manifest, sort_keys=True)
            for name in ("review-tasks.json", "REVIEW.md"):
                raw = (target / name).read_bytes()
                self.assertNotIn(b"\r", raw)
                self.assertIn(hashlib.sha256(raw).hexdigest(), encoded)
            self.assertNotIn(str(target), encoded)
            self.assertTrue((target / "manifest.json").samefile(target / "manifest.pending.json"))
            before = files(target)
            with self.assertRaises((ValueError, OSError)):
                self.product._write_bundle(target, copy.deepcopy(data), revalidate=lambda: None)
            self.assertEqual(files(target), before)
        self.assertEqual(files(targets[0]), files(targets[1]))

    def test_final_source_failure_tampered_written_bytes_and_marker_collision_fail_closed(self):
        data = bundle(self.product, [record("aaa")])
        for cut in ("source_error", "changed_review", "existing_marker"):
            with self.subTest(cut=cut):
                target, reached = scratch() / "bundle", []
                def revalidate():
                    if not (target / "manifest.pending.json").exists() or reached:
                        return
                    reached.append(True)
                    self.assertTrue((target / "review-tasks.json").is_file())
                    self.assertTrue((target / "REVIEW.md").is_file())
                    if cut == "source_error":
                        raise ValueError("synthetic_source_drift")
                    if cut == "changed_review":
                        (target / "REVIEW.md").write_text("synthetic changed material\n", encoding="utf-8")
                    else:
                        (target / "manifest.json").write_bytes(b"synthetic-existing-marker")
                with self.assertRaises((ValueError, OSError)):
                    self.product._write_bundle(target, copy.deepcopy(data), revalidate=revalidate)
                self.assertTrue(reached, "did not reach the declared final revalidation boundary")
                self.assertTrue((target / "manifest.pending.json").exists())
                if cut == "existing_marker":
                    self.assertEqual((target / "manifest.json").read_bytes(), b"synthetic-existing-marker")
                else:
                    self.assertFalse((target / "manifest.json").exists())
                before = files(target)
                with self.assertRaises((ValueError, OSError)):
                    self.product._write_bundle(target, copy.deepcopy(data), revalidate=lambda: None)
                self.assertEqual(files(target), before)


class PreparationCliProbes(unittest.TestCase):
    def test_invalid_count_syntax_and_forbidden_capability_flags_are_arg_errors(self):
        if not SCRIPT.is_file():
            raise RuntimeError("requires fixed implementing source")
        target = scratch() / "never-created"
        for value in ("0", "-1", "1.0", "true", "201", "+1", "01", " 1", "1_0", "1e2"):
            with self.subTest(count=value):
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "prepare",
                    "--output", str(target), "--count", value], cwd=PACKAGE,
                    capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 2)
                self.assertFalse(target.exists())
        for flag in ("--approve", "--publish", "--provider", "--input", "--catalog", "--baseline"):
            with self.subTest(flag=flag):
                result = subprocess.run([sys.executable, "-B", str(SCRIPT), "verify", flag],
                    cwd=PACKAGE, capture_output=True, timeout=60)
                self.assertEqual(result.returncode, 2)


if __name__ == "__main__":
    if sys.argv[1:] == ["--check-fixtures"]:
        rows = [record("aaa"), record("bbb", "combat"), record("ccc", "term")]
        assert len({row["entry"]["id"] for row in rows}) == 3
        assert len(HUMAN_FIELDS) == 9
        print("synthetic fixture controls valid; no preparation module imported")
    else:
        unittest.main(verbosity=2)
