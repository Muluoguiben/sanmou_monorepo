"""Drop-in replacement for `ActionRunner` that dispatches via UIActions.

Keeps the existing ActionRunner (non-implemented stub) untouched so
existing unit tests continue to pass. Consumers opt in by injecting
`UIActionRunner` into `AgentRuntime` instead.
"""
from __future__ import annotations

from pioneer_agent.core.device import CapabilityFlags
from pioneer_agent.core.models import CandidateAction, ExecutionResult
from pioneer_agent.executor.action_handlers import dispatch
from pioneer_agent.executor.ui_actions import UIActions


class UIActionRunner:
    def __init__(self, ui: UIActions, *, capabilities: CapabilityFlags | None = None) -> None:
        self.ui = ui
        self.capabilities = capabilities

    def run(self, action: CandidateAction) -> ExecutionResult:
        if self.capabilities is not None and not self.capabilities.can_execute_input:
            return ExecutionResult(
                action_id=action.action_id,
                status="blocked",
                verification_status="not_applicable",
                failure_reason="input_control capability required for UI execution",
                recovery_required=False,
                summary={
                    "action_type": action.action_type.value,
                    "blocked_by": "capability_flags",
                    "observe_only": self.capabilities.observe_only,
                },
            )
        return dispatch(action, self.ui)
