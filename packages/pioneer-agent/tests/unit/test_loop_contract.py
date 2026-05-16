from __future__ import annotations

import unittest

from pioneer_agent.runtime.loop_contract import (
    ensure_loop_contract,
    validate_loop_contract,
)
from pioneer_agent.storage.trace_store import TickTrace, TracePhase, TraceStep


def _valid_trace() -> TickTrace:
    return TickTrace(
        iteration=0,
        current_phase=TracePhase.TRACE,
        observe=TraceStep(phase=TracePhase.OBSERVE),
        decide=TraceStep(phase=TracePhase.DECIDE),
        act=TraceStep(phase=TracePhase.ACT),
        verify=TraceStep(phase=TracePhase.VERIFY),
        trace=TraceStep(phase=TracePhase.TRACE),
        recover=TraceStep(phase=TracePhase.RECOVER, recovery_strategy="none"),
        next_recovery_strategy="none",
    )


class LoopContractTests(unittest.TestCase):
    def test_valid_trace_passes_contract(self) -> None:
        trace = _valid_trace()

        self.assertEqual(validate_loop_contract(trace), [])
        self.assertIs(ensure_loop_contract(trace), trace)

    def test_missing_phase_and_recovery_strategy_are_reported(self) -> None:
        trace = TickTrace(
            iteration=0,
            current_phase=TracePhase.ACT,
            observe=TraceStep(phase=TracePhase.OBSERVE),
        )

        problems = validate_loop_contract(trace)

        self.assertIn("current_phase must end at trace, got act", problems)
        self.assertIn("missing decide step", problems)
        self.assertIn("missing recover step", problems)
        self.assertIn("next_recovery_strategy is required", problems)
        with self.assertRaisesRegex(ValueError, "loop contract violation"):
            ensure_loop_contract(trace)


if __name__ == "__main__":
    unittest.main()
