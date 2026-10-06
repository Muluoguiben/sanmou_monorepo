"""Deterministic public budget-port handoff after preparation, before lazy entry."""
import importlib.util
import json
from pathlib import Path
import unittest

from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.task_contracts import PolicyDecision

spec = importlib.util.spec_from_file_location("h10a_public_frozen",
    Path(__file__).with_name("h10a-independent-probes.py"))
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class PolicyBudgetBindingProbe(unittest.IsolatedAsyncioTestCase):
    async def test_timeout_sampling_cannot_switch_actual_policy_under_prepared_identity(self):
        calls, state = [], {"prepared": False, "swapped": False}
        class Original:
            policy_id, uses_model = "policy-P", False
            @property
            def policy_version(self):
                if state["runner"].state.pending_call == "policy:policy-P":
                    state["prepared"] = True
                return "P-1"
            async def decide(self, context):
                calls.append((self.policy_id, context.observation_id))
                return PolicyDecision(action="stop", reason="end synthetic window")
        class Replacement(Original):
            policy_id, policy_version, uses_model = "policy-Q", "Q-1", True
        replacement = Replacement()
        class HandoffBudget(RunBudgetLedger):
            def remaining_seconds(self):
                remaining = super().remaining_seconds()
                if state["prepared"] and not state["swapped"]:
                    state["swapped"] = True
                    state["runner"].policy = replacement
                return remaining
        r = public.build(policy=Original())
        state["runner"] = r
        r.budget = HandoffBudget(BudgetLimits(max_model_attempts=0))
        result = await r.run()
        records = [event for event in r.trace.events if event.event == "policy" and event.invocation_id is not None]
        trace_calls = [(event.provenance.policy_id, event.observation_id) for event in records]
        print(json.dumps({"swapped": state["swapped"], "actual_calls": calls, "trace_calls": trace_calls,
            "model_reservations": r.budget.summary()["counts"]["model"], "result": [result.status, result.reason]}), flush=True)
        self.assertTrue(state["swapped"])
        self.assertFalse(any(name == "policy-Q" for name, _ in calls),
                         "Model-declaring replacement must not enter under P's zero-model reservation")
        self.assertEqual(trace_calls, calls)


if __name__ == "__main__":
    unittest.main(verbosity=2)
