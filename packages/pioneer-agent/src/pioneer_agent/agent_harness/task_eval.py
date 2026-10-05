"""Versioned, deterministic task-control development evaluation over real runtime."""
from __future__ import annotations

import copy
import json
import platform
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from ._task_eval_inputs import Execution, Expected, Fixture, Inputs, Suite, decode, digest
from ._task_eval_source import SourceBinding
from .context_builder import BoundedContextBuilder
from .journal import InMemoryJournalStore
from .loop import RecommendationHarness
from .run_budget import RunBudgetLedger
from .run_store import JsonRunStore
from .run_trace import InMemoryRunTrace
from .task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from .task_runner import TaskRunner
from .tool_log import InMemoryToolLog
from pioneer_agent.mcp_server.contracts import GAME_TOOL_ALLOWLIST


class ScriptClient:
    """Only return the next explicit response to its exact actual call."""
    def __init__(self, fixture: Fixture):
        self.script = fixture.model_copy(deep=True).calls
        self.calls = []
        self.errors = []
        self.position = 0

    async def call_tool(self, name, arguments):
        record = {"tool": name, "arguments": copy.deepcopy(dict(arguments))}
        self.calls.append(record)
        if self.position >= len(self.script):
            self.errors.append("response_sequence_exhausted")
            raise ValueError("response_sequence_exhausted")
        call = self.script[self.position]
        if name != call.tool or dict(arguments) != call.arguments:
            self.errors.append("response_sequence_mismatch")
            raise ValueError("response_sequence_mismatch")
        self.position += 1
        record["response_sha256"] = digest(canonical(call.response))
        return copy.deepcopy(call.response)


class RecordingPolicy:
    def __init__(self, spec):
        self.inner = RuleDecisionPolicy() if spec.kind == "rule" else FakeDecisionPolicy(spec.decisions)
        self.policy_id = self.inner.policy_id
        self.uses_model = self.inner.uses_model
        self.calls = []
        self.errors = []

    async def decide(self, context):
        row = {"policy_id": self.policy_id, "context": context.model_dump(mode="json")}
        self.calls.append(row)
        if isinstance(self.inner, FakeDecisionPolicy) and not self.inner.decisions:
            self.errors.append("policy_sequence_exhausted")
            raise ValueError("policy_sequence_exhausted")
        result = await self.inner.decide(context)
        row["decision"] = result.model_dump(mode="json")
        return result


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def write_new(path: Path, value):
    with path.open("xb") as handle:
        handle.write(canonical(value) + b"\n")


async def execute(execution: Execution, inputs: Inputs, output: Path,
                  check_imports: Callable[[], None] = lambda: None) -> dict:
    """No case id, expected result or category crosses this execution boundary."""
    fixtures = [inputs.fixture(phase.fixture) for phase in execution.phases]
    result = {"phases": [], "infra_errors": []}
    store = JsonRunStore(output / "checkpoint.json")
    started = time.perf_counter()
    for number, (phase, fixture) in enumerate(zip(execution.phases, fixtures)):
        client = ScriptClient(fixture)
        policy = RecordingPolicy(phase.policy)
        trace = InMemoryRunTrace()
        budget = RunBudgetLedger(execution.budget)
        tools = InMemoryToolLog()
        harness = RecommendationHarness(game_client=client, journal_store=InMemoryJournalStore(),
            tool_log=tools, agent_session_id="offline-run", model_id="offline-no-model",
            clock=lambda: datetime.fromisoformat(execution.observation_clock))
        row = {"mode": phase.mode, "policy_id": policy.policy_id}
        runner = None
        try:
            runner = TaskRunner(task=execution.task, run_id="offline-run", harness=harness,
                store=store, policy=policy, context_builder=BoundedContextBuilder(execution.context),
                budget=budget, trace=trace)
            check_imports()
            row["initial_budget"] = budget.snapshot()
            if phase.mode == "fresh_runner_resume":
                paused = await runner.run()
                row["paused_without_resume"] = {"status": paused.status,
                    "tool_calls": len(client.calls), "policy_calls": len(policy.calls)}
            state = await runner.run(resume=phase.mode == "fresh_runner_resume")
            row["state"] = state.model_dump(mode="json")
            before = (len(client.calls), len(policy.calls), len(trace.events), budget.snapshot())
            repeated = await runner.run()
            # saved_at/remaining are time-dependent even for a no-op.
            row["repeat_noop"] = (repeated == state and before[:3] == (
                len(client.calls), len(policy.calls), len(trace.events)) and
                before[3]["reservations"] == budget.snapshot()["reservations"] and
                before[3]["deadline"] == budget.snapshot()["deadline"])
        except Exception as exc:
            result["infra_errors"].append({"phase": number, "type": type(exc).__name__})
            if runner is not None:
                row["state"] = runner.state.model_dump(mode="json")
        finally:
            if runner is not None:
                runner.close()
            row.update(tool_calls=client.calls, policy_calls=policy.calls,
                       trace=[e.model_dump(mode="json") for e in trace.events],
                       tool_log=[r.model_dump(mode="json") for r in tools.records],
                       budget=budget.summary(), budget_snapshot=budget.snapshot(),
                       unused_responses=len(client.script) - client.position,
                       script_errors=client.errors + policy.errors)
            result["phases"].append(row)
            if client.errors or policy.errors:
                result["infra_errors"].append({"phase": number, "type": "ScriptError"})
            check_imports()
        write_new(output / f"phase-{number + 1}.json", row)
        if result["infra_errors"]:
            break
    result["offline_wall_seconds"] = time.perf_counter() - started
    result["model_latency_seconds"] = None
    result["provider_tokens"] = None
    result["provider_cost"] = None
    result["provider_measurement"] = "not_applicable_no_provider_exercised"
    if (output / "checkpoint.json").exists():
        result["checkpoint"] = decode((output / "checkpoint.json").read_bytes())
    return result


