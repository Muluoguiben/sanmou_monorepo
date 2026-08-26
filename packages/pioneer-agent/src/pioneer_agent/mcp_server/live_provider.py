"""Explicit adapter from the existing Advisor loop to the game MCP contract."""

from __future__ import annotations

from pioneer_agent.runtime.advisor_loop import AdvisorLoop

from .service import ObservedAdvisorCycle


class AdvisorLoopObservationProvider:
    """Production read-only provider; it exposes no input or execution method."""

    def __init__(self, loop: AdvisorLoop) -> None:
        self._loop = loop

    def observe(self) -> ObservedAdvisorCycle:
        cycle = self._loop.observe()
        return ObservedAdvisorCycle(
            observation=cycle.observation,
            report=cycle.report,
        )
