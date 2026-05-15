"""Tests for structured team-panel extraction and RuntimeState merge."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import apply_team_panel, extract_team_panel


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _StubVisionClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls = 0

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        self.calls += 1
        return _StubResult(data=self._payload)


class TeamPanelDomainTests(unittest.TestCase):
    def test_extract_maps_team_snapshot(self) -> None:
        captured = datetime(2026, 5, 14, 16, 0, 0)
        stub = _StubVisionClient(_team_payload())

        fragment = extract_team_panel(b"png", client=stub, captured_at=captured)

        self.assertEqual(stub.calls, 1)
        self.assertEqual(fragment.teams[0]["team_id"], "部队一")
        self.assertEqual(fragment.teams[0]["formation"], "雁形阵")
        self.assertTrue(fragment.teams[0]["formation_active"])
        self.assertTrue(fragment.teams[0]["bond_active"])
        self.assertEqual(fragment.teams[0]["soldiers"], 32725)
        self.assertEqual(fragment.teams[0]["max_soldiers"], 33000)
        self.assertEqual(fragment.teams[0]["soldier_deficit"], 275)
        self.assertEqual(fragment.team_containers[0]["container_stamina"], 200)
        self.assertEqual(fragment.teams[0]["heroes"][0]["name"], "祝融夫人")
        self.assertEqual(fragment.teams[0]["heroes"][0]["soldier_deficit"], 275)
        self.assertIn("装备", fragment.teams[0]["missing_detail_tabs"])
        self.assertEqual(fragment.field_meta["teams"].source, "vision.team_panel")
        self.assertEqual(fragment.field_meta["teams"].updated_at, captured)

    def test_apply_merges_by_team_id_and_sets_main_lineup(self) -> None:
        state = RuntimeState(
            teams=[{"team_id": "部队一", "old": "keep"}, {"team_id": "部队二", "old": "stay"}],
            team_containers=[{"team_id": "部队一", "status": "old"}],
        )
        fragment = extract_team_panel(b"png", client=_StubVisionClient(_team_payload()))

        merged = apply_team_panel(state, fragment)

        by_id = {team["team_id"]: team for team in merged.teams}
        self.assertEqual(by_id["部队一"]["old"], "keep")
        self.assertEqual(by_id["部队一"]["formation"], "雁形阵")
        self.assertEqual(by_id["部队二"]["old"], "stay")
        self.assertEqual(merged.team_containers[0]["soldier_deficit"], 275)
        self.assertEqual(merged.main_lineup["current_host_team_id"], "部队一")
        self.assertTrue(merged.main_lineup["team_readiness"]["requires_detail_review"])


def _team_payload() -> dict[str, Any]:
    return {
        "page_type": "team_panel",
        "team_id": "部队一",
        "formation": "雁形阵",
        "formation_active": True,
        "bond_active": True,
        "total_soldiers": 32725,
        "max_soldiers": 33000,
        "supply": 100,
        "supply_max": 100,
        "heroes": [
            {
                "name": "祝融夫人",
                "level": 50,
                "soldiers": 10725,
                "max_soldiers": 11000,
                "stamina": 200,
                "stamina_max": 200,
                "tactics": ["南疆烈刃", "胜敌益强", "锐不可当"],
            },
            {
                "name": "孟获",
                "level": 50,
                "soldiers": 11000,
                "max_soldiers": 11000,
                "stamina": 200,
                "stamina_max": 200,
                "tactics": ["雄护南疆", "指点乾坤", "踏锋饮血"],
            },
            {
                "name": "诸葛亮2",
                "level": 50,
                "soldiers": 11000,
                "max_soldiers": 11000,
                "stamina": 200,
                "stamina_max": 200,
                "tactics": ["星罗棋布", "折冲御侮", "践墨随敌"],
            },
        ],
        "visible_entry_points": ["编队", "配将助手"],
        "readiness_notes": ["祝融夫人未满兵"],
        "missing_detail_tabs": ["装备", "兵书"],
        "visible_notes": ["补给 100/100"],
    }


if __name__ == "__main__":
    unittest.main()
