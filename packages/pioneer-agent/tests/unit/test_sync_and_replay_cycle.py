from pathlib import Path
import tempfile
import unittest

from pioneer_agent.app.bootstrap import build_runtime
from pioneer_agent.core.runtime_state_io import load_runtime_state_record
from pioneer_agent.perception.sync_service import StateSyncService
from pioneer_agent.runtime.replay_runtime import ReplayRuntime


class SyncAndReplayCycleTests(unittest.TestCase):
    def test_sync_service_loads_non_empty_seed_state(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        sync_input = project_root / "data" / "perception" / "latest_state.json"

        state, summary = StateSyncService(sync_input).full_sync()

        self.assertTrue(summary.non_empty_state)
        self.assertIn("global_state", summary.domains_refreshed)
        self.assertEqual(state.main_lineup.get("current_host_team_id"), 1)
        self.assertIn("global_state", state.field_meta)

    def test_runtime_log_can_be_replayed_back_into_selector(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        sync_input = project_root / "data" / "perception" / "latest_state.json"

        with tempfile.TemporaryDirectory() as temp_dir:
            log_dir = Path(temp_dir)
            runtime = build_runtime(project_root, sync_input=sync_input, log_dir=log_dir)
            runtime.run_once()

            record = load_runtime_state_record(log_dir / "state.jsonl")
            result = ReplayRuntime().run_state(record.state, "temp_log_record")

            self.assertIsNotNone(result["selected_action"])
            self.assertEqual(result["selected_action"]["action_type"], "attack_land")


if __name__ == "__main__":
    unittest.main()
