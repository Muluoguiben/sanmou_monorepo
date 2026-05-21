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

from qa_agent.ingestion.client_registration_anchor_probe import (
    build_registration_anchor_report,
)


class RegistrationAnchorProbeTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "gameassembly_registration_anchor_probe_round180.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 180,
                    "slice": "gameassembly_registration_anchor_probe",
                    "input_artifacts": [
                        {
                            "file_name": "GameAssembly.dll",
                            "role": "module:GameAssembly.dll",
                            "size_bytes": 94127168,
                            "sha256": "a" * 64,
                        }
                    ],
                    "registration_anchor": {
                        "codegen_modules_pointer_ref_rva": "0x43327b0",
                        "codegen_modules_pointer_ref_section": ".rdata",
                        "codegen_modules_count_field_rva": "0x43327a8",
                        "declared_codegen_module_count": 98,
                        "codegen_modules_array_rva": "0x50a2840",
                        "field_owner_candidate_rva": "0x4332718",
                    },
                    "module_array_summary": {
                        "declared_or_scanned_module_count": 98,
                        "parsed_module_count": 98,
                        "nonzero_method_module_count": 96,
                        "zero_method_module_count": 2,
                        "assembly_csharp_index": 5,
                        "assembly_csharp_struct_rva": "0x44196a0",
                        "assembly_csharp_method_pointer_count": 30078,
                        "assembly_csharp_method_pointer_table_rva": "0x50b9840",
                        "assembly_csharp_firstpass_index": 4,
                        "assembly_csharp_firstpass_struct_rva": "0x4416490",
                        "assembly_csharp_firstpass_method_pointer_count": 354,
                        "sample_modules": [
                            {
                                "index": 5,
                                "module_name": "Assembly-CSharp.dll",
                                "method_pointer_count": 30078,
                                "method_pointer_table_rva": "0x50b9840",
                            }
                        ],
                    },
                    "code_ref_summary": {
                        "available": True,
                        "searched_target_count": 3,
                        "code_ref_count": 0,
                        "code_refs": [],
                    },
                    "counts": {
                        "codegen_modules_field_candidate_count": 1,
                        "declared_codegen_module_count": 98,
                        "parsed_codegen_module_count": 98,
                        "nonzero_method_module_count": 96,
                        "assembly_csharp_index": 5,
                        "assembly_csharp_method_pointer_count": 30078,
                        "registration_anchor_code_ref_count": 0,
                        "metadata_registration_candidate_count": 0,
                        "metadata_registration_callsite_count": 0,
                        "method_index_to_pointer_map_recovered": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "route_conclusion": {
                        "codegen_registration_anchor_found": True,
                        "full_codegen_module_array_recovered": True,
                        "assembly_csharp_module_index_found": True,
                        "codegen_registration_callsite_recovered": False,
                        "metadata_registration_candidate_recovered": False,
                        "method_index_to_pointer_map_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "CodeGenModules field found",
                        "strongest_negative_signal": "MetadataRegistration pairing missing",
                        "search_policy": "recover registration pairing",
                    },
                    "evidence_refs": [
                        "NSLG_REGISTRATION_ANCHOR:round180:codegen-modules-field"
                    ],
                    "next_static_targets": ["recover registration pairing"],
                    "limitations": ["registration-side evidence only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_registration_anchor_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_registration_anchor_report(
                input_path=input_path,
                source_id="fixture-registration-anchor",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_registration_anchor_probe.v1")
        self.assertEqual(report.source_id, "fixture-registration-anchor")
        self.assertEqual(report.counts["declared_codegen_module_count"], 98)
        self.assertEqual(report.module_array_summary["assembly_csharp_index"], 5)
        self.assertEqual(
            report.module_array_summary["assembly_csharp_method_pointer_table_rva"],
            "0x50b9840",
        )
        self.assertTrue(report.route_conclusion["codegen_registration_anchor_found"])
        self.assertFalse(report.route_conclusion["metadata_registration_candidate_recovered"])
        self.assertFalse(report.route_conclusion["init_lua_env_method_pointer_recovered"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_gameassembly_registration_anchor_probe import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "registration-anchor.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_gameassembly_registration_anchor_probe",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-registration-anchor",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_registration_anchor_probe.v1")
        self.assertEqual(data["source_id"], "fixture-registration-anchor")
        self.assertEqual(data["counts"]["parsed_codegen_module_count"], 98)
        self.assertEqual(summary["assembly_csharp_index"], 5)
        self.assertFalse(summary["init_lua_env_method_pointer_recovered"])


if __name__ == "__main__":
    unittest.main()
