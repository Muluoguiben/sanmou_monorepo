from __future__ import annotations

import unittest
from pathlib import Path

import yaml

from qa_agent.video import VideoEvidenceBundle, build_video_knowledge_document


class VideoBuilderTests(unittest.TestCase):
    def test_build_video_knowledge_document_from_bundle(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        data = yaml.safe_load(
            (project_root / "ingestion" / "raw" / "videos" / "bilibili-bundle-sample.yaml").read_text(encoding="utf-8")
        )
        bundle = VideoEvidenceBundle.model_validate(data)
        document = build_video_knowledge_document(bundle)
        self.assertEqual(document.source.video_id, "BV1TEST4x7yz")
        self.assertEqual(len(document.segments), 2)
        self.assertEqual(document.segments[0].segment_id, "intro-lineup-18-64")
        self.assertIn("诸葛亮", document.segments[0].transcript)
        self.assertEqual(document.lineup_candidates, [])


if __name__ == "__main__":
    unittest.main()
