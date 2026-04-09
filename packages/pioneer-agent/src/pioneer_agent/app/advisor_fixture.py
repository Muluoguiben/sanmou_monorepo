from __future__ import annotations

import argparse
import json
from pathlib import Path

from pioneer_agent.core.runtime_state_io import load_runtime_state_record, write_runtime_state_fixture
from pioneer_agent.runtime.replay_runtime import ReplayRuntime


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Print advisor summaries for one or more runtime state fixtures.")
    parser.add_argument(
        "--fixture",
        action="append",
        default=[],
        help="Fixture path to summarize. Repeat the flag to inspect multiple fixtures.",
    )
    parser.add_argument(
        "--from-log",
        default="",
        help="Optional state.jsonl path. When provided, summarize the selected record from this log.",
    )
    parser.add_argument(
        "--index",
        type=int,
        default=-1,
        help="Record index used with --from-log. Use -1 for the latest line.",
    )
    parser.add_argument(
        "--write-fixture",
        default="",
        help="Optional output path. When used with --from-log, also export the selected state as a fixture.",
    )
    return parser


def _resolve_path(project_root: Path, value: str) -> Path:
    candidate = Path(value)
    if candidate.is_absolute():
        return candidate
    return (project_root / candidate).resolve()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    runtime = ReplayRuntime()

    if args.from_log:
        log_path = _resolve_path(project_root, args.from_log)
        record = load_runtime_state_record(log_path, args.index)
        if args.write_fixture:
            write_runtime_state_fixture(record.state, _resolve_path(project_root, args.write_fixture))
        inputs = [(f"{log_path}::record[{record.record_index if record.record_index is not None else 0}]", record.state)]
    else:
        if args.fixture:
            fixture_paths = [_resolve_path(project_root, value) for value in args.fixture]
        else:
            fixture_dir = project_root / "tests" / "fixtures"
            fixture_paths = [path for path in sorted(fixture_dir.glob("*.json")) if not path.name.startswith("template_")]
        inputs = [(str(fixture_path), load_runtime_state_record(fixture_path).state) for fixture_path in fixture_paths]

    for fixture_label, state in inputs:
        result = runtime.run_state(state, fixture_label)
        selected_action = result["selected_action"]
        pipeline = result["selection_reason"].get("pipeline", {})
        rejected = result["selection_reason"].get("rejected_candidates", [])
        triggered_rules = result["selection_reason"].get("triggered_rules", [])
        derived_main_lineup = result["derived_state"]["main_lineup"]

        print(f"=== Advisor Summary: {fixture_label} ===")
        print(
            "phase_tag:"
            f" {result['derived_state']['phase_tag']} | "
            f"primary_constraint: {derived_main_lineup.get('primary_constraint', 'unknown')} | "
            f"readiness: {derived_main_lineup.get('combat_readiness_score', 0)}"
        )
        if selected_action:
            print(f"selected_action: {selected_action['action_type']} score={selected_action['score_total']:.2f}")
        else:
            print("selected_action: none")
        print(
            f"selection_mode: {result['selection_reason'].get('selection_mode', 'unknown')}"
            f" | triggered_rules: {', '.join(triggered_rules) if triggered_rules else 'none'}"
            f" | top_score_gap: {result['selection_reason'].get('top_score_gap', 'n/a')}"
        )
        print(f"advisor_summary: {result['selection_reason'].get('summary', '')}")
        print(
            "pipeline:"
            f" generated={pipeline.get('generated', 0)}"
            f" viable={pipeline.get('viable', 0)}"
            f" rejected={pipeline.get('rejected', 0)}"
        )
        print("top_candidates:")
        for idx, action in enumerate(result["ranked_actions"][:5], start=1):
            top_factors = ", ".join(
                f"{key}={value:.2f}"
                for key, value in sorted(
                    action["score_breakdown"].items(),
                    key=lambda item: abs(item[1]),
                    reverse=True,
                )[:3]
            )
            print(
                f"  {idx}. {action['action_type']} score={action['score_total']:.2f} "
                f"params={json.dumps(action['params'], ensure_ascii=False)} "
                f"key_factors=[{top_factors}]"
            )
        if rejected:
            print("rejected_candidates:")
            for item in rejected[:3]:
                print(
                    f"  - {item['action_type']} reason={item['reason']} "
                    f"params={json.dumps(item['params'], ensure_ascii=False)}"
                )
        print("derived_state:")
        print(json.dumps(result["derived_state"], ensure_ascii=False, indent=2))
        print()


if __name__ == "__main__":
    main()
