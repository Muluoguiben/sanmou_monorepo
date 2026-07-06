"""Quick summary of a `loop.jsonl` trace — handy for diagnosing loop runs.

Usage:
  PYTHONPATH=src python3 -m pioneer_agent.app.loop_inspect data/loop/loop.jsonl
  PYTHONPATH=src python3 -m pioneer_agent.app.loop_inspect data/loop/loop.jsonl --tail 10
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarize an autonomous loop trace.")
    parser.add_argument("jsonl", type=Path, help="Path to loop.jsonl.")
    parser.add_argument("--tail", type=int, default=5, help="Show the last N tick records.")
    args = parser.parse_args(argv)

    records = [json.loads(line) for line in args.jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not records:
        print("(empty trace)")
        return 0

    page_counts = Counter(r.get("page_type") or "(none)" for r in records)
    action_counts = Counter(r.get("selected_action_type") or "(idle)" for r in records)
    exec_counts = Counter(r.get("execution_status") or "(none)" for r in records)

    total_elapsed = sum(r.get("elapsed_s") or 0.0 for r in records)
    total_sleep = sum(r.get("sleep_s") or 0.0 for r in records)

    print(f"total ticks: {len(records)}")
    print(f"total tick elapsed: {total_elapsed:.1f}s | total sleep: {total_sleep:.1f}s")
    print(f"page_type:          {dict(page_counts)}")
    print(f"selected_action:    {dict(action_counts)}")
    print(f"execution_status:   {dict(exec_counts)}")

    if any(r.get("runbook_phase") for r in records):
        phase_counts = Counter(r.get("runbook_phase") or "(none)" for r in records)
        hold_counts = Counter(
            r["runbook_hold_reason"] for r in records if r.get("runbook_hold_reason")
        )
        escalation_counts = Counter(
            kind for r in records for kind in r.get("runbook_escalations") or []
        )
        current_phase = next(
            (r["runbook_phase"] for r in reversed(records) if r.get("runbook_phase")), None
        )
        print(f"runbook phase:      {dict(phase_counts)} | current={current_phase}")
        print(f"runbook holds:      {dict(hold_counts) or '(none)'}")
        print(f"runbook escalation: {dict(escalation_counts) or '(none)'}")

    print(f"\nlast {args.tail} ticks:")
    for r in records[-args.tail:]:
        shot = Path(r["screenshot_path"]).name if r.get("screenshot_path") else "-"
        print(
            f"  #{r['iteration']:>4} {r['started_at']} page={r.get('page_type') or '-':<10} "
            f"action={r.get('selected_action_type') or '-':<30} "
            f"exec={r.get('execution_status') or '-':<9} sleep={r.get('sleep_s')}s shot={shot}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
