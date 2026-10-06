"""Opt-in exact season-tag applicability; not review or factual certification."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

from qa_agent.index.search_index import SearchIndex
from qa_agent.knowledge.models import EntryKind, KnowledgeEntry, LineupSolutionProfile
from qa_agent.retrieval.retriever import RetrievedChunk, Retriever


class SeasonDiagnostic(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    chunk: RetrievedChunk
    reason: Literal["season_mismatch", "missing_season_tags", "not_lineup_solution"]


class SeasonalRetrievalResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    query: str
    season_tag: str
    top_k: int
    match: list[RetrievedChunk]
    mismatch: list[SeasonDiagnostic]
    unknown: list[SeasonDiagnostic]
    execution_authority: Literal["none"] = "none"
    executable: Literal[False] = False


def _validate_request(query: str, season_tag: str, top_k: int) -> None:
    if type(query) is not str or not query.strip():
        raise ValueError("query must be a nonempty string")
    if type(season_tag) is not str or not season_tag or season_tag != season_tag.strip():
        raise ValueError("season tag must be a nonempty exact string without edge whitespace")
    if type(top_k) is not int or top_k <= 0:
        raise ValueError("top_k must be a positive integer")


def retrieve_lineups_for_season(entries: list[KnowledgeEntry], query: str, *,
                               season_tag: str, top_k: int = 5) -> SeasonalRetrievalResult:
    _validate_request(query, season_tag, top_k)
    if type(entries) is not list or any(not isinstance(entry, KnowledgeEntry) for entry in entries):
        raise ValueError("entries must be a list of KnowledgeEntry objects")
    entries = list(entries)
    # Validate the full input BEFORE any partition or retrieval. In particular,
    # cross-season and query-unrelated duplicates must not disappear in a pool.
    SearchIndex(entries)
    pools: dict[str, list[KnowledgeEntry]] = {"match": [], "mismatch": [], "unknown": []}
    reasons = {}
    for entry in entries:
        if entry.entry_kind != EntryKind.LINEUP_SOLUTION:
            group, reason = "unknown", "not_lineup_solution"
        else:
            profile = entry.structured_data
            if not isinstance(profile, LineupSolutionProfile):
                raise ValueError("lineup entry requires LineupSolutionProfile")
            if not profile.season_tags:
                group, reason = "unknown", "missing_season_tags"
            elif season_tag in profile.season_tags:
                group, reason = "match", None
            else:
                group, reason = "mismatch", "season_mismatch"
        pools[group].append(entry)
        reasons[entry.id] = reason
    # Filtering precedes top-k, with original ranking independently in each pool.
    groups = {name: Retriever(pool).retrieve(query, top_k=top_k) for name, pool in pools.items()}
    return SeasonalRetrievalResult(query=query, season_tag=season_tag, top_k=top_k,
        match=groups["match"],
        mismatch=[SeasonDiagnostic(chunk=chunk, reason=reasons[chunk.entry.id]) for chunk in groups["mismatch"]],
        unknown=[SeasonDiagnostic(chunk=chunk, reason=reasons[chunk.entry.id]) for chunk in groups["unknown"]])
