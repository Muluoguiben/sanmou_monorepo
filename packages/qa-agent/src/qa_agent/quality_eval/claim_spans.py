"""Offline, externally labelled claim spans; mechanical links are not entailment."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, field_validator

from qa_agent.quality_eval.runner import _validate_execution_roots
from qa_agent.quality_eval.scoring import digest, ratio, score_answer, snapshot

PROTOCOL = "qa-claim-spans/v1"
NORMALIZATION = "utf8-crlf-to-lf-codepoint-v1"
BASELINE = "claim-spans-v1"
SHA256 = Annotated[StrictStr, Field(pattern=r"^[0-9a-f]{64}$")]
ReviewStatus = Literal["developer-authored", "unreviewed", "human-reviewed"]


def _text(value: str) -> str:
    if type(value) is not str:
        raise ValueError("text must be a string")
    value = value.replace("\r\n", "\n")
    if "\r" in value:
        raise ValueError("bare CR is not supported")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("text must be UTF-8 encodable") from exc
    return value


def _identifier(value: str) -> str:
    _text(value)
    if not value.strip() or any(c in value for c in "[]\r\n"):
        raise ValueError("nonempty single-line evidence ID required")
    return value


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class SupportSpan(_Strict):
    entry_id: StrictStr
    content_sha256: SHA256
    start: StrictInt
    end: StrictInt

    _id = field_validator("entry_id")(_identifier)


class ClaimSegment(_Strict):
    start: StrictInt
    end: StrictInt
    verdict: Literal["supported", "unsupported", "unknown", "nonclaim"]
    support_spans: list[SupportSpan]


class ClaimAnnotation(_Strict):
    protocol: Literal["qa-claim-spans/v1"]
    normalization: Literal["utf8-crlf-to-lf-codepoint-v1"]
    context_sha256: SHA256
    answer_sha256: SHA256
    evidence_sha256: dict[StrictStr, SHA256]
    review_status: ReviewStatus
    source: StrictStr
    reviewer: StrictStr
    context_verdict: Literal["correct", "incorrect", "unknown"]
    segments: list[ClaimSegment]

    @field_validator("source", "reviewer")
    @classmethod
    def provenance(cls, value: str) -> str:
        _text(value)
        if not value.strip():
            raise ValueError("label provenance required")
        return value


class _Ratio(_Strict):
    numerator: Annotated[StrictInt, Field(ge=0)]
    denominator: Annotated[StrictInt, Field(ge=0)]
    value: Annotated[float, Field(ge=0, le=1)] | None

    @field_validator("value", mode="before")
    @classmethod
    def no_bool(cls, value: object) -> object:
        if type(value) is bool:
            raise ValueError("ratio value must not be boolean")
        return value


class _Mechanical(_Strict):
    valid_links: _Ratio


class _Semantic(_Strict):
    review_status: ReviewStatus
    claims: Annotated[StrictInt, Field(ge=0)]
    unjudged_claims: Annotated[StrictInt, Field(ge=0)]
    citation_id_validity: _Ratio
    claim_support: _Ratio
    supported_citation_completeness: _Ratio
    context_correctness: _Ratio
    semantic_method: Literal["external-span-adjudication; no automatic entailment"]


class _Expected(_Strict):
    mechanical: _Mechanical
    semantic: _Semantic


class _Case(_Strict):
    id: StrictStr
    context: StrictStr
    answer: StrictStr
    evidence: dict[StrictStr, StrictStr]
    annotation: ClaimAnnotation
    annotation_sha256: SHA256
    expected: _Expected

    _id = field_validator("id")(_identifier)


class _Corpus(_Strict):
    protocol: Literal["qa-claim-spans/v1"]
    normalization: Literal["utf8-crlf-to-lf-codepoint-v1"]
    split: Literal["development"]
    synthetic: StrictBool
    label_origin: Literal["developer-authored"]
    cases: Annotated[list[_Case], Field(min_length=1)]

    @field_validator("synthetic")
    @classmethod
    def synthetic_only(cls, value: bool) -> bool:
        if not value:
            raise ValueError("synthetic fixture required")
        return value

    @field_validator("cases")
    @classmethod
    def controls_only(cls, cases: list[_Case]) -> list[_Case]:
        if len({case.id for case in cases}) != len(cases):
            raise ValueError("duplicate case ID")
        if any(case.annotation.review_status == "human-reviewed" for case in cases):
            raise ValueError("synthetic cases cannot claim human review")
        return cases


class _Freeze(_Strict):
    protocol: Literal["qa-claim-spans/v1"]
    normalization: Literal["utf8-crlf-to-lf-codepoint-v1"]
    baseline: Literal["claim-spans-v1"]
    cases_sha256: SHA256


def annotation_digest(annotation: dict) -> str:
    """Content version of external labels, not a signature or reviewer identity."""
    return digest(json.dumps(annotation, ensure_ascii=False, sort_keys=True,
                             separators=(",", ":"), allow_nan=False))


def score_claim_spans(answer: str, evidence: dict[str, str], annotation: dict, *,
                      context: str = "", annotation_sha256: str) -> dict:
    # Validate without repairing labels, and score exactly the normalized text
    # whose code-point coordinates the annotator declared.
    parsed = ClaimAnnotation.model_validate(annotation)
    if type(annotation_sha256) is not str or annotation_sha256 != annotation_digest(annotation):
        raise ValueError("annotation binding mismatch")
    answer, context = _text(answer), _text(context)
    if type(evidence) is not dict:
        raise ValueError("evidence must be an ID-to-text object")
    normalized = {_identifier(key): _text(value) for key, value in evidence.items()}
    if parsed.evidence_sha256 != {key: digest(value) for key, value in normalized.items()}:
        raise ValueError("evidence binding mismatch")
    projected = parsed.model_dump(exclude={"protocol", "normalization", "segments"})
    projected["segments"] = []
    count = 0
    for segment in parsed.segments:
        links = segment.support_spans
        if segment.verdict == "nonclaim" and links:
            raise ValueError("nonclaim must have no support links")
        if segment.verdict == "supported" and not links:
            raise ValueError("supported claim needs evidence links")
        seen = set()
        ids = []
        for link in links:
            identity = (link.entry_id, link.content_sha256, link.start, link.end)
            if identity in seen:
                raise ValueError("duplicate support link")
            seen.add(identity)
            text = normalized.get(link.entry_id)
            if text is None or digest(text) != link.content_sha256:
                raise ValueError("support evidence binding mismatch")
            if not 0 <= link.start < link.end <= len(text):
                raise ValueError("support span must be nonempty and within evidence")
            if link.entry_id not in ids:
                ids.append(link.entry_id)
            count += 1
        projected["segments"].append({"start": segment.start, "end": segment.end,
                                      "verdict": segment.verdict, "support_ids": ids})
    semantic = score_answer(answer, normalized, projected, context=context)
    return {"mechanical": {"valid_links": ratio(count, count)}, "semantic": semantic,
            "segments": [segment.model_dump() for segment in parsed.segments],
            "label_declaration": {"source": parsed.source, "reviewer": parsed.reviewer,
                                  "review_status": parsed.review_status, "authenticated": False}}


def _json_text(path: Path) -> str:
    # read_text's universal newline translation would conceal a bare CR.
    return _text(path.read_bytes().decode("utf-8-sig"))


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON object key")
        result[key] = value
    return result


def _check_source(package: Path) -> None:
    expected = package.resolve() / "src/qa_agent/quality_eval/claim_spans.py"
    origin = getattr(__spec__, "origin", None)
    if Path(__file__).resolve() != expected or not origin or Path(origin).resolve() != expected:
        raise ValueError("loaded evaluator/package source mismatch")
    _validate_execution_roots(package)


def run(package: Path, *, baseline: str = BASELINE) -> dict:
    if type(baseline) is not str or baseline != BASELINE:
        raise ValueError("unsupported baseline version")
    _check_source(package)
    fixtures = package / "tests/fixtures/quality_eval/claim_spans_v1"
    before = snapshot(package, list(fixtures.glob("*.json")))
    source = snapshot(package, list((package / "src/qa_agent/quality_eval").glob("*.py")))
    cases_text = _json_text(fixtures / "cases.json")
    frozen = _Freeze.model_validate(json.loads(_json_text(fixtures / "freeze.json"),
                                               object_pairs_hook=_unique_object))
    if digest(cases_text) != frozen.cases_sha256:
        raise ValueError("claim span fixture drift")
    corpus = _Corpus.model_validate(json.loads(cases_text, object_pairs_hook=_unique_object))
    rows = []
    for case in corpus.cases:
        actual = score_claim_spans(case.answer, case.evidence, case.annotation.model_dump(),
                                   context=case.context, annotation_sha256=case.annotation_sha256)
        control_pass = {key: actual[key] for key in ("mechanical", "semantic")} == case.expected.model_dump()
        rows.append({"id": case.id, "annotation_sha256": case.annotation_sha256,
                     "control_pass": control_pass, **actual})
    _check_source(package)
    if before != snapshot(package, list(fixtures.glob("*.json"))) or source != snapshot(
            package, list((package / "src/qa_agent/quality_eval").glob("*.py"))):
        raise ValueError("evaluation input/source drift during run")
    return {"protocol": PROTOCOL, "normalization": NORMALIZATION, "baseline": baseline,
            "split": "development", "synthetic": True, "label_origin": "developer-authored",
            "execution_authority": "none", "executable": False,
            "fixture": before, "eval_source": source, "cases": rows,
            "controls": ratio(sum(row["control_pass"] for row in rows), len(rows)),
            "gate_pass": all(row["control_pass"] for row in rows),
            "provider": {"calls": 0, "quality": "not_measured"},
            "holdout": {"established": False, "denominator": 0},
            "human_review": {"authenticated": False, "labels": 0},
            "limitations": ["External labels, not automatic entailment or authenticated human review.",
                            "Content hashes and module origins are not signed Git/source certification.",
                            "Synthetic development controls do not measure provider or holdout quality."]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", choices=(BASELINE,), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[3], baseline=args.baseline)
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    if not result["gate_pass"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
