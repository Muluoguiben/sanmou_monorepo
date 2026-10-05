"""Synthetic developer-authored gate checks; no provider or semantic gold."""
from datetime import date
from unittest.mock import MagicMock

from qa_agent.chat.agent import ChatAgent
from qa_agent.chat.llm_client import LLMResult
from qa_agent.knowledge.models import KnowledgeEntry, HeroStaticProfile, AttributeSet
from qa_agent.retrieval.retriever import Retriever, RetrievedChunk


def evaluate_cases(cases: list[dict]) -> list[dict]:
    rows = []
    for case in cases:
        if case['split'] != 'development' or case['review_status'] != 'developer-authored':
            raise ValueError('assessment provenance/split mismatch')
        entries = [KnowledgeEntry(id=f'synthetic-{i}', domain='hero', entry_kind='hero_profile',
            topic='甲将', facts=['正文初始武力0'], source_ref=f'synthetic-source-{i}',
            updated_at=date(2026,10,5), confidence=.9,
            structured_data=HeroStaticProfile(name='甲将',base_attributes=AttributeSet(military=v)))
            for i,v in enumerate(case['values'])]
        retriever=Retriever(entries)
        retriever.retrieve_multi=MagicMock(return_value=[RetrievedChunk(e,1.,'synthetic') for e in entries])
        client=MagicMock()
        client.generate.return_value=LLMResult('正文初始武力0 [synthetic-0]','fake',0,0,0)
        reply=ChatAgent(retriever,client).ask(case['question'])
        actual={'status':reply.assessment.status, 'check_scope':reply.assessment.check_scope,
                'answer_calls':client.generate.call_count}
        if actual != case['expected']:
            raise ValueError(f'assessment case failed: {case["id"]}: {actual}')
        rows.append({'id':case['id'], **actual})
    return rows
