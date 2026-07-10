import contextlib
import base64
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from qa_agent.app.advisor_terminal_source_preflight import main


_VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

_FULL_FRAME_BBOX = {
    "x_min": 0,
    "y_min": 0,
    "x_max": 1000,
    "y_max": 1000,
}


def _semantic_frame_guard(target_key: str) -> dict:
    return {
        "schema_version": 1,
        "algorithm": "semantic-roi-rgb24-sha256-v1",
        "semantic_target_key": target_key,
        "frame_size": [1, 1],
        "normalized_bbox": {key: float(value) for key, value in _FULL_FRAME_BBOX.items()},
        "roi_bbox": {"x": 0, "y": 0, "width": 1, "height": 1},
        "click_point": {"x": 0, "y": 0},
        # _VALID_PNG decodes to one black RGB pixel.
        "roi_sha256": hashlib.sha256(b"\x00\x00\x00").hexdigest(),
    }


def _selected_action_params(action_type: str, target_identity: dict) -> dict:
    button = {
        "visible": True,
        "enabled": True,
        "bbox": dict(_FULL_FRAME_BBOX),
    }
    if action_type == "claim_chapter_reward":
        return {**target_identity, "claim_button": button}
    if action_type == "recruit_soldiers":
        return {**target_identity, "recruit_button": button}
    if action_type == "upgrade_building":
        return {
            **target_identity,
            "upgrade_dialog": {
                "visible": True,
                "confirm_button": button,
            },
        }
    raise AssertionError(action_type)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _privacy_review(**overrides: object) -> dict[str, object]:
    review: dict[str, object] = {
        "status": "approved",
        "reviewed_by": "privacy-reviewer",
        "reviewed_at": "2026-05-30T18:21:00+08:00",
        "screenshot_scope": "terminal_ui_only",
        "redaction_applied": False,
        "contains_account_identifier": False,
        "contains_chat_or_social_text": False,
        "contains_payment_or_secret": False,
        "approved_for_repo_storage": True,
    }
    review.update(overrides)
    return review


def _target_and_delta(action_type: str) -> tuple[dict, dict]:
    if action_type == "claim_chapter_reward":
        return (
            {"chapter_id": 17},
            {
                "path": "progress.chapter_claimable",
                "operator": "changes_to",
                "before": True,
                "after": False,
            },
        )
    if action_type == "recruit_soldiers":
        return (
            {"team_id": "guard-1"},
            {
                "selector": {
                    "collection_path": "teams",
                    "identity_field": "team_id",
                    "identity_value": "guard-1",
                },
                "path": "soldiers",
                "operator": "greater_than_before",
                "before": 22000,
                "after": 23000,
            },
        )
    if action_type == "upgrade_building":
        return (
            {
                "building_name": "Main Hall",
                "current_level": 10,
                "target_level": 11,
            },
            {
                "selector": {
                    "collection_path": "city.buildings",
                    "identity_field": "name",
                    "identity_value": "Main Hall",
                },
                "path": "level",
                "operator": "increases_to",
                "before": 10,
                "after": 11,
            },
        )
    raise AssertionError(action_type)


