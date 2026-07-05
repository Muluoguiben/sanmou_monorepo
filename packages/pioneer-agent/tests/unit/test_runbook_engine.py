import unittest

from pioneer_agent.runbook.engine import RunbookEngine
from pioneer_agent.runbook.models import (
    Condition,
    ConditionStatus,
    EscalationKind,
    EscalationRoute,
    OpeningRunbook,
)


def _runbook() -> OpeningRunbook:
    return OpeningRunbook.model_validate(
        {
            "season": "S15 测试",
            "generated_at": "2026-07-05",
            "phases": [
                {
                    "phase_id": "claim_rewards",
                    "title": "收菜",
                    "exit_when": {"rewards_claimed": "== true"},
                    "selector_hints": {"routine": "claim_rewards"},
                },
                {
                    "phase_id": "clear_lv1_2",
                    "title": "杂牌清地",
                    "exit_when": {"inner_lands_owned_lv1_2": ">= 4"},
                    "selector_hints": {"lineup_preset": "junk_team"},
                },
                {
                    "phase_id": "er_tuo_yi",
                    "title": "二拖一",
                    "human_gate": True,
                    "exit_when": {"er_tuo_yi_done": "== true"},
                },
                {
                    "phase_id": "open_lv5",
                    "title": "开5级地",
                    "entry_when": {
                        "main_team_avg_level": ">= 37",
                        "host_team_soldiers": ">= 17000",
                    },
                    "exit_when": {"highest_land_level_cleared": ">= 5"},
                    "abort_when": {
                        "battle_loss_rate": "> 0.35",
                        "consecutive_defeats": ">= 2",
                    },
                    "selector_hints": {"lineup_preset": "diaochan_manyi"},
                },
            ],
        }
    )


class ConditionTests(unittest.TestCase):
    def test_parse_operator_expressions(self) -> None:
        condition = Condition.parse("main_team_avg_level", ">= 37")
        self.assertEqual(condition.op, ">=")
        self.assertEqual(condition.value, 37)

        condition = Condition.parse("rewards_claimed", "== true")
        self.assertEqual(condition.op, "==")
        self.assertIs(condition.value, True)

        condition = Condition.parse("count", 4)
        self.assertEqual(condition.op, "==")
        self.assertEqual(condition.value, 4)

    def test_rejects_unsupported_op(self) -> None:
        with self.assertRaises(ValueError):
            Condition(metric="x", op="~=", value=1)

    def test_missing_metric_is_unknown_not_false(self) -> None:
        condition = Condition.parse("battle_loss_rate", "> 0.35")
        self.assertEqual(condition.evaluate({}), ConditionStatus.UNKNOWN)
        self.assertEqual(
            condition.evaluate({"battle_loss_rate": None}), ConditionStatus.UNKNOWN
        )

    def test_ordering_op_on_non_numeric_is_unknown(self) -> None:
        condition = Condition.parse("main_team_avg_level", ">= 37")
        self.assertEqual(
            condition.evaluate({"main_team_avg_level": "unknown"}),
            ConditionStatus.UNKNOWN,
        )

    def test_dotted_path_resolution(self) -> None:
        condition = Condition.parse("progress.opening_rewards_claimed", "== true")
        metrics = {"progress": {"opening_rewards_claimed": True}}
        self.assertEqual(condition.evaluate(metrics), ConditionStatus.SATISFIED)


