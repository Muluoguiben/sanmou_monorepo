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

from qa_agent.ingestion.client_metadata_registration_candidate_taxonomy import (
    build_metadata_registration_candidate_taxonomy_report,
)


class ClientMetadataRegistrationCandidateTaxonomyTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        path = root / "gameassembly_metadata_registration_candidate_taxonomy_round185.json"
        path.write_text(
            json.dumps(
                {
                    "round": 185,
                    "slice": "gameassembly_metadata_registration_candidate_taxonomy",
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
                        "section_count": 6,
                        "pdata_function_count": 290472,
                    },
                    "scan_policy": {
                        "section": ".rdata",
                        "window_span": "0xa0",
                        "window_step": "0x10",
                        "minimum_count_pointer_pairs": 6,
                        "medium_count_threshold": 64,
                        "high_count_threshold": 1000,
                        "max_count_value": 1000000,
                        "sample_per_field": 4,
                    },
                    "round181_top_candidate_summary": {
                        "candidate_count": 58746,
                        "top_candidate_count": 12,
                        "top_candidate_max_count": 15,
                        "top_candidate_all_counts_below_medium_threshold": True,
                        "paired_by_callsite": False,
                    },
                    "round182_raw_ref_summary": {
                        "target_count": 12,
                        "raw_ref_count": 25,
                        "section_counts": {".rdata": 12, ".data": 13},
                        "target_role_counts": {"metadata_registration_like_candidate": 25},
                        "target_ref_counts": {"metadata_candidate_rank_1": 2},
                    },
                    "metadata_ref_family_summary": {
                        "family_cluster_count": 17,
                        "section_counts": {".rdata": 4, ".data": 13},
                        "top_clusters": [
                            {
                                "section": ".rdata",
                                "start_rva": "0x45464a8",
                                "end_rva": "0x45464d8",
                                "ref_count": 7,
                                "unique_target_count": 7,
                                "target_labels": ["metadata_candidate_rank_1"],
                            }
                        ],
                    },
                    "shifted_window_summary": {
                        "exact_ref_candidate_count": 12,
                        "overlap_edge_count": 11,
                        "cluster_count": 6,
                        "clusters": [
                            {
                                "member_count": 7,
                                "candidate_rvas": ["0x4589370", "0x4589430"],
                                "rva_min": "0x4589370",
                                "rva_max": "0x4589430",
                                "shared_pointer_rva_count": 0,
                                "max_count": 11,
                            }
                        ],
                    },
                    "exact_ref_candidate_summary": {
                        "candidate_count": 12,
                        "raw_ref_total": 25,
                        "max_count": 15,
                        "non_tiny_candidate_count": 0,
                        "all_exact_ref_candidates_are_tiny_count": True,
                    },
                    "high_count_candidate_summary": {
                        "candidate_count": 182,
                        "referenced_candidate_count": 0,
                        "strong_high_count_candidate_count": 169,
                        "low_sample_validity_candidate_count": 176,
                        "top_max_count": 197543,
                    },
                    "exact_ref_candidates": [
                        {
                            "candidate_rva": "0x4589490",
                            "pair_count": 10,
                            "tiny_count_pair_count": 10,
                            "medium_count_pair_count": 0,
                            "high_count_pair_count": 0,
                            "max_count": 12,
                            "sum_count": 42,
                            "raw_ref_count": 4,
                            "pointer_section_counts": {".data": 10},
                            "sample_target_section_counts": {".data": 27},
                            "valid_sample_pointer_count": 27,
                            "plausibility": "exact_ref_tiny_count_family",
                            "raw_refs": [{"ref_rva": "0x45464c0"}],
                            "field_counts": [4, 2, 11],
                            "pointer_rvas": ["0x51ba7c0"],
                        }
                    ],
                    "high_count_candidates": [
                        {
                            "candidate_rva": "0x4e3ced0",
                            "pair_count": 10,
                            "tiny_count_pair_count": 0,
                            "medium_count_pair_count": 0,
                            "high_count_pair_count": 10,
                            "max_count": 31770,
                            "sum_count": 202844,
                            "raw_ref_count": 0,
                            "pointer_section_counts": {".rdata": 10},
                            "sample_target_section_counts": {".data": 3},
                            "valid_sample_pointer_count": 3,
                            "plausibility": "high_count_unowned_low_sample_validity",
                            "field_counts": [15361, 15370],
                            "pointer_rvas": ["0x4e40000"],
                        }
                    ],
                    "counts": {
                        "metadata_candidate_window_count": 58879,
                        "exact_ref_candidate_count": 12,
                        "exact_ref_non_tiny_candidate_count": 0,
                        "exact_ref_max_count": 15,
                        "high_count_candidate_count": 182,
                        "strong_high_count_candidate_count": 169,
                        "referenced_high_count_candidate_count": 0,
                        "shifted_window_cluster_count": 6,
                        "metadata_ref_family_cluster_count": 17,
                        "metadata_registration_owner_recovered": 0,
                        "protected_metadata_method_ownership_recovered": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "route_conclusion": {
                        "metadata_candidate_taxonomy_completed": True,
                        "exact_ref_metadata_candidates_are_tiny_count_family": True,
                        "high_count_metadata_like_candidates_found": True,
                        "high_count_candidates_have_exact_refs": False,
                        "metadata_registration_owner_recovered": False,
                        "metadata_registration_paired_by_callsite": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": ["NSLG_METADATA_TAXONOMY:round185:candidate-window-rescan"],
                    "next_static_targets": ["recover protected metadata ownership"],
                    "limitations": ["static taxonomy only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_build_report_sanitizes_candidate_taxonomy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._write_fixture(Path(tmp))
            report = build_metadata_registration_candidate_taxonomy_report(
                input_path=fixture,
                source_id="gameassembly-metadata-registration-candidate-taxonomy-round118",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(
            report.schema_version,
            "nslg.gameassembly_metadata_registration_candidate_taxonomy.v1",
        )
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertEqual(report.counts["metadata_candidate_window_count"], 58879)
        self.assertEqual(report.counts["exact_ref_non_tiny_candidate_count"], 0)
        self.assertEqual(report.counts["referenced_high_count_candidate_count"], 0)
        self.assertTrue(
            report.route_conclusion["exact_ref_metadata_candidates_are_tiny_count_family"]
        )
        self.assertFalse(report.route_conclusion["metadata_registration_owner_recovered"])
        self.assertEqual(report.exact_ref_candidates[0]["plausibility"], "exact_ref_tiny_count_family")
        self.assertEqual(report.high_count_candidates[0]["high_count_pair_count"], 10)

    def test_cli_writes_yaml(self) -> None:
        from qa_agent.app import summarize_gameassembly_metadata_registration_candidate_taxonomy as cli

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._write_fixture(root)
            output = root / "out.yaml"
            argv = [
                "summarize_gameassembly_metadata_registration_candidate_taxonomy",
                "--input",
                str(fixture),
                "--output",
                str(output),
                "--source-id",
                "gameassembly-metadata-registration-candidate-taxonomy-round118",
            ]
            stdout = io.StringIO()
            with patch.object(sys, "argv", argv):
                with patch("sys.stdout", stdout):
                    cli.main()
            data = yaml.safe_load(output.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(
            data["source_id"],
            "gameassembly-metadata-registration-candidate-taxonomy-round118",
        )
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["exact_ref_candidate_count"], 12)
        self.assertEqual(summary["referenced_high_count_candidate_count"], 0)


if __name__ == "__main__":
    unittest.main()
