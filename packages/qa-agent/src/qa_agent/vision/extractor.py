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
from typing import TYPE_CHECKING, Any

from qa_agent.chat.openai_client import OpenAIChatClient, _strip_json_fence
from qa_agent.knowledge.models import Domain

if TYPE_CHECKING:
    from qa_agent.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


_VISION_SYSTEM_PROMPT_BASE = """你是《三国：谋定天下》游戏截图识别器。只输出合法 JSON，遵循下面的 schema。

schema:
{
  "heroes": [{"name": "武将中文名", "confidence": 0.0-1.0}],
  "skills": [{"name": "战法中文名", "confidence": 0.0-1.0}],
  "text_snippets": ["截图中可辨识的其它关键中文文本（数值/标题/状态）"]
}

硬性规则：
- name 必须**严格**取自下面"合法武将名"或"合法战法名"列表。列表之外的名字一律不要输出。
- 字形相近时（如 郝/郭、岿/屹、卫/衞），优先在列表里找最接近的候选；视觉上无法判断时宁愿 confidence 0.5 也要用列表里的规范名，而不是编一个列表外的字。
- 列表里没有近似项就跳过，宁缺勿滥。
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
    """Calls the OpenAI-compatible vision model and parses the JSON result.

    If a Retriever is provided, the canonical hero and skill names currently
    in the KB are injected into the system prompt as a strict whitelist.
    This pushes the model to snap visually-confusable characters (郝/郭,
    岿/屹, 卫/衞 etc.) onto a real KB name instead of inventing a list-free
    typo, which is where most of the pre-harden misses came from.
    """

    def __init__(
        self,
        client: OpenAIChatClient | None = None,
        *,
        retriever: "Retriever | None" = None,
        hero_names: list[str] | None = None,
        skill_names: list[str] | None = None,
    ) -> None:
        self._client = client or OpenAIChatClient()
        if retriever is not None:
            hero_names = hero_names or _collect_names(retriever, Domain.HERO)
            skill_names = skill_names or _collect_names(retriever, Domain.SKILL)
        self._system_prompt = _build_system_prompt(hero_names, skill_names)

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
            system_prompt=self._system_prompt,
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


def _collect_names(retriever: "Retriever", domain: Domain) -> list[str]:
    """Canonical topic names for all entries of the given domain, deduped."""
    seen: set[str] = set()
    names: list[str] = []
    for entry in retriever.entries:
        if entry.domain != domain:
            continue
        topic = (entry.topic or "").strip()
        if topic and topic not in seen:
            seen.add(topic)
            names.append(topic)
    return names


def _build_system_prompt(
    hero_names: list[str] | None,
    skill_names: list[str] | None,
) -> str:
    """Assemble the full system prompt with whitelist sections when given."""
    parts = [_VISION_SYSTEM_PROMPT_BASE.rstrip()]
    if hero_names:
        parts.append("\n合法武将名（共 {n}，只能从中选）：\n{names}".format(
            n=len(hero_names),
            names="、".join(hero_names[:300]),
        ))
    if skill_names:
        parts.append("\n合法战法名（共 {n}，只能从中选）：\n{names}".format(
            n=len(skill_names),
            names="、".join(skill_names[:300]),
        ))
    return "\n".join(parts)


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
