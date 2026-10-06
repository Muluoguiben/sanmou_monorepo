"""Strict synthetic season applicability controls, separate from QA quality."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, StrictInt, StrictStr, field_validator, model_validator

from qa_agent.index.search_index import SearchIndex
from qa_agent.knowledge.models import KnowledgeEntry
from qa_agent.retrieval.seasonal import _validate_request, retrieve_lineups_for_season


def _id(value: str) -> str:
    if not value.strip():
        raise ValueError("nonempty ID required")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class _Mismatch(_Strict):
    id: StrictStr
    reason: Literal["season_mismatch"]
    _nonempty = field_validator("id")(_id)


class _Unknown(_Strict):
    id: StrictStr
    reason: Literal["missing_season_tags", "not_lineup_solution"]
    _nonempty = field_validator("id")(_id)


class _Expected(_Strict):
    match_ids: list[StrictStr]
    mismatch: list[_Mismatch]
    unknown: list[_Unknown]

    @model_validator(mode="after")
    def unique_ids(self):
        ids = self.match_ids + [row.id for row in self.mismatch + self.unknown]
        for value in ids:
            _id(value)
        if len(set(ids)) != len(ids):
            raise ValueError("duplicate expected ID")
        return self


class _Case(_Strict):
    id: StrictStr
    split: Literal["development"]
    review_status: Literal["developer-authored"]
    query: StrictStr
    season_tag: StrictStr
    top_k: StrictInt
    entries: list[dict]
    expected: _Expected
    _nonempty = field_validator("id")(_id)

    @model_validator(mode="after")
    def valid_request_and_expected(self):
        _validate_request(self.query, self.season_tag, self.top_k)
        entries = _entries(self.entries)
        SearchIndex(entries)
        expected = self.expected
        ids = expected.match_ids + [row.id for row in expected.mismatch + expected.unknown]
        if not set(ids) <= {entry.id for entry in entries}:
            raise ValueError("expected ID not in input entries")
        if any(len(group) > self.top_k for group in (expected.match_ids, expected.mismatch, expected.unknown)):
            raise ValueError("expected group exceeds top_k")
        return self


def _entries(rows: list[dict]) -> list[KnowledgeEntry]:
    for row in rows:
        if set(row) - set(KnowledgeEntry.model_fields):
            raise ValueError("unknown entry field")
    return [KnowledgeEntry.model_validate(row) for row in rows]


def validate_cases(cases: object) -> list[_Case]:
    if type(cases) is not list or not cases:
        raise ValueError("season_cases must be a nonempty list")
    parsed = [_Case.model_validate(case) for case in cases]
    if len({case.id for case in parsed}) != len(parsed):
        raise ValueError("duplicate season case ID")
    return parsed


def evaluate_season_cases(cases: object) -> dict:
    parsed = validate_cases(cases)
    rows = []
    for case in parsed:
        result = retrieve_lineups_for_season(_entries(case.entries), case.query,
                                           season_tag=case.season_tag, top_k=case.top_k)
        actual = {"match_ids": [chunk.entry.id for chunk in result.match],
                  "mismatch": [{"id": item.chunk.entry.id, "reason": item.reason} for item in result.mismatch],
                  "unknown": [{"id": item.chunk.entry.id, "reason": item.reason} for item in result.unknown]}
        expected = case.expected.model_dump()
        rows.append({"id": case.id, "actual": actual, "expected": expected, "control_pass": actual == expected})
    return {"status": "developer-authored-synthetic-controls", "synthetic": True,
            "passed": sum(row["control_pass"] for row in rows), "denominator": len(rows),
            "gate_pass": all(row["control_pass"] for row in rows), "cases": rows,
            "scope": "exact declared season tags; not semantic support or review certification"}
