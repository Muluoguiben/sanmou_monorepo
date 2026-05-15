from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from pioneer_agent.perception.vision import VisionClient


class ScreenshotInterpretation(BaseModel):
    page_type: str = "unknown"
    summary: str = ""
    visible_text: list[str] = Field(default_factory=list)
    key_facts: list[str] = Field(default_factory=list)
    suggested_next_steps: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)


SCREENSHOT_INTERPRETATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "page_type": {
            "type": "string",
            "description": "Best-effort game page type, e.g. city, main_map, chapter, team, hero_list, battle_result, popup, unknown.",
        },
        "summary": {
            "type": "string",
            "description": "One concise Chinese sentence explaining what this screenshot shows.",
        },
        "visible_text": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Important visible Chinese UI text or numbers copied from the screenshot.",
        },
        "key_facts": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observed facts that are useful for a player decision.",
        },
        "suggested_next_steps": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Safe Advisor-only next steps; do not claim an action was executed.",
        },
        "risks": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Uncertainties, missing information, or risky decisions visible in the screenshot.",
        },
        "confidence": {
            "type": "number",
            "minimum": 0,
            "maximum": 1,
            "description": "Overall confidence in the interpretation.",
        },
    },
    "required": [
        "page_type",
        "summary",
        "visible_text",
        "key_facts",
        "suggested_next_steps",
        "risks",
        "confidence",
    ],
}


SCREENSHOT_INTERPRETATION_INSTRUCTION = (
    "You are reading one screenshot from the Chinese SLG game Sanmou / 三国：谋定天下. "
    "Return a practical Advisor interpretation for a player. "
    "Use Chinese for summary, visible_text, key_facts, suggested_next_steps, and risks. "
    "Focus only on what is visible. Do not invent hidden resources, teams, heroes, or results. "
    "If the image is unclear, say what is uncertain in risks and lower confidence. "
    "This is Advisor-only: recommend safe next checks or decisions, but never say that an action was clicked or executed."
)


def interpret_screenshot(
    image: bytes | Path,
    *,
    client: VisionClient | None = None,
) -> ScreenshotInterpretation:
    vision = client or VisionClient()
    result = vision.extract(
        image=image,
        instruction=SCREENSHOT_INTERPRETATION_INSTRUCTION,
        response_schema=SCREENSHOT_INTERPRETATION_SCHEMA,
    )
    return ScreenshotInterpretation.model_validate(result.data)
