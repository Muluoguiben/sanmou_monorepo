from __future__ import annotations

import hashlib
import io
import json
import unittest
from contextlib import redirect_stderr, redirect_stdout
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from pioneer_agent.app.operator_confirmation import main as confirmation_cli_main
from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ObservationSnapshot, RuntimeState
from pioneer_agent.executor.operator_confirmation import (
    JsonlOperatorConfirmationStore,
    OperatorConfirmation,
    OperatorConfirmationError,
    OperatorConfirmationRequest,
    WaitingOperatorConfirmationProvider,
    grant_operator_confirmation,
    load_operator_confirmation_request,
)
from pioneer_agent.executor.semantic_frame_guard import build_semantic_frame_guard


class OperatorConfirmationWaitTests(unittest.TestCase):
    def test_publishes_exact_terminal_binding_and_waits_for_external_grant(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "confirmations.jsonl"
            request_path = root / "request.json"
            store = JsonlOperatorConfirmationStore(store_path)
            action, observation = _action_and_observation()
            current = [datetime(2026, 7, 10, 12, 0, 1, tzinfo=UTC)]
            reviewed_requests: list[OperatorConfirmationRequest] = []

            def sleep_and_grant(seconds: float) -> None:
                current[0] += timedelta(seconds=seconds)
                if reviewed_requests:
                    return
                request = load_operator_confirmation_request(request_path)
                reviewed_requests.append(request)
                store.append_grant(
                    grant_operator_confirmation(
                        request,
                        confirmed_at=current[0],
                        confirmation_id="human-grant-17",
                    )
                )

            provider = WaitingOperatorConfirmationProvider(
                store,
                request_path,
                wait_timeout_seconds=2,
                poll_interval_seconds=0.2,
                confirmation_ttl_seconds=1,
                clock=lambda: current[0],
                sleeper=sleep_and_grant,
            )

            receipt = provider.consume_for_dispatch(
                action=action,
                observation=observation,
                target_key="chapter_claim_button",
                semantic_frame_guard=_semantic_guard(observation),
            )

            self.assertEqual(receipt.confirmation.confirmation_id, "human-grant-17")
            self.assertEqual(len(reviewed_requests), 1)
            request = reviewed_requests[0]
            self.assertEqual(request.action_id, action.action_id)
            self.assertEqual(request.action_type, action.action_type)
            self.assertEqual(request.target_identity, {"chapter_id": 17})
            self.assertEqual(request.observation_id, observation.observation_id)
            self.assertEqual(request.frame_sha256, observation.frame_sha256)
            self.assertEqual(
                request.semantic_frame_guard.roi_sha256,
                _semantic_guard(observation).roi_sha256,
            )
            self.assertEqual(
                request.semantic_frame_guard.normalized_bbox.model_dump(),
                {"x_min": 700.0, "y_min": 800.0, "x_max": 900.0, "y_max": 900.0},
            )
            self.assertEqual(
                request.semantic_frame_guard.click_point.model_dump(),
                {"x": 1536, "y": 918},
            )
            self.assertEqual(request.observation_captured_at, observation.captured_at)
            self.assertEqual(request.confirmation_ttl_seconds, 1)
            self.assertEqual(request.confirmation_store_path, str(store_path.resolve()))
            self.assertFalse(request_path.exists())
            records = [json.loads(line) for line in store_path.read_text().splitlines()]
            self.assertEqual(
                [record["record_type"] for record in records],
                ["grant", "consume"],
            )

    def test_timeout_never_creates_a_grant(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "confirmations.jsonl"
            request_path = root / "request.json"
            current = [datetime(2026, 7, 10, 12, 0, 1, tzinfo=UTC)]
            action, observation = _action_and_observation()
            provider = WaitingOperatorConfirmationProvider(
                JsonlOperatorConfirmationStore(store_path),
                request_path,
                wait_timeout_seconds=0.5,
                poll_interval_seconds=0.25,
                confirmation_ttl_seconds=0.5,
                clock=lambda: current[0],
                sleeper=lambda seconds: current.__setitem__(
                    0,
                    current[0] + timedelta(seconds=seconds),
                ),
            )

            with self.assertRaisesRegex(
                OperatorConfirmationError,
                "timed out",
            ):
                provider.consume_for_dispatch(
                    action=action,
                    observation=observation,
                    target_key="chapter_claim_button",
                    semantic_frame_guard=_semantic_guard(observation),
                )

            self.assertFalse(store_path.exists())
            self.assertFalse(request_path.exists())

    def test_preexisting_matching_grant_cannot_satisfy_a_new_request(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "confirmations.jsonl"
            request_path = root / "request.json"
            store = JsonlOperatorConfirmationStore(store_path)
            action, observation = _action_and_observation()
            store.append_grant(
                OperatorConfirmation(
                    confirmation_id="pre-grant",
                    action_id=action.action_id,
                    action_type=action.action_type,
                    target_key="chapter_claim_button",
                    target_identity={"chapter_id": 17},
                    observation_id=observation.observation_id,
                    frame_sha256=observation.frame_sha256,
                    observation_captured_at=observation.captured_at,
                    confirmed_at=datetime(2026, 7, 10, 12, 0, 0, 500000, tzinfo=UTC),
                    expires_at=datetime(2026, 7, 10, 12, 0, 10, tzinfo=UTC),
                )
            )
            current = [datetime(2026, 7, 10, 12, 0, 1, tzinfo=UTC)]
            provider = WaitingOperatorConfirmationProvider(
                store,
                request_path,
                wait_timeout_seconds=0.5,
                poll_interval_seconds=0.25,
                confirmation_ttl_seconds=0.5,
                clock=lambda: current[0],
                sleeper=lambda seconds: current.__setitem__(
                    0,
                    current[0] + timedelta(seconds=seconds),
                ),
            )

            with self.assertRaisesRegex(OperatorConfirmationError, "timed out"):
                provider.consume_for_dispatch(
                    action=action,
                    observation=observation,
                    target_key="chapter_claim_button",
                    semantic_frame_guard=_semantic_guard(observation),
                )

            records = [json.loads(line) for line in store_path.read_text().splitlines()]
            self.assertEqual([record["record_type"] for record in records], ["grant"])

    def test_cli_requires_explicit_confirm_and_copies_request_binding(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            store_path = root / "confirmations.jsonl"
            request_path = root / "request.json"
            action, observation = _action_and_observation()
            now = datetime.now(UTC)
            request = OperatorConfirmationRequest(
                request_id="request-17",
                action_id=action.action_id,
                action_type=action.action_type,
                target_key="chapter_claim_button",
                target_identity={"chapter_id": 17},
                observation_id=observation.observation_id,
                frame_sha256=observation.frame_sha256,
                semantic_frame_guard=_semantic_guard(observation),
                observation_captured_at=now - timedelta(seconds=1),
                requested_at=now,
                request_expires_at=now + timedelta(seconds=10),
                confirmation_ttl_seconds=5,
                confirmation_store_path=str(store_path),
            )
            request_path.write_text(request.model_dump_json(), encoding="utf-8")

            with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                confirmation_cli_main(["grant", "--request", str(request_path)])
            self.assertFalse(store_path.exists())

            with redirect_stdout(io.StringIO()) as stdout:
                result = confirmation_cli_main(
                    ["grant", "--request", str(request_path), "--confirm"]
                )

            self.assertEqual(result, 0)
            output = json.loads(stdout.getvalue())
            self.assertEqual(output["status"], "granted")
            grant = json.loads(store_path.read_text().splitlines()[0])
            self.assertEqual(grant["record_type"], "grant")
            self.assertEqual(grant["request_id"], request.request_id)
            self.assertEqual(grant["action_id"], action.action_id)
            self.assertEqual(grant["target_identity"], {"chapter_id": 17})
            self.assertEqual(grant["observation_id"], observation.observation_id)
            self.assertEqual(grant["frame_sha256"], observation.frame_sha256)


def _action_and_observation() -> tuple[CandidateAction, ObservationSnapshot]:
    action = CandidateAction(
        action_id="claim-17",
        action_type=ActionType.CLAIM_CHAPTER_REWARD,
        params={"chapter_id": 17},
    )
    return action, ObservationSnapshot(
        observation_id="obs-17",
        captured_at=datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC),
        frame_sha256=hashlib.sha256(_frame_bytes()).hexdigest(),
        frame_size=(1920, 1080),
        page_type="chapter",
        domains_run=["resource_bar", "chapter_panel"],
        observed_state=RuntimeState(),
        source="vision_sync",
    )


def _frame_bytes() -> bytes:
    image = Image.new("RGB", (1920, 1080), (20, 40, 60))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


def _semantic_guard(observation: ObservationSnapshot):  # noqa: ANN201
    return build_semantic_frame_guard(
        _frame_bytes(),
        frame_size=observation.frame_size or (0, 0),
        semantic_target_key="chapter_claim_button",
        bbox={"x_min": 700, "y_min": 800, "x_max": 900, "y_max": 900},
    )


if __name__ == "__main__":
    unittest.main()
