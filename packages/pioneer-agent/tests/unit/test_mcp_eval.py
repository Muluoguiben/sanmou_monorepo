from __future__ import annotations

import ast
from contextlib import redirect_stdout
from copy import deepcopy
from datetime import datetime
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from pioneer_agent.app import mcp_eval as mcp_eval_app
from pioneer_agent.mcp_eval import models as models_module
from pioneer_agent.mcp_eval import runner as runner_module
from pioneer_agent.mcp_eval import scoring as scoring_module
from pioneer_agent.mcp_eval.models import (
    BatteryManifest,
    ScenarioManifest,
    ToolCallRecord,
)
from pioneer_agent.mcp_eval.runner import load_battery, run_battery, write_run_artifacts
from pioneer_agent.mcp_eval.scoring import score_scenario
from pioneer_agent.mcp_server import (
    CONTRACT_VERSION,
    GAME_TOOL_ALLOWLIST,
    GAME_TOOL_ARGUMENTS,
)


REPO_SHA = "94bbe7d887bb7bb0425ef773efdc68d41043286f"
EXPECTED_GENERATION_SCENARIOS = {
    "home-observation",
    "chapter-claimable",
    "chapter-not-claimable",
    "recruit-available",
    "recruit-unavailable",
    "building-upgrade-entry",
    "building-upgrade-confirm",
    "map-filter-positive",
    "map-filter-no-change",
    "map-filter-interrupted",
    "map-filter-ambiguous",
    "battle-report-partial",
    "battle-report-conflict",
}


