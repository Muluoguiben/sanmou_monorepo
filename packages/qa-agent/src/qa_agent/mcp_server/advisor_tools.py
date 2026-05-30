from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any


class AdvisorReplayTools:
    def __init__(
        self,
        *,
        workspace_root: Path,
        python_executable: str | None = None,
        timeout_seconds: int = 30,
    ) -> None:
        self.workspace_root = workspace_root.resolve()
        self.pioneer_root = self.workspace_root / "packages" / "pioneer-agent"
        self.fixture_dir = self.pioneer_root / "tests" / "fixtures"
        self.expectations_path = self.pioneer_root / "tests" / "golden" / "advisor_fixture_expectations.json"
        self.python_executable = python_executable or sys.executable
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_qa_project_root(cls, qa_project_root: Path) -> "AdvisorReplayTools":
        return cls(workspace_root=qa_project_root.resolve().parents[1])

    def golden_replay_status(self, *, include_fixture_results: bool = True) -> dict[str, Any]:
        fixtures = self._fixture_paths()
        expectation_payload = self._load_expectation_payload()
        expectations = self._expectations_from_payload(expectation_payload)
        required_pages = list(expectation_payload.get("required_pr5_pages") or [])
        pr5_expectations = {
            name: item
            for name, item in expectations.items()
            if isinstance(item, dict) and item.get("page")
        }
        covered_pages = sorted(
            {str(item["page"]) for item in pr5_expectations.values() if item.get("page")}
        )
        screenshot_files = sorted(
            path
            for path in (self.fixture_dir / "screenshots").rglob("*")
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
        pr5_locked_field_coverage = self._pr5_locked_field_coverage(pr5_expectations)
        payload: dict[str, Any] = {
            "workspace_root": str(self.workspace_root),
            "pioneer_root": str(self.pioneer_root),
            "fixture_count": len(fixtures),
            "screenshot_fixture_count": len(screenshot_files),
            "expectation_count": len(expectations),
            "expectation_version": expectation_payload.get("version"),
            "expectations_path": str(self.expectations_path),
            "pr5_fixture_count": len(pr5_expectations),
            "pr5_page_coverage": {
                "required": required_pages,
                "covered": covered_pages,
                "missing": sorted(set(required_pages) - set(covered_pages)),
            },
            "pr5_locked_fields": {
                "action": sum("expected_action_type" in item for item in pr5_expectations.values()),
                "report_evidence": sum(bool(item.get("required_report_evidence")) for item in pr5_expectations.values()),
                "action_evidence": sum(bool(item.get("required_action_evidence")) for item in pr5_expectations.values()),
                "report_confidence": sum("expected_report_confidence" in item for item in pr5_expectations.values()),
                "action_confidence": sum("expected_action_confidence" in item for item in pr5_expectations.values()),
                "dispatch_gate": sum("expected_dispatch_status" in item for item in pr5_expectations.values()),
                "runtime_dispatch_gate": sum("expected_dispatch_status" in item for item in pr5_expectations.values()),
                "terminal_dispatch_gate": sum(
                    "expected_dispatch_terminal_for_verifier" in item
                    for item in pr5_expectations.values()
                ),
            },
            "pr5_locked_field_coverage": pr5_locked_field_coverage,
            "missing_expectations": [
                path.name for path in fixtures if path.name not in expectations
            ],
            "extra_expectations": sorted(
                name for name in expectations if not (self.fixture_dir / name).exists()
            ),
            "results": [],
            "failures": [],
            "fixture_replay_checked": include_fixture_results,
        }
        payload["desktop_evidence_display_gate"] = self._desktop_evidence_display_gate()
        comparisons: list[dict[str, Any]] = []
        if include_fixture_results:
            replay_results = self._run_replay(fixtures)
            comparisons = [self._compare_result(item, expectations) for item in replay_results]
            payload["results"] = comparisons
            payload["failures"] = [item for item in comparisons if not item["matched"]]
            payload["pr6_verifier_coverage"] = self._pr6_verifier_coverage(comparisons)
            payload["pr5_dispatch_gate_coverage"] = self._pr5_dispatch_gate_coverage(comparisons)
            payload["pr12_runtime_dispatch_coverage"] = self._pr12_runtime_dispatch_coverage(comparisons)
            payload["pr15_terminal_dispatch_gate_coverage"] = (
                self._pr15_terminal_dispatch_gate_coverage(comparisons)
            )
            payload["pr5_low_risk_terminal_dispatch_coverage"] = (
                self._low_risk_terminal_dispatch_coverage(comparisons)
            )
        else:
            payload["pr6_verifier_coverage"] = {
                "checked": False,
                "required": PR6_LOW_RISK_ACTIONS,
                "covered": [],
                "missing": [],
            }
            payload["pr5_dispatch_gate_coverage"] = {
                "checked": False,
                "required_count": 0,
                "matched_count": 0,
                "failures": [],
            }
            payload["pr12_runtime_dispatch_coverage"] = {
                "checked": False,
                "required_count": 0,
                "matched_count": 0,
                "failures": [],
            }
            payload["pr15_terminal_dispatch_gate_coverage"] = {
                "checked": False,
                "required_count": 0,
                "matched_count": 0,
                "failures": [],
            }
            payload["pr5_low_risk_terminal_dispatch_coverage"] = {
                "checked": False,
                "required": PR6_LOW_RISK_ACTIONS,
                "covered": [],
                "covered_fixtures": {},
                "missing": [],
                "observed": [],
            }
        payload["low_risk_verifier_readiness"] = self._low_risk_verifier_readiness(
            payload["pr6_verifier_coverage"],
            payload["pr5_low_risk_terminal_dispatch_coverage"],
        )
        payload["low_risk_terminal_source_review"] = self._low_risk_terminal_source_review(
            payload["pr5_low_risk_terminal_dispatch_coverage"],
            expectations,
            comparisons,
        )
        payload["attention_reasons"] = self._attention_reasons(payload)
        payload["status"] = "attention" if payload["attention_reasons"] else "ok"
        payload["architecture_iteration_closure_gate"] = (
            self._architecture_iteration_closure_gate(payload)
        )
        return payload

    def fixture_eval(self, *, fixture: str, expected_action_type: str | None = None) -> dict[str, Any]:
        fixture_path = self._resolve_fixture_path(fixture)
        expectations = self._load_expectations()
        expectation = expectations.get(fixture_path.name, {})
        replay_result = self._run_replay([fixture_path])[0]
        if expected_action_type is None and fixture_path.name in expectations:
            expected_action_type = expectation.get("expected_action_type")
        comparison_expectation = dict(expectation)
        comparison_expectation["expected_action_type"] = expected_action_type
        comparison = self._compare_result(replay_result, {fixture_path.name: comparison_expectation})
        return {
            "fixture": comparison["fixture"],
            "matched": comparison["matched"],
            "page": expectation.get("page"),
            "screenshot": expectation.get("screenshot"),
            "expected_action_type": comparison["expected_action_type"],
            "actual_action_type": comparison["actual_action_type"],
            "expected_report_confidence": expectation.get("expected_report_confidence"),
            "expected_action_confidence": expectation.get("expected_action_confidence"),
            "required_report_evidence": expectation.get("required_report_evidence", []),
            "required_action_evidence": expectation.get("required_action_evidence", []),
            "selection_mode": comparison["selection_mode"],
            "top_score_gap": comparison["top_score_gap"],
            "ranked_action_count": comparison["ranked_action_count"],
            "dispatch_gate": comparison["dispatch_gate"],
            "runtime_dispatch_gate": comparison["runtime_dispatch_gate"],
            "terminal_dispatch_gate": comparison["terminal_dispatch_gate"],
            "low_risk_readiness": self._fixture_low_risk_readiness(comparison),
            "semantic_target_gate": replay_result.get("semantic_target_gate"),
            "runtime_dispatch": replay_result.get("runtime_dispatch"),
            "verifier_gate": replay_result.get("verifier_gate"),
            "verifier_spec": replay_result.get("verifier_spec"),
            "terminal_source_review": self._fixture_terminal_source_review(comparison, expectation),
            "selected_action": replay_result.get("selected_action"),
            "selection_reason": replay_result.get("selection_reason"),
            "derived_state": replay_result.get("derived_state"),
        }

    def terminal_source_evidence_eval(
        self,
        *,
        action_type: str,
        terminal_source_evidence: dict[str, Any],
        fixture: str | None = None,
        page: str | None = None,
    ) -> dict[str, Any]:
        expectation = {
            "page": page or terminal_source_evidence.get("page"),
            "terminal_source_evidence": terminal_source_evidence,
        }
        fixture_name = fixture or f"live_{action_type}_terminal_trace.json"
        review = self._terminal_source_evidence_review(
            action_type=action_type,
            fixture=fixture_name,
            expectation=expectation,
        )
        requirements = _terminal_source_requirements([action_type])
        capture_plan = _terminal_source_capture_plan(
            [action_type] if not review["accepted_for_closure"] else [],
            [],
        )
        return {
            "checked": action_type in PR6_LOW_RISK_ACTIONS,
            "action_type": action_type,
            "fixture": fixture_name,
            "ready": bool(review["accepted_for_closure"]),
            "accepted_for_closure": bool(review["accepted_for_closure"]),
            "review": review,
            "next_source_requirements": requirements if not review["accepted_for_closure"] else [],
            "capture_plan": capture_plan,
        }

    def _fixture_paths(self) -> list[Path]:
        if not self.fixture_dir.exists():
            raise FileNotFoundError(f"pioneer fixture dir not found: {self.fixture_dir}")
        return [
            path
            for path in sorted(self.fixture_dir.glob("*.json"))
            if not path.name.startswith("template_")
        ]

    def _load_expectation_payload(self) -> dict[str, Any]:
        if not self.expectations_path.exists():
            return {"fixtures": {}}
        return json.loads(self.expectations_path.read_text(encoding="utf-8"))

    def _load_expectations(self) -> dict[str, dict[str, Any]]:
        return self._expectations_from_payload(self._load_expectation_payload())

    @staticmethod
    def _expectations_from_payload(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
        fixtures = payload.get("fixtures", {})
        if not isinstance(fixtures, dict):
            raise ValueError("invalid expectations file: fixtures must be a mapping")
        return fixtures

    def _resolve_fixture_path(self, value: str) -> Path:
        candidate = Path(value)
        if not candidate.is_absolute():
            if len(candidate.parts) == 1:
                candidate = self.fixture_dir / candidate
            else:
                candidate = self.workspace_root / candidate
        resolved = candidate.resolve()
        if not _is_relative_to(resolved, self.fixture_dir):
            raise ValueError(f"fixture must live under {self.fixture_dir}: {value}")
        if not resolved.exists():
            raise FileNotFoundError(f"fixture not found: {resolved}")
        return resolved

    def _run_replay(self, fixture_paths: list[Path]) -> list[dict[str, Any]]:
        if not fixture_paths:
            return []
        args = [
            self.python_executable,
            "-m",
            "pioneer_agent.app.replay_fixture",
        ]
        for path in fixture_paths:
            args.extend(["--fixture", str(path)])
        env = os.environ.copy()
        extra_paths = [
            str(self.pioneer_root / "src"),
            str(self.workspace_root / "packages" / "sanmou-common" / "src"),
        ]
        env["PYTHONPATH"] = os.pathsep.join(extra_paths + ([env["PYTHONPATH"]] if env.get("PYTHONPATH") else []))
        completed = subprocess.run(
            args,
            cwd=self.pioneer_root,
            env=env,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            stderr = completed.stderr.strip()
            raise RuntimeError(f"advisor replay failed ({completed.returncode}): {stderr}")
        return json.loads(completed.stdout)

    @staticmethod
    def _compare_result(result: dict[str, Any], expectations: dict[str, dict[str, Any]]) -> dict[str, Any]:
        fixture_name = Path(result.get("fixture", "")).name
        expected = expectations.get(fixture_name, {}).get("expected_action_type")
        selected = result.get("selected_action") or {}
        actual = selected.get("action_type")
        selection_reason = result.get("selection_reason") or {}
        dispatch_gate = _dispatch_gate_result(result, expectations.get(fixture_name, {}))
        runtime_dispatch_gate = _runtime_dispatch_gate_result(result, expectations.get(fixture_name, {}))
        terminal_dispatch_gate = _terminal_dispatch_gate_result(result, expectations.get(fixture_name, {}))
        return {
            "fixture": fixture_name,
            "matched": expected == actual,
            "expected_action_type": expected,
            "actual_action_type": actual,
            "selection_mode": selection_reason.get("selection_mode"),
            "top_score_gap": selection_reason.get("top_score_gap"),
            "ranked_action_count": len(result.get("ranked_actions") or []),
            "dispatch_gate": dispatch_gate,
            "runtime_dispatch_gate": runtime_dispatch_gate,
            "terminal_dispatch_gate": terminal_dispatch_gate,
            "semantic_target_gate": result.get("semantic_target_gate"),
            "runtime_dispatch": result.get("runtime_dispatch"),
            "verifier_gate": result.get("verifier_gate"),
            "verifier_spec": result.get("verifier_spec"),
        }

    @staticmethod
    def _pr6_verifier_coverage(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        covered = sorted(
            {
                item["actual_action_type"]
                for item in comparisons
                if item.get("actual_action_type") in PR6_LOW_RISK_ACTIONS
                and (item.get("verifier_gate") or {}).get("decision") == "allow"
                and (item.get("verifier_spec") or {}).get("expected_deltas")
            }
        )
        return {
            "checked": True,
            "required": PR6_LOW_RISK_ACTIONS,
            "covered": covered,
            "missing": sorted(set(PR6_LOW_RISK_ACTIONS) - set(covered)),
        }

    @staticmethod
    def _pr5_locked_field_coverage(pr5_expectations: dict[str, dict[str, Any]]) -> dict[str, Any]:
        required_by_field: dict[str, list[str]] = {
            "expected_action_type": [],
            "required_report_evidence": [],
            "expected_report_confidence": [],
            "expected_action_confidence": [],
            "required_action_evidence": [],
            "expected_dispatch_status": [],
            "runtime_dispatch_gate": [],
            "expected_dispatch_terminal_for_verifier": [],
        }
        for fixture_name, expectation in sorted(pr5_expectations.items()):
            required_by_field["expected_action_type"].append(fixture_name)
            required_by_field["required_report_evidence"].append(fixture_name)
            required_by_field["expected_report_confidence"].append(fixture_name)
            required_by_field["expected_action_confidence"].append(fixture_name)
            action_type = expectation.get("expected_action_type")
            if action_type is not None:
                required_by_field["required_action_evidence"].append(fixture_name)
            if action_type in PR6_LOW_RISK_ACTIONS:
                required_by_field["expected_dispatch_status"].append(fixture_name)
                required_by_field["runtime_dispatch_gate"].append(fixture_name)
                required_by_field["expected_dispatch_terminal_for_verifier"].append(fixture_name)

        missing: list[dict[str, str]] = []
        coverage: dict[str, dict[str, Any]] = {}
        for field_name, required_fixtures in required_by_field.items():
            missing_fixtures = [
                fixture_name
                for fixture_name in required_fixtures
                if not _pr5_field_present(pr5_expectations[fixture_name], field_name)
            ]
            for fixture_name in missing_fixtures:
                missing.append({"fixture": fixture_name, "field": field_name})
            coverage[field_name] = {
                "required_count": len(required_fixtures),
                "covered_count": len(required_fixtures) - len(missing_fixtures),
                "missing": missing_fixtures,
            }
        return {
            "checked": True,
            "fields": coverage,
            "missing": missing,
        }

    @staticmethod
    def _pr5_dispatch_gate_coverage(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        checked = [item for item in comparisons if (item.get("dispatch_gate") or {}).get("checked")]
        failures = [
            {
                "fixture": item["fixture"],
                "expected": item["dispatch_gate"]["expected"],
                "actual": item["dispatch_gate"]["actual"],
            }
            for item in checked
            if not item["dispatch_gate"]["matched"]
        ]
        return {
            "checked": True,
            "required_count": len(checked),
            "matched_count": len(checked) - len(failures),
            "failures": failures,
        }

    @staticmethod
    def _pr12_runtime_dispatch_coverage(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        checked = [item for item in comparisons if (item.get("runtime_dispatch_gate") or {}).get("checked")]
        failures = [
            {
                "fixture": item["fixture"],
                "expected": item["runtime_dispatch_gate"]["expected"],
                "actual": item["runtime_dispatch_gate"]["actual"],
            }
            for item in checked
            if not item["runtime_dispatch_gate"]["matched"]
        ]
        return {
            "checked": True,
            "required_count": len(checked),
            "matched_count": len(checked) - len(failures),
            "failures": failures,
        }

    @staticmethod
    def _pr15_terminal_dispatch_gate_coverage(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        checked = [item for item in comparisons if (item.get("terminal_dispatch_gate") or {}).get("checked")]
        failures = [
            {
                "fixture": item["fixture"],
                "expected": item["terminal_dispatch_gate"]["expected"],
                "actual": item["terminal_dispatch_gate"]["actual"],
            }
            for item in checked
            if not item["terminal_dispatch_gate"]["matched"]
        ]
        return {
            "checked": True,
            "required_count": len(checked),
            "matched_count": len(checked) - len(failures),
            "failures": failures,
        }

    @staticmethod
    def _low_risk_terminal_dispatch_coverage(comparisons: list[dict[str, Any]]) -> dict[str, Any]:
        covered_fixtures: dict[str, str] = {}
        observed: list[dict[str, Any]] = []
        for item in comparisons:
            action_type = item.get("actual_action_type")
            if action_type not in PR6_LOW_RISK_ACTIONS:
                continue
            if not (item.get("terminal_dispatch_gate") or {}).get("checked"):
                continue
            runtime_dispatch = item.get("runtime_dispatch") or {}
            summary = runtime_dispatch.get("summary") or {}
            terminal_for_verifier = summary.get("terminal_for_verifier") is True
            observation = {
                "fixture": item["fixture"],
                "action_type": action_type,
                "status": runtime_dispatch.get("status"),
                "blocked_by": summary.get("blocked_by"),
                "target_key": summary.get("target_key"),
                "flow_step": summary.get("flow_step"),
                "terminal_for_verifier": terminal_for_verifier,
            }
            observed.append(observation)
            if runtime_dispatch.get("status") == "ok" and terminal_for_verifier:
                covered_fixtures.setdefault(str(action_type), item["fixture"])

        covered = sorted(covered_fixtures)
        return {
            "checked": True,
            "required": PR6_LOW_RISK_ACTIONS,
            "covered": covered,
            "covered_fixtures": covered_fixtures,
            "missing": sorted(set(PR6_LOW_RISK_ACTIONS) - set(covered)),
            "observed": sorted(observed, key=lambda item: (item["action_type"], item["fixture"])),
        }

    def _low_risk_terminal_source_review(
        self,
        terminal_dispatch_coverage: dict[str, Any],
        expectations: dict[str, dict[str, Any]],
        comparisons: list[dict[str, Any]],
    ) -> dict[str, Any]:
        checked = bool(terminal_dispatch_coverage.get("checked"))
        covered_fixtures = terminal_dispatch_coverage.get("covered_fixtures") or {}
        observed: list[dict[str, Any]] = []
        accepted_actions: list[str] = []
        for action_type in PR6_LOW_RISK_ACTIONS:
            fixture = covered_fixtures.get(action_type)
            expectation = expectations.get(str(fixture), {}) if fixture else {}
            source_review = self._terminal_source_evidence_review(
                action_type=action_type,
                fixture=fixture,
                expectation=expectation,
            )
            accepted = source_review["accepted_for_closure"]
            observed.append(source_review)
            if accepted:
                accepted_actions.append(action_type)
        missing = sorted(set(PR6_LOW_RISK_ACTIONS) - set(accepted_actions))
        real_source_candidates = (
            self._terminal_real_source_candidates(comparisons, expectations)
            if checked
            else []
        )
        return {
            "checked": checked,
            "ready": checked and not missing,
            "required_actions": PR6_LOW_RISK_ACTIONS,
            "accepted_actions": sorted(accepted_actions),
            "missing_real_terminal_sources": missing,
            "next_source_requirements": _terminal_source_requirements(missing),
            "real_source_candidates": real_source_candidates,
            "capture_plan": (
                _terminal_source_capture_plan(missing, real_source_candidates)
                if checked
                else _unchecked_terminal_source_capture_plan()
            ),
            "observed": observed,
        }

    def _terminal_real_source_candidates(
        self,
        comparisons: list[dict[str, Any]],
        expectations: dict[str, dict[str, Any]],
    ) -> list[dict[str, Any]]:
        candidates: list[dict[str, Any]] = []
        for comparison in comparisons:
            action_type = comparison.get("actual_action_type")
            if action_type not in PR6_LOW_RISK_ACTIONS:
                continue
            fixture = comparison.get("fixture")
            if _terminal_fixture_source_kind(fixture) != "pr5_real_screenshot_fixture":
                continue
            expectation = expectations.get(str(fixture), {})
            runtime_dispatch = comparison.get("runtime_dispatch") or {}
            summary = runtime_dispatch.get("summary") or {}
            terminal_ready = (
                runtime_dispatch.get("status") == "ok"
                and summary.get("terminal_for_verifier") is True
            )
            source_review = self._terminal_source_evidence_review(
                action_type=action_type,
                fixture=fixture,
                expectation=expectation,
            )
            screenshot = expectation.get("screenshot")
            screenshot_exists = bool(screenshot) and self._source_path_exists(str(screenshot))
            disqualifiers: list[str] = []
            if not terminal_ready:
                disqualifiers.append("runtime_dispatch_not_terminal")
            if not source_review["source_evidence_valid"]:
                disqualifiers.append("terminal_source_evidence_invalid")
            if not screenshot_exists:
                disqualifiers.append("screenshot_missing")
            candidates.append(
                {
                    "fixture": fixture,
                    "action_type": action_type,
                    "page": expectation.get("page"),
                    "screenshot": screenshot,
                    "screenshot_exists": screenshot_exists,
                    "source_kind": source_review["source_kind"],
                    "runtime_dispatch": {
                        "status": runtime_dispatch.get("status"),
                        "blocked_by": summary.get("blocked_by"),
                        "target_key": summary.get("target_key"),
                        "flow_step": summary.get("flow_step"),
                        "terminal_for_verifier": summary.get("terminal_for_verifier") is True,
                    },
                    "terminal_dispatch_ready": terminal_ready,
                    "source_evidence_valid": source_review["source_evidence_valid"],
                    "missing_evidence": source_review["missing_evidence"],
                    "closure_eligible": terminal_ready and source_review["source_evidence_valid"],
                    "disqualifiers": sorted(set(disqualifiers)),
                }
            )
        return sorted(candidates, key=lambda item: (item["action_type"], item["fixture"]))

    @staticmethod
    def _low_risk_verifier_readiness(
        verifier_coverage: dict[str, Any],
        terminal_dispatch_coverage: dict[str, Any],
    ) -> dict[str, Any]:
        required = list(PR6_LOW_RISK_ACTIONS)
        checked = bool(verifier_coverage.get("checked")) and bool(terminal_dispatch_coverage.get("checked"))
        verifier_missing = list(verifier_coverage.get("missing") or [])
        terminal_missing = list(terminal_dispatch_coverage.get("missing") or [])
        blocking_actions: dict[str, list[str]] = {}
        for action_type in required:
            reasons: list[str] = []
            if action_type in verifier_missing:
                reasons.append("missing_verifier_spec")
            if action_type in terminal_missing:
                reasons.append("missing_terminal_dispatch")
            if reasons:
                blocking_actions[action_type] = reasons

        return {
            "checked": checked,
            "ready": checked and not blocking_actions,
            "required_actions": required,
            "ready_actions": sorted(set(required) - set(blocking_actions)),
            "blocking_actions": blocking_actions,
            "verifier_spec_missing": verifier_missing,
            "terminal_dispatch_missing": terminal_missing,
            "next_fixture_requirements": _next_fixture_requirements(blocking_actions),
            "observed_terminal_dispatch": terminal_dispatch_coverage.get("observed") or [],
        }

    @staticmethod
    def _attention_reasons(payload: dict[str, Any]) -> list[dict[str, Any]]:
        reasons: list[dict[str, Any]] = []
        if not payload.get("fixture_replay_checked"):
            reasons.append(
                {
                    "code": "fixture_replay_not_run",
                    "message": "include_fixture_results=false skips golden replay comparisons and cannot prove Advisor readiness.",
                }
            )
        if payload.get("missing_expectations"):
            reasons.append(
                {
                    "code": "missing_expectations",
                    "count": len(payload["missing_expectations"]),
                    "fixtures": payload["missing_expectations"],
                }
            )
        if payload.get("extra_expectations"):
            reasons.append(
                {
                    "code": "extra_expectations",
                    "count": len(payload["extra_expectations"]),
                    "fixtures": payload["extra_expectations"],
                }
            )

        page_missing = (payload.get("pr5_page_coverage") or {}).get("missing") or []
        if page_missing:
            reasons.append({"code": "pr5_page_coverage_missing", "pages": page_missing})

        locked_missing = (payload.get("pr5_locked_field_coverage") or {}).get("missing") or []
        if locked_missing:
            reasons.append(
                {
                    "code": "pr5_locked_fields_missing",
                    "count": len(locked_missing),
                    "missing": locked_missing,
                }
            )

        failures = payload.get("failures") or []
        if failures:
            reasons.append(
                {
                    "code": "advisor_replay_failures",
                    "count": len(failures),
                    "fixtures": [item.get("fixture") for item in failures],
                }
            )

        verifier_coverage = payload.get("pr6_verifier_coverage") or {}
        verifier_missing = verifier_coverage.get("missing") or []
        if verifier_coverage.get("checked") and verifier_missing:
            reasons.append(
                {
                    "code": "pr6_verifier_coverage_missing",
                    "actions": verifier_missing,
                }
            )

        dispatch_failures = (payload.get("pr5_dispatch_gate_coverage") or {}).get("failures") or []
        if dispatch_failures:
            reasons.append(
                {
                    "code": "pr5_dispatch_gate_failures",
                    "count": len(dispatch_failures),
                    "failures": dispatch_failures,
                }
            )

        runtime_dispatch_failures = (
            (payload.get("pr12_runtime_dispatch_coverage") or {}).get("failures") or []
        )
        if runtime_dispatch_failures:
            reasons.append(
                {
                    "code": "pr12_runtime_dispatch_gate_failures",
                    "count": len(runtime_dispatch_failures),
                    "failures": runtime_dispatch_failures,
                }
            )

        terminal_gate_failures = (
            (payload.get("pr15_terminal_dispatch_gate_coverage") or {}).get("failures") or []
        )
        if terminal_gate_failures:
            reasons.append(
                {
                    "code": "pr15_terminal_dispatch_gate_failures",
                    "count": len(terminal_gate_failures),
                    "failures": terminal_gate_failures,
                }
            )

        readiness = payload.get("low_risk_verifier_readiness") or {}
        terminal_missing = readiness.get("terminal_dispatch_missing") or []
        if readiness.get("checked") and terminal_missing:
            reasons.append(
                {
                    "code": "low_risk_terminal_dispatch_missing",
                    "actions": terminal_missing,
                    "blocking_actions": readiness.get("blocking_actions") or {},
                }
            )
        source_review = payload.get("low_risk_terminal_source_review") or {}
        source_missing = source_review.get("missing_real_terminal_sources") or []
        if source_review.get("checked") and source_missing:
            reasons.append(
                {
                    "code": "low_risk_terminal_source_review_missing",
                    "actions": source_missing,
                    "observed": source_review.get("observed") or [],
                }
            )
        desktop_gate = payload.get("desktop_evidence_display_gate") or {}
        if desktop_gate.get("checked") and not desktop_gate.get("ready"):
            reasons.append(
                {
                    "code": "desktop_evidence_degraded_display_missing",
                    "missing": desktop_gate.get("missing") or [],
                }
            )
        return reasons

    def _architecture_iteration_closure_gate(self, payload: dict[str, Any]) -> dict[str, Any]:
        source_docs = [
            {
                "code": "canonical_architecture_adr",
                "path": "docs/sanmou-architecture-design.md",
            },
            {
                "code": "derived_iteration_path",
                "path": "docs/sanmou-monorepo-architecture-iteration-path.md",
            },
        ]
        for item in source_docs:
            item["exists"] = (self.workspace_root / item["path"]).exists()

        requirements = [
            _closure_requirement(
                "architecture_source_docs_present",
                all(item["exists"] for item in source_docs),
                {"source_docs": source_docs},
            ),
            _closure_requirement(
                "golden_replay_checked",
                bool(payload.get("fixture_replay_checked")),
                {"fixture_replay_checked": payload.get("fixture_replay_checked")},
            ),
            _closure_requirement(
                "golden_replay_matches_expectations",
                not payload.get("failures")
                and not payload.get("missing_expectations")
                and not payload.get("extra_expectations"),
                {
                    "failure_count": len(payload.get("failures") or []),
                    "missing_expectations": payload.get("missing_expectations") or [],
                    "extra_expectations": payload.get("extra_expectations") or [],
                },
            ),
            _closure_requirement(
                "pr5_page_coverage_complete",
                not ((payload.get("pr5_page_coverage") or {}).get("missing") or []),
                payload.get("pr5_page_coverage") or {},
            ),
            _closure_requirement(
                "pr5_locked_fields_complete",
                not ((payload.get("pr5_locked_field_coverage") or {}).get("missing") or []),
                {
                    "missing": (payload.get("pr5_locked_field_coverage") or {}).get("missing")
                    or [],
                },
            ),
            _closure_requirement(
                "pr6_verifier_specs_complete",
                bool((payload.get("pr6_verifier_coverage") or {}).get("checked"))
                and not ((payload.get("pr6_verifier_coverage") or {}).get("missing") or []),
                payload.get("pr6_verifier_coverage") or {},
            ),
            _closure_requirement(
                "pr5_dispatch_gate_matched",
                bool((payload.get("pr5_dispatch_gate_coverage") or {}).get("checked"))
                and not ((payload.get("pr5_dispatch_gate_coverage") or {}).get("failures") or []),
                payload.get("pr5_dispatch_gate_coverage") or {},
            ),
            _closure_requirement(
                "runtime_dispatch_gate_matched",
                bool((payload.get("pr12_runtime_dispatch_coverage") or {}).get("checked"))
                and not (
                    (payload.get("pr12_runtime_dispatch_coverage") or {}).get("failures")
                    or []
                ),
                payload.get("pr12_runtime_dispatch_coverage") or {},
            ),
            _closure_requirement(
                "terminal_dispatch_expectations_matched",
                bool((payload.get("pr15_terminal_dispatch_gate_coverage") or {}).get("checked"))
                and not (
                    (payload.get("pr15_terminal_dispatch_gate_coverage") or {}).get("failures")
                    or []
                ),
                payload.get("pr15_terminal_dispatch_gate_coverage") or {},
            ),
            _closure_requirement(
                "low_risk_terminal_dispatch_ready",
                bool((payload.get("low_risk_verifier_readiness") or {}).get("ready")),
                payload.get("low_risk_verifier_readiness") or {},
            ),
            _closure_requirement(
                "low_risk_terminal_real_source_reviewed",
                bool((payload.get("low_risk_terminal_source_review") or {}).get("ready")),
                payload.get("low_risk_terminal_source_review") or {},
            ),
            _closure_requirement(
                "desktop_evidence_degraded_display_ready",
                bool((payload.get("desktop_evidence_display_gate") or {}).get("ready")),
                payload.get("desktop_evidence_display_gate") or {},
            ),
        ]
        blocking_codes = [item["code"] for item in requirements if not item["ready"]]
        return {
            "status": "ready" if not blocking_codes else "attention",
            "ready": not blocking_codes,
            "source_docs": source_docs,
            "blocking_codes": blocking_codes,
            "requirements": requirements,
        }

    def _desktop_evidence_display_gate(self) -> dict[str, Any]:
        renderer_root = self.workspace_root / "apps" / "sanmou-advisor-desktop" / "src" / "renderer"
        source_files = {
            "app": renderer_root / "App.tsx",
            "types": renderer_root / "types.ts",
            "styles": renderer_root / "styles.css",
        }
        file_status: dict[str, dict[str, Any]] = {}
        contents: dict[str, str] = {}
        for key, path in source_files.items():
            exists = path.exists()
            file_status[key] = {
                "path": str(path.relative_to(self.workspace_root)),
                "exists": exists,
            }
            contents[key] = path.read_text(encoding="utf-8") if exists else ""

        app_source = contents["app"]
        types_source = contents["types"]
        styles_source = contents["styles"]
        checks = [
            _display_gate_check(
                "structured_evidence_contract_typed",
                "structured_evidence" in types_source and "StructuredEvidence" in types_source,
                "Desktop report types must preserve structured evidence from AdvisorReport and ActionRecommendation.",
            ),
            _display_gate_check(
                "structured_evidence_rendered",
                "structured_evidence" in app_source,
                "Desktop summary must render structured evidence, not only legacy string evidence.",
            ),
            _display_gate_check(
                "blocked_action_reason_rendered",
                "execution_blocked_reason" in app_source,
                "Desktop recommendation panel must expose blocked/degraded action reasons.",
            ),
            _display_gate_check(
                "no_evidence_degraded_copy",
                any(token in app_source for token in ("证据不足", "degraded", "evidence-degraded")),
                "Desktop must label no-evidence recommendations as degraded instead of certain.",
            ),
            _display_gate_check(
                "evidence_state_styles",
                any(token in styles_source for token in ("evidence-degraded", "evidence-status", "degraded")),
                "Desktop styles must include a distinct degraded/no-evidence presentation.",
            ),
        ]
        missing = [item["code"] for item in checks if not item["ready"]]
        missing_files = [
            status["path"] for status in file_status.values() if not status["exists"]
        ]
        return {
            "checked": True,
            "ready": not missing and not missing_files,
            "files": file_status,
            "checks": checks,
            "missing": sorted(missing),
            "missing_files": missing_files,
        }

    @staticmethod
    def _fixture_low_risk_readiness(comparison: dict[str, Any]) -> dict[str, Any]:
        action_type = comparison.get("actual_action_type")
        low_risk = action_type in PR6_LOW_RISK_ACTIONS
        if not low_risk:
            return {
                "checked": False,
                "action_type": action_type,
                "low_risk": False,
                "ready_for_post_action_verifier": False,
                "blockers": [],
            }

        verifier_gate = comparison.get("verifier_gate") or {}
        verifier_spec = comparison.get("verifier_spec") or {}
        expected_deltas = verifier_spec.get("expected_deltas") or []
        verifier_spec_ready = (
            verifier_gate.get("decision") == "allow"
            and bool(expected_deltas)
            and verifier_spec.get("timeout_seconds") is not None
        )

        semantic_gate = comparison.get("semantic_target_gate") or {}
        semantic_dispatch_ready = semantic_gate.get("decision") == "allow"

        runtime_dispatch = comparison.get("runtime_dispatch") or {}
        summary = runtime_dispatch.get("summary") or {}
        runtime_dispatch_ready = runtime_dispatch.get("status") == "ok"
        terminal_dispatch_ready = runtime_dispatch_ready and summary.get("terminal_for_verifier") is True

        blockers: list[str] = []
        if not verifier_spec_ready:
            blockers.append("missing_verifier_spec")
        if semantic_gate.get("decision") == "block":
            blockers.append("semantic_target_gate_blocked")
        if not runtime_dispatch_ready:
            blockers.append("dispatch_not_ok")
        if not terminal_dispatch_ready:
            blockers.append("missing_terminal_dispatch")

        return {
            "checked": True,
            "action_type": action_type,
            "low_risk": True,
            "ready_for_post_action_verifier": not blockers,
            "blockers": blockers,
            "next_fixture_requirements": _next_fixture_requirements(
                {str(action_type): blockers} if blockers else {}
            ),
            "verifier_spec_ready": verifier_spec_ready,
            "semantic_dispatch_ready": semantic_dispatch_ready,
            "runtime_dispatch_ready": runtime_dispatch_ready,
            "terminal_dispatch_ready": terminal_dispatch_ready,
            "observed": {
                "semantic_gate_decision": semantic_gate.get("decision"),
                "status": runtime_dispatch.get("status"),
                "blocked_by": summary.get("blocked_by"),
                "target_key": summary.get("target_key"),
                "flow_step": summary.get("flow_step"),
                "terminal_for_verifier": summary.get("terminal_for_verifier") is True,
            },
        }

    def _fixture_terminal_source_review(
        self,
        comparison: dict[str, Any],
        expectation: dict[str, Any],
    ) -> dict[str, Any]:
        action_type = comparison.get("actual_action_type")
        runtime_dispatch = comparison.get("runtime_dispatch") or {}
        summary = runtime_dispatch.get("summary") or {}
        terminal_ready = (
            action_type in PR6_LOW_RISK_ACTIONS
            and runtime_dispatch.get("status") == "ok"
            and summary.get("terminal_for_verifier") is True
        )
        source_review = self._terminal_source_evidence_review(
            action_type=action_type,
            fixture=comparison.get("fixture"),
            expectation=expectation,
        )
        source_review["checked"] = action_type in PR6_LOW_RISK_ACTIONS
        source_review["terminal_dispatch_ready"] = terminal_ready
        source_review["accepted_for_closure"] = (
            terminal_ready and source_review["source_evidence_valid"]
        )
        source_review["next_source_requirements"] = (
            _terminal_source_requirements([str(action_type)])
            if source_review["checked"] and not source_review["accepted_for_closure"]
            else []
        )
        return source_review

    def _terminal_source_evidence_review(
        self,
        *,
        action_type: Any,
        fixture: Any,
        expectation: dict[str, Any],
    ) -> dict[str, Any]:
        action_key = str(action_type) if action_type in PR6_LOW_RISK_ACTIONS else None
        requirement = (
            LOW_RISK_TERMINAL_SOURCE_REQUIREMENTS.get(action_key)
            if action_key is not None
            else None
        ) or {}
        evidence = expectation.get("terminal_source_evidence")
        source_kind = _terminal_fixture_source_kind(fixture)
        missing: list[str] = []
        source_evidence_present = isinstance(evidence, dict)
        if not source_evidence_present:
            missing.append("terminal_source_evidence")
            evidence = {}

        declared_kind = evidence.get("source_kind")
        if declared_kind:
            source_kind = str(declared_kind)
        accepted_source_kinds = set(requirement.get("accepted_source_kinds") or [])
        if source_kind not in accepted_source_kinds:
            missing.append("accepted_source_kind")

        if evidence.get("review_status") != "reviewed":
            missing.append("review_status")

        evidence_page = evidence.get("page") or expectation.get("page")
        required_page = requirement.get("required_page")
        if required_page and evidence_page != required_page:
            missing.append("page")

        semantic_target = evidence.get("semantic_target")
        required_semantic_target = requirement.get("required_semantic_target")
        if required_semantic_target and semantic_target != required_semantic_target:
            missing.append("semantic_target")

        runtime_dispatch = evidence.get("runtime_dispatch")
        required_runtime_dispatch = requirement.get("required_runtime_dispatch") or {}
        if required_runtime_dispatch and not _runtime_dispatch_matches(
            runtime_dispatch,
            required_runtime_dispatch,
        ):
            missing.append("runtime_dispatch")

        post_action_delta = evidence.get("post_action_delta")
        if not isinstance(post_action_delta, list) or not post_action_delta:
            missing.append("post_action_delta")
        elif not _post_action_delta_matches(
            post_action_delta,
            requirement.get("required_post_action_delta") or [],
        ):
            missing.append("post_action_delta")

        trace_validation: dict[str, Any] | None = None
        verification_record_validation: dict[str, Any] | None = None
        screenshot_path = evidence.get("screenshot")
        if source_kind == "pr5_real_screenshot_fixture":
            if not screenshot_path or not self._source_path_exists(str(screenshot_path)):
                missing.append("screenshot")
        elif source_kind == "live_trace_fixture":
            trace_path = evidence.get("trace")
            if not trace_path or not self._source_path_exists(str(trace_path)):
                missing.append("trace")
            else:
                trace_validation = self._live_trace_evidence_validation(
                    str(trace_path),
                    action_type=action_key,
                    required_runtime_dispatch=required_runtime_dispatch,
                )
                if not trace_validation["matched"]:
                    missing.append("trace_semantics")
            if not screenshot_path or not self._source_path_exists(str(screenshot_path)):
                missing.append("screenshot")
            verification_record_validation = _verification_record_validation(
                evidence.get("verification_record"),
                action_type=action_key,
                required_post_action_delta=requirement.get("required_post_action_delta") or [],
            )
            if not verification_record_validation["valid"]:
                missing.append("verification_record")

        source_evidence_valid = not missing
        return {
            "checked": action_type in PR6_LOW_RISK_ACTIONS,
            "action_type": action_type,
            "fixture": fixture,
            "source_kind": source_kind,
            "source_evidence_present": source_evidence_present,
            "source_evidence_valid": source_evidence_valid,
            "missing_evidence": sorted(set(missing)),
            "evidence_page": evidence_page,
            "required_page": required_page,
            "semantic_target": semantic_target,
            "required_semantic_target": required_semantic_target,
            "runtime_dispatch": runtime_dispatch if isinstance(runtime_dispatch, dict) else None,
            "required_runtime_dispatch": required_runtime_dispatch,
            "post_action_delta": post_action_delta if isinstance(post_action_delta, list) else [],
            "required_post_action_delta": requirement.get("required_post_action_delta") or [],
            "trace_validation": trace_validation,
            "verification_record_validation": verification_record_validation,
            "accepted_for_closure": source_evidence_valid,
            "terminal_dispatch_ready": False,
            "next_source_requirements": [],
        }

    def _source_path_exists(self, value: str) -> bool:
        return self._resolve_source_path(value) is not None

    def _resolve_source_path(self, value: str) -> Path | None:
        path = Path(value)
        candidates = [path] if path.is_absolute() else [
            self.pioneer_root / path,
            self.workspace_root / path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return None

    def _live_trace_evidence_validation(
        self,
        trace_path: str,
        *,
        action_type: str | None,
        required_runtime_dispatch: dict[str, Any],
    ) -> dict[str, Any]:
        records, load_error = self._load_trace_records(trace_path)
        matching_records: list[dict[str, Any]] = []
        for index, record in enumerate(records):
            selected_action = _trace_selected_action(record)
            execution = _trace_execution(record)
            verifier = _trace_post_action_verifier(record)
            action_matches = selected_action.get("action_type") == action_type
            dispatch_matches = _runtime_dispatch_matches(execution, required_runtime_dispatch)
            verifier_verified = verifier.get("status") == "verified"
            if action_matches and dispatch_matches and verifier_verified:
                matching_records.append(
                    {
                        "index": index,
                        "action_type": selected_action.get("action_type"),
                        "target_key": (execution.get("summary") or {}).get("target_key"),
                        "terminal_for_verifier": (execution.get("summary") or {}).get("terminal_for_verifier"),
                        "verifier_status": verifier.get("status"),
                    }
                )
        return {
            "checked": True,
            "trace": trace_path,
            "record_count": len(records),
            "matched": bool(matching_records),
            "matching_records": matching_records,
            "load_error": load_error,
            "required_action_type": action_type,
            "required_runtime_dispatch": required_runtime_dispatch,
            "required_verifier_status": "verified",
        }

    def _load_trace_records(self, trace_path: str) -> tuple[list[dict[str, Any]], str | None]:
        path = self._resolve_source_path(trace_path)
        if path is None:
            return [], "trace file does not exist"
        try:
            raw = path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            return [], str(exc)
        if not raw:
            return [], "trace file is empty"
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            records: list[dict[str, Any]] = []
            for line_number, line in enumerate(raw.splitlines(), start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError as exc:
                    return [], f"invalid jsonl at line {line_number}: {exc}"
                if isinstance(item, dict):
                    records.append(item)
            return records, None
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)], None
        if isinstance(payload, dict):
            return [payload], None
        return [], "trace payload must be an object, object list, or jsonl"


def _next_fixture_requirements(blocking_actions: dict[str, list[str]]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for action_type in sorted(blocking_actions):
        template = LOW_RISK_NEXT_FIXTURE_REQUIREMENTS.get(action_type)
        if template is None:
            continue
        requirement = dict(template)
        requirement["action_type"] = action_type
        requirement["blockers"] = list(blocking_actions[action_type])
        requirements.append(requirement)
    return requirements


def _terminal_source_requirements(action_types: list[str]) -> list[dict[str, Any]]:
    requirements: list[dict[str, Any]] = []
    for action_type in sorted(set(action_types)):
        template = LOW_RISK_TERMINAL_SOURCE_REQUIREMENTS.get(action_type)
        if template is None:
            continue
        requirement = dict(template)
        requirement["action_type"] = action_type
        requirement["terminal_source_evidence_templates"] = (
            _terminal_source_evidence_templates(requirement)
        )
        requirements.append(requirement)
    return requirements


def _terminal_source_capture_plan(
    action_types: list[str],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    disqualifiers_by_action: dict[str, set[str]] = {}
    for candidate in candidates:
        action_type = str(candidate.get("action_type"))
        disqualifiers_by_action.setdefault(action_type, set()).update(candidate.get("disqualifiers") or [])

    actions: list[dict[str, Any]] = []
    for requirement in _terminal_source_requirements(action_types):
        action_type = requirement["action_type"]
        actions.append(
            {
                "code": f"{requirement['code']}_capture_plan",
                "action_type": action_type,
                "required_page": requirement["required_page"],
                "required_semantic_target": requirement["required_semantic_target"],
                "required_runtime_dispatch": requirement["required_runtime_dispatch"],
                "required_post_action_delta": requirement["required_post_action_delta"],
                "accepted_source_kinds": requirement["accepted_source_kinds"],
                "current_candidate_disqualifiers": sorted(
                    disqualifiers_by_action.get(action_type) or {"missing_real_source_candidate"}
                ),
                "pre_final_capture": {
                    "required": True,
                    "purpose": "capture and review the terminal page before the final mutating click",
                    "closure_eligible_without_post_action_delta": False,
                },
                "final_action_policy": {
                    "mutates_game_state": True,
                    "requires_operator_confirmation": True,
                    "allowed_only_after_terminal_dispatch_ready": True,
                },
                "terminal_source_evidence_fields": [
                    "source_kind",
                    "review_status=reviewed",
                    "screenshot",
                    "page",
                    "semantic_target",
                    "runtime_dispatch",
                    "post_action_delta",
                ],
                "live_trace_extra_fields": [
                    "trace",
                    "verification_record",
                ],
                "live_trace_semantic_checks": [
                    "selected_action.action_type matches action_type",
                    "execution.status matches required_runtime_dispatch.status",
                    "execution.summary.target_key matches required_runtime_dispatch.target_key",
                    "execution.summary.terminal_for_verifier=true",
                    "verification.post_action_verifier.status=verified",
                ],
                "advisor_fixture_expectation_patch_template": (
                    _advisor_fixture_expectation_patch_template(requirement)
                ),
            }
        )
    return {
        "checked": True,
        "ready": not actions,
        "blocked_until": "terminal_source_evidence_valid",
        "requires_operator_confirmation_for_final_action": bool(actions),
        "actions": actions,
    }


def _unchecked_terminal_source_capture_plan() -> dict[str, Any]:
    return {
        "checked": False,
        "ready": False,
        "blocked_until": "golden_replay_checked",
        "requires_operator_confirmation_for_final_action": False,
        "actions": [],
    }


def _terminal_source_evidence_templates(requirement: dict[str, Any]) -> dict[str, Any]:
    return {
        source_kind: _terminal_source_evidence_template(requirement, source_kind)
        for source_kind in requirement.get("accepted_source_kinds") or []
    }


def _terminal_source_evidence_template(
    requirement: dict[str, Any],
    source_kind: str,
) -> dict[str, Any]:
    action_type = str(requirement["action_type"])
    evidence: dict[str, Any] = {
        "source_kind": source_kind,
        "review_status": "reviewed",
        "screenshot": f"tests/fixtures/screenshots/pc_client/<capture-date>/{action_type}_terminal.jpg",
        "page": requirement["required_page"],
        "semantic_target": requirement["required_semantic_target"],
        "runtime_dispatch": dict(requirement["required_runtime_dispatch"]),
        "post_action_delta": list(requirement["required_post_action_delta"]),
    }
    if source_kind == "live_trace_fixture":
        evidence["trace"] = f"tests/fixtures/traces/<capture-date>/{action_type}_terminal.jsonl"
        evidence["verification_record"] = {
            "action_type": action_type,
            "status": "verified",
            "checked": [
                _required_delta_path(item)
                for item in requirement["required_post_action_delta"]
            ],
            "post_action_delta": list(requirement["required_post_action_delta"]),
        }
    return evidence


def _advisor_fixture_expectation_patch_template(requirement: dict[str, Any]) -> dict[str, Any]:
    action_type = str(requirement["action_type"])
    runtime_dispatch = requirement["required_runtime_dispatch"]
    terminal_flag = runtime_dispatch.get("terminal_for_verifier")
    return {
        f"<{action_type}_terminal_fixture>.json": {
            "page": requirement["required_page"],
            "screenshot": (
                f"tests/fixtures/screenshots/pc_client/<capture-date>/{action_type}_terminal.jpg"
            ),
            "expected_action_type": action_type,
            "expected_dispatch_status": runtime_dispatch.get("status"),
            "expected_dispatch_target_key": runtime_dispatch.get("target_key"),
            "expected_dispatch_terminal_for_verifier": terminal_flag,
            "terminal_source_evidence": _terminal_source_evidence_template(
                requirement,
                "live_trace_fixture",
            ),
        }
    }


def _closure_requirement(code: str, ready: bool, evidence: dict[str, Any]) -> dict[str, Any]:
    return {
        "code": code,
        "ready": bool(ready),
        "evidence": evidence,
    }


def _display_gate_check(code: str, ready: bool, requirement: str) -> dict[str, Any]:
    return {
        "code": code,
        "ready": bool(ready),
        "requirement": requirement,
    }


def _terminal_fixture_source_kind(fixture: Any) -> str | None:
    if not isinstance(fixture, str) or not fixture:
        return None
    if fixture.startswith("pr5_"):
        return "pr5_real_screenshot_fixture"
    if fixture.startswith("live_") or fixture.startswith("trace_"):
        return "live_trace_fixture"
    return "runtime_state_fixture"


def _runtime_dispatch_matches(actual: Any, required: dict[str, Any]) -> bool:
    if not isinstance(actual, dict):
        return False
    summary = actual.get("summary") if isinstance(actual.get("summary"), dict) else {}
    flattened = {
        "status": actual.get("status"),
        "target_key": actual.get("target_key") or summary.get("target_key"),
        "terminal_for_verifier": (
            actual.get("terminal_for_verifier")
            if "terminal_for_verifier" in actual
            else summary.get("terminal_for_verifier")
        ),
    }
    return all(flattened.get(key) == expected for key, expected in required.items())


def _post_action_delta_matches(actual: list[Any], required: list[str]) -> bool:
    if not required:
        return True
    actual_values: set[str] = set()
    for item in actual:
        actual_values.update(_delta_representations(item))
    required_values = {_normalize_delta_text(item) for item in required}
    return bool(actual_values & required_values)


def _verification_record_validation(
    value: Any,
    *,
    action_type: str | None,
    required_post_action_delta: list[str],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "checked": True,
            "valid": False,
            "issues": ["verification_record_not_object"],
        }
    verifier = value.get("post_action_verifier") if isinstance(value.get("post_action_verifier"), dict) else value
    action_value = verifier.get("action_type") or value.get("action_type")
    status = verifier.get("status") or value.get("status") or value.get("verification_status")
    checked_paths = verifier.get("checked") or value.get("checked") or []
    post_action_delta = value.get("post_action_delta")
    issues: list[str] = []
    if action_value != action_type:
        issues.append("action_type")
    if status != "verified":
        issues.append("status")
    if isinstance(post_action_delta, list):
        if not _post_action_delta_matches(post_action_delta, required_post_action_delta):
            issues.append("post_action_delta")
    elif not _checked_paths_cover_required_delta(checked_paths, required_post_action_delta):
        issues.append("checked_delta")
    return {
        "checked": True,
        "valid": not issues,
        "issues": sorted(set(issues)),
        "action_type": action_value,
        "status": status,
        "checked_paths": checked_paths if isinstance(checked_paths, list) else [],
    }


def _checked_paths_cover_required_delta(value: Any, required: list[str]) -> bool:
    if not required:
        return True
    if not isinstance(value, list) or not value:
        return False
    checked = {str(item) for item in value}
    required_paths = {_required_delta_path(item) for item in required}
    return bool(checked & required_paths)


def _required_delta_path(value: Any) -> str:
    text = str(value).strip()
    if text.startswith("or "):
        text = text[3:]
    for separator in ("=", " increases", " decreases", " present"):
        if separator in text:
            return text.split(separator, 1)[0].strip()
    return text.split(" ", 1)[0].strip()


def _trace_selected_action(record: dict[str, Any]) -> dict[str, Any]:
    selected = record.get("selected_action")
    if isinstance(selected, dict):
        return selected
    act = record.get("act")
    if isinstance(act, dict):
        inputs = act.get("inputs")
        if isinstance(inputs, dict) and isinstance(inputs.get("action"), dict):
            return inputs["action"]
    return {}


def _trace_execution(record: dict[str, Any]) -> dict[str, Any]:
    execution = record.get("execution")
    if isinstance(execution, dict):
        return execution
    act = record.get("act")
    if isinstance(act, dict) and isinstance(act.get("outputs"), dict):
        return act["outputs"]
    return {}


def _trace_post_action_verifier(record: dict[str, Any]) -> dict[str, Any]:
    verification = record.get("verification")
    if isinstance(verification, dict):
        verifier = verification.get("post_action_verifier")
        if isinstance(verifier, dict):
            return verifier
    verify_step = record.get("verify")
    if isinstance(verify_step, dict):
        outputs = verify_step.get("outputs")
        if isinstance(outputs, dict) and isinstance(outputs.get("post_action_verifier"), dict):
            return outputs["post_action_verifier"]
    execution = _trace_execution(record)
    summary = execution.get("summary")
    if isinstance(summary, dict) and isinstance(summary.get("post_action_verifier"), dict):
        return summary["post_action_verifier"]
    return {}


def _delta_representations(item: Any) -> set[str]:
    if isinstance(item, str):
        return {_normalize_delta_text(item)}
    if not isinstance(item, dict):
        return set()

    path = item.get("path")
    if not path:
        return set()
    values: set[str] = set()
    for key in ("value", "expected", "to", "after"):
        if key in item:
            values.add(_normalize_delta_text(f"{path}={_delta_value(item[key])}"))
    for key in ("op", "operator", "change", "direction"):
        if item.get(key):
            values.add(_normalize_delta_text(f"{path} {item[key]}"))
    if item.get("present") is True:
        values.add(_normalize_delta_text(f"{path} present"))
    return values


def _delta_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _normalize_delta_text(value: Any) -> str:
    text = " ".join(str(value).strip().lower().split())
    if text.startswith("or "):
        text = text[3:]
    text = text.replace(" = ", "=")
    return text


def _dispatch_gate_result(result: dict[str, Any], expectation: dict[str, Any]) -> dict[str, Any]:
    expected_status = expectation.get("expected_dispatch_status")
    semantic_target_gate = result.get("semantic_target_gate") or {}
    decision = semantic_target_gate.get("decision")
    actual: dict[str, Any] = {
        "status": None,
        "blocked_by": None,
        "target_key": _dispatch_target_key(semantic_target_gate),
    }
    if decision == "block":
        actual["status"] = "blocked"
        actual["blocked_by"] = "semantic_target_gate"
    elif decision == "allow":
        actual["status"] = "ok"
    elif decision == "skip":
        actual["status"] = "not_applicable"

    expected = {
        "status": expected_status,
        "blocked_by": expectation.get("expected_dispatch_blocked_by"),
        "target_key": expectation.get("expected_dispatch_target_key"),
    }
    checked = expected_status is not None
    matched = True
    if checked:
        matched = expected["status"] == actual["status"]
        if expected["blocked_by"] is not None:
            matched = matched and expected["blocked_by"] == actual["blocked_by"]
        if expected["target_key"] is not None:
            matched = matched and expected["target_key"] == actual["target_key"]
    return {
        "checked": checked,
        "matched": matched,
        "expected": expected,
        "actual": actual,
    }


def _pr5_field_present(expectation: dict[str, Any], field_name: str) -> bool:
    if field_name in {"required_report_evidence", "required_action_evidence"}:
        return bool(expectation.get(field_name))
    if field_name == "runtime_dispatch_gate":
        return "expected_dispatch_status" in expectation
    return field_name in expectation


def _runtime_dispatch_gate_result(result: dict[str, Any], expectation: dict[str, Any]) -> dict[str, Any]:
    expected_status = expectation.get("expected_dispatch_status")
    runtime_dispatch = result.get("runtime_dispatch") or {}
    summary = runtime_dispatch.get("summary") or {}
    runtime_gate = summary.get("semantic_target_gate") or {}
    expected = {
        "status": expected_status,
        "blocked_by": expectation.get("expected_dispatch_blocked_by"),
        "target_key": expectation.get("expected_dispatch_target_key"),
        "semantic_gate_decision": (result.get("semantic_target_gate") or {}).get("decision"),
    }
    actual = {
        "status": runtime_dispatch.get("status"),
        "blocked_by": summary.get("blocked_by"),
        "target_key": summary.get("target_key"),
        "semantic_gate_decision": runtime_gate.get("decision"),
    }
    checked = expected_status is not None
    matched = True
    if checked:
        matched = expected["status"] == actual["status"]
        matched = matched and expected["semantic_gate_decision"] == actual["semantic_gate_decision"]
        if expected["blocked_by"] is not None:
            matched = matched and expected["blocked_by"] == actual["blocked_by"]
        if expected["target_key"] is not None:
            matched = matched and expected["target_key"] == actual["target_key"]
    return {
        "checked": checked,
        "matched": matched,
        "expected": expected,
        "actual": actual,
    }


def _terminal_dispatch_gate_result(result: dict[str, Any], expectation: dict[str, Any]) -> dict[str, Any]:
    expected_terminal = expectation.get("expected_dispatch_terminal_for_verifier")
    runtime_dispatch = result.get("runtime_dispatch") or {}
    summary = runtime_dispatch.get("summary") or {}
    actual = {
        "status": runtime_dispatch.get("status"),
        "target_key": summary.get("target_key"),
        "flow_step": summary.get("flow_step"),
        "terminal_for_verifier": summary.get("terminal_for_verifier") is True,
    }
    expected = {
        "terminal_for_verifier": expected_terminal,
    }
    checked = expected_terminal is not None
    matched = True
    if checked:
        matched = expected_terminal == actual["terminal_for_verifier"]
    return {
        "checked": checked,
        "matched": matched,
        "expected": expected,
        "actual": actual,
    }


def _dispatch_target_key(semantic_target_gate: dict[str, Any]) -> str | None:
    details = semantic_target_gate.get("details") or {}
    action_type = details.get("action_type")
    target = details.get("target")
    if action_type == "claim_chapter_reward" and target == "claim_button":
        return "chapter_claim_button"
    if action_type == "recruit_soldiers" and target == "recruit_button":
        return "recruit_button"
    if action_type == "upgrade_building" and target == "upgrade_button":
        return "building_upgrade_button"
    if action_type == "upgrade_building" and target == "upgrade_dialog.confirm_button":
        return "upgrade_confirm_button"
    return None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True


PR6_LOW_RISK_ACTIONS = [
    "claim_chapter_reward",
    "recruit_soldiers",
    "upgrade_building",
]

LOW_RISK_NEXT_FIXTURE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "claim_chapter_reward": {
        "code": "chapter_claim_button_terminal_fixture",
        "required_page": "chapter",
        "required_semantic_target": "progress.chapter_claim_button",
        "required_action_param_paths": [
            "claim_button.visible",
            "claim_button.enabled",
            "claim_button.bbox.x_min",
            "claim_button.bbox.y_min",
            "claim_button.bbox.x_max",
            "claim_button.bbox.y_max",
        ],
        "expected_runtime_dispatch": {
            "status": "ok",
            "target_key": "chapter_claim_button",
            "terminal_for_verifier": True,
        },
    },
    "recruit_soldiers": {
        "code": "recruit_button_terminal_fixture",
        "required_page": "recruit",
        "required_semantic_target": "teams[*].recruit_button",
        "required_action_param_paths": [
            "recruit_button.visible",
            "recruit_button.enabled",
            "recruit_button.bbox.x_min",
            "recruit_button.bbox.y_min",
            "recruit_button.bbox.x_max",
            "recruit_button.bbox.y_max",
        ],
        "expected_runtime_dispatch": {
            "status": "ok",
            "target_key": "recruit_button",
            "terminal_for_verifier": True,
        },
    },
    "upgrade_building": {
        "code": "upgrade_confirm_button_terminal_fixture",
        "required_page": "building_upgrade",
        "required_semantic_target": "city.upgrade_dialog.confirm_button",
        "required_action_param_paths": [
            "upgrade_dialog.visible",
            "upgrade_dialog.confirm_button.visible",
            "upgrade_dialog.confirm_button.enabled",
            "upgrade_dialog.confirm_button.bbox.x_min",
            "upgrade_dialog.confirm_button.bbox.y_min",
            "upgrade_dialog.confirm_button.bbox.x_max",
            "upgrade_dialog.confirm_button.bbox.y_max",
        ],
        "expected_runtime_dispatch": {
            "status": "ok",
            "target_key": "upgrade_confirm_button",
            "terminal_for_verifier": True,
        },
    },
}

LOW_RISK_TERMINAL_SOURCE_REQUIREMENTS: dict[str, dict[str, Any]] = {
    "claim_chapter_reward": {
        "code": "chapter_claim_terminal_real_source",
        "accepted_source_kinds": ["pr5_real_screenshot_fixture", "live_trace_fixture"],
        "required_page": "chapter",
        "required_semantic_target": "progress.chapter_claim_button",
        "required_runtime_dispatch": {
            "status": "ok",
            "target_key": "chapter_claim_button",
            "terminal_for_verifier": True,
        },
        "required_source_evidence": [
            "real screenshot fixture with screenshot path and manifest page=chapter",
            "or live trace with screenshot metadata, act execution summary, and verification record",
        ],
        "required_post_action_delta": ["progress.chapter_claimable=false"],
    },
    "recruit_soldiers": {
        "code": "recruit_terminal_real_source",
        "accepted_source_kinds": ["pr5_real_screenshot_fixture", "live_trace_fixture"],
        "required_page": "recruit",
        "required_semantic_target": "teams[*].recruit_button",
        "required_runtime_dispatch": {
            "status": "ok",
            "target_key": "recruit_button",
            "terminal_for_verifier": True,
        },
        "required_source_evidence": [
            "real screenshot fixture with screenshot path and manifest page=recruit",
            "or live trace with screenshot metadata, act execution summary, and verification record",
        ],
        "required_post_action_delta": [
            "teams.0.soldiers increases",
            "or teams.0.recruit_finish_time present",
            "or economy.reserve_troops decreases",
        ],
    },
    "upgrade_building": {
        "code": "upgrade_confirm_terminal_real_source",
        "accepted_source_kinds": ["pr5_real_screenshot_fixture", "live_trace_fixture"],
        "required_page": "building_upgrade",
        "required_semantic_target": "city.upgrade_dialog.confirm_button",
        "required_runtime_dispatch": {
            "status": "ok",
            "target_key": "upgrade_confirm_button",
            "terminal_for_verifier": True,
        },
        "required_source_evidence": [
            "real screenshot fixture with screenshot path and manifest page=building_upgrade",
            "or live trace with screenshot metadata, act execution summary, and verification record",
        ],
        "required_post_action_delta": [
            "city.buildings.0.level increases",
            "or economy.resources.wood decreases",
        ],
    },
}
