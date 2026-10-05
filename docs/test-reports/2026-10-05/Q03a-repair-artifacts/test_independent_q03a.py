"""Reviewer-owned synthetic probes, independent of implementation test helpers."""
import copy
from datetime import date
import json
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

from qa_agent.chat.agent import ChatAgent, ChatTurn
from qa_agent.chat.evidence_assessment import assess_evidence
from qa_agent.chat.llm_client import LLMResult
from qa_agent.knowledge.models import (AttributeGrowth, AttributeSet,
    HeroStaticProfile, KnowledgeEntry, LineupSolutionProfile, StatusProfile)
from qa_agent.quality_eval import runner
from qa_agent.quality_eval.scoring import digest
from qa_agent.retrieval.retriever import RetrievedChunk, Retriever

PACKAGE = Path(runner.__file__).resolve().parents[3]

def profile(identifier, *, name="丙将", base=7, maximum=91, growth=2.5,
            constraints=(), notes=(), aliases=(), facts=None):
    return KnowledgeEntry(id=identifier, domain="hero", entry_kind="hero_profile",
        topic=name, aliases=list(aliases), facts=facts or ["合成来源，不代表真实游戏"],
        source_ref="review-source:" + identifier, updated_at=date(2026, 10, 5),
        confidence=0.7, constraints=list(constraints),
        structured_data=HeroStaticProfile(name=name, aliases=list(aliases),
            base_attributes=AttributeSet(military=base, intelligence=base,
                command=base, initiative=base),
            max_attributes=AttributeSet(military=maximum, intelligence=maximum,
                command=maximum, initiative=maximum),
            growth_attributes=AttributeGrowth(military=growth, intelligence=growth,
                command=growth, initiative=growth), notes=list(notes)))

def chunks(entries, score=0.02):
    return [RetrievedChunk(e, score, "independent") for e in entries]

def invoke(question, entries, *, final=None, history=False):
    client = MagicMock()
    client.generate.return_value = LLMResult("合成回答 [review-a]", "offline-fake", 3, 2, 0.1)
    client.generate_json.return_value = ["丁将"]
    retriever = Retriever(entries)
    retriever.retrieve_multi = MagicMock(return_value=chunks(entries))
    if final is not None:
        retriever.retrieve_multi.side_effect = [chunks(entries), chunks(final, 100.0)]
    agent = ChatAgent(retriever, client)
    if history:
        agent.history = [ChatTurn("user", "上次问丁将")]
    reply = agent.ask(question)
    return reply, client

class GateIndependentTests(unittest.TestCase):
    def test_all_twelve_scalar_paths_and_actual_prompt(self):
        item = profile("review-a", base=0)
        for stage, root, value in (("初始", "base_attributes", 0),
                                  ("满级", "max_attributes", 91),
                                  ("成长", "growth_attributes", 2.5)):
            for attr, field in (("武力", "military"), ("智力", "intelligence"),
                                ("统率", "command"), ("先攻", "initiative")):
                with self.subTest(stage=stage, attribute=attr):
                    reply, client = invoke(f"丙将的{stage}{attr}是多少？", [item])
                    self.assertEqual(reply.assessment.status, "supported")
                    self.assertEqual(reply.assessment.fields[0].field_path, f"{root}.{field}")
                    self.assertEqual(reply.assessment.fields[0].value, value)
                    prompt = client.generate.call_args.kwargs["user_message"]
                    self.assertIn(f"[review-a] 丙将 {root}.{field}={value}", prompt)
                    self.assertIn("review-source:review-a", prompt)

    def test_missing_slot_preserves_later_prose_and_does_not_refuse(self):
        item = profile("review-a", base=None, notes=("摘要", "正文记载初始武力为37"))
        reply, client = invoke("丙将初始武力是多少", [item])
        self.assertEqual(reply.assessment.status, "partial")
        self.assertIn("missing_structured_value", reply.assessment.reasons)
        self.assertEqual(client.generate.call_count, 1)
        self.assertIn("正文记载初始武力为37", client.generate.call_args.kwargs["user_message"])

    def test_zero_missing_equal_and_conflicting(self):
        for second, expected in ((None, "partial"), (0, "supported"), (1, "conflicting")):
            reply, client = invoke("丙将初始武力是多少", [profile("review-a", base=0), profile("review-b", base=second)])
            self.assertEqual(reply.assessment.status, expected)
            self.assertEqual(client.generate.call_count, int(expected != "conflicting"))

    def test_three_sources_conflict_complete_and_deterministic(self):
        entries = [profile("review-a", base=0), profile("review-b", base=1), profile("review-c", base=1)]
        reply, client = invoke("丙将初始武力是多少", entries)
        self.assertEqual(reply.assessment.status, "conflicting")
        client.generate.assert_not_called()
        for e in entries:
            self.assertIn(f"[{e.id}]", reply.answer)
            self.assertIn(e.source_ref, reply.answer)
        self.assertEqual(reply.prompt_tokens, 0)

    def test_stages_entities_and_constraints_are_not_false_conflicts(self):
        first = profile("review-a", base=0, maximum=99)
        other = profile("review-b", name="丁将", base=400)
        self.assertEqual(assess_evidence("丙将满级武力是多少", chunks([first, other])).status, "supported")
        scoped = profile("review-c", base=2, constraints=("仅 S3",))
        result = assess_evidence("丙将初始武力是多少", chunks([first, scoped]))
        self.assertEqual(result.check_scope, "unassessed")
        self.assertNotEqual(result.status, "conflicting")

    def test_wrong_entity_and_rewrite_subject_drift_never_supported(self):
        first = profile("review-a")
        other = profile("review-b", name="丁将", base=900)
        for history in (False, True):
            if history:
                reply, client = invoke("丙将初始武力是多少", [first, other], final=[other], history=True)
                self.assertEqual(client.generate_json.call_count, 1)
            else:
                assessment = assess_evidence("丙将初始武力是多少", chunks([other], 10000), catalog=[first, other])
                self.assertIn("entity_not_in_evidence", assessment.reasons)
                continue
            self.assertEqual(reply.assessment.status, "partial")
            self.assertIn("entity_not_in_evidence", reply.assessment.reasons)

    def test_alias_collision_lineup_and_general_text_unassessed(self):
        a = profile("review-a", aliases=("异名",))
        b = profile("review-b", name="丁将", aliases=("异名",))
        self.assertEqual(assess_evidence("异名初始武力是多少", chunks([a, b])).check_scope, "unassessed")
        lineup = KnowledgeEntry(id="review-team", topic="组合", domain="solution", entry_kind="lineup_solution",
            facts=["丙将在队伍中"], source_ref="review-team-source", updated_at=date(2026,10,5), confidence=1,
            structured_data=LineupSolutionProfile(name="组合", hero_names=["丙将"]))
        self.assertEqual(assess_evidence("丙将初始武力是多少", chunks([lineup])).check_scope, "unassessed")
        for question in ("丙将和丁将初始武力是多少", "丙将S1初始武力是多少", "如何配队"):
            self.assertEqual(assess_evidence(question, chunks([a, b])).check_scope, "unassessed")

    def test_empty_no_model_even_with_history(self):
        for history in (False, True):
            reply, client = invoke("不存在的知识", [], history=history)
            self.assertEqual(reply.assessment.status, "not_found")
            client.generate.assert_not_called()
            client.generate_json.assert_not_called()

    def test_original_citation_gate_still_rejects_invented_id(self):
        client = MagicMock()
        client.generate.return_value = LLMResult("事实 [forged-id]", "fake", 0, 0, 0)
        reply = ChatAgent(Retriever([profile("review-a")]), client).ask("丙将初始武力是多少")
        self.assertIn("引用未能", reply.answer)

