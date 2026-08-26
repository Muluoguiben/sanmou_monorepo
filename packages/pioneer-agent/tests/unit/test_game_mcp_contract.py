from __future__ import annotations

import unittest
from datetime import UTC, datetime

from pydantic import ValidationError

from pioneer_agent.mcp_server.contracts import (
    ActionProposal,
    ContractError,
    LiveObservation,
    ObserveGameResponse,
)


class GameMCPContractTests(unittest.TestCase):
    def test_live_observation_requires_aware_timestamp(self) -> None:
        with self.assertRaisesRegex(ValidationError, "timezone-aware"):
            LiveObservation(
                session_id="session-1",
                observation_id="observation-1",
                frame_sha256="a" * 64,
                captured_at=datetime(2026, 8, 26, 12, 0, 0),
                confidence=1.0,
            )

    def test_live_observation_rejects_conflicting_domain_status(self) -> None:
        with self.assertRaisesRegex(ValidationError, "both completed and unknown"):
            LiveObservation(
                session_id="session-1",
                observation_id="observation-1",
                frame_sha256="a" * 64,
                captured_at=datetime(2026, 8, 26, 12, 0, 0, tzinfo=UTC),
                domains_run=["map_land"],
                unknown_domains=["map_land"],
                confidence=0.0,
            )

    def test_non_success_response_requires_structured_error(self) -> None:
        with self.assertRaisesRegex(ValidationError, "require an error"):
            ObserveGameResponse(status="not_configured")

        response = ObserveGameResponse(
            status="not_configured",
            error=ContractError(code="not_configured", message="missing provider"),
        )
        self.assertEqual(response.execution_authority, "none")

    def test_action_proposal_cannot_be_executable(self) -> None:
        with self.assertRaises(ValidationError):
            ActionProposal(
                action_id="claim-1",
                action_type="claim_chapter_reward",
                score=1.0,
                confidence=1.0,
                executable=True,
                execution_blocked_reason="advisor_mode",
            )


if __name__ == "__main__":
    unittest.main()
