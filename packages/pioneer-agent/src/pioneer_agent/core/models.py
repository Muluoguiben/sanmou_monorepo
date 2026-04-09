from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from .enums import ActionType, EventType, RuntimeStage


class FieldMeta(BaseModel):
    value: Any
    confidence: float = 1.0
    source: str = "unknown"
    updated_at: datetime | None = None


class RuntimeState(BaseModel):
    global_state: dict[str, Any] = Field(default_factory=dict)
    progress: dict[str, Any] = Field(default_factory=dict)
    economy: dict[str, Any] = Field(default_factory=dict)
    city: dict[str, Any] = Field(default_factory=dict)
    heroes: list[dict[str, Any]] = Field(default_factory=list)
    teams: list[dict[str, Any]] = Field(default_factory=list)
    map_state: dict[str, Any] = Field(default_factory=dict)
    swap_window: dict[str, Any] = Field(default_factory=dict)
    main_lineup: dict[str, Any] = Field(default_factory=dict)
    team_containers: list[dict[str, Any]] = Field(default_factory=list)
    carrier_pool: list[dict[str, Any]] = Field(default_factory=list)
    swap_constraints: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = Field(default_factory=dict)


class CandidateAction(BaseModel):
    action_id: str
    action_type: ActionType
    params: dict[str, Any] = Field(default_factory=dict)
    preconditions: list[str] = Field(default_factory=list)
    expected_gain: dict[str, Any] = Field(default_factory=dict)
    expected_cost: dict[str, Any] = Field(default_factory=dict)
    risk: dict[str, Any] = Field(default_factory=dict)
    timing: dict[str, Any] = Field(default_factory=dict)
    interruptibility: dict[str, Any] = Field(default_factory=dict)
    source_state_refs: list[str] = Field(default_factory=list)
    score_total: float = 0.0
    score_breakdown: dict[str, float] = Field(default_factory=dict)


class AgentEvent(BaseModel):
    event_type: EventType
    event_time: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class SelectionResult(BaseModel):
    selected_action: CandidateAction | None = None
    ranked_actions: list[CandidateAction] = Field(default_factory=list)
    selection_reason: dict[str, Any] = Field(default_factory=dict)
    next_replan_time: datetime | None = None


class ExecutionResult(BaseModel):
    action_id: str
    status: str
    verification_status: str = "unknown"
    failure_reason: str | None = None
    recovery_required: bool = False
    summary: dict[str, Any] = Field(default_factory=dict)


class RuntimeContext(BaseModel):
    session_id: str
    stage: RuntimeStage = RuntimeStage.IDLE
    started_at: datetime = Field(default_factory=datetime.utcnow)
    last_event: AgentEvent | None = None

