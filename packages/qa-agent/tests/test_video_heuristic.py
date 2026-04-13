from __future__ import annotations

import unittest
from pathlib import Path

from qa_agent.video import HeuristicVideoKnowledgeExtractor, load_video_knowledge_document


class VideoHeuristicTests(unittest.TestCase):
    def test_heuristic_extractor_generates_lineup_candidate(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-evidence-sample.yaml"
        )
        extractor = HeuristicVideoKnowledgeExtractor.from_project_root(project_root)
        enriched = extractor.enrich_document(document)
        self.assertEqual(len(enriched.lineup_candidates), 1)
        candidate = enriched.lineup_candidates[0]
        self.assertEqual(candidate.topic, "S13诸葛亮开荒队")
        self.assertIn("诸葛亮", candidate.hero_names)
        self.assertIn("开荒", candidate.scenario_tags)

    def test_heuristic_extractor_generates_hero_and_skill_candidates(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-evidence-sample.yaml"
        )
        extractor = HeuristicVideoKnowledgeExtractor.from_project_root(project_root)
        enriched = extractor.enrich_document(document)
        self.assertGreaterEqual(len(enriched.hero_candidates), 1)
        self.assertGreaterEqual(len(enriched.skill_candidates), 1)
        self.assertEqual(enriched.hero_candidates[0].hero_name, "诸葛亮")
        self.assertIn(enriched.skill_candidates[0].skill_name, {"盛气凌敌", "草船借箭"})


if __name__ == "__main__":
    unittest.main()
