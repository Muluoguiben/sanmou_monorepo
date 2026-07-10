"""Glue layer: screenshot → page-appropriate domain extractors → RuntimeState merge.

Picks which domain extractors to run based on the detected `page_type` from
the cheap resource_bar call, so we don't invoke the expensive city-buildings
extractor on every screenshot (e.g. while on the main map).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import (
    apply_battle_report,
    apply_chapter_panel,
    apply_city_buildings,
    apply_map_land,
    apply_mode_hub,
    apply_popup,
    apply_recruit_panel,
    apply_resource_bar,
    apply_team_detail,
    apply_team_panel,
    apply_upgrade_dialog,
    expire_map_land_candidates,
    extract_battle_report,
    extract_chapter_panel,
    extract_city_buildings,
    extract_map_land,
    extract_mode_hub,
    extract_popup,
    extract_recruit_panel,
    extract_resource_bar,
    extract_team_detail,
    extract_team_panel,
    extract_upgrade_dialog,
)
from pioneer_agent.perception.vision import VisionClient


@dataclass
class VisionSyncSummary:
    page_type: str | None
    domains_run: list[str]
    notes: list[str]
    image_traces: list[dict[str, Any]] = field(default_factory=list)


class VisionSync:
    """Run all vision extractors that apply to the current screenshot and merge."""

    def __init__(self, client: VisionClient) -> None:
        self.client = client

    def sync(
        self,
        image: bytes | Path,
        state: RuntimeState | None = None,
        *,
        captured_at: datetime | None = None,
    ) -> tuple[RuntimeState, VisionSyncSummary]:
        state = state or RuntimeState()
        captured_at = captured_at or datetime.now()
        _reset_vision_trace_events(self.client)
        domains: list[str] = []
        notes: list[str] = []

        # Always run resource_bar — it also detects page_type cheaply.
        res_fragment = extract_resource_bar(image, client=self.client, captured_at=captured_at)
        state = apply_resource_bar(state, res_fragment)
        domains.append("resource_bar")

        page = res_fragment.page_type
        if res_fragment.notes:
            notes.extend(res_fragment.notes)

        # Candidate lands are ephemeral on every non-map observation. A main-map
        # fragment must compare directly against the prior watermark: expiring it
        # first would erase timezone-ordering ambiguity and could re-enable stale
        # candidates with the same incomparable timestamp.
        if page != "main_map":
            state = expire_map_land_candidates(state, captured_at=captured_at)

        if page != "upgrade_dialog" and _should_run_popup_detector(res_fragment.notes):
            popup_fragment = extract_popup(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_popup(state, popup_fragment)
            domains.append("popup")
            if popup_fragment.notes:
                notes.extend(popup_fragment.notes)
            if state.global_state.get("popup", {}).get("blocking"):
                # A blocking overlay makes prior map targets non-actionable even
                # when the outer classifier still calls the page main_map.
                state = expire_map_land_candidates(state, captured_at=captured_at)
                return state, self._summary(page=page, domains=domains, notes=notes)

        if page == "chapter":
            chapter_fragment = extract_chapter_panel(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_chapter_panel(state, chapter_fragment)
            domains.append("chapter_panel")
            if chapter_fragment.notes:
                notes.extend(chapter_fragment.notes)

        if page == "recruit":
            recruit_fragment = extract_recruit_panel(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_recruit_panel(state, recruit_fragment)
            domains.append("recruit_panel")
            if recruit_fragment.notes:
                notes.extend(recruit_fragment.notes)

        if page == "main_map":
            map_fragment = extract_map_land(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_map_land(state, map_fragment)
            domains.append("map_land")
            if map_fragment.notes:
                notes.extend(map_fragment.notes)

        if page == "battle":
            battle_fragment = extract_battle_report(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_battle_report(state, battle_fragment)
            domains.append("battle_report")
            if battle_fragment.notes:
                notes.extend(battle_fragment.notes)

        if page in {"building", "upgrade_dialog"}:
            upgrade_fragment = extract_upgrade_dialog(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_upgrade_dialog(state, upgrade_fragment)
            domains.append("upgrade_dialog")
            if upgrade_fragment.notes:
                notes.extend(upgrade_fragment.notes)

        if page in {"event_tournament", "mode_hub"}:
            mode_fragment = extract_mode_hub(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_mode_hub(state, mode_fragment)
            domains.append("mode_hub")
            if mode_fragment.notes:
                notes.extend(mode_fragment.notes)

        if page == "city":
            city_fragment = extract_city_buildings(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_city_buildings(state, city_fragment)
            domains.append("city_buildings")
            if city_fragment.notes:
                notes.extend(city_fragment.notes)

        if page in {"team", "team_panel", "lineup", "lineup_config"}:
            team_fragment = extract_team_panel(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_team_panel(state, team_fragment)
            domains.append("team_panel")
            if team_fragment.notes:
                notes.extend(team_fragment.notes)

        if page in {"hero_detail", "tactic_detail", "equipment_mount", "formation_books"}:
            detail_fragment = extract_team_detail(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_team_detail(state, detail_fragment)
            domains.append("team_detail")
            if detail_fragment.notes:
                notes.extend(detail_fragment.notes)

        return state, self._summary(page=page, domains=domains, notes=notes)

    def _summary(
        self,
        *,
        page: str | None,
        domains: list[str],
        notes: list[str],
    ) -> VisionSyncSummary:
        return VisionSyncSummary(
            page_type=page,
            domains_run=domains,
            notes=notes,
            image_traces=_consume_vision_trace_events(self.client),
        )


def _should_run_popup_detector(notes: list[str]) -> bool:
    popup_markers = ("弹窗", "确认", "取消", "关闭", "奖励", "提示", "popup", "dialog")
    return any(
        marker in note.lower()
        for note in notes
        for marker in popup_markers
    )


def _reset_vision_trace_events(client: Any) -> None:
    reset = getattr(client, "reset_trace_events", None)
    if callable(reset):
        reset()


def _consume_vision_trace_events(client: Any) -> list[dict[str, Any]]:
    consume = getattr(client, "consume_trace_events", None)
    if not callable(consume):
        return []
    events = consume()
    return list(events) if events else []
