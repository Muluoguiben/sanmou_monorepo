"""Vision helpers for the QA agent.

Image extraction runs as a separate LLM pass before retrieval (two-pass
design): vision model identifies candidate heroes/skills/text from images,
those candidates are resolved against the KB, then only resolved entities
flow into the text-only answering pass.
"""
from qa_agent.vision.extractor import (
    ExtractedEntity,
    ImageExtractor,
    VisionExtraction,
)
from qa_agent.vision.image_loader import prepare_image_inputs

__all__ = [
    "ExtractedEntity",
    "ImageExtractor",
    "VisionExtraction",
    "prepare_image_inputs",
]
