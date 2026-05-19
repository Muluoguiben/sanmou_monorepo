from __future__ import annotations

from pathlib import Path
import unittest

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.knowledge.strategy_snapshot import StrategySnapshot, load_strategy_snapshot
from pioneer_agent.selector.action_selector import ActionSelector


class ActionSelectorStrategySnapshotTests(unittest.TestCase):
    def test_building_priority_snapshot_boosts_upgrade_score(self) -> None:
        snapshot = StrategySnapshot(
            {
                "schema_version": "strategy_snapshot.v1",
                "generated_at": "2026-05-17",
                "sources": [],
                "building_priorities": [
                    {
                        "key": "recruit-building",
                        "entry_ids": ["recruit-building"],
                        "topic": "征兵所",
                        "aliases": ["barracks"],
                        "priority": 100,
                    }
                ],
                "land_risk_rules": [],
                "lineup_hints": [],
            }
        )
        state = RuntimeState(
            city={
                "upgradeable_buildings": [
                    {
                        "building_id": "mill",
                        "target_level": 2,
                        "chapter_relevance": "low_relevance",
                        "resource_shortages": {},
                    },
                    {
                        "building_id": "barracks",
                        "target_level": 2,
                        "chapter_relevance": "low_relevance",
                        "resource_shortages": {},
                    },
                ]
            }
        )

        result = ActionSelector(strategy_snapshot=snapshot).select(state)

        self.assertIsNotNone(result.selected_action)
        selected = result.selected_action
        assert selected is not None
        self.assertEqual(selected.params["building_id"], "barracks")
        self.assertEqual(selected.params["strategy_entry_ids"], ["recruit-building"])
        self.assertEqual(selected.params["strategy_topic"], "征兵所")
        self.assertEqual(selected.score_breakdown["strategy_priority_bonus"], 10.0)

    def test_generated_snapshot_prioritizes_named_building(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        snapshot = load_strategy_snapshot(project_root / "data" / "strategy_snapshot.yaml")
        state = RuntimeState(
            city={
                "upgradeable_buildings": [
                    {
                        "building_id": "mill",
                        "building_name": "磨坊",
                        "target_level": 2,
                        "chapter_relevance": "low_relevance",
                        "resource_shortages": {},
                    },
                    {
                        "building_id": "main_hall",
                        "building_name": "君王殿",
                        "target_level": 2,
                        "chapter_relevance": "low_relevance",
                        "resource_shortages": {},
                    },
                ]
            }
        )

        result = ActionSelector(strategy_snapshot=snapshot).select(state)

        self.assertIsNotNone(result.selected_action)
        selected = result.selected_action
        assert selected is not None
        self.assertEqual(selected.params["building_id"], "main_hall")
        self.assertEqual(selected.params["building_name"], "君王殿")
        self.assertIn("building-main-city", selected.params["strategy_entry_ids"])
        self.assertEqual(selected.score_breakdown["strategy_priority_bonus"], 9.0)
        self.assertIn("建议升级 君王殿", result.selection_reason["summary"])
        self.assertIn("知识库依据：君王殿是多数城建解锁和章节推进的核心建筑之一", result.selection_reason["summary"])

    def test_default_selector_loads_generated_snapshot(self) -> None:
        state = RuntimeState(
            city={
                "upgradeable_buildings": [
                    {
                        "building_id": "mill",
                        "building_name": "磨坊",
                        "target_level": 2,
                        "chapter_relevance": "low_relevance",
                        "resource_shortages": {},
                    },
                    {
                        "building_id": "main_hall",
                        "building_name": "君王殿",
                        "target_level": 2,
                        "chapter_relevance": "low_relevance",
                        "resource_shortages": {},
                    },
                ]
            }
        )

        result = ActionSelector().select(state)

        self.assertIsNotNone(result.selected_action)
        selected = result.selected_action
        assert selected is not None
        self.assertEqual(selected.params["building_id"], "main_hall")


if __name__ == "__main__":
    unittest.main()
