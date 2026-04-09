from __future__ import annotations

from pathlib import Path

import yaml

from qa_agent.ingestion.models import RawBatchDocument, StagingEntry


def load_raw_batch(path: Path) -> RawBatchDocument:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return RawBatchDocument.model_validate(data)


def load_staging_entries(path: Path) -> list[StagingEntry]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"Staging document must be a list: {path}")
    return [StagingEntry.model_validate(item) for item in data]

