"""Glue layer: screenshot → page-appropriate domain extractors → RuntimeState merge.

Picks which domain extractors to run based on the detected `page_type` from
the cheap resource_bar call, so we don't invoke the expensive city-buildings
extractor on every screenshot (e.g. while on the main map).
"""
from __future__ import annotations

import hashlib
from copy import deepcopy
from dataclasses import dataclass, field
from datetime import UTC, datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from PIL import Image, UnidentifiedImageError

from pioneer_agent.core.models import CaptureGeometry, ObservationSnapshot, RuntimeState
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
    unknown_domains: list[str] = field(default_factory=list)
    image_traces: list[dict[str, Any]] = field(default_factory=list)
    observation: ObservationSnapshot | None = None

    def __post_init__(self) -> None:
        overlap = set(self.domains_run).intersection(self.unknown_domains)
        if overlap:
            raise ValueError(
                "vision domains cannot be both completed and unknown: "
                + ", ".join(sorted(overlap))
            )


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
        capture_geometry: CaptureGeometry | None = None,
    ) -> tuple[RuntimeState, VisionSyncSummary]:
        state = state or RuntimeState()
        captured_at = captured_at or datetime.now(UTC)
        frame_bytes = image.read_bytes() if isinstance(image, Path) else image
        frame_sha256 = hashlib.sha256(frame_bytes).hexdigest()
        observation_id = hashlib.sha256(
            frame_bytes + b"\0" + captured_at.isoformat().encode("utf-8")
        ).hexdigest()
        frame_size = _frame_size(frame_bytes)
        _reset_vision_trace_events(self.client)
        domains: list[str] = []
        unknown_domains: list[str] = []
        notes: list[str] = []
        observed_state = RuntimeState()

        def record(fragment: Any) -> Any:
            nonlocal observed_state
            _tag_fragment_observation(fragment, observation_id)
            observed_state = _merge_observed_fragment(observed_state, fragment)
            return fragment

        # Always run resource_bar — it also detects page_type cheaply.
        res_fragment = record(
            extract_resource_bar(frame_bytes, client=self.client, captured_at=captured_at)
        )
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
            popup_fragment = record(
                extract_popup(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_popup(state, popup_fragment)
            domains.append("popup")
            if popup_fragment.notes:
                notes.extend(popup_fragment.notes)
            if state.global_state.get("popup", {}).get("blocking"):
                # A blocking overlay makes prior map targets non-actionable even
                # when the outer classifier still calls the page main_map.
                state = expire_map_land_candidates(state, captured_at=captured_at)
                return state, self._summary(
                    page=page,
                    domains=domains,
                    unknown_domains=unknown_domains,
                    notes=notes,
                    observation_id=observation_id,
                    captured_at=captured_at,
                    frame_sha256=frame_sha256,
                    frame_size=frame_size,
                    capture_geometry=capture_geometry,
                    observed_state=observed_state,
                )

        if page == "chapter":
            chapter_fragment = record(
                extract_chapter_panel(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_chapter_panel(state, chapter_fragment)
            domains.append("chapter_panel")
            if chapter_fragment.notes:
                notes.extend(chapter_fragment.notes)

        if page == "recruit":
            recruit_fragment = record(
                extract_recruit_panel(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_recruit_panel(state, recruit_fragment)
            domains.append("recruit_panel")
            if recruit_fragment.notes:
                notes.extend(recruit_fragment.notes)

        if page == "main_map":
            map_fragment = extract_map_land(
                frame_bytes,
                client=self.client,
                captured_at=captured_at,
            )
            if map_fragment.parse_status == "observed":
                map_fragment = record(map_fragment)
                state = apply_map_land(state, map_fragment)
                domains.append("map_land")
            else:
                # The route classifier saw the main map, but the secondary
                # parser did not. Fail-close actionable candidates without
                # publishing a trusted empty map/filter observation.
                state = expire_map_land_candidates(state, captured_at=captured_at)
                unknown_domains.append("map_land")
            if map_fragment.notes:
                notes.extend(map_fragment.notes)

        if page == "battle":
            battle_fragment = record(
                extract_battle_report(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_battle_report(state, battle_fragment)
            domains.append("battle_report")
            if battle_fragment.notes:
                notes.extend(battle_fragment.notes)

        if page in {"building", "upgrade_dialog"}:
            upgrade_fragment = record(
                extract_upgrade_dialog(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_upgrade_dialog(state, upgrade_fragment)
            domains.append("upgrade_dialog")
            if upgrade_fragment.notes:
                notes.extend(upgrade_fragment.notes)

        if page in {"event_tournament", "mode_hub"}:
            mode_fragment = record(
                extract_mode_hub(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_mode_hub(state, mode_fragment)
            domains.append("mode_hub")
            if mode_fragment.notes:
                notes.extend(mode_fragment.notes)

        if page == "city":
            city_fragment = record(
                extract_city_buildings(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_city_buildings(state, city_fragment)
            domains.append("city_buildings")
            if city_fragment.notes:
                notes.extend(city_fragment.notes)

        if page in {"team", "team_panel", "lineup", "lineup_config"}:
            team_fragment = record(
                extract_team_panel(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_team_panel(state, team_fragment)
            domains.append("team_panel")
            if team_fragment.notes:
                notes.extend(team_fragment.notes)

        if page in {"hero_detail", "tactic_detail", "equipment_mount", "formation_books"}:
            detail_fragment = record(
                extract_team_detail(frame_bytes, client=self.client, captured_at=captured_at)
            )
            state = apply_team_detail(state, detail_fragment)
            domains.append("team_detail")
            if detail_fragment.notes:
                notes.extend(detail_fragment.notes)

        return state, self._summary(
            page=page,
            domains=domains,
            unknown_domains=unknown_domains,
            notes=notes,
            observation_id=observation_id,
            captured_at=captured_at,
            frame_sha256=frame_sha256,
            frame_size=frame_size,
            capture_geometry=capture_geometry,
            observed_state=observed_state,
        )

    def _summary(
        self,
        *,
        page: str | None,
        domains: list[str],
        unknown_domains: list[str],
        notes: list[str],
        observation_id: str,
        captured_at: datetime,
        frame_sha256: str,
        frame_size: tuple[int, int] | None,
        capture_geometry: CaptureGeometry | None,
        observed_state: RuntimeState,
    ) -> VisionSyncSummary:
        return VisionSyncSummary(
            page_type=page,
            domains_run=domains,
            notes=notes,
            unknown_domains=unknown_domains,
            image_traces=_consume_vision_trace_events(self.client),
            observation=ObservationSnapshot(
                observation_id=observation_id,
                captured_at=captured_at,
                frame_sha256=frame_sha256,
                frame_size=frame_size,
                capture_geometry=capture_geometry,
                page_type=page,
                domains_run=list(domains),
                unknown_domains=list(unknown_domains),
                observed_state=observed_state,
                source="vision_sync",
            ),
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


def _tag_fragment_observation(fragment: Any, observation_id: str) -> None:
    field_meta = getattr(fragment, "field_meta", None)
    if not isinstance(field_meta, dict):
        return
    for key, meta in tuple(field_meta.items()):
        if hasattr(meta, "model_copy"):
            field_meta[key] = meta.model_copy(
                update={"observation_id": observation_id}
            )


def _merge_observed_fragment(
    state: RuntimeState,
    fragment: Any,
) -> RuntimeState:
    payload = state.model_dump(mode="python")
    for field_name in RuntimeState.model_fields:
        if field_name == "field_meta" or not hasattr(fragment, field_name):
            continue
        value = getattr(fragment, field_name)
        if isinstance(value, dict):
            current = payload.get(field_name)
            payload[field_name] = _deep_merge_dict(
                current if isinstance(current, dict) else {},
                value,
            )
        elif isinstance(value, list):
            payload[field_name] = deepcopy(value)

    fragment_meta = getattr(fragment, "field_meta", None)
    if isinstance(fragment_meta, dict):
        payload["field_meta"].update(deepcopy(fragment_meta))
    return RuntimeState.model_validate(payload)


def _deep_merge_dict(
    left: dict[str, Any],
    right: dict[str, Any],
) -> dict[str, Any]:
    merged = deepcopy(left)
    for key, value in right.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge_dict(merged[key], value)
        else:
            merged[key] = deepcopy(value)
    return merged


def _frame_size(frame_bytes: bytes) -> tuple[int, int] | None:
    try:
        with Image.open(BytesIO(frame_bytes)) as image:
            return image.width, image.height
    except (UnidentifiedImageError, OSError):
        return None
