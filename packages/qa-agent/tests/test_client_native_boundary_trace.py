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

from qa_agent.ingestion.client_native_boundary_trace import (
    build_native_loadbuffer_boundary_trace_report,
)


class NativeLoadbufferBoundaryTraceTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 163,
                    "slice": "native_loadbuffer_boundary_trace",
                    "summary": [
                        "Scanned 2 native modules.",
                        "No static bridge was proven.",
                    ],
                    "counts": {
                        "module_count": 2,
                        "loadbuffer_export_signal_count": 1,
                        "boundary_import_call_count": 3,
                        "candidate_function_signal_count": 0,
                    },
                    "module_records": [
                        {
                            "module": "GameAssembly.dll",
                            "binary_sha256": "a" * 64,
                            "size_bytes": 100,
                            "import_count": 2,
                            "target_import_count": 1,
                            "export_count": 1,
                            "target_export_count": 0,
                            "keyword_hit_count": 3,
                            "keyword_data_ref_count": 0,
                            "import_call_count": 1,
                            "inspected_function_count": 1,
                            "boundary_signal_count": 0,
                            "target_imports": [
                                {"iat_rva": "0x100", "name": "KERNEL32.dll!LoadLibraryW"}
                            ],
                            "target_exports": [],
                            "boundary_signals": [],
                        },
                        {
                            "module": "xlua.dll",
                            "binary_sha256": "b" * 64,
                            "size_bytes": 200,
                            "import_count": 3,
                            "target_import_count": 1,
                            "export_count": 10,
                            "target_export_count": 1,
                            "keyword_hit_count": 1,
                            "keyword_data_ref_count": 1,
                            "import_call_count": 2,
                            "inspected_function_count": 2,
                            "boundary_signal_count": 1,
                            "target_imports": [],
                            "target_exports": [{"name": "xluaL_loadbuffer", "rva": "0x200"}],
                            "boundary_signals": [{"kind": "loadbuffer_export"}],
                        },
                    ],
                    "route_conclusion": {
                        "native_loadbuffer_export_present": True,
                        "gameassembly_static_xlua_import_present": False,
                        "gameassembly_to_xlua_static_bridge_proven": False,
                        "textasset_to_loadbuffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "xLua loadbuffer exports are present",
                        "strongest_negative_signal": "TextAsset owner is not proven",
                        "search_policy": "continue with provenance-backed tracing",
                    },
                    "next_static_targets": ["trace RuntimeInitializeOnLoad metadata"],
                    "limitations": ["static evidence only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_sanitizes_modules_and_keeps_decoder_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round163.json"
            self._write_input(input_path)
            report = build_native_loadbuffer_boundary_trace_report(
                input_path=input_path,
                source_id="native-boundary-round52",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.native_loadbuffer_boundary_trace.v1")
        self.assertEqual(report.source_id, "native-boundary-round52")
        self.assertEqual(report.counts["module_count"], 2)
        self.assertFalse(report.route_conclusion["textasset_to_loadbuffer_owner_proven"])
        self.assertEqual(len(report.module_records), 2)
        self.assertEqual(report.module_records[0].module, "GameAssembly.dll")
        self.assertFalse(report.module_records[0].route_flags["has_xlua_or_loadbuffer_import"])
        self.assertTrue(report.module_records[1].route_flags["has_loadbuffer_export"])
        self.assertTrue(all(ref.startswith("NSLG_NATIVE_BOUNDARY:") for ref in report.evidence_refs))

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_native_loadbuffer_boundary import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round163.json"
            output_path = root / "native.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_native_loadbuffer_boundary",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "native-boundary-round52",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.native_loadbuffer_boundary_trace.v1")
        self.assertEqual(data["source_id"], "native-boundary-round52")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["module_count"], 2)
        self.assertFalse(summary["gameassembly_static_xlua_import_present"])


if __name__ == "__main__":
    unittest.main()
