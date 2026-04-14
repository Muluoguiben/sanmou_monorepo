"""ImageExtractor — pass 1 of the vision flow.

Asks the OpenAI-compatible vision model to list candidate entities visible
in one or more images (hero names, skill names, raw salient text) as JSON.
The caller then resolves candidates against the KB (via Retriever) and
filters out anything that doesn't resolve — anti-fabrication guard for the
answering LLM.

Contract:
- Input: list of prepared image URLs (http / data URI), optional user
  question for disambiguation.
- Output: VisionExtraction with typed candidate lists. JSON parse failures
  degrade to empty — the answering pass then runs as a text-only question.
"""
from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from qa_agent.chat.openai_client import OpenAIChatClient, _strip_json_fence

logger = logging.getLogger(__name__)


_VISION_SYSTEM_PROMPT = """你是《三国：谋定天下》游戏截图识别器。只输出合法 JSON，遵循下面的 schema。

schema:
{
  "heroes": [{"name": "武将中文名", "confidence": 0.0-1.0}],
  "skills": [{"name": "战法中文名", "confidence": 0.0-1.0}],
  "text_snippets": ["截图中可辨识的其它关键中文文本（数值/标题/状态）"]
}

规则：
- 只写你能较确定辨识的名字。不确定的就不要写，宁缺勿滥。
- 武将/战法必须是完整中文名，不要写别名/简写。
- text_snippets 用来承载不是武将/战法但与问题相关的数值或标签（如"体力 120"、"第二回合"）。
- 如果截图里完全没有三谋相关内容，输出空数组。
- 不要加解释、不要加 markdown，只输出 JSON 对象。
"""


@dataclass
class ExtractedEntity:
    name: str
    confidence: float

    @classmethod
    def from_dict(cls, data: Any) -> "ExtractedEntity | None":
        if not isinstance(data, dict):
            return None
        name = str(data.get("name", "")).strip()
        if not name:
            return None
        try:
            conf = float(data.get("confidence", 0.5))
        except (TypeError, ValueError):
            conf = 0.5
        conf = max(0.0, min(1.0, conf))
        return cls(name=name, confidence=conf)


@dataclass
class VisionExtraction:
    heroes: list[ExtractedEntity] = field(default_factory=list)
    skills: list[ExtractedEntity] = field(default_factory=list)
    text_snippets: list[str] = field(default_factory=list)
    raw_text: str = ""
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0

    def is_empty(self) -> bool:
        return not (self.heroes or self.skills or self.text_snippets)

    def all_entity_names(self) -> list[str]:
        return [e.name for e in self.heroes] + [e.name for e in self.skills]


class ImageExtractor:
    """Calls the OpenAI-compatible vision model and parses the JSON result."""

    def __init__(self, client: OpenAIChatClient | None = None) -> None:
        self._client = client or OpenAIChatClient()

    def extract(
        self,
        image_urls: list[str],
        *,
        question: str | None = None,
    ) -> VisionExtraction:
        if not image_urls:
            return VisionExtraction()

        user_msg = "识别图中的武将和战法，按 schema 输出 JSON。"
        if question:
            user_msg += f"\n用户问题：{question}"

        result = self._client.generate(
            system_prompt=_VISION_SYSTEM_PROMPT,
            history=[],
            user_message=user_msg,
            temperature=0.0,
            max_tokens=512,
            images=image_urls,
        )

        parsed = _safe_parse_json(result.text)
        heroes = _parse_entities(parsed.get("heroes", []))
        skills = _parse_entities(parsed.get("skills", []))
        snippets = _parse_snippets(parsed.get("text_snippets", []))

        return VisionExtraction(
            heroes=heroes,
            skills=skills,
            text_snippets=snippets,
            raw_text=result.text,
            prompt_tokens=result.prompt_tokens,
            output_tokens=result.output_tokens,
            elapsed_s=result.elapsed_s,
        )


def _safe_parse_json(text: str) -> dict[str, Any]:
    if not text:
        return {}
    try:
        data = json.loads(_strip_json_fence(text))
    except json.JSONDecodeError as exc:
        logger.warning("vision JSON parse failed: %s; raw=%r", exc, text[:200])
        return {}
    return data if isinstance(data, dict) else {}


def _parse_entities(raw: Any) -> list[ExtractedEntity]:
    if not isinstance(raw, list):
        return []
    out: list[ExtractedEntity] = []
    for item in raw:
        ent = ExtractedEntity.from_dict(item)
        if ent:
            out.append(ent)
    return out


def _parse_snippets(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(s).strip() for s in raw if str(s).strip()]
