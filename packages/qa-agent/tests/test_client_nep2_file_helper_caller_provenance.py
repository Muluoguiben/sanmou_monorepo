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

from qa_agent.ingestion.client_nep2_file_helper_caller_provenance import (
    build_nep2_file_helper_caller_provenance_report,
)


class Nep2FileHelperCallerProvenanceTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 187,
                    "slice": "nep2_file_helper_caller_provenance_static_trace",
                    "input_artifacts": [
                        {
                            "file_name": r"C:\local\nep2_vector_candidate_provenance_round186.json",
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
                        "helper_seed_rvas": {
                            "0xda90": "round186_file_helper_reached_from_read_owner"
                        },
                        "caller_depth": 3,
                        "callee_depth": 2,
                    },
                    "counts": {
                        "target_count": 3,
                        "helper_seed_target_count": 1,
                        "caller_path_to_helper_count": 1,
                        "payload_keyword_ref_function_count": 0,
                        "createfile_import_function_count": 1,
                    },
                    "targets": [
                        {
                            "target_rva": "0xda90",
                            "function": {"begin": "0xda90", "end": "0xdbad"},
                            "verdict": "createfile_helper_no_payload_path_refs",
                            "round186_verdict": "file_helper_without_payload_provenance",
                            "helper_seed": "round186_file_helper_reached_from_read_owner",
                            "counts": {"file_import_call": 1},
                            "imports": [
                                {
                                    "rva": "0xdad1",
                                    "import": "KERNEL32.dll!CreateFileW",
                                    "import_name": "CreateFileW",
                                    "class": "file_or_other",
                                }
                            ],
                            "payload_keyword_refs": [],
                            "direct_caller_count": 3,
                            "direct_callee_count": 8,
                            "paths_to_helper_seed": [],
                            "paths_from_helper_seed": [],
                            "evidence_ref": (
                                "NSLG_NEP2_FILE_HELPER_CALLER:"
                                "nep2-file-helper-caller-provenance-round187:target:0xda90"
                            ),
                        },
                        {
                            "target_rva": "0xd720",
                            "function": {"begin": "0xd720", "end": "0xd7c0"},
                            "verdict": "read_mapping_helper_no_payload_path_refs",
                            "helper_seed": "",
                            "counts": {"read_mapping_import_call": 1},
                            "imports": [],
                            "payload_keyword_refs": [],
                            "paths_to_helper_seed": [
                                {
                                    "seed_rva": "0xda90",
                                    "seed_label": "round186_file_helper_reached_from_read_owner",
                                    "depth": 1,
                                    "path": [{"site": "0xd77c"}],
                                }
                            ],
                            "paths_from_helper_seed": [],
                            "evidence_ref": (
                                "NSLG_NEP2_FILE_HELPER_CALLER:"
                                "nep2-file-helper-caller-provenance-round187:target:0xd720"
                            ),
                        },
                    ],
                    "route_conclusion": {
                        "file_helper_payload_owner_proven": False,
                        "metadata_or_luascripts_keyword_link_found": False,
                        "read_mapping_to_file_helper_path_found": True,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "file helper context has no payload refs",
                        "strongest_negative_signal": "no payload path terms",
                        "search_policy": "treat 0xda90 as generic helper",
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_FILE_HELPER_CALLER:nep2-file-helper-caller-provenance-round187:summary"
                    ],
                    "next_static_targets": ["pivot to GameAssembly metadata route"],
                    "limitations": ["static callgraph only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_file_helper_route_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round187.json"
            self._write_input(input_path)
            report = build_nep2_file_helper_caller_provenance_report(
                input_path=input_path,
                source_id="nep2-file-helper-caller-provenance-round124",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.nep2_file_helper_caller_provenance.v1")
        self.assertEqual(report.input_artifacts[0].file_name, "nep2_vector_candidate_provenance_round186.json")
        self.assertEqual(report.nep2_file["file_name"], "NEP2.dll")
        self.assertEqual(report.counts["target_count"], 3)
        self.assertFalse(report.route_conclusion["file_helper_payload_owner_proven"])
        self.assertTrue(report.route_conclusion["read_mapping_to_file_helper_path_found"])
        self.assertEqual(report.targets[0]["imports"][0]["import_name"], "CreateFileW")
        self.assertEqual(report.targets[1]["paths_to_helper_seed"][0]["path_length"], 1)

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_nep2_file_helper_caller_provenance import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round187.json"
            output_path = root / "file_helper.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_file_helper_caller_provenance",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "nep2-file-helper-caller-provenance-round124",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.nep2_file_helper_caller_provenance.v1")
        self.assertEqual(data["source_id"], "nep2-file-helper-caller-provenance-round124")
        self.assertFalse(data["route_conclusion"]["file_helper_payload_owner_proven"])
        self.assertFalse(summary["file_helper_payload_owner_proven"])
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
