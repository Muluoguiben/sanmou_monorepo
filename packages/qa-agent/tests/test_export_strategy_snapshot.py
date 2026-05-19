from pathlib import Path
import tempfile
import unittest

import yaml

from qa_agent.app.export_strategy_snapshot import build_strategy_snapshot, write_strategy_snapshot


class ExportStrategySnapshotTests(unittest.TestCase):
    def test_build_strategy_snapshot_contains_required_sections(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        snapshot = build_strategy_snapshot(project_root / "knowledge_sources")

        self.assertEqual(snapshot["schema_version"], "strategy_snapshot.v1")
        self.assertRegex(snapshot["generated_at"], r"^\d{4}-\d{2}-\d{2}$")
        self.assertGreater(len(snapshot["sources"]), 0)
        self.assertGreater(len(snapshot["building_priorities"]), 0)
        self.assertGreater(len(snapshot["land_risk_rules"]), 0)
        self.assertGreater(len(snapshot["lineup_hints"]), 0)

        building = snapshot["building_priorities"][0]
        self.assertIn("key", building)
        self.assertEqual(building["entry_ids"], [building["key"]])
        self.assertIn("priority", building)
        self.assertIn("rationale", building)

    def test_write_strategy_snapshot_is_deterministic_yaml(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        snapshot = build_strategy_snapshot(project_root / "knowledge_sources")

        with tempfile.TemporaryDirectory() as temp_dir:
            first = Path(temp_dir) / "snapshot-a.yaml"
            second = Path(temp_dir) / "snapshot-b.yaml"
            write_strategy_snapshot(snapshot, first)
            write_strategy_snapshot(snapshot, second)

            self.assertEqual(first.read_text(encoding="utf-8"), second.read_text(encoding="utf-8"))
            loaded = yaml.safe_load(first.read_text(encoding="utf-8"))
            self.assertEqual(loaded["schema_version"], "strategy_snapshot.v1")


if __name__ == "__main__":
    unittest.main()
