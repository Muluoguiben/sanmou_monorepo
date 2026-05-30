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
        self.assertEqual(payload["status"], "ok")
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
        self.assertEqual(payload["failures"], [])

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

                self.assertFalse(result["isError"])
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


if __name__ == "__main__":
    unittest.main()
