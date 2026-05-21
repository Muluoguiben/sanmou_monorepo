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

from qa_agent.ingestion.client_registration_layout_probe import (
    build_registration_layout_report,
)


class ClientRegistrationLayoutProbeTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        path = root / "gameassembly_registration_layout_probe_round181.json"
        path.write_text(
            json.dumps(
                {
                    "round": 181,
                    "slice": "gameassembly_registration_layout_probe",
                    "input_artifacts": [
                        {
                            "role": "module:GameAssembly.dll",
                            "file_name": r"C:\NSLG\GameAssembly.dll",
                            "size_bytes": 94127168,
                            "sha256": "a" * 64,
                        }
                    ],
                    "round180_anchor": {
                        "registration_anchor": {
                            "codegen_modules_count_field_rva": "0x43327a8",
                            "codegen_modules_pointer_ref_rva": "0x43327b0",
                            "declared_codegen_module_count": 98,
                            "codegen_modules_array_rva": "0x50a2840",
                            "field_owner_candidate_rva": "0x4332718",
                            "field_owner_note": "previous owner inference",
                        },
                        "counts": {
                            "codegen_modules_field_candidate_count": 1,
                            "declared_codegen_module_count": 98,
                        },
                    },
                    "code_registration_start_candidates": [
                        {
                            "candidate_start_rva": "0x4332730",
                            "candidate_start_section": ".rdata",
                            "score": 147,
                            "count_pointer_pair_count": 6,
                            "nonzero_count_pointer_pair_count": 6,
                            "pointer_only_field_count": 9,
                            "codegen_modules_count_field_offset": "0x78",
                            "codegen_modules_pointer_field_offset": "0x80",
                            "codegen_modules_count_field_rva": "0x43327a8",
                            "codegen_modules_pointer_field_rva": "0x43327b0",
                            "codegen_modules_array_rva": "0x50a2840",
                            "sample_fields": [
                                {
                                    "offset": "0x78",
                                    "rva": "0x43327a8",
                                    "qword": 98,
                                    "next_qword": "0x1850a2840",
                                    "next_points_to_section": ".rdata",
                                    "next_points_to_rva": "0x50a2840",
                                    "looks_like_count_pointer_pair": True,
                                    "known_field": "CodeGenModules",
                                }
                            ],
                        }
                    ],
                    "primary_code_registration_layout": {
                        "candidate_start_rva": "0x4332730",
                        "candidate_start_va": "0x184332730",
                        "candidate_end_rva": "0x43327b8",
                        "codegen_modules_field_offsets": {
                            "count_offset": "0x78",
                            "pointer_offset": "0x80",
                            "count_rva": "0x43327a8",
                            "pointer_rva": "0x43327b0",
                            "array_rva": "0x50a2840",
                        },
                        "field_rows": [
                            {
                                "offset": "0x78",
                                "rva": "0x43327a8",
                                "qword": 98,
                                "next_qword": "0x1850a2840",
                                "next_points_to_section": ".rdata",
                                "next_points_to_rva": "0x50a2840",
                                "looks_like_count_pointer_pair": True,
                                "known_field": "CodeGenModules",
                            }
                        ],
                    },
                    "registration_xref_summary": {
                        "available": True,
                        "searched_target_count": 10,
                        "code_ref_count": 0,
                        "raw_va_ref_count": 7,
                        "raw_va_refs": [
                            {
                                "target_label": "codegen_modules_array",
                                "target_rva": "0x50a2840",
                                "ref_rva": "0x43327b0",
                                "ref_section": ".rdata",
                            }
                        ],
                    },
                    "metadata_registration_candidate_scan": {
                        "candidate_count": 5,
                        "top_candidates": [
                            {
                                "candidate_rva": "0x45893d0",
                                "score": 121,
                                "count_pointer_pair_count": 9,
                                "pointer_section_counts": {".data": 9},
                                "sample_text_pointer_count": 0,
                                "sample_data_pointer_count": 31,
                                "fields": [
                                    {
                                        "offset": "0x0",
                                        "count": 4,
                                        "pointer_rva": "0x51ba7c0",
                                        "pointer_section": ".data",
                                        "sample": [
                                            {
                                                "index": 0,
                                                "value": "0x185343040",
                                                "target_section": ".data",
                                                "target_rva": "0x5343040",
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                    },
                    "counts": {
                        "code_registration_start_candidate_count": 1,
                        "primary_code_registration_start_rva": 70461232,
                        "code_registration_count_pointer_pair_count": 6,
                        "code_registration_pointer_only_field_count": 9,
                        "codegen_modules_field_offset": 120,
                        "known_codegen_modules_count": 98,
                        "layout_field_row_count": 18,
                        "registration_code_ref_count": 0,
                        "registration_raw_va_ref_count": 7,
                        "metadata_registration_candidate_count": 5,
                        "metadata_registration_paired_by_callsite": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "route_conclusion": {
                        "code_registration_layout_refined": True,
                        "round180_owner_inference_corrected": True,
                        "codegen_modules_field_offset_confirmed": True,
                        "registration_callsite_recovered": False,
                        "metadata_registration_candidate_recovered": True,
                        "metadata_registration_paired_by_callsite": False,
                        "method_index_to_pointer_map_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "layout refined",
                        "strongest_negative_signal": "callsite not recovered",
                        "search_policy": "require callsite pair",
                    },
                    "evidence_refs": [
                        "NSLG_REGISTRATION_LAYOUT:round181:code-registration-start"
                    ],
                    "next_static_targets": ["recover registration callsite"],
                    "limitations": ["static route evidence only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_build_registration_layout_report_sanitizes_and_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._write_fixture(Path(tmp))
            report = build_registration_layout_report(
                input_path=fixture,
                source_id="gameassembly-registration-layout-probe-round106",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_registration_layout_probe.v1")
        self.assertEqual(report.source_id, "gameassembly-registration-layout-probe-round106")
        self.assertEqual(report.round, 181)
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertEqual(report.counts["primary_code_registration_start_rva"], 70461232)
        self.assertEqual(report.counts["codegen_modules_field_offset"], 120)
        self.assertTrue(report.route_conclusion["code_registration_layout_refined"])
        self.assertFalse(report.route_conclusion["metadata_registration_paired_by_callsite"])
        self.assertEqual(
            report.primary_code_registration_layout["codegen_modules_field_offsets"][
                "count_offset"
            ],
            "0x78",
        )
        self.assertEqual(
            report.metadata_registration_candidate_scan["top_candidates"][0]["candidate_rva"],
            "0x45893d0",
        )
        self.assertIn("weak/unpaired", report.metadata_registration_candidate_scan["scan_policy"])

    def test_cli_writes_yaml(self) -> None:
        from qa_agent.app import summarize_gameassembly_registration_layout_probe as cli

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._write_fixture(root)
            output = root / "out.yaml"
            argv = [
                "summarize_gameassembly_registration_layout_probe",
                "--input",
                str(fixture),
                "--output",
                str(output),
                "--source-id",
                "fixture-layout",
            ]
            with patch.object(sys, "argv", argv), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cli.main()

            data = yaml.safe_load(output.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_registration_layout_probe.v1")
        self.assertEqual(data["source_id"], "fixture-layout")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["source_id"], "fixture-layout")
        self.assertEqual(summary["codegen_modules_field_offset"], 120)
