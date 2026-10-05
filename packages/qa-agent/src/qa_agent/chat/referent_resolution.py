"""One-use, immediately-adjacent text-only hero referents.

Grammar: 他/该武将 + optional 的 + 初始/基础/满级/成长 +
武力/智力/统率/先攻 + optional 是 + 多少 + optional ？/?/。.
Outer whitespace is ignored; internal whitespace/extra clauses are not accepted.
History is an integrity binding, never a source of facts. In-memory catalog only.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import TYPE_CHECKING

from qa_agent.knowledge.models import HeroStaticProfile, KnowledgeEntry
from qa_agent.retrieval.retriever import RetrievedChunk

if TYPE_CHECKING:
    from qa_agent.chat.agent import ChatTurn

FOLLOWUP = re.compile(r'(?:他|该武将)的?(初始|基础|满级|成长)(武力|智力|统率|先攻)是?多少[？?。]?')
CLARIFY_REFERENT_ANSWER = '请明确指出要查询的武将名称。'
_REFUSAL_MARKERS = ('未收录', '无法回答', '无法确定', '不知道', '不清楚', '没有证据', '请明确', '引用未能')


def followup_suffix(question: str) -> str | None:
    match = FOLLOWUP.fullmatch(question.strip())
    return f'{match[1]}{match[2]}是多少' if match else None


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',', ':')).encode()).hexdigest()


def entry_fingerprint(entry: KnowledgeEntry) -> str:
    return _digest(entry.model_dump(mode='json'))


def _history_fingerprint(history: list[ChatTurn]) -> str:
    return _digest([{'role':turn.role,'content':turn.content,'evidence_ids':turn.evidence_ids} for turn in history])


def hero_identity(entry: KnowledgeEntry) -> str | None:
    return entry.structured_data.name if isinstance(entry.structured_data,HeroStaticProfile) else None


def _explicit_hero(question: str, entries: list[KnowledgeEntry]) -> str | None:
    aliases: dict[str,set[str]] = {}
    for entry in entries:
        name=hero_identity(entry)
        if name:
            for alias in (name,*entry.aliases,*entry.structured_data.aliases):
                if alias:
                    aliases.setdefault(alias,set()).add(name)
    found=set()
    for alias,names in aliases.items():
        if alias in question:
            if len(names) != 1:
                return None
            found.update(names)
    return next(iter(found)) if len(found)==1 else None


@dataclass(frozen=True)
class AcceptedReferent:
    canonical: str
    sources: dict[str,str]
    history_container: list[ChatTurn] = field(repr=False,compare=False)
    history_digest: str
    completed_position: int

    def resolve(self, history: list[ChatTurn], entries: list[KnowledgeEntry], suffix: str) -> str | None:
        if history is not self.history_container or len(history)!=self.completed_position:
            return None
        if _history_fingerprint(history)!=self.history_digest:
            return None
        current={e.id:e for e in entries}
        if len(current)!=len(entries) or any(identifier not in current or entry_fingerprint(current[identifier])!=fingerprint
                for identifier,fingerprint in self.sources.items()):
            return None
        # Revalidate aliases/canonical identity against the current catalog too.
        if _explicit_hero(self.canonical,entries)!=self.canonical:
            return None
        return self.canonical+suffix


def accept_referent(question: str, cited_ids: list[str], evidence: list[RetrievedChunk],
                    entries: list[KnowledgeEntry], history: list[ChatTurn]) -> AcceptedReferent | None:
    """Caller must first pass the real answer citation gate; never use prose."""
    canonical=_explicit_hero(question,entries)
    if not canonical or not cited_ids or len(history)<2 or [t.role for t in history[-2:]]!=['user','assistant']:
        return None
    # Conservative rejection of known refusal wording, not a semantic success
    # classifier. The existing citation gate remains necessary, not sufficient.
    if any(marker in history[-1].content for marker in _REFUSAL_MARKERS):
        return None
    candidates={c.entry.id:c.entry for c in evidence}
    current={e.id:e for e in entries}
    if len(current)!=len(entries) or any(i not in candidates or i not in current for i in cited_ids):
        return None
    cited={i:candidates[i] for i in cited_ids}
    heroes={hero_identity(e) for e in cited.values() if hero_identity(e) is not None}
    if heroes!={canonical}:
        return None
    fingerprints={i:entry_fingerprint(e) for i,e in cited.items()}
    if any(entry_fingerprint(current[i])!=fingerprint for i,fingerprint in fingerprints.items()):
        return None
    return AcceptedReferent(canonical,fingerprints,history,_history_fingerprint(history),len(history))
