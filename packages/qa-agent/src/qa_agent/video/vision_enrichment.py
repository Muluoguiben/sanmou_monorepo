"""Bridge between sampled video frames and the text-mode LLM lineup extractor.

Runs ImageExtractor over every VideoSegment that has frame_refs and folds the
recognized hero/skill/text_snippet names back into that segment's `ocr_lines`
and `visual_summary`. This way the existing `build_lineup_extraction_prompt`
(pure-text) gets to see the visual evidence as structured hints without
needing to change the JSON schema.

Design goals:
- Keep the preprocess step idempotent: names already in ocr_lines are not
  duplicated.
- Respect per-segment frame caps to stay under token budgets.
- Fail open: vision errors on one segment do not abort the pipeline; the
  segment simply passes through unchanged.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Protocol

from qa_agent.vision.extractor import ImageExtractor, VisionExtraction
from qa_agent.vision.image_loader import prepare_image_inputs

from .models import VideoKnowledgeDocument, VideoSegment

logger = logging.getLogger(__name__)


class _ImageExtractorProtocol(Protocol):
    def extract(self, image_urls: list[str], *, question: str | None = ...) -> VisionExtraction: ...


@dataclass
class VisionEnrichmentStats:
    segments_processed: int = 0
    segments_enriched: int = 0
    frames_analyzed: int = 0
    hero_hits: int = 0
    skill_hits: int = 0
    errors: int = 0


def enrich_document_with_vision(
    document: VideoKnowledgeDocument,
    *,
    extractor: _ImageExtractorProtocol,
    max_frames_per_segment: int = 3,
) -> tuple[VideoKnowledgeDocument, VisionEnrichmentStats]:
    """Augment `document`'s segments with visual-entity signals from their frame_refs.

    Returns a new document (segments copied) plus per-run stats. Segments that
    have no frame_refs, or whose ImageExtractor call raises, pass through
    unchanged. The injected signals land in `ocr_lines` and `visual_summary`
    so downstream text prompts pick them up automatically.
    """
    stats = VisionEnrichmentStats()
    enriched_segments: list[VideoSegment] = []
    for segment in document.segments:
        stats.segments_processed += 1
        if not segment.frame_refs:
            enriched_segments.append(segment)
            continue

        frame_paths = [ref.image_path for ref in segment.frame_refs[:max_frames_per_segment]]
        try:
            image_urls = prepare_image_inputs(frame_paths)
        except (FileNotFoundError, ValueError) as exc:
            logger.warning("skipping segment %s: image loader error: %s", segment.segment_id, exc)
            stats.errors += 1
            enriched_segments.append(segment)
            continue

        try:
            result = extractor.extract(image_urls)
        except Exception as exc:  # noqa: BLE001 — vision provider errors are opaque
            logger.warning("vision extract failed for segment %s: %s", segment.segment_id, exc)
            stats.errors += 1
            enriched_segments.append(segment)
            continue

        stats.frames_analyzed += len(image_urls)
        if result.is_empty():
            enriched_segments.append(segment)
            continue

        new_segment = _merge_vision_result(segment, result)
        enriched_segments.append(new_segment)
        if new_segment is not segment:
            stats.segments_enriched += 1
            stats.hero_hits += len(result.heroes)
            stats.skill_hits += len(result.skills)

    return (
        document.model_copy(update={"segments": enriched_segments}),
        stats,
    )


def _merge_vision_result(segment: VideoSegment, vision: VisionExtraction) -> VideoSegment:
    """Fold vision hero/skill names into ocr_lines and visual_summary.

    - Hero / skill names that are not already in ocr_lines are appended as
      `vision:武将名` / `vision:战法名` so the extractor can distinguish them
      from subtitle-sourced names if desired.
    - text_snippets are appended verbatim (deduped by set membership).
    - visual_summary gets a short `[视觉补充]` suffix listing the top-3
      hero/skill names with confidence for any human reviewing the document.
    """
    existing_ocr = set(segment.ocr_lines)
    additions: list[str] = []
    summary_mentions: list[str] = []

    for hero in vision.heroes:
        hero_name = _repair_mojibake(hero.name)
        summary_mentions.append(f"{hero_name}({hero.confidence:.2f})")
        tag = f"vision:hero:{hero_name}"
        if tag not in existing_ocr:
            additions.append(tag)
            existing_ocr.add(tag)
    for skill in vision.skills:
        skill_name = _repair_mojibake(skill.name)
        summary_mentions.append(f"{skill_name}({skill.confidence:.2f})")
        tag = f"vision:skill:{skill_name}"
        if tag not in existing_ocr:
            additions.append(tag)
            existing_ocr.add(tag)
    for snippet in vision.text_snippets:
        snippet = _repair_mojibake(snippet)
        if snippet and snippet not in existing_ocr:
            additions.append(snippet)
            existing_ocr.add(snippet)

    if not additions:
        return segment

    summary_prefix = segment.visual_summary or ""
    top_mentions = ", ".join(summary_mentions[:3])
    new_summary = summary_prefix
    if top_mentions:
        suffix = f"[视觉补充] {top_mentions}"
        new_summary = (summary_prefix + " " + suffix).strip() if summary_prefix else suffix

    return segment.model_copy(
        update={
            "ocr_lines": list(segment.ocr_lines) + additions,
            "visual_summary": new_summary,
        }
    )


def _repair_mojibake(value: str) -> str:
    """Repair common UTF-8-as-Latin-1 OCR text from vision providers."""
    if not any(marker in value for marker in ("Ã", "ä", "å", "é", "è", "ç", "æ")):
        return value
    try:
        repaired = value.encode("latin1").decode("utf-8")
    except UnicodeError:
        return value
    return repaired if repaired.strip() else value


def build_image_extractor_from_retriever(retriever, **kwargs) -> ImageExtractor:
    """Convenience factory for the common CLI path: retriever → whitelisted extractor."""
    return ImageExtractor(retriever=retriever, **kwargs)