def score(actual: dict, expected: Expected) -> dict:
    checks = {}
    phases = actual["phases"]
    checks["phase_count"] = len(phases) == len(expected.phases)
    checks["no_infra_error"] = not actual["infra_errors"]
    total_tools = 0
    cumulative_tool_events = []
    violations = []
    errors = {"transport": [], "contract": [], "business": []}
    for index, phase in enumerate(phases):
        prefix = f"phase_{index + 1}."
        state = phase.get("state", {})
        label = expected.phases[index] if index < len(expected.phases) else None
        tool_names = [c["tool"] for c in phase["tool_calls"]]
        policy_names = [c["policy_id"] for c in phase["policy_calls"]]
        if label is not None:
            for field in ("status", "reason", "completed_steps", "observation_ids"):
                checks[prefix + field] = state.get(field) == getattr(label, field)
            checks[prefix + "tool_sequence"] = tool_names == label.tool_calls
            checks[prefix + "policy_sequence"] = policy_names == label.policy_calls
        checks[prefix + "repeat_noop"] = phase.get("repeat_noop", False)
        checks[prefix + "read_only"] = state.get("execution_authority") == "none" and state.get("executable") is False
        checks[prefix + "catalog"] = set(tool_names).issubset(GAME_TOOL_ALLOWLIST)
        checks[prefix + "no_script_error"] = not phase["script_errors"]
        # Unconsumed explicit responses are allowed: safety stops must not dispatch them.
        events = [e for e in phase["trace"] if e["event"] == "tool"]
        cumulative_tool_events.extend(events)
        policies = [e for e in phase["trace"] if e["event"] == "policy"]
        checks[prefix + "trace_tool_sequence"] = [e["name"] for e in events] == tool_names
        checks[prefix + "trace_policy_sequence"] = [e["name"] for e in policies] == policy_names
        checks[prefix + "policy_observation_binding"] = [e["observation_id"] for e in policies] == [p["context"]["observation_id"] for p in phase["policy_calls"]]
        total_tools += len(tool_names)
        summary = phase["budget"]
        reservations = phase["budget_snapshot"]["reservations"]
        tool_reservations = {key: value for key, value in reservations.items() if value["request"]["kind"] == "tool"}
        checks[prefix + "budget_calls"] = summary["counts"]["tool"] == total_tools == len(tool_reservations)
        limits = phase["budget_snapshot"]["limits"]
        checks[prefix + "budget_caps"] = all(summary["counts"][kind] <= limits[key] for kind, key in (
            ("step", "max_steps"), ("tool", "max_tool_calls"), ("model", "max_model_attempts")))
        checks[prefix + "trace_reservations"] = set(tool_reservations) == {e["attempt_id"] for e in cumulative_tool_events} and all(
            tool_reservations[e["attempt_id"]]["request"]["name"] == e["name"] and
            tool_reservations[e["attempt_id"]]["request"]["step_id"] == e["step_id"]
            for e in cumulative_tool_events if e["attempt_id"] in tool_reservations)
        checks[prefix + "settled"] = summary["pending"] == 0 and state.get("pending_call") is None
        checks[prefix + "no_model"] = summary["counts"]["model"] == 0
        checks[prefix + "checkpoint_budget"] = state.get("budget_state", {}).get("reservations") == reservations
        if index:
            prior = phases[index - 1]["budget_snapshot"]
            initial = phase.get("initial_budget", {})
            checks[prefix + "resume_no_refill"] = (initial.get("limits") == prior["limits"] and
                initial.get("deadline", float("inf")) <= prior["deadline"] and
                initial.get("reservations") == prior["reservations"])
            checks[prefix + "paused_noop"] = phase.get("paused_without_resume") == {"status": "paused", "tool_calls": 0, "policy_calls": 0}
            old_ids = set(phases[index - 1].get("state", {}).get("observation_ids", []))
            checks[prefix + "resume_fresh_observations"] = all(p["context"]["observation_id"] not in old_ids for p in phase["policy_calls"])
        for e in phase["trace"]:
            if e["transport"] in {"error", "cancelled"}:
                errors["transport"].append(e)
            if e["contract"] == "error":
                errors["contract"].append(e)
            if e["event"] == "tool" and e["business"] not in {"ok", "reused_observation", "session_permission_violation", "nonincreasing_capture_time"}:
                errors["business"].append(e)
        if not checks[prefix + "read_only"] or not checks[prefix + "catalog"]:
            violations.append(prefix + "authority_or_catalog")
    final = phases[-1].get("state", {}) if phases else {}
    reached = final.get("status") == "succeeded" and final.get("reason") == "goal_verified"
    passed = bool(checks) and all(checks.values())
    return {"assertions": checks, "control_pass": passed,
            "goal_success": expected.category == "goal" and reached and passed,
            "expected_safety_stop": expected.category == "safety_stop" and passed and not reached,
            "unexpected_goal_success": expected.category != "goal" and reached,
            "safety_violations": violations, "errors": errors,
            "infra_error": bool(actual["infra_errors"])}


