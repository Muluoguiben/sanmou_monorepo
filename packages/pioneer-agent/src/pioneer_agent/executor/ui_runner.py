"""Drop-in replacement for `ActionRunner` that dispatches via UIActions.

Keeps the existing ActionRunner (non-implemented stub) untouched so
existing unit tests continue to pass. Consumers opt in by injecting
`UIActionRunner` into `AgentRuntime` instead.
"""
from __future__ import annotations

from pioneer_agent.core.models import CandidateAction, ExecutionResult
from pioneer_agent.executor.action_handlers import dispatch
from pioneer_agent.executor.ui_actions import UIActions


class UIActionRunner:
    def __init__(self, ui: UIActions) -> None:
        self.ui = ui

    def run(self, action: CandidateAction) -> ExecutionResult:
        return dispatch(action, self.ui)
