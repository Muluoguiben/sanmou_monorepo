"""Frozen independent H07a probes; offline Rule/Fake, no provider or archives."""
import asyncio
import copy
from datetime import timedelta
import unittest

from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.task_policy import RuleDecisionPolicy
from test_task_approval import make_runner, response_for
from test_task_runner import BASE, SequenceClient, task


class IndependentApprovalProbes(unittest.IsolatedAsyncioTestCase):
    async def test_observed_wait_clock_rollback_rejects_before_calls(self):
        """A rollback above created_at is still a previously observed rollback."""
        wall = [1000.0]
        mono = [1000.0]
        now = [BASE + timedelta(seconds=2)]
        budget = lambda: RunBudgetLedger(BudgetLimits(max_model_attempts=0),
            clock=lambda: wall[0], monotonic=lambda: mono[0])
        store = MemoryRunStore()
        r = make_runner(store=store, now=now, budget=budget())
        saved = await r.run()
        response = response_for(saved)
        now[0] += timedelta(seconds=10)
        wall[0] += 10
        mono[0] += 10
        self.assertEqual((await r.run(resume=True)).status, "awaiting_approval")
        before = len(r._client.calls)
        policy_before = len(r.policy.contexts)
        now[0] -= timedelta(seconds=5)
        wall[0] -= 5
        mono[0] += 1
        result = await r.resume_synthetic(response)
        self.assertEqual((result.status, result.reason, len(r._client.calls) - before,
                          len(r.policy.contexts) - policy_before),
                         ("failed", "approval_clock_rollback", 0, 0))

    async def test_slow_revalidation_checkpoint_cannot_verify_stale_goal(self):
        """The frame can expire during the post-observation checkpoint write."""
        now = [BASE + timedelta(seconds=2)]
        spec = task()
        spec.success_when[0].value = 2
        store = MemoryRunStore()
        saved = await make_runner(store=store, spec=spec, now=now).run()
        now[0] += timedelta(seconds=1)
        r = make_runner(store=store, spec=spec, now=now,
                        client=SequenceClient(count=1), policy=RuleDecisionPolicy())
        write = store._write
        delayed = []
        def slow_write(envelope):
            write(envelope)
            if (envelope.state.status == "revalidating_approval"
                    and envelope.state.observation_ids[-1] == "obs-2" and not delayed):
                delayed.append(True)
                now[0] += timedelta(seconds=120)
        store._write = slow_write
        result = await r.resume_synthetic(response_for(saved))
        self.assertEqual((bool(delayed), result.status, result.reason),
                         (True, "failed", "stale_observation"))

    async def test_slow_revalidation_checkpoint_cannot_outlive_budget(self):
        """A complete ledger deadline can elapse during synchronous persistence."""
        wall = [1000.0]
        budget = lambda: RunBudgetLedger(BudgetLimits(max_model_attempts=0, max_seconds=30.),
            clock=lambda: wall[0], monotonic=lambda: wall[0])
        spec = task()
        spec.success_when[0].value = 2
        store = MemoryRunStore()
        saved = await make_runner(store=store, spec=spec, budget=budget()).run()
        r = make_runner(store=store, spec=spec, budget=budget(),
                        client=SequenceClient(count=1), policy=RuleDecisionPolicy())
        write = store._write
        delayed = []
        def slow_write(envelope):
            write(envelope)
            if (envelope.state.status == "revalidating_approval"
                    and envelope.state.observation_ids[-1] == "obs-2" and not delayed):
                delayed.append(True)
                wall[0] += 31
        store._write = slow_write
        result = await r.resume_synthetic(response_for(saved))
        self.assertEqual((bool(delayed), result.status, result.reason),
                         (True, "failed", "run_deadline"))

    async def test_consumption_save_and_cleanup_preserve_primary(self):
        store = MemoryRunStore()
        saved = await make_runner(store=store).run()
        r = make_runner(store=store, client=SequenceClient(count=1))
        failure = OSError("independent-consume-write")
        write = store._write
        release = r._ownership._release
        def fail_write(envelope):
            if envelope.state.reason == "approval_consumed":
                raise failure
            write(envelope)
        def fail_release():
            release()
            raise RuntimeError("independent-cleanup")
        store._write = fail_write
        r._ownership._release = fail_release
        with self.assertRaises(OSError) as caught:
            await r.resume_synthetic(response_for(saved))
        self.assertIs(caught.exception, failure)
        self.assertEqual((r._client.calls, r.policy.contexts), ([], []))
        self.assertEqual(store.load().status, "awaiting_approval")

    async def test_request_response_mutability_does_not_change_checkpoint(self):
        store = MemoryRunStore()
        r = make_runner(store=store)
        returned = await r.run()
        original = copy.deepcopy(store.load().model_dump())
        returned.approval.request.evidence_refs.append("forged")
        self.assertEqual(store.load().model_dump(), original)
        fresh = make_runner(store=store, client=SequenceClient(count=1))
        result = await fresh.resume_synthetic(response_for(returned))
        self.assertEqual((result.reason, fresh._client.calls, fresh.policy.contexts),
                         ("approval_binding_mismatch", [], []))


if __name__ == "__main__":
    unittest.main(verbosity=2)
