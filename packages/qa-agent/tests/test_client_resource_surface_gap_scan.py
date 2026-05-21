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

from qa_agent.ingestion.client_resource_surface_gap_scan import (
    build_client_resource_surface_gap_scan_report,
)


class ClientResourceSurfaceGapScanTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 190,
                    "slice": "client_resource_surface_gap_scan",
                    "input": {
                        "game_root_label": "NSLG Game",
                        "game_root_exists": True,
                    },
                    "scan_policy": {
                        "mode": "offline_static_metadata_only",
                        "safe_package_roots": [
                            "com.bilibili.nslg_Data",
                            "LocalPersistentData/assets/bundles",
                        ],
                        "aggregate_only_roots": ["LocalPersistentData"],
                    },
                    "counts": {
                        "total_files_seen": 677,
                        "safe_file_count": 556,
                        "aggregate_only_file_count": 76,
                        "sensitive_or_runtime_file_count": 45,
                        "ns_bundle_count": 369,
                        "ns_total_bytes": 7197259176,
                        "safe_magic_sample_count": 240,
                    },
                    "root_groups": [
                        {
                            "root": "LocalPersistentData",
                            "classification": "safe_package_resource",
                            "file_count": 369,
                            "total_bytes": 7197259176,
                            "extension_counts": {".ns": 369},
                            "sample_rel_paths": [
                                "LocalPersistentData/assets/bundles/luascripts.ns"
                            ],
                        }
                    ],
                    "safe_magic_samples": [
                        {
                            "rel_path": r"C:\Users\Lan\Documents\New project\LocalPersistentData\assets\bundles\luascripts.ns",
                            "size": 33098121,
                            "suffix": ".ns",
                            "classification_reason": "resource_cache_bundle_whitelist",
                            "magic_hex": "556e6974794653000000000000000000",
                            "magic_ascii": "UnityFS.........................",
                            "evidence_ref": (
                                "NSLG_CLIENT_RESOURCE_SURFACE:round190:magic:luascripts"
                            ),
                        }
                    ],
                    "ns_bundle_groups": [
                        {
                            "group": "luascripts.ns",
                            "file_count": 1,
                            "total_bytes": 33098121,
                            "largest_file_bytes": 33098121,
                            "sample_files": [
                                {
                                    "rel_path": "LocalPersistentData/assets/bundles/luascripts.ns",
                                    "size": 33098121,
                                    "magic_ascii": "UnityFS",
                                    "magic_hex_prefix": "556e6974794653",
                                }
                            ],
                            "evidence_ref": (
                                "NSLG_CLIENT_RESOURCE_SURFACE:round190:ns-group:luascripts"
                            ),
                        },
                        {
                            "group": "mapres.ns",
                            "file_count": 1,
                            "total_bytes": 57180360,
                            "largest_file_bytes": 57180360,
                            "sample_files": [],
                            "evidence_ref": (
                                "NSLG_CLIENT_RESOURCE_SURFACE:round190:ns-group:mapres"
                            ),
                        },
                    ],
                    "route_conclusion": {
                        "resource_surface_gap_identified": True,
                        "resource_cache_bundle_root_found": True,
                        "luascripts_ns_found": True,
                        "map_resource_ns_found": True,
                        "db_or_log_content_read": False,
                        "account_or_protocol_data_included": False,
                        "decoded_game_knowledge_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "resource cache contains .ns bundles",
                        "strongest_negative_signal": "no bundle decode yet",
                        "search_policy": "prioritize .ns bundle index",
                    },
                    "evidence_refs": [
                        "NSLG_CLIENT_RESOURCE_SURFACE:round190:summary"
                    ],
                    "next_static_targets": ["build sanitized .ns bundle index"],
                    "limitations": ["resource cache bundles are inventoried but not decoded"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_resource_surface_as_non_publishable_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round190.json"
            self._write_input(input_path)
            report = build_client_resource_surface_gap_scan_report(
                input_path=input_path,
                source_id="client-resource-surface-gap-scan-round133",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.client_resource_surface_gap_scan.v1")
        self.assertEqual(report.counts["ns_bundle_count"], 369)
        self.assertTrue(report.route_conclusion["resource_surface_gap_identified"])
        self.assertTrue(report.route_conclusion["luascripts_ns_found"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.ns_bundle_groups[0].group, "luascripts.ns")
        self.assertFalse(report.safe_magic_samples[0].rel_path.startswith("C:"))
        self.assertIn(
            "LocalPersistentData",
            report.safe_magic_samples[0].rel_path,
        )

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_client_resource_surface_gap_scan import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round190.json"
            output_path = root / "resource_surface.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_client_resource_surface_gap_scan",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "client-resource-surface-gap-scan-round133",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.client_resource_surface_gap_scan.v1")
        self.assertEqual(data["source_id"], "client-resource-surface-gap-scan-round133")
        self.assertEqual(data["counts"]["ns_bundle_count"], 369)
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["ns_total_bytes"], 7197259176)
        self.assertTrue(summary["resource_surface_gap_identified"])


if __name__ == "__main__":
    unittest.main()
