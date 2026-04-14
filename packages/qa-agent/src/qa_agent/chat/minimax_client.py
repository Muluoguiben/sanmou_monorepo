"""MiniMax chat client via its Anthropic-compatible endpoint.

Endpoint: https://api.minimaxi.com/anthropic/v1/messages
Auth: x-api-key header with the MiniMax coding-plan key (sk-cp-*).
Model: MiniMax-M2.7 (server echoes any model name you send back as M2.7).

Kept intentionally minimal (stdlib + requests) to avoid pulling in the full
anthropic SDK — same wire format, just a proxy.
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

DEFAULT_BASE_URL = "https://api.minimaxi.com/anthropic"
DEFAULT_MODEL = "MiniMax-M2.7"
DEFAULT_MAX_TOKENS = 2048


class MinimaxError(RuntimeError):
    pass


@dataclass
class ChatResult:
    text: str
    model: str
    prompt_tokens: int
    output_tokens: int
    elapsed_s: float


class MinimaxChatClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
    ) -> None:
        load_package_env()
        api_key = api_key or os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            raise MinimaxError("MINIMAX_API_KEY not set (check packages/qa-agent/.env)")
        self._api_key = api_key
        self._model = model or os.environ.get("MINIMAX_MODEL", DEFAULT_MODEL)
        self._base_url = (base_url or os.environ.get("MINIMAX_BASE_URL", DEFAULT_BASE_URL)).rstrip("/")

    def generate(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        temperature: float = 0.2,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        max_retries: int = 2,
        retry_backoff_s: float = 2.0,
    ) -> ChatResult:
        messages: list[dict[str, Any]] = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "assistant"
            messages.append({"role": role, "content": turn["content"]})
        messages.append({"role": "user", "content": user_message})

        payload = {
            "model": self._model,
            "max_tokens": max_tokens,
            "system": system_prompt,
            "messages": messages,
            "temperature": temperature,
        }

        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            start = time.monotonic()
            try:
                resp = requests.post(
                    f"{self._base_url}/v1/messages",
                    headers={
                        "x-api-key": self._api_key,
                        "anthropic-version": "2023-06-01",
                        "content-type": "application/json",
                    },
                    json=payload,
                    timeout=60,
                )
                resp.raise_for_status()
                data = resp.json()
                elapsed = time.monotonic() - start
                text = _extract_text(data)
                usage = data.get("usage", {}) or {}
                return ChatResult(
                    text=text,
                    model=data.get("model", self._model),
                    prompt_tokens=usage.get("input_tokens", 0) or 0,
                    output_tokens=usage.get("output_tokens", 0) or 0,
                    elapsed_s=elapsed,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning(
                    "minimax attempt %d/%d failed: %s",
                    attempt + 1,
                    max_retries + 1,
                    exc,
                )
                if attempt < max_retries:
                    wait = _extract_retry_delay(exc) or retry_backoff_s * (attempt + 1)
                    time.sleep(wait)

        raise MinimaxError(
            f"minimax generate failed after {max_retries + 1} attempts: {last_exc}"
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


def _extract_text(data: dict[str, Any]) -> str:
    """Pull the assistant's text out of an Anthropic-format response.

    MiniMax may return thinking blocks first and a text block after; take all
    text blocks joined, drop thinking blocks entirely.
    """
    blocks = data.get("content") or []
    parts: list[str] = []
    for block in blocks:
        if block.get("type") == "text":
            parts.append(block.get("text", ""))
    return "\n".join(p for p in parts if p).strip()


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", stripped, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return stripped


def _extract_retry_delay(exc: Exception) -> float | None:
    msg = str(exc)
    match = re.search(r"retry[_-]?after['\"]?\s*:\s*['\"]?(\d+)", msg, re.IGNORECASE)
    if match:
        return float(match.group(1)) + 1.0
    return None
