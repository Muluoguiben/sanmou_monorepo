from __future__ import annotations

import copy
from datetime import date
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import MagicMock, patch

from qa_agent.knowledge.models import Domain, EntryKind, KnowledgeEntry, LineupSolutionProfile
from qa_agent.quality_eval import runner
from qa_agent.quality_eval.season_cases import evaluate_season_cases, validate_cases
from qa_agent.retrieval.retriever import Retriever
from qa_agent.retrieval.seasonal import retrieve_lineups_for_season

PACKAGE = Path(__file__).resolve().parents[1]


def entry(identifier, tags=None, *, topic="合成阵容", priority=0, generic=False):
    return KnowledgeEntry(id=identifier, domain=Domain.TEAM if generic else Domain.SOLUTION,
        entry_kind=EntryKind.GENERIC_RULE if generic else EntryKind.LINEUP_SOLUTION,
        topic=topic, aliases=["合成别名"], facts=["仅用于合成赛季标签控制。"], source_ref="synthetic/" + identifier,
        updated_at=date(2026, 10, 6), confidence=1, priority=priority,
        structured_data=None if generic else LineupSolutionProfile(name=topic, season_tags=tags or []))


def case():
    return dict(id="control", split="development", review_status="developer-authored", query="合成阵容",
        season_tag="S1", top_k=1, entries=[entry("match", ["S1"]).model_dump(mode="json")],
        expected=dict(match_ids=["match"], mismatch=[], unknown=[]))


