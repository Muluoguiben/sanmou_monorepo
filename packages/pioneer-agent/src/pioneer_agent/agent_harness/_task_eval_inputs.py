"""H09a local development suite input boundary (not a public MCP protocol)."""
from __future__ import annotations

import hashlib
import json
import stat
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .context_builder import ContextLimits
from .contracts import structured_content, validate_game_response
from .run_budget import BudgetLimits
from .task_contracts import PolicyDecision, TaskSpec
from pioneer_agent.mcp_server.contracts import GAME_TOOL_ARGUMENTS


class InputError(ValueError):
    pass


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class FixtureRef(Strict):
    path: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class Policy(Strict):
    kind: Literal["rule", "fake"]
    decisions: list[PolicyDecision] = Field(max_length=100)

    @model_validator(mode="after")
    def valid_script(self):
        if (self.kind == "rule" and self.decisions) or (self.kind == "fake" and not self.decisions):
            raise ValueError("rule has no decisions; fake requires explicit decisions")
        return self


class Phase(Strict):
    mode: Literal["run", "fresh_runner_resume"]
    fixture: FixtureRef
    policy: Policy


class Execution(Strict):
    task: TaskSpec
    budget: BudgetLimits
    context: ContextLimits
    observation_clock: str
    phases: list[Phase] = Field(min_length=1, max_length=2)

    @field_validator("observation_clock")
    @classmethod
    def aware_clock(cls, value):
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("aware observation clock required")
        return value

    @model_validator(mode="after")
    def bounded(self):
        if self.phases[0].mode != "run" or any(p.mode != "fresh_runner_resume" for p in self.phases[1:]):
            raise ValueError("only run then fresh runner resume is supported")
        if self.task.max_steps > 100 or self.task.wait_seconds != 0 or self.budget.max_seconds > 300:
            raise ValueError("offline development execution must be bounded and non-waiting")
        return self


class ExpectedPhase(Strict):
    status: Literal["succeeded", "failed", "paused", "cancelled"]
    reason: str = Field(min_length=1)
    completed_steps: int = Field(ge=0)
    tool_calls: list[str] = Field(max_length=400)
    policy_calls: list[str] = Field(max_length=100)
    observation_ids: list[str] = Field(max_length=100)


class Expected(Strict):
    category: Literal["goal", "safety_stop"]
    phases: list[ExpectedPhase] = Field(min_length=1, max_length=2)


class Case(Strict):
    id: str = Field(pattern=r"^[a-z0-9][a-z0-9_-]{0,79}$")
    execution: Execution
    expected: Expected

    @model_validator(mode="after")
    def phase_lengths(self):
        if len(self.execution.phases) != len(self.expected.phases):
            raise ValueError("phase labels missing")
        return self


class Suite(Strict):
    version: Literal["task-development-v1"]
    split: Literal["development"]
    provenance: Literal["developer_authored_not_independent_gold"]
    independent_holdout: Literal[False]
    provider_exercised: Literal[False]
    live_action: Literal[False]
    cases: list[Case] = Field(min_length=8, max_length=8)

    @model_validator(mode="after")
    def denominators(self):
        if len({c.id for c in self.cases}) != len(self.cases):
            raise ValueError("duplicate case ids")
        if sum(c.expected.category == "goal" for c in self.cases) != 2:
            raise ValueError("v1 requires exactly 2 goal and 6 safety cases")
        return self


class Call(Strict):
    tool: str
    arguments: dict[str, Any]
    response: dict[str, Any]

    @model_validator(mode="after")
    def canonical(self):
        if self.tool not in GAME_TOOL_ARGUMENTS or self.arguments:
            raise ValueError("offline v1 only supports catalog tools without arguments")
        if set(self.response) != {"isError", "structuredContent"} or self.response["isError"] is not False:
            raise ValueError("explicit canonical successful transport envelope required")
        validate_game_response(self.tool, structured_content(self.response))
        return self


class Fixture(Strict):
    version: Literal["task-responses-v1"]
    source: Literal["explicit_synthetic_canonical_envelopes"]
    calls: list[Call] = Field(min_length=1, max_length=400)


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def safe_path(root: Path, relative: str) -> Path:
    rel = Path(relative)
    if rel.is_absolute() or not rel.parts or any(p in {"..", "."} for p in rel.parts) or "\\" in relative or ":" in relative:
        raise InputError("path_escape")
    current = root.absolute()
    for part in (*current.parents, current):
        if part.exists() and (part.is_symlink() or getattr(part.lstat(), "st_file_attributes", 0) & 0x400):
            raise InputError("linked_root")
    for part in rel.parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise InputError("linked_input")
    if not current.is_file() or not current.resolve().is_relative_to(root.resolve()):
        raise InputError("not_regular_input")
    return current


def decode(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise InputError("duplicate_json_key")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=lambda _: (_ for _ in ()).throw(InputError("nonfinite_json")))


class Inputs:
    """One read per unique input; parsing and SHA use the identical buffer."""
    def __init__(self, root: Path):
        self.root = root
        self.raw: dict[str, bytes] = {}

    def read(self, relative: str, expected_sha: str | None = None) -> bytes:
        if relative not in self.raw:
            path = safe_path(self.root, relative)
            if path.stat().st_size > 5_000_000:
                raise InputError("input_too_large")
            self.raw[relative] = path.read_bytes()
        raw = self.raw[relative]
        if expected_sha is not None and digest(raw) != expected_sha:
            raise InputError("fixture_digest_mismatch")
        return raw

    def fixture(self, ref: FixtureRef) -> Fixture:
        return Fixture.model_validate(decode(self.read(ref.path, ref.sha256)))

    def manifest(self):
        return {path: {"sha256": digest(raw), "bytes": len(raw)} for path, raw in sorted(self.raw.items())}
