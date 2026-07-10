"""Opening runbook models: season phases with machine-checkable conditions.

A runbook serializes a season opening guide (开荒攻略) into ordered phases.
Each phase carries entry/exit/abort conditions evaluated against a metrics
mapping derived from RuntimeState — never against a screenshot. Evaluation is
three-valued: a missing metric yields UNKNOWN instead of silently failing,
so the engine can escalate perception gaps instead of guessing.
"""
from __future__ import annotations

import operator
from enum import Enum
from typing import Any, Callable, Mapping

import yaml
from pydantic import BaseModel, Field, field_validator, model_validator

_OPS: dict[str, Callable[[Any, Any], bool]] = {
    ">=": operator.ge,
    ">": operator.gt,
    "<=": operator.le,
    "<": operator.lt,
    "==": operator.eq,
    "!=": operator.ne,
}
_ORDERING_OPS = frozenset({">=", ">", "<=", "<"})


class ConditionStatus(str, Enum):
    SATISFIED = "satisfied"
    NOT_SATISFIED = "not_satisfied"
    UNKNOWN = "unknown"


class Condition(BaseModel):
    metric: str
    op: str = "=="
    value: Any = None

    @field_validator("op")
    @classmethod
    def _validate_op(cls, value: str) -> str:
        if value not in _OPS:
            raise ValueError(f"Unsupported condition op: {value!r} (allowed: {sorted(_OPS)})")
        return value

    @classmethod
    def parse(cls, metric: str, expression: Any) -> "Condition":
        """Build a condition from the compact YAML form.

        String expressions may start with an operator token (`">= 37"`,
        `"== true"`); anything else — including bare ints/floats/bools —
        is an equality check.
        """
        if isinstance(expression, str):
            stripped = expression.strip()
            for op_token in sorted(_OPS, key=len, reverse=True):
                if stripped.startswith(op_token):
                    raw_value = stripped[len(op_token):].strip()
                    return cls(metric=metric, op=op_token, value=yaml.safe_load(raw_value))
            return cls(metric=metric, op="==", value=yaml.safe_load(stripped))
        return cls(metric=metric, op="==", value=expression)

    def evaluate(self, metrics: Mapping[str, Any]) -> ConditionStatus:
        observed, found = _resolve_metric(metrics, self.metric)
        if not found or observed is None:
            return ConditionStatus.UNKNOWN
        if self.op in _ORDERING_OPS and not (_is_number(observed) and _is_number(self.value)):
            return ConditionStatus.UNKNOWN
        try:
            result = _OPS[self.op](observed, self.value)
        except TypeError:
            return ConditionStatus.UNKNOWN
        return ConditionStatus.SATISFIED if result else ConditionStatus.NOT_SATISFIED

    def describe(self) -> str:
        return f"{self.metric} {self.op} {self.value!r}"


class ConditionEvaluation(BaseModel):
    metric: str
    op: str
    value: Any = None
    status: ConditionStatus

    def to_dict(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "op": self.op,
            "value": self.value,
            "status": self.status.value,
        }


class ConditionSetResult(BaseModel):
    status: ConditionStatus
    evaluations: list[ConditionEvaluation] = Field(default_factory=list)

    @property
    def missing_metrics(self) -> list[str]:
        return [e.metric for e in self.evaluations if e.status == ConditionStatus.UNKNOWN]

    @property
    def failed(self) -> list[ConditionEvaluation]:
        return [e for e in self.evaluations if e.status == ConditionStatus.NOT_SATISFIED]

    @property
    def satisfied(self) -> list[ConditionEvaluation]:
        return [e for e in self.evaluations if e.status == ConditionStatus.SATISFIED]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status.value,
            "evaluations": [e.to_dict() for e in self.evaluations],
        }


def evaluate_all(conditions: list[Condition], metrics: Mapping[str, Any]) -> ConditionSetResult:
    """AND semantics: any failure fails the set; otherwise any unknown makes it unknown."""
    evaluations = [
        ConditionEvaluation(metric=c.metric, op=c.op, value=c.value, status=c.evaluate(metrics))
        for c in conditions
    ]
    statuses = {e.status for e in evaluations}
    if ConditionStatus.NOT_SATISFIED in statuses:
        overall = ConditionStatus.NOT_SATISFIED
    elif ConditionStatus.UNKNOWN in statuses:
        overall = ConditionStatus.UNKNOWN
    else:
        overall = ConditionStatus.SATISFIED
    return ConditionSetResult(status=overall, evaluations=evaluations)


def evaluate_any(conditions: list[Condition], metrics: Mapping[str, Any]) -> ConditionSetResult:
    """OR semantics for abort sets: any satisfied condition triggers the set."""
    evaluations = [
        ConditionEvaluation(metric=c.metric, op=c.op, value=c.value, status=c.evaluate(metrics))
        for c in conditions
    ]
    statuses = {e.status for e in evaluations}
    if ConditionStatus.SATISFIED in statuses:
        overall = ConditionStatus.SATISFIED
    elif ConditionStatus.UNKNOWN in statuses:
        overall = ConditionStatus.UNKNOWN
    elif evaluations:
        overall = ConditionStatus.NOT_SATISFIED
    else:
        overall = ConditionStatus.NOT_SATISFIED
    return ConditionSetResult(status=overall, evaluations=evaluations)


