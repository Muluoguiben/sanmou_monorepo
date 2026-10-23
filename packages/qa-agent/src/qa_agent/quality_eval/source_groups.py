"""Check declared source-family isolation; never certify holdout independence or human gold."""
from __future__ import annotations

from typing import Literal

from pydantic import Field, model_validator

from qa_agent.knowledge.provenance import Digest, Identifier, StrictModel, canonical_digest


class SourceDocument(StrictModel):
    document_id: Identifier
    content_sha256: Digest | None = None
    derived_from: tuple[Identifier, ...] = ()
    # Explicit grouping may include original/translation/template/related-report families.
    family_ids: tuple[Identifier, ...] = ()
    lineage_status: Literal["reviewed", "unreviewed", "unknown"] = "unknown"

    @model_validator(mode="after")
    def unique_relations(self) -> "SourceDocument":
        if len(set(self.derived_from)) != len(self.derived_from) or self.document_id in self.derived_from:
            raise ValueError("parent IDs must be unique and exclude self")
        if len(set(self.family_ids)) != len(self.family_ids):
            raise ValueError("family IDs must be unique")
        return self


class EvaluationSample(StrictModel):
    sample_id: Identifier
    source_ids: tuple[Identifier, ...] = Field(min_length=1)
    split: Literal["train", "dev", "holdout", "review_queue"]
    developer_exposed: bool | None = Field(default=None, strict=True)

    @model_validator(mode="after")
    def unique_sources(self) -> "EvaluationSample":
        if len(set(self.source_ids)) != len(self.source_ids):
            raise ValueError("sample source IDs must be unique")
        return self


class SourceGroup(StrictModel):
    group_id: Digest
    document_ids: tuple[Identifier, ...]
    sample_ids: tuple[Identifier, ...]
    splits: tuple[str, ...]


class SplitIssue(StrictModel):
    code: Literal["cross_split_source_family", "exposed_holdout", "unknown_holdout_exposure", "unreviewed_holdout_lineage"]
    group_id: Digest
    sample_ids: tuple[Identifier, ...]


class SourceGroupAudit(StrictModel):
    protocol: Literal["knowledge-source-groups-v1"] = "knowledge-source-groups-v1"
    groups: tuple[SourceGroup, ...]
    issues: tuple[SplitIssue, ...]
    split_integrity_passed: bool
    review_queue_count: int
    independent_holdout_verified: Literal[False] = False
    human_gold: Literal[False] = False
    execution_authority: Literal["none"] = "none"


def audit_source_groups(documents: list[SourceDocument], samples: list[EvaluationSample]) -> SourceGroupAudit:
    """Union explicit derivations/families/exact content; report all known leakage."""
    docs = {item.document_id: item for item in documents}
    if len(docs) != len(documents):
        raise ValueError("duplicate document ID")
    if len({item.sample_id for item in samples}) != len(samples):
        raise ValueError("duplicate sample ID")
    for item in documents:
        if any(parent not in docs for parent in item.derived_from):
            raise ValueError(f"unknown parent document: {item.document_id}")
    for item in samples:
        if any(source not in docs for source in item.source_ids):
            raise ValueError(f"unknown sample source: {item.sample_id}")

    # Derivation cycles are invalid provenance, not a reason to silently merge everything.
    remaining = {key: len(item.derived_from) for key, item in docs.items()}
    children: dict[str, list[str]] = {key: [] for key in docs}
    for key, item in docs.items():
        for parent in item.derived_from:
            children[parent].append(key)
    ready = [key for key, count in remaining.items() if count == 0]
    visited_count = 0
    while ready:
        key = ready.pop()
        visited_count += 1
        for child in children[key]:
            remaining[child] -= 1
            if remaining[child] == 0:
                ready.append(child)
    if visited_count != len(docs):
        raise ValueError("cyclic source derivation")

    parents = {key: key for key in docs}
    def find(key: str) -> str:
        while parents[key] != key:
            parents[key] = parents[parents[key]]
            key = parents[key]
        return key
    def union(left: str, right: str) -> None:
        a, b = sorted((find(left), find(right)))
        parents[b] = a
    hashes = {}
    families = {}
    for item in sorted(documents, key=lambda item: item.document_id):
        for parent in item.derived_from:
            union(item.document_id, parent)
        if item.content_sha256:
            union(item.document_id, hashes.setdefault(item.content_sha256, item.document_id))
        for family in item.family_ids:
            union(item.document_id, families.setdefault(family, item.document_id))

    components: dict[str, list[str]] = {}
    for key in sorted(docs):
        components.setdefault(find(key), []).append(key)
    groups = []
    issues = []
    for members in components.values():
        member_set = set(members)
        associated = sorted((item for item in samples if member_set.intersection(item.source_ids)), key=lambda item: item.sample_id)
        splits = sorted({item.split for item in associated if item.split != "review_queue"})
        group_id = canonical_digest(members)
        sample_ids = tuple(item.sample_id for item in associated)
        groups.append(SourceGroup(group_id=group_id, document_ids=tuple(members), sample_ids=sample_ids, splits=tuple(splits)))
        if len(splits) > 1:
            issues.append(SplitIssue(code="cross_split_source_family", group_id=group_id, sample_ids=sample_ids))
        holdout = [item for item in associated if item.split == "holdout"]
        # Exposure belongs to the whole related family, including review_queue material.
        if holdout and any(item.developer_exposed for item in associated):
            issues.append(SplitIssue(code="exposed_holdout", group_id=group_id, sample_ids=sample_ids))
        if holdout and any(item.developer_exposed is None for item in associated):
            issues.append(SplitIssue(code="unknown_holdout_exposure", group_id=group_id, sample_ids=sample_ids))
        if holdout and any(docs[key].lineage_status != "reviewed" for key in members):
            issues.append(SplitIssue(code="unreviewed_holdout_lineage", group_id=group_id, sample_ids=sample_ids))
    return SourceGroupAudit(groups=tuple(sorted(groups, key=lambda group: group.group_id)),
                            issues=tuple(sorted(issues, key=lambda issue: (issue.group_id, issue.code))),
                            split_integrity_passed=not issues,
                            review_queue_count=sum(item.split == "review_queue" for item in samples))


def require_split_integrity(documents: list[SourceDocument], samples: list[EvaluationSample]) -> SourceGroupAudit:
    report = audit_source_groups(documents, samples)
    if not report.split_integrity_passed:
        raise ValueError("source split check failed: " + ", ".join(sorted({item.code for item in report.issues})))
    return report
