from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from qa_agent.video.loader import dump_video_knowledge_document, load_video_knowledge_document


class VideoModelTests(unittest.TestCase):
    def test_load_video_knowledge_document(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"
        )
        self.assertEqual(document.source.video_id, "BV1TEST4x7yz")
        self.assertEqual(document.segments[0].segment_id, "intro-lineup")
        self.assertEqual(document.lineup_candidates[0].topic, "S13诸葛亮开荒队")

    def test_candidate_must_reference_known_segment(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with self.assertRaises(ValidationError):
            load_video_knowledge_document(project_root / "tests" / "fixtures" / "bad_video_doc.yaml")

    def test_dump_and_reload_round_trip(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            out = Path(temp_dir) / "roundtrip.yaml"
            dump_video_knowledge_document(out, document)
            loaded = load_video_knowledge_document(out)
        self.assertEqual(loaded.source.title, document.source.title)
        self.assertEqual(len(loaded.lineup_candidates), 1)


if __name__ == "__main__":
    unittest.main()
