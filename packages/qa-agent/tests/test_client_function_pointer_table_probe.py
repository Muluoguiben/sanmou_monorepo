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

from qa_agent.ingestion.client_function_pointer_table_probe import (
    build_function_pointer_table_probe_report,
)


class ClientFunctionPointerTableProbeTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        path = root / "gameassembly_function_pointer_table_probe_round184.json"
        path.write_text(
            json.dumps(
                {
                    "round": 184,
                    "slice": "gameassembly_function_pointer_table_probe",
                    "input_artifacts": [
                        {
                            "role": "module:GameAssembly.dll",
                            "file_name": r"C:\NSLG\GameAssembly.dll",
                            "size_bytes": 94127168,
                            "sha256": "a" * 64,
                        }
                    ],
                    "gameassembly_summary": {
                        "file_name": "GameAssembly.dll",
                        "size_bytes": 94127168,
                        "sha256": "b" * 64,
                        "image_base": "0x180000000",
                        "entry_rva": "0x5faa3c",
                        "section_count": 6,
                        "pdata_function_count": 290472,
                    },
                    "scan_policy": {
                        "sections": [".data", ".rdata"],
                        "slot_width": 8,
                        "recognized_encodings": ["absolute_va", "raw_rva"],
                        "recognized_target": "qword value resolves to a .pdata function begin",
                        "known_method_table_source": "round180 module_array_records",
                        "known_code_registration_field_source": "round181 primary_code_registration_layout",
                    },
                    "known_method_pointer_tables": {
                        "table_count": 96,
                        "total_declared_method_pointer_count": 190521,
                        "sample": [
                            {
                                "module_name": "Assembly-CSharp.dll",
                                "start_rva": "0x50b9840",
                                "method_pointer_count": 30078,
                            }
                        ],
                    },
                    "known_code_registration_field_tables": {
                        "table_count": 6,
                        "total_declared_pointer_count": 203656,
                        "sample": [
                            {
                                "field_offset": "0x10",
                                "pointer_table_rva": "0x480fd10",
                                "declared_count": 150506,
                            }
                        ],
                    },
                    "target_function_summary": {
                        "target_function_count": 26,
                        "by_category": {
                            "dispatcher_candidate": 24,
                            "global_metadata_string_ref": 2,
                        },
                        "targets": [
                            {
                                "rva": "0xe4ec50",
                                "label": "dispatcher_candidate_rank_1",
                                "category": "dispatcher_candidate",
                            }
                        ],
                    },
                    "scan_summary": {
                        "function_pointer_hit_count": 342009,
                        "pointer_run_count": 57759,
                        "relevant_function_pointer_hit_count": 22,
                        "outside_known_tables_relevant_hit_count": 0,
                        "outside_known_tables_sampled_run_count": 24,
                        "section_counts": {".data": 133465, ".rdata": 208544},
                        "encoding_counts": {"absolute_va": 342009},
                        "target_category_counts": {"dispatcher_candidate": 22},
                    },
                    "codegen_method_table_stats": [
                        {
                            "module_name": "Assembly-CSharp.dll",
                            "module_index": 5,
                            "method_pointer_table_rva": "0x50b9840",
                            "method_pointer_count": 30078,
                            "function_pointer_hit_count": 25077,
                            "relevant_target_hit_count": 8,
                            "target_category_counts": {"dispatcher_candidate": 8},
                        }
                    ],
                    "code_registration_field_table_stats": [
                        {
                            "field_offset": "0x10",
                            "pointer_table_rva": "0x480fd10",
                            "declared_count": 150506,
                            "function_pointer_hit_count": 123600,
                            "relevant_target_hit_count": 2,
                            "target_category_counts": {"dispatcher_candidate": 2},
                        }
                    ],
                    "relevant_function_pointer_hits": [
                        {
                            "slot_rva": "0x50c6928",
                            "slot_section": ".data",
                            "target_rva": "0xe4ec50",
                            "target_label": "dispatcher_candidate_rank_1",
                            "target_category": "dispatcher_candidate",
                            "known_method_table_module": "Assembly-CSharp.dll",
                            "known_method_table_index": 6685,
                        },
                        {
                            "slot_rva": "0x4814df0",
                            "slot_section": ".rdata",
                            "target_rva": "0x2c6ee40",
                            "target_label": "dispatcher_candidate_rank_6",
                            "target_category": "dispatcher_candidate",
                            "known_code_registration_field": "0x10",
                            "known_code_registration_index": 2588,
                        },
                    ],
                    "outside_known_table_runs": [
                        {
                            "section": ".rdata",
                            "start_rva": "0x44f3eb8",
                            "end_rva": "0x44f5678",
                            "hit_count": 760,
                            "candidate_kind": "outside_known_table_pointer_run",
                            "target_category_counts": {},
                            "target_labels": [],
                        }
                    ],
                    "counts": {
                        "known_method_table_count": 96,
                        "known_code_registration_field_table_count": 6,
                        "function_pointer_hit_count": 342009,
                        "known_codegen_method_table_hit_count": 133465,
                        "known_code_registration_field_hit_count": 172773,
                        "outside_known_table_hit_count": 35771,
                        "relevant_function_pointer_hit_count": 22,
                        "known_codegen_method_table_relevant_hit_count": 20,
                        "known_code_registration_field_relevant_hit_count": 2,
                        "outside_known_table_relevant_hit_count": 0,
                        "global_metadata_function_pointer_hit_count": 0,
                        "dispatcher_pointer_hit_count": 22,
                        "dispatcher_pointer_hits_outside_known_tables": 0,
                        "initializer_candidate_table_count": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                        "protected_metadata_method_ownership_recovered": 0,
                    },
                    "route_conclusion": {
                        "function_pointer_tables_scanned": True,
                        "dispatcher_pointer_hits_found": True,
                        "dispatcher_pointer_hits_classified_as_known_il2cpp_tables": True,
                        "global_metadata_function_pointer_hits_found": False,
                        "outside_known_table_relevant_pointer_hits_found": False,
                        "independent_initializer_table_candidate_found": False,
                        "initializer_table_route_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_FUNCTION_POINTER_TABLE:round184:nonexec-function-pointer-scan"
                    ],
                    "next_static_targets": ["recover protected metadata ownership"],
                    "limitations": ["static route evidence only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_build_function_pointer_table_probe_report_sanitizes_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._write_fixture(Path(tmp))
            report = build_function_pointer_table_probe_report(
                input_path=fixture,
                source_id="gameassembly-function-pointer-table-probe-round115",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_function_pointer_table_probe.v1")
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertEqual(report.counts["function_pointer_hit_count"], 342009)
        self.assertEqual(report.counts["dispatcher_pointer_hits_outside_known_tables"], 0)
        self.assertFalse(report.route_conclusion["initializer_table_route_recovered"])
        self.assertFalse(report.route_conclusion["init_lua_env_method_pointer_recovered"])
        self.assertEqual(report.relevant_function_pointer_hits[0]["known_method_table_index"], 6685)
        self.assertEqual(report.relevant_function_pointer_hits[1]["known_code_registration_field"], "0x10")

    def test_cli_writes_yaml(self) -> None:
        from qa_agent.app import summarize_gameassembly_function_pointer_table_probe as cli

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._write_fixture(root)
            output = root / "out.yaml"
            argv = [
                "summarize_gameassembly_function_pointer_table_probe",
                "--input",
                str(fixture),
                "--output",
                str(output),
                "--source-id",
                "fixture-function-pointer-table",
            ]
            with patch.object(sys, "argv", argv), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cli.main()

            data = yaml.safe_load(output.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_function_pointer_table_probe.v1")
        self.assertEqual(data["source_id"], "fixture-function-pointer-table")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["dispatcher_pointer_hit_count"], 22)
        self.assertEqual(summary["dispatcher_pointer_hits_outside_known_tables"], 0)
        self.assertFalse(summary["initializer_table_route_recovered"])


if __name__ == "__main__":
    unittest.main()
