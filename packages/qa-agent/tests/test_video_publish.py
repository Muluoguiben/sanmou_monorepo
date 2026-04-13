from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qa_agent.ingestion.models import ReviewStatus, StagingEntry
from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.loader import load_entries_from_file
from qa_agent.service.query_service import QueryService
from qa_agent.video.loader import load_video_knowledge_document
from qa_agent.video.mapper import stage_lineup_candidate


class VideoPublishTests(unittest.TestCase):
    @staticmethod
    def _mark_reviewed(staged: StagingEntry) -> StagingEntry:
        return StagingEntry(
            metadata=staged.metadata.model_copy(update={"review_status": ReviewStatus.REVIEWED}),
            entry=staged.entry,
        )

    def test_publish_video_lineup_entry_writes_season_bucket(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"
        )
        staged = stage_lineup_candidate(document, document.lineup_candidates[0])
        reviewed = self._mark_reviewed(staged)
        entry = reviewed.to_reviewed_entry()

        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_root = Path(temp_dir) / "knowledge_sources"
            stats = publish_entries([entry], knowledge_root)
            bucket = knowledge_root / "solutions" / "lineups" / "season-s13.yaml"
            self.assertEqual(stats["season-s13.yaml"], 1)
            self.assertTrue(bucket.exists())
            entries = load_entries_from_file(bucket)

        self.assertEqual(entries[0].entry_kind.value, "lineup_solution")
        self.assertEqual(entries[0].topic, "S13诸葛亮开荒队")

    def test_published_video_lineup_is_queryable(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"
        )
        staged = stage_lineup_candidate(document, document.lineup_candidates[0])
        reviewed = self._mark_reviewed(staged)
        entry = reviewed.to_reviewed_entry()

        with tempfile.TemporaryDirectory() as temp_dir:
            knowledge_root = Path(temp_dir) / "knowledge_sources"
            publish_entries([entry], knowledge_root)
            service = QueryService(load_entries_from_file(knowledge_root / "solutions" / "lineups" / "season-s13.yaml"))
            response = service.lookup_topic("S13诸葛亮开荒队", domain="solution")

        self.assertEqual(response.coverage.value, "exact")
        self.assertEqual(response.evidence[0].source_ref, "BILIBILI:BV1TEST4x7yz#18-64")
        self.assertIn("稳定开荒", response.answer)


if __name__ == "__main__":
    unittest.main()
