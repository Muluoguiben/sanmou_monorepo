from __future__ import annotations

import errno
import json
import os
from dataclasses import dataclass
from datetime import datetime
import hashlib
from io import BytesIO
import math
from pathlib import Path
import stat
import subprocess
import sys
from typing import Any


REVIEWED_LIVE_EVIDENCE_ROOT = Path(
    "packages/pioneer-agent/tests/fixtures/live-evidence/reviewed"
)
GIT_PROVENANCE_TRUST_BOUNDARY = "committed_reviewed_live_evidence"


class RawTerminalSourceTraceError(ValueError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.details = details or {}


@dataclass(frozen=True)
class RawTerminalSourceCandidate:
    report: dict[str, Any]
    input_root: Path
    input_root_identity: tuple[int, int, int]
    trace_path: Path
    trace_relative_path: Path
    screenshot_path: Path
    screenshot_relative_path: Path
    trace_bytes: bytes
    screenshot_bytes: bytes
    trace_identity: tuple[int, ...]
    screenshot_identity: tuple[int, ...]

    def assert_sources_unchanged(self) -> None:
        try:
            _root, root_descriptor, root_identity = _open_raw_input_root(
                self.input_root
            )
        except RawTerminalSourceTraceError as exc:
            raise RawTerminalSourceTraceError(
                "source_drift",
                "raw input root became unreadable or unsafe during validation",
                details={"cause": exc.code},
            ) from exc
        try:
            if root_identity != self.input_root_identity:
                raise RawTerminalSourceTraceError(
                    "source_drift",
                    "raw input root changed during validation",
                )
            for field, relative_path, expected_bytes, expected_identity in (
                (
                    "trace",
                    self.trace_relative_path,
                    self.trace_bytes,
                    self.trace_identity,
                ),
                (
                    "screenshot",
                    self.screenshot_relative_path,
                    self.screenshot_bytes,
                    self.screenshot_identity,
                ),
            ):
                snapshot, issues = _read_regular_file_snapshot_at(
                    root_descriptor,
                    relative_path,
                )
                if snapshot is None or issues:
                    raise RawTerminalSourceTraceError(
                        "source_drift",
                        f"{field} source became unreadable or unsafe during validation",
                        details={"field": field, "issues": issues},
                    )
                if (
                    snapshot["bytes"] != expected_bytes
                    or snapshot["identity"] != expected_identity
                ):
                    raise RawTerminalSourceTraceError(
                        "source_drift",
                        f"{field} source changed during validation",
                        details={"field": field},
                    )
        finally:
            os.close(root_descriptor)


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
            "ready_for_staging": bool(review["ready_for_staging"]),
            "structural_valid": bool(review["structural_valid"]),
            "accepted_for_closure": bool(review["accepted_for_closure"]),
            "closure_authority_valid": bool(review["closure_authority_valid"]),
            "review": review,
            "suggested_terminal_source_evidence_patch": (
                _terminal_source_evidence_patch_from_review(review)
            ),
            "suggested_advisor_fixture_expectation_patch": (
                _advisor_fixture_expectation_patch_from_review(
                    fixture_name,
                    review,
                    terminal_source_evidence,
                )
            ),
            "next_source_requirements": requirements if not review["accepted_for_closure"] else [],
            "capture_plan": capture_plan,
        }

    def prepare_raw_terminal_source_candidate(
        self,
        *,
        action_type: str,
        trace_path: Path,
        input_root: Path | None = None,
    ) -> RawTerminalSourceCandidate:
        """Validate one raw live trace without granting review or closure authority."""

        requirement = LOW_RISK_TERMINAL_SOURCE_REQUIREMENTS.get(action_type)
        if requirement is None:
            raise RawTerminalSourceTraceError(
                "unsupported_action",
                f"unsupported low-risk action_type: {action_type}",
            )

        raw_source = _load_raw_terminal_source(
            trace_path=Path(trace_path),
            input_root=Path(input_root) if input_root is not None else None,
        )
        root = raw_source["input_root"]
        root_identity = raw_source["input_root_identity"]
        resolved_trace = raw_source["trace_path"]
        resolved_screenshot = raw_source["screenshot_path"]
        trace_snapshot = raw_source["trace_snapshot"]
        screenshot_snapshot = raw_source["screenshot_snapshot"]
        records = raw_source["records"]
        record = raw_source["record"]
        trace_screenshot_path = raw_source["trace_screenshot_path"]
        image_validation = raw_source["image_validation"]

        selected_action = _trace_selected_action(record)
        params = (
            selected_action.get("params")
            if isinstance(selected_action.get("params"), dict)
            else {}
        )
        target_identity = {
            field_name: params.get(field_name)
            for field_name in requirement.get("required_target_identity") or {}
        }
        target_validation = _target_identity_validation(
            target_identity,
            requirement=requirement,
        )
        if not target_validation["valid"]:
            raise RawTerminalSourceTraceError(
                "target_identity",
                "selected action does not contain a valid target identity",
                details={"validation": target_validation},
            )

        screenshot_size = (
            image_validation.get("width"),
            image_validation.get("height"),
        )
        trace_semantics = self._live_trace_evidence_validation(
            str(resolved_trace),
            records=records,
            action_type=action_type,
            screenshot_path=trace_screenshot_path,
            screenshot_bytes=screenshot_snapshot["bytes"],
            screenshot_sha256=screenshot_snapshot["sha256"],
            screenshot_size=screenshot_size,
            required_runtime_dispatch=requirement.get("required_runtime_dispatch") or {},
            requirement=requirement,
            target_identity=target_identity,
        )
        matching_records = trace_semantics.get("matching_records") or []
        if not trace_semantics.get("matched") or len(matching_records) != 1:
            raise RawTerminalSourceTraceError(
                "trace_semantics",
                "raw trace failed the existing terminal-source binding contract",
                details={"validation": trace_semantics},
            )
        matched = matching_records[0]
        terminal_observation = matched.get("terminal_observation")
        required_page = requirement.get("required_page")
        if (
            not isinstance(terminal_observation, dict)
            or terminal_observation.get("page_type") != required_page
        ):
            raise RawTerminalSourceTraceError(
                "terminal_page",
                "terminal observation page_type does not match the action contract",
                details={
                    "required_page": required_page,
                    "actual_page": (
                        terminal_observation.get("page_type")
                        if isinstance(terminal_observation, dict)
                        else None
                    ),
                },
            )

        verification_record = matched["verification_record"]
        post_action_delta = verification_record.get("post_action_delta") or []
        operator_confirmation = dict(matched["operator_confirmation"])
        operator_confirmation["trace_id"] = matched.get("trace_id")
        operator_confirmation["trace_record_index"] = matched.get("index")
        source_paths = {
            "trace": resolved_trace.relative_to(root).as_posix(),
            "screenshot": resolved_screenshot.relative_to(root).as_posix(),
        }
        report = {
            "schema_version": 1,
            "status": "validated_for_pending_review_staging",
            "raw_binding_valid": True,
            "review_status": "pending_review",
            "privacy_review_status": "pending",
            "accepted_for_closure": False,
            "action_type": action_type,
            "source_paths": source_paths,
            "artifacts": {
                "trace": {
                    "sha256": trace_snapshot["sha256"],
                    "bytes": len(trace_snapshot["bytes"]),
                    "record_count": 1,
                },
                "screenshot": {
                    "sha256": screenshot_snapshot["sha256"],
                    "bytes": len(screenshot_snapshot["bytes"]),
                    "width": image_validation["width"],
                    "height": image_validation["height"],
                    "format": image_validation["format"],
                },
            },
            "evidence_fields": {
                "page": required_page,
                "semantic_target": requirement.get("required_semantic_target"),
                "runtime_dispatch": matched["runtime_dispatch"],
                "target_identity": target_identity,
                "post_action_delta": post_action_delta,
                "verification_record": verification_record,
                "operator_confirmation": operator_confirmation,
            },
            "trace_validation": {
                "record_count": trace_semantics["record_count"],
                "matching_record_index": matched.get("index"),
                "trace_id": matched.get("trace_id"),
            },
        }
        candidate = RawTerminalSourceCandidate(
            report=report,
            input_root=root,
            input_root_identity=root_identity,
            trace_path=resolved_trace,
            trace_relative_path=resolved_trace.relative_to(root),
            screenshot_path=resolved_screenshot,
            screenshot_relative_path=resolved_screenshot.relative_to(root),
            trace_bytes=trace_snapshot["bytes"],
            screenshot_bytes=screenshot_snapshot["bytes"],
            trace_identity=trace_snapshot["identity"],
            screenshot_identity=screenshot_snapshot["identity"],
        )
        candidate.assert_sources_unchanged()
        return candidate

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
        blocking_actions = _terminal_source_blocking_actions(
            missing,
            observed,
            real_source_candidates,
        )
        return {
            "checked": checked,
            "ready": checked and not missing,
            "required_actions": PR6_LOW_RISK_ACTIONS,
            "accepted_actions": sorted(accepted_actions),
            "missing_real_terminal_sources": missing,
            "blocking_actions": blocking_actions,
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
            if not source_review["closure_authority_valid"]:
                disqualifiers.append("terminal_source_closure_authority_invalid")
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
                    "structural_valid": source_review["structural_valid"],
                    "closure_authority_valid": source_review["closure_authority_valid"],
                    "closure_disqualifiers": source_review["closure_disqualifiers"],
                    "missing_evidence": source_review["missing_evidence"],
                    "closure_eligible": terminal_ready and source_review["accepted_for_closure"],
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
                    "blocking_actions": source_review.get("blocking_actions") or {},
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
            terminal_ready
            and source_review["structural_valid"]
            and source_review["closure_authority_valid"]
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
        review_metadata_validation = _review_metadata_validation(evidence)
        if not review_metadata_validation["valid"]:
            missing.append("review_metadata")

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

        target_identity = evidence.get("target_identity")
        target_identity_validation = _target_identity_validation(
            target_identity,
            requirement=requirement,
        )
        if not target_identity_validation["valid"]:
            missing.append("target_identity")

        post_action_delta = evidence.get("post_action_delta")
        post_action_delta_validation = _post_action_delta_validation(
            post_action_delta,
            requirement=requirement,
            target_identity=target_identity,
        )
        if not post_action_delta_validation["valid"]:
            missing.append("post_action_delta")
        post_action_delta_evidence_validation = _post_action_delta_evidence_validation(
            evidence.get("post_action_delta_evidence"),
            evidence=evidence,
            requirement=requirement,
            target_identity=target_identity,
            resolve_source_path=self._resolve_source_path,
        )
        if not post_action_delta_evidence_validation["valid"]:
            missing.append("post_action_delta_evidence")
        privacy_review_validation = _privacy_review_validation(evidence.get("privacy_review"))
        if not privacy_review_validation["valid"]:
            missing.append("privacy_review")

        source_snapshots: dict[str, dict[str, Any]] = {}
        if source_evidence_present and source_kind in accepted_source_kinds:
            file_integrity_validation, source_snapshots = self._file_integrity_validation(
                evidence,
                source_kind,
            )
        else:
            file_integrity_validation = {"checked": False, "valid": False, "issues": []}
        if file_integrity_validation["checked"] and not file_integrity_validation["valid"]:
            missing.append("file_integrity")

        trace_validation: dict[str, Any] | None = None
        verification_record_validation: dict[str, Any] | None = None
        operator_confirmation_validation: dict[str, Any] | None = None
        screenshot_decode_validation: dict[str, Any] | None = None
        strict_trace_validation: dict[str, Any] | None = None
        screenshot_path = evidence.get("screenshot")
        if source_kind == "pr5_real_screenshot_fixture":
            if not screenshot_path or not self._source_path_exists(str(screenshot_path)):
                missing.append("screenshot")
        elif source_kind == "live_trace_fixture":
            screenshot_snapshot = source_snapshots.get("screenshot")
            if not screenshot_path or not self._source_path_exists(str(screenshot_path)):
                missing.append("screenshot")
            elif screenshot_snapshot is None:
                missing.append("screenshot_decode")
            else:
                screenshot_decode_validation = _decodable_image_validation(
                    screenshot_snapshot["bytes"]
                )
                if not screenshot_decode_validation["valid"]:
                    missing.append("screenshot_decode")

            trace_path = evidence.get("trace")
            if not trace_path or not self._source_path_exists(str(trace_path)):
                missing.append("trace")
            else:
                resolved_trace = self._resolve_source_path(str(trace_path))
                trace_snapshot = source_snapshots.get("trace")
                trace_records: list[dict[str, Any]] = []
                if resolved_trace is not None and trace_snapshot is not None:
                    strict_trace_validation, trace_records = _strict_trace_file_validation(
                        trace_snapshot["bytes"],
                        path=resolved_trace,
                    )
                if not strict_trace_validation or not strict_trace_validation["valid"]:
                    missing.append("strict_trace")
                trace_validation = self._live_trace_evidence_validation(
                    str(trace_path),
                    records=trace_records,
                    action_type=action_key,
                    screenshot_path=str(screenshot_path) if screenshot_path else None,
                    screenshot_bytes=(
                        screenshot_snapshot.get("bytes")
                        if screenshot_snapshot is not None
                        else None
                    ),
                    screenshot_sha256=(
                        screenshot_snapshot.get("sha256")
                        if screenshot_snapshot is not None
                        else None
                    ),
                    screenshot_size=(
                        (
                            screenshot_decode_validation.get("width"),
                            screenshot_decode_validation.get("height"),
                        )
                        if screenshot_decode_validation
                        and screenshot_decode_validation.get("valid")
                        else None
                    ),
                    required_runtime_dispatch=required_runtime_dispatch,
                    requirement=requirement,
                    target_identity=target_identity,
                )
                if not trace_validation["matched"]:
                    missing.append("trace_semantics")
            verification_record_validation = _verification_record_validation(
                evidence.get("verification_record"),
                action_type=action_key,
                requirement=requirement,
                target_identity=target_identity,
            )
            verification_trace_binding = _verification_record_trace_binding_validation(
                evidence.get("verification_record"),
                trace_validation=trace_validation,
            )
            verification_record_validation["trace_binding"] = verification_trace_binding
            verification_record_validation["valid"] = bool(
                verification_record_validation["valid"]
                and verification_trace_binding["valid"]
            )
            if not verification_trace_binding["valid"]:
                verification_record_validation["issues"] = sorted(
                    set(verification_record_validation["issues"] + ["trace_binding"])
                )
            if not verification_record_validation["valid"]:
                missing.append("verification_record")
            operator_confirmation_validation = _operator_confirmation_validation(
                evidence.get("operator_confirmation"),
                action_type=action_key,
                required_runtime_dispatch=required_runtime_dispatch,
                trace_validation=trace_validation,
                target_identity=target_identity,
            )
            if not operator_confirmation_validation["valid"]:
                missing.append("operator_confirmation")

        structural_valid = not missing
        closure_authority_validation = self._closure_authority_validation(
            evidence,
            source_kind=source_kind,
            source_snapshots=source_snapshots,
        )
        closure_authority_valid = bool(closure_authority_validation["valid"])
        accepted_for_closure = structural_valid and closure_authority_valid
        return {
            "checked": action_type in PR6_LOW_RISK_ACTIONS,
            "action_type": action_type,
            "fixture": fixture,
            "source_kind": source_kind,
            "source_evidence_present": source_evidence_present,
            # Backwards-compatible alias. This now means structural validity only;
            # closure authority is deliberately reported and gated separately.
            "source_evidence_valid": structural_valid,
            "structural_valid": structural_valid,
            "ready_for_staging": structural_valid,
            "closure_authority_valid": closure_authority_valid,
            "closure_authority_validation": closure_authority_validation,
            "closure_disqualifiers": closure_authority_validation["issues"],
            "missing_evidence": sorted(set(missing)),
            "evidence_page": evidence_page,
            "required_page": required_page,
            "semantic_target": semantic_target,
            "required_semantic_target": required_semantic_target,
            "runtime_dispatch": runtime_dispatch if isinstance(runtime_dispatch, dict) else None,
            "required_runtime_dispatch": required_runtime_dispatch,
            "target_identity": target_identity if isinstance(target_identity, dict) else None,
            "required_target_identity": requirement.get("required_target_identity") or {},
            "target_identity_validation": target_identity_validation,
            "post_action_delta": post_action_delta if isinstance(post_action_delta, list) else [],
            "required_post_action_delta": requirement.get("required_post_action_delta") or [],
            "required_post_action_delta_contract": (
                requirement.get("required_post_action_delta_contract") or []
            ),
            "post_action_delta_validation": post_action_delta_validation,
            "post_action_delta_evidence_validation": post_action_delta_evidence_validation,
            "review_metadata_validation": review_metadata_validation,
            "privacy_review_validation": privacy_review_validation,
            "file_integrity_validation": file_integrity_validation,
            "trace_validation": trace_validation,
            "strict_trace_validation": strict_trace_validation,
            "screenshot_decode_validation": screenshot_decode_validation,
            "verification_record_validation": verification_record_validation,
            "operator_confirmation_validation": operator_confirmation_validation,
            "accepted_for_closure": accepted_for_closure,
            "terminal_dispatch_ready": False,
            "next_source_requirements": [],
        }

    def _source_path_exists(self, value: str) -> bool:
        return self._resolve_source_path(value) is not None

    def _file_integrity_validation(
        self,
        evidence: dict[str, Any],
        source_kind: str | None,
    ) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
        required = [("screenshot", "screenshot_sha256")]
        if source_kind == "live_trace_fixture":
            required.append(("trace", "trace_sha256"))

        checks: list[dict[str, Any]] = []
        snapshots: dict[str, dict[str, Any]] = {}
        issues: list[str] = []
        for path_field, hash_field in required:
            path_value = evidence.get(path_field)
            expected_hash = evidence.get(hash_field)
            check = {
                "path_field": path_field,
                "hash_field": hash_field,
                "path": path_value if isinstance(path_value, str) else None,
                "expected_sha256": expected_hash if isinstance(expected_hash, str) else None,
                "actual_sha256": None,
                "matched": False,
                "regular_file": False,
                "link_count": None,
                "snapshot_stable": False,
            }
            if not isinstance(path_value, str) or not path_value:
                issues.append(path_field)
                checks.append(check)
                continue
            resolved_path = self._resolve_source_path(path_value)
            if resolved_path is None:
                issues.append(path_field)
                checks.append(check)
                continue
            snapshot, snapshot_issues = _read_regular_file_snapshot(resolved_path)
            if snapshot is None:
                issues.extend(f"{path_field}_{item}" for item in snapshot_issues)
                checks.append(check)
                continue
            snapshots[path_field] = snapshot
            check["regular_file"] = True
            check["link_count"] = snapshot["link_count"]
            check["snapshot_stable"] = True
            if not _is_sha256(expected_hash):
                issues.append(hash_field)
                check["actual_sha256"] = snapshot["sha256"]
                checks.append(check)
                continue
            actual_hash = snapshot["sha256"]
            check["actual_sha256"] = actual_hash
            check["matched"] = actual_hash == expected_hash
            if not check["matched"]:
                issues.append(f"{hash_field}_mismatch")
            checks.append(check)

        return (
            {
                "checked": True,
                "valid": not issues,
                "issues": sorted(set(issues)),
                "checks": checks,
            },
            snapshots,
        )

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

    def _closure_authority_validation(
        self,
        evidence: dict[str, Any],
        *,
        source_kind: str | None,
        source_snapshots: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        """Validate the current closure trust boundary, independently of semantics.

        A self-consistent JSON object is useful for staging, but it is not closure
        authority. For now authority comes only from regular, non-symlink evidence
        files under the reviewed fixture root whose exact bytes are regular blobs at
        one stable, clean current Git HEAD.
        """

        issues: list[str] = []
        path_checks: list[dict[str, Any]] = []
        if source_kind != "live_trace_fixture":
            issues.append("source_kind_not_live_trace_fixture")

        for field in ("screenshot", "trace"):
            path_check = self._reviewed_live_evidence_path_validation(
                field,
                evidence.get(field),
            )
            path_checks.append(path_check)
            issues.extend(path_check["issues"])

        git_provenance = evidence.get("git_provenance")
        if not isinstance(git_provenance, dict):
            git_provenance = {}
            issues.append("git_provenance")

        declared_boundary = git_provenance.get("trust_boundary")
        if declared_boundary != GIT_PROVENANCE_TRUST_BOUNDARY:
            issues.append("git_provenance.trust_boundary")
        declared_root = git_provenance.get("reviewed_root")
        if declared_root != REVIEWED_LIVE_EVIDENCE_ROOT.as_posix():
            issues.append("git_provenance.reviewed_root")

        git_root_result = self._run_git("rev-parse", "--show-toplevel")
        git_available = git_root_result["ok"]
        git_root = git_root_result["stdout"] if git_available else None
        if not git_available:
            issues.append("git_repository")
        else:
            try:
                if Path(str(git_root)).resolve() != self.workspace_root:
                    issues.append("git_repository_root")
            except OSError:
                issues.append("git_repository_root")

        head_result = self._run_git("rev-parse", "HEAD") if git_available else {
            "ok": False,
            "stdout": None,
            "stderr": None,
        }
        head_commit = head_result["stdout"] if head_result["ok"] else None
        if not head_commit:
            issues.append("git_head")
        declared_head = git_provenance.get("head_commit")
        # An embedded HEAD is optional because a manifest cannot contain the hash
        # of the same commit that introduces it. If supplied by an external
        # preflight request, it must still match exactly.
        if declared_head is not None and (
            not isinstance(declared_head, str) or declared_head != head_commit
        ):
            issues.append("git_provenance.head_commit")

        initial_status_result = self._run_git(
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ) if git_available else {"ok": False, "stdout": None, "stderr": None}
        initially_clean = bool(
            initial_status_result["ok"] and not initial_status_result["stdout"]
        )
        if not initially_clean:
            issues.append("git_worktree_not_clean")

        blob_checks: list[dict[str, Any]] = []
        for path_check in path_checks:
            field = path_check["field"]
            repo_path = path_check.get("repo_path")
            source_snapshot = source_snapshots.get(field)
            blob_check = {
                "field": field,
                "repo_path": repo_path,
                "committed": False,
                "git_mode": None,
                "git_type": None,
                "head_path": None,
                "head_blob": None,
                "declared_blob": git_provenance.get(f"{field}_blob"),
                "worktree_sha256": (
                    source_snapshot.get("sha256")
                    if source_snapshot is not None
                    else None
                ),
                "head_sha256": None,
                "worktree_matches_head": False,
                "worktree_stable": False,
                "matched": False,
            }
            head_bytes: bytes | None = None
            if (
                path_check["valid"]
                and git_available
                and head_commit
                and isinstance(repo_path, str)
            ):
                head_validation, head_bytes = self._head_blob_snapshot(
                    head_commit,
                    repo_path,
                )
                blob_check.update(head_validation)
                blob_check["committed"] = bool(head_validation["valid"])
                if head_bytes is not None:
                    blob_check["head_sha256"] = _sha256_bytes(head_bytes)
                if source_snapshot is not None and head_bytes is not None:
                    blob_check["worktree_matches_head"] = (
                        source_snapshot["bytes"] == head_bytes
                    )
                    if not blob_check["worktree_matches_head"]:
                        issues.append(f"{field}_worktree_not_head_blob")
                declared_blob = blob_check["declared_blob"]
                blob_check["matched"] = bool(
                    blob_check["committed"]
                    and isinstance(declared_blob, str)
                    and declared_blob == blob_check["head_blob"]
                    and blob_check["worktree_matches_head"]
                )
            if not blob_check["committed"]:
                issues.append(f"{field}_not_committed_regular_blob")
            if not blob_check["matched"]:
                issues.append(f"git_provenance.{field}_blob")
            blob_checks.append(blob_check)

        # Re-open every worktree artifact after all Git reads. All semantic checks
        # above used the first immutable byte snapshot; this final comparison makes
        # a replacement or write during preflight fail closed instead of mixing
        # multiple file versions into one closure decision.
        for path_check, blob_check in zip(path_checks, blob_checks, strict=True):
            field = path_check["field"]
            original = source_snapshots.get(field)
            resolved_path = path_check.get("resolved_path")
            if original is None or not isinstance(resolved_path, str):
                issues.append(f"{field}_worktree_snapshot")
                continue
            final_snapshot, final_issues = _read_regular_file_snapshot(Path(resolved_path))
            if final_snapshot is None:
                issues.extend(f"{field}_{item}" for item in final_issues)
                issues.append(f"{field}_worktree_changed_during_validation")
                continue
            stable = bool(
                final_snapshot["bytes"] == original["bytes"]
                and final_snapshot["identity"] == original["identity"]
            )
            blob_check["worktree_stable"] = stable
            if not stable:
                issues.append(f"{field}_worktree_changed_during_validation")
                blob_check["matched"] = False

        final_head_result = self._run_git("rev-parse", "HEAD") if git_available else {
            "ok": False,
            "stdout": None,
            "stderr": None,
        }
        head_stable = bool(
            final_head_result["ok"] and final_head_result["stdout"] == head_commit
        )
        if not head_stable:
            issues.append("git_head_changed_during_validation")
        final_status_result = self._run_git(
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
        ) if git_available else {"ok": False, "stdout": None, "stderr": None}
        finally_clean = bool(
            final_status_result["ok"] and not final_status_result["stdout"]
        )
        repository_clean = initially_clean and finally_clean
        if not finally_clean:
            issues.append("git_worktree_not_clean")

        bound_to_clean_head = bool(
            repository_clean
            and head_commit
            and head_stable
            and blob_checks
            and all(item["matched"] for item in blob_checks)
        )
        return {
            "checked": True,
            "valid": not issues,
            "trust_boundary": GIT_PROVENANCE_TRUST_BOUNDARY,
            "reviewed_root": REVIEWED_LIVE_EVIDENCE_ROOT.as_posix(),
            "git_available": git_available,
            "git_root": git_root,
            "head_commit": head_commit,
            "declared_head_commit": declared_head,
            "repository_clean": repository_clean,
            "head_stable": head_stable,
            "bound_to_clean_head": bound_to_clean_head,
            "path_checks": path_checks,
            "blob_checks": blob_checks,
            "issues": sorted(set(issues)),
        }

    def _reviewed_live_evidence_path_validation(
        self,
        field: str,
        value: Any,
    ) -> dict[str, Any]:
        issues: list[str] = []
        repo_path: str | None = None
        resolved_path: str | None = None
        link_count: int | None = None
        path = Path(value) if isinstance(value, str) and value else None
        if path is None:
            issues.append(f"{field}_path")
        elif path.is_absolute():
            issues.append(f"{field}_path_not_repo_relative")
        elif ".." in path.parts:
            issues.append(f"{field}_path_escape")
        else:
            candidate = self.workspace_root / path
            reviewed_root = self.workspace_root / REVIEWED_LIVE_EVIDENCE_ROOT
            try:
                candidate_relative = candidate.relative_to(self.workspace_root)
                candidate.relative_to(reviewed_root)
                repo_path = candidate_relative.as_posix()
                candidate_resolved = candidate.resolve(strict=True)
                reviewed_root_resolved = reviewed_root.resolve(strict=True)
                candidate_resolved.relative_to(reviewed_root_resolved)
                resolved_path = str(candidate_resolved)
                cursor = self.workspace_root
                symlink_component = False
                for part in candidate_relative.parts:
                    cursor = cursor / part
                    if cursor.is_symlink():
                        symlink_component = True
                        break
                    is_junction = getattr(cursor, "is_junction", None)
                    if callable(is_junction) and is_junction():
                        issues.append(f"{field}_junction")
                        break
                if symlink_component:
                    issues.append(f"{field}_symlink")
                try:
                    mode = candidate.lstat().st_mode
                except OSError:
                    mode = 0
                if not stat.S_ISREG(mode):
                    issues.append(f"{field}_not_regular_file")
                else:
                    try:
                        link_count = candidate.lstat().st_nlink
                    except OSError:
                        link_count = None
                    if link_count != 1:
                        issues.append(f"{field}_hardlink")
            except (FileNotFoundError, OSError, ValueError):
                issues.append(f"{field}_outside_reviewed_root")

        return {
            "field": field,
            "value": value if isinstance(value, str) else None,
            "repo_path": repo_path,
            "resolved_path": resolved_path,
            "link_count": link_count,
            "valid": not issues,
            "issues": sorted(set(issues)),
        }

    def _head_blob_snapshot(
        self,
        head_commit: str,
        repo_path: str,
    ) -> tuple[dict[str, Any], bytes | None]:
        """Read exactly one literal path from an immutable HEAD tree."""

        issues: list[str] = []
        mode: str | None = None
        object_type: str | None = None
        object_id: str | None = None
        returned_path: str | None = None
        result = self._run_git_bytes(
            "ls-tree",
            "-z",
            "--full-tree",
            head_commit,
            "--",
            repo_path,
            literal_paths=True,
        )
        records = [item for item in (result["stdout"] or b"").split(b"\0") if item]
        if not result["ok"]:
            issues.append("head_ls_tree")
        elif len(records) != 1:
            issues.append("head_entry_count")
        else:
            record = records[0]
            try:
                metadata, returned_path_bytes = record.split(b"\t", 1)
                mode_bytes, type_bytes, object_id_bytes = metadata.split(b" ", 2)
                mode = mode_bytes.decode("ascii")
                object_type = type_bytes.decode("ascii")
                object_id = object_id_bytes.decode("ascii")
                returned_path = returned_path_bytes.decode("utf-8", errors="surrogateescape")
                expected_path_bytes = repo_path.encode("utf-8", errors="surrogateescape")
                if returned_path_bytes != expected_path_bytes:
                    issues.append("head_path_mismatch")
            except (UnicodeError, ValueError):
                issues.append("head_entry_parse")
        if mode not in {"100644", "100755"}:
            issues.append("head_mode")
        if object_type != "blob":
            issues.append("head_type")

        blob_bytes: bytes | None = None
        if object_id is not None and not issues:
            blob_result = self._run_git_bytes("cat-file", "blob", object_id)
            if blob_result["ok"]:
                blob_bytes = blob_result["stdout"]
            else:
                issues.append("head_cat_file")
        return (
            {
                "valid": not issues and blob_bytes is not None,
                "git_mode": mode,
                "git_type": object_type,
                "head_path": returned_path,
                "head_blob": object_id,
                "head_lookup_issues": sorted(set(issues)),
            },
            blob_bytes,
        )

    def _run_git(self, *args: str) -> dict[str, Any]:
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.workspace_root), *args],
                capture_output=True,
                check=False,
                text=True,
                timeout=self.timeout_seconds,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "stdout": None, "stderr": str(exc)}
        return {
            "ok": completed.returncode == 0,
            "stdout": completed.stdout.strip() or None,
            "stderr": completed.stderr.strip() or None,
        }

    def _run_git_bytes(
        self,
        *args: str,
        literal_paths: bool = False,
    ) -> dict[str, Any]:
        env = os.environ.copy()
        if literal_paths:
            env["GIT_LITERAL_PATHSPECS"] = "1"
        try:
            completed = subprocess.run(
                ["git", "-C", str(self.workspace_root), *args],
                capture_output=True,
                check=False,
                text=False,
                timeout=self.timeout_seconds,
                env=env,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return {"ok": False, "stdout": None, "stderr": str(exc)}
        return {
            "ok": completed.returncode == 0,
            "stdout": completed.stdout,
            "stderr": completed.stderr.decode("utf-8", errors="replace").strip() or None,
        }

    def _live_trace_evidence_validation(
        self,
        trace_path: str,
        *,
        records: list[dict[str, Any]],
        action_type: str | None,
        screenshot_path: str | None,
        screenshot_bytes: bytes | None,
        screenshot_sha256: str | None,
        screenshot_size: tuple[Any, Any] | None,
        required_runtime_dispatch: dict[str, Any],
        requirement: dict[str, Any],
        target_identity: Any,
    ) -> dict[str, Any]:
        matching_records: list[dict[str, Any]] = []
        record_evaluations: list[dict[str, Any]] = []
        for index, record in enumerate(records):
            selected_action = _trace_selected_action(record)
            execution = _trace_execution(record)
            verifier = _trace_post_action_verifier(record)
            trace_id = _trace_record_id(record)
            action_matches = selected_action.get("action_type") == action_type
            action_target_validation = _selected_action_target_validation(
                selected_action,
                target_identity=target_identity,
                requirement=requirement,
            )
            dispatch_matches = _runtime_dispatch_matches(execution, required_runtime_dispatch)
            dispatch_time_validation = _trace_dispatch_time_validation(record, execution)
            verifier_validation = _verification_record_validation(
                verifier,
                action_type=action_type,
                requirement=requirement,
                target_identity=target_identity,
            )
            trace_screenshot_path = _trace_screenshot_path(record)
            screenshot_matches = self._source_paths_match(
                trace_screenshot_path,
                screenshot_path,
            )
            terminal_observation_validation = _trace_terminal_observation_validation(
                record,
                screenshot_path=trace_screenshot_path,
                screenshot_sha256=screenshot_sha256,
                screenshot_size=screenshot_size,
                source_paths_match=self._source_paths_match,
            )
            trace_operator_confirmation = _trace_operator_confirmation(record)
            trace_operator_confirmation_validation = (
                _trace_operator_confirmation_validation(
                    trace_operator_confirmation,
                    selected_action=selected_action,
                    execution=execution,
                    action_type=action_type,
                    required_runtime_dispatch=required_runtime_dispatch,
                    target_identity=target_identity,
                    dispatch_time_validation=dispatch_time_validation,
                    terminal_observation_validation=terminal_observation_validation,
                    screenshot_bytes=screenshot_bytes,
                    screenshot_size=screenshot_size,
                )
            )
            summary = execution.get("summary") if isinstance(execution.get("summary"), dict) else {}
            record_evaluations.append(
                {
                    "index": index,
                    "trace_id": trace_id,
                    "action_type": selected_action.get("action_type"),
                    "action_matches": action_matches,
                    "action_target_valid": action_target_validation["valid"],
                    "action_target_issues": action_target_validation["issues"],
                    "dispatch_matches": dispatch_matches,
                    "dispatch_at": dispatch_time_validation["dispatch_at"],
                    "dispatch_time_valid": dispatch_time_validation["valid"],
                    "dispatch_time_issues": dispatch_time_validation["issues"],
                    "screenshot_matches": screenshot_matches,
                    "trace_screenshot_path": trace_screenshot_path,
                    "terminal_observation_valid": terminal_observation_validation["valid"],
                    "terminal_observation_issues": terminal_observation_validation["issues"],
                    "trace_operator_confirmation_valid": trace_operator_confirmation_validation[
                        "valid"
                    ],
                    "trace_operator_confirmation_issues": trace_operator_confirmation_validation[
                        "issues"
                    ],
                    "semantic_frame_guard_validation": trace_operator_confirmation_validation.get(
                        "semantic_frame_guard_validation"
                    ),
                    "target_key": execution.get("target_key") or summary.get("target_key"),
                    "terminal_for_verifier": (
                        execution.get("terminal_for_verifier")
                        if "terminal_for_verifier" in execution
                        else summary.get("terminal_for_verifier")
                    ),
                    "verifier_valid": verifier_validation["valid"],
                    "verifier_issues": verifier_validation["issues"],
                    "verifier_status": verifier_validation["status"],
                    "verifier_checked_paths": verifier_validation["checked_paths"],
                }
            )
            if (
                action_matches
                and action_target_validation["valid"]
                and dispatch_matches
                and dispatch_time_validation["valid"]
                and screenshot_matches
                and verifier_validation["valid"]
                and terminal_observation_validation["valid"]
                and trace_operator_confirmation_validation["valid"]
            ):
                matching_records.append(
                    {
                        "index": index,
                        "trace_id": trace_id,
                        "action_type": selected_action.get("action_type"),
                        "trace_screenshot_path": trace_screenshot_path,
                        "dispatch_at": dispatch_time_validation["dispatch_at"],
                        "selected_action": selected_action,
                        "action_id": selected_action.get("action_id"),
                        "target_key": execution.get("target_key") or summary.get("target_key"),
                        "terminal_for_verifier": (
                            execution.get("terminal_for_verifier")
                            if "terminal_for_verifier" in execution
                            else summary.get("terminal_for_verifier")
                        ),
                        "verifier_status": verifier_validation["status"],
                        "verifier_checked_paths": verifier_validation["checked_paths"],
                        "verification_record": verifier,
                        "terminal_observation": terminal_observation_validation[
                            "observation"
                        ],
                        "operator_confirmation": trace_operator_confirmation,
                        "runtime_dispatch": _runtime_dispatch_projection(execution),
                    }
                )
        return {
            "checked": True,
            "trace": trace_path,
            "record_count": len(records),
            "matched": bool(matching_records),
            "matching_records": matching_records,
            "record_evaluations": record_evaluations,
            "load_error": None,
            "required_action_type": action_type,
            "required_screenshot": screenshot_path,
            "required_screenshot_sha256": screenshot_sha256,
            "required_screenshot_size": (
                list(screenshot_size) if screenshot_size is not None else None
            ),
            "required_runtime_dispatch": required_runtime_dispatch,
            "required_target_identity": requirement.get("required_target_identity") or {},
            "required_post_action_delta": requirement.get("required_post_action_delta") or [],
            "required_post_action_delta_contract": (
                requirement.get("required_post_action_delta_contract") or []
            ),
            "required_verifier_status": "verified",
        }

    def _source_paths_match(self, actual: str | None, expected: str | None) -> bool:
        if not actual or not expected:
            return False
        if actual == expected:
            return True
        actual_resolved = self._resolve_source_path(actual)
        expected_resolved = self._resolve_source_path(expected)
        if actual_resolved is not None and expected_resolved is not None:
            return actual_resolved.resolve() == expected_resolved.resolve()
        return False

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
                "required_target_identity": requirement["required_target_identity"],
                "required_post_action_delta": requirement["required_post_action_delta"],
                "required_post_action_delta_contract": requirement[
                    "required_post_action_delta_contract"
                ],
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
                    "reviewed_by",
                    "reviewed_at",
                    "screenshot",
                    "screenshot_sha256",
                    "privacy_review",
                    "page",
                    "semantic_target",
                    "runtime_dispatch",
                    "target_identity",
                    "post_action_delta",
                    "post_action_delta_evidence",
                ],
                "privacy_review_fields": [
                    "status=approved",
                    "reviewed_by",
                    "reviewed_at",
                    "screenshot_scope",
                    "redaction_applied",
                    "contains_account_identifier=false",
                    "contains_chat_or_social_text=false",
                    "contains_payment_or_secret=false",
                    "approved_for_repo_storage=true",
                ],
                "live_trace_extra_fields": [
                    "trace",
                    "trace_sha256",
                    "verification_record",
                    "operator_confirmation",
                ],
                "live_trace_semantic_checks": [
                    "selected_action.action_type matches action_type",
                    "execution.status matches required_runtime_dispatch.status",
                    "execution.summary.target_key matches required_runtime_dispatch.target_key",
                    "execution.summary.terminal_for_verifier=true",
                    "execution.summary.dispatch_at is aware ISO-8601",
                    "trace.screenshot.path matches terminal_source_evidence.screenshot",
                    "verification.post_action_verifier.status=verified",
                    "selected_action.params and verification target/delta match target_identity",
                    "execution.summary.operator_confirmation is present and confirmed=true",
                    "trace terminal_dispatch and primary observations bind the exact HEAD screenshot SHA-256 and decoded frame_size",
                    "operator confirmation semantic_frame_guard fully binds target ROI and decoded screenshot dimensions",
                    "semantic_frame_guard.capture_geometry exactly mirrors the terminal observation backend, outer window, capture rect/origin, and frame_size",
                    "trace confirmation binds selected action/action_id, target key/identity, and runtime dispatch",
                    "trace confirmation_id/request_id are non-empty and all confirmation timestamps are aware and ordered",
                    "manifest operator_confirmation exactly mirrors the matched trace confirmation plus trace_id/trace_record_index",
                ],
                "advisor_fixture_manifest_target": (
                    _advisor_fixture_manifest_target(action_type)
                ),
                "preflight_tool_calls": _terminal_source_preflight_tool_calls(requirement),
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


