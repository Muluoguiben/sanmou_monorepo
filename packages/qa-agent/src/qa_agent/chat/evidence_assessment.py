"""Bounded scalar checks, not semantic entailment or source truth ranking.

Only an exact single-entity attribute question is assessed. Notes and explicit
prose scope cues prevent comparison: empty constraints do not certify scope.
Missing slots say nothing about facts or notes.
"""
from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from qa_agent.knowledge.models import KnowledgeEntry, HeroStaticProfile
from qa_agent.retrieval.retriever import RetrievedChunk


class FieldEvidence(BaseModel):
    entry_id: str
    source_ref: str
    entity: str
    field_path: str
    value: int | float | str | None


class ApplicabilityEvidence(BaseModel):
    entry_id: str
    source_ref: str
    qualifiers: list[str]


class EvidenceAssessment(BaseModel):
    status: Literal['supported', 'partial', 'conflicting', 'not_found']
    check_scope: Literal['scalar_profile', 'unassessed', 'empty']
    decision: Literal['generate', 'disclose_conflict', 'refuse']
    reasons: list[str] = Field(default_factory=list)
    fields: list[FieldEvidence] = Field(default_factory=list)
    applicability: list[ApplicabilityEvidence] = Field(default_factory=list)

    def prompt_block(self) -> str:
        fields = '\n'.join(
            f'[{f.entry_id}] {f.entity} {f.field_path}={f.value} (source={f.source_ref})'
            for f in self.fields if f.value is not None)
        qualifiers = '\n'.join(
            f'[{a.entry_id}] 适用性未评估：' + '；'.join(a.qualifiers) + f' (source={a.source_ref})'
            for a in self.applicability)
        return '\n'.join(part for part in (fields, qualifiers) if part)

    def conflict_answer(self) -> str:
        return '本轮同一实体同一字段的来源取值不一致，无法确定唯一答案：\n' + self.prompt_block()


def assess_evidence(question: str, chunks: list[RetrievedChunk], *,
                    catalog: list[KnowledgeEntry] | None = None) -> EvidenceAssessment:
    if not chunks:
        return EvidenceAssessment(status='not_found', check_scope='empty', decision='refuse', reasons=['no_evidence'])
    partial = dict(status='partial', check_scope='unassessed', decision='generate')
    # Do not use searchable_terms: lineup members are not lineup identities.
    anchors: dict[str, set[str]] = {}
    for entry in catalog if catalog is not None else [c.entry for c in chunks]:
        data = entry.structured_data
        if isinstance(data, HeroStaticProfile):
            for name in (data.name, *data.aliases, *entry.aliases):
                if name:
                    anchors.setdefault(name, set()).add(data.name)
    matches = []
    for anchor, entities in anchors.items():
        match = re.fullmatch(re.escape(anchor) + r'的?(初始|基础|满级|成长)(武力|智力|统率|先攻)(?:是?多少|是?什么)?[？?。\s]*', question.strip())
        if match and len(entities) == 1:
            matches.append((next(iter(entities)), match.group(1), match.group(2)))
    if len(set(matches)) != 1:
        return EvidenceAssessment(**partial, reasons=['unassessed_question'])
    entity, stage, attribute = matches[0]
    root = {'初始':'base_attributes', '基础':'base_attributes', '满级':'max_attributes', '成长':'growth_attributes'}[stage]
    leaf = {'武力':'military', '智力':'intelligence', '统率':'command', '先攻':'initiative'}[attribute]
    relevant = [c.entry for c in chunks if isinstance(c.entry.structured_data, HeroStaticProfile)
                and c.entry.structured_data.name == entity]
    if not relevant:
        return EvidenceAssessment(**partial, reasons=['entity_not_in_evidence'])
    fields = []
    applicability = []
    for entry in relevant:
        attrs = getattr(entry.structured_data, root)
        fields.append(FieldEvidence(entry_id=entry.id, source_ref=entry.source_ref,
            entity=entity, field_path=f'{root}.{leaf}', value=getattr(attrs, leaf) if attrs is not None else None))
        # Notes are arbitrary prose, so none are certified as scope-free. Facts
        # with explicit bounded scope cues are likewise not silently discarded.
        # This recognizer is deliberately not general season/NLU inference.
        scoped_facts = [fact for fact in entry.facts if re.search(
            r'(?i)(?:\bS\s*\d+\b|赛季|版本|仅|适用|条件|期间|如果|当.+时|前提|阶段)', fact)]
        qualifiers = list(dict.fromkeys([*entry.constraints, *entry.structured_data.notes, *scoped_facts]))
        if qualifiers:
            applicability.append(ApplicabilityEvidence(entry_id=entry.id,
                source_ref=entry.source_ref, qualifiers=qualifiers))
    missing = any(f.value is None for f in fields)
    if applicability:
        return EvidenceAssessment(**partial, reasons=['unassessed_applicability'] +
            (['missing_structured_value'] if missing else []), fields=fields, applicability=applicability)
    values = {f.value for f in fields if f.value is not None}
    if len(values) > 1:
        return EvidenceAssessment(status='conflicting', check_scope='scalar_profile',
            decision='disclose_conflict', reasons=['scalar_disagreement'], fields=fields)
    return EvidenceAssessment(status='partial' if missing else 'supported', check_scope='scalar_profile',
        decision='generate', reasons=['missing_structured_value'] if missing else ['scalar_present'], fields=fields)
