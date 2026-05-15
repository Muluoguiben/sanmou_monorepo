"""Tests for team detail-page extraction and TeamSnapshot merge."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import (
    apply_team_detail,
    apply_team_panel,
    extract_team_detail,
    extract_team_panel,
)


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


class TeamDetailDomainTests(unittest.TestCase):
    def test_extract_maps_visible_detail_snapshot(self) -> None:
        captured = datetime(2026, 5, 14, 17, 10, 0)
        stub = _StubVisionClient(_full_detail_payload())

        fragment = extract_team_detail(b"png", client=stub, captured_at=captured)

        self.assertEqual(stub.calls, 1)
        team = fragment.teams[0]
        self.assertEqual(team["team_id"], "部队一")
        self.assertEqual(team["detail_status"]["装备"], "observed")
        self.assertEqual(team["detail_status"]["马匹"], "observed")
        self.assertEqual(team["detail_status"]["兵书"], "observed")
        self.assertEqual(team["detail_status"]["属性加点"], "observed")
        self.assertEqual(team["detail_status"]["战法等级"], "observed")
        self.assertEqual(team["detail_status"]["兵种适性"], "observed")
        self.assertEqual(team["missing_detail_tabs"], [])
        self.assertTrue(team["team_snapshot"]["pvp_pve_basis_ready"])
        self.assertEqual(team["heroes"][0]["equipment"][0]["name"], "南蛮刀")
        self.assertEqual(team["heroes"][0]["mount"]["name"], "的卢")
        self.assertEqual(team["heroes"][0]["books"][0]["name"], "作战")
        self.assertEqual(team["heroes"][0]["tactic_details"][0]["level"], 10)
        self.assertEqual(fragment.field_meta["teams.team_detail"].source, "vision.team_detail")
        self.assertEqual(fragment.field_meta["teams.team_detail"].updated_at, captured)

    def test_apply_merges_detail_into_existing_team_and_preserves_panel_facts(self) -> None:
        state = RuntimeState(
            teams=[
                {
                    "team_id": "部队一",
                    "page_type": "team_panel",
                    "formation": "雁形阵",
                    "soldiers": 32725,
                    "max_soldiers": 33000,
                    "missing_detail_tabs": ["装备", "马匹", "兵书", "属性加点", "战法等级", "兵种适性"],
                    "heroes": [
                        {
                            "name": "祝融夫人",
                            "level": 50,
                            "soldiers": 10725,
                            "max_soldiers": 11000,
                            "tactics": ["南疆烈刃", "胜敌益强", "锐不可当"],
                        },
                        {"name": "孟获", "level": 50, "soldiers": 11000},
                    ],
                }
            ],
            main_lineup={
                "current_host_team_id": "部队一",
                "team_readiness": {
                    "formation_active": True,
                    "bond_active": True,
                    "missing_detail_tabs": ["装备", "马匹", "兵书", "属性加点", "战法等级", "兵种适性"],
                    "requires_detail_review": True,
                },
            },
        )
        fragment = extract_team_detail(b"png", client=_StubVisionClient(_full_detail_payload()))

        merged = apply_team_detail(state, fragment)

        team = merged.teams[0]
        self.assertEqual(team["formation"], "雁形阵")
        self.assertEqual(team["soldiers"], 32725)
        self.assertEqual(team["missing_detail_tabs"], [])
        self.assertTrue(team["team_snapshot"]["pvp_pve_basis_ready"])
        self.assertEqual(merged.main_lineup["team_readiness"]["missing_detail_tabs"], [])
        self.assertFalse(merged.main_lineup["team_readiness"]["requires_detail_review"])
        self.assertTrue(merged.main_lineup["team_snapshot"]["pvp_pve_basis_ready"])

        heroes = {hero["name"]: hero for hero in team["heroes"]}
        self.assertEqual(heroes["祝融夫人"]["soldiers"], 10725)
        self.assertEqual(heroes["祝融夫人"]["equipment"][0]["slot"], "武器")
        self.assertEqual(heroes["祝融夫人"]["tactic_details"][0]["max_level"], 10)
        self.assertEqual(heroes["孟获"]["soldiers"], 11000)

    def test_partial_detail_keeps_unobserved_tabs_missing(self) -> None:
        fragment = extract_team_detail(
            b"png",
            client=_StubVisionClient(
                {
                    "page_type": "equipment_mount",
                    "team_id": "部队一",
                    "detail_tabs_observed": ["装备", "坐骑"],
                    "heroes": [
                        {
                            "name": "祝融夫人",
                            "equipment": [{"slot": "武器", "name": "南蛮刀"}],
                            "mount": {"name": "的卢"},
                        }
                    ],
                }
            ),
        )

        self.assertNotIn("装备", fragment.teams[0]["missing_detail_tabs"])
        self.assertNotIn("马匹", fragment.teams[0]["missing_detail_tabs"])
        self.assertIn("兵书", fragment.teams[0]["missing_detail_tabs"])
        self.assertIn("属性加点", fragment.teams[0]["missing_detail_tabs"])
        self.assertFalse(fragment.teams[0]["team_snapshot"]["pvp_pve_basis_ready"])

    def test_later_panel_refresh_preserves_detail_fields(self) -> None:
        state = RuntimeState(main_lineup={"current_host_team_id": "部队一"})
        detail_fragment = extract_team_detail(b"png", client=_StubVisionClient(_full_detail_payload()))
        with_details = apply_team_detail(state, detail_fragment)

        panel_fragment = extract_team_panel(
            b"png",
            client=_StubVisionClient(
                {
                    "page_type": "team_panel",
                    "team_id": "部队一",
                    "formation": "雁形阵",
                    "heroes": [
                        {
                            "name": "祝融夫人",
                            "level": 50,
                            "soldiers": 10725,
                            "max_soldiers": 11000,
                        }
                    ],
                }
            ),
        )

        refreshed = apply_team_panel(with_details, panel_fragment)
        hero = refreshed.teams[0]["heroes"][0]
        self.assertEqual(hero["soldiers"], 10725)
        self.assertEqual(hero["equipment"][0]["name"], "南蛮刀")
        self.assertEqual(refreshed.teams[0]["missing_detail_tabs"], [])

    def test_faction_prefixed_hero_name_merges_into_existing_panel_hero(self) -> None:
        state = RuntimeState(
            teams=[
                {
                    "team_id": "部队一",
                    "page_type": "team_panel",
                    "heroes": [
                        {
                            "name": "祝融夫人",
                            "soldiers": 10725,
                            "tactics": ["南疆烈刃", "胜敌益强", "锐不可当"],
                        }
                    ],
                }
            ],
            main_lineup={"current_host_team_id": "部队一"},
        )
        payload = _full_detail_payload()
        payload["heroes"][0]["name"] = "群祝融夫人"
        payload["heroes"][0]["attribute_points"] = {"武力": 100}
        payload["heroes"][0]["tactic_details"][0]["name"] = "南疆劣刃"
        fragment = extract_team_detail(b"png", client=_StubVisionClient(payload))

        merged = apply_team_detail(state, fragment)

        self.assertEqual(len(merged.teams[0]["heroes"]), 1)
        hero = merged.teams[0]["heroes"][0]
        self.assertEqual(hero["name"], "祝融夫人")
        self.assertEqual(hero["soldiers"], 10725)
        self.assertEqual(hero["attribute_points"]["武力"], 100)
        self.assertEqual(hero["tactic_details"][0]["name"], "南疆烈刃")


def _full_detail_payload() -> dict[str, Any]:
    return {
        "page_type": "hero_detail",
        "team_id": "部队一",
        "detail_tabs_observed": ["装备", "马匹", "兵书", "属性加点", "战法等级", "兵种适性"],
        "heroes": [
            {
                "name": "祝融夫人",
                "level": 50,
                "role": "主将",
                "attributes": {"武力": 256, "统率": 218, "先攻": 133},
                "attribute_points": {"武力": 30},
                "soldier_specialties": ["盾兵 S", "骑兵 A"],
                "equipment": [
                    {
                        "slot": "武器",
                        "name": "南蛮刀",
                        "level": 20,
                        "rarity": "橙",
                        "attributes": {"武力": 18},
                    }
                ],
                "mount": {
                    "name": "的卢",
                    "level": 30,
                    "quality": "橙",
                    "skills": ["疾驰"],
                },
                "books": [
                    {
                        "slot": "一",
                        "name": "作战",
                        "level": 5,
                        "active": True,
                        "effects": ["伤害提升"],
                    }
                ],
                "tactic_details": [
                    {
                        "slot": "自带",
                        "name": "南疆烈刃",
                        "level": 10,
                        "max_level": 10,
                    }
                ],
            }
        ],
        "team_effects": ["雁形阵已激活"],
        "visible_notes": ["详情页信息完整"],
    }


if __name__ == "__main__":
    unittest.main()
