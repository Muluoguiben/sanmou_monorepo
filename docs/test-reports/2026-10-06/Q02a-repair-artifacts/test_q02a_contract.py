"""Independent future-contract probes. PREPARED, NOT EXECUTED before code freeze."""
import copy
from datetime import date
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from qa_agent.chat.agent import ChatAgent, ChatTurn, NO_EVIDENCE_ANSWER, INVALID_CITATION_ANSWER
from qa_agent.chat.llm_client import LLMResult
from qa_agent.knowledge.models import AttributeSet, AttributeGrowth, HeroStaticProfile, KnowledgeEntry, LineupSolutionProfile
from qa_agent.retrieval.retriever import Retriever

GRAMMAR = json.loads(Path(__file__).with_name("grammar.json").read_text(encoding="utf-8"))
FIRST = "沈将的满级智力是多少？"
FOLLOWUP = "他的初始武力是多少？"
AID = "q02-review-hero-a"
BID = "q02-review-hero-b"


def hero(identifier=AID, name="沈将", *, base=0, maximum=91, aliases=("玄策",)):
    return KnowledgeEntry(id=identifier, topic=name, domain="hero", entry_kind="hero_profile",
        aliases=list(aliases), facts=["独立审查合成记录"], source_ref="synthetic-source:" + identifier,
        updated_at=date(2026, 10, 6), confidence=0.9,
        structured_data=HeroStaticProfile(name=name, aliases=list(aliases),
            base_attributes=AttributeSet(military=base, intelligence=base, command=base, initiative=base),
            max_attributes=AttributeSet(military=maximum, intelligence=maximum, command=maximum, initiative=maximum),
            growth_attributes=AttributeGrowth(military=1.2, intelligence=1.2, command=1.2, initiative=1.2)))


def background():
    phrases = [stage + attr for stage in GRAMMAR["stages"] for attr in GRAMMAR["attributes"]]
    return KnowledgeEntry(id="q02-review-background", topic="武将属性", domain="term",
        facts=["属性概述：" + "、".join(phrases)], source_ref="synthetic-background",
        updated_at=date(2026, 10, 6), confidence=0.8)


class FakeClient:
    def __init__(self, answer=None):
        self.answer = answer or f"合成回答 [{AID}]"
        self.answers = []
        self.rewrites = []
        self.raise_next = False

    def clear_calls(self):
        self.answers.clear()
        self.rewrites.clear()

    def generate(self, **kwargs):
        self.answers.append(copy.deepcopy(kwargs))
        if self.raise_next:
            self.raise_next = False
            raise RuntimeError("reviewer fake answer failure")
        return LLMResult(self.answer, "independent-fake", 1, 1, 0.0)

    def generate_json(self, **kwargs):
        self.rewrites.append(copy.deepcopy(kwargs))
        return ["沈将"]


