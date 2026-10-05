from datetime import date
import unittest
from unittest.mock import MagicMock, patch
from copy import deepcopy

from qa_agent.chat.agent import ChatAgent, ChatTurn
from qa_agent.chat.llm_client import LLMResult
from qa_agent.knowledge.models import KnowledgeEntry, HeroStaticProfile, AttributeSet
from qa_agent.retrieval.retriever import Retriever, RetrievedChunk
from qa_agent.chat.referent_resolution import CLARIFY_REFERENT_ANSWER, followup_suffix


def hero(identifier='hero-a', name='甲将', value=0, notes=None):
    return KnowledgeEntry(id=identifier, topic=name, domain='hero', entry_kind='hero_profile',
        facts=['合成武将记录'], source_ref='synthetic:'+identifier,updated_at=date(2026,10,6),confidence=.9,
        structured_data=HeroStaticProfile(name=name,aliases=['甲公'] if name=='甲将' else [],
            base_attributes=AttributeSet(military=value), max_attributes=AttributeSet(intelligence=90),notes=notes or []))


def background():
    return KnowledgeEntry(id='mechanic-a',topic='属性机制',domain='team',facts=['初始武力、满级智力与成长统率为武将属性。'],
        source_ref='synthetic:mechanic',updated_at=date(2026,10,6),confidence=.9)


def agent_with(entries=None):
    client=MagicMock()
    client.generate.return_value=LLMResult('事实 [hero-a]','fake',1,1,.1)
    client.generate_json.return_value=['甲将']
    return ChatAgent(Retriever(entries if entries is not None else [hero(),background()]),client),client


