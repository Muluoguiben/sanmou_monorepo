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

from qa_agent.ingestion.client_ns_bundle_format_index import (
    build_ns_bundle_format_index_report,
)


class ClientNsBundleFormatIndexTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 191,
                    "slice": "ns_bundle_format_index",
                    "input": {
                        "bundle_root_label": "LocalPersistentData/assets/bundles",
                        "bundle_root": r"D:\bilibili Game\NSLG\NSLG Game\LocalPersistentData\assets\bundles",
                    },
                    "scan_policy": {
                        "mode": "offline_static_format_index_only",
                        "payload_bytes_exported": False,
                    },
                    "counts": {
                        "bundle_count": 369,
                        "unityfs_parse_ok_count": 369,
                        "block_info_parse_ok_count": 369,
                        "first_block_decompress_ok_count": 369,
                        "serialized_header_parse_ok_count": 369,
                        "protected_serialized_metadata_count": 369,
                        "cab_only_bundle_count": 63,
                        "cab_plus_ress_bundle_count": 306,
                    },
                    "format_groups": [
                        {
                            "asset_group": "luascripts.ns",
                            "bundle_count": 1,
                            "total_bytes": 33098121,
                            "parse_ok_count": 1,
                            "protected_metadata_count": 1,
                            "directory_shapes": {"cab_only": 1},
                            "sample_rel_paths": ["luascripts.ns"],
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:group:luascripts",
                        }
                    ],
                    "cab_block2_groups": [
                        {
                            "metadata_block2_hex": "c5 30 54 e1 bf c4 02 33",
                            "bundle_count": 32,
                            "asset_group_counts": {"terrain": 30, "dynamicatlas.ns": 1},
                            "sample_rel_paths": ["terrain/demo/h0.ns"],
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:block2:terrain",
                        }
                    ],
                    "priority_records": [
                        {
                            "rel_path": "luascripts.ns",
                            "asset_group": "luascripts.ns",
                            "priority_rank": 1,
                            "size_bytes": 33098121,
                            "directory_shape": "cab_only",
                            "block_count": 257,
                            "directory_node_count": 1,
                            "serialized_version": 22,
                            "metadata_size": 196733,
                            "data_offset": 196784,
                            "metadata_block1_sha1": "b4df4fb245788c80afc355bd5eb5d40199562883",
                            "metadata_block2_sha1": "76d272cb449f52a60f6c2a15bb7b36b2cbd8bfb2",
                            "protected_metadata_likely": True,
                            "evidence_ref": "NSLG_NS_BUNDLE_FORMAT_INDEX:round191:bundle:luascripts",
                        }
                    ],
                    "route_conclusion": {
                        "ns_bundle_index_built": True,
                        "unityfs_envelope_parseable": True,
                        "block_info_index_parseable": True,
                        "first_block_decompression_supported": True,
                        "serialized_header_parseable": True,
                        "protected_serialized_metadata_present": True,
                        "all_indexed_bundles_look_protected": True,
                        "decoded_game_knowledge_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "parseable UnityFS envelopes",
                        "strongest_negative_signal": "CAB metadata remains protected",
                        "search_policy": "target protected metadata transform",
                    },
                    "evidence_refs": ["NSLG_NS_BUNDLE_FORMAT_INDEX:round191:summary"],
                    "next_static_targets": ["recover protected metadata transform"],
                    "limitations": ["no decoded gameplay knowledge"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_bundle_index_as_non_publishable_decoder_target(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round191.json"
            self._write_input(input_path)
            report = build_ns_bundle_format_index_report(
                input_path=input_path,
                source_id="ns-bundle-format-index-round136",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.ns_bundle_format_index.v1")
        self.assertEqual(report.counts["bundle_count"], 369)
        self.assertEqual(report.counts["protected_serialized_metadata_count"], 369)
        self.assertTrue(report.route_conclusion["all_indexed_bundles_look_protected"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.format_groups[0].asset_group, "luascripts.ns")
        self.assertTrue(report.priority_records[0].protected_metadata_likely)
        self.assertFalse(str(report.input["bundle_root"]).startswith("D:"))

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_ns_bundle_format_index import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round191.json"
            output_path = root / "ns_bundle_format_index.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_ns_bundle_format_index",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "ns-bundle-format-index-round136",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.ns_bundle_format_index.v1")
        self.assertEqual(data["source_id"], "ns-bundle-format-index-round136")
        self.assertEqual(data["counts"]["bundle_count"], 369)
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["protected_serialized_metadata_count"], 369)


if __name__ == "__main__":
    unittest.main()
