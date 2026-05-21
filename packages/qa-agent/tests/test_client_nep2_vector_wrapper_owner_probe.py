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

from qa_agent.ingestion.client_nep2_vector_wrapper_owner_probe import (
    build_nep2_vector_wrapper_owner_probe_report,
)


class Nep2VectorWrapperOwnerProbeTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 189,
                    "slice": "nep2_vector_wrapper_owner_static_probe",
                    "input_artifacts": [
                        {
                            "file_name": r"C:\Users\Lan\Documents\New project\threads\artifacts\nep2_vector_candidate_provenance_round186.json",
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
                        "base_artifact": "nep2_vector_candidate_provenance_round186.json",
                        "vector_target_count": 11,
                        "known_file_helper_rvas": {"0xda90": "CreateFileW helper"},
                    },
                    "counts": {
                        "vector_target_count": 11,
                        "wrapper_function_count": 13,
                        "direct_vector_wrapper_count": 12,
                        "wrapper_with_vector_call_count": 12,
                        "vector_call_edge_count": 59,
                        "wrapper_with_keyword_ref_count": 0,
                        "wrapper_with_read_mapping_import_count": 0,
                        "wrapper_with_provenance_path_count": 0,
                        "vector_wrapper_owner_candidate_count": 0,
                    },
                    "wrappers": [
                        {
                            "wrapper_rva": "0x2ff0",
                            "function": {"begin": "0x2ff0", "end": "0x379b"},
                            "selection": {
                                "roles": ["direct_vector_caller"],
                                "seed_vector_rvas": ["0x120c0", "0x123e0"],
                            },
                            "verdict": "vector_wrapper_without_payload_source",
                            "counts": {"instructions": 200},
                            "imports": [],
                            "keyword_refs": [],
                            "vector_calls": [
                                {"site": "0x3249", "target_rva": "0x120c0"}
                            ],
                            "file_helper_calls": [],
                            "parent_contexts": [],
                            "provenance_paths": [],
                            "direct_caller_count": 0,
                            "direct_callee_count": 4,
                            "evidence_ref": (
                                "NSLG_NEP2_VECTOR_WRAPPER_OWNER:"
                                "nep2-vector-wrapper-owner-probe-round189:wrapper:0x2ff0"
                            ),
                        }
                    ],
                    "route_conclusion": {
                        "vector_wrapper_owner_candidate_found": False,
                        "vector_wrapper_payload_owner_proven": False,
                        "read_mapping_to_vector_wrapper_path_found": False,
                        "read_mapping_import_in_vector_wrapper_found": False,
                        "file_helper_to_vector_wrapper_bridge_found": False,
                        "metadata_or_luascripts_keyword_link_found": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "vector wrappers are unlinked",
                        "strongest_negative_signal": "no payload owner signal",
                        "search_policy": "demote isolated vector wrappers",
                    },
                    "evidence_refs": [
                        "NSLG_NEP2_VECTOR_WRAPPER_OWNER:round130:summary"
                    ],
                    "next_static_targets": ["recover payload owner"],
                    "limitations": ["static wrapper owner probe only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_vector_wrappers_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round189.json"
            self._write_input(input_path)
            report = build_nep2_vector_wrapper_owner_probe_report(
                input_path=input_path,
                source_id="nep2-vector-wrapper-owner-probe-round130",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.nep2_vector_wrapper_owner_probe.v1")
        self.assertEqual(report.input_artifacts[0].file_name, "nep2_vector_candidate_provenance_round186.json")
        self.assertEqual(report.nep2_file["file_name"], "NEP2.dll")
        self.assertEqual(report.counts["wrapper_function_count"], 13)
        self.assertEqual(report.counts["vector_wrapper_owner_candidate_count"], 0)
        self.assertFalse(report.route_conclusion["vector_wrapper_payload_owner_proven"])
        self.assertEqual(report.wrappers[0]["vector_calls"][0]["target_rva"], "0x120c0")

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_nep2_vector_wrapper_owner_probe import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round189.json"
            output_path = root / "wrapper_probe.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_vector_wrapper_owner_probe",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "nep2-vector-wrapper-owner-probe-round130",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.nep2_vector_wrapper_owner_probe.v1")
        self.assertEqual(data["source_id"], "nep2-vector-wrapper-owner-probe-round130")
        self.assertFalse(data["route_conclusion"]["vector_wrapper_payload_owner_proven"])
        self.assertEqual(summary["vector_wrapper_owner_candidate_count"], 0)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
