"""External-only scorer for Record & Replay holdout submissions.

Run this module in the evaluator environment that owns the sealed oracle and
private signing key.  It emits only aggregate metrics and a signed attestation;
the ordinary Record & Replay CLI intentionally has no oracle argument.
"""
from __future__ import annotations

import argparse
import json

from pioneer_agent.app.cli_utils import user_path
from pioneer_agent.record_replay.holdout_eval import (
    score_holdout_submission_external,
    write_attestation_once,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Score one frozen holdout submission in an external evaluator."
    )
    parser.add_argument("submission", type=user_path)
    parser.add_argument("--oracle", type=user_path, required=True)
    parser.add_argument("--trust-policy", type=user_path, required=True)
    parser.add_argument("--private-key", type=user_path, required=True)
    parser.add_argument("--catalog", type=user_path, required=True)
    parser.add_argument("--registries-root", type=user_path, required=True)
    parser.add_argument("--sessions-root", type=user_path, required=True)
    parser.add_argument("--reviews-root", type=user_path, required=True)
    parser.add_argument("--artifacts-root", type=user_path, required=True)
    parser.add_argument("--evaluator-state-root", type=user_path, required=True)
    parser.add_argument("--attestation-id", required=True)
    parser.add_argument("--attestation-out", type=user_path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        attestation = score_holdout_submission_external(
            submission_path=args.submission,
            oracle_path=args.oracle,
            trust_policy_path=args.trust_policy,
            private_key_path=args.private_key,
            catalog_path=args.catalog,
            registries_root=args.registries_root,
            sessions_root=args.sessions_root,
            reviews_root=args.reviews_root,
            artifacts_root=args.artifacts_root,
            evaluator_state_root=args.evaluator_state_root,
            attestation_id=args.attestation_id,
        )
        write_attestation_once(args.attestation_out, attestation)
        payload = attestation.payload
        _print_json(
            {
                "status": "completed",
                "attestation_id": payload.attestation_id,
                "submission_sha256": payload.submission_sha256,
                "holdout_session_count": payload.holdout_session_count,
                "exact_match_count": payload.exact_match_count,
                "unknown_prediction_count": payload.unknown_prediction_count,
                "accuracy_ppm": payload.accuracy_ppm,
                "passed_policy": payload.passed_policy,
                "oracle_labels_disclosed": False,
                "execution_authority": "none",
                "live_dispatch_allowed": False,
                "independent_eval_ready": False,
            }
        )
        return 0
    except (OSError, RuntimeError, ValueError) as exc:
        _print_json({"status": "failed", "error": str(exc)})
        return 2


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
