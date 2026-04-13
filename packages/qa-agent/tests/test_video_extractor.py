from pathlib import Path
import json
import unittest
from unittest.mock import patch

from qa_agent.video.gemini import GeminiVideoKnowledgeExtractor, build_lineup_extraction_prompt
from qa_agent.video.loader import load_video_knowledge_document


class _FakeResponse:
    def __init__(self, payload: dict) -> None:
        self._payload = payload

    def read(self) -> bytes:
        return json.dumps(self._payload, ensure_ascii=False).encode("utf-8")

    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None


class VideoExtractorTests(unittest.TestCase):
    def test_prompt_contains_segment_ids(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-evidence-sample.yaml"
        )
        prompt = build_lineup_extraction_prompt(document)
        self.assertIn("intro-lineup", prompt)
        self.assertIn("matchup", prompt)
        self.assertIn("诸葛亮", prompt)

    @patch("qa_agent.video.gemini.request.urlopen")
    def test_extractor_parses_structured_candidates(self, mocked_urlopen) -> None:
        mocked_urlopen.return_value = _FakeResponse(
            {
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "lineup_candidates": [
                                                {
                                                    "candidate_id": "zg-kaihuang",
                                                    "segment_id": "intro-lineup",
                                                    "topic": "诸葛亮开荒队",
                                                    "hero_names": ["诸葛亮", "刘备", "黄月英"],
                                                    "core_skills": ["盛气凌敌"],
                                                    "facts": ["适合前期开荒。"],
                                                    "constraints": ["不适合高强度对冲。"],
                                                    "confidence": 0.81,
                                                }
                                            ]
                                        },
                                        ensure_ascii=False,
                                    )
                                }
                            ]
                        }
                    }
                ]
            }
        )
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-evidence-sample.yaml"
        )
        extractor = GeminiVideoKnowledgeExtractor(api_key="test-key")
        candidates = extractor.extract_lineup_candidates(document)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].topic, "诸葛亮开荒队")
        self.assertEqual(candidates[0].segment_id, "intro-lineup")


if __name__ == "__main__":
    unittest.main()
