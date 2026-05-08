from __future__ import annotations

import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from qa_agent.video.models import (
    VideoFrameRef,
    VideoKnowledgeDocument,
    VideoSegment,
    VideoSource,
)
from qa_agent.video.vision_enrichment import enrich_document_with_vision
from qa_agent.vision.extractor import ExtractedEntity, VisionExtraction


class _FakeExtractor:
    def __init__(self, result: VisionExtraction | None = None, raise_error: bool = False):
        self._result = result or VisionExtraction()
        self._raise = raise_error
        self.calls: list[list[str]] = []

    def extract(self, image_urls, *, question=None):
        self.calls.append(list(image_urls))
        if self._raise:
            raise RuntimeError("simulated vision outage")
        return self._result


def _make_doc(segments: list[VideoSegment]) -> VideoKnowledgeDocument:
    source = VideoSource(
        video_id="BV1TESTXYZ",
        title="T",
        uploader="u",
        source_url="https://example.com/BV1TESTXYZ",
        captured_at=datetime(2026, 4, 17, 0, 0, 0),
    )
    return VideoKnowledgeDocument(source=source, segments=segments, lineup_candidates=[])


def _make_frame(path_str: str, timestamp: float = 0.0) -> VideoFrameRef:
    tmp = Path(tempfile.gettempdir()) / path_str
    tmp.write_bytes(b"\xff\xd8\xff\xe0fakejpeg")
    return VideoFrameRef(timestamp_sec=timestamp, image_path=str(tmp), notes=[])


class EnrichDocumentWithVisionTests(unittest.TestCase):
    def test_segment_without_frames_passes_through(self) -> None:
        segment = VideoSegment(
            segment_id="seg-a",
            start_sec=0.0,
            end_sec=30.0,
            transcript="hello",
            ocr_lines=[],
            visual_summary="",
            frame_refs=[],
        )
        doc = _make_doc([segment])
        extractor = _FakeExtractor()
        enriched, stats = enrich_document_with_vision(doc, extractor=extractor)
        self.assertEqual(stats.segments_processed, 1)
        self.assertEqual(stats.segments_enriched, 0)
        self.assertEqual(extractor.calls, [])
        self.assertEqual(enriched.segments[0].ocr_lines, [])

    def test_hero_and_snippet_fold_into_ocr_lines_and_summary(self) -> None:
        frame = _make_frame("vision-frame-1.jpg")
        segment = VideoSegment(
            segment_id="seg-b",
            start_sec=0.0,
            end_sec=30.0,
            transcript="",
            ocr_lines=["原有一行"],
            visual_summary="字幕切片",
            frame_refs=[frame],
        )
        result = VisionExtraction(
            heroes=[ExtractedEntity(name="诸葛亮", confidence=0.98), ExtractedEntity(name="祝融夫人", confidence=0.91)],
            skills=[],
            text_snippets=["兵力 30000", "阵容推荐"],
        )
        extractor = _FakeExtractor(result)
        enriched, stats = enrich_document_with_vision(_make_doc([segment]), extractor=extractor)
        self.assertEqual(stats.segments_enriched, 1)
        self.assertEqual(stats.hero_hits, 2)
        self.assertEqual(stats.frames_analyzed, 1)
        new_lines = enriched.segments[0].ocr_lines
        self.assertIn("vision:hero:诸葛亮", new_lines)
        self.assertIn("vision:hero:祝融夫人", new_lines)
        self.assertIn("兵力 30000", new_lines)
        self.assertIn("原有一行", new_lines)
        self.assertIn("[视觉补充]", enriched.segments[0].visual_summary)
        self.assertIn("诸葛亮", enriched.segments[0].visual_summary)

    def test_duplicate_vision_names_are_deduped(self) -> None:
        frame = _make_frame("vision-frame-2.jpg")
        segment = VideoSegment(
            segment_id="seg-c",
            start_sec=0.0,
            end_sec=30.0,
            ocr_lines=["vision:hero:诸葛亮"],
            frame_refs=[frame],
        )
        result = VisionExtraction(
            heroes=[ExtractedEntity(name="诸葛亮", confidence=0.98)],
        )
        extractor = _FakeExtractor(result)
        enriched, stats = enrich_document_with_vision(_make_doc([segment]), extractor=extractor)
        self.assertEqual(enriched.segments[0].ocr_lines.count("vision:hero:诸葛亮"), 1)
        self.assertEqual(stats.segments_enriched, 0)

    def test_extractor_error_leaves_segment_untouched(self) -> None:
        frame = _make_frame("vision-frame-3.jpg")
        segment = VideoSegment(
            segment_id="seg-d",
            start_sec=0.0,
            end_sec=30.0,
            ocr_lines=["keep"],
            frame_refs=[frame],
        )
        extractor = _FakeExtractor(raise_error=True)
        enriched, stats = enrich_document_with_vision(_make_doc([segment]), extractor=extractor)
        self.assertEqual(stats.errors, 1)
        self.assertEqual(stats.segments_enriched, 0)
        self.assertEqual(enriched.segments[0].ocr_lines, ["keep"])

    def test_max_frames_per_segment_caps_input(self) -> None:
        frames = [
            _make_frame(f"vision-frame-cap-{i}.jpg", timestamp=float(i * 30))
            for i in range(5)
        ]
        segment = VideoSegment(
            segment_id="seg-e",
            start_sec=0.0,
            end_sec=200.0,
            frame_refs=frames,
        )
        extractor = _FakeExtractor()
        enrich_document_with_vision(_make_doc([segment]), extractor=extractor, max_frames_per_segment=2)
        self.assertEqual(len(extractor.calls), 1)
        self.assertEqual(len(extractor.calls[0]), 2)

    def test_missing_frame_path_degrades_to_error_path(self) -> None:
        segment = VideoSegment(
            segment_id="seg-f",
            start_sec=0.0,
            end_sec=30.0,
            frame_refs=[VideoFrameRef(timestamp_sec=0.0, image_path="/nonexistent/path.jpg", notes=[])],
        )
        extractor = _FakeExtractor()
        enriched, stats = enrich_document_with_vision(_make_doc([segment]), extractor=extractor)
        self.assertEqual(stats.errors, 1)
        self.assertEqual(extractor.calls, [])
        self.assertEqual(enriched.segments[0].ocr_lines, [])


if __name__ == "__main__":
    unittest.main()
