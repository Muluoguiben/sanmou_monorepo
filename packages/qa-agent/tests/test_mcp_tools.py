from pathlib import Path
import unittest

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
        self.assertEqual(payload["fixture_count"], 10)
        self.assertEqual(payload["expectation_count"], 10)
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


if __name__ == "__main__":
    unittest.main()
