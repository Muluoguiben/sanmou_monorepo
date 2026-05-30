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
            },
            "missing_expectations": [
                path.name for path in fixtures if path.name not in expectations
            ],
            "extra_expectations": sorted(
                name for name in expectations if not (self.fixture_dir / name).exists()
            ),
            "results": [],
            "failures": [],
        }
        if include_fixture_results:
            replay_results = self._run_replay(fixtures)
            comparisons = [self._compare_result(item, expectations) for item in replay_results]
            payload["results"] = comparisons
            payload["failures"] = [item for item in comparisons if not item["matched"]]
            payload["pr6_verifier_coverage"] = self._pr6_verifier_coverage(comparisons)
            payload["pr5_dispatch_gate_coverage"] = self._pr5_dispatch_gate_coverage(comparisons)
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
        payload["status"] = (
            "ok"
            if not payload["missing_expectations"]
            and not payload["extra_expectations"]
            and not payload["failures"]
            and not payload["pr5_page_coverage"]["missing"]
            and not payload["pr6_verifier_coverage"]["missing"]
            and not payload["pr5_dispatch_gate_coverage"]["failures"]
            else "attention"
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
            "semantic_target_gate": replay_result.get("semantic_target_gate"),
            "verifier_gate": replay_result.get("verifier_gate"),
            "verifier_spec": replay_result.get("verifier_spec"),
            "selected_action": replay_result.get("selected_action"),
            "selection_reason": replay_result.get("selection_reason"),
            "derived_state": replay_result.get("derived_state"),
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
        return {
            "fixture": fixture_name,
            "matched": expected == actual,
            "expected_action_type": expected,
            "actual_action_type": actual,
            "selection_mode": selection_reason.get("selection_mode"),
            "top_score_gap": selection_reason.get("top_score_gap"),
            "ranked_action_count": len(result.get("ranked_actions") or []),
            "dispatch_gate": dispatch_gate,
            "semantic_target_gate": result.get("semantic_target_gate"),
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
