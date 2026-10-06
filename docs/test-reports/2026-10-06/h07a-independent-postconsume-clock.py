"""Frozen continuation of the original clock-rollback/revalidation acceptance gate."""
from datetime import timedelta
import unittest
from unittest.mock import AsyncMock

from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.task_policy import RuleDecisionPolicy
from test_task_approval import make_runner, response_for
from test_task_runner import BASE, SequenceClient, task


class PostConsumptionClockProbe(unittest.IsolatedAsyncioTestCase):
    async def test_clock_rollback_after_consumption_cannot_verify_goal(self):
        now = [BASE + timedelta(seconds=2)]
        spec = task()
        spec.success_when[0].value = 2
        store = MemoryRunStore()
        saved = await make_runner(store=store, spec=spec, now=now).run()
        now[0] += timedelta(seconds=1)
        r = make_runner(store=store, spec=spec, now=now,
                        client=SequenceClient(count=1), policy=RuleDecisionPolicy())
        r.policy.decide = AsyncMock(wraps=r.policy.decide)
        write = store._write
        rolled_back = []
        def write_and_rollback(envelope):
            write(envelope)
            if envelope.state.reason == "approval_consumed" and not rolled_back:
                rolled_back.append(True)
                # Now is below consumed_at but above both captured_at values.
                now[0] -= timedelta(milliseconds=500)
        store._write = write_and_rollback
        result = await r.resume_synthetic(response_for(saved))
        self.assertEqual((bool(rolled_back), result.status, result.reason, r.policy.decide.call_count),
                         (True, "failed", "approval_clock_rollback", 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
