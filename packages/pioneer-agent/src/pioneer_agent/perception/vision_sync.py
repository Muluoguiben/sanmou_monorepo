"""Glue layer: screenshot → page-appropriate domain extractors → RuntimeState merge.

Picks which domain extractors to run based on the detected `page_type` from
the cheap resource_bar call, so we don't invoke the expensive city-buildings
extractor on every screenshot (e.g. while on the main map).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import (
    apply_city_buildings,
    apply_resource_bar,
    extract_city_buildings,
    extract_resource_bar,
)
from pioneer_agent.perception.vision import VisionClient


@dataclass
class VisionSyncSummary:
    page_type: str | None
    domains_run: list[str]
    notes: list[str]


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
        domains: list[str] = []
        notes: list[str] = []

        # Always run resource_bar — it also detects page_type cheaply.
        res_fragment = extract_resource_bar(image, client=self.client, captured_at=captured_at)
        state = apply_resource_bar(state, res_fragment)
        domains.append("resource_bar")

        page = res_fragment.page_type
        if res_fragment.notes:
            notes.extend(res_fragment.notes)

        if page == "city":
            city_fragment = extract_city_buildings(
                image, client=self.client, captured_at=captured_at
            )
            state = apply_city_buildings(state, city_fragment)
            domains.append("city_buildings")
            if city_fragment.notes:
                notes.extend(city_fragment.notes)

        return state, VisionSyncSummary(page_type=page, domains_run=domains, notes=notes)
