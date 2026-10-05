"""Atomic in-process run accounting; checkpoint restore never replenishes quotas."""
from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from .task_contracts import BudgetExceeded, BudgetRequest, Usage


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True, frozen=True)


class BudgetLimits(_Model):
    max_steps: int = Field(default=10, ge=0)
    max_tool_calls: int = Field(default=100, ge=0)
    max_model_attempts: int = Field(default=10, ge=0)
    max_tokens: int = Field(default=100000, ge=0)
    max_seconds: float = Field(default=300.0, gt=0, allow_inf_nan=False)
    max_cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class TokenPrices(_Model):
    """Explicit caller-supplied planning rates, not a provider price claim."""
    input_per_token: float = Field(ge=0, allow_inf_nan=False)
    output_per_token: float = Field(ge=0, allow_inf_nan=False)


class _Reservation(_Model):
    request: BudgetRequest
    usage: Usage | None = None
    outcome: str | None = None


class _Snapshot(_Model):
    version: Literal[1] = 1
    limits: BudgetLimits
    prices: TokenPrices | None = None
    run_id: str | None
    deadline: float = Field(allow_inf_nan=False)
    saved_at: float = Field(allow_inf_nan=False)
    remaining: float = Field(ge=0, allow_inf_nan=False)
    cancelled: bool
    overrun: bool
    reservations: dict[str, _Reservation]


