"""A caller's handled exception is not a current tool/window/policy primary."""
import asyncio
import importlib.util
from pathlib import Path
import traceback
import unittest

from pioneer_agent.agent_harness.task_contracts import TraceEmissionError

spec = importlib.util.spec_from_file_location("h10a_public_frozen",
    Path(__file__).with_name("h10a-independent-probes.py"))
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class AmbientExceptionProbes(unittest.IsolatedAsyncioTestCase):
    async def test_handled_caller_exception_cannot_hide_trace_failure(self):
        for boundary, calls in (("tool", 1), ("policy", 4), ("outcome", 4), ("lifetime_end", 12)):
            with self.subTest(boundary=boundary):
                sink = public.EmitOnlySink(boundary)
                r = public.build(trace=sink)
                try:
                    raise LookupError("CALLER_ALREADY_HANDLED_PRIVATE")
                except LookupError as ambient:
                    with self.assertRaises(TraceEmissionError) as caught:
                        await r.run()
                    self.assertNotIn("CALLER_ALREADY_HANDLED_PRIVATE",
                        "".join(traceback.format_exception(caught.exception)))
                    self.assertFalse(getattr(ambient, "__notes__", []))
                self.assertEqual((len(r._client.calls), sink.after_failure), (calls, 0))
                if boundary == "lifetime_end":
                    self.assertEqual(r.store.load().status, "succeeded")

    async def test_genuine_policy_primary_still_wins_inside_caller_except(self):
        for cancelled in (False, True):
            with self.subTest(cancelled=cancelled):
                primary = asyncio.CancelledError() if cancelled else ValueError("actual-policy-error")
                class Policy:
                    policy_id, uses_model = "current-policy", False
                    calls = 0
                    async def decide(self, context):
                        self.calls += 1
                        raise primary
                policy, sink = Policy(), public.EmitOnlySink("policy")
                r = public.build(policy=policy, trace=sink)
                try:
                    raise LookupError("already-handled")
                except LookupError:
                    if cancelled:
                        with self.assertRaises(asyncio.CancelledError) as caught:
                            await r.run()
                        self.assertIs(caught.exception, primary)
                    else:
                        result = await r.run()
                        self.assertEqual((result.status, result.reason), ("failed", "runtime_error:ValueError"))
                self.assertEqual((policy.calls, len(r._client.calls), sink.after_failure), (1, 4, 0))


if __name__ == "__main__":
    unittest.main(verbosity=2)
