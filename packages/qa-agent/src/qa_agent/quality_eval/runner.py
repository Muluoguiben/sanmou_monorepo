from __future__ import annotations

import argparse
import json
import re
import math
import sys
from pathlib import Path

from qa_agent.quality_eval.scoring import digest, ratio, retrieval_score, score_answer, snapshot
from qa_agent.retrieval.retriever import Retriever


def _nonempty_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _validate_corpus(corpus: object, baseline: str) -> None:
    """Hashes bind bytes, not their suitability as a metric experiment."""
    if not isinstance(corpus, dict):
        raise ValueError('corpus must be an object')
    if type(corpus.get('version')) is not int or corpus['version'] != int(baseline[1:]) or corpus.get('split') != 'development':
        raise ValueError('baseline version/split mismatch')
    if type(corpus.get('top_k')) is not int or corpus['top_k'] <= 0:
        raise ValueError('top_k must be a positive integer')
    if baseline == 'v1' and 'assessment_cases' in corpus:
        raise ValueError('assessment suite requires v2')
    required = ('queries', 'scoring_cases')
    if baseline in {'v2','v3','v4'}:
        required += ('assessment_cases',)
    if baseline in {'v3','v4'}:
        required += ('multiturn_cases',)
    elif 'multiturn_cases' in corpus:
        raise ValueError('multiturn suite requires v3')
    if baseline == 'v4':
        required += ('season_cases',)
    elif 'season_cases' in corpus:
        raise ValueError('season suite requires v4')
    for group in required:
        cases = corpus.get(group)
        if not isinstance(cases, list) or not cases:
            raise ValueError(f'{group} must be a nonempty list')
        ids = []
        for case in cases:
            if not isinstance(case, dict) or not _nonempty_text(case.get('id')):
                raise ValueError('nonempty case ID required')
            ids.append(case['id'])
        if len(set(ids)) != len(ids):
            raise ValueError('duplicate case ID')
    for case in corpus['queries']:
        if case.get('split') != 'development':
            raise ValueError('query split mismatch')
        if not _nonempty_text(case.get('query')) or not _nonempty_text(case.get('category')):
            raise ValueError('query/category required')
        labels = case.get('evidence_labels')
        if not isinstance(labels, list):
            raise ValueError('evidence labels must be a list')
        for label in labels:
            if not isinstance(label, dict) or any(not _nonempty_text(label.get(key)) for key in ('id', 'source_ref', 'facts_sha256')):
                raise ValueError('evidence label identity required')
        if len({label['id'] for label in labels}) != len(labels):
            raise ValueError('duplicate evidence ID')
    for case in corpus['scoring_cases']:
        if (not isinstance(case.get('answer'), str) or not isinstance(case.get('context'), str)
                or not isinstance(case.get('evidence'), dict) or not isinstance(case.get('annotation'), dict)):
            raise ValueError('scoring case answer/context/evidence/annotation required')
    for case in corpus.get('assessment_cases', []):
        if case.get('split') != 'development' or case.get('review_status') != 'developer-authored':
            raise ValueError('assessment provenance/split mismatch')
        if not _nonempty_text(case.get('question')) or not isinstance(case.get('values'), list):
            raise ValueError('assessment question/values required')
        if any(v is not None and (type(v) not in (int, float) or (type(v) is float and not math.isfinite(v)) or v < 0) for v in case['values']):
            raise ValueError('assessment values must be nonnegative finite numbers or null')
        expected = case.get('expected')
        if not isinstance(expected, dict) or set(expected) != {'status', 'check_scope', 'answer_calls'}:
            raise ValueError('assessment expected fields required')
        if (expected['status'] not in ('supported', 'partial', 'conflicting', 'not_found')
                or expected['check_scope'] not in ('scalar_profile', 'unassessed', 'empty')
                or type(expected['answer_calls']) is not int or expected['answer_calls'] not in (0, 1)):
            raise ValueError('invalid assessment expectation')
    for case in corpus.get('multiturn_cases', []):
        if case.get('split')!='development' or case.get('review_status')!='developer-authored':
            raise ValueError('multiturn provenance/split mismatch')
        if not _nonempty_text(case.get('question')) or case.get('scenario') not in (
                'alias_success','no_binding','wrong_citation','raw_miss','single_use',
                'source_withdrawal','new_conflict','history_replace','notes_partial'):
            raise ValueError('invalid multiturn scenario/question')
        expected=case.get('expected')
        if not isinstance(expected,dict) or set(expected)!={'resolution','answer_calls','rewrite_calls','assessment_status'}:
            raise ValueError('multiturn expectation required')
        if (expected['resolution'] not in ('resolved','clarify','raw_not_found')
                or expected['assessment_status'] not in ('supported','partial','conflicting','not_found')
                or any(type(expected[key]) is not int or expected[key] not in (0,1) for key in ('answer_calls','rewrite_calls'))):
            raise ValueError('invalid multiturn expectation')


