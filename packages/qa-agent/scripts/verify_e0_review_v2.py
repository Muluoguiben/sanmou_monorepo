"""Verify the explicit v5 development source and v2 review-preparation manifest.

No material generation, model configuration, network, approval or publication.
The original prepare_e0_review.py and all v1-v4 fixtures remain historical inputs.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


SCRIPT = Path(__file__).resolve()
PACKAGE = SCRIPT.parents[1]
FIXTURES = PACKAGE / "tests/fixtures/quality_eval"
FREEZE = FIXTURES / "e0_review_prep_v2/freeze.json"
PROTOCOL = "qa-e0-review-prep/v2"


def _json(path: Path) -> dict:
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=unique)


def _pretty(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def _legacy_module():
    path = SCRIPT.with_name("prepare_e0_review.py")
    spec = importlib.util.spec_from_file_location("prepare_e0_review_v1_reference", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inputs() -> list[Path]:
    return [SCRIPT, SCRIPT.with_name("prepare_e0_review.py"),
            *(PACKAGE / "src/qa_agent").rglob("*.py"),
            *(PACKAGE / "knowledge_sources").rglob("*.yaml"),
            *(FIXTURES / "v5").glob("*.json"),
            *(FIXTURES / "v4").glob("*.json"),
            *(FIXTURES / "claim_spans_v1").glob("*.json"),
            FIXTURES / "e0_review_prep_v1/freeze.json"]


def build_verification_report() -> dict:
    """Compute a source-bound report; freeze acceptance is done only by verify()."""
    from qa_agent.quality_eval import claim_spans, runner
    from qa_agent.quality_eval.scoring import digest, snapshot

    legacy = _legacy_module()
    for path in _inputs():
        legacy._no_links(path, PACKAGE)
    before = snapshot(PACKAGE, _inputs())
    old = _json(FIXTURES / "e0_review_prep_v1/freeze.json")
    old_inputs = [FIXTURES / group / filename for group in ("v4", "claim_spans_v1")
                  for filename in ("cases.json", "freeze.json")]
    if snapshot(PACKAGE, old_inputs) != old["upstream_files"]:
        raise ValueError("legacy frozen fixtures changed")
    if digest(legacy.SCRIPT.read_text(encoding="utf-8-sig")) != old["script_sha256"]:
        raise ValueError("legacy review preparation script changed")

    current = runner.run(PACKAGE, baseline="v5")
    spans = claim_spans.run(PACKAGE, baseline="claim-spans-v1")
    corpus = _json(FIXTURES / "v5/cases.json")
    previous_corpus = _json(FIXTURES / "v4/cases.json")
    if {**previous_corpus, "version": 5} != corpus:
        raise ValueError("v5 must preserve all v4 cases and labels")
    if (not current["season"]["gate_pass"] or not spans["gate_pass"]
            or current["human_reviewed_labels"] != 0 or current["provider"]["calls"] != 0
            or current["holdout"]["status"] != "not_established" or current["quality_threshold"] is not None
            or spans["provider"]["calls"] != 0 or spans["human_review"]["labels"] != 0):
        raise ValueError("development control or review identity mismatch")
    report = {
        "protocol": PROTOCOL, "baseline": "v5", "split": "review_queue",
        "v5": {"baseline_commit": current["baseline_commit"], "kb": current["kb"],
               "production": current["production"], "cases_sha256": current["cases_sha256"],
               "counts": {key: len(corpus[key]) for key in
                          ("queries", "scoring_cases", "assessment_cases", "multiturn_cases", "season_cases")},
               "report_sha256": digest(_pretty(current))},
        "claim_spans": {"controls": spans["controls"], "fixture": spans["fixture"],
                        "report_sha256": digest(_pretty(spans)), "synthetic": True,
                        "label_origin": "developer-authored"},
        "source_manifest": before,
        "eval_source": current["eval_source"],
        "metrics": legacy.METRICS,
        "provider_calls": 0, "human_reviewed_labels": 0, "human_gold": False,
        "independent_holdout": False, "quality_threshold": None,
        "execution_authority": "none", "executable": False,
        "material_generation": "not_available_in_v2_verifier; existing user materials unchanged",
    }
    runner._validate_execution_roots(PACKAGE)
    if snapshot(PACKAGE, _inputs()) != before:
        raise ValueError("source drift during review verification")
    return report


def verify() -> dict:
    from qa_agent.quality_eval.scoring import snapshot
    legacy = _legacy_module()
    legacy._no_links(FREEZE, PACKAGE)
    before = snapshot(PACKAGE, [FREEZE])
    expected = _json(FREEZE)
    report = build_verification_report()
    if report != expected or snapshot(PACKAGE, [FREEZE]) != before:
        raise ValueError("review preparation v2 manifest mismatch")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    try:
        report = verify()
    except (ValueError, OSError, KeyError, TypeError) as error:
        parser.exit(1, f"review preparation v2 failed: {error}\n")
    print(_pretty(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