class RunbookEngineTests(unittest.TestCase):
    def test_holds_while_exit_not_satisfied(self) -> None:
        engine = RunbookEngine(_runbook())
        decision = engine.evaluate({"rewards_claimed": False})
        self.assertEqual(decision.phase_id, "claim_rewards")
        self.assertFalse(decision.transitioned)
        self.assertEqual(decision.escalations, [])
        self.assertEqual(decision.selector_hints, {"routine": "claim_rewards"})

    def test_advances_when_exit_and_entry_satisfied(self) -> None:
        engine = RunbookEngine(_runbook())
        decision = engine.evaluate({"rewards_claimed": True})
        self.assertTrue(decision.transitioned)
        self.assertEqual(decision.previous_phase_id, "claim_rewards")
        self.assertEqual(decision.phase_id, "clear_lv1_2")
        self.assertEqual(decision.selector_hints, {"lineup_preset": "junk_team"})

    def test_unknown_exit_metric_escalates_to_planner(self) -> None:
        engine = RunbookEngine(_runbook())
        decision = engine.evaluate({})
        self.assertEqual(decision.hold_reason, "exit_metrics_unknown")
        self.assertEqual(len(decision.escalations), 1)
        escalation = decision.escalations[0]
        self.assertEqual(escalation.kind, EscalationKind.UNKNOWN_METRICS)
        self.assertEqual(escalation.route, EscalationRoute.LLM_PLANNER)
        self.assertIn("rewards_claimed", escalation.details["missing_metrics"])

    def test_human_gate_blocks_until_confirmed(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="clear_lv1_2")
        metrics = {"inner_lands_owned_lv1_2": 4}

        decision = engine.evaluate(metrics)
        self.assertFalse(decision.transitioned)
        self.assertEqual(decision.hold_reason, "human_gate_pending")
        self.assertEqual(decision.human_gate_pending, "er_tuo_yi")
        self.assertEqual(decision.escalations[0].kind, EscalationKind.HUMAN_GATE)
        self.assertEqual(decision.escalations[0].route, EscalationRoute.HUMAN)

        engine.confirm_human_gate("er_tuo_yi")
        decision = engine.evaluate(metrics)
        self.assertTrue(decision.transitioned)
        self.assertEqual(decision.phase_id, "er_tuo_yi")

    def test_blocked_entry_escalates_with_failed_conditions(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="er_tuo_yi")
        engine.confirm_human_gate("er_tuo_yi")
        decision = engine.evaluate(
            {
                "er_tuo_yi_done": True,
                "main_team_avg_level": 30,
                "host_team_soldiers": 20000,
            }
        )
        self.assertFalse(decision.transitioned)
        self.assertEqual(decision.hold_reason, "next_entry_not_satisfied")
        escalation = decision.escalations[0]
        self.assertEqual(escalation.kind, EscalationKind.BLOCKED_TRANSITION)
        failed_metrics = [item["metric"] for item in escalation.details["failed"]]
        self.assertEqual(failed_metrics, ["main_team_avg_level"])

    def test_abort_triggers_escalation_and_holds(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="open_lv5")
        decision = engine.evaluate(
            {
                "battle_loss_rate": 0.4,
                "consecutive_defeats": 0,
                "highest_land_level_cleared": 4,
            }
        )
        self.assertEqual(decision.hold_reason, "abort_triggered")
        escalation = decision.escalations[0]
        self.assertEqual(escalation.kind, EscalationKind.ABORT_TRIGGERED)
        self.assertEqual(escalation.route, EscalationRoute.LLM_PLANNER)
        triggered_metrics = [item["metric"] for item in escalation.details["triggered"]]
        self.assertEqual(triggered_metrics, ["battle_loss_rate"])

    def test_abort_unknown_metrics_escalate_without_triggering(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="open_lv5")
        decision = engine.evaluate({"highest_land_level_cleared": 4})
        self.assertIsNone(decision.hold_reason)
        self.assertFalse(decision.transitioned)
        escalation = decision.escalations[0]
        self.assertEqual(escalation.kind, EscalationKind.UNKNOWN_METRICS)
        self.assertEqual(escalation.details["checked"], "abort_when")
        self.assertIn("battle_loss_rate", escalation.details["missing_metrics"])

    def test_abort_unknown_metrics_block_transition(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="open_lv5")
        decision = engine.evaluate({"highest_land_level_cleared": 5})
        self.assertFalse(decision.transitioned)
        self.assertFalse(decision.completed)
        self.assertEqual(decision.hold_reason, "abort_metrics_unknown")
        kinds = [escalation.kind for escalation in decision.escalations]
        self.assertIn(EscalationKind.UNKNOWN_METRICS, kinds)

    def test_start_at_human_gate_phase_holds_until_confirmed(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="er_tuo_yi")
        decision = engine.evaluate({"er_tuo_yi_done": False})
        self.assertEqual(decision.hold_reason, "human_gate_pending")
        self.assertEqual(decision.human_gate_pending, "er_tuo_yi")
        self.assertEqual(decision.selector_hints, {})
        self.assertEqual(decision.escalations[0].kind, EscalationKind.HUMAN_GATE)
        self.assertEqual(decision.escalations[0].route, EscalationRoute.HUMAN)

        engine.confirm_human_gate("er_tuo_yi")
        decision = engine.evaluate({"er_tuo_yi_done": False})
        self.assertIsNone(decision.hold_reason)

    def test_override_to_human_gate_phase_holds_until_confirmed(self) -> None:
        engine = RunbookEngine(_runbook())
        engine.override_phase("er_tuo_yi")
        decision = engine.evaluate({"er_tuo_yi_done": True})
        self.assertEqual(decision.hold_reason, "human_gate_pending")
        self.assertFalse(decision.transitioned)
        self.assertEqual(decision.selector_hints, {})

    def test_completes_after_final_phase(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="open_lv5")
        decision = engine.evaluate(
            {
                "battle_loss_rate": 0.1,
                "consecutive_defeats": 0,
                "highest_land_level_cleared": 5,
            }
        )
        self.assertTrue(decision.completed)
        self.assertTrue(engine.completed)

        decision = engine.evaluate({})
        self.assertTrue(decision.completed)
        self.assertEqual(decision.hold_reason, "runbook_completed")

    def test_override_phase_resets_cursor(self) -> None:
        engine = RunbookEngine(_runbook(), start_phase_id="open_lv5")
        engine.override_phase("clear_lv1_2")
        self.assertEqual(engine.current_phase.phase_id, "clear_lv1_2")


if __name__ == "__main__":
    unittest.main()