class SeasonalRetrieverTests(unittest.TestCase):
    def test_exact_three_groups_and_reasons(self):
        items = [entry("match", ["S1"]), entry("wrong", ["S10"]), entry("untagged"), entry("generic", generic=True)]
        result = retrieve_lineups_for_season(items, "合成阵容", season_tag="S1")
        self.assertEqual([c.entry.id for c in result.match], ["match"])
        self.assertEqual([(r.chunk.entry.id, r.reason) for r in result.mismatch], [("wrong", "season_mismatch")])
        self.assertEqual([(r.chunk.entry.id, r.reason) for r in result.unknown], [("untagged", "missing_season_tags"), ("generic", "not_lineup_solution")])
        self.assertEqual(result.execution_authority, "none")
        self.assertFalse(result.executable)

    def test_filter_before_top_k_avoids_wrong_season_flood(self):
        items = [entry("wrong-" + str(i), ["S2"], priority=100) for i in range(8)] + [entry("right", ["S1"])]
        self.assertNotEqual(Retriever(items).retrieve("合成阵容", top_k=1)[0].entry.id, "right")
        self.assertEqual(retrieve_lineups_for_season(items, "合成阵容", season_tag="S1", top_k=1).match[0].entry.id, "right")

    def test_global_duplicates_even_cross_season_unknown_and_unrelated(self):
        for second in (entry("same", ["S2"]), entry("same", generic=True), entry("same", ["S1"], topic="完全无关")):
            with self.subTest(second=second.entry_kind), patch.object(Retriever, "retrieve") as retrieve:
                with self.assertRaisesRegex(ValueError, "Duplicate"):
                    retrieve_lineups_for_season([entry("same", ["S1"]), second], "does-not-match", season_tag="S1")
                retrieve.assert_not_called()

    def test_multitag_exact_case_sensitive_no_unicode_alias(self):
        items = [entry("multi", ["S1", "S2"])]
        self.assertEqual(len(retrieve_lineups_for_season(items, "合成阵容", season_tag="S2").match), 1)
        for tag in ("s1", "S10", "Ｓ1", "*", "赛季1"):
            with self.subTest(tag=tag):
                result = retrieve_lineups_for_season(items, "合成阵容", season_tag=tag)
                self.assertEqual(result.match, [])
                self.assertEqual(len(result.mismatch), 1)

    def test_existing_model_strip_and_alias_query_reused(self):
        item = entry("model-strip", [" S1 "])
        self.assertEqual(item.structured_data.season_tags, ["S1"])
        result = retrieve_lineups_for_season([item], "合成别名", season_tag="S1")
        self.assertEqual(result.match[0].matched_query, "合成别名")

    def test_strict_request_arguments(self):
        for key, values in {"query": ("", " \n", None, 1, True),
                            "season_tag": ("", " ", " S1", "S1\n", None, 1, True),
                            "top_k": (0, -1, True, False, 1.0, "1", None)}.items():
            for value in values:
                args = dict(query="合成阵容", season_tag="S1", top_k=1)
                args[key] = value
                with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                    retrieve_lineups_for_season([], **args)

    def test_invalid_entry_container_types(self):
        for items in (None, (), {}, [None], [entry("valid").model_dump()]):
            with self.subTest(items=items), self.assertRaises(ValueError):
                retrieve_lineups_for_season(items, "合成阵容", season_tag="S1")

    def test_empty_and_unrelated_pools_no_diagnostic_dump(self):
        for items in ([], [entry("match", ["S1"]), entry("wrong", ["S2"]), entry("generic", generic=True)]):
            result = retrieve_lineups_for_season(items, "zz-nothing-relevant", season_tag="S1")
            self.assertEqual((result.match, result.mismatch, result.unknown), ([], [], []))

    def test_each_pool_cap_and_original_order(self):
        items = [entry("match" + str(i), ["S1"], priority=i) for i in range(4)]
        items += [entry("wrong" + str(i), ["S2"], priority=i) for i in range(4)]
        items += [entry("unknown" + str(i), priority=i) for i in range(4)]
        result = retrieve_lineups_for_season(items, "合成阵容", season_tag="S1", top_k=2)
        self.assertEqual([c.entry.id for c in result.match], ["match3", "match2"])
        self.assertEqual([r.chunk.entry.id for r in result.mismatch], ["wrong3", "wrong2"])
        self.assertEqual([r.chunk.entry.id for r in result.unknown], ["unknown3", "unknown2"])
        self.assertEqual(sum(map(len, (result.match, result.mismatch, result.unknown))), 6)

    def test_input_identity_and_default_retrieval_unchanged(self):
        items = [entry("right", ["S1"]), entry("wrong", ["S2"], priority=100)]
        original = copy.deepcopy(items)
        before = Retriever(items).retrieve("合成别名")
        result = retrieve_lineups_for_season(items, "合成别名", season_tag="S1")
        self.assertIs(result.match[0].entry, items[0])
        self.assertEqual(result.match[0].entry.source_ref, items[0].source_ref)
        self.assertEqual(items, original)
        self.assertEqual(Retriever(items).retrieve("合成别名"), before)

    def test_synthetic_control_and_valid_wrong_expected_fail_gate(self):
        self.assertTrue(evaluate_season_cases([case()])["gate_pass"])
        wrong = case()
        wrong["expected"]["match_ids"] = []
        result = evaluate_season_cases([wrong])
        self.assertFalse(result["gate_pass"])
        self.assertEqual((result["passed"], result["denominator"]), (0, 1))

    def test_exact_case_and_expected_keys(self):
        for level in ("case", "expected", "diagnostic"):
            for operation in ("add", "remove"):
                changed = case()
                if level == "case": target = changed
                elif level == "expected": target = changed["expected"]
                else:
                    changed["expected"]["match_ids"] = []
                    target = {"id": "match", "reason": "season_mismatch"}
                    changed["expected"]["mismatch"] = [target]
                if operation == "add": target["extra"] = 1
                else: target.pop(next(iter(target)))
                with self.subTest(level=level, operation=operation), self.assertRaises(ValueError): validate_cases([changed])

    def test_case_ids_group_types_and_control_metadata(self):
        for value in (None, {}, (), []):
            with self.assertRaises(ValueError): validate_cases(value)
        for key, value in (("id", ""), ("id", "  "), ("id", 7), ("top_k", True), ("top_k", 1.0),
                           ("season_tag", " S1"), ("query", ""), ("split", "holdout"),
                           ("review_status", "human-reviewed"), ("entries", ())):
            changed = case()
            changed[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): validate_cases([changed])
        with self.assertRaisesRegex(ValueError, "duplicate season case"):
            validate_cases([case(), case()])

    def test_expected_ids_types_duplicates_and_reasons(self):
        changes = [dict(match_ids=[True], mismatch=[], unknown=[]),
                   dict(match_ids=["absent"], mismatch=[], unknown=[]),
                   dict(match_ids=["match", "match"], mismatch=[], unknown=[]),
                   dict(match_ids=["match"], mismatch=[dict(id="match", reason="season_mismatch")], unknown=[]),
                   dict(match_ids=[], mismatch=[dict(id="match", reason="missing_season_tags")], unknown=[]),
                   dict(match_ids=[], mismatch=[], unknown=[dict(id="match", reason="season_mismatch")])]
        for expected in changes:
            changed = case()
            changed["expected"] = expected
            with self.subTest(expected=expected), self.assertRaises(ValueError): validate_cases([changed])

    def test_duplicate_entries_rejected_before_evaluating_any_control(self):
        changed = case()
        changed["entries"] *= 2
        with patch("qa_agent.quality_eval.season_cases.retrieve_lineups_for_season") as retrieve:
            with self.assertRaisesRegex(ValueError, "Duplicate"): evaluate_season_cases([case(), {**changed, "id": "other"}])
            retrieve.assert_not_called()

    def test_v4_requires_inherited_groups_and_season_cases(self):
        corpus = json.loads((PACKAGE / "tests/fixtures/quality_eval/v4/cases.json").read_text())
        for group in ("assessment_cases", "multiturn_cases", "season_cases"):
            for value in (None, [], {}, [{}]):
                with self.subTest(group=group, value=value), self.assertRaises(ValueError):
                    runner._validate_corpus({**corpus, group: value}, "v4")

    def test_v4_inherits_v3_cases_exactly(self):
        root = PACKAGE / "tests/fixtures/quality_eval"
        old = json.loads((root / "v3/cases.json").read_text())
        new = json.loads((root / "v4/cases.json").read_text())
        self.assertEqual(new.pop("version"), 4)
        self.assertTrue(new.pop("season_cases"))
        old.pop("version")
        self.assertEqual(new, old)

    def test_foreign_lazy_season_module_rejected_before_call(self):
        name = "qa_agent.quality_eval.season_cases"
        fake = types.ModuleType(name)
        fake.__file__ = "/tmp/foreign/season_cases.py"
        fake.__spec__ = importlib.util.spec_from_file_location(name, fake.__file__)
        fake.validate_cases = MagicMock(side_effect=AssertionError("foreign validation"))
        fake.evaluate_season_cases = MagicMock(side_effect=AssertionError("foreign evaluation"))
        with patch.dict(sys.modules, {name: fake}):
            with self.assertRaisesRegex(ValueError, "source mismatch"): runner.run(PACKAGE, baseline="v4")
        fake.validate_cases.assert_not_called()
        fake.evaluate_season_cases.assert_not_called()

    def test_cli_failed_gate_report_saved_create_only(self):
        result = {"quality_threshold": None, "season": evaluate_season_cases([{**case(), "expected": dict(match_ids=[], mismatch=[], unknown=[])}])}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "report.json"
            with patch.object(sys, "argv", ["runner", "--baseline", "v4", "--output", str(path)]), patch.object(runner, "run", return_value=result):
                with self.assertRaises(SystemExit) as error: runner.main()
                self.assertEqual(error.exception.code, 1)
                self.assertEqual(json.loads(path.read_text()), result)
                original = path.read_bytes()
                with self.assertRaises(FileExistsError): runner.main()
                self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
