"""Synthetic checker tests, NOT native Windows task-eval acceptance evidence."""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import types
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[3]
SPEC = importlib.util.spec_from_file_location("windows_task_eval_ci", ROOT / "scripts/check_windows_task_eval.py")
gate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gate)


class WindowsTaskEvalCITests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.output = self.root / "output"
        self.output.mkdir()
        self.commit, self.tree = "a" * 40, "b" * 40
        self.exe = "C:\\Python\\python.exe"
        self.inputs = {}
        for path in (ROOT / gate.SUITE).rglob("*.json"):
            relative = path.relative_to(ROOT / gate.SUITE).as_posix()
            raw = path.read_bytes()
            self.inputs[relative] = raw
            target = self.root / gate.SUITE / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
        self.launcher = "packages/pioneer-agent/src/pioneer_agent/app/task_eval.py"
        path = self.root / self.launcher
        path.parent.mkdir(parents=True, exist_ok=True)
        data = b"# Synthetic checker fixture; no evaluator implementation.\n"
        path.write_bytes(data)
        blob = hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()
        self.tracked = {self.launcher: blob}
        self.report = {
            "report_version": "task-eval-report-v1", "complete": True, "valid_suite": True,
            "source_verified": True, "gate_pass": True, "run_mode": "committed_cli",
            "infra_errors": [], "artifact_errors": {},
            "environment": {"platform": "Windows-SYNTHETIC", "executable": self.exe},
            "source": {"commit": self.commit, "tree": self.tree, "root": str(self.root),
                "source_verified": True, "module_source_verified": True,
                "launcher": {"bound": True, "mode": "module", "spec_name": "pioneer_agent.app.task_eval",
                    "file": str(path), "spec_origin": str(path), "raw_sha256": gate.sha(data)},
                "raw_byte_manifest": {self.launcher: {"blob": blob, "sha256": gate.sha(data), "bytes": len(data)}}},
            "inputs": {k: {"bytes": len(v), "sha256": gate.sha(v)} for k, v in self.inputs.items()},
            "denominators": dict(goal_success=2, expected_safety_stop=6, control_pass=8, infra_error=8),
            "totals": dict(goal_success=2, expected_safety_stop=6, control_pass=8, infra_error=0,
                           unexpected_goal_success=0, safety_violations=0), "cases": [], "artifacts": {}}
        suite = gate.decode(self.inputs["suite.json"])
        self.report["suite"] = {k: v for k, v in suite.items() if k != "cases"}
        for spec in suite["cases"]:
            goal = spec["expected"]["category"] == "goal"
            actual = {"infra_errors": [], "provider_measurement": "not_applicable_no_provider_exercised",
                      "model_latency_seconds": None, "provider_tokens": None, "provider_cost": None, "phases": []}
            for expected in spec["expected"]["phases"]:
                state = {k: expected[k] for k in ("status", "reason", "completed_steps", "observation_ids")}
                state.update(execution_authority="none", executable=False, pending_call=None,
                             task={"execution_authority": "none", "executable": False},
                             budget_state={"limits": {"max_model_attempts": 0}, "reservations": {}})
                actual["phases"].append({"state": state, "repeat_noop": True, "script_errors": [],
                    "budget": {"pending": 0, "counts": {"model": 0}},
                    "budget_snapshot": copy.deepcopy(state["budget_state"])})
            actual["checkpoint"] = {"owner_id": "synthetic", "revision": 1, "storage_version": 1,
                                    "state": copy.deepcopy(actual["phases"][-1]["state"])}
            score = {"control_pass": True, "infra_error": False, "goal_success": goal,
                     "observed_goal_verified": goal, "expected_safety_stop": not goal,
                     "unexpected_goal_success": False, "safety_violations": [], "assertions": {"synthetic": True}}
            self.report["cases"].append({"id": spec["id"], "score": score, "actual": actual})
        self.save_artifacts()

    def save_artifacts(self):
        self.report["artifacts"] = {}
        for case in self.report["cases"]:
            directory = self.output / case["id"]
            directory.mkdir(exist_ok=True)
            entries = {"checkpoint.json": case["actual"]["checkpoint"], "checkpoint.json.lock": {}}
            entries.update({f"phase-{i}.json": p for i, p in enumerate(case["actual"]["phases"], 1)})
            for name, value in entries.items():
                raw = json.dumps(value).encode()
                (directory / name).write_bytes(raw)
                self.report["artifacts"][case["id"] + "/" + name] = gate.sha(raw)
        (self.output / "report.json").write_bytes(self.raw())

    def raw(self):
        return json.dumps(self.report).encode()

    def validate(self):
        return gate.validate_report(self.raw(), root=self.root, output=self.output, commit=self.commit,
            tree=self.tree, executable=self.exe, inputs=self.inputs, tracked=self.tracked)

    def test_synthetic_positive_and_expected_safety_failures(self):
        self.assertEqual(self.validate()["control_pass"], 8)
        self.assertEqual(sum(c["actual"]["phases"][-1]["state"]["status"] == "failed"
                             for c in self.report["cases"]), 6)

    def test_contract_mutations_fail_closed(self):
        mutations = [
            ("complete", 1), ("valid_suite", False), ("source_verified", False), ("gate_pass", 1),
            ("environment.platform", "Linux-test"), ("environment.executable", "other"),
            ("source.commit", "c" * 40), ("source.tree", "d" * 40),
            ("source.source_verified", 1), ("source.launcher.mode", "direct_script"),
            ("totals.control_pass", 7), ("totals.infra_error", False),
            ("denominators.goal_success", True), ("suite.provider_exercised", True),
            ("suite.live_action", True), ("suite.independent_holdout", True),
            ("cases.0.score.control_pass", False), ("cases.0.score.assertions.synthetic", 1),
            ("cases.0.score.infra_error", True), ("cases.0.actual.provider_tokens", 0),
            ("cases.0.actual.phases.0.state.execution_authority", "execute"),
            ("cases.0.actual.phases.0.state.task.executable", True),
            ("cases.0.actual.phases.0.budget.counts.model", 1),
            ("cases.0.actual.phases.0.budget.counts.model", False),
            ("cases.0.actual.phases.0.budget.pending", 1),
            ("cases.0.actual.phases.0.repeat_noop", False),
            ("cases.0.actual.phases.0.state.completed_steps", True),
            ("cases.0.actual.phases.0.state.budget_state.limits.max_model_attempts", 1),
            ("cases.0.actual.phases.0.budget_snapshot.reservations", {"r": {"request": {"kind": "model"}}}),
            ("cases.0.actual.checkpoint.state.budget_state.limits.max_model_attempts", 1),
            ("cases.0.actual.checkpoint.state.task.execution_authority", "execute"),
        ]
        baseline = copy.deepcopy(self.report)
        for path, value in mutations:
            with self.subTest(path=path, value=value):
                self.report = copy.deepcopy(baseline)
                target = self.report
                keys = path.split(".")
                for key in keys[:-1]:
                    target = target[int(key)] if isinstance(target, list) else target[key]
                target[keys[-1]] = value
                self.save_artifacts()
                with self.assertRaises((ValueError, KeyError)):
                    self.validate()

    def test_missing_and_duplicate_cases(self):
        for cases in (self.report["cases"][:-1], [self.report["cases"][0]] * 8):
            with self.subTest(count=len(cases)):
                self.report["cases"] = cases
                with self.assertRaises(ValueError):
                    self.validate()

    def test_artifact_bytes_and_manifest_coverage(self):
        name = next(iter(self.report["artifacts"]))
        (self.output / name).write_bytes(b"{}")
        with self.assertRaises(ValueError):
            self.validate()
        self.save_artifacts()
        self.report["artifacts"]["../escape"] = "0" * 64
        with self.assertRaises(ValueError):
            self.validate()
        self.save_artifacts()
        (self.output / "extra.json").write_bytes(b"{}")
        with self.assertRaises(ValueError):
            self.validate()

    def test_source_byte_and_input_digest_mismatch(self):
        self.report["inputs"]["suite.json"]["sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            self.validate()
        self.report["inputs"]["suite.json"]["sha256"] = gate.sha(self.inputs["suite.json"])
        (self.root / self.launcher).write_bytes(b"changed")
        with self.assertRaises(ValueError):
            self.validate()

    def test_links_and_relative_paths(self):
        for name in ("../x", "x/../y", "x//y", "C:/x", "/x", "x\\y", "x:stream"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                gate.read_file(self.output, name)
        target = self.output / "hardlink"
        os.link(self.output / "report.json", target)
        with self.assertRaises(ValueError):
            gate.read_file(self.output, "hardlink")
        target.unlink()
        with patch.object(gate, "physical", side_effect=ValueError("linked_path")):
            with self.assertRaises(ValueError):
                self.validate()

    def test_nonlocal_paths_rejected_before_io(self):
        for name in ("relative", "/tmp/x", "\\\\server\\share", "\\\\wsl$\\Ubuntu\\x", "C:relative", "C:\\x\\..\\y"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                gate.local_windows_path(name)

    def test_physical_reparse_rejected(self):
        fake = types.SimpleNamespace(st_mode=0o40755, st_file_attributes=0x400)
        with patch.object(Path, "lstat", return_value=fake), self.assertRaises(ValueError):
            gate.physical(self.root)

    def test_strict_json(self):
        for raw in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}'):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                gate.decode(raw)

    def test_exact_type_and_report_limit(self):
        for actual, expected in ((False, 0), (True, 1), (1, True), (0, False)):
            with self.subTest(actual=actual), self.assertRaises(ValueError):
                gate.exact(actual, expected, "test")
        with self.assertRaises(ValueError):
            list(gate.evidence_lines(b"x" * (gate.MAX_REPORT + 1)))

    def test_log_roundtrip_and_timestamp_prefix(self):
        raw = self.raw()
        lines = list(gate.evidence_lines(raw))
        self.assertEqual(gate.decode_log(lines), raw)
        self.assertEqual(gate.decode_log(["2026-10-06T12:34:56.123Z " + s for s in lines]), raw)

    def test_empty_report_evidence_roundtrip(self):
        lines = list(gate.evidence_lines(b""))
        self.assertEqual(len(lines), 2)
        self.assertEqual(lines[0].split()[2:], ["0", gate.sha(b""), "0"])
        self.assertEqual(gate.decode_log(lines), b"")
        with self.assertRaises(ValueError):
            gate.decode(b"")

    def test_exit_zero_empty_report_retained_but_gate_red(self):
        original = self.save_artifacts
        def empty_report():
            original()
            (self.output / "report.json").write_bytes(b"")
        self.save_artifacts = empty_report
        code, log, _ = self.orchestration()
        self.assertEqual(code, 1)
        self.assertIn('"child_returncode": 0', log)
        self.assertEqual(gate.decode_log(log.splitlines()), b"")
        self.assertIn('"error_type": "JSONDecodeError"', log)
        self.assertNotIn('"h09b_gate_pass": true', log)

    def test_log_corruption_missing_duplicate_order_limits(self):
        lines = list(gate.evidence_lines(self.raw()))
        variants = [lines[:-1], lines[1:], lines[:1] + lines[2:], lines[:2] + lines[1:],
                    lines[:1] + [lines[2], lines[1]] + lines[3:], lines + [lines[-1]],
                    [lines[0], lines[0]] + lines[1:], ["x" * (gate.MAX_LOG + 1)],
                    [lines[0].replace(str(len(self.raw())), str(gate.MAX_REPORT + 1))] + lines[1:],
                    lines[:1] + [lines[1] + "AAAA"] + lines[2:]]
        for index, variant in enumerate(variants):
            with self.subTest(index=index), self.assertRaises(ValueError):
                gate.decode_log(variant)

    def orchestration(self, code=0, missing=False, timeout=False, output_exists=False):
        """Mocked platform/process orchestration only; never native evidence."""
        temp = self.root / "runner-temp"
        temp.mkdir()
        parent = temp / "owned"
        parent.mkdir()
        self.output = parent / "evaluation"
        if output_exists:
            self.output.mkdir()
        commands = []
        def process(command, **kwargs):
            commands.append((command, kwargs))
            if command[0] == "git":
                args = command[3:]
                if args == ["rev-parse", "HEAD"]:
                    data = self.commit.encode()
                elif args == ["rev-parse", "HEAD^{tree}"]:
                    data = self.tree.encode()
                elif args[0] == "ls-tree":
                    data = b"100644 blob " + self.tracked[self.launcher].encode() + b"\t" + self.launcher.encode() + b"\0"
                else:
                    data = self.inputs[args[2].split(gate.SUITE + "/", 1)[1]]
                return subprocess.CompletedProcess(command, 0, stdout=data)
            self.assertEqual(command[:3], [self.exe, "-m", "pioneer_agent.app.task_eval"])
            self.assertNotIn("shell", kwargs)
            self.assertGreater(kwargs["timeout"], 0)
            self.assertLessEqual(kwargs["timeout"], gate.TIMEOUT)
            self.assertFalse(self.output.exists())
            self.output.mkdir()
            if not missing:
                self.save_artifacts()
            if timeout:
                raise subprocess.TimeoutExpired(command, 1)
            return subprocess.CompletedProcess(command, code)
        environment = {"RUNNER_OS": "Windows", "RUNNER_TEMP": str(temp), "GITHUB_SHA": self.commit}
        with contextlib.ExitStack() as stack:
            stack.enter_context(patch.object(gate, "__file__", str(self.root / "scripts/check_windows_task_eval.py")))
            stack.enter_context(patch.object(gate, "os", types.SimpleNamespace(name="nt", environ=environment, pathsep=os.pathsep)))
            stack.enter_context(patch.object(gate, "sys", types.SimpleNamespace(platform="win32", executable=self.exe)))
            stack.enter_context(patch.object(gate.platform, "system", return_value="Windows"))
            stack.enter_context(patch.object(gate, "local_windows_path", side_effect=Path))
            stack.enter_context(patch.object(gate.tempfile, "mkdtemp", return_value=str(parent)))
            stack.enter_context(patch.object(gate.subprocess, "run", side_effect=process))
            capture = stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
            result = gate.main()
        return result, capture.getvalue(), commands

    def test_mocked_cli_positive(self):
        code, log, commands = self.orchestration()
        self.assertEqual(code, 0, log[-500:])
        self.assertEqual(gate.decode_log(log.splitlines()), self.raw())
        self.assertEqual(sum(c[0][0] == self.exe for c in commands), 1)

    def test_exit_zero_without_report_is_red(self):
        code, log, _ = self.orchestration(missing=True)
        self.assertEqual(code, 1)
        self.assertIn('"child_returncode": 0', log)
        self.assertNotIn('"h09b_gate_pass": true', log)

    def test_nonzero_child_preserves_report_before_red(self):
        code, log, _ = self.orchestration(code=2)
        self.assertEqual(code, 1)
        self.assertEqual(gate.decode_log(log.splitlines()), self.raw())
        self.assertIn('"child_returncode": 2', log)

    def test_timeout_preserves_report_before_red(self):
        code, log, _ = self.orchestration(timeout=True)
        self.assertEqual(code, 1)
        self.assertEqual(gate.decode_log(log.splitlines()), self.raw())
        self.assertIn("TimeoutExpired", log)

    def test_existing_output_never_launched_or_overwritten(self):
        code, log, commands = self.orchestration(output_exists=True)
        self.assertEqual(code, 1)
        self.assertIn("output_exists", log)
        self.assertFalse(any(c[0][0] == self.exe for c in commands))

    def test_non_native_main_rejected(self):
        with patch.object(gate.platform, "system", return_value="Linux"), contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(gate.main(), 1)


if __name__ == "__main__":
    unittest.main()
