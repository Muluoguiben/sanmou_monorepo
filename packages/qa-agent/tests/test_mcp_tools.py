import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from qa_agent.mcp_server.advisor_tools import AdvisorReplayTools
from qa_agent.mcp_server.tooling import KnowledgeToolHandler
from qa_agent.service.query_service import QueryService


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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
                "advisor_terminal_source_evidence_eval",
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
        self.assertNotIn("low_risk_terminal_dispatch_ready", closure_gate["blocking_codes"])
        self.assertIn("low_risk_terminal_real_source_reviewed", closure_gate["blocking_codes"])
        self.assertNotIn("desktop_evidence_degraded_display_ready", closure_gate["blocking_codes"])
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
        self.assertEqual(low_risk_requirement["evidence"]["blocking_actions"], {})
        source_requirement = next(
            item
            for item in closure_gate["requirements"]
            if item["code"] == "low_risk_terminal_real_source_reviewed"
        )
        self.assertEqual(
            set(source_requirement["evidence"]["missing_real_terminal_sources"]),
            {"claim_chapter_reward", "recruit_soldiers", "upgrade_building"},
        )
        self.assertEqual(
            [item["code"] for item in payload["attention_reasons"]],
            ["low_risk_terminal_source_review_missing"],
        )
        self.assertIn(
            "claim_chapter_reward",
            payload["attention_reasons"][0]["blocking_actions"],
        )
        desktop_gate = payload["desktop_evidence_display_gate"]
        self.assertTrue(desktop_gate["checked"])
        self.assertTrue(desktop_gate["ready"])
        self.assertTrue(all(item["exists"] for item in desktop_gate["files"].values()))
        self.assertEqual(desktop_gate["missing"], [])
        desktop_requirement = next(
            item
            for item in closure_gate["requirements"]
            if item["code"] == "desktop_evidence_degraded_display_ready"
        )
        self.assertTrue(desktop_requirement["ready"])
        self.assertEqual(desktop_requirement["evidence"]["missing"], [])
        self.assertEqual(payload["fixture_count"], 19)
        self.assertEqual(payload["expectation_count"], 19)
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
        self.assertEqual(payload["pr5_dispatch_gate_coverage"]["required_count"], 6)
        self.assertEqual(payload["pr5_dispatch_gate_coverage"]["matched_count"], 6)
        self.assertEqual(payload["pr5_dispatch_gate_coverage"]["failures"], [])
        self.assertEqual(payload["pr12_runtime_dispatch_coverage"]["required_count"], 6)
        self.assertEqual(payload["pr12_runtime_dispatch_coverage"]["matched_count"], 6)
        self.assertEqual(payload["pr12_runtime_dispatch_coverage"]["failures"], [])
        self.assertEqual(payload["pr15_terminal_dispatch_gate_coverage"]["required_count"], 6)
        self.assertEqual(payload["pr15_terminal_dispatch_gate_coverage"]["matched_count"], 6)
        self.assertEqual(payload["pr15_terminal_dispatch_gate_coverage"]["failures"], [])
        readiness = payload["low_risk_verifier_readiness"]
        self.assertTrue(readiness["checked"])
        self.assertTrue(readiness["ready"])
        self.assertEqual(
            readiness["ready_actions"],
            ["claim_chapter_reward", "recruit_soldiers", "upgrade_building"],
        )
        self.assertEqual(readiness["verifier_spec_missing"], [])
        self.assertEqual(readiness["terminal_dispatch_missing"], [])
        self.assertEqual(readiness["blocking_actions"], {})
        self.assertEqual(readiness["next_fixture_requirements"], [])
        terminal = payload["pr5_low_risk_terminal_dispatch_coverage"]
        self.assertTrue(terminal["checked"])
        self.assertEqual(
            terminal["covered"],
            ["claim_chapter_reward", "recruit_soldiers", "upgrade_building"],
        )
        self.assertEqual(
            terminal["covered_fixtures"],
            {
                "claim_chapter_reward": "pr21_chapter_claim_terminal_state.json",
                "recruit_soldiers": "pr22_recruit_terminal_state.json",
                "upgrade_building": "pr20_upgrade_confirm_terminal_state.json",
            },
        )
        self.assertEqual(terminal["missing"], [])
        self.assertEqual(len(terminal["observed"]), 6)
        terminal_claim = next(
            item
            for item in terminal["observed"]
            if item["fixture"] == "pr21_chapter_claim_terminal_state.json"
        )
        self.assertEqual(terminal_claim["target_key"], "chapter_claim_button")
        self.assertTrue(terminal_claim["terminal_for_verifier"])
        terminal_recruit = next(
            item
            for item in terminal["observed"]
            if item["fixture"] == "pr22_recruit_terminal_state.json"
        )
        self.assertEqual(terminal_recruit["target_key"], "recruit_button")
        self.assertTrue(terminal_recruit["terminal_for_verifier"])
        upgrade_observation = next(
            item for item in terminal["observed"] if item["fixture"] == "pr5_building_upgrade_state.json"
        )
        self.assertEqual(upgrade_observation["status"], "ok")
        self.assertEqual(upgrade_observation["flow_step"], "open_upgrade_dialog")
        self.assertFalse(upgrade_observation["terminal_for_verifier"])
        terminal_upgrade = next(
            item
            for item in terminal["observed"]
            if item["fixture"] == "pr20_upgrade_confirm_terminal_state.json"
        )
        self.assertEqual(terminal_upgrade["status"], "ok")
        self.assertEqual(terminal_upgrade["target_key"], "upgrade_confirm_button")
        self.assertEqual(terminal_upgrade["flow_step"], "confirm_upgrade")
        self.assertTrue(terminal_upgrade["terminal_for_verifier"])
        self.assertEqual(readiness["observed_terminal_dispatch"], terminal["observed"])
        source_review = payload["low_risk_terminal_source_review"]
        self.assertTrue(source_review["checked"])
        self.assertFalse(source_review["ready"])
        self.assertEqual(source_review["accepted_actions"], [])
        self.assertEqual(
            set(source_review["missing_real_terminal_sources"]),
            {"claim_chapter_reward", "recruit_soldiers", "upgrade_building"},
        )
        source_blocking = source_review["blocking_actions"]
        self.assertEqual(
            set(source_blocking),
            {"claim_chapter_reward", "recruit_soldiers", "upgrade_building"},
        )
        self.assertIn(
            "missing_real_terminal_source",
            source_blocking["claim_chapter_reward"]["blockers"],
        )
        self.assertIn(
            "no_terminal_real_candidate",
            source_blocking["claim_chapter_reward"]["blockers"],
        )
        self.assertIn(
            "no_valid_terminal_source_evidence",
            source_blocking["claim_chapter_reward"]["blockers"],
        )
        self.assertEqual(
            source_blocking["claim_chapter_reward"]["required_runtime_dispatch"][
                "target_key"
            ],
            "chapter_claim_button",
        )
        self.assertEqual(
            source_blocking["claim_chapter_reward"]["required_post_action_delta"],
            ["progress.chapter_claimable=false"],
        )
        self.assertEqual(
            [item["code"] for item in source_review["next_source_requirements"]],
            [
                "chapter_claim_terminal_real_source",
                "recruit_terminal_real_source",
                "upgrade_confirm_terminal_real_source",
            ],
        )
        self.assertEqual(
            source_review["next_source_requirements"][0]["accepted_source_kinds"],
            ["pr5_real_screenshot_fixture", "live_trace_fixture"],
        )
        evidence_templates = source_review["next_source_requirements"][0][
            "terminal_source_evidence_templates"
        ]
        self.assertEqual(
            evidence_templates["live_trace_fixture"]["semantic_target"],
            "progress.chapter_claim_button",
        )
        self.assertEqual(
            evidence_templates["live_trace_fixture"]["verification_record"]["status"],
            "verified",
        )
        self.assertEqual(
            evidence_templates["pr5_real_screenshot_fixture"]["runtime_dispatch"]["target_key"],
            "chapter_claim_button",
        )
        self.assertEqual(
            source_review["next_source_requirements"][0]["required_runtime_dispatch"],
            {
                "status": "ok",
                "target_key": "chapter_claim_button",
                "terminal_for_verifier": True,
            },
        )
        self.assertEqual(
            {item["source_kind"] for item in source_review["observed"]},
            {"runtime_state_fixture"},
        )
        self.assertTrue(
            all(not item["source_evidence_present"] for item in source_review["observed"])
        )
        self.assertTrue(
            all("terminal_source_evidence" in item["missing_evidence"] for item in source_review["observed"])
        )
        self.assertTrue(
            all("accepted_source_kind" in item["missing_evidence"] for item in source_review["observed"])
        )
        real_candidates = source_review["real_source_candidates"]
        self.assertEqual(
            [item["fixture"] for item in real_candidates],
            [
                "pr5_chapter_main_task_state.json",
                "pr5_recruit_guard_camp_state.json",
                "pr5_building_upgrade_state.json",
            ],
        )
        self.assertTrue(all(item["screenshot_exists"] for item in real_candidates))
        self.assertTrue(all(not item["closure_eligible"] for item in real_candidates))
        self.assertTrue(
            all("runtime_dispatch_not_terminal" in item["disqualifiers"] for item in real_candidates)
        )
        self.assertTrue(
            all("terminal_source_evidence_invalid" in item["disqualifiers"] for item in real_candidates)
        )
        candidate_by_fixture = {item["fixture"]: item for item in real_candidates}
        self.assertEqual(
            candidate_by_fixture["pr5_building_upgrade_state.json"]["runtime_dispatch"]["target_key"],
            "building_upgrade_button",
        )
        self.assertFalse(
            candidate_by_fixture["pr5_building_upgrade_state.json"]["runtime_dispatch"]["terminal_for_verifier"]
        )
        self.assertEqual(
            candidate_by_fixture["pr5_chapter_main_task_state.json"]["runtime_dispatch"]["status"],
            "blocked",
        )
        self.assertEqual(
            candidate_by_fixture["pr5_recruit_guard_camp_state.json"]["runtime_dispatch"]["status"],
            "blocked",
        )
        capture_plan = source_review["capture_plan"]
        self.assertTrue(capture_plan["checked"])
        self.assertFalse(capture_plan["ready"])
        self.assertTrue(capture_plan["requires_operator_confirmation_for_final_action"])
        self.assertEqual(capture_plan["blocked_until"], "terminal_source_evidence_valid")
        self.assertEqual(
            [item["action_type"] for item in capture_plan["actions"]],
            ["claim_chapter_reward", "recruit_soldiers", "upgrade_building"],
        )
        self.assertEqual(
            capture_plan["actions"][0]["code"],
            "chapter_claim_terminal_real_source_capture_plan",
        )
        self.assertEqual(
            capture_plan["actions"][0]["required_runtime_dispatch"],
            {
                "status": "ok",
                "target_key": "chapter_claim_button",
                "terminal_for_verifier": True,
            },
        )
        self.assertEqual(
            capture_plan["actions"][0]["required_post_action_delta"],
            ["progress.chapter_claimable=false"],
        )
        self.assertIn(
            "runtime_dispatch_not_terminal",
            capture_plan["actions"][0]["current_candidate_disqualifiers"],
        )
        self.assertTrue(capture_plan["actions"][0]["pre_final_capture"]["required"])
        self.assertFalse(
            capture_plan["actions"][0]["pre_final_capture"]["closure_eligible_without_post_action_delta"]
        )
        self.assertTrue(capture_plan["actions"][0]["final_action_policy"]["mutates_game_state"])
        self.assertTrue(
            capture_plan["actions"][0]["final_action_policy"]["requires_operator_confirmation"]
        )
        self.assertIn("post_action_delta", capture_plan["actions"][0]["terminal_source_evidence_fields"])
        self.assertIn("reviewed_by", capture_plan["actions"][0]["terminal_source_evidence_fields"])
        self.assertIn("reviewed_at", capture_plan["actions"][0]["terminal_source_evidence_fields"])
        self.assertIn("screenshot_sha256", capture_plan["actions"][0]["terminal_source_evidence_fields"])
        self.assertIn("post_action_delta_evidence", capture_plan["actions"][0]["terminal_source_evidence_fields"])
        self.assertIn("verification_record", capture_plan["actions"][0]["live_trace_extra_fields"])
        self.assertIn("trace_sha256", capture_plan["actions"][0]["live_trace_extra_fields"])
        self.assertIn("operator_confirmation", capture_plan["actions"][0]["live_trace_extra_fields"])
        self.assertIn(
            "verification.post_action_verifier.status=verified",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        self.assertIn(
            "trace.screenshot.path matches terminal_source_evidence.screenshot",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        self.assertIn(
            "verification.post_action_verifier action/delta matches required_post_action_delta",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        self.assertIn(
            "operator_confirmation.confirmed=true",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        self.assertIn(
            "operator_confirmation.trace_id/trace_record_index matches trace record",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        expectation_template = capture_plan["actions"][0][
            "advisor_fixture_expectation_patch_template"
        ]["<claim_chapter_reward_terminal_fixture>.json"]
        self.assertEqual(expectation_template["expected_action_type"], "claim_chapter_reward")
        self.assertEqual(expectation_template["expected_dispatch_target_key"], "chapter_claim_button")
        self.assertTrue(expectation_template["expected_dispatch_terminal_for_verifier"])
        self.assertEqual(
            expectation_template["terminal_source_evidence"]["source_kind"],
            "live_trace_fixture",
        )
        self.assertEqual(
            expectation_template["terminal_source_evidence"]["reviewed_by"],
            "<reviewer-id>",
        )
        self.assertEqual(
            expectation_template["terminal_source_evidence"]["screenshot_sha256"],
            "<sha256-of-screenshot>",
        )
        self.assertEqual(
            expectation_template["terminal_source_evidence"]["trace_sha256"],
            "<sha256-of-trace>",
        )
        self.assertEqual(
            expectation_template["terminal_source_evidence"]["post_action_delta_evidence"]["source"],
            "verification_record",
        )
        self.assertEqual(
            expectation_template["terminal_source_evidence"]["verification_record"]["checked"],
            ["progress.chapter_claimable"],
        )
        self.assertTrue(
            expectation_template["terminal_source_evidence"]["operator_confirmation"]["confirmed"]
        )
        self.assertEqual(
            expectation_template["terminal_source_evidence"]["operator_confirmation"][
                "trace_id"
            ],
            "<trace-id-from-matching-record>",
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
        self.assertIn("low_risk_terminal_real_source_reviewed", closure_gate["blocking_codes"])
        self.assertNotIn("desktop_evidence_degraded_display_ready", closure_gate["blocking_codes"])
        self.assertFalse(payload["pr6_verifier_coverage"]["checked"])
        self.assertFalse(payload["pr5_dispatch_gate_coverage"]["checked"])
        self.assertFalse(payload["pr12_runtime_dispatch_coverage"]["checked"])
        self.assertFalse(payload["pr15_terminal_dispatch_gate_coverage"]["checked"])
        self.assertFalse(payload["pr5_low_risk_terminal_dispatch_coverage"]["checked"])
        self.assertEqual(payload["low_risk_terminal_source_review"]["real_source_candidates"], [])
        self.assertEqual(
            payload["low_risk_terminal_source_review"]["capture_plan"],
            {
                "checked": False,
                "ready": False,
                "blocked_until": "golden_replay_checked",
                "requires_operator_confirmation_for_final_action": False,
                "actions": [],
            },
        )
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
            "pr20_upgrade_confirm_terminal_state.json": {
                "status": "ok",
                "blocked_by": None,
                "target_key": "upgrade_confirm_button",
            },
            "pr21_chapter_claim_terminal_state.json": {
                "status": "ok",
                "blocked_by": None,
                "target_key": "chapter_claim_button",
            },
            "pr22_recruit_terminal_state.json": {
                "status": "ok",
                "blocked_by": None,
                "target_key": "recruit_button",
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
                source_review = payload["terminal_source_review"]

                self.assertFalse(result["isError"])
                self.assertTrue(readiness["checked"])
                self.assertTrue(readiness["low_risk"])
                self.assertTrue(readiness["verifier_spec_ready"])
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
                expected_terminal = fixture in {
                    "pr20_upgrade_confirm_terminal_state.json",
                    "pr21_chapter_claim_terminal_state.json",
                    "pr22_recruit_terminal_state.json",
                }
                self.assertEqual(
                    terminal_dispatch_gate["expected"],
                    {"terminal_for_verifier": expected_terminal},
                )
                self.assertEqual(
                    terminal_dispatch_gate["actual"]["terminal_for_verifier"],
                    expected_terminal,
                )
                self.assertEqual(readiness["terminal_dispatch_ready"], expected_terminal)

                if fixture == "pr5_building_upgrade_state.json":
                    self.assertFalse(readiness["ready_for_post_action_verifier"])
                    self.assertEqual(len(readiness["next_fixture_requirements"]), 1)
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
                elif fixture in {
                    "pr20_upgrade_confirm_terminal_state.json",
                    "pr21_chapter_claim_terminal_state.json",
                    "pr22_recruit_terminal_state.json",
                }:
                    self.assertTrue(readiness["semantic_dispatch_ready"])
                    self.assertTrue(readiness["runtime_dispatch_ready"])
                    self.assertTrue(readiness["ready_for_post_action_verifier"])
                    self.assertEqual(readiness["blockers"], [])
                    self.assertEqual(readiness["next_fixture_requirements"], [])
                    self.assertEqual(readiness["observed"]["target_key"], dispatch_expected["target_key"])
                    self.assertTrue(source_review["terminal_dispatch_ready"])
                    self.assertEqual(source_review["source_kind"], "runtime_state_fixture")
                    self.assertFalse(source_review["accepted_for_closure"])
                    self.assertFalse(source_review["source_evidence_present"])
                    self.assertIn("terminal_source_evidence", source_review["missing_evidence"])
                    self.assertIn("accepted_source_kind", source_review["missing_evidence"])
                    self.assertIn("runtime_dispatch", source_review["missing_evidence"])
                    self.assertIn("semantic_target", source_review["missing_evidence"])
                    self.assertEqual(len(source_review["next_source_requirements"]), 1)
                    self.assertEqual(
                        source_review["next_source_requirements"][0]["required_runtime_dispatch"]["target_key"],
                        dispatch_expected["target_key"],
                    )
                else:
                    self.assertFalse(readiness["ready_for_post_action_verifier"])
                    self.assertEqual(len(readiness["next_fixture_requirements"]), 1)
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

    def test_terminal_source_evidence_review_validates_required_semantics(self) -> None:
        tools = AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[1])
        screenshot = "tests/fixtures/screenshots/pc_client/pr5_20260529/chapter_main_task_20260529.jpg"
        valid_expectation = {
            "page": "chapter",
            "terminal_source_evidence": {
                "source_kind": "pr5_real_screenshot_fixture",
                "review_status": "reviewed",
                "reviewed_by": "qa-reviewer",
                "reviewed_at": "2026-05-30T18:20:00+08:00",
                "screenshot": screenshot,
                "screenshot_sha256": _sha256(Path(__file__).resolve().parents[2] / "pioneer-agent" / screenshot),
                "page": "chapter",
                "semantic_target": "progress.chapter_claim_button",
                "runtime_dispatch": {
                    "status": "ok",
                    "target_key": "chapter_claim_button",
                    "terminal_for_verifier": True,
                },
                "post_action_delta": [
                    {"path": "progress.chapter_claimable", "value": False},
                ],
                "post_action_delta_evidence": {
                    "source": "reviewed_before_after_observation",
                    "post_action_delta": [
                        {"path": "progress.chapter_claimable", "value": False},
                    ],
                    "supporting_refs": [
                        "tests/fixtures/screenshots/pc_client/pr5_20260529/chapter_main_task_20260529.jpg",
                        "reviewed-post-action-observation",
                    ],
                },
            },
        }

        review = tools._terminal_source_evidence_review(
            action_type="claim_chapter_reward",
            fixture="pr5_chapter_claim_terminal_state.json",
            expectation=valid_expectation,
        )

        self.assertTrue(review["source_evidence_valid"])
        self.assertEqual(review["missing_evidence"], [])
        self.assertEqual(review["required_page"], "chapter")
        self.assertEqual(review["required_semantic_target"], "progress.chapter_claim_button")
        self.assertEqual(review["required_runtime_dispatch"]["target_key"], "chapter_claim_button")
        self.assertEqual(review["required_post_action_delta"], ["progress.chapter_claimable=false"])
        self.assertTrue(review["post_action_delta_evidence_validation"]["valid"])
        self.assertTrue(review["review_metadata_validation"]["valid"])
        self.assertTrue(review["file_integrity_validation"]["valid"])

        invalid_delta_evidence_expectation = {
            "page": "chapter",
            "terminal_source_evidence": {
                **valid_expectation["terminal_source_evidence"],
                "post_action_delta_evidence": {
                    "source": "reviewed_before_after_observation",
                    "post_action_delta": ["teams.0.soldiers increases"],
                    "supporting_refs": ["reviewed-post-action-observation"],
                },
            },
        }
        invalid_delta_evidence = tools._terminal_source_evidence_review(
            action_type="claim_chapter_reward",
            fixture="pr5_chapter_claim_terminal_state.json",
            expectation=invalid_delta_evidence_expectation,
        )

        self.assertFalse(invalid_delta_evidence["source_evidence_valid"])
        self.assertIn("post_action_delta_evidence", invalid_delta_evidence["missing_evidence"])
        self.assertEqual(
            invalid_delta_evidence["post_action_delta_evidence_validation"]["issues"],
            ["post_action_delta"],
        )

        invalid_review_metadata_expectation = {
            "page": "chapter",
            "terminal_source_evidence": {
                **valid_expectation["terminal_source_evidence"],
                "reviewed_by": "",
                "reviewed_at": "<reviewed-iso8601>",
            },
        }
        invalid_review_metadata = tools._terminal_source_evidence_review(
            action_type="claim_chapter_reward",
            fixture="pr5_chapter_claim_terminal_state.json",
            expectation=invalid_review_metadata_expectation,
        )

        self.assertFalse(invalid_review_metadata["source_evidence_valid"])
        self.assertIn("review_metadata", invalid_review_metadata["missing_evidence"])
        self.assertEqual(
            invalid_review_metadata["review_metadata_validation"]["issues"],
            ["reviewed_at", "reviewed_by"],
        )

        invalid_hash_expectation = {
            "page": "chapter",
            "terminal_source_evidence": {
                **valid_expectation["terminal_source_evidence"],
                "screenshot_sha256": "0" * 64,
            },
        }
        invalid_hash_review = tools._terminal_source_evidence_review(
            action_type="claim_chapter_reward",
            fixture="pr5_chapter_claim_terminal_state.json",
            expectation=invalid_hash_expectation,
        )

        self.assertFalse(invalid_hash_review["source_evidence_valid"])
        self.assertIn("file_integrity", invalid_hash_review["missing_evidence"])
        self.assertEqual(
            invalid_hash_review["file_integrity_validation"]["issues"],
            ["screenshot_sha256_mismatch"],
        )

        invalid_expectation = {
            "page": "chapter",
            "terminal_source_evidence": {
                **valid_expectation["terminal_source_evidence"],
                "page": "recruit",
                "semantic_target": "teams[*].recruit_button",
                "runtime_dispatch": {
                    "status": "ok",
                    "target_key": "recruit_button",
                    "terminal_for_verifier": True,
                },
                "post_action_delta": ["teams.0.soldiers increases"],
            },
        }
        invalid_review = tools._terminal_source_evidence_review(
            action_type="claim_chapter_reward",
            fixture="pr5_chapter_claim_terminal_state.json",
            expectation=invalid_expectation,
        )

        self.assertFalse(invalid_review["source_evidence_valid"])
        self.assertEqual(
            set(invalid_review["missing_evidence"]),
            {"page", "post_action_delta", "runtime_dispatch", "semantic_target"},
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            screenshot_path = temp_root / "claim-terminal.png"
            screenshot_path.write_bytes(b"placeholder")
            trace_path = temp_root / "claim-live-trace.jsonl"
            trace_record = {
                "trace_id": "trace-claim-1",
                "screenshot": {"path": str(screenshot_path)},
                "selected_action": {"action_type": "claim_chapter_reward"},
                "execution": {
                    "status": "ok",
                    "summary": {
                        "target_key": "chapter_claim_button",
                        "terminal_for_verifier": True,
                    },
                },
                "verification": {
                    "post_action_verifier": {
                        "action_type": "claim_chapter_reward",
                        "status": "verified",
                        "checked": ["progress.chapter_claimable"],
                    },
                },
            }
            trace_path.write_text(json.dumps(trace_record, ensure_ascii=False), encoding="utf-8")
            live_expectation = {
                "page": "chapter",
                "terminal_source_evidence": {
                    "source_kind": "live_trace_fixture",
                    "review_status": "reviewed",
                    "reviewed_by": "qa-reviewer",
                    "reviewed_at": "2026-05-30T18:20:00+08:00",
                    "screenshot": str(screenshot_path),
                    "screenshot_sha256": _sha256(screenshot_path),
                    "trace": str(trace_path),
                    "trace_sha256": _sha256(trace_path),
                    "page": "chapter",
                    "semantic_target": "progress.chapter_claim_button",
                    "runtime_dispatch": {
                        "status": "ok",
                        "target_key": "chapter_claim_button",
                        "terminal_for_verifier": True,
                    },
                    "post_action_delta": [
                        {"path": "progress.chapter_claimable", "value": False},
                    ],
                    "post_action_delta_evidence": {
                        "source": "verification_record",
                        "post_action_delta": [
                            {"path": "progress.chapter_claimable", "value": False},
                        ],
                        "supporting_refs": [
                            "terminal_source_evidence.trace",
                            "terminal_source_evidence.verification_record",
                            "operator_confirmation.trace_id",
                        ],
                    },
                    "verification_record": {
                        "action_type": "claim_chapter_reward",
                        "status": "verified",
                        "checked": ["progress.chapter_claimable"],
                    },
                    "operator_confirmation": {
                        "confirmed": True,
                        "action_type": "claim_chapter_reward",
                        "scope": "final_mutating_click",
                        "requires_operator_confirmation": True,
                        "confirmed_at": "2026-05-30T17:45:00+08:00",
                        "trace_id": "trace-claim-1",
                        "trace_record_index": 0,
                        "runtime_dispatch": {
                            "status": "ok",
                            "target_key": "chapter_claim_button",
                            "terminal_for_verifier": True,
                        },
                    },
                },
            }

            live_review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_chapter_claim_terminal_trace.json",
                expectation=live_expectation,
            )

            self.assertTrue(live_review["source_evidence_valid"])
            self.assertEqual(live_review["missing_evidence"], [])
            self.assertTrue(live_review["trace_validation"]["matched"])
            self.assertTrue(live_review["post_action_delta_evidence_validation"]["valid"])
            self.assertTrue(live_review["review_metadata_validation"]["valid"])
            self.assertTrue(live_review["file_integrity_validation"]["valid"])
            self.assertEqual(
                live_review["trace_validation"]["required_post_action_delta"],
                ["progress.chapter_claimable=false"],
            )
            self.assertEqual(
                live_review["trace_validation"]["matching_records"][0]["verifier_checked_paths"],
                ["progress.chapter_claimable"],
            )
            self.assertEqual(
                live_review["trace_validation"]["matching_records"][0]["trace_screenshot_path"],
                str(screenshot_path),
            )
            self.assertEqual(
                live_review["trace_validation"]["matching_records"][0]["trace_id"],
                "trace-claim-1",
            )
            self.assertTrue(
                live_review["trace_validation"]["record_evaluations"][0]["screenshot_matches"]
            )
            self.assertTrue(live_review["verification_record_validation"]["valid"])
            self.assertTrue(live_review["operator_confirmation_validation"]["valid"])
            self.assertTrue(
                live_review["operator_confirmation_validation"]["trace_binding"]["matched"]
            )

            wrong_screenshot_path = temp_root / "other-terminal.png"
            wrong_screenshot_path.write_bytes(b"placeholder")
            wrong_screenshot_expectation = {
                "page": "chapter",
                "terminal_source_evidence": {
                    **live_expectation["terminal_source_evidence"],
                    "screenshot": str(wrong_screenshot_path),
                },
            }
            wrong_screenshot_review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_chapter_claim_terminal_trace.json",
                expectation=wrong_screenshot_expectation,
            )

            self.assertFalse(wrong_screenshot_review["source_evidence_valid"])
            self.assertIn("trace_semantics", wrong_screenshot_review["missing_evidence"])
            self.assertFalse(
                wrong_screenshot_review["trace_validation"]["record_evaluations"][0][
                    "screenshot_matches"
                ]
            )

            bad_verifier_trace_path = temp_root / "claim-live-trace-wrong-verifier.jsonl"
            bad_verifier_trace_record = {
                **trace_record,
                "verification": {
                    "post_action_verifier": {
                        "action_type": "recruit_soldiers",
                        "status": "verified",
                        "checked": ["teams.0.soldiers"],
                    },
                },
            }
            bad_verifier_trace_path.write_text(
                json.dumps(bad_verifier_trace_record, ensure_ascii=False),
                encoding="utf-8",
            )
            invalid_verifier_trace_expectation = {
                "page": "chapter",
                "terminal_source_evidence": {
                    **live_expectation["terminal_source_evidence"],
                    "trace": str(bad_verifier_trace_path),
                },
            }
            invalid_verifier_trace_review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_chapter_claim_terminal_trace.json",
                expectation=invalid_verifier_trace_expectation,
            )

            self.assertFalse(invalid_verifier_trace_review["source_evidence_valid"])
            self.assertIn(
                "trace_semantics",
                invalid_verifier_trace_review["missing_evidence"],
            )
            self.assertTrue(
                invalid_verifier_trace_review["verification_record_validation"]["valid"]
            )
            self.assertFalse(invalid_verifier_trace_review["trace_validation"]["matched"])
            trace_evaluation = invalid_verifier_trace_review["trace_validation"][
                "record_evaluations"
            ][0]
            self.assertEqual(trace_evaluation["verifier_issues"], ["action_type", "checked_delta"])
            self.assertTrue(trace_evaluation["action_matches"])
            self.assertTrue(trace_evaluation["dispatch_matches"])
            self.assertFalse(trace_evaluation["verifier_valid"])

            bad_trace_path = temp_root / "claim-live-trace-wrong-target.jsonl"
            bad_trace_record = {
                **trace_record,
                "execution": {
                    "status": "ok",
                    "summary": {
                        "target_key": "recruit_button",
                        "terminal_for_verifier": True,
                    },
                },
            }
            bad_trace_path.write_text(json.dumps(bad_trace_record, ensure_ascii=False), encoding="utf-8")
            invalid_live_expectation = {
                "page": "chapter",
                "terminal_source_evidence": {
                    **live_expectation["terminal_source_evidence"],
                    "trace": str(bad_trace_path),
                    "verification_record": {
                        "action_type": "claim_chapter_reward",
                        "status": "failed",
                        "checked": ["progress.chapter_claimable"],
                    },
                },
            }
            invalid_live_review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_chapter_claim_terminal_trace.json",
                expectation=invalid_live_expectation,
            )

            self.assertFalse(invalid_live_review["source_evidence_valid"])
            self.assertIn("trace_semantics", invalid_live_review["missing_evidence"])
            self.assertIn("verification_record", invalid_live_review["missing_evidence"])
            self.assertFalse(invalid_live_review["trace_validation"]["matched"])
            self.assertEqual(
                invalid_live_review["verification_record_validation"]["issues"],
                ["status"],
            )

    def test_advisor_terminal_source_evidence_eval_preflights_live_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            screenshot_path = temp_root / "claim-terminal.png"
            screenshot_path.write_bytes(b"placeholder")
            trace_path = temp_root / "claim-live-trace.jsonl"
            trace_path.write_text(
                json.dumps(
                    {
                        "trace_id": "trace-claim-1",
                        "screenshot": {"path": str(screenshot_path)},
                        "selected_action": {"action_type": "claim_chapter_reward"},
                        "execution": {
                            "status": "ok",
                            "summary": {
                                "target_key": "chapter_claim_button",
                                "terminal_for_verifier": True,
                            },
                        },
                        "verification": {
                            "post_action_verifier": {
                                "action_type": "claim_chapter_reward",
                                "status": "verified",
                                "checked": ["progress.chapter_claimable"],
                            },
                        },
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            evidence = {
                "source_kind": "live_trace_fixture",
                "review_status": "reviewed",
                "reviewed_by": "qa-reviewer",
                "reviewed_at": "2026-05-30T18:20:00+08:00",
                "screenshot": str(screenshot_path),
                "screenshot_sha256": _sha256(screenshot_path),
                "trace": str(trace_path),
                "trace_sha256": _sha256(trace_path),
                "page": "chapter",
                "semantic_target": "progress.chapter_claim_button",
                "runtime_dispatch": {
                    "status": "ok",
                    "target_key": "chapter_claim_button",
                    "terminal_for_verifier": True,
                },
                "post_action_delta": [
                    {"path": "progress.chapter_claimable", "value": False},
                ],
                "post_action_delta_evidence": {
                    "source": "verification_record",
                    "post_action_delta": [
                        {"path": "progress.chapter_claimable", "value": False},
                    ],
                    "supporting_refs": [
                        "terminal_source_evidence.trace",
                        "terminal_source_evidence.verification_record",
                        "operator_confirmation.trace_id",
                    ],
                },
                "verification_record": {
                    "action_type": "claim_chapter_reward",
                    "status": "verified",
                    "checked": ["progress.chapter_claimable"],
                },
                "operator_confirmation": {
                    "confirmed": True,
                    "action_type": "claim_chapter_reward",
                    "scope": "final_mutating_click",
                    "requires_operator_confirmation": True,
                    "confirmed_at": "2026-05-30T17:45:00+08:00",
                    "trace_id": "trace-claim-1",
                    "trace_record_index": 0,
                    "runtime_dispatch": {
                        "status": "ok",
                        "target_key": "chapter_claim_button",
                        "terminal_for_verifier": True,
                    },
                },
            }

            result = self.handler.call_tool(
                "advisor_terminal_source_evidence_eval",
                {
                    "action_type": "claim_chapter_reward",
                    "terminal_source_evidence": evidence,
                    "fixture": "live_chapter_claim_terminal_trace.json",
                },
            )
            payload = result["structuredContent"]

            self.assertFalse(result["isError"])
            self.assertTrue(payload["ready"])
            self.assertTrue(payload["accepted_for_closure"])
            self.assertEqual(payload["review"]["missing_evidence"], [])
            self.assertTrue(payload["review"]["trace_validation"]["matched"])
            self.assertEqual(payload["next_source_requirements"], [])
            self.assertTrue(payload["capture_plan"]["ready"])
            self.assertEqual(
                payload["suggested_terminal_source_evidence_patch"]["screenshot_sha256"],
                _sha256(screenshot_path),
            )
            self.assertEqual(
                payload["suggested_terminal_source_evidence_patch"]["trace_sha256"],
                _sha256(trace_path),
            )
            expectation_patch = payload["suggested_advisor_fixture_expectation_patch"][
                "live_chapter_claim_terminal_trace.json"
            ]
            self.assertEqual(expectation_patch["page"], "chapter")
            self.assertEqual(expectation_patch["screenshot"], str(screenshot_path))
            self.assertEqual(
                expectation_patch["expected_action_type"],
                "claim_chapter_reward",
            )
            self.assertEqual(
                expectation_patch["expected_dispatch_target_key"],
                "chapter_claim_button",
            )
            self.assertTrue(expectation_patch["expected_dispatch_terminal_for_verifier"])
            self.assertEqual(
                expectation_patch["terminal_source_evidence"]["screenshot_sha256"],
                _sha256(screenshot_path),
            )
            self.assertEqual(
                expectation_patch["terminal_source_evidence"]["trace_sha256"],
                _sha256(trace_path),
            )

            invalid_evidence = {
                **evidence,
                "runtime_dispatch": {
                    "status": "ok",
                    "target_key": "recruit_button",
                    "terminal_for_verifier": True,
                },
                "operator_confirmation": {
                    **evidence["operator_confirmation"],
                    "confirmed": False,
                    "trace_record_index": 9,
                },
            }
            invalid_result = self.handler.call_tool(
                "advisor_terminal_source_evidence_eval",
                {
                    "action_type": "claim_chapter_reward",
                    "terminal_source_evidence": invalid_evidence,
                },
            )
            invalid_payload = invalid_result["structuredContent"]

            self.assertFalse(invalid_payload["ready"])
            self.assertIn("runtime_dispatch", invalid_payload["review"]["missing_evidence"])
            self.assertIn("operator_confirmation", invalid_payload["review"]["missing_evidence"])
            self.assertIn(
                "confirmed",
                invalid_payload["review"]["operator_confirmation_validation"]["issues"],
            )
            self.assertIn(
                "trace_binding",
                invalid_payload["review"]["operator_confirmation_validation"]["issues"],
            )
            self.assertIn(
                "trace_record_match",
                invalid_payload["review"]["operator_confirmation_validation"]["trace_binding"][
                    "issues"
                ],
            )
            self.assertEqual(
                invalid_payload["next_source_requirements"][0]["required_runtime_dispatch"]["target_key"],
                "chapter_claim_button",
            )
            self.assertFalse(invalid_payload["capture_plan"]["ready"])

            missing_hash_evidence = {
                key: value
                for key, value in evidence.items()
                if key not in {"screenshot_sha256", "trace_sha256"}
            }
            missing_hash_result = self.handler.call_tool(
                "advisor_terminal_source_evidence_eval",
                {
                    "action_type": "claim_chapter_reward",
                    "terminal_source_evidence": missing_hash_evidence,
                },
            )
            missing_hash_payload = missing_hash_result["structuredContent"]

            self.assertFalse(missing_hash_payload["ready"])
            self.assertIn("file_integrity", missing_hash_payload["review"]["missing_evidence"])
            self.assertEqual(
                missing_hash_payload["suggested_terminal_source_evidence_patch"][
                    "screenshot_sha256"
                ],
                _sha256(screenshot_path),
            )
            self.assertEqual(
                missing_hash_payload["suggested_terminal_source_evidence_patch"]["trace_sha256"],
                _sha256(trace_path),
            )
            self.assertEqual(
                missing_hash_payload["suggested_terminal_source_evidence_patch"][
                    "post_action_delta_evidence"
                ]["source"],
                "verification_record",
            )
            missing_hash_expectation_patch = missing_hash_payload[
                "suggested_advisor_fixture_expectation_patch"
            ]["live_claim_chapter_reward_terminal_trace.json"]
            self.assertEqual(
                missing_hash_expectation_patch["terminal_source_evidence"][
                    "screenshot_sha256"
                ],
                _sha256(screenshot_path),
            )
            self.assertEqual(
                missing_hash_expectation_patch["terminal_source_evidence"]["trace_sha256"],
                _sha256(trace_path),
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
