from __future__ import annotations

import json
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import ValidationError

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import (
    CandidateAction,
    ObservationSnapshot,
    RuntimeState,
)
from pioneer_agent.executor.operator_confirmation import (
    JsonlOperatorConfirmationStore,
    OperatorConfirmation,
    OperatorConfirmationError,
    validate_confirmation_receipt,
)


class OperatorConfirmationTests(unittest.TestCase):
    def test_consumes_exact_binding_once_and_orders_dispatch_after_confirmation(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "confirmations.jsonl"
            store = JsonlOperatorConfirmationStore(path)
            action = _claim_action()
            observation = _observation()
            confirmation = _confirmation(action, observation)
            store.append_grant(confirmation)

            receipt = store.consume_for_dispatch(
                action=action,
                observation=observation,
                target_key="chapter_claim_button",
                now=confirmation.confirmed_at + timedelta(seconds=1),
            )

            self.assertGreater(receipt.dispatch_at, confirmation.confirmed_at)
            self.assertEqual(
                receipt.to_summary()["target_identity"],
                {"chapter_id": 17},
            )
            records = [json.loads(line) for line in path.read_text().splitlines()]
            self.assertEqual([item["record_type"] for item in records], ["grant", "consume"])
            self.assertEqual(records[1]["confirmation_id"], confirmation.confirmation_id)
            with self.assertRaises(OperatorConfirmationError):
                validate_confirmation_receipt(
                    receipt,
                    action=action.model_copy(update={"action_id": "different-action"}),
                    observation=observation,
                    target_key="chapter_claim_button",
                )

            with self.assertRaises(OperatorConfirmationError):
                store.consume_for_dispatch(
                    action=action,
                    observation=observation,
                    target_key="chapter_claim_button",
                    now=confirmation.confirmed_at + timedelta(seconds=2),
                )

    def test_rejects_expired_or_mismatched_frame_without_consuming(self) -> None:
        with TemporaryDirectory() as tmp:
            store = JsonlOperatorConfirmationStore(Path(tmp) / "confirmations.jsonl")
            action = _claim_action()
            observation = _observation()
            confirmation = _confirmation(action, observation)
            store.append_grant(confirmation)

            mismatched = observation.model_copy(update={"frame_sha256": "b" * 64})
            with self.assertRaises(OperatorConfirmationError):
                store.consume_for_dispatch(
                    action=action,
                    observation=mismatched,
                    target_key="chapter_claim_button",
                    now=confirmation.confirmed_at + timedelta(seconds=1),
                )
            with self.assertRaises(OperatorConfirmationError):
                store.consume_for_dispatch(
                    action=action,
                    observation=observation,
                    target_key="chapter_claim_button",
                    now=confirmation.expires_at,
                )

    def test_rejects_naive_timestamps_and_oversized_ttl(self) -> None:
        action = _claim_action()
        observation = _observation()
        payload = _confirmation(action, observation).model_dump(mode="python")
        payload["confirmed_at"] = datetime(2026, 7, 10, 12, 0, 1)
        with self.assertRaises(ValidationError):
            OperatorConfirmation.model_validate(payload)

        with TemporaryDirectory() as tmp:
            store = JsonlOperatorConfirmationStore(
                Path(tmp) / "confirmations.jsonl",
                max_ttl_seconds=5,
            )
            confirmation = _confirmation(action, observation).model_copy(
                update={"expires_at": datetime(2026, 7, 10, 12, 0, 20, tzinfo=UTC)}
            )
            with self.assertRaises(OperatorConfirmationError):
                store.append_grant(confirmation)


def _claim_action() -> CandidateAction:
    return CandidateAction(
        action_id="claim-17",
        action_type=ActionType.CLAIM_CHAPTER_REWARD,
        params={"chapter_id": 17},
    )


def _observation() -> ObservationSnapshot:
    return ObservationSnapshot(
        observation_id="obs-17",
        captured_at=datetime(2026, 7, 10, 12, 0, 0, tzinfo=UTC),
        frame_sha256="a" * 64,
        frame_size=(1920, 1080),
        page_type="chapter",
        domains_run=["resource_bar", "chapter_panel"],
        observed_state=RuntimeState(),
        source="vision_sync",
    )


def _confirmation(
    action: CandidateAction,
    observation: ObservationSnapshot,
) -> OperatorConfirmation:
    return OperatorConfirmation(
        confirmation_id="confirm-17",
        action_id=action.action_id,
        action_type=action.action_type,
        target_key="chapter_claim_button",
        target_identity={"chapter_id": 17},
        observation_id=observation.observation_id,
        frame_sha256=observation.frame_sha256,
        observation_captured_at=observation.captured_at,
        confirmed_at=datetime(2026, 7, 10, 12, 0, 1, tzinfo=UTC),
        expires_at=datetime(2026, 7, 10, 12, 0, 10, tzinfo=UTC),
    )


if __name__ == "__main__":
    unittest.main()
