"""LLM client protocol + provider factory.

Supports Gemini (google-genai) and MiniMax (Anthropic-compatible coding plan).
Pick via env var LLM_PROVIDER=gemini|minimax. Defaults to minimax since
Gemini free tier has 20 req/day which is too tight for regression work.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Protocol

from qa_agent.chat.env import load_package_env


@dataclass
class LLMResult:
    text: str
    model: str
    prompt_tokens: int
    output_tokens: int
    elapsed_s: float


class LLMClient(Protocol):
    def generate(
        self,
        *,
        system_prompt: str,
        history: list[dict[str, str]],
        user_message: str,
        temperature: float = 0.2,
        max_retries: int = 2,
        retry_backoff_s: float = 2.0,
    ) -> Any: ...

    def generate_json(
        self,
        *,
        system_prompt: str,
        user_message: str,
        response_schema: dict[str, Any] | None = None,
        temperature: float = 0.0,
    ) -> Any: ...


def build_llm_client(provider: str | None = None) -> LLMClient:
    load_package_env()
    provider = (provider or os.environ.get("LLM_PROVIDER", "minimax")).lower()
    if provider == "minimax":
        from qa_agent.chat.minimax_client import MinimaxChatClient
        return MinimaxChatClient()
    if provider == "gemini":
        from qa_agent.chat.gemini_client import GeminiChatClient
        return GeminiChatClient()
    raise ValueError(f"Unknown LLM_PROVIDER: {provider!r} (expected 'minimax' or 'gemini')")