def _terminal_source_blocking_actions(
    missing_actions: list[str],
    observed_reviews: list[dict[str, Any]],
    candidates: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    observed_by_action = {
        str(item.get("action_type")): item
        for item in observed_reviews
        if item.get("action_type") in PR6_LOW_RISK_ACTIONS
    }
    candidates_by_action: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        action_type = str(candidate.get("action_type"))
        candidates_by_action.setdefault(action_type, []).append(candidate)

    requirements_by_action = {
        item["action_type"]: item
        for item in _terminal_source_requirements(missing_actions)
    }
    blocking: dict[str, dict[str, Any]] = {}
    for action_type in sorted(set(missing_actions)):
        observed = observed_by_action.get(action_type, {})
        action_candidates = candidates_by_action.get(action_type, [])
        candidate_disqualifiers = sorted(
            {
                str(disqualifier)
                for candidate in action_candidates
                for disqualifier in candidate.get("disqualifiers") or []
            }
        )
        missing_evidence = sorted(set(observed.get("missing_evidence") or []))
        blockers = {"missing_real_terminal_source"}
        if not action_candidates:
            blockers.add("no_real_source_candidate")
        elif not any(candidate.get("terminal_dispatch_ready") for candidate in action_candidates):
            blockers.add("no_terminal_real_candidate")
        if action_candidates and not any(candidate.get("source_evidence_valid") for candidate in action_candidates):
            blockers.add("no_valid_terminal_source_evidence")
        if action_candidates and not any(candidate.get("closure_authority_valid") for candidate in action_candidates):
            blockers.add("no_trusted_terminal_source_authority")

        requirement = requirements_by_action.get(action_type, {})
        blocking[action_type] = {
            "blockers": sorted(blockers),
            "observed_source_kind": observed.get("source_kind"),
            "observed_missing_evidence": missing_evidence,
            "candidate_count": len(action_candidates),
            "candidate_disqualifiers": (
                candidate_disqualifiers or ["missing_real_source_candidate"]
            ),
            "required_page": requirement.get("required_page"),
            "required_semantic_target": requirement.get("required_semantic_target"),
            "required_runtime_dispatch": requirement.get("required_runtime_dispatch"),
            "required_target_identity": requirement.get("required_target_identity") or {},
            "required_post_action_delta": requirement.get("required_post_action_delta"),
            "required_post_action_delta_contract": (
                requirement.get("required_post_action_delta_contract") or []
            ),
            "accepted_source_kinds": requirement.get("accepted_source_kinds") or [],
        }
    return blocking


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


def _advisor_fixture_manifest_target(action_type: str) -> dict[str, Any]:
    fixture_key = f"<{action_type}_terminal_fixture>.json"
    return {
        "expectations_path": (
            "packages/pioneer-agent/tests/golden/advisor_fixture_expectations.json"
        ),
        "fixture_key": fixture_key,
        "json_path": f"fixtures.{fixture_key}",
    }


def _terminal_source_preflight_tool_calls(requirement: dict[str, Any]) -> list[dict[str, Any]]:
    action_type = str(requirement["action_type"])
    calls: list[dict[str, Any]] = []
    for source_kind in requirement.get("accepted_source_kinds") or []:
        calls.append(
            {
                "source_kind": source_kind,
                "tool_name": "advisor_terminal_source_evidence_eval",
                "arguments": {
                    "action_type": action_type,
                    "fixture": f"<{action_type}_terminal_fixture>.json",
                    "page": requirement["required_page"],
                    "terminal_source_evidence": _terminal_source_evidence_template(
                        requirement,
                        source_kind,
                    ),
                },
            }
        )
    return calls


def _terminal_source_evidence_template(
    requirement: dict[str, Any],
    source_kind: str,
) -> dict[str, Any]:
    action_type = str(requirement["action_type"])
    target_identity = _target_identity_template(requirement)
    delta_template = _post_action_delta_template(
        requirement,
        target_identity=target_identity,
    )
    evidence: dict[str, Any] = {
        "source_kind": source_kind,
        "review_status": "reviewed",
        "reviewed_by": "<reviewer-id>",
        "reviewed_at": "<reviewed-iso8601>",
        "screenshot": (
            f"{REVIEWED_LIVE_EVIDENCE_ROOT.as_posix()}/<capture-date>/"
            f"{action_type}_terminal.jpg"
        ),
        "screenshot_sha256": "<sha256-of-screenshot>",
        "page": requirement["required_page"],
        "semantic_target": requirement["required_semantic_target"],
        "runtime_dispatch": dict(requirement["required_runtime_dispatch"]),
        "target_identity": target_identity,
        "privacy_review": _terminal_source_privacy_review_template(),
        "post_action_delta": [delta_template],
        "post_action_delta_evidence": {
            "source": "verification_record",
            "post_action_delta": [delta_template],
            "supporting_refs": [],
        },
    }
    if source_kind == "live_trace_fixture":
        evidence["trace"] = (
            f"{REVIEWED_LIVE_EVIDENCE_ROOT.as_posix()}/<capture-date>/"
            f"{action_type}_terminal.jsonl"
        )
        evidence["trace_sha256"] = "<sha256-of-trace>"
        evidence["git_provenance"] = {
            "trust_boundary": GIT_PROVENANCE_TRUST_BOUNDARY,
            "reviewed_root": REVIEWED_LIVE_EVIDENCE_ROOT.as_posix(),
            "screenshot_blob": "<git-blob-at-head>",
            "trace_blob": "<git-blob-at-head>",
        }
        evidence["post_action_delta_evidence"] = {
            "source": "verification_record",
            "post_action_delta": [delta_template],
            "supporting_refs": [
                "terminal_source_evidence.trace",
                "terminal_source_evidence.verification_record",
                "operator_confirmation.trace_id",
            ],
        }
        evidence["verification_record"] = {
            "action_type": action_type,
            "status": "verified",
            "target": target_identity,
            "checked": [_delta_template_checked_path(delta_template)],
            "post_action_delta": [delta_template],
        }
        evidence["operator_confirmation"] = {
            "confirmed": True,
            "requires_operator_confirmation": True,
            "scope": "final_mutating_click",
            "confirmation_id": "<confirmation-id-from-trace>",
            "request_id": "<request-id-from-trace>",
            "action_id": "<selected-action-id-from-trace>",
            "action_type": action_type,
            "target_key": requirement["required_runtime_dispatch"]["target_key"],
            "target_identity": target_identity,
            "observation_id": "<terminal-observation-id-from-trace>",
            "frame_sha256": "<terminal-frame-sha256-from-trace>",
            "semantic_frame_guard": {
                "schema_version": 1,
                "algorithm": _SEMANTIC_ROI_ALGORITHM,
                "semantic_target_key": requirement["required_runtime_dispatch"][
                    "target_key"
                ],
                "frame_size": ["<decoded-width>", "<decoded-height>"],
                "capture_geometry": {
                    "schema_version": 1,
                    "capture_backend": "<wgc-or-dxgi>",
                    "outer_window": {
                        "hwnd": "<hwnd>",
                        "pid": "<pid>",
                        "left": "<outer-left>",
                        "top": "<outer-top>",
                        "right": "<outer-right>",
                        "bottom": "<outer-bottom>",
                        "width": "<outer-width>",
                        "height": "<outer-height>",
                    },
                    "capture_rect": {
                        "left": "<capture-left>",
                        "top": "<capture-top>",
                        "right": "<capture-right>",
                        "bottom": "<capture-bottom>",
                        "width": "<decoded-width>",
                        "height": "<decoded-height>",
                    },
                    "capture_origin": {
                        "x": "<capture-left>",
                        "y": "<capture-top>",
                    },
                    "frame_size": ["<decoded-width>", "<decoded-height>"],
                },
                "normalized_bbox": {
                    "x_min": "<target-x-min>",
                    "y_min": "<target-y-min>",
                    "x_max": "<target-x-max>",
                    "y_max": "<target-y-max>",
                },
                "roi_bbox": {
                    "x": "<roi-x>",
                    "y": "<roi-y>",
                    "width": "<roi-width>",
                    "height": "<roi-height>",
                },
                "click_point": {"x": "<click-x>", "y": "<click-y>"},
                "roi_sha256": "<roi-sha256-from-terminal-frame>",
            },
            "observation_captured_at": "<terminal-observation-captured-iso8601>",
            "confirmed_at": "<operator-confirmed-iso8601-from-trace>",
            "expires_at": "<confirmation-expires-iso8601-from-trace>",
            "consumed_at": "<confirmation-consumed-iso8601-from-trace>",
            "dispatch_at": "<dispatch-iso8601-from-trace>",
            "trace_id": "<trace-id-from-matching-record>",
            "trace_record_index": 0,
            "runtime_dispatch": dict(requirement["required_runtime_dispatch"]),
        }
    return evidence


def _target_identity_template(requirement: dict[str, Any]) -> dict[str, Any]:
    return {
        field_name: f"<{field_name}>"
        for field_name in (requirement.get("required_target_identity") or {})
    }


def _post_action_delta_template(
    requirement: dict[str, Any],
    *,
    target_identity: dict[str, Any],
) -> dict[str, Any]:
    contracts = requirement.get("required_post_action_delta_contract") or []
    contract = dict(contracts[0]) if contracts else {}
    selector = contract.get("selector")
    if isinstance(selector, dict):
        identity_param = selector.get("identity_param")
        contract["selector"] = {
            "collection_path": selector.get("collection_path"),
            "identity_field": selector.get("identity_field"),
            "identity_value": target_identity.get(str(identity_param)),
        }
    before = _contract_expected_value(contract, "before", target_identity)
    after = _contract_expected_value(contract, "after", target_identity)
    if before is _UNSET:
        before = f"<{contract.get('path', 'value')}-before>"
    if after is _UNSET:
        after = f"<{contract.get('path', 'value')}-after>"
    contract.pop("before_param", None)
    contract.pop("after_param", None)
    contract["before"] = before
    contract["after"] = after
    if isinstance(contract.get("selector"), dict):
        contract["selector"].pop("identity_param", None)
    return contract


def _delta_template_checked_path(delta: dict[str, Any]) -> str:
    selector = delta.get("selector")
    if isinstance(selector, dict):
        return (
            f"{selector.get('collection_path')}["
            f"{selector.get('identity_field')}={selector.get('identity_value')!r}]"
            f".{delta.get('path')}"
        )
    return str(delta.get("path") or "")


def _terminal_source_evidence_patch_from_review(review: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    integrity = review.get("file_integrity_validation")
    if isinstance(integrity, dict):
        for check in integrity.get("checks") or []:
            if not isinstance(check, dict):
                continue
            hash_field = check.get("hash_field")
            actual_sha256 = check.get("actual_sha256")
            if isinstance(hash_field, str) and _is_sha256(actual_sha256):
                patch[hash_field] = actual_sha256

    authority = review.get("closure_authority_validation")
    if isinstance(authority, dict):
        blob_values = {
            f"{check.get('field')}_blob": check.get("head_blob")
            for check in authority.get("blob_checks") or []
            if isinstance(check, dict) and isinstance(check.get("head_blob"), str)
        }
        if len(blob_values) == 2:
            patch["git_provenance"] = {
                "trust_boundary": GIT_PROVENANCE_TRUST_BOUNDARY,
                "reviewed_root": REVIEWED_LIVE_EVIDENCE_ROOT.as_posix(),
                **blob_values,
            }

    if (
        not patch.get("post_action_delta_evidence")
        and review.get("source_kind") == "live_trace_fixture"
        and review.get("post_action_delta")
    ):
        patch["post_action_delta_evidence"] = {
            "source": "verification_record",
            "post_action_delta": list(review.get("post_action_delta") or []),
            "supporting_refs": [
                "terminal_source_evidence.trace",
                "terminal_source_evidence.verification_record",
                "operator_confirmation.trace_id",
            ],
        }

    privacy_validation = review.get("privacy_review_validation")
    if isinstance(privacy_validation, dict) and not privacy_validation.get("valid"):
        patch["privacy_review"] = _terminal_source_privacy_review_template()

    return patch


def _terminal_source_privacy_review_template() -> dict[str, Any]:
    return {
        "status": "approved",
        "reviewed_by": "<privacy-reviewer-id>",
        "reviewed_at": "<privacy-reviewed-iso8601>",
        "screenshot_scope": "terminal_ui_only",
        "redaction_applied": False,
        "contains_account_identifier": False,
        "contains_chat_or_social_text": False,
        "contains_payment_or_secret": False,
        "approved_for_repo_storage": True,
    }


def _advisor_fixture_expectation_patch_from_review(
    fixture: str,
    review: dict[str, Any],
    evidence: dict[str, Any],
) -> dict[str, Any]:
    action_type = str(review.get("action_type") or "")
    if action_type not in PR6_LOW_RISK_ACTIONS:
        return {}
    required_dispatch = review.get("required_runtime_dispatch")
    if not isinstance(required_dispatch, dict) or not required_dispatch:
        return {}

    merged_evidence = dict(evidence)
    merged_evidence.update(_terminal_source_evidence_patch_from_review(review))
    fixture_key = Path(fixture).name
    return {
        fixture_key: {
            "page": review.get("required_page") or merged_evidence.get("page"),
            "screenshot": merged_evidence.get("screenshot"),
            "expected_action_type": action_type,
            "expected_dispatch_status": required_dispatch.get("status"),
            "expected_dispatch_target_key": required_dispatch.get("target_key"),
            "expected_dispatch_terminal_for_verifier": required_dispatch.get(
                "terminal_for_verifier"
            ),
            "terminal_source_evidence": merged_evidence,
        }
    }


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
    flattened = _runtime_dispatch_projection(actual)
    return all(flattened.get(key) == expected for key, expected in required.items())


def _runtime_dispatch_projection(actual: dict[str, Any]) -> dict[str, Any]:
    summary = actual.get("summary") if isinstance(actual.get("summary"), dict) else {}
    return {
        "status": actual.get("status"),
        "target_key": actual.get("target_key") or summary.get("target_key"),
        "terminal_for_verifier": (
            actual.get("terminal_for_verifier")
            if "terminal_for_verifier" in actual
            else summary.get("terminal_for_verifier")
        ),
    }


def _target_identity_validation(
    value: Any,
    *,
    requirement: dict[str, Any],
) -> dict[str, Any]:
    schema = requirement.get("required_target_identity") or {}
    issues: list[str] = []
    if not isinstance(value, dict):
        return {
            "valid": False,
            "issues": ["target_identity_not_object"],
            "target_identity": None,
        }

    for field_name, field_spec in schema.items():
        field_value = value.get(field_name)
        value_type = field_spec.get("type") if isinstance(field_spec, dict) else None
        if value_type == "positive_integer":
            valid = (
                isinstance(field_value, int)
                and not isinstance(field_value, bool)
                and field_value > 0
            )
        elif value_type == "nonnegative_integer":
            valid = (
                isinstance(field_value, int)
                and not isinstance(field_value, bool)
                and field_value >= 0
            )
        elif value_type == "nonempty_string":
            valid = isinstance(field_value, str) and bool(field_value.strip())
        else:
            valid = field_name in value and field_value is not None
        if not valid:
            issues.append(field_name)

    current_level = value.get("current_level")
    target_level = value.get("target_level")
    if "current_level" in schema and "target_level" in schema:
        if (
            isinstance(current_level, bool)
            or not isinstance(current_level, int)
            or isinstance(target_level, bool)
            or not isinstance(target_level, int)
            or target_level != current_level + 1
        ):
            issues.append("target_level_relation")

    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "target_identity": dict(value),
    }


def _selected_action_target_validation(
    selected_action: Any,
    *,
    target_identity: Any,
    requirement: dict[str, Any],
) -> dict[str, Any]:
    target_validation = _target_identity_validation(
        target_identity,
        requirement=requirement,
    )
    issues = list(target_validation["issues"])
    params = selected_action.get("params") if isinstance(selected_action, dict) else None
    if not isinstance(params, dict):
        issues.append("selected_action.params")
        params = {}
    if isinstance(target_identity, dict):
        for field_name in (requirement.get("required_target_identity") or {}):
            if not _strict_value_equal(params.get(field_name), target_identity.get(field_name)):
                issues.append(f"selected_action.params.{field_name}")
    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "selected_params": params,
    }


