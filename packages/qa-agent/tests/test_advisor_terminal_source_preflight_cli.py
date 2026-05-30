import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from qa_agent.app.advisor_terminal_source_preflight import main


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class AdvisorTerminalSourcePreflightCliTests(unittest.TestCase):
    def test_cli_outputs_ready_payload_and_manifest_patch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            screenshot_path = temp_root / "claim-terminal.png"
            screenshot_path.write_bytes(b"terminal screenshot")
            trace_path = temp_root / "claim-terminal.jsonl"
            trace_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace-claim-cli",
                        "screenshot": {"path": str(screenshot_path)},
                        "selected_action": {"action_type": "claim_chapter_reward"},
                        "execution": {
                            "status": "ok",
                            "summary": {
                                "target_key": "chapter_claim_button",
                                "terminal_for_verifier": True,
                            },
                        },
                        "verification": {
                            "post_action_verifier": {
                                "action_type": "claim_chapter_reward",
                                "status": "verified",
                                "checked": ["progress.chapter_claimable"],
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence = {
                "source_kind": "live_trace_fixture",
                "review_status": "reviewed",
                "reviewed_by": "qa-reviewer",
                "reviewed_at": "2026-05-30T18:20:00+08:00",
                "screenshot": str(screenshot_path),
                "screenshot_sha256": _sha256(screenshot_path),
                "trace": str(trace_path),
                "trace_sha256": _sha256(trace_path),
                "page": "chapter",
                "semantic_target": "progress.chapter_claim_button",
                "runtime_dispatch": {
                    "status": "ok",
                    "target_key": "chapter_claim_button",
                    "terminal_for_verifier": True,
                },
                "post_action_delta": [
                    {"path": "progress.chapter_claimable", "value": False},
                ],
                "post_action_delta_evidence": {
                    "source": "verification_record",
                    "post_action_delta": [
                        {"path": "progress.chapter_claimable", "value": False},
                    ],
                    "supporting_refs": [
                        "terminal_source_evidence.trace",
                        "terminal_source_evidence.verification_record",
                        "operator_confirmation.trace_id",
                    ],
                },
                "verification_record": {
                    "action_type": "claim_chapter_reward",
                    "status": "verified",
                    "checked": ["progress.chapter_claimable"],
                },
                "operator_confirmation": {
                    "confirmed": True,
                    "action_type": "claim_chapter_reward",
                    "scope": "final_mutating_click",
                    "requires_operator_confirmation": True,
                    "confirmed_at": "2026-05-30T17:45:00+08:00",
                    "trace_id": "trace-claim-cli",
                    "trace_record_index": 0,
                    "runtime_dispatch": {
                        "status": "ok",
                        "target_key": "chapter_claim_button",
                        "terminal_for_verifier": True,
                    },
                },
            }
            evidence_path = temp_root / "evidence.json"
            evidence_path.write_text(
                json.dumps(evidence, ensure_ascii=False),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--action-type",
                        "claim_chapter_reward",
                        "--evidence-json",
                        str(evidence_path),
                        "--fixture",
                        "live_claim_terminal_trace.json",
                    ]
                )
            payload = json.loads(stdout.getvalue())

            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ready"])
            self.assertTrue(payload["accepted_for_closure"])
            self.assertEqual(payload["review"]["missing_evidence"], [])
            manifest_patch = payload["suggested_advisor_fixture_expectation_patch"][
                "live_claim_terminal_trace.json"
            ]
            self.assertEqual(
                manifest_patch["expected_dispatch_target_key"],
                "chapter_claim_button",
            )
            self.assertEqual(
                manifest_patch["terminal_source_evidence"]["trace_sha256"],
                _sha256(trace_path),
            )

    def test_cli_returns_nonzero_when_evidence_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            evidence_path = temp_root / "evidence.json"
            evidence_path.write_text(
                json.dumps(
                    {
                        "source_kind": "live_trace_fixture",
                        "review_status": "reviewed",
                        "page": "chapter",
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--action-type",
                        "claim_chapter_reward",
                        "--evidence-json",
                        str(evidence_path),
                    ]
                )
            payload = json.loads(stdout.getvalue())

            self.assertEqual(exit_code, 2)
            self.assertFalse(payload["ready"])
            self.assertIn("review_metadata", payload["review"]["missing_evidence"])
            self.assertIn("trace", payload["review"]["missing_evidence"])


if __name__ == "__main__":
    unittest.main()
