import copy
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from qa_agent.mcp_server.advisor_tools import (
    LOW_RISK_TERMINAL_SOURCE_REQUIREMENTS,
    AdvisorReplayTools,
    _post_action_delta_validation,
)
from qa_agent.mcp_server.tooling import KnowledgeToolHandler
from qa_agent.service.query_service import QueryService


_VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)

_FULL_FRAME_BBOX = {
    "x_min": 0,
    "y_min": 0,
    "x_max": 1000,
    "y_max": 1000,
}


def _capture_geometry() -> dict:
    return {
        "schema_version": 1,
        "capture_backend": "wgc",
        "outer_window": {
            "hwnd": 100,
            "pid": 200,
            "left": 0,
            "top": 0,
            "right": 1,
            "bottom": 1,
            "width": 1,
            "height": 1,
        },
        "capture_rect": {
            "left": 0,
            "top": 0,
            "right": 1,
            "bottom": 1,
            "width": 1,
            "height": 1,
        },
        "capture_origin": {"x": 0, "y": 0},
        "frame_size": [1, 1],
    }


def _semantic_frame_guard(target_key: str) -> dict:
    return {
        "schema_version": 1,
        "algorithm": "semantic-roi-rgb24-sha256-v1",
        "semantic_target_key": target_key,
        "frame_size": [1, 1],
        "capture_geometry": _capture_geometry(),
        "normalized_bbox": {key: float(value) for key, value in _FULL_FRAME_BBOX.items()},
        "roi_bbox": {"x": 0, "y": 0, "width": 1, "height": 1},
        "click_point": {"x": 0, "y": 0},
        # _VALID_PNG decodes to one black RGB pixel.
        "roi_sha256": hashlib.sha256(b"\x00\x00\x00").hexdigest(),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _privacy_review(**overrides: object) -> dict[str, object]:
    review: dict[str, object] = {
        "status": "approved",
        "reviewed_by": "privacy-reviewer",
        "reviewed_at": "2026-05-30T18:21:00+08:00",
        "screenshot_scope": "terminal_ui_only",
        "redaction_applied": False,
        "contains_account_identifier": False,
        "contains_chat_or_social_text": False,
        "contains_payment_or_secret": False,
        "approved_for_repo_storage": True,
    }
    review.update(overrides)
    return review


def _claim_target_delta() -> tuple[dict, dict]:
    return (
        {"chapter_id": 17},
        {
            "path": "progress.chapter_claimable",
            "operator": "changes_to",
            "before": True,
            "after": False,
        },
    )


def _write_claim_live_evidence(root: Path) -> tuple[dict, Path, Path]:
    screenshot_path = root / "claim-terminal.png"
    screenshot_path.write_bytes(_VALID_PNG)
    trace_path = root / "claim-live-trace.jsonl"
    target_identity, delta = _claim_target_delta()
    trace_id = "trace-claim-1"
    action_id = "action-claim-1"
    frame_sha256 = _sha256(screenshot_path)
    observation = {
        "observation_id": "observation-claim-1",
        "captured_at": "2026-05-30T17:45:00+08:00",
        "frame_sha256": frame_sha256,
        "frame_size": [1, 1],
        "capture_geometry": _capture_geometry(),
        "page_type": "chapter",
        "domains_run": ["resource_bar", "chapter_panel"],
        "source": "vision_sync",
    }
    runtime_dispatch = {
        "status": "ok",
        "target_key": "chapter_claim_button",
        "terminal_for_verifier": True,
    }
    claim_button = {
        "visible": True,
        "enabled": True,
        "bbox": dict(_FULL_FRAME_BBOX),
    }
    operator_confirmation = {
        "confirmed": True,
        "requires_operator_confirmation": True,
        "scope": "final_mutating_click",
        "confirmation_id": "confirmation-claim-1",
        "request_id": "request-claim-1",
        "action_id": action_id,
        "action_type": "claim_chapter_reward",
        "target_key": "chapter_claim_button",
        "target_identity": target_identity,
        "observation_id": observation["observation_id"],
        "frame_sha256": frame_sha256,
        "semantic_frame_guard": _semantic_frame_guard("chapter_claim_button"),
        "observation_captured_at": observation["captured_at"],
        "confirmed_at": "2026-05-30T17:45:05+08:00",
        "expires_at": "2026-05-30T17:45:15+08:00",
        "consumed_at": "2026-05-30T17:45:06+08:00",
        "dispatch_at": "2026-05-30T17:45:06+08:00",
        "runtime_dispatch": runtime_dispatch,
    }
    trace_record = {
        "trace_id": trace_id,
        "screenshot": {
            "path": str(screenshot_path),
            "metadata": {"observation": observation},
        },
        "frames": [
            {
                "role": "terminal_dispatch",
                "path": str(screenshot_path),
                "sha256": frame_sha256,
                "observation": observation,
            }
        ],
        "selected_action": {
            "action_id": action_id,
            "action_type": "claim_chapter_reward",
            "params": {**target_identity, "claim_button": claim_button},
        },
        "execution": {
            "action_id": action_id,
            "status": "ok",
            "summary": {
                "target_key": "chapter_claim_button",
                "terminal_for_verifier": True,
                "dispatch_at": operator_confirmation["dispatch_at"],
                "operator_confirmation": operator_confirmation,
            },
        },
        "verification": {
            "post_action_verifier": {
                "action_type": "claim_chapter_reward",
                "status": "verified",
                "target": target_identity,
                "checked": ["progress.chapter_claimable"],
                "post_action_delta": [delta],
            },
        },
    }
    trace_path.write_text(json.dumps(trace_record, ensure_ascii=False), encoding="utf-8")
    verification_record = trace_record["verification"]["post_action_verifier"]
    evidence = {
        "source_kind": "live_trace_fixture",
        "review_status": "reviewed",
        "reviewed_by": "qa-reviewer",
        "reviewed_at": "2026-05-30T18:20:00+08:00",
        "screenshot": str(screenshot_path),
        "screenshot_sha256": frame_sha256,
        "trace": str(trace_path),
        "trace_sha256": _sha256(trace_path),
        "privacy_review": _privacy_review(),
        "page": "chapter",
        "semantic_target": "progress.chapter_claim_button",
        "runtime_dispatch": runtime_dispatch,
        "target_identity": target_identity,
        "post_action_delta": [delta],
        "post_action_delta_evidence": {
            "source": "verification_record",
            "post_action_delta": [delta],
            "supporting_refs": [
                "terminal_source_evidence.trace",
                "terminal_source_evidence.verification_record",
                "operator_confirmation.trace_id",
            ],
        },
        "verification_record": verification_record,
        "operator_confirmation": {
            **operator_confirmation,
            "trace_id": trace_id,
            "trace_record_index": 0,
        },
    }
    return evidence, trace_path, screenshot_path


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(root), *args],
        capture_output=True,
        check=True,
        text=True,
    )
    return completed.stdout.strip()


