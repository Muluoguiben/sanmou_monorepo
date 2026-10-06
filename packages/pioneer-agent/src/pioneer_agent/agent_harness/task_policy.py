"""Deterministic policy baseline; goal verification stays in the runner."""
from pioneer_agent.agent_harness.task_contracts import PolicyContext, PolicyDecision


class RuleDecisionPolicy:
    policy_id = "rule-observe-v1"
    policy_version = "1"
    uses_model = False

    async def decide(self, context: PolicyContext) -> PolicyDecision:
        return PolicyDecision(action="continue", reason="observe_until_verified_goal")


class FakeDecisionPolicy:
    policy_id = "fake-script-v1"
    policy_version = "1"
    uses_model = False

    def __init__(self, decisions: list[PolicyDecision]):
        self.decisions = list(decisions)
        self.contexts: list[PolicyContext] = []

    async def decide(self, context: PolicyContext) -> PolicyDecision:
        self.contexts.append(context.model_copy(deep=True))
        if not self.decisions:
            return PolicyDecision(action="stop", reason="fake_script_exhausted")
        return self.decisions.pop(0)