class PhaseDefinition(BaseModel):
    phase_id: str
    title: str
    goal: str = ""
    entry_when: list[Condition] = Field(default_factory=list)
    exit_when: list[Condition] = Field(default_factory=list)
    abort_when: list[Condition] = Field(default_factory=list)
    selector_hints: dict[str, Any] = Field(default_factory=dict)
    human_gate: bool = False
    needs_review: bool = False
    notes: list[str] = Field(default_factory=list)
    source_ref: str | None = None

    @model_validator(mode="before")
    @classmethod
    def _coerce_condition_mappings(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        for key in ("entry_when", "exit_when", "abort_when"):
            raw = data.get(key)
            if isinstance(raw, Mapping):
                data[key] = [Condition.parse(metric, expr) for metric, expr in raw.items()]
            elif isinstance(raw, list):
                data[key] = [
                    Condition.parse(item["metric"], item.get("expr", item.get("value")))
                    if isinstance(item, Mapping) and "op" not in item
                    else item
                    for item in raw
                ]
        return data

    @field_validator("selector_hints")
    @classmethod
    def _validate_selector_hints(cls, hints: dict[str, Any]) -> dict[str, Any]:
        if "allowed_action_types" in hints and not isinstance(
            hints["allowed_action_types"], list
        ):
            raise ValueError("selector_hints.allowed_action_types must be a list")

        if "target_land_levels" in hints:
            levels = hints["target_land_levels"]
            if not isinstance(levels, list) or not levels:
                raise ValueError("selector_hints.target_land_levels must be a non-empty list")
            if any(
                isinstance(level, bool)
                or not isinstance(level, int)
                or not 1 <= level <= 12
                for level in levels
            ):
                raise ValueError(
                    "selector_hints.target_land_levels entries must be integers from 1 to 12"
                )

        if "land_scope" in hints and hints["land_scope"] not in {
            "inner_city",
            "outer_city",
            "inner_and_outer",
        }:
            raise ValueError(
                "selector_hints.land_scope must be inner_city, outer_city, or inner_and_outer"
            )

        if "lineup_preset" in hints:
            preset = hints["lineup_preset"]
            if not isinstance(preset, str) or not preset.strip():
                raise ValueError("selector_hints.lineup_preset must be a non-empty string")
            hints = dict(hints)
            hints["lineup_preset"] = preset.strip()
        return hints


class OpeningRunbook(BaseModel):
    schema_version: str = "opening_runbook.v1"
    season: str
    generated_at: str
    sources: list[dict[str, Any]] = Field(default_factory=list)
    phases: list[PhaseDefinition]

    @model_validator(mode="after")
    def _validate_phases(self) -> "OpeningRunbook":
        if not self.phases:
            raise ValueError("Runbook must define at least one phase")
        seen: set[str] = set()
        for phase in self.phases:
            if phase.phase_id in seen:
                raise ValueError(f"Duplicate phase_id: {phase.phase_id}")
            seen.add(phase.phase_id)
        return self

    def phase(self, phase_id: str) -> PhaseDefinition:
        for phase in self.phases:
            if phase.phase_id == phase_id:
                return phase
        raise KeyError(f"Unknown phase_id: {phase_id}")

    def phase_index(self, phase_id: str) -> int:
        for index, phase in enumerate(self.phases):
            if phase.phase_id == phase_id:
                return index
        raise KeyError(f"Unknown phase_id: {phase_id}")


class EscalationKind(str, Enum):
    ABORT_TRIGGERED = "abort_triggered"
    HUMAN_GATE = "human_gate"
    BLOCKED_TRANSITION = "blocked_transition"
    UNKNOWN_METRICS = "unknown_metrics"
    ACTION_FILTER_STUCK = "action_filter_stuck"
    RUNBOOK_COMPLETED = "runbook_completed"


class EscalationRoute(str, Enum):
    LLM_PLANNER = "llm_planner"
    HUMAN = "human"


class RunbookEscalation(BaseModel):
    kind: EscalationKind
    route: EscalationRoute
    phase_id: str
    details: dict[str, Any] = Field(default_factory=dict)


class RunbookDecision(BaseModel):
    phase_id: str
    previous_phase_id: str
    transitioned: bool = False
    completed: bool = False
    hold_reason: str | None = None
    human_gate_pending: str | None = None
    selector_hints: dict[str, Any] = Field(default_factory=dict)
    escalations: list[RunbookEscalation] = Field(default_factory=list)
    exit_result: dict[str, Any] = Field(default_factory=dict)
    abort_result: dict[str, Any] = Field(default_factory=dict)


def _resolve_metric(metrics: Mapping[str, Any], dotted: str) -> tuple[Any, bool]:
    if dotted in metrics:
        return metrics[dotted], True
    current: Any = metrics
    for part in dotted.split("."):
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        else:
            return None, False
    return current, True


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)
