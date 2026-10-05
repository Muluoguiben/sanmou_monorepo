"""Developer-authored deterministic multi-turn controls, not provider quality."""
from copy import deepcopy
from datetime import date
from unittest.mock import MagicMock

from qa_agent.chat.agent import ChatAgent
from qa_agent.chat.llm_client import LLMResult
from qa_agent.knowledge.models import KnowledgeEntry, HeroStaticProfile, AttributeSet
from qa_agent.retrieval.retriever import Retriever, RetrievedChunk

SCENARIOS = ('alias_success','no_binding','wrong_citation','raw_miss','single_use',
             'source_withdrawal','new_conflict','history_replace','notes_partial')


def evaluate_referent_cases(cases: list[dict]) -> list[dict]:
    rows=[]
    for case in cases:
        scenario=case['scenario']
        if scenario not in SCENARIOS:
            raise ValueError('unknown referent scenario')
        a=KnowledgeEntry(id='synthetic-a',topic='甲将',domain='hero',entry_kind='hero_profile',
            facts=['合成武将记录'],source_ref='synthetic-source-a',updated_at=date(2026,10,6),confidence=.9,
            structured_data=HeroStaticProfile(name='甲将',aliases=['甲公'],base_attributes=AttributeSet(military=0)))
        b=a.model_copy(deep=True,update={'id':'synthetic-b','topic':'乙将','source_ref':'synthetic-source-b'})
        b.structured_data.name='乙将'
        b.structured_data.aliases=[]
        background=KnowledgeEntry(id='synthetic-rule',topic='属性机制',domain='team',
            facts=['初始武力是武将属性。'],source_ref='synthetic-rule-source',updated_at=date(2026,10,6),confidence=.9)
        if scenario=='notes_partial': a.structured_data.notes=['未评估的背景说明']
        retriever=Retriever([a] if scenario=='raw_miss' else [a,b,background])
        client=MagicMock()
        client.generate.return_value=LLMResult('合成答案 [synthetic-a]','fake',0,0,0)
        client.generate_json.return_value=['甲将']
        if scenario=='wrong_citation':
            retriever.retrieve_multi=MagicMock(return_value=[RetrievedChunk(e,1.,'synthetic') for e in retriever.entries])
            client.generate.return_value=LLMResult('乙 [synthetic-b]','fake',0,0,0)
        agent=ChatAgent(retriever,client)
        if scenario!='no_binding': agent.ask('甲公')
        if scenario=='source_withdrawal': retriever.entries.remove(a)
        if scenario=='history_replace': agent.history=deepcopy(agent.history)
        if scenario=='new_conflict':
            other=a.model_copy(deep=True,update={'id':'synthetic-new','source_ref':'synthetic-new-source'})
            other.structured_data.base_attributes.military=1
            retriever.entries.append(other)
        if scenario=='single_use': agent.ask(case['question'])
        client.reset_mock()
        reply=agent.ask(case['question'])
        actual={'resolution':reply.referent_resolution,'answer_calls':client.generate.call_count,
                'rewrite_calls':client.generate_json.call_count,'assessment_status':reply.assessment.status}
        if actual!=case['expected']:
            raise ValueError(f'referent case failed: {case["id"]}: {actual}')
        if actual['resolution']=='resolved' and actual['answer_calls']:
            if f'用户问题：{reply.resolved_question}' not in client.generate.call_args.kwargs['user_message']:
                raise ValueError('resolved question missing from actual prompt')
        rows.append({'id':case['id'],**actual})
    return rows
