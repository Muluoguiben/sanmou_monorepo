"""Operator channel for runbook human gates.

The autonomous loop holds before a human_gate phase (二拖一 / 远征) and emits a
HUMAN_GATE escalation. Confirm it here; the running loop picks the approval up
on its next tick without a restart.

Usage:
  PYTHONPATH=src python3 -m pioneer_agent.app.runbook_gate show \
      --state data/loop/runbook_state.json
  PYTHONPATH=src python3 -m pioneer_agent.app.runbook_gate confirm er_tuo_yi \
      --state data/loop/runbook_state.json
"""
from __future__ import annotations

import argparse
from pathlib import Path

from pioneer_agent.runbook.loader import load_default_opening_runbook, load_runbook
from pioneer_agent.runbook.state_store import RunbookStateStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or confirm runbook human gates.")
    parser.add_argument("command", choices=("show", "confirm"))
    parser.add_argument("phase_id", nargs="?", default=None,
                        help="Phase to confirm (required for confirm).")
    parser.add_argument("--state", type=Path, default=Path("data/loop/runbook_state.json"),
                        help="Runbook state file used by the loop.")
    parser.add_argument("--runbook-path", type=Path, default=None,
                        help="Runbook YAML to validate the phase against (default: packaged runbook).")
    args = parser.parse_args(argv)

    store = RunbookStateStore(args.state)
    record = store.load()

    if args.command == "show":
        print(f"state file:       {args.state}")
        print(f"current phase:    {record.current_phase_id or '(fresh start)'}")
        print(f"confirmed gates:  {sorted(record.confirmed_gates) or '(none)'}")
        return 0

    if not args.phase_id:
        parser.error("confirm requires a phase_id")

    runbook = (
        load_runbook(args.runbook_path)
        if args.runbook_path is not None
        else load_default_opening_runbook()
    )
    if runbook is not None:
        try:
            phase = runbook.phase(args.phase_id)
        except KeyError:
            parser.error(
                f"unknown phase {args.phase_id!r}; known: "
                f"{[p.phase_id for p in runbook.phases]}"
            )
        if not phase.human_gate:
            print(f"note: phase {args.phase_id!r} has no human_gate — confirmation is a no-op for it")

    record = store.confirm_gate(args.phase_id)
    print(f"confirmed gate:   {args.phase_id}")
    print(f"confirmed gates:  {sorted(record.confirmed_gates)}")
    print("the running loop will pick this up on its next tick")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
