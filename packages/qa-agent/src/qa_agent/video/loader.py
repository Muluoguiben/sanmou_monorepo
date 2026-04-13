from __future__ import annotations

from pathlib import Path

import yaml

from .models import VideoKnowledgeDocument


def load_video_knowledge_document(path: Path) -> VideoKnowledgeDocument:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return VideoKnowledgeDocument.model_validate(data)


def dump_video_knowledge_document(path: Path, document: VideoKnowledgeDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.dump(document.model_dump(mode="json"), allow_unicode=True, default_flow_style=False, sort_keys=False)
    path.write_text(text, encoding="utf-8")
