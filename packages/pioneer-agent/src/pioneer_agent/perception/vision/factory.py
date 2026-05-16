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
    if selected.startswith("openai:"):
        from .openai_client import OpenAIVisionClient

        return OpenAIVisionClient(profile=selected.split(":", 1)[1])
    if selected in {"openai", "gpt"}:
        from .openai_client import OpenAIVisionClient

        return OpenAIVisionClient()
    if selected.startswith("gpt-5."):
        from .openai_client import OpenAIVisionClient

        return OpenAIVisionClient(model=selected)
    raise ValueError(
        f"unknown vision provider: {selected!r} (expected 'gemini', 'openai', "
        "'openai:<profile>', or a gpt-5.x model)"
    )
