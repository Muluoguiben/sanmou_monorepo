from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.app.video_extract import main


class VideoCliTests(unittest.TestCase):
    def test_video_extract_cli_uses_existing_candidates_and_writes_outputs(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        input_path = project_root / "ingestion" / "raw" / "videos" / "bilibili-lineup-sample.yaml"

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "video-knowledge.yaml"
            staging_output_path = Path(temp_dir) / "video-staging.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "video_extract",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--staging-output",
                    str(staging_output_path),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()

            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["lineup_candidates"], 1)
            self.assertTrue(output_path.exists())
            self.assertTrue(staging_output_path.exists())

            enriched = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(enriched["source"]["video_id"], "BV1TEST4x7yz")
            self.assertEqual(len(enriched["lineup_candidates"]), 1)

            staged = yaml.safe_load(staging_output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(staged), 1)
            self.assertEqual(staged[0]["entry"]["entry_kind"], "lineup_solution")
            self.assertTrue(staged[0]["entry"]["source_ref"].startswith("BILIBILI:BV1TEST4x7yz#"))

    def test_video_extract_cli_requires_key_when_no_candidates_are_present(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        input_path = project_root / "ingestion" / "raw" / "videos" / "bilibili-evidence-sample.yaml"
        stdout = io.StringIO()
        with patch.object(sys, "argv", ["video_extract", "--input", str(input_path)]):
            with patch("sys.stdout", stdout):
                main()
        result = json.loads(stdout.getvalue())
        self.assertEqual(len(result["lineup_candidates"]), 1)
        self.assertEqual(result["lineup_candidates"][0]["topic"], "S13诸葛亮开荒队")

    def test_video_extract_cli_gemini_mode_requires_key(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        input_path = project_root / "ingestion" / "raw" / "videos" / "bilibili-evidence-sample.yaml"
        with patch.object(sys, "argv", ["video_extract", "--input", str(input_path), "--extractor", "gemini"]):
            with self.assertRaises(RuntimeError):
                main()


if __name__ == "__main__":
    unittest.main()