class EvaluationIndependentTests(unittest.TestCase):
    def transformed_run(self, *, corpus_change=None, freeze_change=None):
        """Synthetic read boundary, updating hash to test schema independently of drift."""
        fixture = PACKAGE / "tests/fixtures/quality_eval/v2"
        corpus = json.loads((fixture / "cases.json").read_text(encoding="utf-8-sig"))
        freeze = json.loads((fixture / "freeze.json").read_text(encoding="utf-8-sig"))
        if corpus_change:
            corpus_change(corpus)
        raw = json.dumps(corpus, ensure_ascii=False)
        freeze["cases_sha256"] = digest(raw)
        if freeze_change:
            freeze_change(freeze)
        frozen_text = json.dumps(freeze, ensure_ascii=False)
        original = Path.read_text
        def replacement(path, *args, **kwargs):
            if path == fixture / "cases.json":
                return raw
            if path == fixture / "freeze.json":
                return frozen_text
            return original(path, *args, **kwargs)
        with patch.object(Path, "read_text", replacement):
            return runner.run(PACKAGE, baseline="v2")

    def test_real_v2_and_expected_v1_drift(self):
        result = runner.run(PACKAGE, baseline="v2")
        self.assertEqual(result["retrieval"]["query_count"], 12)
        self.assertEqual(result["provider"]["calls"], 0)
        self.assertEqual(len(result["assessment_cases"]), 6)
        with self.assertRaisesRegex(ValueError, "source drift"):
            runner.run(PACKAGE)

    def test_algorithm_and_evidence_source_mismatch_rejected(self):
        with self.assertRaises(ValueError):
            self.transformed_run(freeze_change=lambda f: f["production"].update(algorithm="unsafe-algorithm"))
        with self.assertRaisesRegex(ValueError, "source mismatch"):
            self.transformed_run(corpus_change=lambda c: c["queries"][0]["evidence_labels"][0].update(source_ref="wrong-source"))

    def test_duplicate_and_wrong_split_rejected(self):
        with self.assertRaises(ValueError):
            self.transformed_run(corpus_change=lambda c: c["queries"].append(copy.deepcopy(c["queries"][0])))
        with self.assertRaises(ValueError):
            self.transformed_run(corpus_change=lambda c: c["queries"][0].update(split="holdout"))

    def test_nonpositive_or_boolean_top_k_rejected(self):
        for value in (0, -1, True):
            with self.subTest(top_k=value), self.assertRaises(ValueError):
                self.transformed_run(corpus_change=lambda c: c.update(top_k=value))

    def test_missing_required_assessment_cases_rejected(self):
        with self.assertRaises(ValueError):
            self.transformed_run(corpus_change=lambda c: c.pop("assessment_cases"))

    def test_noninteger_version_rejected(self):
        with self.assertRaises(ValueError):
            self.transformed_run(corpus_change=lambda c: c.update(version=2.0))