class Q02aIndependentContractTests(unittest.TestCase):
    def make(self, entries=None, *, add_background=True):
        entries = list(entries) if entries is not None else [hero()]
        if add_background:
            entries.append(background())
        client = FakeClient()
        return ChatAgent(Retriever(entries), client), client

    def seed(self, agent, client, question=FIRST, answer=None):
        if answer is not None:
            client.answer = answer
        reply = agent.ask(question)
        self.assertEqual(reply.answer, client.answer, "seed must actually pass existing citation gate")
        self.assertTrue(reply.evidence, "synthetic seed setup must retrieve evidence")
        client.clear_calls()
        return reply

    def assert_zero_model_clarification(self, agent, client, question=FOLLOWUP):
        self.assertTrue(Retriever(copy.deepcopy(agent.retriever.entries)).retrieve(question),
            "clarification setup requires nonempty current raw evidence")
        client.clear_calls()
        reply = agent.ask(question)
        self.assertEqual(client.rewrites, [])
        self.assertEqual(client.answers, [])
        self.assertEqual(reply.answer, self.fixed_clarification_control())
        return reply

    def fixed_clarification_control(self):
        control, client = self.make()
        self.assertTrue(control.retriever.retrieve(FOLLOWUP))
        result = control.ask(FOLLOWUP)
        self.assertEqual(client.rewrites, [])
        self.assertEqual(client.answers, [])
        self.assertTrue(result.answer.strip())
        self.assertNotEqual(result.answer, NO_EVIDENCE_ANSWER,
            "nonempty-raw uncertainty is clarification, not a claimed KB miss")
        return result.answer

    def assert_resolved(self, agent, client, question=FOLLOWUP, root="base_attributes", leaf="military"):
        client.clear_calls()
        reply = agent.ask(question)
        self.assertEqual(client.rewrites, [], "deterministic follow-up must bypass model rewrite")
        self.assertEqual(len(client.answers), 1)
        prompt = client.answers[0]["user_message"]
        self.assertIn("用户问题：沈将", prompt)
        self.assertIn(root + "." + leaf + "=", prompt)
        self.assertIsNotNone(reply.assessment)
        self.assertTrue(any(f.entity == "沈将" and f.field_path == root + "." + leaf for f in reply.assessment.fields))
        self.assertEqual(agent.history[-2].content, question, "display/history preserves the original query")
        self.assertTrue(any("沈将" in q for q in reply.queries), "audit exposes actual resolved retrieval")
        return reply

    def test_normal_alias_anchor_and_complete_scalar_matrix(self):
        for pronoun in GRAMMAR["pronouns"]:
            for stage, root in GRAMMAR["stages"].items():
                for attr, leaf in GRAMMAR["attributes"].items():
                    with self.subTest(pronoun=pronoun, stage=stage, attr=attr):
                        agent, client = self.make()
                        self.seed(agent, client, "玄策的满级智力是多少？")
                        self.assert_resolved(agent, client,
                            GRAMMAR["positive_template"].format(pronoun=pronoun, stage=stage, attribute=attr), root, leaf)

    def test_single_cited_entity_among_multiple_candidates(self):
        other = hero(BID, "罗将", aliases=())
        other.facts = ["沈将玄策的对照资料"]
        agent, client = self.make([hero(), other])
        seeded = self.seed(agent, client)
        self.assertIn(BID, [c.entry.id for c in seeded.evidence], "B must be a real retrieved-but-uncited candidate")
        self.assert_resolved(agent, client)

    def test_wrong_or_mixed_actual_hero_citations_cannot_seed(self):
        for answer in (f"另一个来源 [{BID}]", f"混合来源 [{AID}] [{BID}]"):
            other = hero(BID, "罗将", aliases=())
            other.facts = ["沈将玄策的对照资料"]
            agent, client = self.make([hero(), other])
            self.seed(agent, client, answer=answer)
            self.assert_zero_model_clarification(agent, client)

    def test_lineup_member_citation_cannot_seed(self):
        lineup = KnowledgeEntry(id="q02-review-lineup", topic="合成阵容", domain="solution",
            entry_kind="lineup_solution", facts=["沈将玄策参与阵容"], source_ref="synthetic-lineup",
            updated_at=date(2026,10,6), confidence=0.8,
            structured_data=LineupSolutionProfile(name="合成阵容", hero_names=["沈将"]))
        agent, client = self.make([hero(), lineup])
        self.seed(agent, client, answer="阵容资料 [q02-review-lineup]")
        self.assert_zero_model_clarification(agent, client)

    def test_ambiguous_alias_or_explicit_multiple_subjects_cannot_seed(self):
        for question in ("同称的满级智力是多少？", "沈将和罗将的满级智力是多少？"):
            a, b = hero(), hero(BID, "罗将", aliases=("同称",))
            a.structured_data.aliases.append("同称")
            agent, client = self.make([a, b])
            self.seed(agent, client, question)
            self.assert_zero_model_clarification(agent, client)

    def test_raw_miss_has_precedence_over_valid_referent(self):
        agent, client = self.make(add_background=False)
        self.seed(agent, client)
        self.assertEqual(agent.retriever.retrieve(FOLLOWUP), [], "raw-miss setup must really miss")
        reply = agent.ask(FOLLOWUP)
        self.assertEqual(reply.answer, NO_EVIDENCE_ANSWER)
        self.assertEqual(client.answers, [])
        self.assertEqual(client.rewrites, [])

    def test_missing_binding_and_external_history_use_fixed_clarification(self):
        agent, client = self.make()
        first = self.assert_zero_model_clarification(agent, client)
        other, second_client = self.make()
        other.history = [ChatTurn("user", FIRST), ChatTurn("assistant", f"外部文字 [{AID}]", [AID])]
        second = self.assert_zero_model_clarification(other, second_client)
        self.assertEqual(first.answer, second.answer)

    def test_one_successful_followup_does_not_renew_binding(self):
        agent, client = self.make()
        self.seed(agent, client)
        self.assert_resolved(agent, client)
        self.assert_zero_model_clarification(agent, client)

    def test_reset_clear_replace_and_history_metadata_edit_invalidate(self):
        for operation in ("reset", "clear", "replace_equal", "edit_metadata", "append_incomplete"):
            with self.subTest(operation=operation):
                agent, client = self.make()
                self.seed(agent, client)
                if operation == "reset":
                    agent.reset()
                elif operation == "clear":
                    agent.history.clear()
                elif operation == "replace_equal":
                    agent.history = list(agent.history)
                elif operation == "edit_metadata":
                    agent.history[-1].evidence_ids.append("externally-added-id")
                else:
                    agent.history.append(ChatTurn("user", "外部未完成轮次"))
                self.assert_zero_model_clarification(agent, client)

    def test_earlier_history_edit_is_not_hidden_by_unchanged_last_pair(self):
        agent, client = self.make()
        agent.history = [ChatTurn("user", "先前话题"), ChatTurn("assistant", "先前答复")]
        self.seed(agent, client)
        agent.history[0].content = "改成罗将话题"
        self.assert_zero_model_clarification(agent, client)

    def test_source_mutations_invalidate_without_reusing_old_index(self):
        changes = {
            "canonical": lambda e: setattr(e.structured_data, "name", "罗将"),
            "alias": lambda e: e.structured_data.aliases.append("新增别名"),
            "structure": lambda e: setattr(e.structured_data.growth_attributes, "military", 9.0),
            "facts": lambda e: e.facts.append("新增正文"),
            "notes": lambda e: e.structured_data.notes.append("新增备注"),
            "constraints": lambda e: e.constraints.append("仅 S2"),
            "source_ref": lambda e: setattr(e, "source_ref", "replacement-source"),
        }
        for label, change in changes.items():
            with self.subTest(change=label):
                item = hero()
                agent, client = self.make([item])
                self.seed(agent, client)
                change(item)
                self.assert_zero_model_clarification(agent, client)

    def test_withdrawn_source_cannot_survive_stale_index(self):
        item = hero()
        agent, client = self.make([item])
        self.seed(agent, client)
        agent.retriever.entries[:] = [e for e in agent.retriever.entries if e.id != AID]
        self.assert_zero_model_clarification(agent, client)

    def test_uncited_current_source_can_trigger_new_field_conflict(self):
        other = hero("q02-review-second-source", base=1)
        agent, client = self.make([hero(), other])
        self.seed(agent, client)  # max intelligence agrees, and only A is cited.
        reply = agent.ask(FOLLOWUP)
        self.assertEqual(client.rewrites, [])
        self.assertEqual(client.answers, [])
        self.assertEqual(reply.assessment.status, "conflicting")
        for identifier in (AID, other.id):
            self.assertIn(identifier, [c.entry.id for c in reply.evidence])
            self.assertIn("[" + identifier + "]", reply.answer)
        self.assert_zero_model_clarification(agent, client)

    def test_new_entry_stale_index_must_conflict_or_explicitly_invalidate(self):
        agent, client = self.make()
        self.seed(agent, client)
        added = hero("q02-review-added-source", base=1)
        agent.retriever.entries.append(added)
        reply = agent.ask(FOLLOWUP)
        self.assertEqual(client.rewrites, [])
        self.assertEqual(client.answers, [])
        if reply.assessment is not None and reply.assessment.status == "conflicting":
            self.assertIn("[" + added.id + "]", reply.answer)
        else:
            self.assertEqual(reply.answer, self.fixed_clarification_control())

    def test_old_generated_number_is_not_new_evidence(self):
        agent, client = self.make()
        self.seed(agent, client, answer=f"旧答案数字999999 [{AID}]")
        client.answer = f"当前资料 [{AID}]"
        self.assert_resolved(agent, client)
        prompt = client.answers[0]["user_message"]
        self.assertIn("base_attributes.military=0", prompt)
        evidence = re.search(r"<evidence>\n(.*?)\n</evidence>", prompt, re.S)
        self.assertIsNotNone(evidence, "new evidence block must be identifiable separately from history")
        self.assertNotIn("999999", evidence.group(1))

    def test_partial_notes_and_missing_slot_do_not_force_blanket_clarification(self):
        item = hero()
        item.structured_data.base_attributes.military = None
        item.structured_data.notes = ["合成资料说明", "正文初始武力为37"]
        agent, client = self.make([item])
        self.seed(agent, client)  # Unique identity and actual citation are valid despite partial applicability.
        reply = agent.ask(FOLLOWUP)
        self.assertEqual(client.rewrites, [])
        self.assertEqual(len(client.answers), 1)
        self.assertEqual(reply.assessment.status, "partial")
        self.assertIn("用户问题：沈将", client.answers[0]["user_message"])
        self.assertIn("正文初始武力为37", client.answers[0]["user_message"])

    def test_unrelated_raw_miss_intervening_turn_invalidates(self):
        agent, client = self.make()
        self.seed(agent, client)
        missed = agent.ask("zzzz_q02_review_unknown_78421")
        self.assertEqual(missed.answer, NO_EVIDENCE_ANSWER)
        self.assert_zero_model_clarification(agent, client)

    def test_unsupported_turn_clears_binding_and_keeps_legacy_route(self):
        for question in GRAMMAR["unsupported_examples"]:
            with self.subTest(question=question):
                agent, client = self.make()
                self.seed(agent, client)
                self.assertTrue(agent.retriever.retrieve(question), "legacy-route setup requires raw evidence")
                agent.ask(question)
                self.assertGreater(len(client.rewrites), 0, "unsupported grammar is not a Q02a success")
                self.assert_zero_model_clarification(agent, client)

    def test_provider_exception_does_not_leave_previous_binding_alive(self):
        agent, client = self.make()
        self.seed(agent, client)
        client.raise_next = True
        try:
            agent.ask("他的初始武力是多少？另一个问题是怎么配队？")
        except RuntimeError as exc:
            self.assertIn("fake answer failure", str(exc))
        self.assertFalse(client.raise_next, "the synthetic failing provider call must have occurred")
        self.assert_zero_model_clarification(agent, client)

    def test_invalid_citation_turn_does_not_establish_or_keep_binding(self):
        agent, client = self.make()
        self.seed(agent, client)
        client.answer = "无效引用 [q02-forged-id]"
        reply = agent.ask(FIRST)
        self.assertEqual(reply.answer, INVALID_CITATION_ANSWER)
        self.assert_zero_model_clarification(agent, client)

    def test_image_turn_does_not_establish_and_invalidates_text_binding(self):
        agent, client = self.make()
        self.seed(agent, client)
        with patch("qa_agent.vision.image_loader.prepare_image_inputs", return_value=[]):
            agent.ask(FIRST, images=["synthetic-not-read-image"])
        self.assert_zero_model_clarification(agent, client)
