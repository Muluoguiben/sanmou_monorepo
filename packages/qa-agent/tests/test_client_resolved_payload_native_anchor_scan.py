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

from qa_agent.ingestion.client_resolved_payload_native_anchor_scan import (
    build_resolved_payload_native_anchor_scan_report,
)


class ResolvedPayloadNativeAnchorScanTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "resolved_payload_native_anchor_scan_round176.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 176,
                    "slice": "resolved_payload_native_anchor_scan",
                    "input_artifacts": [
                        {
                            "file_name": "serialized_textasset_path_resolution_round175.json",
                            "role": "Round175 resolved path_id/object_offset evidence",
                            "size_bytes": 100,
                            "sha256": "a" * 64,
                        }
                    ],
                    "anchor_summary": {
                        "anchor_count": 368,
                        "strong_anchor_count": 272,
                        "weak_anchor_count": 96,
                    },
                    "cab_control": {
                        "anchor_kind_with_hits_count": 8,
                        "anchor_kind_hit_counts": {"payload_first16": 16},
                        "strong_anchor_hit_count_capped": 255,
                        "weak_anchor_hit_count_capped": 150,
                        "sample_hits": [
                            {
                                "kind": "payload_first16",
                                "strength": "strong",
                                "hit_count_capped": 1,
                                "sample_offsets_hex": ["0x88"],
                            }
                        ],
                    },
                    "module_records": [
                        {
                            "module": "GameAssembly.dll",
                            "missing": False,
                            "size_bytes": 1000,
                            "anchor_hit_count_capped": 2,
                            "strong_anchor_hit_count_capped": 0,
                            "weak_anchor_hit_count_capped": 2,
                            "cooccurrence_count": 0,
                            "strong_cooccurrence_count": 0,
                            "anchor_kind_hit_counts": {"script_len_le32": 2},
                            "section_hit_counts": {".text": 2},
                            "hit_samples": [
                                {
                                    "file_offset_hex": "0x10",
                                    "rva": "0x1000",
                                    "section": ".text",
                                    "kind": "script_len_le32",
                                    "strength": "weak",
                                }
                            ],
                        }
                    ],
                    "counts": {
                        "anchor_count": 368,
                        "strong_anchor_count": 272,
                        "weak_anchor_count": 96,
                        "module_count": 4,
                        "present_module_count": 4,
                        "missing_module_count": 0,
                        "cab_control_strong_anchor_hit_count_capped": 255,
                        "cab_control_weak_anchor_hit_count_capped": 150,
                        "native_strong_anchor_hit_count_capped": 0,
                        "native_weak_anchor_hit_count_capped": 990,
                        "native_anchor_cooccurrence_count": 0,
                        "native_strong_anchor_cooccurrence_count": 0,
                    },
                    "route_conclusion": {
                        "resolved_path_id_object_offset_anchor_available": True,
                        "cab_control_anchors_verified": True,
                        "native_exact_strong_anchor_found": False,
                        "native_strong_anchor_cooccurrence_found": False,
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "CAB anchors verified",
                        "strongest_negative_signal": "no native strong anchors",
                        "search_policy": "continue boundary-focused owner analysis",
                    },
                    "evidence_refs": [
                        "NSLG_RESOLVED_PAYLOAD_NATIVE_ANCHOR:round176:module:GameAssembly.dll"
                    ],
                    "next_static_targets": ["boundary-focused disassembly"],
                    "limitations": ["static native anchor scan only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_native_anchor_scan_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_resolved_payload_native_anchor_scan_report(
                input_path=input_path,
                source_id="fixture-native-anchor-scan",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(
            report.schema_version,
            "nslg.resolved_payload_native_anchor_scan.v1",
        )
        self.assertEqual(report.source_id, "fixture-native-anchor-scan")
        self.assertEqual(report.counts["native_strong_anchor_hit_count_capped"], 0)
        self.assertFalse(report.route_conclusion["native_exact_strong_anchor_found"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.module_records[0].module, "GameAssembly.dll")

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_resolved_payload_native_anchor_scan import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "native-anchor.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_resolved_payload_native_anchor_scan",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-native-anchor-scan",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.resolved_payload_native_anchor_scan.v1")
        self.assertEqual(data["source_id"], "fixture-native-anchor-scan")
        self.assertEqual(data["counts"]["native_strong_anchor_hit_count_capped"], 0)
        self.assertFalse(summary["native_exact_strong_anchor_found"])
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