def _write_repo_relative_claim_live_evidence(
    workspace_root: Path,
    *,
    commit: bool,
) -> tuple[dict, Path, Path]:
    reviewed_root = (
        workspace_root
        / "packages"
        / "pioneer-agent"
        / "tests"
        / "fixtures"
        / "live-evidence"
        / "reviewed"
        / "2026-05-30"
    )
    reviewed_root.mkdir(parents=True)
    evidence, trace_path, screenshot_path = _write_claim_live_evidence(reviewed_root)
    screenshot_rel = screenshot_path.relative_to(workspace_root).as_posix()
    trace_rel = trace_path.relative_to(workspace_root).as_posix()
    trace_record = json.loads(trace_path.read_text(encoding="utf-8"))
    trace_record["screenshot"]["path"] = screenshot_rel
    trace_record["frames"][0]["path"] = screenshot_rel
    trace_path.write_text(json.dumps(trace_record, ensure_ascii=False), encoding="utf-8")
    evidence["screenshot"] = screenshot_rel
    evidence["trace"] = trace_rel
    evidence["trace_sha256"] = _sha256(trace_path)

    _git(workspace_root, "init", "-q")
    _git(workspace_root, "config", "user.email", "qa-tests@example.invalid")
    _git(workspace_root, "config", "user.name", "QA Tests")
    if commit:
        _git(workspace_root, "add", screenshot_rel, trace_rel)
        _git(workspace_root, "commit", "-q", "-m", "review live evidence")
    else:
        marker = workspace_root / "README.md"
        marker.write_text("test repository\n", encoding="utf-8")
        _git(workspace_root, "add", "README.md")
        _git(workspace_root, "commit", "-q", "-m", "initialize")

    evidence["git_provenance"] = {
        "trust_boundary": "committed_reviewed_live_evidence",
        "reviewed_root": "packages/pioneer-agent/tests/fixtures/live-evidence/reviewed",
        "screenshot_blob": (
            _git(workspace_root, "rev-parse", f"HEAD:{screenshot_rel}")
            if commit
            else "0" * 40
        ),
        "trace_blob": (
            _git(workspace_root, "rev-parse", f"HEAD:{trace_rel}")
            if commit
            else "0" * 40
        ),
    }
    return evidence, trace_path, screenshot_path


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
            ["progress.chapter_claimable true->false"],
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
            ["live_trace_fixture"],
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
        guard_template = evidence_templates["live_trace_fixture"][
            "operator_confirmation"
        ]["semantic_frame_guard"]
        self.assertIn("capture_geometry", guard_template)
        self.assertIn("outer_window", guard_template["capture_geometry"])
        self.assertIn("capture_rect", guard_template["capture_geometry"])
        self.assertNotIn("pr5_real_screenshot_fixture", evidence_templates)
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
            ["progress.chapter_claimable true->false"],
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
        self.assertIn("privacy_review", capture_plan["actions"][0]["terminal_source_evidence_fields"])
        self.assertIn("post_action_delta_evidence", capture_plan["actions"][0]["terminal_source_evidence_fields"])
        self.assertIn(
            "approved_for_repo_storage=true",
            capture_plan["actions"][0]["privacy_review_fields"],
        )
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
            "selected_action.params and verification target/delta match target_identity",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        self.assertIn(
            "execution.summary.operator_confirmation is present and confirmed=true",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        self.assertIn(
            "manifest operator_confirmation exactly mirrors the matched trace confirmation plus trace_id/trace_record_index",
            capture_plan["actions"][0]["live_trace_semantic_checks"],
        )
        self.assertEqual(
            capture_plan["actions"][0]["advisor_fixture_manifest_target"],
            {
                "expectations_path": (
                    "packages/pioneer-agent/tests/golden/advisor_fixture_expectations.json"
                ),
                "fixture_key": "<claim_chapter_reward_terminal_fixture>.json",
                "json_path": "fixtures.<claim_chapter_reward_terminal_fixture>.json",
            },
        )
        self.assertEqual(
            [
                item["source_kind"]
                for item in capture_plan["actions"][0]["preflight_tool_calls"]
            ],
            ["live_trace_fixture"],
        )
        live_preflight = capture_plan["actions"][0]["preflight_tool_calls"][0]
        self.assertEqual(live_preflight["tool_name"], "advisor_terminal_source_evidence_eval")
        self.assertEqual(
            live_preflight["arguments"]["action_type"],
            "claim_chapter_reward",
        )
        self.assertEqual(
            live_preflight["arguments"]["terminal_source_evidence"]["trace_sha256"],
            "<sha256-of-trace>",
        )
        self.assertEqual(
            live_preflight["arguments"]["terminal_source_evidence"][
                "operator_confirmation"
            ]["scope"],
            "final_mutating_click",
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
            expectation_template["terminal_source_evidence"]["privacy_review"]["status"],
            "approved",
        )
        self.assertTrue(
            expectation_template["terminal_source_evidence"]["privacy_review"][
                "approved_for_repo_storage"
            ]
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
        self.assertTrue(
            {
                "confirmation_id",
                "request_id",
                "action_id",
                "action_type",
                "target_key",
                "target_identity",
                "observation_id",
                "frame_sha256",
                "observation_captured_at",
                "confirmed_at",
                "expires_at",
                "consumed_at",
                "dispatch_at",
                "runtime_dispatch",
            }.issubset(
                expectation_template["terminal_source_evidence"][
                    "operator_confirmation"
                ]
            )
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

    def test_advisor_fixture_eval_summary_omits_large_diagnostics(self) -> None:
        result = self.handler.call_tool(
            "advisor_fixture_eval",
            {
                "fixture": "chapter_claimable_state.json",
                "include_details": False,
            },
        )
        payload = result["structuredContent"]

        self.assertEqual(
            payload,
            {
                "fixture": "chapter_claimable_state.json",
                "matched": True,
                "page": None,
                "expected_action_type": "claim_chapter_reward",
                "actual_action_type": "claim_chapter_reward",
                "execution_authority": "none",
            },
        )
        self.assertLess(len(result["content"][0]["text"]), 500)

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
                ["progress.current_chapter_id", "progress.chapter_claimable"],
            ),
            "pr5_recruit_guard_camp_state.json": (
                "recruit_soldiers",
                "any",
                30.0,
                ["soldiers", "recruit_finish_time"],
            ),
            "pr5_building_upgrade_state.json": (
                "upgrade_building",
                "all",
                20.0,
                ["level"],
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
                "privacy_review": _privacy_review(),
                "page": "chapter",
                "semantic_target": "progress.chapter_claim_button",
                "runtime_dispatch": {
                    "status": "ok",
                    "target_key": "chapter_claim_button",
                    "terminal_for_verifier": True,
                },
                "target_identity": {"chapter_id": 17},
                "post_action_delta": [
                    {
                        "path": "progress.chapter_claimable",
                        "operator": "changes_to",
                        "before": True,
                        "after": False,
                    },
                ],
                "post_action_delta_evidence": {
                    "source": "verification_record",
                    "post_action_delta": [
                        {
                            "path": "progress.chapter_claimable",
                            "operator": "changes_to",
                            "before": True,
                            "after": False,
                        },
                    ],
                    "supporting_refs": [
                        "terminal_source_evidence.trace",
                        "terminal_source_evidence.verification_record",
                        "THIS_FILE_DOES_NOT_EXIST.json",
                    ],
                },
            },
        }

        review = tools._terminal_source_evidence_review(
            action_type="claim_chapter_reward",
            fixture="pr5_chapter_claim_terminal_state.json",
            expectation=valid_expectation,
        )

        self.assertFalse(review["source_evidence_valid"])
        self.assertIn("accepted_source_kind", review["missing_evidence"])
        self.assertIn("post_action_delta_evidence", review["missing_evidence"])
        self.assertEqual(review["required_page"], "chapter")
        self.assertEqual(review["required_semantic_target"], "progress.chapter_claim_button")
        self.assertEqual(review["required_runtime_dispatch"]["target_key"], "chapter_claim_button")
        self.assertEqual(
            review["required_post_action_delta"],
            ["progress.chapter_claimable true->false"],
        )
        self.assertFalse(review["post_action_delta_evidence_validation"]["valid"])
        self.assertIn(
            "supporting_ref_binding",
            review["post_action_delta_evidence_validation"]["issues"],
        )
        self.assertTrue(review["review_metadata_validation"]["valid"])
        self.assertTrue(review["privacy_review_validation"]["valid"])
        self.assertFalse(review["file_integrity_validation"]["checked"])

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
        self.assertIn(
            "post_action_delta",
            invalid_delta_evidence["post_action_delta_evidence_validation"]["issues"],
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

        invalid_privacy_expectation = {
            "page": "chapter",
            "terminal_source_evidence": {
                **valid_expectation["terminal_source_evidence"],
                "privacy_review": _privacy_review(
                    contains_account_identifier=True,
                    approved_for_repo_storage=False,
                ),
            },
        }
        invalid_privacy_review = tools._terminal_source_evidence_review(
            action_type="claim_chapter_reward",
            fixture="pr5_chapter_claim_terminal_state.json",
            expectation=invalid_privacy_expectation,
        )

        self.assertFalse(invalid_privacy_review["source_evidence_valid"])
        self.assertIn("privacy_review", invalid_privacy_review["missing_evidence"])
        self.assertEqual(
            invalid_privacy_review["privacy_review_validation"]["issues"],
            ["approved_for_repo_storage", "contains_account_identifier"],
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
        self.assertIn("accepted_source_kind", invalid_hash_review["missing_evidence"])

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
        self.assertTrue(
            {"page", "post_action_delta", "runtime_dispatch", "semantic_target"}.issubset(
                set(invalid_review["missing_evidence"])
            )
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            evidence, trace_path, screenshot_path = _write_claim_live_evidence(temp_root)
            trace_record = json.loads(trace_path.read_text(encoding="utf-8"))
            live_expectation = {
                "page": "chapter",
                "terminal_source_evidence": evidence,
            }

            live_review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_chapter_claim_terminal_trace.json",
                expectation=live_expectation,
            )

            self.assertTrue(live_review["source_evidence_valid"])
            self.assertTrue(live_review["structural_valid"])
            self.assertTrue(live_review["ready_for_staging"])
            self.assertFalse(live_review["accepted_for_closure"])
            self.assertFalse(live_review["closure_authority_valid"])
            self.assertIn(
                "screenshot_path_not_repo_relative",
                live_review["closure_disqualifiers"],
            )
            self.assertEqual(live_review["missing_evidence"], [])
            self.assertTrue(live_review["trace_validation"]["matched"])
            self.assertTrue(live_review["post_action_delta_evidence_validation"]["valid"])
            self.assertTrue(live_review["review_metadata_validation"]["valid"])
            self.assertTrue(live_review["privacy_review_validation"]["valid"])
            self.assertTrue(live_review["file_integrity_validation"]["valid"])
            self.assertEqual(
                live_review["trace_validation"]["required_post_action_delta"],
                ["progress.chapter_claimable true->false"],
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
            self.assertFalse(
                invalid_verifier_trace_review["verification_record_validation"]["valid"]
            )
            self.assertFalse(invalid_verifier_trace_review["trace_validation"]["matched"])
            trace_evaluation = invalid_verifier_trace_review["trace_validation"][
                "record_evaluations"
            ][0]
            self.assertEqual(
                trace_evaluation["verifier_issues"],
                ["action_type", "post_action_delta", "target_identity"],
            )
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
            self.assertIn(
                "status",
                invalid_live_review["verification_record_validation"]["issues"],
            )

    def test_advisor_terminal_source_evidence_eval_preflights_live_trace(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            evidence, trace_path, screenshot_path = _write_claim_live_evidence(temp_root)

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
            self.assertFalse(payload["ready"])
            self.assertFalse(payload["accepted_for_closure"])
            self.assertTrue(payload["ready_for_staging"])
            self.assertTrue(payload["structural_valid"])
            self.assertFalse(payload["closure_authority_valid"])
            self.assertEqual(payload["review"]["missing_evidence"], [])
            self.assertTrue(payload["review"]["trace_validation"]["matched"])
            self.assertTrue(payload["next_source_requirements"])
            self.assertFalse(payload["capture_plan"]["ready"])
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

    def test_terminal_source_closure_requires_committed_reviewed_git_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            evidence, _trace_path, _screenshot_path = (
                _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
            )
            tools = AdvisorReplayTools(workspace_root=workspace_root)

            review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={
                    "page": "chapter",
                    "terminal_source_evidence": evidence,
                },
            )

            self.assertTrue(review["structural_valid"])
            self.assertTrue(review["ready_for_staging"])
            self.assertTrue(review["closure_authority_valid"])
            self.assertTrue(review["accepted_for_closure"])
            authority = review["closure_authority_validation"]
            self.assertTrue(authority["repository_clean"])
            self.assertTrue(authority["head_commit"])
            self.assertIsNone(authority["declared_head_commit"])
            self.assertTrue(authority["bound_to_clean_head"])
            self.assertTrue(all(item["matched"] for item in authority["blob_checks"]))
            self.assertTrue(all(item["worktree_matches_head"] for item in authority["blob_checks"]))
            self.assertTrue(all(item["worktree_stable"] for item in authority["blob_checks"]))
            self.assertEqual(
                review["trace_validation"]["required_screenshot_sha256"],
                evidence["screenshot_sha256"],
            )
            self.assertEqual(review["trace_validation"]["required_screenshot_size"], [1, 1])

    def test_terminal_source_rejects_ignored_literal_pathspec_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            evidence, trace_path, screenshot_path = (
                _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
            )
            alias_screenshot = screenshot_path.with_name("claim-*.png")
            alias_trace = trace_path.with_name("claim-*.jsonl")
            alias_screenshot.write_bytes(screenshot_path.read_bytes() + b"ignored-alias")
            screenshot_rel = alias_screenshot.relative_to(workspace_root).as_posix()
            trace_rel = alias_trace.relative_to(workspace_root).as_posix()
            frame_sha256 = _sha256(alias_screenshot)
            record = json.loads(trace_path.read_text(encoding="utf-8"))
            record["screenshot"]["path"] = screenshot_rel
            record["screenshot"]["metadata"]["observation"]["frame_sha256"] = frame_sha256
            record["frames"][0]["path"] = screenshot_rel
            record["frames"][0]["sha256"] = frame_sha256
            record["frames"][0]["observation"]["frame_sha256"] = frame_sha256
            record["execution"]["summary"]["operator_confirmation"][
                "frame_sha256"
            ] = frame_sha256
            alias_trace.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            evidence["screenshot"] = screenshot_rel
            evidence["screenshot_sha256"] = frame_sha256
            evidence["trace"] = trace_rel
            evidence["trace_sha256"] = _sha256(alias_trace)
            evidence["operator_confirmation"]["frame_sha256"] = frame_sha256
            exclude = workspace_root / ".git" / "info" / "exclude"
            literal_patterns = [
                "/" + screenshot_rel.replace("*", "[*]"),
                "/" + trace_rel.replace("*", "[*]"),
            ]
            exclude.write_text(
                exclude.read_text(encoding="utf-8")
                + "\n"
                + "\n".join(literal_patterns)
                + "\n",
                encoding="utf-8",
            )
            self.assertEqual(
                _git(workspace_root, "status", "--porcelain=v1", "--untracked-files=all"),
                "",
            )

            review = AdvisorReplayTools(
                workspace_root=workspace_root
            )._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={"page": "chapter", "terminal_source_evidence": evidence},
            )

            self.assertTrue(review["structural_valid"])
            self.assertFalse(review["accepted_for_closure"])
            self.assertIn(
                "screenshot_not_committed_regular_blob",
                review["closure_disqualifiers"],
            )
            self.assertIn(
                "trace_not_committed_regular_blob",
                review["closure_disqualifiers"],
            )
            self.assertTrue(
                all(
                    "head_entry_count" in item["head_lookup_issues"]
                    for item in review["closure_authority_validation"]["blob_checks"]
                )
            )

    def test_terminal_source_rejects_assume_unchanged_worktree_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            evidence, trace_path, screenshot_path = (
                _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
            )
            screenshot_rel = screenshot_path.relative_to(workspace_root).as_posix()
            trace_rel = trace_path.relative_to(workspace_root).as_posix()
            _git(
                workspace_root,
                "update-index",
                "--assume-unchanged",
                "--",
                screenshot_rel,
                trace_rel,
            )
            screenshot_path.write_bytes(screenshot_path.read_bytes() + b"uncommitted-tamper")
            frame_sha256 = _sha256(screenshot_path)
            record = json.loads(trace_path.read_text(encoding="utf-8"))
            record["screenshot"]["metadata"]["observation"]["frame_sha256"] = frame_sha256
            record["frames"][0]["sha256"] = frame_sha256
            record["frames"][0]["observation"]["frame_sha256"] = frame_sha256
            record["execution"]["summary"]["operator_confirmation"][
                "frame_sha256"
            ] = frame_sha256
            trace_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
            evidence["screenshot_sha256"] = frame_sha256
            evidence["trace_sha256"] = _sha256(trace_path)
            evidence["operator_confirmation"]["frame_sha256"] = frame_sha256
            self.assertEqual(
                _git(workspace_root, "status", "--porcelain=v1", "--untracked-files=all"),
                "",
            )

            review = AdvisorReplayTools(
                workspace_root=workspace_root
            )._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={"page": "chapter", "terminal_source_evidence": evidence},
            )

            self.assertTrue(review["structural_valid"])
            self.assertFalse(review["accepted_for_closure"])
            self.assertIn(
                "screenshot_worktree_not_head_blob",
                review["closure_disqualifiers"],
            )
            self.assertIn(
                "trace_worktree_not_head_blob",
                review["closure_disqualifiers"],
            )

    def test_terminal_source_rejects_hardlink_and_mid_validation_replacement(self) -> None:
        with self.subTest("hardlink"):
            with tempfile.TemporaryDirectory() as temp_dir, tempfile.TemporaryDirectory() as external:
                workspace_root = Path(temp_dir)
                evidence, _trace_path, screenshot_path = (
                    _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
                )
                os.link(screenshot_path, Path(external) / "external.png")
                review = AdvisorReplayTools(
                    workspace_root=workspace_root
                )._terminal_source_evidence_review(
                    action_type="claim_chapter_reward",
                    fixture="live_claim_terminal_trace.json",
                    expectation={"page": "chapter", "terminal_source_evidence": evidence},
                )
                self.assertFalse(review["structural_valid"])
                self.assertFalse(review["accepted_for_closure"])
                self.assertIn("screenshot_hardlink", review["closure_disqualifiers"])

        with self.subTest("mid-validation replacement"):
            with tempfile.TemporaryDirectory() as temp_dir:
                workspace_root = Path(temp_dir)
                evidence, _trace_path, screenshot_path = (
                    _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
                )
                screenshot_rel = screenshot_path.relative_to(workspace_root).as_posix()
                _git(
                    workspace_root,
                    "update-index",
                    "--assume-unchanged",
                    "--",
                    screenshot_rel,
                )
                tools = AdvisorReplayTools(workspace_root=workspace_root)
                original_run_git = tools._run_git
                mutated = False

                def mutate_after_first_status(*args: str) -> dict:
                    nonlocal mutated
                    result = original_run_git(*args)
                    if args and args[0] == "status" and not mutated:
                        screenshot_path.write_bytes(
                            screenshot_path.read_bytes() + b"raced-after-snapshot"
                        )
                        mutated = True
                    return result

                tools._run_git = mutate_after_first_status  # type: ignore[method-assign]
                review = tools._terminal_source_evidence_review(
                    action_type="claim_chapter_reward",
                    fixture="live_claim_terminal_trace.json",
                    expectation={"page": "chapter", "terminal_source_evidence": evidence},
                )
                self.assertTrue(mutated)
                self.assertFalse(review["accepted_for_closure"])
                self.assertIn(
                    "screenshot_worktree_changed_during_validation",
                    review["closure_disqualifiers"],
                )

    def test_terminal_source_binds_trace_hash_and_dimensions_to_head_screenshot(self) -> None:
        for mismatch in ("sha256", "frame_size", "primary_observation"):
            with self.subTest(mismatch=mismatch), tempfile.TemporaryDirectory() as temp_dir:
                workspace_root = Path(temp_dir)
                evidence, trace_path, _screenshot_path = (
                    _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
                )
                record = json.loads(trace_path.read_text(encoding="utf-8"))
                if mismatch == "sha256":
                    fake_sha256 = "f" * 64
                    record["screenshot"]["metadata"]["observation"][
                        "frame_sha256"
                    ] = fake_sha256
                    record["frames"][0]["sha256"] = fake_sha256
                    record["frames"][0]["observation"]["frame_sha256"] = fake_sha256
                    record["execution"]["summary"]["operator_confirmation"][
                        "frame_sha256"
                    ] = fake_sha256
                    evidence["operator_confirmation"]["frame_sha256"] = fake_sha256
                    expected_issue = "terminal_dispatch_frame_screenshot_sha256_binding"
                elif mismatch == "frame_size":
                    fake_size = [2, 2]
                    record["screenshot"]["metadata"]["observation"][
                        "frame_size"
                    ] = fake_size
                    record["frames"][0]["observation"]["frame_size"] = fake_size
                    record["execution"]["summary"]["operator_confirmation"][
                        "semantic_frame_guard"
                    ]["frame_size"] = fake_size
                    evidence["operator_confirmation"]["semantic_frame_guard"][
                        "frame_size"
                    ] = fake_size
                    expected_issue = "terminal_dispatch_observation_frame_size_binding"
                else:
                    record["screenshot"]["metadata"]["observation"][
                        "page_type"
                    ] = "attacker_mismatched_page"
                    expected_issue = "screenshot_primary_observation_binding"
                trace_path.write_text(json.dumps(record, ensure_ascii=False), encoding="utf-8")
                evidence["trace_sha256"] = _sha256(trace_path)
                trace_rel = trace_path.relative_to(workspace_root).as_posix()
                _git(workspace_root, "add", trace_rel)
                _git(workspace_root, "commit", "-q", "-m", f"mismatch {mismatch}")
                evidence["git_provenance"]["trace_blob"] = _git(
                    workspace_root,
                    "rev-parse",
                    f"HEAD:{trace_rel}",
                )

                review = AdvisorReplayTools(
                    workspace_root=workspace_root
                )._terminal_source_evidence_review(
                    action_type="claim_chapter_reward",
                    fixture="live_claim_terminal_trace.json",
                    expectation={"page": "chapter", "terminal_source_evidence": evidence},
                )

                self.assertFalse(review["structural_valid"])
                self.assertFalse(review["accepted_for_closure"])
                self.assertIn("trace_semantics", review["missing_evidence"])
                issues = review["trace_validation"]["record_evaluations"][0][
                    "terminal_observation_issues"
                ]
                self.assertIn(expected_issue, issues)

    def test_terminal_source_rebuilds_complete_semantic_guard_from_screenshot(self) -> None:
        cases = {
            "semantic_target_key": (
                "attacker_chosen_other_button",
                "operator_confirmation.semantic_frame_guard.semantic_target_key",
            ),
            "normalized_bbox": (
                {"x_min": 0.0, "y_min": 0.0, "x_max": 900.0, "y_max": 1000.0},
                "operator_confirmation.semantic_frame_guard.normalized_bbox_binding",
            ),
            "roi_bbox": (
                {"x": 1, "y": 0, "width": 1, "height": 1},
                "operator_confirmation.semantic_frame_guard.roi_bbox",
            ),
            "click_point": (
                {"x": 1, "y": 0},
                "operator_confirmation.semantic_frame_guard.click_point",
            ),
            "roi_sha256": (
                "0" * 64,
                "operator_confirmation.semantic_frame_guard.roi_sha256_binding",
            ),
        }
        for field_name, (replacement, expected_issue) in cases.items():
            with self.subTest(field_name=field_name), tempfile.TemporaryDirectory() as temp_dir:
                workspace_root = Path(temp_dir)
                evidence, trace_path, _screenshot_path = (
                    _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
                )
                record = json.loads(trace_path.read_text(encoding="utf-8"))
                record["execution"]["summary"]["operator_confirmation"][
                    "semantic_frame_guard"
                ][field_name] = replacement
                evidence["operator_confirmation"]["semantic_frame_guard"][
                    field_name
                ] = copy.deepcopy(replacement)
                trace_path.write_text(
                    json.dumps(record, ensure_ascii=False),
                    encoding="utf-8",
                )
                evidence["trace_sha256"] = _sha256(trace_path)
                trace_rel = trace_path.relative_to(workspace_root).as_posix()
                _git(workspace_root, "add", trace_rel)
                _git(workspace_root, "commit", "-q", "-m", f"forge {field_name}")
                evidence["git_provenance"]["trace_blob"] = _git(
                    workspace_root,
                    "rev-parse",
                    f"HEAD:{trace_rel}",
                )

                review = AdvisorReplayTools(
                    workspace_root=workspace_root
                )._terminal_source_evidence_review(
                    action_type="claim_chapter_reward",
                    fixture="live_claim_terminal_trace.json",
                    expectation={"page": "chapter", "terminal_source_evidence": evidence},
                )

                self.assertFalse(review["structural_valid"])
                self.assertFalse(review["accepted_for_closure"])
                self.assertIn("trace_semantics", review["missing_evidence"])
                trace_issues = review["trace_validation"]["record_evaluations"][0][
                    "trace_operator_confirmation_issues"
                ]
                self.assertIn(expected_issue, trace_issues)

    def test_terminal_source_rejects_missing_or_forged_capture_geometry(self) -> None:
        translated = _capture_geometry()
        translated["outer_window"].update(
            {"left": 10, "top": 20, "right": 11, "bottom": 21}
        )
        translated["capture_rect"].update(
            {"left": 10, "top": 20, "right": 11, "bottom": 21}
        )
        translated["capture_origin"] = {"x": 10, "y": 20}
        backend_changed = _capture_geometry()
        backend_changed["capture_backend"] = "dxgi"
        window_changed = _capture_geometry()
        window_changed["outer_window"]["hwnd"] = 101
        origin_invalid = _capture_geometry()
        origin_invalid["capture_origin"] = {"x": 1, "y": 0}
        frame_size_changed = _capture_geometry()
        frame_size_changed["outer_window"].update(
            {"right": 2, "bottom": 2, "width": 2, "height": 2}
        )
        frame_size_changed["capture_rect"].update(
            {"right": 2, "bottom": 2, "width": 2, "height": 2}
        )
        frame_size_changed["frame_size"] = [2, 2]
        cases = {
            "missing": (
                None,
                "operator_confirmation.semantic_frame_guard.fields",
            ),
            "backend": (
                backend_changed,
                "operator_confirmation.semantic_frame_guard.capture_geometry_binding",
            ),
            "outer_window": (
                window_changed,
                "operator_confirmation.semantic_frame_guard.capture_geometry_binding",
            ),
            "capture_rect_and_origin": (
                translated,
                "operator_confirmation.semantic_frame_guard.capture_geometry_binding",
            ),
            "origin_invalid": (
                origin_invalid,
                "operator_confirmation.semantic_frame_guard.capture_geometry.capture_origin_binding",
            ),
            "frame_size": (
                frame_size_changed,
                "operator_confirmation.semantic_frame_guard.capture_geometry.frame_size",
            ),
        }
        for label, (replacement, expected_issue) in cases.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                workspace_root = Path(temp_dir)
                evidence, trace_path, _screenshot_path = (
                    _write_repo_relative_claim_live_evidence(workspace_root, commit=True)
                )
                record = json.loads(trace_path.read_text(encoding="utf-8"))
                trace_guard = record["execution"]["summary"]["operator_confirmation"][
                    "semantic_frame_guard"
                ]
                manifest_guard = evidence["operator_confirmation"]["semantic_frame_guard"]
                if replacement is None:
                    del trace_guard["capture_geometry"]
                    del manifest_guard["capture_geometry"]
                else:
                    trace_guard["capture_geometry"] = copy.deepcopy(replacement)
                    manifest_guard["capture_geometry"] = copy.deepcopy(replacement)
                trace_path.write_text(json.dumps(record), encoding="utf-8")
                evidence["trace_sha256"] = _sha256(trace_path)
                trace_rel = trace_path.relative_to(workspace_root).as_posix()
                _git(workspace_root, "add", trace_rel)
                _git(workspace_root, "commit", "-q", "-m", f"forge geometry {label}")
                evidence["git_provenance"]["trace_blob"] = _git(
                    workspace_root,
                    "rev-parse",
                    f"HEAD:{trace_rel}",
                )

                review = AdvisorReplayTools(
                    workspace_root=workspace_root
                )._terminal_source_evidence_review(
                    action_type="claim_chapter_reward",
                    fixture="live_claim_terminal_trace.json",
                    expectation={"page": "chapter", "terminal_source_evidence": evidence},
                )

                self.assertFalse(review["structural_valid"])
                self.assertFalse(review["accepted_for_closure"])
                trace_issues = review["trace_validation"]["record_evaluations"][0][
                    "trace_operator_confirmation_issues"
                ]
                self.assertIn(expected_issue, trace_issues)

    def test_terminal_source_rejects_placeholder_absolute_and_uncommitted_sources(self) -> None:
        tools = AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            evidence, _trace_path, screenshot_path = _write_claim_live_evidence(temp_root)
            screenshot_path.write_bytes(b"terminal screenshot")
            evidence["screenshot_sha256"] = _sha256(screenshot_path)
            review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={"page": "chapter", "terminal_source_evidence": evidence},
            )

            self.assertFalse(review["structural_valid"])
            self.assertFalse(review["ready_for_staging"])
            self.assertFalse(review["accepted_for_closure"])
            self.assertIn("screenshot_decode", review["missing_evidence"])
            self.assertIn(
                "screenshot_path_not_repo_relative",
                review["closure_disqualifiers"],
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            evidence, trace_path, _screenshot_path = _write_claim_live_evidence(temp_root)
            trace_record = json.loads(trace_path.read_text(encoding="utf-8"))
            # The legacy loader accepted a JSON array. Closure evidence must be
            # strict JSONL, even when the enclosed record is otherwise valid.
            trace_path.write_text(json.dumps([trace_record]), encoding="utf-8")
            evidence["trace_sha256"] = _sha256(trace_path)
            review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={"page": "chapter", "terminal_source_evidence": evidence},
            )

            self.assertFalse(review["structural_valid"])
            self.assertIn("strict_trace", review["missing_evidence"])
            self.assertIn(
                "trace_object_line_1",
                review["strict_trace_validation"]["issues"],
            )

        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            evidence, _trace_path, _screenshot_path = (
                _write_repo_relative_claim_live_evidence(workspace_root, commit=False)
            )
            review = AdvisorReplayTools(
                workspace_root=workspace_root
            )._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={"page": "chapter", "terminal_source_evidence": evidence},
            )

            self.assertTrue(review["structural_valid"])
            self.assertFalse(review["accepted_for_closure"])
            self.assertIn("git_worktree_not_clean", review["closure_disqualifiers"])
            self.assertIn(
                "screenshot_not_committed_regular_blob",
                review["closure_disqualifiers"],
            )

    def test_reviewed_live_evidence_paths_reject_escape_and_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace_root = Path(temp_dir)
            tools = AdvisorReplayTools(workspace_root=workspace_root)
            escaped = tools._reviewed_live_evidence_path_validation(
                "screenshot",
                "packages/pioneer-agent/tests/fixtures/live-evidence/reviewed/../../escape.png",
            )
            self.assertFalse(escaped["valid"])
            self.assertIn("screenshot_path_escape", escaped["issues"])

            reviewed_root = (
                workspace_root
                / "packages/pioneer-agent/tests/fixtures/live-evidence/reviewed"
            )
            reviewed_root.mkdir(parents=True)
            actual = reviewed_root / "actual.png"
            actual.write_bytes(_VALID_PNG)
            link = reviewed_root / "linked.png"
            link.symlink_to(actual.name)
            symlinked = tools._reviewed_live_evidence_path_validation(
                "screenshot",
                link.relative_to(workspace_root).as_posix(),
            )
            self.assertFalse(symlinked["valid"])
            self.assertIn("screenshot_symlink", symlinked["issues"])

    def test_static_screenshot_metadata_cannot_satisfy_executor_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence, _trace_path, _screenshot_path = _write_claim_live_evidence(
                Path(temp_dir)
            )
            evidence["source_kind"] = "pr5_real_screenshot_fixture"
            evidence["post_action_delta_evidence"] = {
                **evidence["post_action_delta_evidence"],
                "supporting_refs": [
                    "terminal_source_evidence.trace",
                    "terminal_source_evidence.verification_record",
                    "THIS_FILE_DOES_NOT_EXIST.json",
                ],
            }

            payload = AdvisorReplayTools.from_qa_project_root(
                Path(__file__).resolve().parents[1]
            ).terminal_source_evidence_eval(
                action_type="claim_chapter_reward",
                fixture="pr5_chapter_claim_terminal_state.json",
                page="chapter",
                terminal_source_evidence=evidence,
            )

            self.assertFalse(payload["ready"])
            self.assertIn("accepted_source_kind", payload["review"]["missing_evidence"])
            self.assertIn(
                "post_action_delta_evidence",
                payload["review"]["missing_evidence"],
            )
            self.assertIn(
                "supporting_ref_binding",
                payload["review"]["post_action_delta_evidence_validation"]["issues"],
            )

    def test_operator_confirmation_must_be_aware_and_precede_dispatch(self) -> None:
        tools = AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence, _trace_path, _screenshot_path = _write_claim_live_evidence(
                Path(temp_dir)
            )
            cases = {
                "naive": "2026-05-30T17:45:00",
                "after_dispatch": "2026-05-30T17:47:00+08:00",
            }
            for label, confirmed_at in cases.items():
                with self.subTest(label=label):
                    invalid = {
                        **evidence,
                        "operator_confirmation": {
                            **evidence["operator_confirmation"],
                            "confirmed_at": confirmed_at,
                        },
                    }
                    review = tools._terminal_source_evidence_review(
                        action_type="claim_chapter_reward",
                        fixture="live_claim_terminal_trace.json",
                        expectation={
                            "page": "chapter",
                            "terminal_source_evidence": invalid,
                        },
                    )
                    self.assertFalse(review["source_evidence_valid"])
                    self.assertIn("operator_confirmation", review["missing_evidence"])
                    issue = (
                        "confirmed_at_aware_iso8601"
                        if label == "naive"
                        else "confirmation_not_before_dispatch"
                    )
                    self.assertIn(
                        issue,
                        review["operator_confirmation_validation"]["issues"],
                    )

    def test_manifest_confirmation_cannot_replace_missing_trace_confirmation(self) -> None:
        tools = AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                Path(temp_dir)
            )
            trace_record = json.loads(trace_path.read_text(encoding="utf-8"))
            del trace_record["execution"]["summary"]["operator_confirmation"]
            trace_path.write_text(json.dumps(trace_record, ensure_ascii=False), encoding="utf-8")
            evidence["trace_sha256"] = _sha256(trace_path)

            review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={"page": "chapter", "terminal_source_evidence": evidence},
            )

            self.assertFalse(review["source_evidence_valid"])
            self.assertIn("trace_semantics", review["missing_evidence"])
            self.assertIn("operator_confirmation", review["missing_evidence"])
            evaluation = review["trace_validation"]["record_evaluations"][0]
            self.assertFalse(evaluation["trace_operator_confirmation_valid"])
            self.assertIn(
                "trace_operator_confirmation_not_object",
                evaluation["trace_operator_confirmation_issues"],
            )

    def test_manifest_confirmation_must_exactly_mirror_matched_trace(self) -> None:
        tools = AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence, _trace_path, _screenshot_path = _write_claim_live_evidence(
                Path(temp_dir)
            )
            cases = {
                "confirmation_id": "confirmation-other",
                "request_id": "request-other",
                "action_id": "action-other",
                "action_type": "recruit_soldiers",
                "target_key": "other_button",
                "target_identity": {"chapter_id": 18},
                "observation_id": "observation-other",
                "frame_sha256": "0" * 64,
                "observation_captured_at": "2026-05-30T17:45:01+08:00",
                "confirmed_at": "2026-05-30T17:45:04+08:00",
                "expires_at": "2026-05-30T17:45:14+08:00",
                "consumed_at": "2026-05-30T17:45:07+08:00",
                "dispatch_at": "2026-05-30T17:45:07+08:00",
                "runtime_dispatch": {
                    "status": "ok",
                    "target_key": "other_button",
                    "terminal_for_verifier": True,
                },
            }
            manifest_only_guard = copy.deepcopy(
                evidence["operator_confirmation"]["semantic_frame_guard"]
            )
            manifest_only_guard["capture_geometry"]["outer_window"]["hwnd"] = 999
            cases["semantic_frame_guard"] = manifest_only_guard
            for field_name, replacement in cases.items():
                with self.subTest(field_name=field_name):
                    invalid = copy.deepcopy(evidence)
                    invalid["operator_confirmation"][field_name] = replacement
                    review = tools._terminal_source_evidence_review(
                        action_type="claim_chapter_reward",
                        fixture="live_claim_terminal_trace.json",
                        expectation={
                            "page": "chapter",
                            "terminal_source_evidence": invalid,
                        },
                    )
                    self.assertFalse(review["source_evidence_valid"])
                    self.assertIn("operator_confirmation", review["missing_evidence"])
                    self.assertIn(
                        f"trace_confirmation_mismatch.{field_name}",
                        review["operator_confirmation_validation"]["issues"],
                    )

    def test_trace_confirmation_must_bind_terminal_observation_and_time(self) -> None:
        tools = AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[1])
        cases = {
            "empty_confirmation_id": ("confirmation_id", ""),
            "empty_request_id": ("request_id", ""),
            "action_id": ("action_id", "action-other"),
            "action_type": ("action_type", "recruit_soldiers"),
            "target_key": ("target_key", "other_button"),
            "target_identity": ("target_identity", {"chapter_id": 18}),
            "observation_id": ("observation_id", "observation-other"),
            "frame_sha256": ("frame_sha256", "0" * 64),
            "dispatch_at": ("dispatch_at", "2026-05-30T17:45:07+08:00"),
            "runtime_dispatch": (
                "runtime_dispatch",
                {
                    "status": "ok",
                    "target_key": "other_button",
                    "terminal_for_verifier": True,
                },
            ),
            "confirmation_before_observation": (
                "confirmed_at",
                "2026-05-30T17:44:59+08:00",
            ),
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            for label, (field_name, replacement) in cases.items():
                with self.subTest(label=label):
                    case_root = temp_root / label
                    case_root.mkdir()
                    evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                        case_root
                    )
                    trace_record = json.loads(trace_path.read_text(encoding="utf-8"))
                    trace_confirmation = trace_record["execution"]["summary"][
                        "operator_confirmation"
                    ]
                    trace_confirmation[field_name] = replacement
                    evidence["operator_confirmation"][field_name] = replacement
                    trace_path.write_text(
                        json.dumps(trace_record, ensure_ascii=False),
                        encoding="utf-8",
                    )
                    evidence["trace_sha256"] = _sha256(trace_path)

                    review = tools._terminal_source_evidence_review(
                        action_type="claim_chapter_reward",
                        fixture="live_claim_terminal_trace.json",
                        expectation={
                            "page": "chapter",
                            "terminal_source_evidence": evidence,
                        },
                    )

                    self.assertFalse(review["source_evidence_valid"])
                    self.assertIn("trace_semantics", review["missing_evidence"])
                    evaluation = review["trace_validation"]["record_evaluations"][0]
                    self.assertFalse(evaluation["trace_operator_confirmation_valid"])
                    self.assertTrue(evaluation["trace_operator_confirmation_issues"])

    def test_trace_selected_action_target_must_match_evidence_identity(self) -> None:
        tools = AdvisorReplayTools.from_qa_project_root(Path(__file__).resolve().parents[1])
        with tempfile.TemporaryDirectory() as temp_dir:
            evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                Path(temp_dir)
            )
            trace_record = json.loads(trace_path.read_text(encoding="utf-8"))
            trace_record["selected_action"]["params"]["chapter_id"] = 18
            trace_path.write_text(json.dumps(trace_record, ensure_ascii=False), encoding="utf-8")
            evidence["trace_sha256"] = _sha256(trace_path)

            review = tools._terminal_source_evidence_review(
                action_type="claim_chapter_reward",
                fixture="live_claim_terminal_trace.json",
                expectation={
                    "page": "chapter",
                    "terminal_source_evidence": evidence,
                },
            )

            self.assertFalse(review["source_evidence_valid"])
            self.assertIn("trace_semantics", review["missing_evidence"])
            evaluation = review["trace_validation"]["record_evaluations"][0]
            self.assertFalse(evaluation["action_target_valid"])
            self.assertIn(
                "selected_action.params.chapter_id",
                evaluation["action_target_issues"],
            )

    def test_weak_global_and_wrong_identity_deltas_are_rejected(self) -> None:
        cases = [
            (
                "recruit_soldiers",
                {"team_id": "guard-1"},
                {
                    "path": "economy.reserve_troops",
                    "operator": "less_than_before",
                    "before": 40000,
                    "after": 39000,
                },
            ),
            (
                "upgrade_building",
                {
                    "building_name": "Main Hall",
                    "current_level": 10,
                    "target_level": 11,
                },
                {
                    "path": "economy.resources.wood",
                    "operator": "less_than_before",
                    "before": 900000,
                    "after": 780000,
                },
            ),
            (
                "recruit_soldiers",
                {"team_id": "guard-1"},
                {
                    "selector": {
                        "collection_path": "teams",
                        "identity_field": "team_id",
                        "identity_value": "guard-2",
                    },
                    "path": "soldiers",
                    "operator": "greater_than_before",
                    "before": 22000,
                    "after": 23000,
                },
            ),
            *[
                (
                    "recruit_soldiers",
                    {"team_id": "guard-1"},
                    {
                        "selector": {
                            "collection_path": "teams",
                            "identity_field": "team_id",
                            "identity_value": "guard-1",
                        },
                        "path": "recruit_finish_time",
                        "operator": "becomes_present",
                        "before": None,
                        "after": invalid_after,
                    },
                )
                for invalid_after in (False, 0, "   ")
            ],
        ]
        for action_type, target_identity, delta in cases:
            with self.subTest(action_type=action_type, delta=delta):
                validation = _post_action_delta_validation(
                    [delta],
                    requirement=LOW_RISK_TERMINAL_SOURCE_REQUIREMENTS[action_type],
                    target_identity=target_identity,
                )
                self.assertFalse(validation["valid"])
                self.assertIn(
                    "delta[0].target_bound_contract",
                    validation["issues"],
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
