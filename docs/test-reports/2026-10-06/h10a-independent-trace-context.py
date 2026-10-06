"""Same F2 oracle at invocation-time validation, including implicit context."""
import importlib.util
from pathlib import Path
import traceback
import unittest

from pioneer_agent.agent_harness.task_contracts import TraceEmissionError

_spec = importlib.util.spec_from_file_location("h10a_targeted_frozen",
    Path(__file__).with_name("h10a-independent-targeted.py"))
targeted = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(targeted)
SENTINEL = "H10A_PRIVATE_IMPLICIT_CONTEXT_4b861d"


class InvocationContextPrivacy(unittest.IsolatedAsyncioTestCase):
    async def test_late_validation_wrapper_hides_private_exception_chain(self):
        class Policy:
            policy_id, policy_version, uses_model = "late-declaration", "initial-valid", False
            calls = 0
            async def decide(self, context):
                self.calls += 1
                raise AssertionError("must not invoke after declaration failure")
        policy = Policy()
        r = targeted.build(policy=policy)
        write = r.store._write
        cuts = []
        def change_declaration(envelope):
            write(envelope)
            if envelope.state.pending_call == "policy:late-declaration":
                cuts.append(True)
                policy.policy_version = {"private": SENTINEL}
        r.store._write = change_declaration
        with self.assertRaises(TraceEmissionError) as caught:
            await r.run()
        self.assertTrue(cuts)
        self.assertEqual((policy.calls, r._client.calls),
            (0, ["session_status", "observe_game", "get_runtime_state", "list_action_candidates"]))
        formatted = "".join(traceback.format_exception(caught.exception))
        self.assertNotIn(SENTINEL, formatted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
