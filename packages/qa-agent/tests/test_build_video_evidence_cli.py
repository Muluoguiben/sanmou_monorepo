from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.app.build_video_evidence import main


class BuildVideoEvidenceCliTests(unittest.TestCase):
    def test_build_video_evidence_cli_writes_normalized_document(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        input_path = project_root / "ingestion" / "raw" / "videos" / "bilibili-bundle-sample.yaml"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "video-evidence.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "build_video_evidence",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()

            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["video_id"], "BV1TEST4x7yz")
            self.assertEqual(summary["segments"], 2)
            self.assertTrue(output_path.exists())

            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["segments"][0]["segment_id"], "intro-lineup-18-64")
            self.assertEqual(data["segments"][1]["segment_id"], "matchup-64-118")
            self.assertEqual(data["lineup_candidates"], [])


if __name__ == "__main__":
    unittest.main()
