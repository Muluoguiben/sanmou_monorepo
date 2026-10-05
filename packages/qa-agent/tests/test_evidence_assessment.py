from datetime import date
import unittest
from unittest.mock import MagicMock

from qa_agent.chat.agent import ChatAgent, ChatTurn
from qa_agent.chat.llm_client import LLMResult
from qa_agent.chat.evidence_assessment import assess_evidence
from qa_agent.knowledge.models import KnowledgeEntry, HeroStaticProfile, AttributeSet, AttributeGrowth, LineupSolutionProfile
from qa_agent.retrieval.retriever import RetrievedChunk, Retriever


def hero(identifier='hero-a', value=0, **kw):
    return KnowledgeEntry(id=identifier, domain='hero', entry_kind='hero_profile',
        topic='甲将', facts=['初始武力为0'], source_ref=identifier+'-source',
        updated_at=date(2026, 10, 5), confidence=.9,
        structured_data=HeroStaticProfile(name='甲将', aliases=['甲公'],
            base_attributes=AttributeSet(military=value),
            max_attributes=AttributeSet(military=100)), **kw)


def chunks(*entries):
    return [RetrievedChunk(e, 1., 'synthetic') for e in entries]


class EvidenceAssessmentTests(unittest.TestCase):
    def test_zero_conflict_stops_real_agent(self):
        client=MagicMock()
        reply=ChatAgent(Retriever([hero(), hero('hero-b',1)]),client).ask('甲将初始武力是多少？')
        self.assertEqual(reply.assessment.status,'conflicting')
        client.generate.assert_not_called()
        self.assertIn('[hero-a]',reply.answer)
        self.assertIn('[hero-b]',reply.answer)

    def test_zero_equal_and_none_are_distinct(self):
        self.assertEqual(assess_evidence('甲将初始武力是多少',chunks(hero(),hero('hero-b',0))).status,'supported')
        result=assess_evidence('甲将初始武力是多少',chunks(hero(),hero('hero-b',None)))
        self.assertEqual(result.status,'partial')
        self.assertIn('missing_structured_value',result.reasons)

    def test_missing_keeps_body_generation_and_prompt_has_checked_value(self):
        for value in (None,0):
            client=MagicMock()
            client.generate.return_value=LLMResult('初始武力0 [hero-a]','fake',1,1,.1)
            reply=ChatAgent(Retriever([hero(value=value)]),client).ask('甲公初始武力是多少？')
            self.assertEqual(client.generate.call_count,1)
            prompt=client.generate.call_args.kwargs['user_message']
            self.assertIn('初始武力为0',prompt)
            if value is not None:
                self.assertIn('base_attributes.military=0',prompt)
                self.assertEqual(reply.assessment.status,'supported')

    def test_complex_scope_and_free_text_unassessed(self):
        for question in ('甲将怎么样','甲将S1初始武力是多少','甲将和乙将初始武力是多少'):
            result=assess_evidence(question,chunks(hero(),hero('hero-b',1)))
            self.assertEqual(result.check_scope,'unassessed')
            self.assertEqual(result.decision,'generate')

    def test_constraints_are_not_assumed_comparable(self):
        result=assess_evidence('甲将初始武力是多少',chunks(hero(),hero('hero-b',1,constraints=['S1'])))
        self.assertNotEqual(result.status,'conflicting')
        self.assertIn('unassessed_applicability',result.reasons)

    def test_empty(self):
        self.assertEqual(assess_evidence('什么',[]).status,'not_found')

    def test_wrong_entity_is_not_supported(self):
        other=hero().model_copy(update={'topic':'乙将','structured_data':HeroStaticProfile(name='乙将',base_attributes=AttributeSet(military=1))})
        result=assess_evidence('甲将初始武力是多少',chunks(other),catalog=[hero(),other])
        self.assertEqual(result.check_scope,'unassessed')
        self.assertIn('entity_not_in_evidence',result.reasons)

    def test_lineup_member_is_not_identity(self):
        item=KnowledgeEntry(id='lineup-a',domain='solution',entry_kind='lineup_solution',
            topic='测试阵容',facts=['甲将参与'],source_ref='synthetic',updated_at=date(2026,10,5),confidence=1,
            structured_data=LineupSolutionProfile(name='测试阵容',hero_names=['甲将']))
        result=assess_evidence('甲将初始武力是多少',chunks(item))
        self.assertEqual(result.check_scope,'unassessed')

    def test_other_entity_and_other_stage_do_not_conflict(self):
        other=hero('hero-b',1)
        other.structured_data.name='乙将'
        for question in ('甲将初始武力是多少','甲将满级武力是多少'):
            self.assertEqual(assess_evidence(question,chunks(hero(),other)).status,'supported')

    def test_final_retrieval_not_initial_is_assessed(self):
        retriever=Retriever([hero(),hero('hero-b',1)])
        retriever.retrieve_multi=MagicMock(side_effect=[chunks(hero()),chunks(*retriever.entries)])
        client=MagicMock()
        client.generate_json.return_value=['甲将']
        agent=ChatAgent(retriever,client)
        agent.history=[ChatTurn('user','先前问题')]
        reply=agent.ask('甲将初始武力是多少')
        self.assertEqual(reply.assessment.status,'conflicting')
        client.generate.assert_not_called()
        self.assertEqual(client.generate_json.call_count,1)

    def test_unassessed_relevance_does_not_block_generation(self):
        client=MagicMock()
        client.generate.return_value=LLMResult('已有事实 [hero-a]','fake',0,0,0)
        retriever=Retriever([hero()])
        retriever.retrieve_multi=MagicMock(return_value=[RetrievedChunk(hero(),.01,'weak')])
        reply=ChatAgent(retriever,client).ask('怎么搭配')
        self.assertEqual(reply.assessment.check_scope,'unassessed')
        client.generate.assert_called_once()

    def test_all_notes_preserved_when_slot_missing(self):
        item=hero(value=None)
        item.structured_data.notes=['背景','初始武力为0']
        prompt=ChatAgent._compose_user_message('甲将初始武力是多少',chunks(item))
        self.assertIn('[hero-a] notes: 初始武力为0',prompt)

    def test_growth_and_all_four_dimensions(self):
        item=hero()
        item.structured_data.growth_attributes=AttributeGrowth(military=0,intelligence=1.2,command=2,initiative=3)
        for name,value in (('武力',0),('智力',1.2),('统率',2),('先攻',3)):
            result=assess_evidence(f'甲将成长{name}是多少',chunks(item))
            self.assertEqual(result.status,'supported')
            self.assertEqual(result.fields[0].value,value)

    def test_all_disagreeing_sources_disclosed_without_rank_selection(self):
        result=assess_evidence('甲将初始武力是多少',chunks(hero(),hero('hero-b',1),hero('hero-c',1)))
        for identifier in ('hero-a','hero-b','hero-c'):
            self.assertIn(f'[{identifier}]',result.conflict_answer())
            self.assertIn(identifier+'-source',result.conflict_answer())

    def test_history_rewrite_cannot_change_assessed_subject(self):
        original=hero()
        other=hero('hero-b',1)
        other.structured_data.name='乙将'
        other.topic='乙将'
        retriever=Retriever([original,other])
        retriever.retrieve_multi=MagicMock(side_effect=[chunks(original),chunks(other)])
        client=MagicMock()
        client.generate_json.return_value=['乙将']
        client.generate.return_value=LLMResult('证据不适用 [hero-b]','fake',0,0,0)
        agent=ChatAgent(retriever,client)
        agent.history=[ChatTurn('user','先前乙将')]
        result=agent.ask('甲将初始武力是多少')
        self.assertIn('entity_not_in_evidence',result.assessment.reasons)
        self.assertNotEqual(result.assessment.status,'supported')

    def test_ambiguous_alias_never_selects_one_entity(self):
        a=hero()
        b=hero('hero-b',1)
        b.structured_data.name='乙将'
        result=assess_evidence('甲公初始武力是多少',chunks(a,b))
        self.assertEqual(result.check_scope,'unassessed')
