from __future__ import annotations

import json
import logging
import os
import re
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types

from qa_agent.chat.env import load_package_env

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-flash-latest"


class GeminiError(RuntimeError):
    pass


@dataclass
class GeminiResponse:
    text: str
    model: str
    prompt_tokens: int
    output_tokens: int
    elapsed_s: float


class GeminiChatClient:
    def __init__(self, api_key: str | None = None, model: str | None = None) -> None:
        load_package_env()
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise GeminiError("GEMINI_API_KEY not set (check packages/qa-agent/.env)")
        self._client = genai.Client(api_key=api_key)
        self._model = model or os.environ.get("GEMINI_MODEL", DEFAULT_MODEL)

    def generate(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        temperature: float = 0.2,
        max_retries: int = 2,
        retry_backoff_s: float = 2.0,
    ) -> GeminiResponse:
        contents: list[types.Content] = []
        for turn in history:
            role = "user" if turn["role"] == "user" else "model"
            contents.append(
                types.Content(role=role, parts=[types.Part.from_text(text=turn["content"])])
            )
        contents.append(
            types.Content(role="user", parts=[types.Part.from_text(text=user_message)])
        )

        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
        )

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
                usage = resp.usage_metadata
                return GeminiResponse(
                    text=resp.text or "",
                    model=self._model,
                    prompt_tokens=getattr(usage, "prompt_token_count", 0) or 0,
                    output_tokens=getattr(usage, "candidates_token_count", 0) or 0,
                    elapsed_s=elapsed,
                )
            except Exception as exc:  # noqa: BLE001
                last_exc = exc
                logger.warning("gemini attempt %d/%d failed: %s", attempt + 1, max_retries + 1, exc)
                if attempt < max_retries:
                    wait = self._extract_retry_delay(exc) or retry_backoff_s * (attempt + 1)
                    time.sleep(wait)

        raise GeminiError(f"gemini generate failed after {max_retries + 1} attempts: {last_exc}")

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> Any:
        config_kwargs: dict[str, Any] = {
            "system_instruction": system_prompt,
            "temperature": temperature,
            "response_mime_type": "application/json",
        }
        if response_schema is not None:
            config_kwargs["response_schema"] = response_schema
        config = types.GenerateContentConfig(**config_kwargs)

        resp = self._client.models.generate_content(
            model=self._model,
            contents=[types.Content(role="user", parts=[types.Part.from_text(text=user_message)])],
            config=config,
        )
        return json.loads(resp.text or "null")

    @staticmethod
    def _extract_retry_delay(exc: Exception) -> float | None:
        msg = str(exc)
        match = re.search(r"retryDelay['\"]?\s*:\s*['\"]?(\d+)s", msg)
        if match:
            return float(match.group(1)) + 1.0
        return None