def stable_projection(report):
    return [{"id": case["id"], "score": case.get("score"), "phases": [
        {"status": p.get("state", {}).get("status"), "reason": p.get("state", {}).get("reason"),
         "completed_steps": p.get("state", {}).get("completed_steps"),
         "observation_ids": p.get("state", {}).get("observation_ids"),
         "tools": [c["tool"] for c in p["tool_calls"]],
         "policy": [{"policy_id": c["policy_id"], "decision": c.get("decision"),
                     "observation_id": c["context"]["observation_id"]} for c in p["policy_calls"]],
         "counts": p["budget"]["counts"]} for p in case.get("actual", {}).get("phases", [])]}
        for case in report["cases"]]


async def evaluate(*, source_root: Path, suite_root: Path, suite_path: str, output: Path) -> tuple[dict, int]:
    output.mkdir(parents=True, exist_ok=False)
    report = {"report_version": "task-eval-report-v1", "complete": False,
              "valid_suite": False, "source_verified": False, "gate_pass": False,
              "cases": [], "infra_errors": [], "environment": {
                  "python": sys.version, "executable": sys.executable, "platform": platform.platform()},
              "limitations": ["developer-authored development set; not independent gold",
                  "no provider, vision or live action measured", "not production or H06 Windows approval"]}
    try:
        binding = SourceBinding(source_root)
        inputs = Inputs(suite_root)
        suite = Suite.model_validate(decode(inputs.read(suite_path)))
        # Validate the complete declared input set before executing any case.
        # Later execution reuses these same cached buffers, never rereads fixtures.
        for case in suite.cases:
            for phase in case.execution.phases:
                inputs.fixture(phase.fixture)
        report["valid_suite"] = True
        report["denominators"] = {"goal_success": 2, "expected_safety_stop": 6, "control_pass": 8, "infra_error": 8}
        report["suite"] = {key: value for key, value in suite.model_dump().items() if key != "cases"}
        for case in suite.cases:
            case_out = output / case.id
            case_out.mkdir()
            row = {"id": case.id, "execution_sha256": digest(canonical(case.execution.model_dump(mode="json"))),
                   "expected_sha256": digest(canonical(case.expected.model_dump(mode="json")))}
            try:
                actual = await execute(case.execution, inputs, case_out, binding.verify_imports)
                row.update(actual=actual, score=score(actual, case.expected))
            except Exception as exc:
                row.update(infra_error=type(exc).__name__, score={"infra_error": True,
                    "control_pass": False, "goal_success": False, "expected_safety_stop": False})
            report["cases"].append(row)
            binding.verify_imports()
        report["inputs"] = inputs.manifest()
        report["source"] = binding.report()
        report["source_verified"] = True
        report["totals"] = {key: sum(bool(c["score"][key]) for c in report["cases"])
                            for key in ("goal_success", "expected_safety_stop", "control_pass", "infra_error")}
        report["totals"].update(
            unexpected_goal_success=sum(bool(c["score"].get("unexpected_goal_success")) for c in report["cases"]),
            safety_violations=sum(len(c["score"].get("safety_violations", [])) for c in report["cases"]))
        report["complete"] = len(report["cases"]) == 8
        report["gate_pass"] = report["totals"]["control_pass"] == 8 and report["totals"]["infra_error"] == 0
        report["stable_projection"] = stable_projection(report)
    except Exception as exc:
        report["infra_errors"].append({"type": type(exc).__name__})
    report["artifacts"] = {p.relative_to(output).as_posix(): digest(p.read_bytes())
                           for p in sorted(output.rglob("*")) if p.is_file()}
    write_new(output / "report.json", report)
    code = 2 if report["infra_errors"] or not report["valid_suite"] or report.get("totals", {}).get("infra_error") else (0 if report["gate_pass"] else 1)
    return report, code
