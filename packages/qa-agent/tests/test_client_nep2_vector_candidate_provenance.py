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

from qa_agent.ingestion.client_nep2_vector_candidate_provenance import (
    build_nep2_vector_candidate_provenance_report,
)


class Nep2VectorCandidateProvenanceTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 186,
                    "slice": "nep2_vector_candidate_provenance_static_trace",
                    "input_artifacts": [
                        {
                            "file_name": r"C:\local\global_metadata_loader_mutation_scan_round168.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "nep2_file": {
                        "file_name": r"D:\bilibili Game\NSLG\NSLG Game\NEP2.dll",
                        "size_bytes": 100,
                        "sha256": "b" * 64,
                        "pdata_function_count": 2,
                    },
                    "selection_policy": {
                        "provenance_seed_rvas": {
                            "0xd720": "round170_read_mapping_owner_GetFileSizeEx"
                        }
                    },
                    "counts": {
                        "target_count": 2,
                        "vector_candidate_count": 1,
                        "provenance_linked_target_count": 1,
                        "provenance_linked_vector_candidate_count": 0,
                        "keyword_ref_target_count": 0,
                    },
                    "targets": [
                        {
                            "target_rva": "0x120c0",
                            "function": {"begin": "0x120c0", "end": "0x123d8"},
                            "verdict": "vector_or_block_helper_without_payload_provenance",
                            "selection": {"source": "round168_top_candidate", "round168_score": 678},
                            "counts": {"vector_instruction": 54},
                            "imports": [],
                            "keyword_refs": [],
                            "direct_calls": [{"rva": "0x120e8", "target_rva": "0x35640"}],
                            "direct_caller_count": 11,
                            "direct_callee_count": 4,
                            "provenance_linked": False,
                            "provenance_paths": [],
                            "evidence_ref": (
                                "NSLG_NEP2_VECTOR_PROVENANCE:"
                                "nep2-vector-candidate-provenance-round186:target:0x120c0"
                            ),
                        },
                        {
                            "target_rva": "0xda90",
                            "function": {"begin": "0xda90", "end": "0xdb33"},
                            "verdict": "file_helper_without_payload_provenance",
                            "selection": {"source": "round168_top_candidate", "round168_score": 60},
                            "counts": {"file_import_call": 1},
                            "imports": [
                                {
                                    "rva": "0xdad1",
                                    "import": "KERNEL32.dll!CreateFileW",
                                    "import_name": "CreateFileW",
                                    "class": "file_or_other",
                                }
                            ],
                            "keyword_refs": [],
                            "direct_callers": [{"site": "0xd77c"}],
                            "direct_caller_count": 3,
                            "direct_callee_count": 0,
                            "provenance_linked": True,
                            "provenance_paths": [
                                {
                                    "seed_rva": "0xd720",
                                    "seed_label": "round170_read_mapping_owner_GetFileSizeEx",
                                    "depth": 1,
                                }
                            ],
                            "evidence_ref": (
                                "NSLG_NEP2_VECTOR_PROVENANCE:"
                                "nep2-vector-candidate-provenance-round186:target:0xda90"
                            ),
                        },
                    ],
                    "route_conclusion": {
                        "vector_candidate_provenance_link_found": False,
                        "read_mapping_to_vector_path_found": False,
                        "read_mapping_to_file_helper_path_found": True,
                        "metadata_or_luascripts_keyword_link_found": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_VECTOR_PROVENANCE:nep2-vector-candidate-provenance-round186:summary"
                    ],
                    "next_static_targets": ["recover payload-owner provenance"],
                    "limitations": ["static callgraph only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_vector_provenance_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round186.json"
            self._write_input(input_path)
            report = build_nep2_vector_candidate_provenance_report(
                input_path=input_path,
                source_id="nep2-vector-candidate-provenance-round121",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.nep2_vector_candidate_provenance.v1")
        self.assertEqual(report.input_artifacts[0].file_name, "global_metadata_loader_mutation_scan_round168.json")
        self.assertEqual(report.nep2_file["file_name"], "NEP2.dll")
        self.assertEqual(report.counts["target_count"], 2)
        self.assertEqual(report.counts["provenance_linked_vector_candidate_count"], 0)
        self.assertFalse(report.route_conclusion["read_mapping_to_vector_path_found"])
        self.assertTrue(report.route_conclusion["read_mapping_to_file_helper_path_found"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.targets[0]["target_rva"], "0x120c0")

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_nep2_vector_candidate_provenance import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round186.json"
            output_path = root / "vector.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_vector_candidate_provenance",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "nep2-vector-candidate-provenance-round121",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.nep2_vector_candidate_provenance.v1")
        self.assertEqual(data["source_id"], "nep2-vector-candidate-provenance-round121")
        self.assertEqual(data["counts"]["vector_candidate_count"], 1)
        self.assertFalse(data["route_conclusion"]["read_mapping_to_vector_path_found"])
        self.assertEqual(summary["provenance_linked_vector_candidate_count"], 0)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
