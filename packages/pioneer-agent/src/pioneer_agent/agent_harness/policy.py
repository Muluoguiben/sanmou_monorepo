"""Fail-closed stop and screenshot-sensorium checkpoint policy."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pioneer_agent.agent_harness.journal import DecisionJournal, canonical_identity


class StopReason(str, Enum):
    CONTRACT_VIOLATION = "contract_violation"
    EXECUTION_AUTHORITY_VIOLATION = "execution_authority_violation"
    TOOL_FAILURE = "tool_failure"
    CONSECUTIVE_TOOL_FAILURES = "consecutive_tool_failures"
    OBSERVATION_STALE = "observation_stale"
    WINDOW_IDENTITY_CHANGED = "window_identity_changed"
    CAPTURE_UNHEALTHY = "capture_unhealthy"
    CRITICAL_DOMAIN_UNKNOWN = "critical_domain_unknown"
    CHECKPOINT_STALE = "checkpoint_stale"
    ALL_CANDIDATES_BLOCKED = "all_candidates_blocked"
    HUMAN_CONFIRMATION_REQUIRED = "human_confirmation_required"
    NO_CANDIDATES = "no_candidates"


class StopDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    should_stop: bool = False
    reason: StopReason | None = None
    details: list[str] = Field(default_factory=list)


class DomainCheckpoint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str
    domains: tuple[str, ...]
    refresh_every_s: float = Field(gt=0)
    stale_after_s: float = Field(gt=0)
    critical: bool = True


DEFAULT_CHECKPOINTS = (
    DomainCheckpoint(name="resources", domains=("resource_bar",), refresh_every_s=60, stale_after_s=180),
    DomainCheckpoint(name="chapter", domains=("chapter_panel",), refresh_every_s=120, stale_after_s=360),
    DomainCheckpoint(name="teams", domains=("team_panel", "team_detail"), refresh_every_s=120, stale_after_s=360),
    DomainCheckpoint(name="lands", domains=("map_land",), refresh_every_s=60, stale_after_s=180),
    DomainCheckpoint(name="battle_reports", domains=("battle_report",), refresh_every_s=30, stale_after_s=120),
    DomainCheckpoint(name="timers", domains=("timing",), refresh_every_s=30, stale_after_s=120),
)


class StopPolicy:
    def __init__(
        self,
        *,
        max_observation_age_s: float = 120.0,
        max_consecutive_tool_failures: int = 2,
        checkpoints: tuple[DomainCheckpoint, ...] = DEFAULT_CHECKPOINTS,
    ) -> None:
        if max_consecutive_tool_failures < 1:
            raise ValueError("max_consecutive_tool_failures must be positive")
        self.max_observation_age_s = max_observation_age_s
        self.max_consecutive_tool_failures = max_consecutive_tool_failures
        self.checkpoints = checkpoints

    def observation_stop(
        self,
        *,
        captured_at: datetime,
        now: datetime,
        unknown_domains: list[str],
    ) -> StopDecision:
        age_s = (now - captured_at).total_seconds()
        if age_s < -5 or age_s > self.max_observation_age_s:
            return StopDecision(
                should_stop=True,
                reason=StopReason.OBSERVATION_STALE,
                details=[f"observation_age_s={age_s:.3f}"],
            )
        critical_domains = {
            domain
            for checkpoint in self.checkpoints
            if checkpoint.critical
            for domain in checkpoint.domains
        }
        unknown = sorted(critical_domains.intersection(unknown_domains))
        if unknown:
            return StopDecision(
                should_stop=True,
                reason=StopReason.CRITICAL_DOMAIN_UNKNOWN,
                details=unknown,
            )
        return StopDecision()

    def checkpoint_stop(self, journal: DecisionJournal, now: datetime) -> StopDecision:
        stale: list[str] = []
        for checkpoint in self.checkpoints:
            latest = journal.latest_tooling_fact(f"checkpoint:{checkpoint.name}")
            if latest is not None:
                reference_time = latest.observed_at
            else:
                due_marker = next(
                    (
                        item
                        for item in reversed(journal.tooling.inferred)
                        if item.metadata.get("checkpoint_name") == checkpoint.name
                    ),
                    None,
                )
                if due_marker is None:
                    continue
                reference_time = due_marker.inferred_at
            age_s = (now - reference_time).total_seconds()
            if checkpoint.critical and age_s > checkpoint.stale_after_s:
                stale.append(f"{checkpoint.name}:{age_s:.3f}s")
        if stale:
            return StopDecision(
                should_stop=True,
                reason=StopReason.CHECKPOINT_STALE,
                details=stale,
            )
        return StopDecision()

    def due_checkpoints(self, journal: DecisionJournal, now: datetime) -> list[str]:
        due: list[str] = []
        for checkpoint in self.checkpoints:
            latest = journal.latest_tooling_fact(f"checkpoint:{checkpoint.name}")
            if latest is None or (now - latest.observed_at).total_seconds() > checkpoint.refresh_every_s:
                due.append(checkpoint.name)
        return due

    def window_stop(self, journal: DecisionJournal, current_identity: Any) -> StopDecision:
        previous = journal.latest_tooling_fact("window_identity")
        if previous is None:
            return StopDecision()
        if canonical_identity(previous.metadata.get("window_identity")) != canonical_identity(current_identity):
            return StopDecision(
                should_stop=True,
                reason=StopReason.WINDOW_IDENTITY_CHANGED,
                details=["window identity differs from the last journaled observation"],
            )
        return StopDecision()

    @staticmethod
    def candidates_stop(candidates: list[Any]) -> StopDecision:
        if not candidates:
            return StopDecision(should_stop=True, reason=StopReason.NO_CANDIDATES)
        if all(candidate.blockers for candidate in candidates):
            return StopDecision(
                should_stop=True,
                reason=StopReason.ALL_CANDIDATES_BLOCKED,
                details=sorted({str(item) for candidate in candidates for item in candidate.blockers}),
            )
        return StopDecision()

    @staticmethod
    def confirmation_stop(candidate: Any) -> StopDecision:
        risk = candidate.risk
        confirmation = any(
            risk.get(key) is True
            for key in ("confirmation_required", "confirm_required", "requires_human_confirmation")
        )
        level = str(risk.get("level", risk.get("risk_level", "low"))).lower()
        high_risk = level in {"high", "critical"}
        action_requires_confirmation = candidate.action_type in {
            "attack_land",
            "abandon_land",
            "transfer_main_lineup_to_team",
        }
        if confirmation or high_risk or action_requires_confirmation:
            return StopDecision(
                should_stop=True,
                reason=StopReason.HUMAN_CONFIRMATION_REQUIRED,
                details=[candidate.action_id, candidate.action_type],
            )
        return StopDecision()
