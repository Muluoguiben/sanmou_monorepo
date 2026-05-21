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
        expectations = self._load_expectations()
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
            "expectations_path": str(self.expectations_path),
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
        payload["status"] = "ok" if not payload["missing_expectations"] and not payload["extra_expectations"] and not payload["failures"] else "attention"
        return payload

    def fixture_eval(self, *, fixture: str, expected_action_type: str | None = None) -> dict[str, Any]:
        fixture_path = self._resolve_fixture_path(fixture)
        expectations = self._load_expectations()
        replay_result = self._run_replay([fixture_path])[0]
        if expected_action_type is None and fixture_path.name in expectations:
            expected_action_type = expectations[fixture_path.name].get("expected_action_type")
        comparison = self._compare_result(replay_result, {fixture_path.name: {"expected_action_type": expected_action_type}})
        return {
            "fixture": comparison["fixture"],
            "matched": comparison["matched"],
            "expected_action_type": comparison["expected_action_type"],
            "actual_action_type": comparison["actual_action_type"],
            "selection_mode": comparison["selection_mode"],
            "top_score_gap": comparison["top_score_gap"],
            "ranked_action_count": comparison["ranked_action_count"],
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

    def _load_expectations(self) -> dict[str, dict[str, Any]]:
        if not self.expectations_path.exists():
            return {}
        payload = json.loads(self.expectations_path.read_text(encoding="utf-8"))
        fixtures = payload.get("fixtures", {})
        if not isinstance(fixtures, dict):
            raise ValueError(f"invalid expectations file: {self.expectations_path}")
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
        return {
            "fixture": fixture_name,
            "matched": expected == actual,
            "expected_action_type": expected,
            "actual_action_type": actual,
            "selection_mode": selection_reason.get("selection_mode"),
            "top_score_gap": selection_reason.get("top_score_gap"),
            "ranked_action_count": len(result.get("ranked_actions") or []),
        }


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent.resolve())
    except ValueError:
        return False
    return True
