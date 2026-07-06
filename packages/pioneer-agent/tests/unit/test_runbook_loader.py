import tempfile
import unittest
from pathlib import Path

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.runbook.loader import (
    DEFAULT_OPENING_RUNBOOK_PATH,
    load_default_opening_runbook,
    load_runbook,
    metrics_from_runtime_state,
)
from pioneer_agent.runbook.models import OpeningRunbook


class RunbookLoaderTests(unittest.TestCase):
    def test_load_seed_s15_runbook(self) -> None:
        runbook = load_default_opening_runbook()
        self.assertIsInstance(runbook, OpeningRunbook)
        self.assertTrue(DEFAULT_OPENING_RUNBOOK_PATH.exists())
        phase_ids = [phase.phase_id for phase in runbook.phases]
        self.assertEqual(phase_ids[0], "claim_rewards")
        self.assertIn("er_tuo_yi", phase_ids)
        self.assertIn("open_lv5_6", phase_ids)

        er_tuo_yi = runbook.phase("er_tuo_yi")
        self.assertTrue(er_tuo_yi.human_gate)

        open_lv5_6 = runbook.phase("open_lv5_6")
        self.assertTrue(open_lv5_6.needs_review)
        self.assertTrue(open_lv5_6.abort_when)
        entry_metrics = {condition.metric for condition in open_lv5_6.entry_when}
        self.assertIn("main_team_avg_level", entry_metrics)

    def test_seed_runbook_marks_untrusted_values_for_review(self) -> None:
        runbook = load_default_opening_runbook()
        for phase in runbook.phases:
            self.assertTrue(
                phase.needs_review,
                f"seed phase {phase.phase_id} must stay needs_review until 人工复核",
            )

    def test_rejects_duplicate_phase_ids(self) -> None:
        payload = {
            "season": "S15",
            "generated_at": "2026-07-05",
            "phases": [
                {"phase_id": "a", "title": "A"},
                {"phase_id": "a", "title": "A2"},
            ],
        }
        with self.assertRaises(ValueError):
            OpeningRunbook.model_validate(payload)

    def test_rejects_empty_phases(self) -> None:
        with self.assertRaises(ValueError):
            OpeningRunbook.model_validate(
                {"season": "S15", "generated_at": "2026-07-05", "phases": []}
            )

    def test_load_runbook_from_yaml_file(self) -> None:
        payload = "\n".join(
            [
                "season: S15",
                "generated_at: '2026-07-05'",
                "phases:",
                "- phase_id: only",
                "  title: 唯一阶段",
                "  exit_when:",
                "    done: '== true'",
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runbook.yaml"
            path.write_text(payload, encoding="utf-8")
            runbook = load_runbook(path)
        self.assertEqual(runbook.phases[0].phase_id, "only")

    def test_missing_default_runbook_returns_none(self) -> None:
        missing = Path("/nonexistent/opening_runbook.yaml")
        self.assertIsNone(load_default_opening_runbook(missing))

    def test_load_warns_on_allowlist_entries_matching_no_action_type(self) -> None:
        payload = "\n".join(
            [
                "season: S15",
                "generated_at: '2026-07-07'",
                "phases:",
                "- phase_id: bad_allowlist",
                "  title: 拼写错误",
                "  exit_when:",
                "    done: '== true'",
                "  selector_hints:",
                "    allowed_action_types: [ATTACK_LAND, attack_land]",
            ]
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "runbook.yaml"
            path.write_text(payload, encoding="utf-8")
            with self.assertLogs("pioneer_agent.runbook.loader", level="WARNING") as captured:
                load_runbook(path)
        self.assertTrue(any("ATTACK_LAND" in line for line in captured.output))

    def test_user_path_expands_home(self) -> None:
        from pioneer_agent.app.cli_utils import user_path

        self.assertEqual(user_path("~/x.json"), Path.home() / "x.json")
        self.assertEqual(user_path("data/loop/x.json"), Path("data/loop/x.json"))


class MetricsFromRuntimeStateTests(unittest.TestCase):
    def test_extracts_flat_metrics_and_keeps_dotted_paths(self) -> None:
        state = RuntimeState(
            global_state={"phase_tag": "opening_sprint", "hours_since_server_open": 5.5},
            progress={"opening_rewards_claimed": True},
            main_lineup={"avg_level": 38.5, "current_host_team_id": "team-1"},
            team_containers=[
                {"team_id": "team-1", "soldiers": 17500, "container_stamina": 80},
                {"team_id": "team-2", "soldiers": 9000},
            ],
        )
        metrics = metrics_from_runtime_state(state, extra_metrics={"inner_lands_owned_lv1_2": 4})

        self.assertEqual(metrics["main_team_avg_level"], 38.5)
        self.assertEqual(metrics["host_team_soldiers"], 17500)
        self.assertEqual(metrics["host_team_stamina"], 80)
        self.assertEqual(metrics["phase_tag"], "opening_sprint")
        self.assertEqual(metrics["inner_lands_owned_lv1_2"], 4)
        self.assertTrue(metrics["progress"]["opening_rewards_claimed"])

    def test_handles_empty_state(self) -> None:
        metrics = metrics_from_runtime_state(RuntimeState())
        self.assertNotIn("main_team_avg_level", metrics)
        self.assertNotIn("host_team_soldiers", metrics)


if __name__ == "__main__":
    unittest.main()