def _post_action_delta_validation(
    value: Any,
    *,
    requirement: dict[str, Any],
    target_identity: Any,
) -> dict[str, Any]:
    contracts = requirement.get("required_post_action_delta_contract") or []
    issues: list[str] = []
    matches: list[dict[str, Any]] = []
    if not isinstance(value, list) or not value:
        return {
            "valid": False,
            "issues": ["post_action_delta_not_nonempty_list"],
            "matches": [],
        }
    if not _target_identity_validation(
        target_identity,
        requirement=requirement,
    )["valid"]:
        issues.append("target_identity")

    for index, delta in enumerate(value):
        if not isinstance(delta, dict):
            issues.append(f"delta[{index}].not_object")
            continue
        matched_contract = next(
            (
                contract
                for contract in contracts
                if _delta_matches_contract(
                    delta,
                    contract,
                    target_identity=target_identity,
                )
            ),
            None,
        )
        if matched_contract is None:
            issues.append(f"delta[{index}].target_bound_contract")
        else:
            matches.append({"index": index, "contract": matched_contract})

    return {
        "valid": not issues and len(matches) == len(value),
        "issues": sorted(set(issues)),
        "matches": matches,
    }


def _delta_matches_contract(
    delta: dict[str, Any],
    contract: dict[str, Any],
    *,
    target_identity: Any,
) -> bool:
    if delta.get("path") != contract.get("path"):
        return False
    if delta.get("operator") != contract.get("operator"):
        return False

    required_selector = contract.get("selector")
    actual_selector = delta.get("selector")
    if isinstance(required_selector, dict):
        if not isinstance(actual_selector, dict) or not isinstance(target_identity, dict):
            return False
        identity_param = required_selector.get("identity_param")
        expected_identity = target_identity.get(identity_param)
        if not _strict_value_equal(
            actual_selector.get("identity_value"),
            expected_identity,
        ):
            return False
        for field_name in ("collection_path", "identity_field"):
            if actual_selector.get(field_name) != required_selector.get(field_name):
                return False
    elif actual_selector not in (None, {}):
        return False

    if "before" not in delta or "after" not in delta:
        return False
    before = delta.get("before")
    after = delta.get("after")
    expected_before = _contract_expected_value(contract, "before", target_identity)
    expected_after = _contract_expected_value(contract, "after", target_identity)
    operator = contract.get("operator")

    if expected_before is not _UNSET and not _strict_value_equal(before, expected_before):
        return False
    if expected_after is not _UNSET and not _strict_value_equal(after, expected_after):
        return False
    if not _contract_value_type_matches(after, contract.get("value_type")):
        return False
    if operator == "changes_to":
        return not _strict_value_equal(before, after)
    if operator == "greater_than_before":
        return _is_finite_number(before) and _is_finite_number(after) and after > before
    if operator == "becomes_present":
        return before in (None, "", [], {}) and after not in (None, "", [], {})
    if operator == "increases_to":
        return (
            _is_finite_number(before)
            and _is_finite_number(after)
            and after > before
            and expected_after is not _UNSET
            and _strict_value_equal(after, expected_after)
        )
    return False