def _ready_live_evidence(
    root: Path,
    *,
    action_type: str,
    page: str,
    semantic_target: str,
    target_key: str,
) -> dict:
    screenshot_path = root / f"{action_type}.png"
    screenshot_path.write_bytes(_VALID_PNG)
    trace_path = root / f"{action_type}.jsonl"
    trace_id = f"trace-{action_type}"
    action_id = f"action-{action_type}"
    target_identity, delta = _target_and_delta(action_type)
    delta_items = [delta]
    frame_sha256 = _sha256(screenshot_path)
    observation = {
        "observation_id": f"observation-{action_type}",
        "captured_at": "2026-05-30T17:45:00+08:00",
        "frame_sha256": frame_sha256,
        "frame_size": [1, 1],
    }
    runtime_dispatch = {
        "status": "ok",
        "target_key": target_key,
        "terminal_for_verifier": True,
    }
    operator_confirmation = {
        "confirmed": True,
        "requires_operator_confirmation": True,
        "scope": "final_mutating_click",
        "confirmation_id": f"confirmation-{action_type}",
        "request_id": f"request-{action_type}",
        "action_id": action_id,
        "action_type": action_type,
        "target_key": target_key,
        "target_identity": target_identity,
        "observation_id": observation["observation_id"],
        "frame_sha256": frame_sha256,
        "semantic_frame_guard": _semantic_frame_guard(target_key),
        "observation_captured_at": observation["captured_at"],
        "confirmed_at": "2026-05-30T17:45:05+08:00",
        "expires_at": "2026-05-30T17:45:15+08:00",
        "consumed_at": "2026-05-30T17:45:06+08:00",
        "dispatch_at": "2026-05-30T17:45:06+08:00",
        "runtime_dispatch": runtime_dispatch,
    }
    trace_path.write_text(
        json.dumps(
            {
                "trace_id": trace_id,
                "screenshot": {
                    "path": str(screenshot_path),
                    "metadata": {"observation": observation},
                },
                "frames": [
                    {
                        "role": "terminal_dispatch",
                        "path": str(screenshot_path),
                        "sha256": frame_sha256,
                        "observation": observation,
                    }
                ],
                "selected_action": {
                    "action_id": action_id,
                    "action_type": action_type,
                    "params": _selected_action_params(action_type, target_identity),
                },
                "execution": {
                    "action_id": action_id,
                    "status": "ok",
                    "summary": {
                        "target_key": target_key,
                        "terminal_for_verifier": True,
                        "dispatch_at": operator_confirmation["dispatch_at"],
                        "operator_confirmation": operator_confirmation,
                    },
                },
                "verification": {
                    "post_action_verifier": {
                        "action_type": action_type,
                        "status": "verified",
                        "target": target_identity,
                        "post_action_delta": delta_items,
                    },
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return {
        "source_kind": "live_trace_fixture",
        "review_status": "reviewed",
        "reviewed_by": "qa-reviewer",
        "reviewed_at": "2026-05-30T18:20:00+08:00",
        "screenshot": str(screenshot_path),
        "screenshot_sha256": frame_sha256,
        "trace": str(trace_path),
        "trace_sha256": _sha256(trace_path),
        "privacy_review": _privacy_review(),
        "page": page,
        "semantic_target": semantic_target,
        "runtime_dispatch": runtime_dispatch,
        "target_identity": target_identity,
        "post_action_delta": delta_items,
        "post_action_delta_evidence": {
            "source": "verification_record",
            "post_action_delta": delta_items,
            "supporting_refs": [
                "terminal_source_evidence.trace",
                "terminal_source_evidence.verification_record",
                "operator_confirmation.trace_id",
            ],
        },
        "verification_record": {
            "action_type": action_type,
            "status": "verified",
            "target": target_identity,
            "post_action_delta": delta_items,
        },
        "operator_confirmation": {
            **operator_confirmation,
            "trace_id": trace_id,
            "trace_record_index": 0,
        },
    }


class AdvisorTerminalSourcePreflightCliTests(unittest.TestCase):
    def test_cli_outputs_staging_payload_without_granting_temp_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            evidence = _ready_live_evidence(
                temp_root,
                action_type="claim_chapter_reward",
                page="chapter",
                semantic_target="progress.chapter_claim_button",
                target_key="chapter_claim_button",
            )
            screenshot_path = Path(evidence["screenshot"])
            trace_path = Path(evidence["trace"])
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

            self.assertEqual(exit_code, 2)
            self.assertFalse(payload["ready"])
            self.assertFalse(payload["accepted_for_closure"])
            self.assertTrue(payload["ready_for_staging"])
            self.assertTrue(payload["structural_valid"])
            self.assertFalse(payload["closure_authority_valid"])
            self.assertIn(
                "screenshot_path_not_repo_relative",
                payload["review"]["closure_disqualifiers"],
            )
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

    def test_batch_requires_all_low_risk_actions_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            claim_evidence = _ready_live_evidence(
                temp_root,
                action_type="claim_chapter_reward",
                page="chapter",
                semantic_target="progress.chapter_claim_button",
                target_key="chapter_claim_button",
            )
            batch_path = temp_root / "batch.json"
            batch_path.write_text(
                json.dumps(
                    [
                        {
                            "action_type": "claim_chapter_reward",
                            "fixture": "live_claim_terminal_trace.json",
                            "terminal_source_evidence": claim_evidence,
                        }
                    ],
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--batch-json", str(batch_path)])
            payload = json.loads(stdout.getvalue())

            self.assertEqual(exit_code, 2)
            self.assertFalse(payload["ready"])
            self.assertEqual(payload["accepted_actions"], [])
            self.assertEqual(payload["staging_actions"], ["claim_chapter_reward"])
            self.assertEqual(
                payload["missing_actions"],
                ["claim_chapter_reward", "recruit_soldiers", "upgrade_building"],
            )

    def test_batch_keeps_structural_temp_evidence_out_of_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            batch_items = [
                {
                    "action_type": "claim_chapter_reward",
                    "fixture": "live_claim_terminal_trace.json",
                    "terminal_source_evidence": _ready_live_evidence(
                        temp_root,
                        action_type="claim_chapter_reward",
                        page="chapter",
                        semantic_target="progress.chapter_claim_button",
                        target_key="chapter_claim_button",
                    ),
                },
                {
                    "action_type": "recruit_soldiers",
                    "fixture": "live_recruit_terminal_trace.json",
                    "terminal_source_evidence": _ready_live_evidence(
                        temp_root,
                        action_type="recruit_soldiers",
                        page="recruit",
                        semantic_target="teams[*].recruit_button",
                        target_key="recruit_button",
                    ),
                },
                {
                    "action_type": "upgrade_building",
                    "fixture": "live_upgrade_terminal_trace.json",
                    "terminal_source_evidence": _ready_live_evidence(
                        temp_root,
                        action_type="upgrade_building",
                        page="building_upgrade",
                        semantic_target="city.upgrade_dialog.confirm_button",
                        target_key="upgrade_confirm_button",
                    ),
                },
            ]
            batch_path = temp_root / "batch.json"
            batch_path.write_text(json.dumps({"items": batch_items}, ensure_ascii=False), encoding="utf-8")

            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(["--batch-json", str(batch_path)])
            payload = json.loads(stdout.getvalue())

            self.assertEqual(exit_code, 2)
            self.assertFalse(payload["ready"])
            self.assertEqual(
                payload["accepted_actions"],
                [],
            )
            self.assertEqual(
                payload["staging_actions"],
                ["claim_chapter_reward", "recruit_soldiers", "upgrade_building"],
            )
            self.assertEqual(
                payload["missing_actions"],
                ["claim_chapter_reward", "recruit_soldiers", "upgrade_building"],
            )
            self.assertEqual(len(payload["failing_results"]), 3)
            self.assertTrue(
                all(item["closure_disqualifiers"] for item in payload["failing_results"])
            )
            self.assertEqual(
                set(payload["suggested_advisor_fixture_expectation_patch"]),
                {
                    "live_claim_terminal_trace.json",
                    "live_recruit_terminal_trace.json",
                    "live_upgrade_terminal_trace.json",
                },
            )


if __name__ == "__main__":
    unittest.main()
