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

from qa_agent.ingestion.client_nep2_init_data_owner_scan import (
    build_nep2_init_data_owner_scan_report,
)


class Nep2InitDataOwnerScanTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 171,
                    "slice": "nep2_init_luascripts_data_owner_scan",
                    "binary_name": r"D:\bilibili Game\NSLG\NSLG Game\NEP2.dll",
                    "input_artifacts": [
                        {
                            "file_name": r"C:\local\nep2_init_luascripts_bridge_summary_round161.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "counts": {
                        "focus_target_count": 90,
                        "data_reference_count": 255,
                        "data_ref_owner_function_count": 0,
                        "bridge_record_window_count": 4,
                        "bridge_record_with_code_pointer_count": 2,
                        "inspected_function_count": 13,
                        "payload_owner_candidate_count": 0,
                        "partial_provenance_function_count": 1,
                    },
                    "target_kind_counts": {"raw_string_hit": 71},
                    "data_ref_section_counts": {".data": 73, ".rdata": 2, ".rsrc": 180},
                    "candidate_verdict_counts": {
                        "provenance_partial_no_payload_owner": 1,
                        "tiny_metadata_or_lambda_helper": 9,
                    },
                    "data_reference_samples": [
                        {
                            "kind": "rva32",
                            "section": ".data",
                            "at_rva": "0x881390",
                            "target_rva": "0x4040",
                            "target_labels": ["code pointer slot"],
                            "target_kinds": ["bridge_code_pointer_slot"],
                        }
                    ],
                    "bridge_record_windows": [
                        {
                            "center_rva": "0x881320",
                            "label": "InitLuaScriptsScan@CGameProtector",
                            "section": ".data",
                            "code_pointer_count": 2,
                            "data_pointer_count": 0,
                            "string_ref_count": 1,
                            "code_pointer_samples": [
                                {"at_rva": "0x881390", "target_rva": "0x4040"}
                            ],
                        }
                    ],
                    "inspected_functions": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_DATA_OWNER:round171:function:0x6033f0",
                            "function": {"begin": "0x6033f0", "end": "0x60366d"},
                            "source": "round161_candidate",
                            "verdict": "provenance_partial_no_payload_owner",
                            "score": 308,
                            "counts": {"file_import_calls": 2},
                            "file_import_names": ["CloseHandle", "CreateFileW"],
                            "payload_keyword_refs": [],
                            "bridge_keyword_refs": [],
                            "has_16byte_or_loop_signal": True,
                        }
                    ],
                    "route_conclusion": {
                        "init_luascripts_bridge_metadata_confirmed": True,
                        "data_reference_owners_found": False,
                        "bridge_record_code_pointers_found": True,
                        "payload_owner_candidate_found": False,
                        "file_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "global_metadata_loader_proven": False,
                        "plaintext_metadata_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "bridge records resolve to support pointers",
                        "strongest_negative_signal": "no payload-owner candidate",
                        "search_policy": "treat as routing evidence only",
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_INIT_DATA_OWNER:nep2-init-data-owner-scan-round171:summary"
                    ],
                    "next_static_targets": ["prioritize TextAsset/LuaScripts payload decoder"],
                    "limitations": ["static scan only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_init_data_owner_scan_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round171.json"
            self._write_input(input_path)
            report = build_nep2_init_data_owner_scan_report(
                input_path=input_path,
                source_id="nep2-init-data-owner-scan-round76",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.nep2_init_data_owner_scan.v1")
        self.assertEqual(report.source_id, "nep2-init-data-owner-scan-round76")
        self.assertEqual(report.binary_name, "NEP2.dll")
        self.assertEqual(report.input_artifacts[0].file_name, "nep2_init_luascripts_bridge_summary_round161.json")
        self.assertEqual(report.counts["data_reference_count"], 255)
        self.assertEqual(report.counts["payload_owner_candidate_count"], 0)
        self.assertFalse(report.route_conclusion["payload_owner_candidate_found"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.inspected_functions[0]["file_import_names"], ["CloseHandle", "CreateFileW"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_nep2_init_data_owner_scan import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round171.json"
            output_path = root / "init-data-owner.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_init_data_owner_scan",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "nep2-init-data-owner-scan-round76",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.nep2_init_data_owner_scan.v1")
        self.assertEqual(data["source_id"], "nep2-init-data-owner-scan-round76")
        self.assertEqual(data["counts"]["inspected_function_count"], 13)
        self.assertFalse(data["route_conclusion"]["payload_owner_candidate_found"])
        self.assertEqual(summary["payload_owner_candidate_count"], 0)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
