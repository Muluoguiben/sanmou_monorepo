from __future__ import annotations

import hashlib
import re
from pathlib import Path

CITATION = re.compile(r"\[([^\[\]\n]+)\]")


def digest(text: str) -> str:
    return hashlib.sha256(text.replace("\r\n", "\n").encode("utf-8")).hexdigest()


def snapshot(root: Path, paths: list[Path]) -> dict:
    """Portable UTF-8/LF content manifest; paths and contents both bind the hash."""
    files = {p.relative_to(root).as_posix(): digest(p.read_text(encoding="utf-8-sig"))
             for p in sorted(paths) if p.is_file()}
    import json
    return {"algorithm": "sha256-utf8-lf-v1", "files": files,
            "digest": digest(json.dumps(files, sort_keys=True, ensure_ascii=False))}


def ratio(numerator: int | float, denominator: int) -> dict:
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def retrieval_score(expected: list[str], retrieved: list[str]) -> dict:
    if len(set(expected)) != len(expected) or len(set(retrieved)) != len(retrieved):
        raise ValueError("duplicate evidence ID")
    hits = set(expected) & set(retrieved)
    rank = next((i for i, item in enumerate(retrieved, 1) if item in expected), None)
    return {"recall": ratio(len(hits), len(expected)),
            "reciprocal_rank": 1 / rank if rank else (0 if expected else None),
            "empty_retrieval": not retrieved}


def score_answer(answer: str, evidence: dict[str, str], annotation: dict, *, context: str = "") -> dict:
    """Score a fully segmented, answer-bound adjudication, never infer semantics.

    Verdicts are external labels. Unknown/unreviewed claims remain unknown.
    Supported labels must identify evidence actually cited in that claim.
    """
    if annotation["context_sha256"] != digest(context):
        raise ValueError("query/history context binding mismatch")
    if annotation["answer_sha256"] != digest(answer):
        raise ValueError("answer binding mismatch")
    if annotation["evidence_sha256"] != {k: digest(v) for k, v in evidence.items()}:
        raise ValueError("evidence binding mismatch")
    review = annotation["review_status"]
    if review not in {"developer-authored", "unreviewed", "human-reviewed"}:
        raise ValueError("invalid review status")
    if not annotation.get("source") or not annotation.get("reviewer"):
        raise ValueError("label provenance required")
    context_verdict = annotation["context_verdict"]
    if context_verdict not in {"correct", "incorrect", "unknown"}:
        raise ValueError("invalid context verdict")
    offset = 0
    claims = supported = judged = complete = 0
    for segment in annotation["segments"]:
        start, end = segment["start"], segment["end"]
        if type(start) is not int or type(end) is not int or start != offset or not start < end <= len(answer):
            raise ValueError("segments must cover answer exactly, without gaps/overlap")
        offset = end
        verdict = segment["verdict"]
        if verdict not in {"supported", "unsupported", "unknown", "nonclaim"}:
            raise ValueError("invalid verdict")
        if verdict == "nonclaim":
            continue
        claims += 1
        refs = segment["support_ids"]
        cited = CITATION.findall(answer[start:end])
        if any(ref not in evidence for ref in refs):
            raise ValueError("support evidence missing")
        if verdict == "supported" and not refs:
            raise ValueError("supported claim needs evidence")
        known = review != "unreviewed" and verdict != "unknown"
        judged += int(known)
        supported += int(known and verdict == "supported")
        complete += int(known and verdict == "supported" and set(refs) <= set(cited))
    if offset != len(answer):
        raise ValueError("unannotated answer text")
    citations = CITATION.findall(answer)
    return {"review_status": review, "claims": claims, "unjudged_claims": claims - judged,
            "citation_id_validity": ratio(sum(c in evidence for c in citations), len(citations)),
            "claim_support": ratio(supported, judged),
            "supported_citation_completeness": ratio(complete, claims),
            "context_correctness": ratio(int(context_verdict == "correct" and review != "unreviewed"),
                                         int(context_verdict != "unknown" and review != "unreviewed")),
            "semantic_method": "external-span-adjudication; no automatic entailment"}


def refusal_score(expected: list[bool], actual: list[bool]) -> dict:
    if len(expected) != len(actual) or any(type(x) is not bool for x in expected + actual):
        raise ValueError("paired boolean refusal labels required")
    tp = sum(e and a for e, a in zip(expected, actual))
    return {"precision": ratio(tp, sum(actual)), "recall": ratio(tp, sum(expected)),
            "accuracy": ratio(sum(e == a for e, a in zip(expected, actual)), len(expected))}
