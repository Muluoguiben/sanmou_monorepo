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

from qa_agent.ingestion.client_global_metadata_loader_scan import (
    build_global_metadata_loader_scan_report,
)


class GlobalMetadataLoaderScanTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 168,
                    "slice": "global_metadata_loader_mutation_static_scan",
                    "metadata_wrapper": {
                        "magic": "0xfab11baf",
                        "file_size": 21182776,
                        "payload_offset": 8,
                        "payload_size": 21182768,
                    },
                    "input_artifacts": [
                        {
                            "file_name": r"C:\local\global_metadata_transform_probe_round167.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "counts": {
                        "binary_count": 4,
                        "candidate_count": 554,
                        "full_loader_mutation_candidate_count": 0,
                        "file_16_candidate_count": 2,
                        "metadata_ref_candidate_count": 0,
                        "raw_hit_global_metadata_ascii": 2,
                        "raw_hit_global_metadata_short_ascii": 2,
                    },
                    "binaries": [
                        {
                            "binary_name": "NEP2.dll",
                            "exists": True,
                            "sha256": "b" * 64,
                            "image_base": "0x180000000",
                            "pdata_function_count": 42977,
                            "import_class_counts": {
                                "file_or_mapping": 7,
                                "file_read_or_mapping": 5,
                            },
                            "raw_metadata_hit_counts": {"global_metadata_ascii": 0},
                            "instruction_totals": {"instructions": 36997},
                            "candidate_count": 16,
                            "full_loader_mutation_candidate_count": 0,
                            "file_16_candidate_count": 2,
                            "metadata_ref_candidate_count": 0,
                            "top_file_16_candidates": [
                                {
                                    "binary": "NEP2.dll",
                                    "function": {
                                        "begin": "0xd410",
                                        "end": "0xd71e",
                                        "size": "0x30e",
                                    },
                                    "score": 168,
                                    "reasons": ["file_api_ref=2", "block16_or_align=1"],
                                    "classification": {
                                        "has_file_api": True,
                                        "has_read_or_mapping_api": False,
                                        "has_metadata_ref_or_wrapper_const": False,
                                        "has_payload_plus8_signal": True,
                                        "has_16byte_or_loop_signal": True,
                                        "full_loader_mutation_gate": False,
                                    },
                                    "counts": {"file_api_ref": 2, "block_size_16": 1},
                                    "import_refs": [
                                        {
                                            "rva": "0xd555",
                                            "import": "KERNEL32.dll!FindFirstFileW",
                                            "class": "file_or_mapping",
                                        }
                                    ],
                                    "constant_refs": [
                                        {"rva": "0xd611", "label": "block_size_16"}
                                    ],
                                    "evidence_ref": (
                                        "NSLG_GLOBAL_METADATA_LOADER:"
                                        "global-metadata-loader-mutation-scan-round168:"
                                        "NEP2.dll:0xd410"
                                    ),
                                }
                            ],
                        }
                    ],
                    "route_conclusion": {
                        "full_loader_mutation_candidate_found": False,
                        "file_api_16byte_candidates_found": True,
                        "metadata_reference_candidates_found": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "textasset_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "Top file+16 route candidate is NEP2.dll 0xd410.",
                        "strongest_negative_signal": "No full loader mutation gate was found.",
                        "search_policy": "Deep-slice NEP2 file+16 candidates.",
                    },
                    "next_static_targets": ["Deep-slice NEP2.dll 0xd410"],
                    "limitations": ["Offline/static scan only"],
                    "evidence_refs": [
                        "NSLG_GLOBAL_METADATA_LOADER:global-metadata-loader-mutation-scan-round168:summary"
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_loader_scan_as_static_trace_seed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round168.json"
            self._write_input(input_path)
            report = build_global_metadata_loader_scan_report(
                input_path=input_path,
                source_id="global-metadata-loader-mutation-scan-round67",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.global_metadata_loader_scan.v1")
        self.assertEqual(report.source_id, "global-metadata-loader-mutation-scan-round67")
        self.assertEqual(report.counts["candidate_count"], 554)
        self.assertEqual(report.counts["file_16_candidate_count"], 2)
        self.assertEqual(report.counts["full_loader_mutation_candidate_count"], 0)
        self.assertFalse(report.route_conclusion["plaintext_metadata_recovered"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.input_artifacts[0].file_name, "global_metadata_transform_probe_round167.json")
        self.assertEqual(report.top_file_16_candidates[0]["function"]["begin"], "0xd410")
        self.assertFalse(
            report.top_file_16_candidates[0]["classification"]["full_loader_mutation_gate"]
        )

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_global_metadata_loader_scan import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round168.json"
            output_path = root / "loader-scan.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_global_metadata_loader_scan",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "global-metadata-loader-mutation-scan-round67",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.global_metadata_loader_scan.v1")
        self.assertEqual(data["source_id"], "global-metadata-loader-mutation-scan-round67")
        self.assertFalse(data["route_conclusion"]["plaintext_metadata_recovered"])
        self.assertEqual(summary["candidate_count"], 554)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