def _contract_value_type_matches(value: Any, value_type: Any) -> bool:
    if value_type is None:
        return True
    if value_type != "aware_datetime_or_nonempty_string":
        return False
    if isinstance(value, datetime):
        return value.tzinfo is not None and value.utcoffset() is not None
    return isinstance(value, str) and bool(value.strip())


_UNSET = object()


def _contract_expected_value(
    contract: dict[str, Any],
    phase: str,
    target_identity: Any,
) -> Any:
    if phase in contract:
        return contract[phase]
    param_name = contract.get(f"{phase}_param")
    if isinstance(param_name, str) and isinstance(target_identity, dict):
        return target_identity.get(param_name, _UNSET)
    return _UNSET


def _strict_value_equal(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    return left == right


def _is_finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and (not isinstance(value, float) or math.isfinite(value))
    )


def _verification_record_validation(
    value: Any,
    *,
    action_type: str | None,
    requirement: dict[str, Any],
    target_identity: Any,
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
    verification_target = verifier.get("target") or value.get("target")
    post_action_delta = verifier.get("post_action_delta") or value.get("post_action_delta")
    issues: list[str] = []
    if action_value != action_type:
        issues.append("action_type")
    if status != "verified":
        issues.append("status")
    target_validation = _target_identity_validation(
        verification_target,
        requirement=requirement,
    )
    if not target_validation["valid"]:
        issues.append("target_identity")
    elif not _target_identity_matches(
        verification_target,
        target_identity,
        requirement=requirement,
    ):
        issues.append("target_identity")
    delta_validation = _post_action_delta_validation(
        post_action_delta,
        requirement=requirement,
        target_identity=target_identity,
    )
    if not delta_validation["valid"]:
        issues.append("post_action_delta")
    return {
        "checked": True,
        "valid": not issues,
        "issues": sorted(set(issues)),
        "action_type": action_value,
        "status": status,
        "checked_paths": checked_paths if isinstance(checked_paths, list) else [],
        "target_identity": verification_target if isinstance(verification_target, dict) else None,
        "target_identity_validation": target_validation,
        "post_action_delta_validation": delta_validation,
    }


def _post_action_delta_evidence_validation(
    value: Any,
    *,
    evidence: dict[str, Any],
    requirement: dict[str, Any],
    target_identity: Any,
    resolve_source_path: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "valid": False,
            "issues": ["post_action_delta_evidence_not_object"],
        }
    issues: list[str] = []
    source = value.get("source")
    if source != "verification_record":
        issues.append("source")
    delta = value.get("post_action_delta")
    delta_validation = _post_action_delta_validation(
        delta,
        requirement=requirement,
        target_identity=target_identity,
    )
    if not delta_validation["valid"]:
        issues.append("post_action_delta")
    if not _structured_equal(delta, evidence.get("post_action_delta")):
        issues.append("post_action_delta_binding")
    supporting_refs = value.get("supporting_refs")
    required_refs = {
        "terminal_source_evidence.trace",
        "terminal_source_evidence.verification_record",
        "operator_confirmation.trace_id",
    }
    ref_bindings: list[dict[str, Any]] = []
    if not isinstance(supporting_refs, list) or not all(
        isinstance(item, str) and item.strip() for item in supporting_refs
    ):
        issues.append("supporting_refs")
        supporting_refs = []
    else:
        actual_refs = set(supporting_refs)
        if actual_refs != required_refs:
            issues.append("supporting_refs")
        for ref in supporting_refs:
            binding = _supporting_ref_binding(
                ref,
                evidence=evidence,
                resolve_source_path=resolve_source_path,
            )
            ref_bindings.append(binding)
            if not binding["valid"]:
                issues.append("supporting_ref_binding")
    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "source": source if isinstance(source, str) else None,
        "supporting_refs": supporting_refs if isinstance(supporting_refs, list) else [],
        "ref_bindings": ref_bindings,
        "post_action_delta_validation": delta_validation,
    }


