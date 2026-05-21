from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.ingestion.client_luascripts import build_luascripts_textasset_catalog


class LuaScriptsTextAssetCatalogTests(unittest.TestCase):
    def _summary(self) -> dict:
        return {
            "cab": "threads\\artifacts\\round31_unityfs_extract\\CAB-fixture",
            "bundle": "D:\\bilibili Game\\NSLG\\NSLG Game\\LocalPersistentData\\assets\\bundles\\luascripts.ns",
            "container_luascripts_bytes_entries": 20,
            "data_entries": 3,
            "relevant_records": [
                {
                    "path": "Assets/Bundles/LuaScripts/Data/Scenario1/hero/heros.bytes",
                    "path_id_hex": "0x1",
                    "stem": "heros",
                    "script_len": 128,
                    "sha1": "a" * 40,
                    "printable_score": 0.32,
                    "extracted_path": "threads\\artifacts\\round31_luascripts_textassets\\heros.bytes.bin",
                    "decompress_attempts": [{"name": "zlib", "ok": False, "error": "error: bad header"}],
                },
                {
                    "path": "Assets/Bundles/LuaScripts/Data/Scenario1/story/hero_story.bytes",
                    "path_id_hex": "0x2",
                    "stem": "hero_story",
                    "script_len": 256,
                    "sha1": "b" * 40,
                    "printable_score": 0.81,
                    "extracted_path": "C:\\Users\\Lan\\secret\\hero_story.bytes.bin",
                    "decompress_attempts": [],
                },
            ],
        }

    def test_catalog_classifies_assets_and_sanitizes_paths(self) -> None:
        catalog = build_luascripts_textasset_catalog(
            self._summary(),
            source_id="fixture-round",
            generated_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
        )
        dumped = json.dumps(catalog.model_dump(mode="json"), ensure_ascii=False)

        self.assertEqual(catalog.cataloged_records, 2)
        self.assertEqual(catalog.unique_stems, 2)
        self.assertEqual(catalog.scenarios, ["Scenario1"])
        self.assertIn("hero", catalog.kb_domain_counts)
        self.assertIn("story_plot", catalog.kb_domain_counts)
        self.assertIn("heros", catalog.high_value_stems)
        self.assertEqual(catalog.records[0].extraction_status, "obfuscated_binary_pending_decoder")
        self.assertEqual(catalog.records[1].extracted_artifact, "hero_story.bytes.bin")
        self.assertNotIn("LocalPersistentData", dumped)
        self.assertNotIn("D:\\", dumped)

    def test_catalog_cli_writes_yaml(self) -> None:
        from qa_agent.app.catalog_luascripts_textassets import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            input_path = tmp / "luascripts_extract.json"
            output_path = tmp / "catalog.yaml"
            input_path.write_text(json.dumps(self._summary(), ensure_ascii=False), encoding="utf-8")
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "catalog_luascripts_textassets",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-round",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["source_id"], "fixture-round")
        self.assertEqual(data["cataloged_records"], 2)
        self.assertEqual(summary["cataloged_records"], 2)
        self.assertEqual(summary["unique_stems"], 2)


if __name__ == "__main__":
    unittest.main()
