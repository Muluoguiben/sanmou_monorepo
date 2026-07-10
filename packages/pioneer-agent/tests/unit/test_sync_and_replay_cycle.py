from pathlib import Path
import unittest

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

    def test_seed_state_can_be_replayed_into_canonical_runtime(self) -> None:
        project_root = Path(__file__).resolve().parents[2]
        sync_input = project_root / "data" / "perception" / "latest_state.json"

        state, _summary = StateSyncService(sync_input).full_sync()
        result = ReplayRuntime().run_state(state, "seed_state")

        self.assertIsNotNone(result["selected_action"])
        self.assertEqual(result["selected_action"]["action_type"], "attack_land")


if __name__ == "__main__":
    unittest.main()
