from pathlib import Path
import tempfile
import unittest

import yaml

from pioneer_agent.knowledge.strategy_snapshot import load_default_strategy_snapshot, load_strategy_snapshot


class StrategySnapshotTests(unittest.TestCase):
    def test_load_strategy_snapshot_and_query_by_key(self) -> None:
        payload = {
            "schema_version": "strategy_snapshot.v1",
            "generated_at": "2026-04-13",
            "sources": [{"path": "building.yaml", "entry_count": 1, "entry_ids": ["building-upgrade"]}],
            "building_priorities": [
                {"key": "building-upgrade", "topic": "建筑升级", "priority": 95, "rationale": "资源和前置满足。"}
            ],
            "land_risk_rules": [
                {"key": "combat-land-level", "topic": "地块等级", "priority": 90, "rule": "收益与风险同时上升。"}
            ],
            "lineup_hints": [
                {"key": "lineup-s1-example", "name": "示例开荒队", "hero_names": ["武将甲", "武将乙"]}
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "snapshot.yaml"
            path.write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")

            snapshot = load_strategy_snapshot(path)

        self.assertEqual(snapshot.schema_version, "strategy_snapshot.v1")
        self.assertEqual(snapshot.generated_at, "2026-04-13")
        self.assertEqual(snapshot.get_building_priority("building-upgrade")["topic"], "建筑升级")
        self.assertEqual(snapshot.find_building_priority("建筑升级")["key"], "building-upgrade")
        self.assertEqual(snapshot.get_land_risk_rule("combat-land-level")["priority"], 90)
        self.assertEqual(snapshot.get_lineup_hint("lineup-s1-example")["hero_names"], ["武将甲", "武将乙"])
        self.assertIsNone(snapshot.get("building_priorities", "missing"))

    def test_load_strategy_snapshot_rejects_missing_required_section(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "snapshot.yaml"
            path.write_text("schema_version: strategy_snapshot.v1\n", encoding="utf-8")

            with self.assertRaises(ValueError):
                load_strategy_snapshot(path)

    def test_load_generated_strategy_snapshot_artifact(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        snapshot = load_strategy_snapshot(project_root / "data" / "strategy_snapshot.yaml")

        self.assertGreater(len(snapshot.section("building_priorities")), 0)
        self.assertGreater(len(snapshot.section("land_risk_rules")), 0)
        self.assertGreater(len(snapshot.section("lineup_hints")), 0)

    def test_load_default_strategy_snapshot_from_repo_data(self) -> None:
        snapshot = load_default_strategy_snapshot()

        self.assertIsNotNone(snapshot)
        assert snapshot is not None
        self.assertEqual(snapshot.schema_version, "strategy_snapshot.v1")


if __name__ == "__main__":
    unittest.main()
