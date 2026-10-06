"""Repository-built readonly recipes; resolving one never runs a task."""
from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr, model_validator

from pioneer_agent.agent_harness.task_contracts import TaskSpec
from pioneer_agent.runbook.models import Condition, ConditionSetResult, ConditionStatus, _resolve_metric, evaluate_all


class _Strict(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid")


class ChapterParameters(_Strict):
    target_chapter: StrictInt = Field(ge=1, le=1000)


class _Template(_Strict):
    task_version: Literal[1] = 1
    task_id_format: Literal["chapter-observer@1.0.0:target-{target_chapter}"] = "chapter-observer@1.0.0:target-{target_chapter}"
    goal_format: Literal["Observe chapter >= {target_chapter} (read-only)"] = "Observe chapter >= {target_chapter} (read-only)"
    success_metric: Literal["progress.current_chapter_id"] = "progress.current_chapter_id"
    success_op: Literal[">="] = ">="
    success_parameter: Literal["target_chapter"] = "target_chapter"
    stop_when: list[Condition] = Field(default_factory=list)
    required_domains: list[StrictStr] = Field(default_factory=lambda: ["chapter_panel"])
    allowed_tools: list[StrictStr] = Field(default_factory=lambda: [
        "session_status", "observe_game", "get_runtime_state", "list_action_candidates"])
    max_steps: Literal[3] = 3
    wait_seconds: Literal[0] = 0
    execution_authority: Literal["none"] = "none"
    executable: Literal[False] = False


class SkillDefinition(_Strict):
    registry_schema: Literal[1] = 1
    skill_id: StrictStr
    version: StrictStr
    admission: Literal["repository_builtin_allowlist"] = "repository_builtin_allowlist"
    parameter_schema: dict[str, Any]
    preconditions: list[Condition]
    template: _Template
    template_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    execution_authority: Literal["none"] = "none"
    executable: Literal[False] = False


class SkillCompilation(_Strict):
    status: Literal["ready", "blocked"]
    reason: Literal["preconditions_satisfied", "precondition_not_satisfied", "precondition_unknown"]
    skill_id: StrictStr
    version: StrictStr
    admission: Literal["repository_builtin_allowlist"] = "repository_builtin_allowlist"
    template_digest: StrictStr = Field(pattern=r"^[0-9a-f]{64}$")
    parameters: ChapterParameters
    preflight: ConditionSetResult
    missing_metrics: list[StrictStr]
    task: TaskSpec | None
    task_digest: StrictStr | None = Field(pattern=r"^[0-9a-f]{64}$")
    execution_authority: Literal["none"] = "none"
    executable: Literal[False] = False

    @model_validator(mode="after")
    def consistent_result(self):
        ready = self.status == "ready"
        if ready != (self.preflight.status == ConditionStatus.SATISFIED):
            raise ValueError("compilation status must match preflight")
        if ready:
            if self.task is None or self.task_digest is None or self.reason != "preconditions_satisfied":
                raise ValueError("ready compilation requires task and digest")
        elif self.task is not None or self.task_digest is not None:
            raise ValueError("blocked compilation must not expose a task")
        return self


def _digest(value: dict) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _chapter_definition() -> SkillDefinition:
    definition = SkillDefinition(skill_id="chapter-observer", version="1.0.0",
        parameter_schema=ChapterParameters.model_json_schema(),
        preconditions=[Condition(metric="progress.current_chapter_id", op=">=", value=1)],
        template=_Template(), template_digest="0" * 64)
    definition.template_digest = _digest(definition.model_dump(mode="json", exclude={"template_digest"}))
    return definition


# No public registration/catalog parameter. In-process monkeypatching is not a
# trust boundary; an external object's reviewed claim is never consulted.
_BUILTINS = (_chapter_definition(),)


def _catalog() -> dict[tuple[str, str], SkillDefinition]:
    catalog = {}
    for item in _BUILTINS:
        definition = SkillDefinition.model_validate(item.model_dump(mode="json"))
        key = (definition.skill_id, definition.version)
        if key in catalog:
            raise ValueError("duplicate builtin skill ID/version")
        catalog[key] = definition
    # Validate all entries, not only the requested one. The exact descriptor
    # includes the fixed four-tool list rather than a widening global catalog.
    expected = _chapter_definition()
    for key, definition in catalog.items():
        if key != ("chapter-observer", "1.0.0") or definition != expected:
            raise ValueError("skill is not in the repository builtin allowlist")
    return catalog


def list_skills() -> list[SkillDefinition]:
    return [definition.model_copy(deep=True) for definition in _catalog().values()]


def resolve_skill(skill_id: str, version: str) -> SkillDefinition:
    if type(skill_id) is not str or not skill_id.strip() or type(version) is not str or not version.strip():
        raise ValueError("explicit skill ID and exact version required")
    definition = _catalog().get((skill_id, version))
    if definition is None:
        raise ValueError("unknown skill ID/version")
    return definition.model_copy(deep=True)


def compile_skill(skill_id: str, version: str, parameters: dict, *, metrics: dict[str, Any]) -> SkillCompilation:
    definition = resolve_skill(skill_id, version)
    if type(parameters) is not dict:
        raise ValueError("parameters must be an object")
    params = ChapterParameters.model_validate(parameters)
    if type(metrics) is not dict or any(type(key) is not str for key in metrics):
        raise ValueError("metrics must be a string-keyed object")
    metric = "progress.current_chapter_id"
    observed, found = _resolve_metric(metrics, metric)
    # Local type restriction only. A float/bool must not borrow numeric DSL
    # semantics. The caller's metrics and shared conditions are never changed.
    projected = {metric: observed if found and type(observed) is int else None}
    preflight = evaluate_all(definition.preconditions, projected)
    common = dict(skill_id=definition.skill_id, version=definition.version,
        template_digest=definition.template_digest, parameters=params.model_copy(deep=True),
        preflight=preflight, missing_metrics=preflight.missing_metrics)
    if preflight.status != ConditionStatus.SATISFIED:
        reason = "precondition_not_satisfied" if preflight.status == ConditionStatus.NOT_SATISFIED else "precondition_unknown"
        return SkillCompilation(status="blocked", reason=reason, task=None, task_digest=None, **common)
    target = params.target_chapter
    template = definition.template
    task = TaskSpec(version=1, task_id=f"chapter-observer@1.0.0:target-{target}",
        goal=f"Observe chapter >= {target} (read-only)",
        success_when=[Condition(metric=metric, op=">=", value=target)],
        stop_when=[], required_domains=list(template.required_domains),
        allowed_tools=list(template.allowed_tools), max_steps=3, wait_seconds=0,
        execution_authority="none", executable=False)
    return SkillCompilation(status="ready", reason="preconditions_satisfied", task=task,
        task_digest=_digest(task.model_dump(mode="json")), **common)
