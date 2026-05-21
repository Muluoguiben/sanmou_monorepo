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

from qa_agent.ingestion.client_nep2_metadata_loader_deep_slice import (
    build_nep2_metadata_loader_deep_slice_report,
)


class Nep2MetadataLoaderDeepSliceTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 169,
                    "slice": "nep2_global_metadata_loader_candidate_deep_slice",
                    "input_artifacts": [
                        {
                            "file_name": r"C:\local\global_metadata_loader_mutation_scan_round168.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "target_rvas": ["0xd410", "0xd870"],
                    "counts": {
                        "target_count": 2,
                        "closed_target_count": 2,
                        "read_or_mapping_target_count": 0,
                        "metadata_ref_target_count": 0,
                        "directory_walker_target_count": 1,
                        "file_status_helper_target_count": 1,
                    },
                    "verdict_counts": {
                        "closed_directory_size_walker_not_metadata_loader": 1,
                        "closed_file_status_helper_not_metadata_loader": 1,
                    },
                    "targets": [
                        {
                            "target_rva": "0xd410",
                            "function": {"begin": "0xd410", "end": "0xd71e"},
                            "verdict": "closed_directory_size_walker_not_metadata_loader",
                            "counts": {"import_class:directory_enum": 3},
                            "imports_seen": ["FindClose", "FindFirstFileW", "FindNextFileW"],
                            "has_read_or_mapping_import": False,
                            "has_metadata_string_or_constant_ref": False,
                            "directory_walker_signature": True,
                            "file_status_helper_signature": False,
                            "string_refs": [
                                {
                                    "from_rva": "0xd5a8",
                                    "text": "lea rcx, [rip]",
                                    "target": {"rva": "0x77d7cc", "utf16le": "."},
                                }
                            ],
                            "evidence_ref": (
                                "NSLG_NEP2_METADATA_LOADER_DEEP_SLICE:"
                                "nep2-global-metadata-loader-deep-slice-round169:0xd410"
                            ),
                        }
                    ],
                    "route_conclusion": {
                        "targets_closed_as_metadata_loader_candidates": True,
                        "global_metadata_loader_proven": False,
                        "file_buffer_owner_proven": False,
                        "metadata_wrapper_or_string_provenance_found": False,
                        "read_or_mapping_proven": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "filesystem helper signatures",
                        "strongest_negative_signal": "no ReadFile or metadata refs",
                        "search_policy": "pivot to read owners",
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_METADATA_LOADER_DEEP_SLICE:round70:summary"
                    ],
                    "next_static_targets": ["prioritize actual ReadFile owners"],
                    "limitations": ["static deep-slice only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_closes_nep2_helpers_without_publish_promotion(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round169.json"
            self._write_input(input_path)
            report = build_nep2_metadata_loader_deep_slice_report(
                input_path=input_path,
                source_id="nep2-global-metadata-loader-deep-slice-round70",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.nep2_global_metadata_loader_deep_slice.v1")
        self.assertEqual(report.source_id, "nep2-global-metadata-loader-deep-slice-round70")
        self.assertEqual(report.counts["target_count"], 2)
        self.assertEqual(report.counts["closed_target_count"], 2)
        self.assertEqual(report.counts["read_or_mapping_target_count"], 0)
        self.assertFalse(report.route_conclusion["global_metadata_loader_proven"])
        self.assertTrue(report.route_conclusion["targets_closed_as_metadata_loader_candidates"])
        self.assertEqual(report.input_artifacts[0].file_name, "global_metadata_loader_mutation_scan_round168.json")
        self.assertEqual(report.targets[0]["verdict"], "closed_directory_size_walker_not_metadata_loader")

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_nep2_metadata_loader_deep_slice import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round169.json"
            output_path = root / "deep-slice.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_metadata_loader_deep_slice",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "nep2-global-metadata-loader-deep-slice-round70",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.nep2_global_metadata_loader_deep_slice.v1")
        self.assertEqual(data["source_id"], "nep2-global-metadata-loader-deep-slice-round70")
        self.assertTrue(data["route_conclusion"]["targets_closed_as_metadata_loader_candidates"])
        self.assertEqual(summary["closed_target_count"], 2)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
