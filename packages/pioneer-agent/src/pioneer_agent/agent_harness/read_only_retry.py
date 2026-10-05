"""Opt-in retry for canonical read-only calls; no runner or provider dependency."""
from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable
from typing import TypeVar

from pioneer_agent.mcp_server.contracts import GAME_TOOL_ALLOWLIST

from .task_contracts import BudgetExceeded, BudgetRequest, RunBudget, RunTrace, TraceEvent, Usage


T = TypeVar("T")
R = TypeVar("R")


async def call_read_only_with_retry(
    *, budget: RunBudget, trace: RunTrace, request: BudgetRequest,
    call: Callable[[], Awaitable[T]], validate: Callable[[T], R],
    max_attempts: int = 3, backoff_seconds: float = 0.05,
    observation_id: str | None = None, evidence_refs: list[str] | None = None,
) -> R:
    """Retry TimeoutError/ConnectionError raised by transport, never validation.

    No business outcome retry. `validate` must include schema/permission/binding
    checks; it runs outside the retryable transport-error boundary. One helper
    owns no global run scheduling and never changes the original deadline.
    """
    if request.kind != "tool" or request.name not in GAME_TOOL_ALLOWLIST:
        raise ValueError("canonical_read_only_tool_required")
    if type(max_attempts) is not int or not 1 <= max_attempts <= 100:
        raise ValueError("max_attempts_out_of_range")
    if not math.isfinite(backoff_seconds) or backoff_seconds < 0:
        raise ValueError("invalid_backoff")
    for attempt in range(max_attempts):
        reservation = budget.reserve(request)
        event = TraceEvent(
            run_id=request.run_id, step_id=request.step_id, event="tool",
            name=request.name, attempt_id=reservation, observation_id=observation_id,
            evidence_refs=list(evidence_refs or []), usage=Usage(),
            metadata={"attempt": attempt + 1},
        )
        outcome = "error"
        retry = False
        try:
            try:
                remaining = budget.remaining_seconds()
                if remaining <= 0:
                    raise BudgetExceeded("deadline")
                async with asyncio.timeout(remaining):
                    raw = await call()
            except (TimeoutError, ConnectionError) as exc:
                event.transport = "error"
                event.error_type = type(exc).__name__
                retry = attempt + 1 < max_attempts
                if not retry:
                    raise
            else:
                event.transport = "ok"
                try:
                    result = validate(raw)
                except Exception as exc:
                    event.contract = "error"
                    event.error_type = type(exc).__name__
                    raise
                event.contract = "ok"
                # A valid payload may report blocked/unknown. Never label it success.
                event.business = "not_evaluated"
                outcome = "validated"
                return result
        except asyncio.CancelledError:
            budget.cancel()
            event.transport = "cancelled"
            event.error_type = "CancelledError"
            outcome = "cancelled"
            raise
        except Exception as exc:
            if event.transport == "not_attempted" and not isinstance(exc, BudgetExceeded):
                event.transport = "error"
            event.error_type = type(exc).__name__
            raise
        finally:
            budget.settle(reservation, Usage(), outcome=outcome)
            trace.emit(event)
        if retry:
            delay = backoff_seconds * (2 ** attempt)
            if budget.remaining_seconds() <= delay:
                raise BudgetExceeded("retry_deadline")
            try:
                await asyncio.sleep(delay)
            except asyncio.CancelledError:
                budget.cancel()
                raise
    raise AssertionError("unreachable")
