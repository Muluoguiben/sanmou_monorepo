"""Additional finite-scope controls; original eb895ae probes remain untouched."""
import unittest

import test_q02a_contract as contract
from qa_agent.knowledge.models import KnowledgeEntry, HeroStaticProfile, LineupSolutionProfile


class Q02aRepairScopeTests(unittest.TestCase):
    def setUp(self):
        self.h = contract.Q02aIndependentContractTests()

    def test_bare_alias_punctuation_outer_space_and_regex_literal(self):
        for question, alias in (("沈将", "玄策"), ("沈将？", "玄策"), (" 玄策。 ", "玄策"),
                ("玄(策)+", "玄(策)+"), ("玄 策的初始武力是多少？", "玄 策")):
            with self.subTest(question=question):
                item = contract.hero(aliases=(alias,))
                agent, client = self.h.make([item])
                self.h.seed(agent, client, question)
                self.h.assert_resolved(agent, client)

    def test_prefix_overlap_does_not_make_exact_full_name_ambiguous(self):
        a = contract.hero()
        b = contract.hero(contract.BID, "沈", aliases=())
        agent, client = self.h.make([a, b])
        self.h.seed(agent, client, "沈将")
        self.h.assert_resolved(agent, client)

    def test_extra_syntax_space_and_other_clauses_do_not_seed(self):
        for question in ("沈将 的初始武力是多少？", "沈将初始 武力是多少？", "沈将？？", "请介绍沈将"):
            with self.subTest(question=question):
                agent, client = self.h.make()
                self.h.seed(agent, client, question)
                self.h.assert_zero_model_clarification(agent, client)

    def test_validated_hero_domain_generic_kind_still_cannot_seed(self):
        payload = contract.hero().model_dump()
        payload.update(domain="hero", entry_kind="generic_rule")
        item = KnowledgeEntry.model_validate(payload)
        self.assertIsInstance(item.structured_data, HeroStaticProfile)
        agent, client = self.h.make([item])
        self.h.seed(agent, client)
        self.h.assert_zero_model_clarification(agent, client)

    def test_unique_eligible_hero_with_generic_background_citation_can_seed(self):
        agent, client = self.h.make()
        self.h.seed(agent, client, answer=f"合成资料 [{contract.AID}] [q02-review-background]")
        self.h.assert_resolved(agent, client)

    def test_unique_eligible_hero_with_lineup_background_citation_can_seed(self):
        data = contract.background().model_dump()
        data.update(id="q02-background-lineup", domain="solution", entry_kind="lineup_solution",
            topic="合成阵容", facts=["沈将与玄策的阵容背景"],
            structured_data=LineupSolutionProfile(name="合成阵容", hero_names=["沈将", "罗将"]))
        lineup = KnowledgeEntry.model_validate(data)
        agent, client = self.h.make([contract.hero(), lineup])
        self.h.seed(agent, client, answer=f"合成资料 [{contract.AID}] [q02-background-lineup]")
        self.h.assert_resolved(agent, client)

    def test_later_shared_old_alias_does_not_redirect_accepted_canonical(self):
        a = contract.hero()
        b = contract.hero(contract.BID, "罗将", aliases=())
        agent, client = self.h.make([a, b])
        self.h.seed(agent, client, "玄策")
        b.structured_data.aliases.append("玄策")
        reply = self.h.assert_resolved(agent, client)
        self.assertTrue(reply.resolved_question.startswith("沈将"))
        self.assertTrue(all(c.entry.structured_data.name == "沈将" for c in reply.evidence))

    def test_current_canonical_ambiguity_clarifies_instead_of_redirecting(self):
        a = contract.hero()
        b = contract.hero(contract.BID, "罗将", aliases=())
        agent, client = self.h.make([a, b])
        self.h.seed(agent, client, "玄策")
        b.structured_data.aliases.append("沈将")
        self.h.assert_zero_model_clarification(agent, client)
