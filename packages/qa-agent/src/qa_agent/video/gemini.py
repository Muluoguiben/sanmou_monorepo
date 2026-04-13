from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib import error, parse, request

from .models import VideoKnowledgeDocument, VideoLineupCandidate


_LINEUP_SCHEMA: dict[str, Any] = {
    "type": "OBJECT",
    "properties": {
        "lineup_candidates": {
            "type": "ARRAY",
            "items": {
                "type": "OBJECT",
                "properties": {
                    "candidate_id": {"type": "STRING"},
                    "segment_id": {"type": "STRING"},
                    "topic": {"type": "STRING"},
                    "aliases": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "season_tags": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "lineup_rating": {"type": "STRING"},
                    "factions": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "hero_names": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "core_skills": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "scenario_tags": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "facts": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "constraints": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "notes": {"type": "ARRAY", "items": {"type": "STRING"}},
                    "confidence": {"type": "NUMBER"},
                },
                "required": ["candidate_id", "segment_id", "topic", "facts", "confidence"],
            },
        }
    },
    "required": ["lineup_candidates"],
}


def build_lineup_extraction_prompt(document: VideoKnowledgeDocument) -> str:
    segment_payload = []
    for segment in document.segments:
        segment_payload.append(
            {
                "segment_id": segment.segment_id,
                "start_sec": segment.start_sec,
                "end_sec": segment.end_sec,
                "transcript": segment.transcript,
                "ocr_lines": segment.ocr_lines,
                "visual_summary": segment.visual_summary,
            }
        )

    payload = {
        "source": {
            "video_id": document.source.video_id,
            "title": document.source.title,
            "uploader": document.source.uploader,
        },
        "segments": segment_payload,
    }
    return (
        "你是《三国：谋定天下》知识抽取器。\n"
        "任务：只从给定视频证据中抽取高置信的阵容方案候选，输出 JSON。\n"
        "要求：\n"
        "1. 只抽取能够从 transcript、OCR、visual_summary 明确支持的内容。\n"
        "2. 没有充分证据时返回空数组。\n"
        "3. facts 写稳定结论，不写营销话术。\n"
        "4. constraints 写适用边界、风险或不适用场景。\n"
        "5. candidate_id 用短横线 slug，segment_id 必须引用输入里的 segment_id。\n"
        "6. confidence 取 0 到 1。\n"
        "7. 结果只包含 lineup_candidates。\n\n"
        f"输入证据:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


@dataclass
class GeminiVideoKnowledgeExtractor:
    api_key: str
    model: str = "gemini-2.0-flash"
    timeout_sec: int = 60

    def extract_lineup_candidates(self, document: VideoKnowledgeDocument) -> list[VideoLineupCandidate]:
        prompt = build_lineup_extraction_prompt(document)
        response = self._generate_structured_json(prompt)
        raw_candidates = response.get("lineup_candidates", [])
        return [VideoLineupCandidate.model_validate(item) for item in raw_candidates]

    def enrich_document(self, document: VideoKnowledgeDocument) -> VideoKnowledgeDocument:
        return document.model_copy(update={"lineup_candidates": self.extract_lineup_candidates(document)})

    def _generate_structured_json(self, prompt: str) -> dict[str, Any]:
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            f"{parse.quote(self.model, safe='')}:generateContent?key={parse.quote(self.api_key, safe='')}"
        )
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "response_mime_type": "application/json",
                "response_schema": _LINEUP_SCHEMA,
            },
        }
        req = request.Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout_sec) as resp:
                body = resp.read().decode("utf-8")
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini request failed with HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Gemini request failed: {exc.reason}") from exc

        data = json.loads(body)
        return json.loads(_extract_text(data))


def _extract_text(response: dict[str, Any]) -> str:
    candidates = response.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini response did not include candidates")
    content = candidates[0].get("content") or {}
    parts = content.get("parts") or []
    if not parts or "text" not in parts[0]:
        raise RuntimeError("Gemini response did not include text output")
    return parts[0]["text"]
