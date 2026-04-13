from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.app.publish_staging import main
from qa_agent.ingestion.models import ReviewStatus, StagingEntry
from qa_agent.video.loader import load_video_knowledge_document
from qa_agent.video.mapper import stage_lineup_candidate


class PublishStagingCliTests(unittest.TestCase):
    @staticmethod
    def _write_staging_file(path: Path, staged: StagingEntry) -> None:
        path.write_text(
            yaml.dump([staged.model_dump(mode="json")], allow_unicode=True, default_flow_style=False, sort_keys=False),
            encoding="utf-8",
        )

    def test_publish_staging_cli_publishes_reviewed_video_lineup(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"
        )
        staged = stage_lineup_candidate(document, document.lineup_candidates[0])
        reviewed = StagingEntry(
            metadata=staged.metadata.model_copy(update={"review_status": ReviewStatus.REVIEWED}),
            entry=staged.entry,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            staging_path = Path(temp_dir) / "video-staging.yaml"
            knowledge_root = Path(temp_dir) / "knowledge_sources"
            self._write_staging_file(staging_path, reviewed)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "publish_staging",
                    "--input",
                    str(staging_path),
                    "--knowledge-dir",
                    str(knowledge_root),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()

            summary = json.loads(stdout.getvalue())
            bucket = knowledge_root / "solutions" / "lineups" / "season-s13.yaml"
            self.assertEqual(summary["published_entries"], 1)
            self.assertEqual(summary["bucket_stats"]["season-s13.yaml"], 1)
            self.assertTrue(bucket.exists())

    def test_publish_staging_cli_skips_unreviewed_by_default(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_video_knowledge_document(
            project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"
        )
        staged = stage_lineup_candidate(document, document.lineup_candidates[0])

        with tempfile.TemporaryDirectory() as temp_dir:
            staging_path = Path(temp_dir) / "video-staging.yaml"
            knowledge_root = Path(temp_dir) / "knowledge_sources"
            self._write_staging_file(staging_path, staged)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "publish_staging",
                    "--input",
                    str(staging_path),
                    "--knowledge-dir",
                    str(knowledge_root),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()

            summary = json.loads(stdout.getvalue())
            bucket = knowledge_root / "solutions" / "lineups" / "season-s13.yaml"
            self.assertEqual(summary["published_entries"], 0)
            self.assertEqual(summary["skipped_entries"], 1)
            self.assertFalse(bucket.exists())


if __name__ == "__main__":
    unittest.main()
