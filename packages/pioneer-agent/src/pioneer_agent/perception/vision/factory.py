from __future__ import annotations

import os
from typing import Protocol


class VisionExtractor(Protocol):
    def extract(
        self,
        image,
        instruction,
        response_schema,
        **kwargs,
    ):  # type: ignore[no-untyped-def]
        ...


def build_vision_client(provider: str | None = None) -> VisionExtractor:
    selected = (provider or os.environ.get("PIONEER_VISION_PROVIDER") or "gemini").lower()
    if selected == "gemini":
        from .client import VisionClient

        return VisionClient()
    if selected in {"openai", "gpt", "gpt-5.4"}:
        from .openai_client import OpenAIVisionClient

        return OpenAIVisionClient()
    raise ValueError(
        f"unknown vision provider: {selected!r} (expected 'gemini' or 'openai')"
    )
