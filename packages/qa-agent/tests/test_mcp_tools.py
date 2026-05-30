from pathlib import Path
import unittest

from qa_agent.mcp_server.advisor_tools import AdvisorReplayTools
from qa_agent.mcp_server.tooling import KnowledgeToolHandler
from qa_agent.service.query_service import QueryService


class McpToolTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        project_root = Path(__file__).resolve().parents[1]
        source_paths = sorted((project_root / "knowledge_sources").glob("*.yaml"))
        cls.handler = KnowledgeToolHandler(QueryService.from_source_paths(source_paths))

    def test_tool_definitions_are_stable(self) -> None:
        definitions = self.handler.tool_definitions()
        self.assertEqual(
            [item["name"] for item in definitions],
            [
                "lookup_topic",
                "answer_rule_question",
                "resolve_term",
                "advisor_golden_replay_status",
                "advisor_fixture_eval",
            ],
        )

    def test_lookup_topic_tool_returns_structured_content(self) -> None:
        result = self.handler.call_tool("lookup_topic", {"topic": "建筑升级"})
        self.assertFalse(result["isError"])
        self.assertIn("structuredContent", result)
        self.assertEqual(result["structuredContent"]["coverage"], "exact")
        self.assertEqual(result["structuredContent"]["evidence"][0]["entry_id"], "building-upgrade")

    def test_answer_rule_question_tool_reports_not_found(self) -> None:
        result = self.handler.call_tool("answer_rule_question", {"question": "赛季秘闻是什么？"})
        self.assertEqual(result["structuredContent"]["coverage"], "not_found")
        self.assertEqual(result["structuredContent"]["evidence"], [])

    def test_resolve_term_tool_returns_alias_mapping(self) -> None:
        result = self.handler.call_tool("resolve_term", {"term": "打地"})
        payload = result["structuredContent"]
        self.assertEqual(payload["coverage"], "exact")
        self.assertEqual(payload["evidence"][0]["topic"], "攻占地块")

    def test_advisor_golden_replay_status_reports_expectation_failures(self) -> None:
        result = self.handler.call_tool("advisor_golden_replay_status", {})
        payload = result["structuredContent"]
        self.assertFalse(result["isError"])
        self.assertEqual(payload["status"], "attention")
        closure_gate = payload["architecture_iteration_closure_gate"]
        self.assertFalse(closure_gate["ready"])
        self.assertEqual(closure_gate["status"], "attention")
        self.assertIn("low_risk_terminal_dispatch_ready", closure_gate["blocking_codes"])
        self.assertNotIn("golden_replay_checked", closure_gate["blocking_codes"])
        self.assertNotIn("pr6_verifier_specs_complete", closure_gate["blocking_codes"])
        self.assertTrue(all(item["exists"] for item in closure_gate["source_docs"]))
        self.assertEqual(
            [item["path"] for item in closure_gate["source_docs"]],
            [
                "docs/sanmou-architecture-design.md",
                "docs/sanmou-monorepo-architecture-iteration-path.md",
            ],
        )
        low_risk_requirement = next(
            item
            for item in closure_gate["requirements"]
            if item["code"] == "low_risk_terminal_dispatch_ready"
        )
        self.assertEqual(
            low_risk_requirement["evidence"]["blocking_actions"],
            {
                "claim_chapter_reward": ["missing_terminal_dispatch"],
                "recruit_soldiers": ["missing_terminal_dispatch"],
                "upgrade_building": ["missing_terminal_dispatch"],
            },
        )
        self.assertEqual(
            [item["code"] for item in payload["attention_reasons"]],
            ["low_risk_terminal_dispatch_missing"],
        )
        self.assertEqual(payload["fixture_count"], 16)
        self.assertEqual(payload["expectation_count"], 16)
        self.assertEqual(payload["expectation_version"], 2)
        self.assertEqual(payload["pr5_fixture_count"], 6)
        self.assertEqual(payload["pr5_page_coverage"]["missing"], [])
        self.assertEqual(
            set(payload["pr5_page_coverage"]["covered"]),
            {"home", "city", "chapter", "recruit", "building_upgrade", "team"},
        )
        self.assertEqual(payload["pr5_locked_fields"]["action"], 6)
        self.assertEqual(payload["pr5_locked_fields"]["report_evidence"], 6)
        self.assertEqual(payload["pr5_locked_fields"]["report_confidence"], 6)
        self.assertEqual(payload["pr5_locked_fields"]["dispatch_gate"], 3)
        self.assertEqual(payload["pr5_locked_fields"]["runtime_dispatch_gate"], 3)
        self.assertEqual(payload["pr5_locked_fields"]["terminal_dispatch_gate"], 3)
        locked = payload["pr5_locked_field_coverage"]
        self.assertTrue(locked["checked"])
        self.assertEqual(locked["missing"], [])
        self.assertEqual(locked["fields"]["expected_action_type"]["covered_count"], 6)
        self.assertEqual(locked["fields"]["required_report_evidence"]["covered_count"], 6)
        self.assertEqual(locked["fields"]["required_action_evidence"]["covered_count"], 5)
        self.assertEqual(locked["fields"]["expected_report_confidence"]["covered_count"], 6)
        self.assertEqual(locked["fields"]["expected_action_confidence"]["covered_count"], 6)
        self.assertEqual(locked["fields"]["expected_dispatch_status"]["covered_count"], 3)
        self.assertEqual(locked["fields"]["runtime_dispatch_gate"]["covered_count"], 3)
        self.assertEqual(locked["fields"]["expected_dispatch_terminal_for_verifier"]["covered_count"], 3)
        self.assertEqual(payload["pr6_verifier_coverage"]["missing"], [])
        self.assertEqual(
            set(payload["pr6_verifier_coverage"]["covered"]),
            {"claim_chapter_reward", "recruit_soldiers", "upgrade_building"},
        )
        self.assertEqual(payload["pr5_dispatch_gate_coverage"]["required_count"], 3)
        self.assertEqual(payload["pr5_dispatch_gate_coverage"]["matched_count"], 3)
        self.assertEqual(payload["pr5_dispatch_gate_coverage"]["failures"], [])
        self.assertEqual(payload["pr12_runtime_dispatch_coverage"]["required_count"], 3)
        self.assertEqual(payload["pr12_runtime_dispatch_coverage"]["matched_count"], 3)
        self.assertEqual(payload["pr12_runtime_dispatch_coverage"]["failures"], [])
        self.assertEqual(payload["pr15_terminal_dispatch_gate_coverage"]["required_count"], 3)
        self.assertEqual(payload["pr15_terminal_dispatch_gate_coverage"]["matched_count"], 3)
        self.assertEqual(payload["pr15_terminal_dispatch_gate_coverage"]["failures"], [])
        readiness = payload["low_risk_verifier_readiness"]
        self.assertTrue(readiness["checked"])
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["ready_actions"], [])
        self.assertEqual(readiness["verifier_spec_missing"], [])
        self.assertEqual(
            set(readiness["terminal_dispatch_missing"]),
            {"claim_chapter_reward", "recruit_soldiers", "upgrade_building"},
        )
        self.assertEqual(
            readiness["blocking_actions"],
            {
                "claim_chapter_reward": ["missing_terminal_dispatch"],
                "recruit_soldiers": ["missing_terminal_dispatch"],
                "upgrade_building": ["missing_terminal_dispatch"],
            },
        )
        self.assertEqual(
            [item["code"] for item in readiness["next_fixture_requirements"]],
            [
                "chapter_claim_button_terminal_fixture",
                "recruit_button_terminal_fixture",
                "upgrade_confirm_button_terminal_fixture",
            ],
        )
        self.assertEqual(
            readiness["next_fixture_requirements"][0]["expected_runtime_dispatch"],
            {
                "status": "ok",
                "target_key": "chapter_claim_button",
                "terminal_for_verifier": True,
            },
        )
        terminal = payload["pr5_low_risk_terminal_dispatch_coverage"]
        self.assertTrue(terminal["checked"])
        self.assertEqual(terminal["covered"], [])
        self.assertEqual(
            set(terminal["missing"]),
            {"claim_chapter_reward", "recruit_soldiers", "upgrade_building"},
        )
        self.assertEqual(len(terminal["observed"]), 3)
        upgrade_observation = next(
            item for item in terminal["observed"] if item["action_type"] == "upgrade_building"
        )
        self.assertEqual(upgrade_observation["status"], "ok")
        self.assertEqual(upgrade_observation["flow_step"], "open_upgrade_dialog")
        self.assertFalse(upgrade_observation["terminal_for_verifier"])
        self.assertEqual(readiness["observed_terminal_dispatch"], terminal["observed"])
        self.assertEqual(
            payload["attention_reasons"][0]["blocking_actions"],
            readiness["blocking_actions"],
        )
        self.assertEqual(payload["failures"], [])

    def test_advisor_golden_replay_status_without_fixture_results_is_attention(self) -> None:
        result = self.handler.call_tool(
            "advisor_golden_replay_status",
            {"include_fixture_results": False},
        )
        payload = result["structuredContent"]

        self.assertFalse(result["isError"])
        self.assertEqual(payload["status"], "attention")
        self.assertFalse(payload["fixture_replay_checked"])
        self.assertEqual(payload["results"], [])
        self.assertEqual(payload["failures"], [])
        self.assertEqual(
            [item["code"] for item in payload["attention_reasons"]],
            ["fixture_replay_not_run"],
        )
        closure_gate = payload["architecture_iteration_closure_gate"]
        self.assertFalse(closure_gate["ready"])
        self.assertEqual(closure_gate["status"], "attention")
        self.assertIn("golden_replay_checked", closure_gate["blocking_codes"])
        self.assertIn("pr6_verifier_specs_complete", closure_gate["blocking_codes"])
        self.assertIn("low_risk_terminal_dispatch_ready", closure_gate["blocking_codes"])
        self.assertFalse(payload["pr6_verifier_coverage"]["checked"])
        self.assertFalse(payload["pr5_dispatch_gate_coverage"]["checked"])
        self.assertFalse(payload["pr12_runtime_dispatch_coverage"]["checked"])
        self.assertFalse(payload["pr15_terminal_dispatch_gate_coverage"]["checked"])
        self.assertFalse(payload["pr5_low_risk_terminal_dispatch_coverage"]["checked"])
        readiness = payload["low_risk_verifier_readiness"]
        self.assertFalse(readiness["checked"])
        self.assertFalse(readiness["ready"])
        self.assertEqual(readiness["blocking_actions"], {})

    def test_advisor_fixture_eval_returns_selected_action(self) -> None:
        result = self.handler.call_tool(
            "advisor_fixture_eval",
            {"fixture": "chapter_claimable_state.json"},
        )
        payload = result["structuredContent"]
        self.assertFalse(result["isError"])
        self.assertTrue(payload["matched"])
        self.assertEqual(payload["expected_action_type"], "claim_chapter_reward")
        self.assertEqual(payload["actual_action_type"], "claim_chapter_reward")
        self.assertEqual(payload["selected_action"]["action_type"], "claim_chapter_reward")

    def test_advisor_fixture_eval_includes_pr5_metadata(self) -> None:
        result = self.handler.call_tool(
            "advisor_fixture_eval",
            {"fixture": "pr5_team_panel_state.json"},
        )
        payload = result["structuredContent"]
        self.assertFalse(result["isError"])
        self.assertTrue(payload["matched"])
        self.assertEqual(payload["page"], "team")
        self.assertEqual(payload["actual_action_type"], "inspect_team_readiness")
        self.assertEqual(payload["expected_action_confidence"], 0.79)
        self.assertIn("team_panel_20260529.jpg", payload["screenshot"])
        self.assertIn("main_lineup.team_readiness", payload["required_action_evidence"])
        self.assertFalse(payload["low_risk_readiness"]["checked"])
        self.assertFalse(payload["low_risk_readiness"]["low_risk"])

    def test_advisor_fixture_eval_includes_pr6_verifier_spec(self) -> None:
        expected = {
            "pr5_chapter_main_task_state.json": (
                "claim_chapter_reward",
                "all",
                10.0,
                ["progress.chapter_claimable"],
            ),
            "pr5_recruit_guard_camp_state.json": (
                "recruit_soldiers",
                "any",
                30.0,
                ["teams.0.soldiers", "teams.0.recruit_finish_time", "economy.reserve_troops"],
            ),
            "pr5_building_upgrade_state.json": (
                "upgrade_building",
                "any",
                20.0,
                ["city.buildings.0.level", "economy.resources.wood"],
            ),
        }

        for fixture, (action_type, match_policy, timeout, delta_paths) in expected.items():
            with self.subTest(fixture=fixture):
                result = self.handler.call_tool("advisor_fixture_eval", {"fixture": fixture})
                payload = result["structuredContent"]
                spec = payload["verifier_spec"]

                self.assertFalse(result["isError"])
                self.assertTrue(payload["matched"])
                self.assertEqual(payload["verifier_gate"]["decision"], "allow")
                self.assertEqual(spec["action_type"], action_type)
                self.assertEqual(spec["match_policy"], match_policy)
                self.assertEqual(spec["timeout_seconds"], timeout)
                self.assertEqual(
                    [delta["path"] for delta in spec["expected_deltas"]],
                    delta_paths,
                )

    def test_advisor_fixture_eval_includes_pr5_dispatch_gate(self) -> None:
        expected = {
            "pr5_chapter_main_task_state.json": {
                "status": "blocked",
                "blocked_by": "semantic_target_gate",
                "target_key": None,
            },
            "pr5_recruit_guard_camp_state.json": {
                "status": "blocked",
                "blocked_by": "semantic_target_gate",
                "target_key": None,
            },
            "pr5_building_upgrade_state.json": {
                "status": "ok",
                "blocked_by": None,
                "target_key": "building_upgrade_button",
            },
        }

        for fixture, dispatch_expected in expected.items():
            with self.subTest(fixture=fixture):
                result = self.handler.call_tool("advisor_fixture_eval", {"fixture": fixture})
                payload = result["structuredContent"]
                dispatch_gate = payload["dispatch_gate"]
                runtime_dispatch_gate = payload["runtime_dispatch_gate"]
                terminal_dispatch_gate = payload["terminal_dispatch_gate"]
                readiness = payload["low_risk_readiness"]

                self.assertFalse(result["isError"])
                self.assertTrue(readiness["checked"])
                self.assertTrue(readiness["low_risk"])
                self.assertFalse(readiness["ready_for_post_action_verifier"])
                self.assertTrue(readiness["verifier_spec_ready"])
                self.assertEqual(len(readiness["next_fixture_requirements"]), 1)
                self.assertTrue(dispatch_gate["checked"])
                self.assertTrue(dispatch_gate["matched"])
                self.assertEqual(dispatch_gate["expected"], dispatch_expected)
                self.assertEqual(dispatch_gate["actual"], dispatch_expected)
                self.assertTrue(runtime_dispatch_gate["checked"])
                self.assertTrue(runtime_dispatch_gate["matched"])
                self.assertEqual(runtime_dispatch_gate["expected"]["status"], dispatch_expected["status"])
                self.assertEqual(runtime_dispatch_gate["expected"]["blocked_by"], dispatch_expected["blocked_by"])
                self.assertEqual(runtime_dispatch_gate["expected"]["target_key"], dispatch_expected["target_key"])
                self.assertEqual(runtime_dispatch_gate["actual"]["status"], dispatch_expected["status"])
                self.assertEqual(runtime_dispatch_gate["actual"]["blocked_by"], dispatch_expected["blocked_by"])
                self.assertEqual(runtime_dispatch_gate["actual"]["target_key"], dispatch_expected["target_key"])
                self.assertEqual(
                    payload["runtime_dispatch"]["summary"]["semantic_target_gate"]["decision"],
                    runtime_dispatch_gate["expected"]["semantic_gate_decision"],
                )
                self.assertTrue(terminal_dispatch_gate["checked"])
                self.assertTrue(terminal_dispatch_gate["matched"])
                self.assertEqual(
                    terminal_dispatch_gate["expected"],
                    {"terminal_for_verifier": False},
                )
                self.assertFalse(terminal_dispatch_gate["actual"]["terminal_for_verifier"])
                self.assertFalse(readiness["terminal_dispatch_ready"])

                if fixture == "pr5_building_upgrade_state.json":
                    self.assertTrue(readiness["semantic_dispatch_ready"])
                    self.assertTrue(readiness["runtime_dispatch_ready"])
                    self.assertEqual(readiness["blockers"], ["missing_terminal_dispatch"])
                    self.assertEqual(readiness["observed"]["flow_step"], "open_upgrade_dialog")
                    self.assertEqual(
                        readiness["next_fixture_requirements"][0]["code"],
                        "upgrade_confirm_button_terminal_fixture",
                    )
                    self.assertEqual(
                        readiness["next_fixture_requirements"][0]["expected_runtime_dispatch"]["target_key"],
                        "upgrade_confirm_button",
                    )
                else:
                    self.assertFalse(readiness["semantic_dispatch_ready"])
                    self.assertFalse(readiness["runtime_dispatch_ready"])
                    self.assertEqual(
                        readiness["blockers"],
                        [
                            "semantic_target_gate_blocked",
                            "dispatch_not_ok",
                            "missing_terminal_dispatch",
                        ],
                    )
                    self.assertEqual(readiness["observed"]["blocked_by"], "semantic_target_gate")
                    self.assertIn(
                        readiness["next_fixture_requirements"][0]["code"],
                        {
                            "chapter_claim_button_terminal_fixture",
                            "recruit_button_terminal_fixture",
                        },
                    )

    def test_pr5_locked_field_coverage_reports_missing_fields(self) -> None:
        coverage = AdvisorReplayTools._pr5_locked_field_coverage(
            {
                "fixture.json": {
                    "page": "chapter",
                    "expected_action_type": "claim_chapter_reward",
                    "expected_report_confidence": 0.91,
                    "expected_action_confidence": 0.87,
                    "required_report_evidence": [],
                }
            }
        )

        self.assertIn(
            {"fixture": "fixture.json", "field": "required_report_evidence"},
            coverage["missing"],
        )
        self.assertIn(
            {"fixture": "fixture.json", "field": "required_action_evidence"},
            coverage["missing"],
        )
        self.assertIn(
            {"fixture": "fixture.json", "field": "expected_dispatch_status"},
            coverage["missing"],
        )
        self.assertIn(
            {"fixture": "fixture.json", "field": "runtime_dispatch_gate"},
            coverage["missing"],
        )
        self.assertIn(
            {"fixture": "fixture.json", "field": "expected_dispatch_terminal_for_verifier"},
            coverage["missing"],
        )


if __name__ == "__main__":
    unittest.main()