def _supporting_ref_binding(
    ref: str,
    *,
    evidence: dict[str, Any],
    resolve_source_path: Any,
) -> dict[str, Any]:
    if ref == "terminal_source_evidence.trace":
        trace_path = evidence.get("trace")
        resolved = (
            resolve_source_path(str(trace_path))
            if isinstance(trace_path, str) and trace_path
            else None
        )
        valid = resolved is not None and _is_sha256(evidence.get("trace_sha256"))
        return {
            "ref": ref,
            "valid": valid,
            "resolved_path": str(resolved) if resolved is not None else None,
            "hash_field": "trace_sha256",
        }
    if ref == "terminal_source_evidence.verification_record":
        return {
            "ref": ref,
            "valid": isinstance(evidence.get("verification_record"), dict),
            "binding": "trace.verification.post_action_verifier",
        }
    if ref == "operator_confirmation.trace_id":
        confirmation = evidence.get("operator_confirmation")
        trace_id = confirmation.get("trace_id") if isinstance(confirmation, dict) else None
        return {
            "ref": ref,
            "valid": isinstance(trace_id, str) and bool(trace_id.strip()),
            "trace_id": trace_id,
        }

    resolved = resolve_source_path(ref) if isinstance(ref, str) else None
    return {
        "ref": ref,
        "valid": False,
        "resolved_path": str(resolved) if resolved is not None else None,
        "issue": "unsupported_supporting_ref",
    }


def _structured_equal(left: Any, right: Any) -> bool:
    return json.dumps(left, sort_keys=True, ensure_ascii=False, default=str) == json.dumps(
        right,
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    )


def _target_identity_matches(
    actual: Any,
    expected: Any,
    *,
    requirement: dict[str, Any],
) -> bool:
    if not isinstance(actual, dict) or not isinstance(expected, dict):
        return False
    return all(
        _strict_value_equal(actual.get(field_name), expected.get(field_name))
        for field_name in (requirement.get("required_target_identity") or {})
    )


def _verification_record_trace_binding_validation(
    value: Any,
    *,
    trace_validation: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {"valid": False, "issues": ["verification_record_not_object"]}
    matching_records = (
        trace_validation.get("matching_records")
        if isinstance(trace_validation, dict)
        else None
    )
    if not isinstance(matching_records, list) or not matching_records:
        return {"valid": False, "issues": ["matching_trace_record"]}
    expected = _verification_record_fingerprint(value)
    for record in matching_records:
        if not isinstance(record, dict):
            continue
        trace_record = record.get("verification_record")
        if _structured_equal(expected, _verification_record_fingerprint(trace_record)):
            return {
                "valid": True,
                "issues": [],
                "trace_id": record.get("trace_id"),
                "trace_record_index": record.get("index"),
            }
    return {"valid": False, "issues": ["verification_record_mismatch"]}


def _verification_record_fingerprint(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    verifier = value.get("post_action_verifier") if isinstance(value.get("post_action_verifier"), dict) else value
    return {
        "action_type": verifier.get("action_type") or value.get("action_type"),
        "status": verifier.get("status") or value.get("status") or value.get("verification_status"),
        "target": verifier.get("target") or value.get("target"),
        "post_action_delta": verifier.get("post_action_delta") or value.get("post_action_delta"),
    }


def _privacy_review_validation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "valid": False,
            "issues": ["privacy_review_not_object"],
        }
    issues: list[str] = []
    if value.get("status") != "approved":
        issues.append("status")

    metadata_validation = _review_metadata_validation(value)
    issues.extend(metadata_validation["issues"])

    scope = value.get("screenshot_scope")
    allowed_scopes = {
        "terminal_ui_only",
        "redacted_terminal_ui",
        "redacted_full_window",
    }
    if scope not in allowed_scopes:
        issues.append("screenshot_scope")

    redaction_applied = value.get("redaction_applied")
    if not isinstance(redaction_applied, bool):
        issues.append("redaction_applied")
    elif scope in {"redacted_terminal_ui", "redacted_full_window"} and not redaction_applied:
        issues.append("redaction_applied")

    for field in (
        "contains_account_identifier",
        "contains_chat_or_social_text",
        "contains_payment_or_secret",
    ):
        if value.get(field) is not False:
            issues.append(field)
    if value.get("approved_for_repo_storage") is not True:
        issues.append("approved_for_repo_storage")

    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "status": value.get("status") if isinstance(value.get("status"), str) else None,
        "screenshot_scope": scope if isinstance(scope, str) else None,
        "redaction_applied": redaction_applied if isinstance(redaction_applied, bool) else None,
        "metadata_validation": metadata_validation,
    }


def _review_metadata_validation(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "valid": False,
            "issues": ["terminal_source_evidence_not_object"],
        }
    issues: list[str] = []
    reviewed_by = value.get("reviewed_by")
    reviewed_at = value.get("reviewed_at")
    if not _usable_review_string(reviewed_by):
        issues.append("reviewed_by")
    if not _valid_iso_datetime(reviewed_at):
        issues.append("reviewed_at")
    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "reviewed_by": reviewed_by if isinstance(reviewed_by, str) else None,
        "reviewed_at": reviewed_at if isinstance(reviewed_at, str) else None,
    }


def _usable_review_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "<" not in value


def _valid_iso_datetime(value: Any) -> bool:
    if not isinstance(value, str) or not value.strip() or "<" in value:
        return False
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return True


def _parse_aware_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip() and "<" not in value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    text = value.strip().lower()
    return len(text) == 64 and all(char in "0123456789abcdef" for char in text)


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _snapshot_stat_identity(value: os.stat_result) -> tuple[int, ...]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(stat.S_IFMT(value.st_mode)),
        int(value.st_size),
        int(getattr(value, "st_mtime_ns", int(value.st_mtime * 1_000_000_000))),
        int(getattr(value, "st_ctime_ns", int(value.st_ctime * 1_000_000_000))),
        int(value.st_nlink),
    )


def _secure_dirfd_capable() -> bool:
    return bool(
        os.name == "posix"
        and getattr(os, "O_DIRECTORY", 0)
        and getattr(os, "O_NOFOLLOW", 0)
        and os.open in os.supports_dir_fd
        and os.stat in os.supports_dir_fd
        and os.stat in os.supports_follow_symlinks
    )


def _normalized_absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _directory_identity(value: os.stat_result) -> tuple[int, int, int]:
    return (
        int(value.st_dev),
        int(value.st_ino),
        int(stat.S_IFMT(value.st_mode)),
    )


def _open_directory_no_symlinks(path: Path) -> tuple[Path, int, tuple[int, int, int]]:
    """Open one absolute directory path component-by-component without reparse hops."""

    if not _secure_dirfd_capable():
        raise OSError(errno.ENOTSUP, "secure POSIX dir_fd operations are unavailable")
    lexical = _normalized_absolute_path(path)
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(lexical.anchor, flags)
    try:
        for part in lexical.parts[1:]:
            if part in {"", "."}:
                continue
            if part == "..":
                raise OSError(errno.EPERM, "parent traversal is not allowed")
            next_descriptor = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = next_descriptor
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            raise OSError(errno.ENOTDIR, "path is not a directory")
        return lexical, descriptor, _directory_identity(opened)
    except Exception:
        os.close(descriptor)
        raise


def _open_raw_input_root(path: Path) -> tuple[Path, int, tuple[int, int, int]]:
    try:
        return _open_directory_no_symlinks(path)
    except OSError as exc:
        if exc.errno == errno.ENOTSUP:
            raise RawTerminalSourceTraceError(
                "unsupported_platform",
                "raw staging requires secure POSIX dir_fd support",
            ) from exc
        code = (
            "input_root_symlink"
            if exc.errno in {errno.ELOOP, errno.ENOTDIR}
            else "input_root"
        )
        raise RawTerminalSourceTraceError(
            code,
            "raw input root does not exist, is unreadable, or contains a symlink",
        ) from exc


def _load_raw_terminal_source(
    *,
    trace_path: Path,
    input_root: Path | None,
) -> dict[str, Any]:
    raw_root = Path(input_root) if input_root is not None else trace_path.parent
    root, root_descriptor, root_identity = _open_raw_input_root(raw_root)
    try:
        resolved_trace = _resolve_raw_source_path(
            trace_path,
            input_root=root,
            base_dir=Path.cwd(),
            field="trace",
        )
        trace_snapshot = _required_raw_snapshot(
            resolved_trace,
            field="trace",
            input_root=root,
            input_root_descriptor=root_descriptor,
        )
        strict_trace, records = _strict_trace_file_validation(
            trace_snapshot["bytes"],
            path=resolved_trace,
        )
        if not strict_trace["valid"]:
            raise RawTerminalSourceTraceError(
                "invalid_trace_jsonl",
                "raw trace failed strict JSONL validation",
                details={"validation": strict_trace},
            )
        if len(records) != 1:
            raise RawTerminalSourceTraceError(
                "trace_record_count",
                "raw staging accepts exactly one trace record",
                details={"record_count": len(records)},
            )

        record = records[0]
        frames = record.get("frames") if isinstance(record.get("frames"), list) else []
        terminal_frames = [
            frame
            for frame in frames
            if isinstance(frame, dict) and frame.get("role") == "terminal_dispatch"
        ]
        if len(terminal_frames) != 1:
            raise RawTerminalSourceTraceError(
                "terminal_frame_count",
                "trace must contain exactly one terminal_dispatch frame",
                details={"terminal_frame_count": len(terminal_frames)},
            )
        terminal_frame_path = terminal_frames[0].get("path")
        trace_screenshot = record.get("screenshot")
        trace_screenshot_path = (
            trace_screenshot.get("path")
            if isinstance(trace_screenshot, dict)
            else None
        )
        if (
            not isinstance(terminal_frame_path, str)
            or not terminal_frame_path.strip()
            or not isinstance(trace_screenshot_path, str)
            or not trace_screenshot_path.strip()
        ):
            raise RawTerminalSourceTraceError(
                "terminal_frame_path",
                "trace screenshot and terminal frame require non-empty paths",
            )
        if terminal_frame_path != trace_screenshot_path:
            raise RawTerminalSourceTraceError(
                "terminal_frame_path_binding",
                "trace screenshot path must exactly match terminal frame path",
            )
        resolved_screenshot = _resolve_raw_source_path(
            Path(terminal_frame_path),
            input_root=root,
            base_dir=resolved_trace.parent,
            field="screenshot",
        )
        if resolved_screenshot.suffix.lower() != ".png":
            raise RawTerminalSourceTraceError(
                "terminal_frame_format",
                "terminal frame must be an original PNG",
            )
        screenshot_snapshot = _required_raw_snapshot(
            resolved_screenshot,
            field="screenshot",
            input_root=root,
            input_root_descriptor=root_descriptor,
        )
        image_validation = _decodable_image_validation(screenshot_snapshot["bytes"])
        if not image_validation["valid"] or image_validation.get("format") != "PNG":
            raise RawTerminalSourceTraceError(
                "terminal_frame_decode",
                "terminal frame is not a fully decodable PNG",
                details={"validation": image_validation},
            )
        return {
            "input_root": root,
            "input_root_identity": root_identity,
            "trace_path": resolved_trace,
            "screenshot_path": resolved_screenshot,
            "trace_snapshot": trace_snapshot,
            "screenshot_snapshot": screenshot_snapshot,
            "records": records,
            "record": record,
            "trace_screenshot_path": trace_screenshot_path,
            "image_validation": image_validation,
        }
    finally:
        os.close(root_descriptor)


