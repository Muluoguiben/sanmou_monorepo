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

from pioneer_agent.app.cli_utils import user_path
from pioneer_agent.runbook.loader import RUNBOOK_LOAD_ERRORS, load_runbook_or_default
from pioneer_agent.runbook.state_store import RunbookStateStore


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect or confirm runbook human gates.")
    parser.add_argument("command", choices=("show", "confirm"))
    parser.add_argument("phase_id", nargs="?", default=None,
                        help="Phase to confirm (required for confirm).")
    parser.add_argument("--state", type=user_path, default=Path("data/loop/runbook_state.json"),
                        help="Runbook state file used by the loop.")
    parser.add_argument("--runbook-path", type=user_path, default=None,
                        help="Runbook YAML to validate the phase against (default: packaged runbook).")
    args = parser.parse_args(argv)

    store = RunbookStateStore(args.state)

    try:
        runbook = load_runbook_or_default(args.runbook_path)
    except RUNBOOK_LOAD_ERRORS as exc:
        parser.error(f"failed to load runbook: {exc}")
    active_season = runbook.season if runbook is not None else None

    if args.command == "show":
        record = store.load()
        print(f"state file:       {args.state}")
        print(f"confirmations:    {store.confirmations_path}")
        print(f"active season:    {active_season or '(no runbook found)'}")
        print(f"stored season:    {record.season or '(unstamped)'}")
        print(f"current phase:    {record.current_phase_id or '(fresh start)'}")
        print(f"completed:        {record.completed}")
        entries = store.confirmation_entries()
        if not entries and not record.confirmed_gates:
            print("confirmed gates:  (none)")
        else:
            print("confirmed gates:")
            for gate in sorted(record.confirmed_gates - {p for p, _s in entries}):
                print(f"  - {gate} (from state file)")
            for phase_id, season in entries:
                if active_season is not None and season != active_season:
                    label = f"(season: {season or 'unstamped'}) [IGNORED by active season]"
                else:
                    label = f"(season: {season or 'unstamped'})"
                print(f"  - {phase_id} {label}")
        return 0

    if not args.phase_id:
        parser.error("confirm requires a phase_id")

    if runbook is None:
        parser.error(
            "no runbook available to stamp the season — refusing to write an unstamped "
            "confirmation (it would be ignored by the loop); pass --runbook-path"
        )
    try:
        phase = runbook.phase(args.phase_id)
    except KeyError:
        parser.error(
            f"unknown phase {args.phase_id!r}; known: "
            f"{[p.phase_id for p in runbook.phases]}"
        )
    if not phase.human_gate:
        print(f"note: phase {args.phase_id!r} has no human_gate — confirmation is a no-op for it")

    if not args.state.exists():
        print(
            f"warning: state file {args.state} does not exist yet — if the loop runs with a "
            "custom --log-dir/--runbook-state or a different working directory, pass the "
            "matching --state or this confirmation will never be seen"
        )

    record = store.confirm_gate(args.phase_id, season=active_season)
    print(f"confirmed gate:   {args.phase_id} (season: {active_season})")
    print(f"appended to:      {store.confirmations_path}")
    print(f"confirmed gates:  {sorted(record.confirmed_gates)}")
    print("the running loop will pick this up on its next tick")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