class McpEvalTests(unittest.TestCase):
    def test_checked_in_battery_covers_session_c_scenarios(self) -> None:
        loaded = load_battery(_battery_path())
        generation = {
            scenario.scenario_id
            for scenario in loaded.manifest.scenarios
            if scenario.split == "generation"
        }
        holdout = {
            scenario.scenario_id
            for scenario in loaded.manifest.scenarios
            if scenario.split == "holdout"
        }

        self.assertEqual(generation, EXPECTED_GENERATION_SCENARIOS)
        self.assertEqual(holdout, {"holdout-map-filter"})
        self.assertEqual(len(loaded.transcripts), 14)
        self.assertEqual(loaded.manifest.contract_version, CONTRACT_VERSION)
        self.assertEqual(
            {scenario.contract_version for scenario in loaded.manifest.scenarios},
            {CONTRACT_VERSION},
        )
        for transcript in loaded.transcripts.values():
            for call in transcript.calls:
                with self.subTest(scenario=transcript.scenario_id, call=call.call_id):
                    self.assertIn(call.tool_name, GAME_TOOL_ALLOWLIST)
                    self.assertEqual(
                        frozenset(call.arguments_summary),
                        GAME_TOOL_ARGUMENTS[call.tool_name],
                    )
        self.assertTrue(
            all(
                scenario.execution_authority == "none"
                and scenario.live_control_allowed is False
                and scenario.oracle_access_allowed is False
                for scenario in loaded.manifest.scenarios
            )
        )

    def test_static_runner_scores_generation_and_never_scores_holdout(self) -> None:
        result = run_battery(
            _battery_path(),
            repo_sha=REPO_SHA,
            now=datetime.fromisoformat("2026-08-26T12:00:00+08:00"),
        )

        self.assertEqual(result.aggregate.scenario_count, 14)
        self.assertEqual(result.aggregate.scored_generation_count, 13)
        self.assertEqual(result.aggregate.unscored_holdout_count, 1)
        self.assertEqual(set(result.aggregate.mean_scores.values()), {1.0})
        self.assertEqual(result.aggregate.total_tool_calls, 42)
        self.assertEqual(result.aggregate.mean_critical_domain_query_coverage, 1.0)
        self.assertEqual(result.aggregate.scenarios_with_missed_risk_domains, 0)
        self.assertFalse(result.aggregate.live_control_used)
        self.assertFalse(result.aggregate.holdout_oracle_accessed)

        holdout = next(report for report in result.scenario_reports if report.split == "holdout")
        self.assertFalse(holdout.scored)
        self.assertTrue(
            all(value is None for value in holdout.scores.model_dump().values())
        )
        self.assertFalse(holdout.oracle_accessed)

    def test_run_manifest_is_versioned_and_binds_inputs_and_tool_log(self) -> None:
        result = run_battery(_battery_path(), repo_sha=REPO_SHA, random_seed=19)
        manifest = result.run_manifest

        self.assertEqual(manifest.schema_version, 1)
        self.assertEqual(manifest.repo_sha, REPO_SHA)
        self.assertEqual(manifest.contract_version, CONTRACT_VERSION)
        self.assertEqual(manifest.prompt_version, "recommendation-only-v1")
        self.assertEqual(manifest.playbook_version, "decision-window-v1")
        self.assertEqual(manifest.random_seed, 19)
        self.assertRegex(manifest.fixture_catalog_digest, r"^[0-9a-f]{64}$")
        self.assertRegex(manifest.tool_log_digest, r"^[0-9a-f]{64}$")
        self.assertEqual(manifest.start_state["scenario_count"], 14)
        self.assertEqual(manifest.end_state["completed_scenarios"], 14)
        self.assertEqual(manifest.execution_authority, "none")
        self.assertFalse(manifest.live_control_used)

    def test_artifacts_are_write_once_and_holdout_report_has_no_labels(self) -> None:
        result = run_battery(_battery_path(), repo_sha=REPO_SHA)
        with TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "run"
            manifest_path, report_path = write_run_artifacts(output_dir, result)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            report = json.loads(report_path.read_text(encoding="utf-8"))

            self.assertEqual(manifest["repo_sha"], REPO_SHA)
            self.assertEqual(report["aggregate"]["scenario_count"], 14)
            holdout = next(
                item for item in report["scenario_reports"] if item["split"] == "holdout"
            )
            self.assertFalse(holdout["scored"])
            self.assertFalse(holdout["oracle_accessed"])
            serialized_holdout = json.dumps(holdout, sort_keys=True)
            self.assertNotIn("expectations", serialized_holdout)
            self.assertNotIn("expected_state", serialized_holdout)
            with self.assertRaises(FileExistsError):
                write_run_artifacts(output_dir, result)

    def test_cli_emits_paths_and_safety_boundary(self) -> None:
        with TemporaryDirectory() as tmp:
            stdout = StringIO()
            with redirect_stdout(stdout):
                status = mcp_eval_app.main(
                    [
                        "--battery",
                        str(_battery_path()),
                        "--output-dir",
                        str(Path(tmp) / "run"),
                        "--repo-sha",
                        REPO_SHA,
                    ]
                )
            output = json.loads(stdout.getvalue())

            self.assertEqual(status, 0)
            self.assertEqual(output["status"], "completed")
            self.assertEqual(output["execution_authority"], "none")
            self.assertFalse(output["live_control_used"])
            self.assertFalse(output["holdout_oracle_accessed"])
            self.assertTrue(Path(output["run_manifest"]).is_file())
            self.assertTrue(Path(output["metrics_report"]).is_file())

    def test_sensorium_reports_stale_and_missed_risk_domains(self) -> None:
        loaded = load_battery(_battery_path())
        base = next(
            item
            for item in loaded.manifest.scenarios
            if item.scenario_id == "map-filter-interrupted"
        )
        data = base.model_dump(mode="json")
        data["sensorium"]["stale_after_seconds"] = {
            "map_land": 0.001,
            "popup": 0.001,
        }
        manifest = ScenarioManifest.model_validate(data)

        report = score_scenario(manifest, loaded.transcripts[manifest.scenario_id])

        self.assertEqual(
            set(report.sensorium.stale_critical_domains_at_end),
            {"map_land", "popup"},
        )
        self.assertEqual(
            set(report.sensorium.missed_risk_domains_before_failure),
            {"map_land", "popup"},
        )
        self.assertEqual(report.sensorium.critical_domain_query_coverage, 1.0)

    def test_mutating_or_unknown_tool_is_rejected(self) -> None:
        data = _minimal_tool_call()
        for tool_name in ("click", "execute_prepared_action", "press_key"):
            with self.subTest(tool_name=tool_name), self.assertRaises(ValidationError):
                ToolCallRecord.model_validate({**data, "tool_name": tool_name})

    def test_tool_arguments_must_match_server_contract(self) -> None:
        cases = (
            ("session_status", {"refresh": True}),
            ("observe_game", {"source": "static_fixture"}),
            ("get_last_trace", {"limit": 1}),
            ("evaluate_fixture", {"fixture_id": "sample"}),
            ("evaluate_fixture", {}),
            ("evaluate_fixture", {"fixture": ".json"}),
            ("evaluate_fixture", {"fixture": "../private.json"}),
            ("evaluate_fixture", {"fixture": 1}),
        )
        for tool_name, arguments in cases:
            with self.subTest(tool_name=tool_name), self.assertRaises(ValidationError):
                ToolCallRecord.model_validate(
                    {
                        **_minimal_tool_call(),
                        "tool_name": tool_name,
                        "arguments_summary": arguments,
                    }
                )

    def test_battery_and_scenarios_reject_contract_version_drift(self) -> None:
        raw = _battery_json()
        raw["contract_version"] = "sanmou-game/v2"
        with self.assertRaises(ValidationError):
            BatteryManifest.model_validate(raw)

        raw = _battery_json()
        raw["scenarios"][0]["contract_version"] = "sanmou-game/v2"
        with self.assertRaises(ValidationError):
            BatteryManifest.model_validate(raw)

    def test_sensitive_or_raw_payload_is_rejected_from_tool_log(self) -> None:
        for arguments in (
            {"password": "value"},
            {"access_token": "value"},
            {"raw_image": "bytes"},
            {"preview": "data:image/png;base64,AAAA"},
        ):
            with self.subTest(arguments=arguments), self.assertRaises(ValidationError):
                ToolCallRecord.model_validate(
                    {**_minimal_tool_call(), "arguments_summary": arguments}
                )

    def test_holdout_manifest_cannot_contain_expectations(self) -> None:
        raw = _battery_json()
        holdout = next(item for item in raw["scenarios"] if item["split"] == "holdout")
        self.assertNotIn("expectations", holdout)
        holdout["expectations"] = deepcopy(raw["scenarios"][0]["expectations"])

        with self.assertRaises(ValidationError):
            BatteryManifest.model_validate(raw)

    def test_generation_holdout_session_capture_and_digest_cannot_overlap(self) -> None:
        for field in ("session_id", "capture_group_id", "fixture_sha256"):
            raw = _battery_json()
            generation = next(item for item in raw["scenarios"] if item["split"] == "generation")
            holdout = next(item for item in raw["scenarios"] if item["split"] == "holdout")
            holdout[field] = generation[field]
            with self.subTest(field=field), self.assertRaises(ValidationError):
                BatteryManifest.model_validate(raw)

    def test_fixture_digest_mismatch_fails_closed(self) -> None:
        raw = _battery_json()
        raw["scenarios"][0]["fixture_sha256"] = "0" * 64
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "battery.json").write_text(
                json.dumps(raw, ensure_ascii=False), encoding="utf-8"
            )
            for name in ("static-tool-calls.generation.json", "static-tool-calls.holdout.json"):
                (root / name).write_bytes((_battery_path().parent / name).read_bytes())

            with self.assertRaisesRegex(ValueError, "multiple digests|digest mismatch"):
                load_battery(root / "battery.json")

    def test_eval_modules_have_no_live_control_network_or_mcp_client_surface(self) -> None:
        forbidden_imports = {
            "socket",
            "subprocess",
            "requests",
            "mcp",
            "pioneer_agent.adapters",
            "pioneer_agent.executor",
            "pioneer_agent.safety",
        }
        forbidden_calls = {
            "SendInput",
            "click",
            "drag",
            "key_press",
            "mouse_event",
            "send",
            "sendall",
        }
        for module in (models_module, runner_module, scoring_module, mcp_eval_app):
            source = Path(module.__file__).read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            imports.update(
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            )
            self.assertFalse(
                any(
                    imported == forbidden or imported.startswith(f"{forbidden}.")
                    for imported in imports
                    for forbidden in forbidden_imports
                ),
                module.__name__,
            )
            calls = {
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            }
            self.assertTrue(calls.isdisjoint(forbidden_calls), module.__name__)


def _battery_path() -> Path:
    return Path(__file__).resolve().parents[2] / "evaluation" / "scenarios" / "v1" / "battery.json"


def _battery_json() -> dict:
    return json.loads(_battery_path().read_text(encoding="utf-8"))


def _minimal_tool_call() -> dict:
    return {
        "call_id": "call-1",
        "ordinal": 0,
        "tool_name": "session_status",
        "arguments_summary": {},
        "result_summary": {},
        "started_at": "2026-08-26T10:00:00+08:00",
        "duration_ms": 1.0,
        "success": True,
        "domains_queried": [],
        "domain_observed_at": {},
        "observation_refs": [],
        "trace_refs": [],
        "model_id": None,
        "session_id": "session-1",
        "tool_cost_units": 0.0,
        "vision_cost_units": 0.0,
    }


if __name__ == "__main__":
    unittest.main()
