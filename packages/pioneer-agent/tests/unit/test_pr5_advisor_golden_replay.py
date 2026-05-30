from __future__ import annotations

import json
import unittest
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from pioneer_agent.adapters.capture import CaptureFrame
from pioneer_agent.core.device import (
    CapabilityFlags,
    DevicePlatform,
    DeviceProfile,
    DeviceSession,
    ObservationSource,
    ObservationSourceType,
)
from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.perception.vision_sync import VisionSyncSummary
from pioneer_agent.runtime.advisor_loop import build_advisor_report
from pioneer_agent.selector.action_selector import ActionSelector
from pioneer_agent.core.enums import ActionType
from pioneer_agent.verifier import VerifierGateDecision, VerifierRegistry


REQUIRED_PR5_PAGES = {"home", "city", "chapter", "recruit", "building_upgrade", "team"}
PR6_VERIFIER_EXPECTATIONS = {
    "claim_chapter_reward": {
        "timeout_seconds": 10.0,
        "match_policy": "all",
        "delta_paths": ["progress.chapter_claimable"],
    },
    "recruit_soldiers": {
        "timeout_seconds": 30.0,
        "match_policy": "any",
        "delta_paths": [
            "teams.0.soldiers",
            "teams.0.recruit_finish_time",
            "economy.reserve_troops",
        ],
    },
    "upgrade_building": {
        "timeout_seconds": 20.0,
        "match_policy": "any",
        "delta_paths": [
            "city.buildings.0.level",
            "economy.resources.wood",
        ],
    },
}


class Pr5AdvisorGoldenReplayTests(unittest.TestCase):
    def test_pr5_real_screenshot_manifest_covers_required_pages(self) -> None:
        project_root = _project_root()
        payload = _load_expectation_payload()
        expectations = _pr5_expectations(payload)
        manifest = _load_manifest()

        self.assertEqual(set(payload["required_pr5_pages"]), REQUIRED_PR5_PAGES)
        self.assertEqual({item["page"] for item in expectations.values()}, REQUIRED_PR5_PAGES)
        self.assertEqual({item["page"] for item in manifest["screenshots"]}, REQUIRED_PR5_PAGES)

        manifest_by_page = {item["page"]: item for item in manifest["screenshots"]}
        for fixture_name, expected in expectations.items():
            with self.subTest(fixture_name=fixture_name):
                self.assertIn(expected["page"], manifest_by_page)
                screenshot = project_root / expected["screenshot"]
                self.assertTrue(screenshot.exists(), screenshot)
                with Image.open(screenshot) as image:
                    self.assertGreaterEqual(image.width, 600)
                    self.assertGreaterEqual(image.height, 300)
                    self.assertEqual(image.format, "JPEG")

                runtime_fixture = project_root / "tests" / "fixtures" / fixture_name
                self.assertTrue(runtime_fixture.exists(), runtime_fixture)
                self.assertGreater(len(expected["required_report_evidence"]), 0)
                self.assertIn("expected_report_confidence", expected)

                if expected["expected_action_type"] is None:
                    self.assertIsNone(expected["expected_action_confidence"])
                    self.assertEqual(expected["required_action_evidence"], [])
                else:
                    self.assertIsInstance(expected["expected_action_confidence"], (float, int))
                    self.assertGreater(len(expected["required_action_evidence"]), 0)

    def test_pr5_advisor_reports_lock_action_evidence_and_confidence(self) -> None:
        project_root = _project_root()
        expectations = _pr5_expectations(_load_expectation_payload())
        deriver = StateDeriver()
        selector = ActionSelector()
        verifier_registry = VerifierRegistry()

        for fixture_name, expected in sorted(expectations.items()):
            with self.subTest(fixture_name=fixture_name):
                state = load_runtime_state_record(project_root / "tests" / "fixtures" / fixture_name).state
                derived = deriver.derive(state)
                selection = selector.select(derived)
                screenshot = project_root / expected["screenshot"]
                frame = _frame(screenshot.read_bytes())
                report = build_advisor_report(
                    frame=frame,
                    state=derived,
                    selection=selection,
                    vision_summary=VisionSyncSummary(
                        page_type=expected["vision_page_type"],
                        domains_run=list(expected["vision_domains"]),
                        notes=[fixture_name],
                    ),
                )

                actual_action_type = (
                    report.recommended_action.action_type.value
                    if report.recommended_action is not None
                    else None
                )
                self.assertEqual(actual_action_type, expected["expected_action_type"])
                self.assertAlmostEqual(report.confidence, expected["expected_report_confidence"])
                for ref in expected["required_report_evidence"]:
                    self.assertIn(ref, report.evidence)

                if report.recommended_action is None:
                    self.assertIsNone(expected["expected_action_confidence"])
                    continue

                self.assertAlmostEqual(
                    report.recommended_action.confidence,
                    expected["expected_action_confidence"],
                )
                self.assertFalse(report.recommended_action.executable)
                self.assertEqual(report.recommended_action.execution_blocked_reason, "advisor_mode")
                for ref in expected["required_action_evidence"]:
                    self.assertIn(ref, report.recommended_action.evidence)
                for param_path in expected.get("required_action_param_paths", []):
                    self.assertTrue(
                        _has_path(report.recommended_action.params, param_path),
                        f"{fixture_name} missing action param path {param_path}",
                    )

                if actual_action_type in PR6_VERIFIER_EXPECTATIONS:
                    verifier_expected = PR6_VERIFIER_EXPECTATIONS[actual_action_type]
                    action_type = ActionType(actual_action_type)
                    verdict = verifier_registry.evaluate(action_type)
                    spec = verifier_registry.get(action_type)

                    self.assertEqual(verdict.decision, VerifierGateDecision.ALLOW)
                    self.assertIsNotNone(spec)
                    self.assertEqual(spec.timeout_seconds, verifier_expected["timeout_seconds"])
                    self.assertEqual(str(spec.match_policy.value), verifier_expected["match_policy"])
                    self.assertEqual(
                        [delta.path for delta in spec.expected_deltas],
                        verifier_expected["delta_paths"],
                    )


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_expectation_payload() -> dict[str, Any]:
    path = _project_root() / "tests" / "golden" / "advisor_fixture_expectations.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _pr5_expectations(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    fixtures = payload["fixtures"]
    return {
        name: value
        for name, value in fixtures.items()
        if isinstance(value, dict) and value.get("page") in REQUIRED_PR5_PAGES
    }


def _has_path(payload: dict[str, Any], dotted_path: str) -> bool:
    current: Any = payload
    for part in dotted_path.split("."):
        if not isinstance(current, dict) or part not in current:
            return False
        current = current[part]
    return True


def _load_manifest() -> dict[str, Any]:
    path = (
        _project_root()
        / "tests"
        / "fixtures"
        / "screenshots"
        / "pc_client"
        / "pr5_20260529"
        / "manifest.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def _frame(payload: bytes) -> CaptureFrame:
    source = ObservationSource(
        source_type=ObservationSourceType.SCREENSHOT_FILE,
        capabilities=CapabilityFlags(observe_only=True),
    )
    session = DeviceSession(
        profile=DeviceProfile(
            platform=DevicePlatform.PC_CLIENT,
            resolution=(1286, 666),
            screenshot_size=(1286, 666),
        ),
        source=source,
    )
    return CaptureFrame(
        png=payload,
        captured_at=datetime(2026, 5, 29, 14, 40, 0),
        device_session=session,
        source_type=ObservationSourceType.SCREENSHOT_FILE,
    )


if __name__ == "__main__":
    unittest.main()