def _resolve_raw_source_path(
    value: Path,
    *,
    input_root: Path,
    base_dir: Path,
    field: str,
) -> Path:
    if ".." in value.parts:
        raise RawTerminalSourceTraceError(
            "path_escape",
            f"{field} path must not contain parent traversal",
            details={"field": field},
        )
    candidate = value if value.is_absolute() else base_dir / value
    lexical = _normalized_absolute_path(candidate)
    try:
        lexical.relative_to(input_root)
    except ValueError as exc:
        raise RawTerminalSourceTraceError(
            "path_escape",
            f"{field} path escapes the raw input root",
            details={"field": field},
        ) from exc
    return lexical


def _required_raw_snapshot(
    path: Path,
    *,
    field: str,
    input_root: Path,
    input_root_descriptor: int,
) -> dict[str, Any]:
    try:
        relative_path = path.relative_to(input_root)
    except ValueError as exc:
        raise RawTerminalSourceTraceError(
            "path_escape",
            f"{field} path escapes the raw input root",
            details={"field": field},
        ) from exc
    snapshot, issues = _read_regular_file_snapshot_at(
        input_root_descriptor,
        relative_path,
    )
    if snapshot is None or issues:
        if "symlink" in issues:
            raise RawTerminalSourceTraceError(
                "source_symlink",
                f"{field} path contains a symlink",
                details={"field": field, "issues": issues},
            )
        raise RawTerminalSourceTraceError(
            "unsafe_source_file",
            f"{field} must be a unique-link regular file",
            details={"field": field, "issues": issues},
        )
    return snapshot


def _read_regular_file_snapshot_at(
    root_descriptor: int,
    relative_path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Read a stable file below one already-pinned directory descriptor."""

    if not _secure_dirfd_capable():
        return None, ["unsupported_platform"]
    if relative_path.is_absolute() or ".." in relative_path.parts:
        return None, ["path_escape"]
    parts = [part for part in relative_path.parts if part not in {"", "."}]
    if not parts:
        return None, ["not_regular_file"]

    directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    parent_descriptor = os.dup(root_descriptor)
    try:
        for part in parts[:-1]:
            try:
                next_descriptor = os.open(
                    part,
                    directory_flags,
                    dir_fd=parent_descriptor,
                )
            except OSError as exc:
                issue = (
                    "symlink"
                    if exc.errno in {errno.ELOOP, errno.ENOTDIR}
                    else "unreadable"
                )
                return None, [issue]
            os.close(parent_descriptor)
            parent_descriptor = next_descriptor

        leaf = parts[-1]
        try:
            before = os.stat(
                leaf,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError:
            return None, ["unreadable"]
        if stat.S_ISLNK(before.st_mode):
            return None, ["symlink"]
        if not stat.S_ISREG(before.st_mode):
            return None, ["not_regular_file"]
        if before.st_nlink != 1:
            return None, ["hardlink"]

        flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_BINARY", 0)
        descriptor: int | None = None
        issues: list[str] = []
        try:
            descriptor = os.open(leaf, flags, dir_fd=parent_descriptor)
            opened = os.fstat(descriptor)
            if not stat.S_ISREG(opened.st_mode):
                issues.append("not_regular_file")
            if opened.st_nlink != 1:
                issues.append("hardlink")
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                issues.append("replaced_during_read")
            with os.fdopen(descriptor, "rb", closefd=True) as handle:
                descriptor = None
                data = handle.read()
                after_read = os.fstat(handle.fileno())
        except OSError:
            if descriptor is not None:
                os.close(descriptor)
            return None, sorted(set(issues + ["unreadable"]))

        try:
            after_path = os.stat(
                leaf,
                dir_fd=parent_descriptor,
                follow_symlinks=False,
            )
        except OSError:
            return None, sorted(set(issues + ["replaced_during_read"]))
        opened_identity = _snapshot_stat_identity(opened)
        if _snapshot_stat_identity(after_read) != opened_identity:
            issues.append("changed_during_read")
        if _snapshot_stat_identity(after_path) != opened_identity:
            issues.append("replaced_during_read")
        if len(data) != after_read.st_size:
            issues.append("changed_during_read")
        if issues:
            return None, sorted(set(issues))
        return (
            {
                "bytes": data,
                "sha256": _sha256_bytes(data),
                "identity": opened_identity,
                "link_count": opened.st_nlink,
            },
            [],
        )
    finally:
        os.close(parent_descriptor)


def _read_regular_file_snapshot(
    path: Path,
) -> tuple[dict[str, Any] | None, list[str]]:
    """Read one stable, unique-link regular-file snapshot without following the leaf."""

    issues: list[str] = []
    try:
        before = path.lstat()
    except OSError:
        return None, ["unreadable"]
    if path.is_symlink():
        return None, ["symlink"]
    if not stat.S_ISREG(before.st_mode):
        return None, ["not_regular_file"]
    if before.st_nlink != 1:
        return None, ["hardlink"]

    flags = os.O_RDONLY
    flags |= getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    descriptor: int | None = None
    try:
        descriptor = os.open(path, flags)
        opened = os.fstat(descriptor)
        if not stat.S_ISREG(opened.st_mode):
            issues.append("not_regular_file")
        if opened.st_nlink != 1:
            issues.append("hardlink")
        if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
            issues.append("replaced_during_read")
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            descriptor = None
            data = handle.read()
            after_read = os.fstat(handle.fileno())
    except OSError:
        if descriptor is not None:
            os.close(descriptor)
        return None, sorted(set(issues + ["unreadable"]))

    try:
        after_path = path.lstat()
    except OSError:
        return None, sorted(set(issues + ["replaced_during_read"]))
    opened_identity = _snapshot_stat_identity(opened)
    if _snapshot_stat_identity(after_read) != opened_identity:
        issues.append("changed_during_read")
    if _snapshot_stat_identity(after_path) != opened_identity:
        issues.append("replaced_during_read")
    if len(data) != after_read.st_size:
        issues.append("changed_during_read")
    if issues:
        return None, sorted(set(issues))
    return (
        {
            "path": path,
            "bytes": data,
            "sha256": _sha256_bytes(data),
            "identity": opened_identity,
            "link_count": opened.st_nlink,
        },
        [],
    )


def _decodable_image_validation(value: bytes) -> dict[str, Any]:
    """Use a real decoder and fully load pixels; signatures alone are insufficient."""

    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError:
        return {
            "checked": True,
            "valid": False,
            "format": None,
            "width": None,
            "height": None,
            "issues": ["image_decoder_unavailable"],
        }

    image_format: str | None = None
    width: int | None = None
    height: int | None = None
    try:
        with Image.open(BytesIO(value)) as image:
            image_format = image.format
            width, height = image.size
            image.verify()
        with Image.open(BytesIO(value)) as image:
            image.load()
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        return {
            "checked": True,
            "valid": False,
            "format": image_format,
            "width": width,
            "height": height,
            "issues": [f"image_decode:{type(exc).__name__}"],
        }

    issues: list[str] = []
    if not isinstance(width, int) or width <= 0:
        issues.append("image_width")
    if not isinstance(height, int) or height <= 0:
        issues.append("image_height")
    if not image_format:
        issues.append("image_format")
    return {
        "checked": True,
        "valid": not issues,
        "format": image_format,
        "width": width,
        "height": height,
        "issues": issues,
    }


def _strict_trace_file_validation(
    value: bytes,
    *,
    path: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Accept only strict UTF-8 JSONL trace records with the terminal schema."""

    issues: list[str] = []
    records: list[dict[str, Any]] = []
    if path.suffix.lower() != ".jsonl":
        issues.append("trace_extension_jsonl")
    try:
        raw = value.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        return (
            {
                "checked": True,
                "valid": False,
                "record_count": 0,
                "issues": [f"trace_read:{type(exc).__name__}"],
            },
            [],
        )
    for line_number, line in enumerate(raw.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            issues.append(f"trace_jsonl_line_{line_number}")
            continue
        if not isinstance(item, dict):
            issues.append(f"trace_object_line_{line_number}")
            continue
        records.append(item)
        if not isinstance(item.get("trace_id"), str) or not item["trace_id"].strip():
            issues.append(f"trace_id_line_{line_number}")
        if not isinstance(item.get("screenshot"), dict):
            issues.append(f"trace_screenshot_line_{line_number}")
        if not isinstance(item.get("frames"), list) or not item["frames"]:
            issues.append(f"trace_frames_line_{line_number}")
        if not isinstance(item.get("selected_action"), dict):
            issues.append(f"trace_selected_action_line_{line_number}")
        if not isinstance(item.get("execution"), dict):
            issues.append(f"trace_execution_line_{line_number}")
        verification = item.get("verification")
        if not isinstance(verification, dict) or not isinstance(
            verification.get("post_action_verifier"),
            dict,
        ):
            issues.append(f"trace_verification_line_{line_number}")
    if not records:
        issues.append("trace_records")
    return (
        {
            "checked": True,
            "valid": not issues,
            "record_count": len(records),
            "issues": sorted(set(issues)),
        },
        records,
    )


def _trace_dispatch_time_validation(
    record: dict[str, Any],
    execution: dict[str, Any],
) -> dict[str, Any]:
    summary = execution.get("summary") if isinstance(execution.get("summary"), dict) else {}
    raw = summary.get("dispatch_at")
    parsed = _parse_aware_datetime(raw)
    return {
        "valid": parsed is not None,
        "issues": [] if parsed is not None else ["dispatch_at_aware_iso8601"],
        "dispatch_at": parsed.isoformat() if parsed is not None else raw,
    }


def _trace_terminal_observation_validation(
    record: dict[str, Any],
    *,
    screenshot_path: str | None,
    screenshot_sha256: str | None,
    screenshot_size: tuple[Any, Any] | None,
    source_paths_match: Any,
) -> dict[str, Any]:
    issues: list[str] = []
    required_frame_size = _trace_frame_size(screenshot_size)
    if not _is_sha256(screenshot_sha256):
        issues.append("screenshot_sha256")
    if required_frame_size is None:
        issues.append("screenshot_frame_size")
    frames = record.get("frames")
    if not isinstance(frames, list):
        frames = []
        issues.append("frames")
    terminal_frames = [
        frame
        for frame in frames
        if isinstance(frame, dict)
        and frame.get("role") == "terminal_dispatch"
    ]
    if len(terminal_frames) != 1:
        issues.append("terminal_dispatch_frame")
        terminal_frame: dict[str, Any] = {}
    else:
        terminal_frame = terminal_frames[0]
        if not source_paths_match(
            str(terminal_frame.get("path")) if terminal_frame.get("path") else None,
            screenshot_path,
        ):
            issues.append("terminal_dispatch_frame_path")

    observation = (
        terminal_frame.get("observation")
        if isinstance(terminal_frame.get("observation"), dict)
        else {}
    )
    observation_fingerprint = _trace_observation_fingerprint(observation)
    if observation_fingerprint is None:
        issues.append("terminal_dispatch_observation")

    frame_sha256 = terminal_frame.get("sha256")
    if not _is_sha256(frame_sha256):
        issues.append("terminal_dispatch_frame_sha256")
    elif (
        observation_fingerprint is not None
        and frame_sha256 != observation_fingerprint["frame_sha256"]
    ):
        issues.append("terminal_dispatch_frame_sha256_binding")
    if _is_sha256(screenshot_sha256) and str(frame_sha256).lower() != str(
        screenshot_sha256
    ).lower():
        issues.append("terminal_dispatch_frame_screenshot_sha256_binding")
    if observation_fingerprint is not None:
        if (
            _is_sha256(screenshot_sha256)
            and observation_fingerprint["frame_sha256"]
            != str(screenshot_sha256).lower()
        ):
            issues.append("terminal_dispatch_observation_screenshot_sha256_binding")
        if (
            required_frame_size is not None
            and observation_fingerprint["frame_size"] != list(required_frame_size)
        ):
            issues.append("terminal_dispatch_observation_frame_size_binding")

    screenshot = record.get("screenshot") if isinstance(record.get("screenshot"), dict) else {}
    metadata = screenshot.get("metadata") if isinstance(screenshot.get("metadata"), dict) else {}
    primary_observation = metadata.get("observation")
    primary_fingerprint = _trace_observation_fingerprint(primary_observation)
    if primary_fingerprint is None:
        issues.append("screenshot_primary_observation")
    elif observation_fingerprint is not None and not _structured_equal(
        primary_observation,
        observation,
    ):
        issues.append("screenshot_primary_observation_binding")
    if primary_fingerprint is not None:
        if (
            _is_sha256(screenshot_sha256)
            and primary_fingerprint["frame_sha256"] != str(screenshot_sha256).lower()
        ):
            issues.append("screenshot_primary_observation_sha256_binding")
        if (
            required_frame_size is not None
            and primary_fingerprint["frame_size"] != list(required_frame_size)
        ):
            issues.append("screenshot_primary_observation_frame_size_binding")

    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "frame": terminal_frame if terminal_frame else None,
        "observation": observation if observation else None,
        "observation_fingerprint": observation_fingerprint,
        "required_screenshot_sha256": screenshot_sha256,
        "required_frame_size": (
            list(required_frame_size) if required_frame_size is not None else None
        ),
    }


def _trace_observation_fingerprint(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    observation_id = value.get("observation_id")
    frame_sha256 = value.get("frame_sha256")
    frame_size = _trace_frame_size(value.get("frame_size"))
    captured_at = _parse_aware_datetime(value.get("captured_at"))
    if (
        not isinstance(observation_id, str)
        or not observation_id.strip()
        or not _is_sha256(frame_sha256)
        or frame_size is None
        or captured_at is None
    ):
        return None
    return {
        "observation_id": observation_id,
        "frame_sha256": str(frame_sha256).lower(),
        "frame_size": list(frame_size),
        "captured_at": captured_at.isoformat(),
    }


def _trace_frame_size(value: Any) -> tuple[int, int] | None:
    if (
        not isinstance(value, (list, tuple))
        or len(value) != 2
        or any(
            isinstance(item, bool) or not isinstance(item, int) or item <= 0
            for item in value
        )
    ):
        return None
    return int(value[0]), int(value[1])


_SEMANTIC_FRAME_GUARD_FIELDS = {
    "schema_version",
    "algorithm",
    "semantic_target_key",
    "frame_size",
    "capture_geometry",
    "normalized_bbox",
    "roi_bbox",
    "click_point",
    "roi_sha256",
}
_SEMANTIC_ROI_ALGORITHM = "semantic-roi-rgb24-sha256-v1"


def _semantic_frame_guard_validation(
    value: Any,
    *,
    selected_action: dict[str, Any],
    action_type: str | None,
    expected_target_key: Any,
    screenshot_bytes: bytes | None,
    screenshot_size: tuple[Any, Any] | None,
    expected_capture_geometry: Any,
) -> dict[str, Any]:
    """Rebuild the runtime ROI guard from the bound screenshot and action bbox."""

    if not isinstance(value, dict):
        return {
            "valid": False,
            "issues": ["semantic_frame_guard_not_object"],
        }

    issues: list[str] = []
    if set(value) != _SEMANTIC_FRAME_GUARD_FIELDS:
        issues.append("semantic_frame_guard.fields")
    if value.get("schema_version") != 1:
        issues.append("semantic_frame_guard.schema_version")
    if value.get("algorithm") != _SEMANTIC_ROI_ALGORITHM:
        issues.append("semantic_frame_guard.algorithm")

    binding = _selected_action_semantic_binding(selected_action, action_type=action_type)
    if not binding["valid"]:
        issues.extend(binding["issues"])
    expected_key = binding.get("semantic_target_key")
    if not isinstance(expected_target_key, str) or expected_key != expected_target_key:
        issues.append("semantic_frame_guard.runtime_target_binding")
    if value.get("semantic_target_key") != expected_key:
        issues.append("semantic_frame_guard.semantic_target_key")

    decoded_size = _trace_frame_size(screenshot_size)
    guard_size = _trace_frame_size(value.get("frame_size"))
    if decoded_size is None:
        issues.append("semantic_frame_guard.screenshot_frame_size")
    if guard_size is None or guard_size != decoded_size:
        issues.append("semantic_frame_guard.frame_size")

    observation_capture_validation = _capture_geometry_validation(
        expected_capture_geometry,
        screenshot_size=decoded_size,
    )
    guard_capture_validation = _capture_geometry_validation(
        value.get("capture_geometry"),
        screenshot_size=decoded_size,
    )
    if not observation_capture_validation["valid"]:
        issues.extend(
            "semantic_frame_guard.observation_"
            + item.removeprefix("semantic_frame_guard.")
            for item in observation_capture_validation["issues"]
        )
    if not guard_capture_validation["valid"]:
        issues.extend(guard_capture_validation["issues"])
    if (
        observation_capture_validation["valid"]
        and guard_capture_validation["valid"]
        and not _structured_equal(
            guard_capture_validation["capture_geometry"],
            observation_capture_validation["capture_geometry"],
        )
    ):
        issues.append("semantic_frame_guard.capture_geometry_binding")

    guard_bbox = _normalized_semantic_bbox(value.get("normalized_bbox"))
    expected_bbox = binding.get("normalized_bbox")
    if guard_bbox is None:
        issues.append("semantic_frame_guard.normalized_bbox")
    elif not _structured_equal(guard_bbox, expected_bbox):
        issues.append("semantic_frame_guard.normalized_bbox_binding")

    expected_roi: dict[str, int] | None = None
    expected_click: dict[str, int] | None = None
    if decoded_size is not None and isinstance(expected_bbox, dict):
        expected_roi, expected_click = _semantic_target_geometry(
            decoded_size,
            expected_bbox,
        )
        if expected_roi is None or expected_click is None:
            issues.append("semantic_frame_guard.geometry")
    guard_roi = _strict_int_mapping(
        value.get("roi_bbox"),
        fields=("x", "y", "width", "height"),
        positive_fields={"width", "height"},
    )
    if guard_roi is None or not _structured_equal(guard_roi, expected_roi):
        issues.append("semantic_frame_guard.roi_bbox")
    guard_click = _strict_int_mapping(
        value.get("click_point"),
        fields=("x", "y"),
        positive_fields=set(),
    )
    if guard_click is None or not _structured_equal(guard_click, expected_click):
        issues.append("semantic_frame_guard.click_point")

    declared_roi_sha256 = value.get("roi_sha256")
    if (
        not isinstance(declared_roi_sha256, str)
        or declared_roi_sha256 != declared_roi_sha256.lower()
        or not _is_sha256(declared_roi_sha256)
    ):
        issues.append("semantic_frame_guard.roi_sha256")

    computed_roi_sha256: str | None = None
    if (
        isinstance(screenshot_bytes, bytes)
        and decoded_size is not None
        and expected_roi is not None
    ):
        try:
            from PIL import Image
        except ImportError:
            issues.append("semantic_frame_guard.screenshot_decode")
        else:
            try:
                with Image.open(BytesIO(screenshot_bytes)) as image:
                    rgb = image.convert("RGB")
                    rgb.load()
                if rgb.size != decoded_size:
                    issues.append("semantic_frame_guard.screenshot_frame_size")
                else:
                    crop = rgb.crop(
                        (
                            expected_roi["x"],
                            expected_roi["y"],
                            expected_roi["x"] + expected_roi["width"],
                            expected_roi["y"] + expected_roi["height"],
                        )
                    )
                    computed_roi_sha256 = _sha256_bytes(crop.tobytes())
            except (OSError, ValueError):
                issues.append("semantic_frame_guard.screenshot_decode")
    else:
        issues.append("semantic_frame_guard.screenshot_bytes")
    if computed_roi_sha256 != declared_roi_sha256:
        issues.append("semantic_frame_guard.roi_sha256_binding")

    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "selected_action_binding": binding,
        "expected_semantic_target_key": expected_key,
        "expected_frame_size": list(decoded_size) if decoded_size is not None else None,
        "expected_capture_geometry": observation_capture_validation.get(
            "capture_geometry"
        ),
        "capture_geometry_validation": guard_capture_validation,
        "expected_normalized_bbox": expected_bbox,
        "expected_roi_bbox": expected_roi,
        "expected_click_point": expected_click,
        "computed_roi_sha256": computed_roi_sha256,
    }


_CAPTURE_GEOMETRY_FIELDS = {
    "schema_version",
    "capture_backend",
    "outer_window",
    "capture_rect",
    "capture_origin",
    "frame_size",
}
_CAPTURE_RECT_FIELDS = {"left", "top", "right", "bottom", "width", "height"}
_CAPTURE_WINDOW_FIELDS = _CAPTURE_RECT_FIELDS | {"hwnd", "pid"}


def _capture_geometry_validation(
    value: Any,
    *,
    screenshot_size: tuple[int, int] | None,
) -> dict[str, Any]:
    issues: list[str] = []
    if not isinstance(value, dict):
        return {
            "valid": False,
            "issues": ["semantic_frame_guard.capture_geometry_not_object"],
            "capture_geometry": None,
        }
    if set(value) != _CAPTURE_GEOMETRY_FIELDS:
        issues.append("semantic_frame_guard.capture_geometry.fields")
    if value.get("schema_version") != 1:
        issues.append("semantic_frame_guard.capture_geometry.schema_version")
    backend = value.get("capture_backend")
    if backend not in {"wgc", "dxgi"}:
        issues.append("semantic_frame_guard.capture_geometry.capture_backend")

    outer = _strict_capture_rect(value.get("outer_window"), window_identity=True)
    rect = _strict_capture_rect(value.get("capture_rect"), window_identity=False)
    origin = _strict_capture_origin(value.get("capture_origin"))
    frame_size = _trace_frame_size(value.get("frame_size"))
    if outer is None:
        issues.append("semantic_frame_guard.capture_geometry.outer_window")
    if rect is None:
        issues.append("semantic_frame_guard.capture_geometry.capture_rect")
    if origin is None:
        issues.append("semantic_frame_guard.capture_geometry.capture_origin")
    if frame_size is None or frame_size != screenshot_size:
        issues.append("semantic_frame_guard.capture_geometry.frame_size")
    if rect is not None and frame_size is not None and (
        rect["width"], rect["height"]
    ) != frame_size:
        issues.append("semantic_frame_guard.capture_geometry.capture_rect_frame_size")
    if rect is not None and origin is not None and (
        origin["x"] != rect["left"] or origin["y"] != rect["top"]
    ):
        issues.append("semantic_frame_guard.capture_geometry.capture_origin_binding")
    if outer is not None and rect is not None and not (
        outer["left"] <= rect["left"] < rect["right"] <= outer["right"]
        and outer["top"] <= rect["top"] < rect["bottom"] <= outer["bottom"]
    ):
        issues.append("semantic_frame_guard.capture_geometry.outer_window_binding")

    canonical = None
    if outer is not None and rect is not None and origin is not None and frame_size is not None:
        canonical = {
            "schema_version": value.get("schema_version"),
            "capture_backend": backend,
            "outer_window": outer,
            "capture_rect": rect,
            "capture_origin": origin,
            "frame_size": list(frame_size),
        }
    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "capture_geometry": canonical,
    }


