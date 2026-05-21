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

from qa_agent.ingestion.client_serialized_textasset_layout import (
    build_serialized_textasset_layout_report,
)


class SerializedTextAssetLayoutTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "serialized_textasset_layout_probe_round174.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 174,
                    "slice": "serialized_textasset_object_layout_probe",
                    "input_artifacts": [
                        {
                            "file_name": "luascripts_textasset_extract_round31.json",
                            "role": "Round31 TextAsset path and object match catalog",
                            "size_bytes": 100,
                            "sha256": "a" * 64,
                        }
                    ],
                    "counts": {
                        "relevant_record_count": 104,
                        "match_count": 932,
                        "valid_layout_count": 932,
                        "invalid_layout_count": 0,
                        "name_stem_match_count": 932,
                        "name_stem_mismatch_count": 0,
                        "payload_offset_formula_match_count": 932,
                        "script_len_match_count": 932,
                        "unique_object_offset_count": 52,
                        "unique_payload_hash_count": 52,
                        "unique_stem_count": 16,
                        "duplicate_object_offset_group_count": 40,
                    },
                    "path_record_summary": {
                        "record_count": 104,
                        "unique_path_count": 104,
                        "unique_path_id_count": 104,
                        "preload_size_counts": [{"preload_size": 1, "count": 104}],
                        "path_record_offset_min": 1,
                        "path_record_offset_max": 2,
                        "sample_paths": ["Assets/Bundles/LuaScripts/Data/heros.bytes"],
                    },
                    "stem_summaries": [
                        {
                            "stem": "heros",
                            "record_count": 1,
                            "match_count": 1,
                            "valid_layout_count": 1,
                            "name_stem_match_count": 1,
                            "unique_object_offset_count": 1,
                            "unique_payload_hash_count": 1,
                            "repeated_object_offset_group_count": 0,
                            "script_len_counts": [{"script_len": 23232, "count": 1}],
                            "scenario_count": 0,
                            "sample_paths": ["Assets/Bundles/LuaScripts/Data/heros.bytes"],
                        }
                    ],
                    "object_layout_groups": [
                        {
                            "object_offset": 123,
                            "object_offset_hex": "0x7b",
                            "stem": "heros",
                            "parsed_name": "heros",
                            "parsed_name_len": 5,
                            "payload_offset": 136,
                            "payload_offset_hex": "0x88",
                            "script_len": 23232,
                            "layout_valid": True,
                            "match_count": 1,
                            "path_count": 1,
                            "path_id_count": 1,
                            "scenario_count": 0,
                            "payload_sha256": "b" * 64,
                            "payload_hash_count": 1,
                            "sample_paths": ["Assets/Bundles/LuaScripts/Data/heros.bytes"],
                            "sample_path_ids": ["0x1"],
                            "payload_first16_hex": "00" * 16,
                            "payload_last16_hex": "11" * 16,
                        }
                    ],
                    "prior_route_context": {
                        "round172_payload_variant_count": 932,
                        "round173_textasset_payload_owner_proven": False,
                    },
                    "route_conclusion": {
                        "serialized_textasset_object_layout_confirmed": True,
                        "static_payload_offsets_and_lengths_confirmed": True,
                        "path_id_to_exact_object_offset_resolved": False,
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "932 TextAsset object matches validate layout",
                        "strongest_negative_signal": "path_id to exact object offset is unresolved",
                        "search_policy": "parse SerializedFile tables",
                    },
                    "evidence_refs": [
                        "NSLG_SERIALIZED_TEXTASSET_LAYOUT:round174:stem:heros"
                    ],
                    "next_static_targets": ["parse SerializedFile object table"],
                    "limitations": ["static layout probe only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_layout_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_serialized_textasset_layout_report(
                input_path=input_path,
                source_id="fixture-serialized-layout",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.serialized_textasset_layout.v1")
        self.assertEqual(report.source_id, "fixture-serialized-layout")
        self.assertEqual(report.counts["match_count"], 932)
        self.assertEqual(report.stem_summaries[0].stem, "heros")
        self.assertTrue(report.route_conclusion["serialized_textasset_object_layout_confirmed"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_serialized_textasset_layout import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "serialized-layout.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_serialized_textasset_layout",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-serialized-layout",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.serialized_textasset_layout.v1")
        self.assertEqual(data["source_id"], "fixture-serialized-layout")
        self.assertEqual(data["counts"]["valid_layout_count"], 932)
        self.assertTrue(summary["serialized_textasset_object_layout_confirmed"])
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
