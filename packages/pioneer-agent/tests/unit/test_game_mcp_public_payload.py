from __future__ import annotations

import asyncio
import json
import unittest

from pioneer_agent.agent_harness.contracts import InProcessMcpClient, structured_content, validate_game_response
from pioneer_agent.core.models import RuntimeState
from pioneer_agent.derivation.team_snapshot import evaluate_team_snapshot
from pioneer_agent.mcp_server.contracts import CONTRACT_VERSION, GAME_TOOL_ARGUMENTS
from pioneer_agent.mcp_server.privacy import MAX_PUBLIC_COLLECTION_ITEMS, project_runtime_state, project_risk
from pioneer_agent.mcp_server.server import create_server
from pioneer_agent.mcp_server.service import GameMCPService, ObservedAdvisorCycle
from pioneer_agent.perception.domains import map_land, battle_report, chapter_panel, resource_bar
from pioneer_agent.perception.vision.prompts import (
    MapLandDetection, BattleReportDetection, ChapterPanelDetection, PageDetection,
)
if __package__:
    from .test_game_mcp_service import _cycle, _CountingProvider
else:
    from test_game_mcp_service import _cycle, _CountingProvider


def domain_state():
    captured = _cycle().observation.captured_at
    state = RuntimeState()
    state.map_state.update(map_land._build_fragment(MapLandDetection.model_validate({
        "page_type": "main_map", "filter_panel_visible": True, "resource_filter_enabled": True,
        "selected_resource_types": ["stone"], "selected_levels": [5],
        "resource_toggles": [{"resource_type": "stone", "selected": True, "visible": True, "enabled": True,
                              "x_min": 1, "y_min": 1, "x_max": 10, "y_max": 10}],
        "lands": [{
            "land_id": "L5", "level": 5, "resource_type": "stone",
            "occupied": False, "occupation_pending": True, "occupation_countdown": "02:35",
            "protected": False, "reachable": True, "can_attack": False,
            "coordinate_x": 12, "coordinate_y": 34,
        }],
    }), captured_at=captured).map_state)
    state.map_state.update(battle_report._build_fragment(BattleReportDetection.model_validate({
        "page_type": "battle", "report_id": "report-5", "result": "win",
        "occupation_result": "unknown", "resource_type": "stone", "land_level": 5,
        "attacker_initial_soldiers": 1000, "attacker_remaining_soldiers": 900,
        "attacker_heroes": [{"name": "赵云", "level": 20, "initial_soldiers": 1000, "remaining_soldiers": 900}],
        "defender_heroes": [{"name": "守军", "level": 20}],
    }), captured_at=captured).map_state)
    state.progress.update(chapter_panel._build_fragment(ChapterPanelDetection.model_validate({
        "page_type": "chapter", "current_chapter_id": 5, "chapter_claimable": False,
        "tasks": [{"name": "占领五级地", "current": 1, "required": 2, "completed": False}],
    }), captured_at=captured).progress)
    resources = resource_bar._build_fragment(PageDetection.model_validate({
        "page_type": "main_map", "resources": {"stone": 123, "military_order": 4, "copper": 50},
    }), captured_at=captured)
    state.global_state.update(resources.global_state)
    state.economy.update(resources.economy)
    state.timing = {
        "next_action_ready_time": captured.isoformat(),
        "next_recruit_finish_time": None,
        "next_resource_threshold_times": {"stone": captured.isoformat()},
        "next_stamina_threshold_times": [{"team_id": "T1", "target_stamina": 20, "target_time": captured.isoformat()}],
    }
    return state


