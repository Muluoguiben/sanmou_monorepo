from __future__ import annotations

from pioneer_agent.core.models import CandidateAction, ExecutionResult


class ActionRunner:
    def run(self, action: CandidateAction) -> ExecutionResult:
        return ExecutionResult(
            action_id=action.action_id,
            status="not_implemented",
            verification_status="not_implemented",
            failure_reason="Execution layer scaffold only.",
            recovery_required=False,
            summary={"action_type": action.action_type.value},
        )

