"""Batch regression runner for the chat layer.

Runs each question in tests/fixtures/chat_regression_questions.yaml against
the live Gemini API and prints PASS/FAIL per check. Does NOT import unittest
because we don't want this in the default test sweep (API cost + flakiness).

Usage:
    cd packages/qa-agent
    PYTHONPATH=src python3 scripts/chat_regression.py
    PYTHONPATH=src python3 scripts/chat_regression.py --only q15,q16
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qa_agent.chat.agent import ChatAgent  # noqa: E402


@dataclass
class CheckResult:
    name: str
    passed: bool
    detail: str = ""


@dataclass
class QuestionResult:
    id: str
    question: str
    answer: str
    evidence_ids: list[str]
    checks: list[CheckResult]

    @property
    def all_passed(self) -> bool:
        return all(c.passed for c in self.checks)


def _load_questions(path: Path) -> list[dict]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _check_reply(reply, spec: dict) -> list[CheckResult]:
    evidence_ids = [c.entry.id for c in reply.evidence]
    checks: list[CheckResult] = []

    if spec.get("must_not_fabricate"):
        answer_lower = reply.answer.lower()
        says_not_found = "未收录" in reply.answer or "暂未" in reply.answer
        no_fab_fluff = not any(
            marker in answer_lower
            for marker in ["建议", "followup", "相关主题"]
        )
        checks.append(CheckResult(
            "not_found_graceful",
            says_not_found and no_fab_fluff,
            f"answer={reply.answer[:120]!r}",
        ))
        return checks

    must_cite = spec.get("must_cite", [])
    if must_cite:
        cited = [eid for eid in must_cite if eid in evidence_ids or eid in reply.answer]
        checks.append(CheckResult(
            "must_cite",
            bool(cited),
            f"expected any of {must_cite}, evidence={evidence_ids}",
        ))

    contains_any = spec.get("contains_any", [])
    if contains_any:
        hits = [s for s in contains_any if s in reply.answer]
        checks.append(CheckResult(
            "contains_any",
            bool(hits),
            f"expected any of {contains_any}, got hits={hits}",
        ))

    must_not_contain = spec.get("must_not_contain", [])
    if must_not_contain:
        leaks = [s for s in must_not_contain if s in reply.answer]
        checks.append(CheckResult(
            "must_not_contain",
            not leaks,
            f"unexpected leaks={leaks}" if leaks else "",
        ))

    return checks


def _run_one(agent: ChatAgent, spec: dict) -> QuestionResult:
    agent.reset()
    reply = agent.ask(spec["question"])
    return QuestionResult(
        id=spec["id"],
        question=spec["question"],
        answer=reply.answer,
        evidence_ids=[c.entry.id for c in reply.evidence],
        checks=_check_reply(reply, spec),
    )


def _run_conversation(agent: ChatAgent, spec: dict, pace: float) -> QuestionResult:
    agent.reset()
    all_checks: list[CheckResult] = []
    last_reply = None
    last_ids: list[str] = []
    for i, turn in enumerate(spec["turns"]):
        if i > 0 and pace > 0:
            time.sleep(pace)
        last_reply = agent.ask(turn["question"])
        last_ids = [c.entry.id for c in last_reply.evidence]
        turn_checks = _check_reply(last_reply, turn)
        for check in turn_checks:
            check.name = f"turn{i+1}.{check.name}"
        all_checks.extend(turn_checks)
    return QuestionResult(
        id=spec["id"],
        question=spec["turns"][-1]["question"] if spec.get("turns") else "",
        answer=last_reply.answer if last_reply else "",
        evidence_ids=last_ids,
        checks=all_checks,
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--fixtures",
        default="tests/fixtures/chat_regression_questions.yaml",
    )
    parser.add_argument(
        "--conversations",
        default="tests/fixtures/chat_regression_conversations.yaml",
        help="Multi-turn fixture file (skipped if missing).",
    )
    parser.add_argument(
        "--skip-single",
        action="store_true",
        help="Skip single-question fixture.",
    )
    parser.add_argument(
        "--skip-conversations",
        action="store_true",
        help="Skip multi-turn fixture.",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated id prefixes to include (e.g. 'q15,q16').",
    )
    parser.add_argument("--verbose", action="store_true")
    parser.add_argument(
        "--pace",
        type=float,
        default=13.0,
        help="Seconds to wait between questions (stay under free-tier 5 req/min).",
    )
    args = parser.parse_args()

    package_root = Path(__file__).resolve().parents[1]

    single_specs: list[dict] = []
    conv_specs: list[dict] = []

    if not args.skip_single:
        single_specs = _load_questions(package_root / args.fixtures)

    if not args.skip_conversations:
        conv_path = package_root / args.conversations
        if conv_path.exists():
            conv_specs = _load_questions(conv_path)

    if args.only:
        prefixes = [p.strip() for p in args.only.split(",") if p.strip()]
        single_specs = [s for s in single_specs if any(s["id"].startswith(p) for p in prefixes)]
        conv_specs = [s for s in conv_specs if any(s["id"].startswith(p) for p in prefixes)]

    agent = ChatAgent.from_knowledge_dir(package_root / "knowledge_sources")

    passed = 0
    failed: list[QuestionResult] = []
    api_call_idx = 0

    def _handle(result: QuestionResult, label: str) -> None:
        nonlocal passed
        status = "PASS" if result.all_passed else "FAIL"
        print(f"[{status}] {result.id}  {label[:80]}")
        for check in result.checks:
            mark = "✓" if check.passed else "✗"
            print(f"    {mark} {check.name}: {check.detail}")
        if args.verbose or not result.all_passed:
            print(f"    evidence: {result.evidence_ids}")
            print(f"    answer:   {result.answer[:200]}")
        if result.all_passed:
            passed += 1
        else:
            failed.append(result)

    for spec in single_specs:
        if api_call_idx > 0 and args.pace > 0:
            time.sleep(args.pace)
        api_call_idx += 1
        result = _run_one(agent, spec)
        _handle(result, spec["question"])

    for spec in conv_specs:
        if api_call_idx > 0 and args.pace > 0:
            time.sleep(args.pace)
        api_call_idx += len(spec.get("turns", []))
        result = _run_conversation(agent, spec, pace=args.pace)
        _handle(result, spec.get("description", spec["id"]))

    total = len(single_specs) + len(conv_specs)
    print(f"\n=== {passed}/{total} passed ===")
    if failed:
        print(f"failed: {[r.id for r in failed]}")
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
