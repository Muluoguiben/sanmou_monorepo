"""Single canonical-reason correction; original 339aa56 probes stay immutable."""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import AsyncMock

_path = Path(__file__).with_name("h07a-independent-probes.py")
_spec = importlib.util.spec_from_file_location("h07a_frozen_original_probes", _path)
original = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(original)

from pioneer_agent.agent_harness.policy import StopReason


class CanonicalApprovalProbes(original.IndependentApprovalProbes):
    async def test_slow_revalidation_checkpoint_cannot_verify_stale_goal(self):
        # Same failure injection as the original; canonical name plus zero policy.
        self.assertEqual(StopReason.OBSERVATION_STALE.value, "observation_stale")
        now = [original.BASE + original.timedelta(seconds=2)]
        spec = original.task()
        spec.success_when[0].value = 2
        store = original.MemoryRunStore()
        saved = await original.make_runner(store=store, spec=spec, now=now).run()
        now[0] += original.timedelta(seconds=1)
        r = original.make_runner(store=store, spec=spec, now=now,
            client=original.SequenceClient(count=1), policy=original.RuleDecisionPolicy())
        r.policy.decide = AsyncMock(wraps=r.policy.decide)
        write = store._write
        delayed = []
        def slow_write(envelope):
            write(envelope)
            if (envelope.state.status == "revalidating_approval"
                    and envelope.state.observation_ids[-1] == "obs-2" and not delayed):
                delayed.append(True)
                now[0] += original.timedelta(seconds=120)
        store._write = slow_write
        result = await r.resume_synthetic(original.response_for(saved))
        self.assertEqual((bool(delayed), result.status, result.reason, r.policy.decide.call_count),
                         (True, "failed", "observation_stale", 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