class RunBudgetLedger:
    """Share one instance among workers. Cross-process quota/lease is not provided.

    Cleanup and waits consume the same wall deadline. Cancellation prohibits new
    reservations but allows final accounting and bounded transport cleanup. A
    caller must bound its awaits using remaining_seconds(), as specified by A0.
    """
    def __init__(self, limits: BudgetLimits | None = None, *,
                 prices: TokenPrices | None = None,
                 clock: Callable[[], float] = time.time,
                 monotonic: Callable[[], float] = time.monotonic) -> None:
        self.limits = limits or BudgetLimits()
        self.prices = prices
        self._clock, self._monotonic = clock, monotonic
        self._deadline = clock() + self.limits.max_seconds
        self._mono_deadline = monotonic() + self.limits.max_seconds
        self._run_id: str | None = None
        self._reservations: dict[str, _Reservation] = {}
        self._cancelled = False
        self._overrun = False
        self._lock = threading.RLock()

    def _totals(self) -> dict[str, Any]:
        counts = {"step": 0, "tool": 0, "model": 0}
        charged_tokens = 0
        charged_cost = 0.0
        measured_tokens = 0
        measured_cost = 0.0
        unknown_tokens = unknown_cost = 0
        pending = 0
        for entry in self._reservations.values():
            req, usage = entry.request, entry.usage
            counts[req.kind] += 1
            if usage is None:
                pending += 1
            actual_in = usage.input_tokens if usage else None
            actual_out = usage.output_tokens if usage else None
            incoming = req.input_tokens if actual_in is None else actual_in
            outgoing = req.output_tokens if actual_out is None else actual_out
            charged_tokens += incoming + outgoing
            if req.kind == "model":
                if actual_in is None or actual_out is None:
                    unknown_tokens += 1
                else:
                    measured_tokens += actual_in + actual_out
                if usage is None or usage.cost is None:
                    unknown_cost += 1
                    if self.prices:
                        charged_cost += (incoming * self.prices.input_per_token
                                         + outgoing * self.prices.output_per_token)
                else:
                    measured_cost += usage.cost
                    charged_cost += usage.cost
        return {"counts": counts, "charged_tokens": charged_tokens,
                "charged_cost": charged_cost if self.prices or unknown_cost == 0 else None,
                "measured_tokens": measured_tokens if unknown_tokens == 0 else None,
                "measured_cost": measured_cost if unknown_cost == 0 else None,
                "unknown_token_attempts": unknown_tokens,
                "unknown_cost_attempts": unknown_cost, "pending": pending}

    def reserve(self, request: BudgetRequest) -> str:
        request = BudgetRequest.model_validate(request.model_dump())
        with self._lock:
            if self._cancelled:
                raise BudgetExceeded("cancelled")
            if self._overrun:
                raise BudgetExceeded("settled_usage_exceeded_budget")
            if self.remaining_seconds() <= 0:
                raise BudgetExceeded("deadline")
            if self._run_id is not None and request.run_id != self._run_id:
                raise BudgetExceeded("run_identity")
            if request.kind == "model" and request.input_tokens + request.output_tokens == 0:
                raise BudgetExceeded("model_token_reservation_required")
            totals = self._totals()
            if totals["charged_tokens"] >= self.limits.max_tokens:
                raise BudgetExceeded("tokens")
            caps = {"step": self.limits.max_steps, "tool": self.limits.max_tool_calls,
                    "model": self.limits.max_model_attempts}
            if totals["counts"][request.kind] >= caps[request.kind]:
                raise BudgetExceeded(request.kind + "_attempts")
            if totals["charged_tokens"] + request.input_tokens + request.output_tokens > self.limits.max_tokens:
                raise BudgetExceeded("tokens")
            if (self.limits.max_cost is not None and totals["charged_cost"] is not None
                    and totals["charged_cost"] >= self.limits.max_cost):
                raise BudgetExceeded("cost")
            if self.limits.max_cost is not None and request.kind == "model":
                if self.prices is None:
                    raise BudgetExceeded("unknown_price")
                charge = (request.input_tokens * self.prices.input_per_token
                          + request.output_tokens * self.prices.output_per_token)
                if totals["charged_cost"] + charge > self.limits.max_cost:
                    raise BudgetExceeded("cost")
            reservation = uuid4().hex
            self._reservations[reservation] = _Reservation(request=request)
            self._run_id = request.run_id
            return reservation

    def settle(self, reservation_id: str, usage: Usage, *, outcome: str) -> None:
        usage = Usage.model_validate(usage.model_dump())
        with self._lock:
            entry = self._reservations.get(reservation_id)
            if entry is None:
                raise ValueError("unknown_reservation")
            if entry.usage is not None:
                raise ValueError("already_settled")
            self._reservations[reservation_id] = _Reservation(
                request=entry.request, usage=usage, outcome=outcome)
            totals = self._totals()
            if totals["charged_tokens"] > self.limits.max_tokens:
                self._overrun = True
            cost = totals["charged_cost"]
            if self.limits.max_cost is not None and (cost is None or cost > self.limits.max_cost):
                self._overrun = True

    def remaining_seconds(self) -> float:
        with self._lock:
            if self._cancelled:
                return 0.0
            return max(0.0, min(self._deadline - self._clock(),
                                self._mono_deadline - self._monotonic()))

    def cancel(self) -> None:
        with self._lock:
            self._cancelled = True

    def summary(self) -> dict[str, Any]:
        with self._lock:
            return {**self._totals(), "remaining_seconds": self.remaining_seconds(),
                    "cancelled": self._cancelled, "overrun": self._overrun}

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return _Snapshot(
                limits=self.limits, prices=self.prices, run_id=self._run_id,
                deadline=self._deadline, saved_at=self._clock(),
                remaining=self.remaining_seconds(), cancelled=self._cancelled,
                overrun=self._overrun, reservations=self._reservations,
            ).model_dump(mode="json")

    def restore(self, snapshot: dict[str, Any]) -> None:
        saved = _Snapshot.model_validate(snapshot)
        with self._lock:
            if self._reservations or self._cancelled or self._run_id is not None:
                raise ValueError("restore_requires_fresh_ledger")
            if saved.limits != self.limits or saved.prices != self.prices:
                raise ValueError("checkpoint_budget_configuration_mismatch")
            if any(entry.request.run_id != saved.run_id for entry in saved.reservations.values()):
                raise ValueError("checkpoint_run_identity")
            now = self._clock()
            if now < saved.saved_at:
                raise ValueError("clock_rollback_during_restore")
            remaining = max(0.0, min(saved.deadline - now, saved.remaining - (now - saved.saved_at)))
            self._deadline = min(saved.deadline, now + remaining)
            self._mono_deadline = self._monotonic() + remaining
            self._run_id = saved.run_id
            self._reservations = {key: value.model_copy(deep=True) for key, value in saved.reservations.items()}
            self._cancelled, self._overrun = saved.cancelled, saved.overrun
            totals = self._totals()
            caps = {"step": self.limits.max_steps, "tool": self.limits.max_tool_calls,
                    "model": self.limits.max_model_attempts}
            if (totals["charged_tokens"] > self.limits.max_tokens
                    or any(totals["counts"][kind] > cap for kind, cap in caps.items())
                    or (self.limits.max_cost is not None and
                        (totals["charged_cost"] is None or totals["charged_cost"] > self.limits.max_cost))):
                self._overrun = True
