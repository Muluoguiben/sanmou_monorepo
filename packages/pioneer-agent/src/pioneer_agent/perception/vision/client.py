"""Gemini-backed vision client for extracting structured game state from screenshots.

Design notes (from empirical testing against 三国·谋定天下 screenshots):
- Model `gemini-flash-latest` works for EU-region accounts; `gemini-2.0-flash` is
  blocked at the account level with 429 limit:0.
- Images >2MB stall the google-genai SDK; downscale to <=1280px width beforehand.
- `response_schema` + `response_mime_type="application/json"` gives reliable JSON.
"""
from __future__ import annotations

import io
import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from PIL import Image

logger = logging.getLogger(__name__)

DEFAULT_KEY_PATH = Path.home() / ".config" / "sanmou" / "gemini.key"
DEFAULT_MODEL = "gemini-flash-latest"
MAX_IMAGE_WIDTH = 1280
MAX_IMAGE_BYTES = 2 * 1024 * 1024


class VisionError(RuntimeError):
    """Raised when vision extraction fails after retries."""


@dataclass
class VisionResult:
    data: dict[str, Any]
    model: str
    prompt_tokens: int
    output_tokens: int
    elapsed_s: float


class VisionClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str = DEFAULT_MODEL,
        key_path: Path = DEFAULT_KEY_PATH,
    ) -> None:
        if api_key is None:
            api_key = key_path.read_text().strip()
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(
        self,
        image: bytes | Path,
        instruction: str,
        response_schema: dict[str, Any],
        *,
        temperature: float = 0.0,
        max_retries: int = 2,
        retry_backoff_s: float = 2.0,
    ) -> VisionResult:
        image_bytes = self._normalize_image(image)
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=response_schema,
            temperature=temperature,
        )
        contents = [
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            instruction,
        ]

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                resp = self._client.models.generate_content(
                    model=self._model,
                    contents=contents,
                    config=config,
                )
                elapsed = time.monotonic() - start
                data = json.loads(resp.text)
                usage = resp.usage_metadata
                return VisionResult(
                    data=data,
                    model=self._model,
                    prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                    elapsed_s=elapsed,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "vision attempt %d/%d failed: %s", attempt + 1, max_retries + 1, exc
                )
                if attempt < max_retries:
                    time.sleep(retry_backoff_s * (attempt + 1))

        raise VisionError(f"vision extraction failed after {max_retries + 1} attempts: {last_exc}") from last_exc

    @staticmethod
    def _normalize_image(image: bytes | Path) -> bytes:
        if isinstance(image, Path):
            raw = image.read_bytes()
        else:
            raw = image

        img = Image.open(io.BytesIO(raw))
        needs_resize = img.width > MAX_IMAGE_WIDTH or len(raw) > MAX_IMAGE_BYTES
        if not needs_resize:
            return raw

        ratio = MAX_IMAGE_WIDTH / img.width
        new_size = (MAX_IMAGE_WIDTH, int(img.height * ratio))
        resized = img.resize(new_size, Image.LANCZOS)
        buf = io.BytesIO()
        resized.save(buf, format="PNG", optimize=True)
        return buf.getvalue()
