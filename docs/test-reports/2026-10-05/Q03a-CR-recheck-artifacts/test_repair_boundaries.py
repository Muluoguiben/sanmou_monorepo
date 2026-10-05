"""New reviewer cases: lazy origins and conservative-but-not-refusing notes."""
import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

from test_independent_q03a import profile, invoke
from qa_agent.quality_eval import runner
from qa_agent.quality_eval import assessment_cases
import qa_agent

PACKAGE = Path(runner.__file__).resolve().parents[3]

class RepairBoundaryTests(unittest.TestCase):
    def test_foreign_lazy_dependency_is_rejected_before_call(self):
        name = "qa_agent.quality_eval.assessment_cases"
        foreign = types.ModuleType(name)
        foreign.__file__ = "/tmp/independent-foreign-lazy/assessment_cases.py"
        foreign.__spec__ = importlib.util.spec_from_file_location(name, foreign.__file__)
        foreign.evaluate_cases = MagicMock(side_effect=AssertionError("foreign evaluator executed"))
        with patch.dict(sys.modules, {name: foreign}):
            with self.assertRaisesRegex(ValueError, "execution source mismatch"):
                runner.run(PACKAGE, baseline="v2")
        foreign.evaluate_cases.assert_not_called()

    def test_late_foreign_module_is_rejected_before_result(self):
        name = "qa_agent.review_foreign_late"
        foreign = types.ModuleType(name)
        foreign.__file__ = "/tmp/independent-foreign-late.py"
        foreign.__spec__ = importlib.util.spec_from_file_location(name, foreign.__file__)
        original = assessment_cases.evaluate_cases
        def injected(cases):
            result = original(cases)
            sys.modules[name] = foreign
            return result
        try:
            with patch.object(assessment_cases, "evaluate_cases", injected):
                with self.assertRaisesRegex(ValueError, "execution source mismatch"):
                    runner.run(PACKAGE, baseline="v2")
        finally:
            sys.modules.pop(name, None)

    def test_correct_file_but_foreign_spec_origin_is_rejected(self):
        module = sys.modules["qa_agent.retrieval.retriever"]
        with patch.object(module.__spec__, "origin", "/tmp/foreign-retriever.py"):
            with self.assertRaisesRegex(ValueError, "execution source mismatch"):
                runner.run(PACKAGE, baseline="v2")

    def test_extra_package_search_root_is_rejected(self):
        with patch.object(qa_agent, "__path__", [*qa_agent.__path__, "/tmp/foreign-qa-root"]):
            with self.assertRaisesRegex(ValueError, "package search path mismatch"):
                runner.run(PACKAGE, baseline="v2")

    def test_benign_notes_downgrade_but_do_not_refuse(self):
        reply, client = invoke("丙将初始武力是多少", [profile("review-a", notes=("普通资料备注",))])
        self.assertEqual((reply.assessment.status, reply.assessment.check_scope), ("partial", "unassessed"))
        self.assertEqual(client.generate.call_count, 1)
        prompt = client.generate.call_args.kwargs["user_message"]
        self.assertIn("普通资料备注", prompt)
        self.assertIn("适用性未评估", prompt)
        self.assertIn("review-source:review-a", prompt)

    def test_disjoint_fact_scopes_are_preserved_in_actual_prompt(self):
        a = profile("review-a", base=21, facts=["S1 期间初始武力21"])
        b = profile("review-b", base=31, facts=["S2 期间初始武力31"])
        reply, client = invoke("丙将初始武力是多少", [a, b])
        self.assertEqual(reply.assessment.check_scope, "unassessed")
        self.assertEqual(client.generate.call_count, 1)
        prompt = client.generate.call_args.kwargs["user_message"]
        for marker in ("S1", "S2", "review-source:review-a", "review-source:review-b"):
            self.assertIn(marker, prompt)

    def test_clean_same_scope_conflict_still_stops_answer(self):
        reply, client = invoke("丙将初始武力是多少", [profile("review-a", base=0), profile("review-b", base=1)])
        self.assertEqual(reply.assessment.status, "conflicting")
        client.generate.assert_not_called()
        self.assertIn("[review-a]", reply.answer)
        self.assertIn("[review-b]", reply.answer)

    def test_missing_scalar_notes_keep_body_and_missing_reason(self):
        reply, client = invoke("丙将初始武力是多少", [profile("review-a", base=None,
            notes=("普通描述", "初始武力在正文记为37"))])
        self.assertEqual(reply.assessment.status, "partial")
        self.assertIn("missing_structured_value", reply.assessment.reasons)
        self.assertEqual(client.generate.call_count, 1)
        self.assertIn("初始武力在正文记为37", client.generate.call_args.kwargs["user_message"])
