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

from qa_agent.ingestion.client_nep2_read_mapping_owner_scan import (
    build_nep2_read_mapping_owner_scan_report,
)


class Nep2ReadMappingOwnerScanTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 170,
                    "slice": "nep2_read_mapping_owner_static_scan",
                    "input_artifacts": [
                        {
                            "file_name": r"C:\local\nep2_global_metadata_loader_deep_slice_round169.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "nep2_file": {
                        "file_name": r"D:\bilibili Game\NSLG\NSLG Game\NEP2.dll",
                        "sha256": "b" * 64,
                    },
                    "import_class_counts": {"read_or_mapping": 8},
                    "counts": {
                        "read_mapping_owner_count": 2,
                        "readfile_owner_count": 0,
                        "mapview_owner_count": 0,
                        "create_file_mapping_owner_count": 0,
                        "get_file_size_owner_count": 2,
                        "metadata_provenance_owner_count": 0,
                        "luascripts_provenance_owner_count": 0,
                        "protected_payload_signal_owner_count": 0,
                        "provenance_linked_owner_count": 0,
                    },
                    "verdict_counts": {
                        "actual_read_mapping_owner_no_metadata_or_luascripts_provenance": 2
                    },
                    "read_mapping_import_owner_counts": {"GetFileSize": 1, "GetFileSizeEx": 1},
                    "owners": [
                        {
                            "target_rva": "0xd720",
                            "function": {"begin": "0xd720", "end": "0xd7b3"},
                            "verdict": "actual_read_mapping_owner_no_metadata_or_luascripts_provenance",
                            "owner_read_mapping_events": [
                                {
                                    "rva": "0xd798",
                                    "import": "KERNEL32.dll!GetFileSizeEx",
                                    "import_name": "GetFileSizeEx",
                                }
                            ],
                            "counts": {"import:GetFileSizeEx": 1},
                            "imports_seen": ["CloseHandle", "GetFileSizeEx"],
                            "read_mapping_imports_seen": ["GetFileSizeEx"],
                            "neighborhood_provenance_labels": [],
                            "has_read_or_mapping_import": True,
                            "has_metadata_provenance": False,
                            "has_luascripts_provenance": False,
                            "has_protected_payload_signal": False,
                            "evidence_ref": (
                                "NSLG_NEP2_READ_MAPPING_OWNER:"
                                "nep2-read-mapping-owner-scan-round170:0xd720"
                            ),
                        }
                    ],
                    "route_conclusion": {
                        "actual_read_mapping_owners_found": True,
                        "metadata_linked_read_mapping_owner_found": False,
                        "global_metadata_loader_proven": False,
                        "file_buffer_owner_proven": False,
                        "metadata_wrapper_or_string_provenance_found": False,
                        "luascripts_or_init_scan_provenance_found": False,
                        "protected_payload_signal_found": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "actual GetFileSize owners found",
                        "strongest_negative_signal": "no metadata/LuaScripts provenance",
                        "search_policy": "pivot to data-reference ownership",
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_READ_MAPPING_OWNER:nep2-read-mapping-owner-scan-round170:summary"
                    ],
                    "next_static_targets": ["pivot to NEP2 InitLuaScriptsScan data ownership"],
                    "limitations": ["static import-owner scan only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_read_mapping_owner_scan_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round170.json"
            self._write_input(input_path)
            report = build_nep2_read_mapping_owner_scan_report(
                input_path=input_path,
                source_id="nep2-read-mapping-owner-scan-round73",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.nep2_read_mapping_owner_scan.v1")
        self.assertEqual(report.source_id, "nep2-read-mapping-owner-scan-round73")
        self.assertEqual(report.input_artifacts[0].file_name, "nep2_global_metadata_loader_deep_slice_round169.json")
        self.assertEqual(report.nep2_file["file_name"], "NEP2.dll")
        self.assertEqual(report.counts["read_mapping_owner_count"], 2)
        self.assertEqual(report.counts["provenance_linked_owner_count"], 0)
        self.assertFalse(report.route_conclusion["metadata_linked_read_mapping_owner_found"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.owners[0]["read_mapping_imports_seen"], ["GetFileSizeEx"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_nep2_read_mapping_owner_scan import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round170.json"
            output_path = root / "owner-scan.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_read_mapping_owner_scan",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "nep2-read-mapping-owner-scan-round73",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.nep2_read_mapping_owner_scan.v1")
        self.assertEqual(data["source_id"], "nep2-read-mapping-owner-scan-round73")
        self.assertEqual(data["counts"]["read_mapping_owner_count"], 2)
        self.assertFalse(data["route_conclusion"]["metadata_linked_read_mapping_owner_found"])
        self.assertEqual(summary["provenance_linked_owner_count"], 0)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
