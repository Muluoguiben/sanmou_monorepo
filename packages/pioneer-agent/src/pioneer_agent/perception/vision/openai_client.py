"""OpenAI-compatible vision client for pioneer-agent perception.

The sub2api gateway used by this repo requires `reasoning_effort` and
`store:false` on every request. This client keeps the same `.extract(...)`
contract as the Gemini `VisionClient`, so resource extraction, city extraction,
and dynamic UI locating can switch providers without downstream changes.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import re
import time
from pathlib import Path
from typing import Any

import requests

from .client import VisionError, VisionResult
from .env import load_vision_env
from .image import prepare_image

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://45.76.98.138/v1"
DEFAULT_MODEL = "gpt-5.4"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_MAX_TOKENS = 1024


class OpenAIVisionClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        load_vision_env()
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise VisionError(
                "OPENAI_API_KEY not set (check packages/pioneer-agent/.env or packages/qa-agent/.env)"
            )
        self._api_key = api_key
        self._model = (
            model
            or os.environ.get("PIONEER_OPENAI_MODEL")
            or os.environ.get("OPENAI_VISION_MODEL")
            or DEFAULT_MODEL
        )
        self._base_url = (
            base_url
            or os.environ.get("PIONEER_OPENAI_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or DEFAULT_BASE_URL
        ).rstrip("/")
        self._reasoning_effort = (
            reasoning_effort
            or os.environ.get("PIONEER_OPENAI_REASONING_EFFORT")
            or os.environ.get("OPENAI_REASONING_EFFORT")
            or DEFAULT_REASONING_EFFORT
        )

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
        prepared = prepare_image(image)
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": DEFAULT_MAX_TOKENS,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You extract structured UI state from 三国·谋定天下 screenshots. "
                        "Return only valid JSON. Do not include markdown, comments, or explanations."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": _build_user_message(instruction, response_schema),
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": _to_data_uri(prepared.data, prepared.mime_type),
                            },
                        },
                    ],
                },
            ],
            "reasoning_effort": self._reasoning_effort,
            "store": False,
        }
        if temperature != 0.0:
            payload["temperature"] = temperature

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                response = requests.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=180,
                )
                response.raise_for_status()
                body = response.json()
                elapsed = time.monotonic() - start
                text = _extract_text(body)
                data = json.loads(_strip_json_fence(text))
                usage = body.get("usage", {}) or {}
                return VisionResult(
                    data=data if isinstance(data, dict) else {},
                    model=body.get("model", self._model),
                    prompt_tokens=usage.get("prompt_tokens", 0) or 0,
                    output_tokens=usage.get("completion_tokens", 0) or 0,
                    elapsed_s=elapsed,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "openai vision attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(retry_backoff_s * (attempt + 1))

        raise VisionError(
            f"openai vision extraction failed after {max_retries + 1} attempts: {last_exc}"
        ) from last_exc


def _build_user_message(instruction: str, response_schema: dict[str, Any]) -> str:
    schema = json.dumps(response_schema, ensure_ascii=False, indent=2)
    return (
        f"{instruction}\n\n"
        "Return JSON that matches this schema exactly. Omit unclear optional values rather than guessing.\n"
        f"{schema}"
    )


def _to_data_uri(data: bytes, mime_type: str) -> str:
    encoded = base64.b64encode(data).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def _extract_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    message = choices[0].get("message") or {}
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [part.get("text", "") for part in content if part.get("type") == "text"]
        return "\n".join(part for part in parts if part).strip()
    return ""


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", stripped, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return stripped
