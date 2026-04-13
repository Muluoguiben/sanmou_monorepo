from pathlib import Path
import unittest

from qa_agent.video.loader import load_video_knowledge_document
from qa_agent.video.mapper import stage_all_video_entries, stage_lineup_candidate


class VideoMapperTests(unittest.TestCase):
    def test_stage_lineup_candidate_produces_solution_entry(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"
        )
        staged = stage_lineup_candidate(document, document.lineup_candidates[0])
        self.assertEqual(staged.entry.domain.value, "solution")
        self.assertEqual(staged.entry.entry_kind.value, "lineup_solution")
        self.assertEqual(staged.entry.topic, "S13诸葛亮开荒队")
        self.assertTrue(staged.entry.source_ref.startswith("BILIBILI:BV1TEST4x7yz#"))
        self.assertIn("诸葛亮", staged.entry.structured_data.hero_names)
        self.assertEqual(staged.metadata.source_site, "bilibili")

    def test_stage_all_video_entries_maps_multiple_candidate_types(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-evidence-sample.yaml"
        )
        from qa_agent.video import HeuristicVideoKnowledgeExtractor

        enriched = HeuristicVideoKnowledgeExtractor.from_project_root(project_root).enrich_document(document)
        staged_entries, direct_entries = stage_all_video_entries(enriched, project_root)
        entry_kinds = {entry.entry.entry_kind.value for entry in staged_entries}
        direct_domains = {entry.domain.value for entry in direct_entries}
        self.assertIn("lineup_solution", entry_kinds)
        self.assertIn("hero_profile", entry_kinds)
        self.assertIn("skill_profile", entry_kinds)
        self.assertTrue("combat" in direct_domains or len(direct_entries) == 0)


if __name__ == "__main__":
    unittest.main()
