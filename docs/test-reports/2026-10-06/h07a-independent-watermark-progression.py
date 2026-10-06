"""Same planned clock matrix: a later revalidation check must raise the floor."""
from datetime import timedelta
import unittest
from unittest.mock import AsyncMock

from pioneer_agent.agent_harness.run_store import MemoryRunStore
from pioneer_agent.agent_harness.task_policy import RuleDecisionPolicy
from test_task_approval import make_runner, response_for
from test_task_runner import BASE, SequenceClient, task


class RevalidationWatermarkProgression(unittest.IsolatedAsyncioTestCase):
    async def test_observed_later_revalidation_time_cannot_regress_above_consumed(self):
        now = [BASE + timedelta(seconds=2)]
        spec = task()
        spec.success_when[0].value = 2
        store = MemoryRunStore()
        saved = await make_runner(store=store, spec=spec, now=now).run()
        now[0] = BASE + timedelta(seconds=3)
        r = make_runner(store=store, spec=spec, now=now,
                        client=SequenceClient(count=1), policy=RuleDecisionPolicy())
        r.policy.decide = AsyncMock(wraps=r.policy.decide)
        write = store._write
        phases = []
        def advance_then_rollback(envelope):
            write(envelope)
            state = envelope.state
            if (state.status == "revalidating_approval" and state.observation_ids[-1] == "obs-2"
                    and not phases):
                phases.append("observed_t10")
                now[0] = BASE + timedelta(seconds=10)
            elif state.reason == "approval_revalidated" and phases == ["observed_t10"]:
                phases.append("regressed_t8")
                now[0] = BASE + timedelta(seconds=8)
        store._write = advance_then_rollback
        result = await r.resume_synthetic(response_for(saved))
        self.assertEqual((phases, result.status, result.reason, r.policy.decide.call_count),
                         (["observed_t10", "regressed_t8"], "failed", "approval_clock_rollback", 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
