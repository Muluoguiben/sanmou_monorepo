from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from qa_agent.app.run_video_pipeline import main


class RunVideoPipelineCliTests(unittest.TestCase):
    def test_pipeline_runs_end_to_end_with_heuristic_extractor(self) -> None:
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
            self.assertIn("season-s13.yaml", summary["bucket_stats"])
            self.assertEqual(summary["query_results"]["lineup"]["coverage"], "exact")
            self.assertEqual(summary["query_results"]["lineup"]["evidence"][0]["source_ref"], "BILIBILI:BV1TEST4x7yz#18-64")


if __name__ == "__main__":
    unittest.main()
