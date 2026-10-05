from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from qa_agent.quality_eval.scoring import digest, ratio, retrieval_score, score_answer, snapshot
from qa_agent.retrieval.retriever import Retriever


def run(package: Path, *, baseline: str = 'v1') -> dict:
    if baseline not in {'v1', 'v2'}:
        raise ValueError('unsupported baseline version')
    if package.resolve() != Path(__file__).resolve().parents[3]:
        raise ValueError('loaded evaluator/package source mismatch')
    fixtures = package / 'tests/fixtures/quality_eval' / baseline
    corpus = json.loads((fixtures / "cases.json").read_text(encoding="utf-8-sig"))
    frozen = json.loads((fixtures / "freeze.json").read_text(encoding="utf-8-sig"))
    if not re.fullmatch(r'[0-9a-f]{40}', frozen.get('baseline_commit', '')):
        raise ValueError('invalid source commit binding')
    if corpus['version'] != int(baseline[1:]) or corpus['split'] != 'development':
        raise ValueError('baseline version/split mismatch')
    for group in ('queries', 'scoring_cases', 'assessment_cases'):
        cases = corpus.get(group, [])
        if len({c['id'] for c in cases}) != len(cases):
            raise ValueError('duplicate case ID')
    if any(c['split'] != 'development' for c in corpus['queries']):
        raise ValueError('query split mismatch')
    for case in corpus['queries']:
        labels = case['evidence_labels']
        if len({label['id'] for label in labels}) != len(labels):
            raise ValueError('duplicate evidence ID')
    kb = snapshot(package, list((package / "knowledge_sources").rglob("*.yaml")))
    production = snapshot(package, [p for p in (package / "src/qa_agent").rglob("*.py")
                                    if "quality_eval" not in p.parts])
    if kb != frozen["kb"] or production != frozen["production"]:
        raise ValueError("frozen KB/production source drift; create a reviewed new baseline version")
    if digest((fixtures / "cases.json").read_text(encoding="utf-8-sig")) != frozen["cases_sha256"]:
        raise ValueError("query/label fixture drift")
    retriever = Retriever.from_knowledge_dir(package / "knowledge_sources")
    entries = {e.id: e for e in retriever.entries}
    rows = []
    for case in corpus["queries"]:
        for label in case["evidence_labels"]:
            entry = entries[label["id"]]
            if label["source_ref"] != entry.source_ref or label["facts_sha256"] != digest("\n".join(entry.answer_lines())):
                raise ValueError("evidence label source mismatch")
        actual = [c.entry.id for c in retriever.retrieve(case["query"], top_k=corpus["top_k"])]
        expected = [e["id"] for e in case["evidence_labels"]]
        rows.append({**case, "retrieved_ids": actual, **retrieval_score(expected, actual)})
    answerable = [r for r in rows if r["evidence_labels"]]
    mocks = [{"id": c["id"], **score_answer(c["answer"], c["evidence"], c["annotation"], context=c["context"])}
             for c in corpus["scoring_cases"]]
    from qa_agent.quality_eval.assessment_cases import evaluate_cases
    assessments = evaluate_cases(corpus.get('assessment_cases', []))
    return {"protocol": 'qa-development-eval/' + baseline, "split": "development",
            'baseline_commit': frozen['baseline_commit'], 'assessment_cases': assessments,
            "execution_authority": "none", "executable": False,
            "kb": kb, "production": production, "cases_sha256": frozen["cases_sha256"],
            "eval_source": snapshot(package, list((package / "src/qa_agent/quality_eval").glob("*.py"))),
            "retrieval": {"top_k": corpus["top_k"], "query_count": len(rows),
                          "macro_recall": ratio(sum(r["recall"]["value"] for r in answerable), len(answerable)),
                          "mrr": ratio(sum(r["reciprocal_rank"] for r in answerable), len(answerable)),
                          "by_category": {tag: {"count": len(group),
                              "macro_recall": ratio(sum(r["recall"]["value"] for r in group if r["evidence_labels"]), sum(bool(r["evidence_labels"]) for r in group))}
                              for tag in sorted({r["category"] for r in rows})
                              for group in [[r for r in rows if r["category"] == tag]]}, "rows": rows},
            "mock_scoring_only": mocks,
            "refusal": {"status": "not_measured_provider", "denominator": 0},
            "multiturn": {"status": "raw_followup_retrieval_only_no_history_rewrite", "denominator": 2},
            "provider": {"calls": 0, "quality": "not_measured"},
            "holdout": {"status": "not_established", "denominator": 0},
            "human_reviewed_labels": 0, "quality_threshold": None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline frozen lexical development baseline; never loads model configuration")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--baseline', choices=('v1','v2'), default='v1')
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[3], baseline=args.baseline)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
