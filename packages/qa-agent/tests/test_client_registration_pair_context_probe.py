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

from qa_agent.ingestion.client_registration_pair_context_probe import (
    build_registration_pair_context_report,
)


class ClientRegistrationPairContextProbeTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        path = root / "gameassembly_registration_pair_context_probe_round182.json"
        path.write_text(
            json.dumps(
                {
                    "round": 182,
                    "slice": "gameassembly_registration_pair_context_probe",
                    "input_artifacts": [
                        {
                            "role": "module:GameAssembly.dll",
                            "file_name": r"C:\NSLG\GameAssembly.dll",
                            "size_bytes": 94127168,
                            "sha256": "a" * 64,
                        }
                    ],
                    "round181_layout_anchor": {
                        "primary_code_registration_start_rva": 70461232,
                        "codegen_modules_field_offset": 120,
                        "metadata_registration_candidate_count": 58746,
                    },
                    "registration_targets": [
                        {
                            "label": "code_registration_start",
                            "rva": "0x4332730",
                            "role": "direct_code_registration_start",
                        }
                    ],
                    "metadata_targets": [
                        {
                            "label": "metadata_candidate_rank_1",
                            "rva": "0x45893d0",
                            "role": "metadata_registration_like_candidate",
                            "rank": 1,
                            "score": 121,
                            "count_pointer_pair_count": 9,
                        }
                    ],
                    "raw_registration_ref_summary": {
                        "target_count": 10,
                        "raw_ref_count": 7,
                        "section_counts": {".rdata": 7},
                        "target_role_counts": {"code_registration_field_target": 7},
                        "target_ref_counts": {"codegen_modules_array": 1},
                        "refs": [
                            {
                                "target_label": "codegen_modules_array",
                                "target_role": "code_registration_field_target",
                                "target_rva": "0x50a2840",
                                "ref_rva": "0x43327b0",
                                "ref_section": ".rdata",
                            }
                        ],
                    },
                    "raw_metadata_ref_summary": {
                        "target_count": 12,
                        "raw_ref_count": 25,
                        "section_counts": {".data": 13, ".rdata": 12},
                        "target_role_counts": {"metadata_registration_like_candidate": 25},
                        "target_ref_counts": {"metadata_candidate_rank_1": 2},
                        "refs": [
                            {
                                "target_label": "metadata_candidate_rank_1",
                                "target_role": "metadata_registration_like_candidate",
                                "target_rva": "0x45893d0",
                                "ref_rva": "0x45464b0",
                                "ref_section": ".rdata",
                            }
                        ],
                    },
                    "code_ref_summary": {
                        "searched_target_count": 22,
                        "code_ref_count": 0,
                        "registration_code_ref_count": 0,
                        "metadata_candidate_code_ref_count": 0,
                        "refs": [],
                    },
                    "pair_neighborhood_scan": {
                        "window_size_bytes": 512,
                        "paired_neighborhood_count": 0,
                        "neighborhoods": [],
                    },
                    "call_argument_window_scan": {
                        "available": True,
                        "candidate_window_count": 0,
                        "windows": [],
                    },
                    "metadata_ref_families": {
                        "family_cluster_count": 1,
                        "clusters": [
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
                    "counts": {
                        "registration_target_count": 10,
                        "metadata_target_count": 12,
                        "raw_registration_ref_count": 7,
                        "raw_code_registration_start_ref_count": 0,
                        "raw_metadata_candidate_ref_count": 25,
                        "registration_code_ref_count": 0,
                        "metadata_candidate_code_ref_count": 0,
                        "paired_neighborhood_count": 0,
                        "call_argument_pair_window_count": 0,
                        "metadata_ref_family_cluster_count": 1,
                        "registration_pair_recovered": 0,
                        "metadata_registration_paired_by_callsite": 0,
                        "init_lua_env_method_pointer_recovered": 0,
                    },
                    "route_conclusion": {
                        "registration_pair_recovered": False,
                        "metadata_registration_paired_by_callsite": False,
                        "metadata_candidate_family_refs_found": True,
                        "direct_code_registration_start_ref_found": False,
                        "call_argument_pair_window_found": False,
                        "pair_neighborhood_found": False,
                        "method_index_to_pointer_map_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "metadata candidate family refs",
                        "strongest_negative_signal": "no pair context",
                        "search_policy": "pivot away from direct pair xrefs",
                    },
                    "evidence_refs": [
                        "NSLG_REGISTRATION_PAIR_CONTEXT:round182:pair-neighborhood-scan"
                    ],
                    "next_static_targets": ["recover metadata ownership"],
                    "limitations": ["static route evidence only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_build_registration_pair_context_report_sanitizes_and_preserves_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._write_fixture(Path(tmp))
            report = build_registration_pair_context_report(
                input_path=fixture,
                source_id="gameassembly-registration-pair-context-probe-round109",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_registration_pair_context_probe.v1")
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertEqual(report.counts["raw_metadata_candidate_ref_count"], 25)
        self.assertEqual(report.counts["paired_neighborhood_count"], 0)
        self.assertFalse(report.route_conclusion["registration_pair_recovered"])
        self.assertTrue(report.route_conclusion["metadata_candidate_family_refs_found"])
        self.assertEqual(report.metadata_ref_families["clusters"][0]["start_rva"], "0x45464a8")

    def test_cli_writes_yaml(self) -> None:
        from qa_agent.app import summarize_gameassembly_registration_pair_context_probe as cli

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._write_fixture(root)
            output = root / "out.yaml"
            argv = [
                "summarize_gameassembly_registration_pair_context_probe",
                "--input",
                str(fixture),
                "--output",
                str(output),
                "--source-id",
                "fixture-pair-context",
            ]
            with patch.object(sys, "argv", argv), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cli.main()

            data = yaml.safe_load(output.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_registration_pair_context_probe.v1")
        self.assertEqual(data["source_id"], "fixture-pair-context")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["raw_metadata_candidate_ref_count"], 25)
        self.assertFalse(summary["registration_pair_recovered"])


if __name__ == "__main__":
    unittest.main()
