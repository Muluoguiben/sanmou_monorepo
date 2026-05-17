from __future__ import annotations

import unittest
from datetime import datetime

from qa_agent.video.evidence_quality import EvidenceQualityContext, filter_document_for_evidence_quality
from qa_agent.video.models import (
    VideoFrameRef,
    VideoKnowledgeDocument,
    VideoLineupCandidate,
    VideoSegment,
    VideoSource,
)


def _context() -> EvidenceQualityContext:
    return EvidenceQualityContext(
        hero_names=frozenset({"祝融夫人", "马云禄", "徐庶", "刘备"}),
        skill_names=frozenset({"折冲御侮"}),
        hero_aliases={"祝融": "祝融夫人", "祝融夫人": "祝融夫人", "马云禄": "马云禄", "徐庶": "徐庶", "刘备": "刘备"},
        skill_aliases={"折冲御侮": "折冲御侮"},
    )


def _doc(segment: VideoSegment, candidates: list[VideoLineupCandidate]) -> VideoKnowledgeDocument:
    return VideoKnowledgeDocument(
        source=VideoSource(
            video_id="BV1TEST",
            title="三谋开荒测试",
            uploader="u",
            source_url="https://www.bilibili.com/video/BV1TEST/",
            captured_at=datetime(2026, 5, 17, 0, 0, 0),
        ),
        segments=[segment],
        lineup_candidates=candidates,
    )


class EvidenceQualityTests(unittest.TestCase):
    def test_rejects_ocr_menu_words_as_lineup(self) -> None:
        segment = VideoSegment(
            segment_id="seg",
            start_sec=0,
            end_sec=30,
            transcript="这里是寻访和奖励界面",
            ocr_lines=["寻访", "总领奖励", "跳过动画"],
            visual_summary="B站元数据导入。",
            frame_refs=[VideoFrameRef(timestamp_sec=20, image_path="/tmp/a.jpg")],
        )
        candidate = VideoLineupCandidate(
            candidate_id="bad",
            segment_id="seg",
            topic="寻访阵容",
            hero_names=["寻访", "寻访一次", "寻访五次"],
            facts=["坏候选"],
            confidence=0.62,
        )
        filtered, stats = filter_document_for_evidence_quality(_doc(segment, [candidate]), _context())
        self.assertEqual(filtered.lineup_candidates, [])
        self.assertEqual(stats["after"]["lineup"], 0)
        self.assertIn("lineup_segment_not_allowed", stats["reject_reasons"])

    def test_accepts_lineup_with_visual_and_subtitle_support(self) -> None:
        segment = VideoSegment(
            segment_id="seg",
            start_sec=20,
            end_sec=45,
            transcript="这里祝融带马云禄和徐庶开荒",
            ocr_lines=[
                "vision:hero:祝融夫人",
                "vision:hero:马云禄",
                "vision:hero:徐庶",
                "vision:frame_kind:lineup_table",
            ],
            visual_summary="B站 AI 中文字幕切片。 [视觉补充] 祝融夫人(0.98), 马云禄(0.98), 徐庶(0.98)",
            frame_refs=[VideoFrameRef(timestamp_sec=30, image_path="/tmp/b.jpg")],
        )
        candidate = VideoLineupCandidate(
            candidate_id="good",
            segment_id="seg",
            topic="祝融夫人开荒队",
            hero_names=["祝融夫人", "马云禄", "徐庶"],
            core_skills=["折冲御侮", "不是战法"],
            facts=["好候选"],
            confidence=0.62,
        )
        filtered, stats = filter_document_for_evidence_quality(_doc(segment, [candidate]), _context())
        self.assertEqual(stats["after"]["lineup"], 1)
        self.assertEqual(filtered.lineup_candidates[0].hero_names, ["祝融夫人", "马云禄", "徐庶"])
        self.assertEqual(filtered.lineup_candidates[0].core_skills, ["折冲御侮"])


if __name__ == "__main__":
    unittest.main()