class GameMCPPublicPayloadTests(unittest.TestCase):
    def test_real_domain_builders_survive_service_and_canonical_consumer(self):
        state = domain_state()
        cycle = _cycle()
        action = cycle.report.available_actions[0].model_copy(update={
            "risk": {"level": "high", "confirmation_required": True},
            "params": {"resource_type": "stone", "occupation_pending": True},
        })
        cycle = ObservedAdvisorCycle(
            observation=cycle.observation.model_copy(update={"observed_state": state}),
            report=cycle.report.model_copy(update={
                "current_state": state, "available_actions": [action], "recommended_action": action,
                "risks": [action.risk],
            }),
        )
        provider = _CountingProvider(cycle)
        client = InProcessMcpClient(create_server(GameMCPService(observation_provider=provider)))

        async def exercise():
            responses = {}
            for name in ("observe_game", "get_runtime_state", "get_advisor_report", "list_action_candidates"):
                payload = structured_content(await client.call_tool(name, {}))
                validate_game_response(name, payload)
                responses[name] = payload
            return responses

        responses = asyncio.run(exercise())
        public = responses["get_runtime_state"]["runtime_state"]
        report = responses["get_advisor_report"]["advisor_report"]
        self.assertEqual(public, report["current_state"])
        self.assertEqual(public["map_state"]["map_land_filter"]["selected_resource_types"], ["stone"])
        self.assertEqual(public["map_state"]["visible_lands"][0]["occupation_countdown"], "02:35")
        self.assertTrue(public["map_state"]["visible_lands"][0]["occupation_pending"])
        self.assertFalse(public["map_state"]["visible_lands"][0]["occupied"])
        battle = public["map_state"]["latest_battle_report"]
        self.assertEqual(battle["attacker_losses"], 100)
        self.assertEqual(battle["occupation_result"], "unknown")
        self.assertEqual(battle["attacker_heroes"][0]["remaining_soldiers"], 900)
        self.assertFalse(battle["verification"]["action_verification_ready"])
        self.assertEqual(public["map_state"]["battle_report_verification"]["checks"]["occupation"], "unknown")
        self.assertEqual(public["progress"]["chapter_tasks"][0]["required"], 2)
        self.assertFalse(public["progress"]["chapter_tasks"][0]["completed"])
        self.assertEqual(public["economy"], state.economy)
        self.assertEqual(public["global_state"]["military_order"], 4)
        self.assertEqual(public["timing"], state.timing)
        candidate = responses["list_action_candidates"]["candidates"][0]
        self.assertEqual(candidate["risk"], {"level": "high", "confirmation_required": True})
        self.assertEqual(report["recommended_action"]["risk"], candidate["risk"])
        self.assertEqual(report["risks"], [candidate["risk"]])
        self.assertEqual(candidate["params"]["resource_type"], "stone")
        self.assertFalse(candidate["executable"])
        self.assertEqual(candidate["execution_authority"], "none")
        self.assertEqual(provider.calls, 1)
        self.assertEqual(CONTRACT_VERSION, "sanmou-game/v1")
        self.assertEqual(len(GAME_TOOL_ARGUMENTS), 7)
        self.assertEqual(GAME_TOOL_ARGUMENTS["evaluate_fixture"], {"fixture", "include_details"})

    def test_nested_domain_shapes_reject_private_and_misplaced_keys(self):
        state = domain_state()
        land = state.map_state["visible_lands"][0]
        land.update(owner="PRIVATE_OWNER", visible_notes=["PRIVATE_CHAT"], metadata={"name": "PRIVATE_META"})
        land["coordinate"]["resource_type"] = "PRIVATE_WRONG_DOMAIN"
        report = state.map_state["latest_battle_report"]
        report.update(attacker_name="PRIVATE_ACCOUNT", defender_name="PRIVATE_ACCOUNT",
                      key_events=["PRIVATE_CHAT"], visible_notes=["PRIVATE_CHAT"])
        report["verification"]["checks"]["name"] = "PRIVATE_WRONG_DOMAIN"
        report["attacker_heroes"][0]["equipment"] = [{"name": "PRIVATE_WRONG_DOMAIN"}]
        state.timing["next_action_ready_time"] = {"name": "PRIVATE_WRONG_TYPE"}
        state.economy["resources"]["stone"] = {"name": "PRIVATE_WRONG_TYPE"}
        state.progress["chapter_tasks"][0]["name"] = "file:///private/account"
        state.global_state["current_time"] = "C:\\Users\\Private\\frame.png"
        land["land_id"] = "A" * 256
        serialized = json.dumps(project_runtime_state(state), ensure_ascii=False)
        for private in ("PRIVATE_", "file://", "C:\\\\Users", "A" * 256, "metadata"):
            self.assertNotIn(private, serialized)
        self.assertNotIn("stone", project_runtime_state(state)["economy"]["resources"])

    def test_projection_bounds_collections_and_strings_and_preserves_unknown(self):
        state = domain_state()
        state.map_state["visible_lands"] *= MAX_PUBLIC_COLLECTION_ITEMS + 5
        state.progress["chapter_tasks"][0]["name"] = "任务" * 600
        state.timing["next_team_return_time"] = None
        public = project_runtime_state(state)
        self.assertEqual(len(public["map_state"]["visible_lands"]), MAX_PUBLIC_COLLECTION_ITEMS)
        self.assertEqual(len(public["progress"]["chapter_tasks"][0]["name"]), 500)
        self.assertIsNone(public["timing"]["next_team_return_time"])
        self.assertNotIn("visible_notes", public["map_state"]["visible_lands"][0])

    def test_deep_gear_and_readiness_are_preserved_without_arbitrary_metadata(self):
        team = {
            "team_id": "T1", "heroes": [{
                "name": "赵云", "equipment": [{
                    "name": "长枪", "attributes": {"武力": 18, "account": "PRIVATE"},
                }],
            }],
        }
        judgement = evaluate_team_snapshot(team)
        team["team_snapshot"] = {"readiness_judgement": judgement}
        public = project_runtime_state(RuntimeState(teams=[team]))["teams"][0]
        self.assertEqual(public["heroes"][0]["equipment"][0]["attributes"], {"武力": 18})
        self.assertEqual(public["team_snapshot"]["readiness_judgement"], judgement)
        risk = project_risk({
            "level": "high", "confirmation_required": True,
            "readiness_judgement": judgement,
            "summary": {"level": "PRIVATE"}, "metadata": {"summary": "PRIVATE"},
        })
        self.assertEqual(risk["readiness_judgement"], judgement)
        self.assertNotIn("PRIVATE", repr(risk))
        judgement["issues"][0]["message"] = "兵书/韬略 file:///private/account"
        self.assertNotIn("file:", repr(project_risk({"readiness_judgement": judgement})))


if __name__ == "__main__":
    unittest.main()
