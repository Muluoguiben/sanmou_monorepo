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

from qa_agent.ingestion.client_gameassembly_global_metadata_owner_probe import (
    build_gameassembly_global_metadata_owner_probe_report,
)


class GameAssemblyGlobalMetadataOwnerProbeTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 188,
                    "slice": "gameassembly_global_metadata_owner_probe",
                    "input_artifacts": [
                        {
                            "file_name": r"D:\bilibili Game\NSLG\NSLG Game\GameAssembly.dll",
                            "sha256": "a" * 64,
                        }
                    ],
                    "gameassembly_summary": {
                        "file_name": r"D:\bilibili Game\NSLG\NSLG Game\GameAssembly.dll",
                        "size_bytes": 100,
                        "sha256": "b" * 64,
                        "pdata_function_count": 2,
                    },
                    "selection_policy": {
                        "seed_rvas": {
                            "0x55f6d0": "round183_global_metadata_string_ref_function",
                            "0x5736d0": "round183_global_metadata_string_ref_function",
                        },
                        "caller_depth": 2,
                        "callee_depth": 1,
                    },
                    "counts": {
                        "target_count": 2,
                        "seed_function_count": 2,
                        "metadata_string_ref_function_count": 2,
                        "file_or_mapping_import_function_count": 0,
                        "metadata_candidate_ref_function_count": 0,
                        "loader_owner_candidate_count": 0,
                    },
                    "targets": [
                        {
                            "target_rva": "0x55f6d0",
                            "function": {"begin": "0x55f6d0", "end": "0x55f719"},
                            "contexts": [
                                {
                                    "seed_rva": "0x55f6d0",
                                    "seed_label": "round183_global_metadata_string_ref_function",
                                    "role": "seed",
                                    "depth": 0,
                                    "path_length": 1,
                                }
                            ],
                            "verdict": "metadata_string_ref_without_file_or_registration_owner",
                            "counts": {"metadata_string_ref": 1},
                            "imports": [],
                            "metadata_string_refs": [
                                {
                                    "rva": "0x55f6e9",
                                    "target_rva": "0x401000",
                                    "terms": ["global-metadata.dat"],
                                    "text": "0055f6e9: lea rcx, [rip+0x1]",
                                }
                            ],
                            "metadata_candidate_refs": [],
                            "constants": [],
                            "direct_caller_count": 0,
                            "direct_callee_count": 0,
                            "evidence_ref": (
                                "NSLG_GAMEASSEMBLY_GLOBAL_METADATA_OWNER:"
                                "gameassembly-global-metadata-owner-probe-round188:target:0x55f6d0"
                            ),
                        }
                    ],
                    "route_conclusion": {
                        "global_metadata_owner_candidate_found": False,
                        "global_metadata_string_refs_confirmed": True,
                        "file_or_mapping_api_link_found": False,
                        "metadata_registration_candidate_link_found": False,
                        "metadata_registration_owner_recovered": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "string refs only",
                        "strongest_negative_signal": "no owner context",
                        "search_policy": "do not promote string refs alone",
                    },
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_GLOBAL_METADATA_OWNER:round127:summary"
                    ],
                    "next_static_targets": ["recover protected metadata ownership"],
                    "limitations": ["static callgraph only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_string_ref_route_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round188.json"
            self._write_input(input_path)
            report = build_gameassembly_global_metadata_owner_probe_report(
                input_path=input_path,
                source_id="gameassembly-global-metadata-owner-probe-round127",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_global_metadata_owner_probe.v1")
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertEqual(report.gameassembly_summary["file_name"], "GameAssembly.dll")
        self.assertEqual(report.counts["target_count"], 2)
        self.assertEqual(report.counts["loader_owner_candidate_count"], 0)
        self.assertFalse(report.route_conclusion["global_metadata_owner_candidate_found"])
        self.assertTrue(report.route_conclusion["global_metadata_string_refs_confirmed"])
        self.assertEqual(report.targets[0]["metadata_string_refs"][0]["terms"], ["global-metadata.dat"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_gameassembly_global_metadata_owner_probe import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round188.json"
            output_path = root / "owner_probe.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_gameassembly_global_metadata_owner_probe",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "gameassembly-global-metadata-owner-probe-round127",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_global_metadata_owner_probe.v1")
        self.assertEqual(data["source_id"], "gameassembly-global-metadata-owner-probe-round127")
        self.assertFalse(data["route_conclusion"]["global_metadata_owner_candidate_found"])
        self.assertEqual(summary["loader_owner_candidate_count"], 0)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
