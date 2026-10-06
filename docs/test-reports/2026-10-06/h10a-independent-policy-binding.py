"""Prepared identity must name the actual policy object entering lazy dispatch."""
import asyncio
import importlib.util
import json
from pathlib import Path
import unittest

from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.task_contracts import PolicyDecision

spec = importlib.util.spec_from_file_location("h10a_public_frozen",
    Path(__file__).with_name("h10a-independent-probes.py"))
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


async def swapped_policy_run(causal):
    calls = []
    class Original:
        policy_id, policy_version, uses_model = "policy-P", "P-1", False
        async def decide(self, context):
            calls.append((self.policy_id, context.observation_id))
            return PolicyDecision(action="stop", reason="end this synthetic window")
    class Replacement(Original):
        policy_id, policy_version, uses_model = "policy-Q", "Q-1", True
    replacement, store = Replacement(), MemoryRunStore()
    r = public.build(causal=causal, policy=Original(), store=store)
    r.budget = RunBudgetLedger(BudgetLimits(max_model_attempts=0))
    write = store._write
    scheduled = []
    def queue_replacement(envelope):
        write(envelope)
        if envelope.state.pending_call == "policy:policy-P" and not scheduled:
            scheduled.append(True)
            asyncio.get_running_loop().call_soon(setattr, r, "policy", replacement)
    store._write = queue_replacement
    result = await r.run()
    records = [event for event in r.trace.events if event.event == "policy"]
    actual = [event for event in records if getattr(event, "invocation_id", None) is not None]
    observed = {"causal": causal, "calls": calls, "model_reservations": r.budget.summary()["counts"]["model"],
        "trace_invocations": [(event.name, event.provenance.policy_id, event.observation_id) for event in actual],
        "result": [result.status, result.reason]}
    print(json.dumps(observed), flush=True)
    return r, calls, actual, scheduled


class PolicyBindingProbe(unittest.IsolatedAsyncioTestCase):
    async def test_lazy_dispatch_cannot_substitute_unreserved_policy_under_old_identity(self):
        r, calls, records, scheduled = await swapped_policy_run(True)
        self.assertTrue(scheduled)
        self.assertFalse(any(name == "policy-Q" for name, _ in calls),
                         "Replacement declares model use but the budget permits zero model attempts")
        self.assertEqual([(event.provenance.policy_id, event.observation_id) for event in records], calls)
        self.assertEqual(r.budget.summary()["counts"]["model"], 0)

    async def test_default_v1_still_calls_the_original_bound_policy(self):
        r, calls, _, scheduled = await swapped_policy_run(False)
        self.assertTrue(scheduled)
        self.assertEqual(calls, [("policy-P", "obs-1")])
        self.assertEqual(r.budget.summary()["counts"]["model"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
