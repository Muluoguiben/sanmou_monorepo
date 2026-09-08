from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.app.run_video_pipeline import main
from qa_agent.app.publish_staging import main as publish_main
from qa_agent.ingestion.loader import load_staging_entries
from qa_agent.ingestion.models import ReviewStatus
from qa_agent.video.models import VideoCombatCandidate
from qa_agent.app.video_extract import _resolve_enriched_document


class RunVideoPipelineCliTests(unittest.TestCase):
    def test_machine_pipeline_stops_at_pending_and_default_publisher_refuses(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        input_path = project_root / "ingestion" / "raw" / "videos" / "bilibili-bundle-sample.yaml"

        with tempfile.TemporaryDirectory() as temp_dir:
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "run_video_pipeline",
                    "--input",
                    str(input_path),
                    "--workspace",
                    temp_dir,
                    "--extractor",
                    "heuristic",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()

            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["video_id"], "BV1TEST4x7yz")
            self.assertEqual(summary["lineup_candidates"], 1)
            self.assertEqual(summary["bucket_stats"], {})
            self.assertEqual(summary["query_results"], {})
            self.assertIsNone(summary["knowledge_root"])
            self.assertTrue(summary["review_required"])
            self.assertFalse((Path(temp_dir) / "knowledge_sources").exists())
            self.assertFalse((Path(temp_dir) / "video-staging-reviewed.yaml").exists())
            pending = load_staging_entries(Path(summary["staging_path"]))
            self.assertGreater(len(pending), 0)
            self.assertTrue(all(item.metadata.review_status == ReviewStatus.NORMALIZED for item in pending))
            for item in pending:
                with self.assertRaises(ValueError):
                    item.to_reviewed_entry()
            # The ordinary publisher must refuse the actual emitted artifact.
            output = io.StringIO()
            kb = Path(temp_dir) / "temporary-publish-target"
            with patch.object(sys, "argv", ["publish_staging", "--input", summary["staging_path"], "--knowledge-dir", str(kb)]):
                with patch("sys.stdout", output):
                    publish_main()
            result = json.loads(output.getvalue())
            self.assertEqual(result["published_entries"], 0)
            self.assertEqual(result["skipped_entries"], len(pending))
            self.assertFalse(kb.exists())
            extracted = yaml.safe_load(Path(summary["enriched_path"]).read_text(encoding="utf-8"))
            self.assertEqual(summary["pending_combat_entries"], len(extracted["combat_candidates"]))

    def test_combat_extraction_is_retained_without_publishable_output(self):
        project_root = Path(__file__).resolve().parents[1]
        source = project_root / "ingestion/raw/videos/bilibili-bundle-sample.yaml"
        def extract(**kwargs):
            document = _resolve_enriched_document(**kwargs)
            candidate = VideoCombatCandidate(candidate_id="synthetic-combat", segment_id=document.segments[0].segment_id,
                                             topic="合成战斗规则", facts=["合成证据"], confidence=0.8)
            return document.model_copy(update={"combat_candidates": [candidate]})
        with tempfile.TemporaryDirectory() as tmp:
            output = io.StringIO()
            with patch.object(sys, "argv", ["run_video_pipeline", "--input", str(source), "--workspace", tmp, "--extractor", "heuristic"]):
                with patch("qa_agent.app.run_video_pipeline._resolve_enriched_document", side_effect=extract), patch("sys.stdout", output):
                    main()
            summary = json.loads(output.getvalue())
            self.assertEqual(summary["pending_combat_entries"], 1)
            self.assertFalse((Path(tmp) / "knowledge_sources").exists())
            extracted = yaml.safe_load(Path(summary["enriched_path"]).read_text(encoding="utf-8"))
            self.assertEqual(extracted["combat_candidates"][0]["facts"], ["合成证据"])


if __name__ == "__main__":
    unittest.main()
