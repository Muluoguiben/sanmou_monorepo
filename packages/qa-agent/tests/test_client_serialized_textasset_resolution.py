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

from qa_agent.ingestion.client_serialized_textasset_resolution import (
    build_serialized_textasset_resolution_report,
)


class SerializedTextAssetResolutionTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "serialized_textasset_path_resolution_round175.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 175,
                    "slice": "serialized_textasset_path_id_object_offset_resolution",
                    "input_artifacts": [
                        {
                            "file_name": "luascripts_textasset_extract_round31.json",
                            "role": "Round31 TextAsset path/container and extracted payload catalog",
                            "size_bytes": 100,
                            "sha256": "a" * 64,
                        }
                    ],
                    "counts": {
                        "relevant_record_count": 104,
                        "container_record_valid_count": 104,
                        "container_record_invalid_count": 0,
                        "resolved_record_count": 104,
                        "unresolved_record_count": 0,
                        "ambiguous_record_count": 0,
                        "unique_path_id_count": 104,
                        "unique_resolved_object_offset_count": 16,
                        "unique_resolved_payload_sha1_count": 16,
                    },
                    "stem_summaries": [
                        {
                            "stem": "heros",
                            "record_count": 1,
                            "resolved_record_count": 1,
                            "unique_resolved_object_offset_count": 1,
                            "scenario_count": 1,
                            "script_len_counts": [{"script_len": 23232, "count": 1}],
                            "sample_paths": ["Assets/Bundles/LuaScripts/Data/heros.bytes"],
                        }
                    ],
                    "resolved_object_groups": [
                        {
                            "object_offset": 123,
                            "object_offset_hex": "0x7b",
                            "payload_offset": 136,
                            "payload_offset_hex": "0x88",
                            "stem": "heros",
                            "script_len": 23232,
                            "payload_sha1": "b" * 40,
                            "payload_sha256": "c" * 64,
                            "path_count": 1,
                            "path_id_count": 1,
                            "scenario_count": 1,
                            "sample_paths": ["Assets/Bundles/LuaScripts/Data/heros.bytes"],
                            "sample_path_ids": ["0x1"],
                        }
                    ],
                    "resolved_records": [
                        {
                            "path": "Assets/Bundles/LuaScripts/Data/heros.bytes",
                            "stem": "heros",
                            "scenario": "Scenario1",
                            "path_id_hex": "0x1",
                            "preload_index": 7,
                            "preload_size": 1,
                            "file_id": 0,
                            "container_record_offset_hex": "0x100",
                            "container_valid": True,
                            "candidate_count": 10,
                            "resolved": True,
                            "resolved_object_offset_hex": "0x7b",
                            "resolved_payload_offset_hex": "0x88",
                            "resolved_script_len": 23232,
                            "resolved_payload_sha1": "b" * 40,
                            "resolved_payload_sha256": "c" * 64,
                        }
                    ],
                    "prior_route_context": {
                        "round174_serialized_textasset_object_layout_confirmed": True,
                    },
                    "route_conclusion": {
                        "path_id_to_exact_object_offset_resolved": True,
                        "serialized_textasset_object_layout_confirmed": True,
                        "container_path_records_verified": True,
                        "catalog_payload_sha1_resolution_confirmed": True,
                        "metadata_object_table_independently_decrypted": False,
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "104/104 records resolve",
                        "strongest_negative_signal": "decoder is not recovered",
                        "search_policy": "use resolved offsets",
                    },
                    "evidence_refs": [
                        "NSLG_SERIALIZED_TEXTASSET_PATH_RESOLUTION:round175:0x1:0x7b"
                    ],
                    "next_static_targets": ["recover decoder using resolved offsets"],
                    "limitations": ["static resolution only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_resolution_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_serialized_textasset_resolution_report(
                input_path=input_path,
                source_id="fixture-serialized-resolution",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(
            report.schema_version,
            "nslg.serialized_textasset_path_resolution.v1",
        )
        self.assertEqual(report.source_id, "fixture-serialized-resolution")
        self.assertEqual(report.counts["resolved_record_count"], 104)
        self.assertTrue(report.route_conclusion["path_id_to_exact_object_offset_resolved"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.resolved_records[0].file_id, 0)

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_serialized_textasset_resolution import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "serialized-resolution.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_serialized_textasset_resolution",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-serialized-resolution",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(
            data["schema_version"],
            "nslg.serialized_textasset_path_resolution.v1",
        )
        self.assertEqual(data["source_id"], "fixture-serialized-resolution")
        self.assertEqual(data["counts"]["resolved_record_count"], 104)
        self.assertTrue(summary["path_id_to_exact_object_offset_resolved"])
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
