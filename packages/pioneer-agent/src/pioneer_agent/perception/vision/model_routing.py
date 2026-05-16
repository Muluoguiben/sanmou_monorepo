"""Model routing profiles for screenshot perception.

The real-time Sanmou loop should not use the strongest/slowest model for every
tick. These profiles make the routing explicit and keep dense visual extraction,
normal state extraction, recovery, verifier, and offline eval from drifting into
one unreviewable default.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class VisionModelProfile:
    name: str
    model: str
    reasoning_effort: str
    max_tokens: int
    image_detail: str | None = None
    verbosity: str | None = None
    description: str = ""


PROFILES: dict[str, VisionModelProfile] = {
    "realtime": VisionModelProfile(
        name="realtime",
        model="gpt-5.4",
        reasoning_effort="low",
        max_tokens=1024,
        description=(
            "Default live-loop state extraction: page/domain classification, "
            "clear single-screen UI fields, and normal Advisor observations."
        ),
    ),
    "recovery": VisionModelProfile(
        name="recovery",
        model="gpt-5.4",
        reasoning_effort="medium",
        max_tokens=1500,
        image_detail="high",
        description=(
            "Unknown popup, contradictory state, or stuck-loop diagnosis. "
            "Still produces recommendations, not direct input."
        ),
    ),
    "verifier": VisionModelProfile(
        name="verifier",
        model="gpt-5.4",
        reasoning_effort="medium",
        max_tokens=1024,
        image_detail="high",
        description=(
            "Post-action verification when deterministic deltas are not enough. "
            "Runs independently from the actor path."
        ),
    ),
    "dense_table": VisionModelProfile(
        name="dense_table",
        model="gpt-5.4",
        reasoning_effort="high",
        max_tokens=2000,
        image_detail="original",
        verbosity="high",
        description=(
            "Dense small-text lineup/config tables. Crop to one table/column/row "
            "before using this profile. Prefer gpt-5.5 via env override when the "
            "gateway supports it."
        ),
    ),
    "eval": VisionModelProfile(
        name="eval",
        model="gpt-5.4",
        reasoning_effort="high",
        max_tokens=2000,
        image_detail="original",
        verbosity="high",
        description=(
            "Offline model/prompt/crop evaluation. Do not silently use this as a "
            "runtime default."
        ),
    ),
}

DEFAULT_PROFILE = "realtime"


def normalize_profile_name(value: str | None) -> str:
    if not value:
        return DEFAULT_PROFILE
    return value.strip().lower().replace("-", "_")


def get_vision_model_profile(name: str | None = None) -> VisionModelProfile:
    selected = normalize_profile_name(
        name
        or os.environ.get("PIONEER_VISION_MODEL_PROFILE")
        or os.environ.get("PIONEER_OPENAI_PROFILE")
    )
    try:
        return PROFILES[selected]
    except KeyError as exc:
        expected = ", ".join(sorted(PROFILES))
        raise ValueError(f"unknown vision model profile {selected!r}; expected one of: {expected}") from exc


def profile_names() -> tuple[str, ...]:
    return tuple(sorted(PROFILES))