def _strict_capture_rect(value: Any, *, window_identity: bool) -> dict[str, int] | None:
    expected_fields = _CAPTURE_WINDOW_FIELDS if window_identity else _CAPTURE_RECT_FIELDS
    if not isinstance(value, dict) or set(value) != expected_fields:
        return None
    parsed: dict[str, int] = {}
    for field_name in expected_fields:
        item = value.get(field_name)
        if isinstance(item, bool) or not isinstance(item, int):
            return None
        if field_name in {"width", "height", "hwnd", "pid"} and item <= 0:
            return None
        parsed[field_name] = item
    if (
        parsed["right"] <= parsed["left"]
        or parsed["bottom"] <= parsed["top"]
        or parsed["right"] - parsed["left"] != parsed["width"]
        or parsed["bottom"] - parsed["top"] != parsed["height"]
    ):
        return None
    return parsed


def _strict_capture_origin(value: Any) -> dict[str, int] | None:
    if not isinstance(value, dict) or set(value) != {"x", "y"}:
        return None
    if any(
        isinstance(value.get(field), bool) or not isinstance(value.get(field), int)
        for field in ("x", "y")
    ):
        return None
    return {"x": value["x"], "y": value["y"]}


def _selected_action_semantic_binding(
    selected_action: Any,
    *,
    action_type: str | None,
) -> dict[str, Any]:
    issues: list[str] = []
    params = selected_action.get("params") if isinstance(selected_action, dict) else None
    if not isinstance(params, dict):
        return {
            "valid": False,
            "issues": ["semantic_frame_guard.selected_action_params"],
            "semantic_target_key": None,
            "normalized_bbox": None,
        }

    target_key: str | None = None
    button: Any = None
    if action_type == "claim_chapter_reward":
        target_key = "chapter_claim_button"
        button = params.get("claim_button")
    elif action_type == "recruit_soldiers":
        target_key = "recruit_button"
        button = params.get("recruit_button")
    elif action_type == "upgrade_building":
        target_key = "upgrade_confirm_button"
        dialog = params.get("upgrade_dialog")
        if not isinstance(dialog, dict) or dialog.get("visible") is not True:
            issues.append("semantic_frame_guard.upgrade_dialog")
        else:
            button = dialog.get("confirm_button")
    else:
        issues.append("semantic_frame_guard.action_type")

    if not isinstance(button, dict):
        issues.append("semantic_frame_guard.selected_action_button")
        bbox = None
    else:
        if button.get("visible") is not True:
            issues.append("semantic_frame_guard.button_visible")
        if button.get("enabled") is not True:
            issues.append("semantic_frame_guard.button_enabled")
        bbox = _normalized_semantic_bbox(button.get("bbox"))
        if bbox is None:
            issues.append("semantic_frame_guard.selected_action_bbox")
    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "semantic_target_key": target_key,
        "normalized_bbox": bbox,
    }


def _normalized_semantic_bbox(value: Any) -> dict[str, float] | None:
    fields = ("x_min", "y_min", "x_max", "y_max")
    if not isinstance(value, dict) or set(value) != set(fields):
        return None
    normalized: dict[str, float] = {}
    for field_name in fields:
        item = value.get(field_name)
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
            or not 0 <= float(item) <= 1000
        ):
            return None
        normalized[field_name] = float(item)
    if (
        normalized["x_max"] <= normalized["x_min"]
        or normalized["y_max"] <= normalized["y_min"]
    ):
        return None
    return normalized


def _semantic_target_geometry(
    frame_size: tuple[int, int],
    bbox: dict[str, float],
) -> tuple[dict[str, int] | None, dict[str, int] | None]:
    width, height = frame_size
    left = round(bbox["x_min"] / 1000 * width)
    top = round(bbox["y_min"] / 1000 * height)
    right = round(bbox["x_max"] / 1000 * width)
    bottom = round(bbox["y_max"] / 1000 * height)
    if right <= left or bottom <= top:
        return None, None
    roi = {
        "x": left,
        "y": top,
        "width": right - left,
        "height": bottom - top,
    }
    click = {
        "x": min(
            max(round((bbox["x_min"] + bbox["x_max"]) / 2000 * width), left),
            right - 1,
        ),
        "y": min(
            max(round((bbox["y_min"] + bbox["y_max"]) / 2000 * height), top),
            bottom - 1,
        ),
    }
    return roi, click


def _strict_int_mapping(
    value: Any,
    *,
    fields: tuple[str, ...],
    positive_fields: set[str],
) -> dict[str, int] | None:
    if not isinstance(value, dict) or set(value) != set(fields):
        return None
    parsed: dict[str, int] = {}
    for field_name in fields:
        item = value.get(field_name)
        if isinstance(item, bool) or not isinstance(item, int):
            return None
        if item < 0 or (field_name in positive_fields and item <= 0):
            return None
        parsed[field_name] = item
    return parsed


def _trace_operator_confirmation(record: dict[str, Any]) -> dict[str, Any] | None:
    execution = _trace_execution(record)
    summary = execution.get("summary") if isinstance(execution.get("summary"), dict) else {}
    value = summary.get("operator_confirmation")
    return dict(value) if isinstance(value, dict) else None


_OPERATOR_CONFIRMATION_FIELDS = (
    "confirmed",
    "requires_operator_confirmation",
    "scope",
    "confirmation_id",
    "request_id",
    "action_id",
    "action_type",
    "target_key",
    "target_identity",
    "observation_id",
    "frame_sha256",
    "semantic_frame_guard",
    "observation_captured_at",
    "confirmed_at",
    "expires_at",
    "consumed_at",
    "dispatch_at",
    "runtime_dispatch",
)

