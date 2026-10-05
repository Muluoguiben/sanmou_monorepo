"""Post-freeze independent probes; do not change the preimplementation suite."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import MagicMock, patch

import test_q02a_contract as contract
from qa_agent.knowledge.models import KnowledgeEntry, HeroStaticProfile
from qa_agent.quality_eval import runner

PACKAGE = Path(runner.__file__).resolve().parents[3]


class Q02aSupplementalTests(unittest.TestCase):
    def test_excluded_name_is_not_an_explicit_hero_subject(self):
        h = contract.Q02aIndependentContractTests()
        for question in ("不要介绍沈将，请只说明城建。", "沈将只是引文中的名字，本题只问城建。"):
            with self.subTest(question=question):
                agent, client = h.make()
                seeded = h.seed(agent, client, question)
                self.assertIn(contract.AID, [c.entry.id for c in seeded.evidence])
                reply = agent.ask(contract.FOLLOWUP)
                trace = dict(previous_question=question, previous_answer=seeded.answer,
                    resolution=reply.referent_resolution, resolved_question=reply.resolved_question,
                    answer_calls=len(client.answers), rewrite_calls=len(client.rewrites), answer=reply.answer)
                self.assertEqual(len(client.answers), 0, json.dumps(trace, ensure_ascii=False))
                self.assertEqual(len(client.rewrites), 0)
                self.assertEqual(reply.answer, h.fixed_clarification_control())

    def test_nonhero_metadata_cannot_supply_a_hero_referent(self):
        h = contract.Q02aIndependentContractTests()
        payload = contract.hero().model_dump()
        payload.update(domain="term", entry_kind="generic_rule")
        item = KnowledgeEntry.model_validate(payload)  # No model_copy validation bypass.
        self.assertIsInstance(item.structured_data, HeroStaticProfile)
        self.assertEqual(item.domain.value, "term")
        agent, client = h.make([item])
        seeded = h.seed(agent, client)
        reply = agent.ask(contract.FOLLOWUP)
        trace = dict(domain=item.domain.value, entry_kind=item.entry_kind.value,
            previous_answer=seeded.answer, resolution=reply.referent_resolution,
            resolved_question=reply.resolved_question, answer_calls=len(client.answers))
        self.assertEqual(len(client.answers), 0, json.dumps(trace, ensure_ascii=False))
        self.assertEqual(reply.answer, h.fixed_clarification_control())

    def test_foreign_lazy_referent_evaluator_is_rejected_before_call(self):
        name = "qa_agent.quality_eval.referent_cases"
        foreign = types.ModuleType(name)
        foreign.__file__ = "/tmp/q02a-foreign/referent_cases.py"
        foreign.__spec__ = importlib.util.spec_from_file_location(name, foreign.__file__)
        foreign.evaluate_referent_cases = MagicMock(side_effect=AssertionError("foreign evaluator executed"))
        with patch.dict(sys.modules, {name: foreign}):
            with self.assertRaisesRegex(ValueError, "execution source mismatch"):
                runner.run(PACKAGE, baseline="v3")
        foreign.evaluate_referent_cases.assert_not_called()

    def test_v3_suite_and_call_counts_are_strict(self):
        corpus = json.loads((PACKAGE / "tests/fixtures/quality_eval/v3/cases.json").read_text())
        for key in ("answer_calls", "rewrite_calls"):
            changed = copy.deepcopy(corpus)
            changed["multiturn_cases"][0]["expected"][key] = True
            with self.subTest(key=key), self.assertRaises(ValueError):
                runner._validate_corpus(changed, "v3")
        for value in (None, []):
            changed = copy.deepcopy(corpus)
            changed["multiturn_cases"] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                runner._validate_corpus(changed, "v3")
        changed = copy.deepcopy(corpus)
        changed.pop("multiturn_cases")
        with self.assertRaises(ValueError):
            runner._validate_corpus(changed, "v3")

    def test_historical_v1_v2_reject_current_production(self):
        for baseline in ("v1", "v2"):
            with self.subTest(baseline=baseline), self.assertRaisesRegex(ValueError, "source drift"):
                runner.run(PACKAGE, baseline=baseline)
