"""Replay real mobile TeamSnapshot screenshots through the offline eval fixture."""
from __future__ import annotations

import json
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.perception.vision_sync import VisionSync
from pioneer_agent.selector.action_selector import ActionSelector


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "fixture"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _ReplayVisionClient:
    """Return reviewed payloads captured from real screenshots, in call order."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.calls: list[str] = []

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        if len(self.calls) >= len(self._payloads):
            raise AssertionError("unexpected extra vision extraction")
        payload = self._payloads[len(self.calls)]
        self.calls.append(str(payload["domain"]))
        return _StubResult(data=dict(payload["data"]))


class TeamSnapshotScreenshotEvalTests(unittest.TestCase):
    def test_real_mobile_screenshots_replay_into_team_snapshot_judgement(self) -> None:
        fixture = _load_fixture()
        state = RuntimeState(
            global_state={
                "server_open_time": "2026-05-14T10:00:00+08:00",
                "current_time": "2026-05-14T17:30:00+08:00",
                "phase_tag": "advisor_team_review",
            },
            progress={"chapter_claimable": False, "task_progress": {}},
            economy={"reserve_troops": 0},
            city={"upgradeable_buildings": []},
            map_state={"candidate_lands": []},
        )

        for shot in fixture["screenshots"]:
            image_path = _fixture_dir() / shot["image"]
            self.assertTrue(image_path.exists(), shot["id"])
            self.assertGreater(image_path.stat().st_size, 100_000, shot["id"])

            client = _ReplayVisionClient(shot["payloads"])
            state, summary = VisionSync(client).sync(
                image_path,
                state=state,
                captured_at=datetime.fromisoformat(shot["captured_at"]),
            )

            self.assertEqual(summary.domains_run, shot["expected_domains"], shot["id"])
            self.assertEqual(client.calls, shot["expected_domains"], shot["id"])

        derived = StateDeriver().derive(state)
        team = derived.teams[0]
        expected = fixture["expected"]

        self.assertEqual(team["team_id"], expected["team_id"])
        self.assertEqual([hero["name"] for hero in team["heroes"]], expected["heroes"])
        self.assertEqual(team["missing_detail_tabs"], expected["missing_detail_tabs"])
        self.assertEqual(team["detail_status"], expected["detail_status"])
        self.assertEqual(
            team["team_snapshot"]["detail_completion"],
            {tab: True for tab in expected["detail_status"]},
        )

        zhurong = team["heroes"][0]
        self.assertEqual(
            [item["name"] for item in zhurong["tactic_details"]],
            expected["zhurong"]["tactic_details"],
        )
        self.assertEqual(zhurong["equipment"][0]["name"], expected["zhurong"]["equipment"])
        self.assertEqual(zhurong["mount"]["name"], expected["zhurong"]["mount"])
        self.assertEqual(zhurong["attribute_points"], expected["zhurong"]["attribute_points"])
        self.assertEqual(
            [item["name"] for item in zhurong["books"]],
            expected["zhurong"]["books"],
        )

        judgement = team["team_snapshot"]["readiness_judgement"]
        self.assertEqual(judgement["overall_status"], expected["judgement"]["overall_status"])
        self.assertEqual(judgement["basis_ready"], expected["judgement"]["basis_ready"])
        self.assertEqual(
            judgement["facts"]["detailed_hero_count"],
            expected["judgement"]["detailed_hero_count"],
        )
        self.assertEqual(judgement["facts"]["hero_count"], expected["judgement"]["hero_count"])
        self.assertIn(
            expected["judgement"]["required_issue"],
            [issue["code"] for issue in judgement["issues"]],
        )

        result = ActionSelector().select(derived)
        self.assertIsNotNone(result.selected_action)
        selected = result.selected_action
        assert selected is not None
        self.assertEqual(selected.action_type.value, "inspect_team_readiness")
        self.assertEqual(
            selected.params["readiness_judgement"]["overall_status"],
            expected["judgement"]["overall_status"],
        )


def _fixture_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures"


def _load_fixture() -> dict[str, Any]:
    path = _fixture_dir() / "vision" / "team_snapshot_mobile_20260514.json"
    return json.loads(path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
