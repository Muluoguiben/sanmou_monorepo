"""OpenAI-compatible chat client (GPT-5.x via sub2api gateway).

The sub2api gateway (http://45.76.98.138/v1) proxies GPT-5.x reasoning models.
Two non-standard requirements vs vanilla OpenAI:

- `reasoning_effort` (low/medium/high/xhigh) MUST be set, otherwise the
  gateway returns 503. Default "low" — cheapest, fast enough for chat.
- `store: false` per provider config.

Supports vision via the OpenAI image_url content format, unlike MiniMax-M2.7
which is text-only. Pass `images=[url, ...]` to generate().
"""
from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

import requests

from qa_agent.chat.env import load_package_env

logger = logging.getLogger(__name__)

DEFAULT_BASE_URL = "http://45.76.98.138/v1"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_REASONING_EFFORT = "low"
DEFAULT_MAX_TOKENS = 2048


class OpenAIError(RuntimeError):
    pass


@dataclass
class ChatResult:
    text: str
    model: str
    prompt_tokens: int
    output_tokens: int
    elapsed_s: float


class OpenAIChatClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        reasoning_effort: str | None = None,
    ) -> None:
        load_package_env()
        api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise OpenAIError("OPENAI_API_KEY not set (check packages/qa-agent/.env)")
        self._api_key = api_key
        self._model = model or os.environ.get("OPENAI_MODEL", DEFAULT_MODEL)
        self._base_url = (base_url or os.environ.get("OPENAI_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")
        self._reasoning_effort = (
            reasoning_effort
            or os.environ.get("OPENAI_REASONING_EFFORT", DEFAULT_REASONING_EFFORT)
        )

    def generate(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, Any]],
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_retries: int = 2,
        retry_backoff_s: float = 2.0,
        images: list[str] | None = None,
    ) -> ChatResult:
        messages: list[dict[str, Any]] = [{"role": "system", "content": system_prompt}]
        for turn in history:
            role = "user" if turn["role"] == "user" else "assistant"
            messages.append({"role": role, "content": turn["content"]})
        messages.append({"role": "user", "content": _build_user_content(user_message, images)})

        payload: dict[str, Any] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": messages,
            "reasoning_effort": self._reasoning_effort,
            "store": False,
        }
        # GPT-5 reasoning models ignore temperature; only send when user overrides default.
        if temperature != 0.2:
            payload["temperature"] = temperature

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                resp = requests.post(
                    f"{self._base_url}/chat/completions",
                    headers={
                        "Authorization": f"Bearer {self._api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                    timeout=180,
                )
                resp.raise_for_status()
                data = resp.json()
                elapsed = time.monotonic() - start
                text = _extract_text(data)
                usage = data.get("usage", {}) or {}
                return ChatResult(
                    text=text,
                    model=data.get("model", self._model),
                    prompt_tokens=usage.get("prompt_tokens", 0) or 0,
                    output_tokens=usage.get("completion_tokens", 0) or 0,
                    elapsed_s=elapsed,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "openai attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    time.sleep(retry_backoff_s * (attempt + 1))

        raise OpenAIError(
            f"openai generate failed after {max_retries + 1} attempts: {last_exc}"
        )

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> Any:
        reinforced_system = (
            system_prompt
            + "\n\n严格要求：只输出合法的 JSON，不要任何 markdown 代码块、注释或前后说明文字。"
        )
        result = self.generate(
            system_prompt=reinforced_system,
            history=[],
            user_message=user_message,
            temperature=temperature,
            max_tokens=512,
        )
        return json.loads(_strip_json_fence(result.text))


def _build_user_content(message: str, images: list[str] | None) -> Any:
    if not images:
        return message
    parts: list[dict[str, Any]] = [{"type": "text", "text": message}]
    for url in images:
        parts.append({"type": "image_url", "image_url": {"url": url}})
    return parts


def _extract_text(data: dict[str, Any]) -> str:
    choices = data.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message") or {}
    content = msg.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        parts = [p.get("text", "") for p in content if p.get("type") == "text"]
        return "\n".join(p for p in parts if p).strip()
    return ""


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", stripped, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return stripped
