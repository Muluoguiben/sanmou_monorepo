"""Deadline consumed by provenance must not invent an actual invocation."""
import importlib.util
from pathlib import Path
import unittest

from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.task_contracts import PolicyDecision

spec = importlib.util.spec_from_file_location("h10a_targeted_frozen",
    Path(__file__).with_name("h10a-independent-targeted.py"))
targeted = importlib.util.module_from_spec(spec)
spec.loader.exec_module(targeted)


class DispatchDeadlineProbe(unittest.IsolatedAsyncioTestCase):
    async def test_provenance_deadline_zero_call_has_no_invoked_trace(self):
        for boundary, expected_tools in (("tool", 0), ("policy", 4)):
            with self.subTest(boundary=boundary):
                clock = [1000.]
                budget = RunBudgetLedger(BudgetLimits(max_model_attempts=0, max_seconds=1.),
                    clock=lambda: clock[0], monotonic=lambda: clock[0])
                class Policy:
                    policy_id, uses_model = "deadline-policy", False
                    calls = 0
                    advanced = False
                    @property
                    def policy_version(self):
                        pending = self.runner.state.pending_call
                        target = "session_status" if boundary == "tool" else "policy:deadline-policy"
                        if pending == target and not self.advanced:
                            self.advanced = True
                            clock[0] += 2  # Cost of declaration/provenance work after prior guard.
                        return "declared-only"
                    async def decide(self, context):
                        self.calls += 1
                        return PolicyDecision(action="continue", reason="continue")
                policy = Policy()
                r = targeted.build(policy=policy)
                r.budget = budget  # Fresh public budget port, before any run/reservation.
                policy.runner = r
                result = await r.run()
                self.assertTrue(policy.advanced)
                self.assertEqual((result.status, result.reason), ("failed", "run_deadline"))
                self.assertEqual((len(r._client.calls), policy.calls), (expected_tools, 0))
                attempted = [event for event in r.trace.events if event.event == boundary]
                self.assertTrue(all(event.invocation_id is None and event.transport == "not_attempted"
                                    for event in attempted),
                    [(event.event, event.transport, event.invocation_id) for event in attempted])
                if boundary == "policy":
                    self.assertTrue(all(event.provenance.context_digest is None for event in attempted))
                self.assertEqual(budget.summary()["counts"]["model"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
