from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import apply_recruit_panel, extract_recruit_panel


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


class RecruitPanelDomainTests(unittest.TestCase):
    def test_raw_boolean_cannot_be_coerced_to_soldier_count(self) -> None:
        with self.assertRaises(ValidationError):
            extract_recruit_panel(
                b"png",
                client=_StubVision(
                    {"teams": [{"team_id": "部队一", "soldiers": True}]}
                ),
            )

    def test_extract_maps_recruit_panel(self) -> None:
        fragment = extract_recruit_panel(
            b"png",
            client=_StubVision(
                {
                    "reserve_troops": 9000,
                    "teams": [
                        {
                            "team_id": "部队一",
                            "soldiers": 24000,
                            "max_soldiers": 30000,
                            "recruiting": False,
                            "can_recruit_now": True,
                            "recruit_button_visible": True,
                            "recruit_button_enabled": True,
                            "button_x_min": 760,
                            "button_y_min": 820,
                            "button_x_max": 920,
                            "button_y_max": 900,
                        }
                    ],
                    "visible_notes": ["可征兵"],
                }
            ),
            captured_at=datetime(2026, 5, 17, 12, 0, 0),
        )

        self.assertEqual(fragment.economy["reserve_troops"], 9000)
        team = fragment.teams[0]
        self.assertEqual(team["team_id"], "部队一")
        self.assertEqual(team["soldier_deficit"], 6000)
        self.assertTrue(team["recruit_button"]["enabled"])
        self.assertEqual(team["recruit_button"]["bbox"]["x_min"], 760)
        self.assertIn("economy.reserve_troops", fragment.field_meta)

    def test_apply_recruit_panel_merges_economy_and_team(self) -> None:
        fragment = extract_recruit_panel(
            b"png",
            client=_StubVision(
                {
                    "reserve_troops": 1200,
                    "teams": [
                        {
                            "team_id": "部队一",
                            "soldiers": 800,
                            "max_soldiers": 1000,
                            "recruiting": True,
                            "recruit_finish_time": "00:12:00",
                        }
                    ],
                }
            ),
        )
        state = RuntimeState(
            economy={"wood": 100},
            teams=[{"team_id": "部队一", "level": 10}],
        )

        merged = apply_recruit_panel(state, fragment)

        self.assertEqual(merged.economy["wood"], 100)
        self.assertEqual(merged.economy["reserve_troops"], 1200)
        self.assertEqual(merged.teams[0]["level"], 10)
        self.assertEqual(merged.teams[0]["status"], "recruiting")
        self.assertEqual(merged.teams[0]["recruit_finish_time"], "00:12:00")


if __name__ == "__main__":
    unittest.main()