class ReferentResolutionTests(unittest.TestCase):
    def test_adjacent_alias_followup_uses_resolved_prompt_without_rewrite(self):
        agent,client=agent_with()
        agent.ask('甲公初始武力是多少？')
        client.reset_mock()
        reply=agent.ask('他的满级智力是多少？')
        client.generate_json.assert_not_called()
        client.generate.assert_called_once()
        self.assertEqual(reply.resolved_question,'甲将满级智力是多少')
        self.assertEqual(reply.assessment.status,'supported')
        self.assertIn('用户问题：甲将满级智力是多少',client.generate.call_args.kwargs['user_message'])
        self.assertEqual(agent.history[-2].content,'他的满级智力是多少？')

    def test_missing_binding_is_terminal_clarification(self):
        agent,client=agent_with()
        reply=agent.ask('他初始武力多少')
        self.assertIn('明确',reply.answer)
        client.generate.assert_not_called()
        client.generate_json.assert_not_called()

    def assert_clarifies(self,agent,client):
        client.reset_mock()
        result=agent.ask('他的初始武力是多少？')
        self.assertEqual(result.answer,CLARIFY_REFERENT_ANSWER)
        self.assertEqual(result.evidence,[])
        client.generate.assert_not_called()
        client.generate_json.assert_not_called()
        return result

    def test_binding_is_one_use_not_renewed_by_success(self):
        agent,client=agent_with()
        agent.ask('甲将初始武力是多少')
        self.assertEqual(agent.ask('他初始武力多少').referent_resolution,'resolved')
        self.assert_clarifies(agent,client)

    def test_notes_partial_can_establish_binding(self):
        agent,client=agent_with([hero(notes=['背景说明']),background()])
        self.assertEqual(agent.ask('甲将初始武力是多少').assessment.status,'partial')
        client.reset_mock()
        self.assertEqual(agent.ask('他初始武力多少').referent_resolution,'resolved')
        client.generate_json.assert_not_called()

    def test_actual_citations_not_all_candidates_define_subject(self):
        for answer,valid in [('甲 [hero-a]',True),('乙 [hero-b]',False),('两者 [hero-a] [hero-b]',False),
                ('无引用',False),('伪造 [absent-id]',False),('机制 [mechanic-a]',False)]:
            with self.subTest(answer=answer):
                agent,client=agent_with([hero(),hero('hero-b','乙将',1),background()])
                agent.retriever.retrieve_multi=MagicMock(return_value=[
                    RetrievedChunk(e,1.,'first') for e in agent.retriever.entries])
                client.generate.return_value=LLMResult(answer,'fake',0,0,0)
                agent.ask('甲将初始武力是多少')
                client.reset_mock()
                if valid:
                    self.assertEqual(agent.ask('他初始武力多少').referent_resolution,'resolved')
                else:
                    self.assert_clarifies(agent,client)

    def test_ambiguous_alias_and_multihero_question_do_not_bind(self):
        for question,collision in [('甲公初始武力多少',True),('甲将和乙将的属性',False)]:
            b=hero('hero-b','乙将')
            if collision:
                b.structured_data.aliases=['甲公']
            agent,client=agent_with([hero(),b,background()])
            agent.ask(question)
            self.assert_clarifies(agent,client)

    def test_history_identity_full_content_and_order_are_bound(self):
        for mutation in ('replace','edit_old','ids','reorder','append','clear','reset'):
            with self.subTest(mutation=mutation):
                agent,client=agent_with()
                agent.history=[ChatTurn('user','旧问题'),ChatTurn('assistant','旧内容')]
                agent.ask('甲将初始武力多少')
                if mutation=='replace': agent.history=deepcopy(agent.history)
                elif mutation=='edit_old': agent.history[0].content='修改早期内容'
                elif mutation=='ids': agent.history[-1].evidence_ids.append('new')
                elif mutation=='reorder': agent.history[:2]=reversed(agent.history[:2])
                elif mutation=='append': agent.history.append(ChatTurn('user','插入'))
                elif mutation=='clear': agent.history.clear()
                else: agent.reset()
                self.assert_clarifies(agent,client)

    def test_external_history_cannot_create_binding(self):
        agent,client=agent_with()
        agent.history=[ChatTurn('user','甲将初始武力多少'),ChatTurn('assistant','事实 [hero-a]',['hero-a'])]
        self.assert_clarifies(agent,client)

    def test_full_source_fingerprint_withdrawal_and_stale_index(self):
        for mutation in ('notes','source','priority','withdraw','identity'):
            agent,client=agent_with()
            agent.ask('甲将初始武力多少')
            item=agent.retriever.entries[0]
            if mutation=='notes': item.structured_data.notes.append('新增未展示尾部')
            elif mutation=='source': item.source_ref='new-source'
            elif mutation=='priority': item.priority=42
            elif mutation=='identity': item.structured_data.name='乙将'
            else: agent.retriever.entries.pop(0)
            self.assert_clarifies(agent,client)

    def test_new_source_retrieved_from_rebuilt_catalog_reaches_conflict_gate(self):
        agent,client=agent_with()
        agent.ask('甲将初始武力多少')
        agent.retriever.entries.append(hero('hero-b','甲将',1))
        client.reset_mock()
        reply=agent.ask('他初始武力多少')
        self.assertEqual(reply.assessment.status,'conflicting')
        self.assertIn('[hero-b]',reply.answer)
        client.generate.assert_not_called()
        client.generate_json.assert_not_called()
        self.assert_clarifies(agent,client)

    def test_empty_current_catalog_does_not_use_old_index_or_binding(self):
        agent,client=agent_with()
        agent.ask('甲将初始武力多少')
        agent.retriever.entries.clear()
        client.reset_mock()
        reply=agent.ask('他初始武力多少')
        self.assertEqual(reply.answer,'知识库暂未收录此问题。')
        client.generate.assert_not_called()
        client.generate_json.assert_not_called()

    def test_raw_miss_cannot_be_recovered_from_binding(self):
        agent,client=agent_with([hero()])
        agent.ask('甲将')
        client.reset_mock()
        reply=agent.ask('他的满级智力是多少？')
        self.assertEqual(reply.answer,'知识库暂未收录此问题。')
        self.assertEqual(reply.referent_resolution,'raw_not_found')
        client.generate.assert_not_called()
        client.generate_json.assert_not_called()

    def test_intermediate_unsupported_or_exception_turn_clears_binding(self):
        for exception in (False,True):
            agent,client=agent_with()
            agent.ask('甲将初始武力多少')
            if exception:
                with patch.object(agent.retriever,'retrieve_multi',side_effect=RuntimeError('synthetic')):
                    with self.assertRaises(RuntimeError): agent.ask('其他问题')
            else: agent.ask('无关未知xyz')
            self.assert_clarifies(agent,client)

    def test_images_argument_clears_and_does_not_establish_text_binding(self):
        agent,client=agent_with()
        agent.ask('甲将初始武力多少')
        agent.ask('甲将初始武力多少',images=[])
        self.assert_clarifies(agent,client)

    def test_snapshot_is_shared_across_raw_resolved_and_assessment(self):
        agent,client=agent_with()
        agent.ask('甲将初始武力多少')
        original=Retriever.retrieve_multi
        observed=[]
        def mutate_external(view,*args,**kwargs):
            observed.append(view)
            if len(observed)==1:
                agent.retriever.entries.clear()
            return original(view,*args,**kwargs)
        with patch.object(Retriever,'retrieve_multi',mutate_external):
            result=agent.ask('他初始武力多少')
        self.assertEqual(result.referent_resolution,'resolved')
        self.assertIs(observed[0],observed[1])
        self.assertIsNot(observed[0],agent.retriever)
        self.assertEqual(result.assessment.status,'supported')

    def test_whitelist_grammar_is_complete_and_bounded(self):
        for text in ('他的初始武力是多少？','该武将基础统率多少',' 他成长先攻多少。 '):
            self.assertIsNotNone(followup_suffix(text))
        for text in ('他们初始武力多少','他初始武力多少以及满级智力','他S1初始武力多少',
                '他的 初始武力多少','再详细说说他','他初始武力多少??'):
            self.assertIsNone(followup_suffix(text))

    def test_resolved_miss_or_wrong_subject_is_terminal_no_model(self):
        for result in ([],[RetrievedChunk(hero('hero-b','乙将'),1.,'wrong')]):
            agent,client=agent_with()
            agent.ask('甲将初始武力多少')
            client.reset_mock()
            with patch.object(Retriever,'retrieve_multi',side_effect=[[RetrievedChunk(background(),1.,'raw')],result]):
                reply=agent.ask('他初始武力多少')
            self.assertEqual(reply.answer,CLARIFY_REFERENT_ANSWER)
            self.assertEqual(reply.evidence,[])
            client.generate.assert_not_called()
            client.generate_json.assert_not_called()

    def test_unsupported_syntax_keeps_legacy_path_but_consumes_binding(self):
        agent,client=agent_with()
        agent.ask('甲将初始武力多少')
        client.reset_mock()
        reply=agent.ask('他初始武力多少啊')
        self.assertEqual(reply.referent_resolution,'not_applicable')
        client.generate_json.assert_called_once()
        self.assert_clarifies(agent,client)

    def test_known_refusal_even_with_valid_citation_does_not_bind(self):
        agent,client=agent_with()
        client.generate.return_value=LLMResult('知识库未收录该细节 [hero-a]','fake',0,0,0)
        agent.ask('甲将初始武力多少')
        self.assert_clarifies(agent,client)

    def test_source_changed_during_first_generation_cannot_bind(self):
        agent,client=agent_with()
        def mutate(**kwargs):
            agent.retriever.entries[0].structured_data.notes.append('midcall-change')
            return LLMResult('事实 [hero-a]','fake',0,0,0)
        client.generate.side_effect=mutate
        agent.ask('甲将初始武力多少')
        self.assert_clarifies(agent,client)

    def test_nonempty_images_input_clears_binding_on_legacy_image_path(self):
        agent,client=agent_with()
        agent.ask('甲将初始武力多少')
        with patch('qa_agent.vision.image_loader.prepare_image_inputs',return_value=[]):
            agent.ask('甲将初始武力多少',images=['synthetic-image'])
        self.assert_clarifies(agent,client)