def _validate_execution_roots(package: Path) -> None:
    """Reject mixed QA import trees, including dependencies loaded lazily.

    This is a local module-origin restriction, not a signature or protection
    against deliberate in-process monkeypatching of executable objects.
    """
    source = package.resolve() / 'src'
    for name, module in tuple(sys.modules.items()):
        if name != 'qa_agent' and not name.startswith('qa_agent.'):
            continue
        if module is None:
            raise ValueError(f'QA execution source mismatch: {name}')
        relative = source.joinpath(*name.split('.'))
        expected = relative / '__init__.py' if hasattr(module, '__path__') else relative.with_suffix('.py')
        actual = getattr(module, '__file__', None)
        origin = getattr(getattr(module, '__spec__', None), 'origin', None)
        if not actual or Path(actual).resolve() != expected.resolve() or not origin or Path(origin).resolve() != expected.resolve():
            raise ValueError(f'QA execution source mismatch: {name}')
        if hasattr(module, '__path__') and [Path(p).resolve() for p in module.__path__] != [relative.resolve()]:
            raise ValueError(f'QA package search path mismatch: {name}')


def run(package: Path, *, baseline: str = 'v1') -> dict:
    if baseline not in {'v1', 'v2', 'v3', 'v4'}:
        raise ValueError('unsupported baseline version')
    if package.resolve() != Path(__file__).resolve().parents[3]:
        raise ValueError('loaded evaluator/package source mismatch')
    fixtures = package / 'tests/fixtures/quality_eval' / baseline
    corpus = json.loads((fixtures / "cases.json").read_text(encoding="utf-8-sig"))
    frozen = json.loads((fixtures / "freeze.json").read_text(encoding="utf-8-sig"))
    if not isinstance(frozen, dict) or not isinstance(frozen.get('baseline_commit'), str) or not re.fullmatch(r'[0-9a-f]{40}', frozen['baseline_commit']):
        raise ValueError('invalid source commit binding')
    _validate_corpus(corpus, baseline)
    kb = snapshot(package, list((package / "knowledge_sources").rglob("*.yaml")))
    production = snapshot(package, [p for p in (package / "src/qa_agent").rglob("*.py")
                                    if "quality_eval" not in p.parts])
    if kb != frozen["kb"] or production != frozen["production"]:
        raise ValueError("frozen KB/production source drift; create a reviewed new baseline version")
    if digest((fixtures / "cases.json").read_text(encoding="utf-8-sig")) != frozen["cases_sha256"]:
        raise ValueError("query/label fixture drift")
    # Import gate dependencies before checking their actual origins. Checking
    # only this runner is insufficient when it is loaded via importlib.
    from qa_agent.quality_eval.assessment_cases import evaluate_cases
    from qa_agent.quality_eval.referent_cases import evaluate_referent_cases
    if baseline == 'v4':
        from qa_agent.quality_eval.season_cases import evaluate_season_cases, validate_cases
    _validate_execution_roots(package)
    if baseline == 'v4':
        validate_cases(corpus['season_cases'])
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
    assessments = evaluate_cases(corpus.get('assessment_cases', []))
    referents = evaluate_referent_cases(corpus.get('multiturn_cases', []))
    season = evaluate_season_cases(corpus['season_cases']) if baseline == 'v4' else None
    _validate_execution_roots(package)
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
            "multiturn": ({"status":"developer-authored-fake-client-controls", "denominator":len(referents),
                           "passed":len(referents),"cases":referents} if baseline in {'v3','v4'} else
                          {"status": "raw_followup_retrieval_only_no_history_rewrite", "denominator": 2}),
            "provider": {"calls": 0, "quality": "not_measured"},
            "holdout": {"status": "not_established", "denominator": 0},
            "human_reviewed_labels": 0, "quality_threshold": None,
            **({'season': season} if baseline == 'v4' else {})}


def main() -> None:
    parser = argparse.ArgumentParser(description="Offline frozen lexical development baseline; never loads model configuration")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument('--baseline', choices=('v1','v2','v3','v4'), default='v1')
    args = parser.parse_args()
    result = run(Path(__file__).resolve().parents[3], baseline=args.baseline)
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    if args.baseline == 'v4' and not result['season']['gate_pass']:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
