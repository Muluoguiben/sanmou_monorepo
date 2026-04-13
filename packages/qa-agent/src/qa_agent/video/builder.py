from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

from .models import VideoFrameRef, VideoKnowledgeDocument, VideoSegment, VideoSource


def _slugify(value: str) -> str:
    lowered = value.lower().strip()
    return "-".join(part for part in lowered.replace("/", " ").replace("_", " ").split() if part)


class VideoEvidenceSegment(BaseModel):
    start_sec: float = Field(ge=0.0)
    end_sec: float = Field(gt=0.0)
    title: str | None = None
    transcript: str | None = None
    transcript_lines: list[str] = Field(default_factory=list)
    ocr_lines: list[str] = Field(default_factory=list)
    visual_summary: str | None = None
    frame_paths: list[str] = Field(default_factory=list)

    @field_validator("title", "transcript", "visual_summary", mode="before")
    @classmethod
    def _strip_optional_scalar(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("transcript_lines", "ocr_lines", "frame_paths")
    @classmethod
    def _strip_lists(cls, values: list[str]) -> list[str]:
        return [value.strip() for value in values if value.strip()]


class VideoEvidenceBundle(BaseModel):
    source: VideoSource
    segments: list[VideoEvidenceSegment] = Field(min_length=1)


def build_video_knowledge_document(bundle: VideoEvidenceBundle) -> VideoKnowledgeDocument:
    segments: list[VideoSegment] = []
    for index, raw_segment in enumerate(bundle.segments, start=1):
        title_token = _slugify(raw_segment.title or f"segment-{index}")
        segment_id = f"{title_token}-{int(raw_segment.start_sec)}-{int(raw_segment.end_sec)}"
        transcript = raw_segment.transcript or " ".join(raw_segment.transcript_lines)
        frame_refs = [
            VideoFrameRef(
                timestamp_sec=raw_segment.start_sec,
                image_path=frame_path,
                notes=[raw_segment.title] if raw_segment.title else [],
            )
            for frame_path in raw_segment.frame_paths
        ]
        segments.append(
            VideoSegment(
                segment_id=segment_id,
                start_sec=raw_segment.start_sec,
                end_sec=raw_segment.end_sec,
                transcript=transcript,
                ocr_lines=raw_segment.ocr_lines,
                visual_summary=raw_segment.visual_summary or "",
                frame_refs=frame_refs,
            )
        )
    return VideoKnowledgeDocument(source=bundle.source, segments=segments, lineup_candidates=[])
