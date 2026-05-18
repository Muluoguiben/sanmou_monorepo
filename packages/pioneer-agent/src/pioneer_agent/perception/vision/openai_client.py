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
from .model_routing import get_vision_model_profile

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://45.76.98.138/v1"
# Model / reasoning defaults now live in model_routing.PROFILES (the realtime
# profile is the runtime default). Only the max-tokens floor remains here as a
# last-resort fallback when neither env nor profile supplies one.
DEFAULT_MAX_TOKENS = 1024
# Soft cap so a long-lived client that never consume_trace_events() can't grow
# the trace buffer without bound; oldest events are dropped first.
TRACE_EVENT_CAP = 256


class OpenAIVisionClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
        profile: str | None = None,
        image_detail: str | None = None,
        max_tokens: int | None = None,
        verbosity: str | None = None,
    ) -> None:
        load_vision_env()
        selected_profile = get_vision_model_profile(profile)
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise VisionError(
                "OPENAI_API_KEY not set (check packages/pioneer-agent/.env or packages/qa-agent/.env)"
            )
        self._api_key = api_key
        self._profile = selected_profile
        self._model = (
            model
            or os.environ.get("PIONEER_OPENAI_MODEL")
            or os.environ.get("OPENAI_VISION_MODEL")
            or selected_profile.model
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
            or selected_profile.reasoning_effort
        )
        self._image_detail = (
            image_detail
            or os.environ.get("PIONEER_OPENAI_IMAGE_DETAIL")
            or selected_profile.image_detail
        )
        self._max_tokens = (
            max_tokens
            if max_tokens is not None
            else _int_env("PIONEER_OPENAI_MAX_TOKENS")
            or selected_profile.max_tokens
            or DEFAULT_MAX_TOKENS
        )
        self._verbosity = (
            verbosity
            or os.environ.get("PIONEER_OPENAI_VERBOSITY")
            or selected_profile.verbosity
        )
        self._trace_events: list[dict[str, Any]] = []

    def reset_trace_events(self) -> None:
        self._trace_events.clear()

    def consume_trace_events(self) -> list[dict[str, Any]]:
        events = list(self._trace_events)
        self._trace_events.clear()
        return events

    def extract(
        self,
        image: bytes | Path,
        instruction: str,
        response_schema: dict[str, Any],
        *,
        temperature: float = 0.0,
        max_retries: int = 2,
        retry_backoff_s: float = 2.0,
        reasoning_effort: str | None = None,
        image_detail: str | None = None,
        max_tokens: int | None = None,
        verbosity: str | None = None,
    ) -> VisionResult:
        prepared = prepare_image(image)
        detail = image_detail if image_detail is not None else self._image_detail
        image_url: dict[str, Any] = {
            "url": _to_data_uri(prepared.data, prepared.mime_type),
        }
        if detail:
            image_url["detail"] = detail
        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens if max_tokens is not None else self._max_tokens,
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
                            "image_url": image_url,
                        },
                    ],
                },
            ],
            "reasoning_effort": reasoning_effort or self._reasoning_effort,
            "store": False,
        }
        selected_verbosity = verbosity if verbosity is not None else self._verbosity
        if selected_verbosity:
            payload["text"] = {"verbosity": selected_verbosity}
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
                prompt_tokens = usage.get("prompt_tokens", 0) or 0
                output_tokens = usage.get("completion_tokens", 0) or 0
                self._trace_events.append(
                    {
                        "profile": self._profile.name,
                        "model": body.get("model", self._model),
                        "reasoning_effort": payload["reasoning_effort"],
                        "image_detail": detail,
                        "max_tokens": payload["max_tokens"],
                        "verbosity": selected_verbosity,
                        "raw_size": _size_dict(prepared.original_size),
                        "prepared_size": _size_dict(prepared.prepared_size),
                        "resized": prepared.resized,
                        "prompt_tokens": prompt_tokens,
                        "output_tokens": output_tokens,
                        "elapsed_s": round(elapsed, 3),
                    }
                )
                if len(self._trace_events) > TRACE_EVENT_CAP:
                    del self._trace_events[:-TRACE_EVENT_CAP]
                return VisionResult(
                    data=data if isinstance(data, dict) else {},
                    model=body.get("model", self._model),
                    prompt_tokens=prompt_tokens,
                    output_tokens=output_tokens,
                    elapsed_s=elapsed,
                    original_size=prepared.original_size,
                    prepared_size=prepared.prepared_size,
                    resized=prepared.resized,
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


def _int_env(name: str) -> int | None:
    value = os.environ.get(name)
    if not value:
        return None
    try:
        parsed = int(value)
    except ValueError as exc:
        raise VisionError(f"{name} must be an integer, got {value!r}") from exc
    if parsed <= 0:
        raise VisionError(f"{name} must be positive, got {parsed}")
    return parsed


def _size_dict(size: tuple[int, int]) -> dict[str, int]:
    return {"width": size[0], "height": size[1]}


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
