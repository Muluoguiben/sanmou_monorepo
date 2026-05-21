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

from qa_agent.ingestion.client_codegen_module_probe import build_codegen_module_probe_report


class CodeGenModuleProbeTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "gameassembly_codegen_module_probe_round179.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 179,
                    "slice": "gameassembly_codegen_module_probe",
                    "input_artifacts": [
                        {
                            "file_name": "GameAssembly.dll",
                            "role": "module:GameAssembly.dll",
                            "size_bytes": 94127168,
                            "sha256": "a" * 64,
                        }
                    ],
                    "gameassembly_summary": {
                        "file_name": "GameAssembly.dll",
                        "size_bytes": 94127168,
                        "sha256": "a" * 64,
                        "image_base_hex": "0x180000000",
                        "section_count": 6,
                        "pdata_function_count": 290472,
                        "sections": [{"name": "il2cpp", "virtual_address_hex": "0x630000"}],
                    },
                    "codegen_module_summary": {
                        "candidate_count": 95,
                        "contiguous_run_count": 4,
                        "largest_contiguous_run_count": 49,
                        "assembly_csharp_module_count": 2,
                    },
                    "assembly_csharp_modules": [
                        {
                            "module_name": "Assembly-CSharp.dll",
                            "struct_rva": "0x44196a0",
                            "ref_rva": "0x50a2868",
                            "method_pointer_count": 30078,
                            "method_pointer_table_rva": "0x50b9840",
                            "method_pointer_table_section": ".data",
                            "method_pointer_table_stats": {
                                "scanned_count": 30078,
                                "text_pointer_count": 29351,
                                "null_pointer_count": 727,
                                "other_pointer_count": 0,
                                "sample_size": 64,
                                "sample_text_pointer_count": 51,
                                "sample_null_pointer_count": 13,
                                "sample_other_pointer_count": 0,
                                "sample_entries": [
                                    {
                                        "index": 13,
                                        "pointer_rva": "0x641b00",
                                        "section": "il2cpp",
                                        "is_null": False,
                                    }
                                ],
                            },
                        }
                    ],
                    "codegen_module_runs": [
                        {
                            "start_ref_rva": "0x50a2840",
                            "end_ref_rva": "0x50a29c0",
                            "module_count": 49,
                            "first_module": "AVProVideo.Extensions.Timeline.dll",
                            "last_module": "UnityEngine.AudioModule.dll",
                            "contains_assembly_csharp": True,
                            "contains_assembly_csharp_firstpass": True,
                            "sample_modules": ["Assembly-CSharp.dll"],
                        }
                    ],
                    "counts": {
                        "codegen_module_candidate_count": 95,
                        "codegen_module_run_count": 4,
                        "largest_codegen_module_run_count": 49,
                        "assembly_csharp_module_count": 2,
                        "assembly_csharp_method_pointer_count": 30078,
                        "assembly_csharp_method_pointer_text_count": 29351,
                        "assembly_csharp_method_pointer_null_count": 727,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "route_conclusion": {
                        "assembly_csharp_codegen_module_found": True,
                        "assembly_csharp_method_pointer_table_found": True,
                        "codegen_module_array_found": True,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "CodeGenModule records found",
                        "strongest_negative_signal": "metadata names are protected",
                        "search_policy": "recover metadata registration ownership",
                    },
                    "evidence_refs": [
                        "NSLG_CODEGEN_MODULE:round179:module:Assembly-CSharp.dll"
                    ],
                    "next_static_targets": ["recover metadata registration ownership"],
                    "limitations": ["registration-side anchor only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_codegen_probe_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_codegen_module_probe_report(
                input_path=input_path,
                source_id="fixture-codegen-module-probe",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_codegen_module_probe.v1")
        self.assertEqual(report.source_id, "fixture-codegen-module-probe")
        self.assertEqual(report.counts["assembly_csharp_method_pointer_count"], 30078)
        self.assertEqual(report.assembly_csharp_modules[0].method_pointer_table_rva, "0x50b9840")
        self.assertEqual(
            report.assembly_csharp_modules[0].method_pointer_table_stats.text_pointer_count,
            29351,
        )
        self.assertFalse(report.route_conclusion["init_lua_env_method_pointer_recovered"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_gameassembly_codegen_module_probe import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "codegen-module-probe.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_gameassembly_codegen_module_probe",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-codegen-module-probe",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_codegen_module_probe.v1")
        self.assertEqual(data["source_id"], "fixture-codegen-module-probe")
        self.assertEqual(data["counts"]["codegen_module_candidate_count"], 95)
        self.assertEqual(summary["assembly_csharp_method_pointer_count"], 30078)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
