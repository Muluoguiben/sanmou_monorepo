"""Extract the top-bar resource state from a game screenshot.

Maps Gemini's `PageDetection` output into a `RuntimeState` fragment targeting:
- `global_state.page_type`  — detected page
- `global_state.military_order` / `military_order_max` — 军令 current/cap
- `economy.resources.{wood,stone,iron,grain}` — four city resources
- `economy.currencies.{copper,gold_bead,yuanbao}` — spend currencies

Resource fixtures historically keep only the four materials under
`economy.resources`; we put soft currencies under a separate `currencies`
bucket so existing consumers keep working unchanged.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import FieldMeta

from ..vision import VisionClient
from ..vision.prompts import (
    PAGE_DETECTION_INSTRUCTION,
    PAGE_DETECTION_SCHEMA,
    PageDetection,
)

SOURCE_LABEL = "vision.resource_bar"
MATERIAL_KEYS = ("wood", "stone", "iron", "grain")
CURRENCY_KEYS = ("copper", "gold_bead", "yuanbao")


@dataclass
class ResourceBarFragment:
    """Partial RuntimeState update produced from a single screenshot."""

    page_type: str
    global_state: dict[str, Any] = field(default_factory=dict)
    economy: dict[str, Any] = field(default_factory=dict)
    field_meta: dict[str, FieldMeta] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)
    raw: PageDetection | None = None


def extract_resource_bar(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
    captured_at: datetime | None = None,
) -> ResourceBarFragment:
    """Run vision extraction and return a RuntimeState fragment.

    `client` is injectable for tests — pass a stub with a matching `.extract()`.
    """
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=PAGE_DETECTION_INSTRUCTION,
        response_schema=PAGE_DETECTION_SCHEMA,
    )
    parsed = PageDetection.model_validate(result.data)
    return _build_fragment(parsed, captured_at=captured_at)


def _build_fragment(
    parsed: PageDetection,
    *,
    captured_at: datetime | None,
) -> ResourceBarFragment:
    resources = parsed.resources

    global_state: dict[str, Any] = {"page_type": parsed.page_type}
    if resources.military_order is not None:
        global_state["military_order"] = resources.military_order
    if resources.military_order_max is not None:
        global_state["military_order_max"] = resources.military_order_max

    materials = {k: getattr(resources, k) for k in MATERIAL_KEYS if getattr(resources, k) is not None}
    currencies = {k: getattr(resources, k) for k in CURRENCY_KEYS if getattr(resources, k) is not None}

    economy: dict[str, Any] = {}
    if materials:
        economy["resources"] = materials
    if currencies:
        economy["currencies"] = currencies

    field_meta: dict[str, FieldMeta] = {}
    if global_state:
        field_meta["global_state"] = FieldMeta(
            value="loaded",
            confidence=0.9,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )
    if economy:
        field_meta["economy"] = FieldMeta(
            value="loaded",
            confidence=0.9,
            source=SOURCE_LABEL,
            updated_at=captured_at,
        )

    return ResourceBarFragment(
        page_type=parsed.page_type,
        global_state=global_state,
        economy=economy,
        field_meta=field_meta,
        notes=list(parsed.visible_notes),
        raw=parsed,
    )
