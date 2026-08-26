"""CLI for replaying the checked-in, static MCP evaluation battery."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from pioneer_agent.mcp_eval.runner import run_battery, write_run_artifacts
from pioneer_agent.mcp_eval.source_bindings import RecordReplayCorpusPaths


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run static read-only sanmou-game MCP scenarios."
    )
    parser.add_argument("--battery", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--repo-sha", required=True)
    parser.add_argument("--model-provider", default="static-fixture")
    parser.add_argument("--model-id", default="static-tool-calls-v1")
    parser.add_argument("--random-seed", type=int, default=0)
    parser.add_argument("--golden-expectations", type=Path, default=None)
    parser.add_argument("--golden-fixture-root", type=Path, default=None)
    parser.add_argument("--record-replay-catalog", type=Path, default=None)
    parser.add_argument("--record-replay-registries-root", type=Path, default=None)
    parser.add_argument("--record-replay-sessions-root", type=Path, default=None)
    parser.add_argument("--record-replay-reviews-root", type=Path, default=None)
    parser.add_argument("--record-replay-artifacts-root", type=Path, default=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    record_replay = _record_replay_paths(args)
    result = run_battery(
        args.battery,
        repo_sha=args.repo_sha,
        model_provider=args.model_provider,
        model_id=args.model_id,
        random_seed=args.random_seed,
        golden_expectations=args.golden_expectations,
        golden_fixture_root=args.golden_fixture_root,
        record_replay=record_replay,
    )
    manifest_path, report_path = write_run_artifacts(args.output_dir, result)
    print(
        json.dumps(
            {
                "status": "completed",
                "run_id": result.run_manifest.run_id,
                "scenario_count": result.aggregate.scenario_count,
                "scored_generation_count": result.aggregate.scored_generation_count,
                "unscored_holdout_count": result.aggregate.unscored_holdout_count,
                "run_manifest": str(manifest_path),
                "metrics_report": str(report_path),
                "execution_authority": "none",
                "live_control_used": False,
                "holdout_oracle_accessed": False,
                "source_bindings": result.run_manifest.source_bindings.model_dump(
                    mode="json"
                ),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


def _record_replay_paths(args: argparse.Namespace) -> RecordReplayCorpusPaths | None:
    values = (
        args.record_replay_catalog,
        args.record_replay_registries_root,
        args.record_replay_sessions_root,
        args.record_replay_reviews_root,
        args.record_replay_artifacts_root,
    )
    if all(value is None for value in values):
        return None
    if any(value is None for value in values):
        raise ValueError("all Record & Replay corpus paths must be provided together")
    return RecordReplayCorpusPaths(
        catalog=args.record_replay_catalog,
        registries_root=args.record_replay_registries_root,
        sessions_root=args.record_replay_sessions_root,
        reviews_root=args.record_replay_reviews_root,
        artifacts_root=args.record_replay_artifacts_root,
    )


if __name__ == "__main__":
    raise SystemExit(main())
