"""Tests for VisionSync — page-conditional domain routing."""
from __future__ import annotations

import hashlib
import io
import unittest
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from PIL import Image

from pioneer_agent.core.models import FieldMeta, RuntimeState
from pioneer_agent.perception.vision_sync import VisionSync


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _ScriptedVisionClient:
    """Returns a different payload for each extraction, in order of schema type."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.calls: list[str] = []

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        instruction_lower = instruction.lower()
        if "explicitly classified as the main_map page" in instruction_lower:
            self.calls.append("map_land")
            return _StubResult(data=self._payloads[len(self.calls) - 1])
        if "explicitly classified as the battle page" in instruction_lower:
            self.calls.append("battle_report")
            return _StubResult(data=self._payloads[len(self.calls) - 1])
        # Differentiate by instruction prefix — cheap and accurate enough for tests.
        if "mode hub" in instruction.lower() or "演武大会" in instruction or "征战入口" in instruction:
            kind = "mode_hub"
        elif "building upgrade confirmation" in instruction.lower() or "建筑升级确认框" in instruction:
            kind = "upgrade_dialog"
        elif "popup" in instruction.lower() or "弹窗" in instruction or "dialog" in instruction.lower():
            kind = "popup"
        elif "chapter task panel" in instruction.lower() or "章节" in instruction:
            kind = "chapter_panel"
        elif "recruitment/soldier panel" in instruction.lower() or "征兵" in instruction:
            kind = "recruit_panel"
        elif "resource" in instruction.lower() or "top bar" in instruction.lower() or "page type" in instruction.lower():
            kind = "resource_bar"
        elif "城内" in instruction or "city" in instruction.lower() or "building" in instruction.lower():
            kind = "city_buildings"
        elif "detail screenshot" in instruction.lower() or "装备, 马匹" in instruction:
            kind = "team_detail"
        elif "部队" in instruction or "team" in instruction.lower() or "lineup" in instruction.lower():
            kind = "team_panel"
        else:
            kind = "other"
        self.calls.append(kind)
        return _StubResult(data=self._payloads[len(self.calls) - 1])


class VisionSyncTests(unittest.TestCase):
    def test_path_input_is_read_once_and_all_extractors_receive_same_bytes(self) -> None:
        original_buffer = io.BytesIO()
        replacement_buffer = io.BytesIO()
        Image.new("RGB", (320, 180), (1, 2, 3)).save(original_buffer, format="PNG")
        Image.new("RGB", (640, 360), (4, 5, 6)).save(replacement_buffer, format="PNG")
        original = original_buffer.getvalue()
        replacement = replacement_buffer.getvalue()

        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "watch.png"
            path.write_bytes(original)

            class _MutatingClient(_ScriptedVisionClient):
                def __init__(self) -> None:
                    super().__init__(
                        [
                            {"page_type": "city", "resources": {}, "visible_notes": []},
                            {"buildings": [], "visible_notes": []},
                        ]
                    )
                    self.frames: list[bytes] = []

                def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
                    frame = image.read_bytes() if isinstance(image, Path) else image
                    self.frames.append(frame)
                    if len(self.frames) == 1:
                        path.write_bytes(replacement)
                    return super().extract(image, instruction, response_schema, **kwargs)

            client = _MutatingClient()
            _state, summary = VisionSync(client).sync(path, RuntimeState())

        assert summary.observation is not None
        self.assertEqual(client.frames, [original, original])
        self.assertEqual(summary.observation.frame_sha256, hashlib.sha256(original).hexdigest())
        self.assertEqual(summary.observation.frame_size, (320, 180))

    def test_summary_carries_same_frame_observation_without_deduping_entities(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "city",
                    "resources": {"wood": 100},
                    "visible_notes": [],
                },
                {
                    "buildings": [
                        {"name": "Main Hall", "level": 10},
                        {"name": "Main Hall", "level": 9},
                    ],
                    "visible_notes": [],
                },
            ]
        )
        buffer = io.BytesIO()
        Image.new("RGB", (320, 180), (0, 0, 0)).save(buffer, format="PNG")
        frame = buffer.getvalue()
        captured_at = datetime(2026, 7, 10, 8, 0, tzinfo=UTC)

        _state, summary = VisionSync(client).sync(
            frame,
            RuntimeState(),
            captured_at=captured_at,
        )

        observation = summary.observation
        self.assertIsNotNone(observation)
        assert observation is not None
        self.assertEqual(observation.frame_sha256, hashlib.sha256(frame).hexdigest())
        self.assertEqual(observation.frame_size, (320, 180))
        self.assertEqual(observation.captured_at, captured_at)
        self.assertEqual(observation.domains_run, ["resource_bar", "city_buildings"])
        self.assertEqual(len(observation.observed_state.city["buildings"]), 2)
        for meta_key in ("global_state", "economy", "city"):
            meta = observation.observed_state.field_meta[meta_key]
            self.assertEqual(meta.observation_id, observation.observation_id)
            self.assertEqual(meta.updated_at, captured_at)

    def test_main_map_runs_map_land_from_explicit_page_type(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "main_map",
                    "resources": {"copper": 100},
                    "visible_notes": ["banner"],
                },
                {
                    "page_type": "main_map",
                    "filter_panel_visible": False,
                    "resource_filter_enabled": False,
                    "selected_resource_types": [],
                    "selected_levels": [],
                    "filter_button_visible": False,
                    "filter_button_enabled": False,
                    "apply_button_visible": False,
                    "apply_button_enabled": False,
                    "resource_toggles": [],
                    "level_toggles": [],
                    "lands": [],
                    "visible_notes": [],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png", state=RuntimeState())
        self.assertEqual(summary.page_type, "main_map")
        self.assertEqual(summary.domains_run, ["resource_bar", "map_land"])
        self.assertEqual(client.calls, ["resource_bar", "map_land"])
        self.assertEqual(state.global_state.get("page_type"), "main_map")
        self.assertIn("banner", summary.notes)

    def test_battle_page_runs_report_parser_but_does_not_verify_action(self) -> None:
        client = _ScriptedVisionClient(
            [
                {"page_type": "battle", "resources": {}, "visible_notes": []},
                {
                    "page_type": "battle",
                    "result": "win",
                    "occupation_result": "unknown",
                    "attacker_heroes": [],
                    "defender_heroes": [],
                    "key_events": [],
                    "visible_sections": [],
                    "visible_notes": [],
                },
            ]
        )
        state, summary = VisionSync(client).sync(b"png")

        self.assertEqual(summary.domains_run, ["resource_bar", "battle_report"])
        self.assertEqual(client.calls, ["resource_bar", "battle_report"])
        verification = state.map_state["battle_report_verification"]
        self.assertFalse(verification["action_verification_ready"])
        self.assertEqual(verification["verifier_status"], "unverified")

    def test_battle_route_with_unknown_secondary_parse_preserves_prior_report(self) -> None:
        client = _ScriptedVisionClient(
            [
                {"page_type": "battle", "resources": {}, "visible_notes": []},
                {
                    "page_type": "unknown",
                    "result": "unknown",
                    "occupation_result": "unknown",
                    "attacker_heroes": [],
                    "defender_heroes": [],
                    "key_events": [],
                    "visible_sections": [],
                    "visible_notes": [],
                },
            ]
        )
        previous = RuntimeState(
            map_state={
                "latest_battle_report": {"report_id": "prior"},
                "battle_reports": [{"report_id": "prior"}],
            }
        )

        state, summary = VisionSync(client).sync(b"png", state=previous)

        self.assertEqual(summary.domains_run, ["resource_bar", "battle_report"])
        self.assertEqual(client.calls, ["resource_bar", "battle_report"])
        self.assertEqual(state.map_state["latest_battle_report"]["report_id"], "prior")
        self.assertEqual(state.map_state["battle_reports"], [{"report_id": "prior"}])

    def test_city_page_also_runs_city_buildings(self) -> None:
        client = _ScriptedVisionClient(
            [
                {"page_type": "city", "resources": {}},
                {
                    "prosperity": 165883,
                    "territory": "60/60",
                    "buildings": [{"name": "征兵所", "level": 10}],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.page_type, "city")
        self.assertEqual(summary.domains_run, ["resource_bar", "city_buildings"])
        self.assertEqual(client.calls, ["resource_bar", "city_buildings"])
        self.assertEqual(state.city.get("prosperity"), 165883)
        self.assertEqual(len(state.city.get("buildings", [])), 1)

    def test_unknown_page_stops_after_resource_bar(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "unknown",
                    "resources": {},
                    "visible_notes": ["land-like words must not trigger routing"],
                }
            ]
        )
        sync = VisionSync(client)
        _state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar"])
        self.assertEqual(client.calls, ["resource_bar"])

    def test_non_map_snapshot_clears_ephemeral_candidate_lands(self) -> None:
        client = _ScriptedVisionClient(
            [{"page_type": "unknown", "resources": {}, "visible_notes": []}]
        )
        previous = RuntimeState(
            map_state={
                "candidate_lands": [{"land_id": "stale"}],
                "candidate_land_count": 1,
                "visible_lands": [{"land_id": "historical"}],
            }
        )

        state, _summary = VisionSync(client).sync(b"png", state=previous)

        self.assertEqual(state.map_state["candidate_lands"], [])
        self.assertEqual(state.map_state["candidate_land_count"], 0)
        self.assertEqual(state.map_state["visible_lands"], [{"land_id": "historical"}])

    def test_older_non_map_snapshot_does_not_expire_newer_candidates(self) -> None:
        client = _ScriptedVisionClient(
            [{"page_type": "unknown", "resources": {}, "visible_notes": []}]
        )
        previous = RuntimeState(
            map_state={
                "candidate_lands": [{"land_id": "newer"}],
                "candidate_land_count": 1,
            },
            field_meta={
                "map_state.candidate_lands": FieldMeta(
                    value=1,
                    source="vision.map_land",
                    updated_at=datetime(2026, 7, 10, 12, 0, 1),
                )
            },
        )

        state, _summary = VisionSync(client).sync(
            b"png",
            state=previous,
            captured_at=datetime(2026, 7, 10, 12, 0, 0),
        )

        self.assertEqual(state.map_state["candidate_lands"], [{"land_id": "newer"}])

    def test_mixed_timezone_main_map_cannot_replace_prior_candidate_watermark(self) -> None:
        client = _ScriptedVisionClient(
            [
                {"page_type": "main_map", "resources": {}, "visible_notes": []},
                {
                    "page_type": "main_map",
                    "filter_panel_visible": False,
                    "resource_filter_enabled": False,
                    "selected_resource_types": [],
                    "selected_levels": [],
                    "filter_button_visible": False,
                    "filter_button_enabled": False,
                    "apply_button_visible": False,
                    "apply_button_enabled": False,
                    "resource_toggles": [],
                    "level_toggles": [],
                    "lands": [
                        {
                            "land_id": "ambiguous",
                            "level": 6,
                            "resource_type": "stone",
                            "occupied": False,
                            "protected": False,
                            "reachable": True,
                            "can_attack": True,
                            "x_min": 400,
                            "y_min": 420,
                            "x_max": 500,
                            "y_max": 520,
                        }
                    ],
                    "visible_notes": [],
                },
            ]
        )
        previous = RuntimeState(
            map_state={
                "candidate_lands": [{"land_id": "aware-prior"}],
                "candidate_land_count": 1,
            },
            field_meta={
                "map_state.candidate_lands": FieldMeta(
                    value=1,
                    source="vision.map_land",
                    updated_at=datetime(2026, 7, 10, 4, 0, tzinfo=timezone.utc),
                )
            },
        )

        state, _summary = VisionSync(client).sync(
            b"png",
            state=previous,
            captured_at=datetime(2026, 7, 10, 13, 0),
        )

        self.assertEqual(state.map_state["candidate_lands"], [{"land_id": "aware-prior"}])

    def test_popup_note_runs_popup_detector(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "chapter",
                    "resources": {},
                    "visible_notes": ["发现确认弹窗"],
                },
                {
                    "popup_visible": True,
                    "popup_type": "confirmation",
                    "title": "确认",
                    "blocking": True,
                    "safe_default_action": "cancel",
                    "buttons": [{"label": "取消", "role": "cancel"}],
                    "visible_notes": ["确认框"],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar", "popup"])
        self.assertEqual(client.calls, ["resource_bar", "popup"])
        self.assertTrue(state.global_state["popup"]["visible"])
        self.assertEqual(state.global_state["popup"]["safe_default_action"], "cancel")
        self.assertIn("确认框", summary.notes)

    def test_chapter_page_runs_chapter_panel(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "chapter",
                    "resources": {},
                    "visible_notes": ["章节任务"],
                },
                {
                    "current_chapter_id": 3,
                    "current_chapter_title": "开疆拓土",
                    "chapter_claimable": True,
                    "claim_button_visible": True,
                    "claim_button_enabled": True,
                    "claim_x_min": 700,
                    "claim_y_min": 800,
                    "claim_x_max": 900,
                    "claim_y_max": 900,
                    "tasks": [{"name": "占领 4 级地", "completed": True}],
                    "visible_notes": ["奖励可领"],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar", "chapter_panel"])
        self.assertEqual(client.calls, ["resource_bar", "chapter_panel"])
        self.assertTrue(state.progress["chapter_claimable"])
        self.assertEqual(state.progress["current_chapter_id"], 3)
        self.assertIn("奖励可领", summary.notes)

    def test_recruit_page_runs_recruit_panel(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "recruit",
                    "resources": {},
                    "visible_notes": ["征兵"],
                },
                {
                    "reserve_troops": 9000,
                    "teams": [
                        {
                            "team_id": "部队一",
                            "soldiers": 24000,
                            "max_soldiers": 30000,
                            "recruit_button_visible": True,
                            "recruit_button_enabled": True,
                            "button_x_min": 760,
                            "button_y_min": 820,
                            "button_x_max": 920,
                            "button_y_max": 900,
                        }
                    ],
                    "visible_notes": ["可征兵"],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar", "recruit_panel"])
        self.assertEqual(client.calls, ["resource_bar", "recruit_panel"])
        self.assertEqual(state.economy["reserve_troops"], 9000)
        self.assertEqual(state.teams[0]["soldier_deficit"], 6000)
        self.assertIn("可征兵", summary.notes)

    def test_upgrade_dialog_page_runs_upgrade_dialog(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "upgrade_dialog",
                    "resources": {},
                    "visible_notes": ["建筑升级确认框"],
                },
                {
                    "dialog_visible": True,
                    "building_name": "征兵所",
                    "current_level": 9,
                    "next_level": 10,
                    "can_upgrade": False,
                    "cannot_upgrade_reason": "石料不足",
                    "costs": [{"name": "石料", "required": 12000, "available": 8000, "enough": False}],
                    "confirm_button_visible": True,
                    "confirm_button_enabled": False,
                    "confirm_x_min": 720,
                    "confirm_y_min": 820,
                    "confirm_x_max": 920,
                    "confirm_y_max": 900,
                    "close_button_visible": True,
                    "close_x_min": 930,
                    "close_y_min": 80,
                    "close_x_max": 980,
                    "close_y_max": 140,
                    "visible_notes": ["资源不足"],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar", "upgrade_dialog"])
        self.assertEqual(client.calls, ["resource_bar", "upgrade_dialog"])
        self.assertEqual(state.city["upgrade_dialog"]["building_name"], "征兵所")
        self.assertFalse(state.city["upgrade_dialog"]["can_upgrade"])
        self.assertEqual(state.city["upgrade_dialog"]["confirm_button"]["bbox"]["x_min"], 720)
        self.assertIn("资源不足", summary.notes)

    def test_event_tournament_page_runs_mode_hub(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "event_tournament",
                    "resources": {},
                    "visible_notes": ["演武大会"],
                },
                {
                    "page_type": "event_tournament",
                    "title": "演武大会",
                    "active_tab": "征战",
                    "entries": [
                        {
                            "name": "演武大会",
                            "status": "available",
                            "can_enter": True,
                            "can_register": True,
                            "button_label": "前往",
                        }
                    ],
                    "total_score": 1280,
                    "rank": 36,
                    "visible_notes": ["可报名"],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar", "mode_hub"])
        self.assertEqual(client.calls, ["resource_bar", "mode_hub"])
        self.assertEqual(state.global_state["event_tournament"]["title"], "演武大会")
        self.assertTrue(state.global_state["event_tournament"]["entries"][0]["can_enter"])
        self.assertIn("可报名", summary.notes)

    def test_team_page_runs_team_panel(self) -> None:
        client = _ScriptedVisionClient(
            [
                {"page_type": "team", "resources": {}, "visible_notes": ["部队总览"]},
                {
                    "page_type": "team_panel",
                    "team_id": "部队一",
                    "formation": "雁形阵",
                    "formation_active": True,
                    "bond_active": True,
                    "total_soldiers": 32725,
                    "max_soldiers": 33000,
                    "supply": 100,
                    "supply_max": 100,
                    "heroes": [
                        {"name": "祝融夫人", "level": 50, "soldiers": 10725, "max_soldiers": 11000},
                        {"name": "孟获", "level": 50, "soldiers": 11000, "max_soldiers": 11000},
                        {"name": "诸葛亮", "level": 50, "soldiers": 11000, "max_soldiers": 11000},
                    ],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar", "team_panel"])
        self.assertEqual(client.calls, ["resource_bar", "team_panel"])
        self.assertEqual(state.teams[0]["team_id"], "部队一")
        self.assertEqual(state.teams[0]["soldier_deficit"], 275)

    def test_hero_detail_page_runs_team_detail(self) -> None:
        client = _ScriptedVisionClient(
            [
                {"page_type": "hero_detail", "resources": {}, "visible_notes": ["武将详情"]},
                {
                    "page_type": "hero_detail",
                    "team_id": "部队一",
                    "detail_tabs_observed": ["装备", "马匹", "兵书", "属性加点", "战法等级", "兵种适性"],
                    "heroes": [
                        {
                            "name": "祝融夫人",
                            "attribute_points": {"武力": 30},
                            "equipment": [{"slot": "武器", "name": "南蛮刀"}],
                            "mount": {"name": "的卢"},
                            "books": [{"slot": "一", "name": "作战"}],
                            "tactic_details": [{"name": "南疆烈刃", "level": 10, "max_level": 10}],
                            "soldier_specialties": ["盾兵 S"],
                        }
                    ],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar", "team_detail"])
        self.assertEqual(client.calls, ["resource_bar", "team_detail"])
        self.assertEqual(state.teams[0]["team_id"], "部队一")
        self.assertEqual(state.teams[0]["missing_detail_tabs"], [])
        self.assertTrue(state.main_lineup["team_snapshot"]["pvp_pve_basis_ready"])


if __name__ == "__main__":
    unittest.main()
