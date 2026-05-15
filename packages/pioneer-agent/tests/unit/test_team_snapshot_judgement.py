from pathlib import Path
import unittest

from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.derivation.state_deriver import StateDeriver
from pioneer_agent.derivation.team_snapshot import evaluate_team_snapshot
from pioneer_agent.selector.action_selector import ActionSelector


class TeamSnapshotJudgementTests(unittest.TestCase):
    def test_ready_fixture_is_usable_for_pvp_pve_and_expedition(self) -> None:
        state = _load_fixture("team_snapshot_ready_state.json")

        derived = StateDeriver().derive(state)

        judgement = derived.teams[0]["team_snapshot"]["readiness_judgement"]
        self.assertEqual(judgement["overall_status"], "ready")
        self.assertTrue(judgement["basis_ready"])
        self.assertEqual(judgement["facts"]["detail_coverage_ratio"], 1.0)
        self.assertEqual(judgement["mode_judgement"]["pvp"]["status"], "ready")
        self.assertEqual(judgement["mode_judgement"]["pve"]["status"], "ready")
        self.assertEqual(judgement["mode_judgement"]["expedition"]["status"], "ready")
        self.assertEqual(
            derived.main_lineup["team_snapshot"]["readiness_judgement"]["overall_status"],
            "ready",
        )

        result = ActionSelector().select(derived)
        self.assertFalse(
            any(action.action_type.value == "inspect_team_readiness" for action in result.ranked_actions)
        )

    def test_team_panel_fixture_requires_detail_review(self) -> None:
        state = _load_fixture("team_panel_state.json")

        derived = StateDeriver().derive(state)

        judgement = derived.teams[0]["team_snapshot"]["readiness_judgement"]
        self.assertEqual(judgement["overall_status"], "insufficient_basis")
        self.assertFalse(judgement["basis_ready"])
        self.assertIn("missing_detail_tabs", [issue["code"] for issue in judgement["issues"]])

        result = ActionSelector().select(derived)
        self.assertIsNotNone(result.selected_action)
        selected = result.selected_action
        assert selected is not None
        self.assertEqual(selected.action_type.value, "inspect_team_readiness")
        self.assertEqual(
            selected.params["readiness_judgement"]["overall_status"],
            "insufficient_basis",
        )
        self.assertGreater(selected.score_breakdown["team_snapshot_judgement"], 0)

    def test_partial_hero_detail_coverage_blocks_final_judgement(self) -> None:
        team = {
            "team_id": "部队一",
            "page_type": "team_detail",
            "formation_active": True,
            "bond_active": True,
            "soldiers": 33000,
            "max_soldiers": 33000,
            "missing_detail_tabs": [],
            "team_snapshot": {
                "detail_completion": {
                    "装备": True,
                    "马匹": True,
                    "兵书": True,
                    "属性加点": True,
                    "战法等级": True,
                    "兵种适性": True,
                },
                "pvp_pve_basis_ready": True,
            },
            "heroes": [
                {
                    "name": "祝融夫人",
                    "equipment": [{"name": "虎头湛金枪"}],
                    "mount": {"name": "乌云踏雪"},
                    "books": [{"name": "火裔绝刃"}],
                    "attribute_points": {"武力": 100},
                    "tactic_details": [{"name": "南疆烈刃", "level": 10, "max_level": 10}],
                    "soldier_specialties": ["骑兵 S"],
                },
                {"name": "孟获", "tactics": ["雄护南疆", "指点乾坤", "踏锋饮血"]},
                {"name": "诸葛亮2", "tactics": ["星罗棋布", "折冲御侮", "践墨随敌"]},
            ],
        }

        judgement = evaluate_team_snapshot(team)

        self.assertEqual(judgement["overall_status"], "insufficient_basis")
        self.assertFalse(judgement["basis_ready"])
        self.assertEqual(judgement["facts"]["detailed_hero_count"], 1)
        self.assertIn(
            "partial_hero_detail_coverage",
            [issue["code"] for issue in judgement["issues"]],
        )


def _load_fixture(name: str):
    project_root = Path(__file__).resolve().parents[2]
    return load_runtime_state_record(project_root / "tests" / "fixtures" / name).state


if __name__ == "__main__":
    unittest.main()
