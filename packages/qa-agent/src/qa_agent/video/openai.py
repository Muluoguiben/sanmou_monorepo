from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass

from pydantic import ValidationError

from qa_agent.chat.openai_client import OpenAIChatClient

from .gemini import build_lineup_extraction_prompt
from .models import VideoKnowledgeDocument, VideoLineupCandidate

logger = logging.getLogger(__name__)


DEFAULT_VIDEO_MODEL = "gpt-5.4"
DEFAULT_MAX_TOKENS = 8192


@dataclass
class OpenAIVideoKnowledgeExtractor:
    client: OpenAIChatClient | None = None
    model: str = DEFAULT_VIDEO_MODEL
    max_tokens: int = DEFAULT_MAX_TOKENS
    reasoning_effort: str = "low"

    def __post_init__(self) -> None:
        if self.client is None:
            self.client = OpenAIChatClient(model=self.model, reasoning_effort=self.reasoning_effort)

    def extract_lineup_candidates(self, document: VideoKnowledgeDocument) -> list[VideoLineupCandidate]:
        prompt = build_lineup_extraction_prompt(document)
        system_prompt = (
            "你是《三国：谋定天下》视频知识抽取器。\n"
            "输出严格遵守以下 JSON schema（不要额外字段、不要嵌套结构、不要 markdown 代码块）：\n"
            "{\n"
            '  "lineup_candidates": [\n'
            "    {\n"
            '      "candidate_id": "string，短横线 slug（必填）",\n'
            '      "segment_id": "string，单个 segment_id，必须出现在输入 segments 里（必填）",\n'
            '      "topic": "string，阵容主题，如 \\"S13 诸葛亮开荒队\\"（必填）",\n'
            '      "aliases": ["string"],\n'
            '      "season_tags": ["string"],\n'
            '      "lineup_rating": "string",\n'
            '      "factions": ["string"],\n'
            '      "hero_names": ["string"],\n'
            '      "core_skills": ["string"],\n'
            '      "scenario_tags": ["string"],\n'
            '      "facts": ["string"] (必填，至少 1 条),\n'
            '      "constraints": ["string"],\n'
            '      "notes": ["string"],\n'
            '      "confidence": 0.0~1.0 float（必填）\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "关键约束：segment_id 不是数组；hero_names/core_skills 是顶层字段，不要嵌套到 lineup 对象里。"
        )
        result = self.client.generate(
            system_prompt=system_prompt,
            history=[],
            user_message=prompt,
            temperature=0.0,
            max_tokens=self.max_tokens,
        )
        data = json.loads(_strip_json_fence(result.text))
        raw_candidates = data.get("lineup_candidates", [])
        candidates: list[VideoLineupCandidate] = []
        for item in raw_candidates:
            try:
                candidates.append(VideoLineupCandidate.model_validate(item))
            except (ValidationError, ValueError, TypeError, AttributeError) as exc:
                logger.warning(
                    "OpenAI lineup candidate validation failed, skipping: %s; payload=%s",
                    exc,
                    item,
                )
        return candidates

    def enrich_document(self, document: VideoKnowledgeDocument) -> VideoKnowledgeDocument:
        return document.model_copy(update={"lineup_candidates": self.extract_lineup_candidates(document)})


def _strip_json_fence(text: str) -> str:
    stripped = text.strip()
    fence = re.match(r"^```(?:json)?\s*(.*?)\s*```\s*$", stripped, re.DOTALL)
    if fence:
        return fence.group(1).strip()
    return stripped