_OPERATOR_CONFIRMATION_TIMESTAMP_FIELDS = (
    "observation_captured_at",
    "confirmed_at",
    "expires_at",
    "consumed_at",
    "dispatch_at",
)


def _trace_operator_confirmation_validation(
    value: Any,
    *,
    selected_action: dict[str, Any],
    execution: dict[str, Any],
    action_type: str | None,
    required_runtime_dispatch: dict[str, Any],
    target_identity: Any,
    dispatch_time_validation: dict[str, Any],
    terminal_observation_validation: dict[str, Any],
    screenshot_bytes: bytes | None,
    screenshot_size: tuple[Any, Any] | None,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "valid": False,
            "issues": ["trace_operator_confirmation_not_object"],
            "confirmation": None,
        }

    issues: list[str] = []
    for field_name in _OPERATOR_CONFIRMATION_FIELDS:
        if field_name not in value:
            issues.append(f"operator_confirmation.{field_name}")
    if value.get("confirmed") is not True:
        issues.append("operator_confirmation.confirmed")
    if value.get("requires_operator_confirmation") is not True:
        issues.append("operator_confirmation.requires_operator_confirmation")
    if value.get("scope") != "final_mutating_click":
        issues.append("operator_confirmation.scope")

    for field_name in ("confirmation_id", "request_id"):
        field_value = value.get(field_name)
        if not isinstance(field_value, str) or not field_value.strip():
            issues.append(f"operator_confirmation.{field_name}")

    selected_action_id = selected_action.get("action_id")
    if not isinstance(selected_action_id, str) or not selected_action_id.strip():
        issues.append("selected_action.action_id")
    if value.get("action_id") != selected_action_id:
        issues.append("operator_confirmation.action_id")
    if execution.get("action_id") != selected_action_id:
        issues.append("execution.action_id")
    if value.get("action_type") != action_type:
        issues.append("operator_confirmation.action_type")

    dispatch_projection = _runtime_dispatch_projection(execution)
    expected_target_key = dispatch_projection.get("target_key")
    if value.get("target_key") != expected_target_key:
        issues.append("operator_confirmation.target_key")
    if not _structured_equal(value.get("target_identity"), target_identity):
        issues.append("operator_confirmation.target_identity")
    if not _runtime_dispatch_matches(value.get("runtime_dispatch"), required_runtime_dispatch):
        issues.append("operator_confirmation.runtime_dispatch")
    elif not _structured_equal(value.get("runtime_dispatch"), dispatch_projection):
        issues.append("operator_confirmation.runtime_dispatch_binding")

    semantic_guard_validation: dict[str, Any] = {
        "valid": False,
        "issues": ["terminal_dispatch_observation"],
    }
    terminal_observation = terminal_observation_validation.get("observation_fingerprint")
    if not terminal_observation_validation.get("valid") or not isinstance(
        terminal_observation,
        dict,
    ):
        issues.append("terminal_dispatch_observation")
    else:
        if value.get("observation_id") != terminal_observation.get("observation_id"):
            issues.append("operator_confirmation.observation_id")
        if str(value.get("frame_sha256") or "").lower() != terminal_observation.get(
            "frame_sha256"
        ):
            issues.append("operator_confirmation.frame_sha256")
        semantic_guard_validation = _semantic_frame_guard_validation(
            value.get("semantic_frame_guard"),
            selected_action=selected_action,
            action_type=action_type,
            expected_target_key=expected_target_key,
            screenshot_bytes=screenshot_bytes,
            screenshot_size=screenshot_size,
            expected_capture_geometry=(
                terminal_observation_validation.get("observation") or {}
            ).get("capture_geometry"),
        )
        if not semantic_guard_validation["valid"]:
            issues.extend(
                f"operator_confirmation.{item}"
                for item in semantic_guard_validation["issues"]
            )
        confirmation_observed_at = _parse_aware_datetime(
            value.get("observation_captured_at")
        )
        terminal_observed_at = _parse_aware_datetime(terminal_observation.get("captured_at"))
        if (
            confirmation_observed_at is None
            or terminal_observed_at is None
            or confirmation_observed_at != terminal_observed_at
        ):
            issues.append("operator_confirmation.observation_captured_at")

    parsed_times: dict[str, datetime | None] = {
        field_name: _parse_aware_datetime(value.get(field_name))
        for field_name in _OPERATOR_CONFIRMATION_TIMESTAMP_FIELDS
    }
    for field_name, parsed in parsed_times.items():
        if parsed is None:
            issues.append(f"operator_confirmation.{field_name}_aware_iso8601")
    trace_dispatch_at = _parse_aware_datetime(dispatch_time_validation.get("dispatch_at"))
    if not dispatch_time_validation.get("valid") or trace_dispatch_at is None:
        issues.append("execution.dispatch_at_aware_iso8601")
    elif parsed_times["dispatch_at"] != trace_dispatch_at:
        issues.append("operator_confirmation.dispatch_at_binding")

    observed_at = parsed_times["observation_captured_at"]
    confirmed_at = parsed_times["confirmed_at"]
    consumed_at = parsed_times["consumed_at"]
    dispatch_at = parsed_times["dispatch_at"]
    expires_at = parsed_times["expires_at"]
    if (
        observed_at is not None
        and confirmed_at is not None
        and observed_at > confirmed_at
    ):
        issues.append("operator_confirmation.confirmation_before_observation")
    if confirmed_at is not None and consumed_at is not None and confirmed_at >= consumed_at:
        issues.append("operator_confirmation.confirmation_not_before_consumption")
    if consumed_at is not None and dispatch_at is not None and consumed_at > dispatch_at:
        issues.append("operator_confirmation.consumption_after_dispatch")
    if dispatch_at is not None and expires_at is not None and dispatch_at >= expires_at:
        issues.append("operator_confirmation.dispatch_not_before_expiry")

    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "confirmation": dict(value),
        "fingerprint": _operator_confirmation_fingerprint(value),
        "semantic_frame_guard_validation": semantic_guard_validation,
    }


def _operator_confirmation_validation(
    value: Any,
    *,
    action_type: str | None,
    required_runtime_dispatch: dict[str, Any],
    trace_validation: dict[str, Any] | None,
    target_identity: Any,
) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "checked": True,
            "valid": False,
            "issues": ["operator_confirmation_not_object"],
        }
    issues: list[str] = []
    confirmed = value.get("confirmed") is True
    if not confirmed:
        issues.append("confirmed")
    if value.get("requires_operator_confirmation") is not True:
        issues.append("requires_operator_confirmation")
    if value.get("action_type") != action_type:
        issues.append("action_type")
    if value.get("scope") != "final_mutating_click":
        issues.append("scope")
    parsed_times = {
        field_name: _parse_aware_datetime(value.get(field_name))
        for field_name in _OPERATOR_CONFIRMATION_TIMESTAMP_FIELDS
    }
    for field_name, parsed in parsed_times.items():
        if parsed is None:
            issues.append(f"{field_name}_aware_iso8601")
    confirmed_at = parsed_times["confirmed_at"]
    dispatch_at = parsed_times["dispatch_at"]
    if not _structured_equal(value.get("target_identity"), target_identity):
        issues.append("target_identity")
    if not _runtime_dispatch_matches(value.get("runtime_dispatch"), required_runtime_dispatch):
        issues.append("runtime_dispatch")
    trace_binding = _operator_trace_binding_validation(value, trace_validation)
    if not trace_binding["valid"]:
        issues.append("trace_binding")
    trace_confirmation = trace_binding.get("operator_confirmation")
    if trace_binding.get("matched") and isinstance(trace_confirmation, dict):
        manifest_fingerprint = _operator_confirmation_fingerprint(value)
        trace_fingerprint = _operator_confirmation_fingerprint(trace_confirmation)
        for field_name in _OPERATOR_CONFIRMATION_FIELDS:
            if not _structured_equal(
                manifest_fingerprint.get(field_name),
                trace_fingerprint.get(field_name),
            ):
                issues.append(f"trace_confirmation_mismatch.{field_name}")
    elif trace_binding.get("matched"):
        issues.append("trace_operator_confirmation")
    if (
        confirmed_at is not None
        and dispatch_at is not None
        and confirmed_at >= dispatch_at
    ):
        issues.append("confirmation_not_before_dispatch")
    return {
        "checked": True,
        "valid": not issues,
        "issues": sorted(set(issues)),
        "confirmed": confirmed,
        "action_type": value.get("action_type"),
        "scope": value.get("scope"),
        "confirmed_at": confirmed_at.isoformat() if confirmed_at is not None else value.get("confirmed_at"),
        "dispatch_at": dispatch_at.isoformat() if dispatch_at is not None else value.get("dispatch_at"),
        "trace_binding": trace_binding,
    }


def _operator_confirmation_fingerprint(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    fingerprint: dict[str, Any] = {}
    for field_name in _OPERATOR_CONFIRMATION_FIELDS:
        field_value = value.get(field_name)
        if field_name in _OPERATOR_CONFIRMATION_TIMESTAMP_FIELDS:
            parsed = _parse_aware_datetime(field_value)
            fingerprint[field_name] = parsed.isoformat() if parsed is not None else field_value
        else:
            fingerprint[field_name] = field_value
    return fingerprint


def _operator_trace_binding_validation(
    value: dict[str, Any],
    trace_validation: dict[str, Any] | None,
) -> dict[str, Any]:
    trace_id = value.get("trace_id")
    trace_record_index = value.get("trace_record_index")
    issues: list[str] = []
    if not isinstance(trace_id, str) or not trace_id.strip():
        issues.append("trace_id")
    if (
        not isinstance(trace_record_index, int)
        or isinstance(trace_record_index, bool)
        or trace_record_index < 0
    ):
        issues.append("trace_record_index")

    matching_records = (
        trace_validation.get("matching_records")
        if isinstance(trace_validation, dict)
        else None
    )
    if not isinstance(matching_records, list) or not matching_records:
        issues.append("matching_trace_record")
        matching_records = []

    matched = False
    dispatch_at: Any = None
    operator_confirmation: Any = None
    for record in matching_records:
        if not isinstance(record, dict):
            continue
        if record.get("trace_id") == trace_id and record.get("index") == trace_record_index:
            matched = True
            dispatch_at = record.get("dispatch_at")
            operator_confirmation = record.get("operator_confirmation")
            break
    if (
        isinstance(trace_id, str)
        and trace_id.strip()
        and isinstance(trace_record_index, int)
        and not isinstance(trace_record_index, bool)
        and trace_record_index >= 0
        and not matched
    ):
        issues.append("trace_record_match")

    return {
        "valid": not issues,
        "issues": sorted(set(issues)),
        "trace_id": trace_id,
        "trace_record_index": trace_record_index,
        "matched": matched,
        "dispatch_at": dispatch_at,
        "operator_confirmation": operator_confirmation,
    }


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


def _trace_record_id(record: dict[str, Any]) -> str | None:
    value = record.get("trace_id")
    if value:
        return str(value)
    trace_step = record.get("trace")
    if isinstance(trace_step, dict):
        trace_value = trace_step.get("trace_id")
        if trace_value:
            return str(trace_value)
    return None


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


def _trace_screenshot_path(record: dict[str, Any]) -> str | None:
    screenshot = record.get("screenshot")
    if isinstance(screenshot, dict) and screenshot.get("path"):
        return str(screenshot["path"])
    observe = record.get("observe")
    if isinstance(observe, dict):
        outputs = observe.get("outputs")
        if isinstance(outputs, dict) and outputs.get("screenshot"):
            return str(outputs["screenshot"])
    return None


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
        "accepted_source_kinds": ["live_trace_fixture"],
        "required_page": "chapter",
        "required_semantic_target": "progress.chapter_claim_button",
        "required_runtime_dispatch": {
            "status": "ok",
            "target_key": "chapter_claim_button",
            "terminal_for_verifier": True,
        },
        "required_source_evidence": [
            "live trace with terminal screenshot metadata, action-bound dispatch timestamp, operator confirmation, and verification record",
        ],
        "required_target_identity": {
            "chapter_id": {"type": "positive_integer"},
        },
        "required_post_action_delta": ["progress.chapter_claimable true->false"],
        "required_post_action_delta_contract": [
            {
                "path": "progress.chapter_claimable",
                "operator": "changes_to",
                "before": True,
                "after": False,
            },
        ],
    },
    "recruit_soldiers": {
        "code": "recruit_terminal_real_source",
        "accepted_source_kinds": ["live_trace_fixture"],
        "required_page": "recruit",
        "required_semantic_target": "teams[*].recruit_button",
        "required_runtime_dispatch": {
            "status": "ok",
            "target_key": "recruit_button",
            "terminal_for_verifier": True,
        },
        "required_source_evidence": [
            "live trace with terminal screenshot metadata, team-bound dispatch timestamp, operator confirmation, and verification record",
        ],
        "required_target_identity": {
            "team_id": {"type": "nonempty_string"},
        },
        "required_post_action_delta": [
            "teams[team_id=<team_id>].soldiers increases",
            "or teams[team_id=<team_id>].recruit_finish_time becomes present",
        ],
        "required_post_action_delta_contract": [
            {
                "selector": {
                    "collection_path": "teams",
                    "identity_field": "team_id",
                    "identity_param": "team_id",
                },
                "path": "soldiers",
                "operator": "greater_than_before",
            },
            {
                "selector": {
                    "collection_path": "teams",
                    "identity_field": "team_id",
                    "identity_param": "team_id",
                },
                "path": "recruit_finish_time",
                "operator": "becomes_present",
                "value_type": "aware_datetime_or_nonempty_string",
            },
        ],
    },
    "upgrade_building": {
        "code": "upgrade_confirm_terminal_real_source",
        "accepted_source_kinds": ["live_trace_fixture"],
        "required_page": "building_upgrade",
        "required_semantic_target": "city.upgrade_dialog.confirm_button",
        "required_runtime_dispatch": {
            "status": "ok",
            "target_key": "upgrade_confirm_button",
            "terminal_for_verifier": True,
        },
        "required_source_evidence": [
            "live trace with terminal screenshot metadata, building-bound dispatch timestamp, operator confirmation, and verification record",
        ],
        "required_target_identity": {
            "building_name": {"type": "nonempty_string"},
            "current_level": {"type": "nonnegative_integer"},
            "target_level": {"type": "positive_integer"},
        },
        "required_post_action_delta": [
            "city.buildings[name=<building_name>].level current_level->target_level",
        ],
        "required_post_action_delta_contract": [
            {
                "selector": {
                    "collection_path": "city.buildings",
                    "identity_field": "name",
                    "identity_param": "building_name",
                },
                "path": "level",
                "operator": "increases_to",
                "before_param": "current_level",
                "after_param": "target_level",
            },
        ],
    },
}
