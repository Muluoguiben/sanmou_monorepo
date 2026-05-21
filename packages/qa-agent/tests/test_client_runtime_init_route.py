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

from qa_agent.ingestion.client_runtime_init_route import (
    build_runtime_init_metadata_route_report,
)


class RuntimeInitMetadataRouteTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 164,
                    "slice": "runtime_init_metadata_route_summary",
                    "input_artifacts": [
                        {
                            "role": "round72_global_metadata_structure",
                            "file_name": "global_metadata_structure_round72.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "counts": {
                        "runtime_initialize_anchor_count": 1,
                        "global_metadata_file_size": 21182776,
                        "global_metadata_plaintext_needle_hit_count": 0,
                        "native_boundary_loadbuffer_export_signal_count": 3,
                    },
                    "runtime_initialize_anchor": {
                        "init_lua_env_anchor_found_in_analysis": True,
                        "assembly": "Assembly-CSharp",
                        "managed_type": "NSLGame.Patcher.GameUpdater",
                        "method": "InitLuaEnv",
                    },
                    "global_metadata_wrapper": {
                        "word0": "0xfab11baf",
                        "word1_equals_file_size": True,
                        "protected_size_mod_16": 0,
                    },
                    "route_conclusion": {
                        "runtime_init_anchor_known": True,
                        "runtime_initialize_onloads_file_present": False,
                        "global_metadata_protected_wrapper_confirmed": True,
                        "protected_global_metadata_decoded": False,
                        "init_lua_env_method_address_recovered": False,
                        "textasset_to_loadbuffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "InitLuaEnv is known",
                        "strongest_blocker": "metadata is protected",
                        "search_policy": "recover method ownership",
                    },
                    "next_static_targets": ["recover protected metadata"],
                    "limitations": ["static route summary only"],
                    "evidence_refs": [
                        "NSLG_RUNTIME_INIT_ROUTE:round55:anchor:initluaenv"
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_runtime_route_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round164.json"
            self._write_input(input_path)
            report = build_runtime_init_metadata_route_report(
                input_path=input_path,
                source_id="runtime-init-route-round55",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.runtime_init_metadata_route.v1")
        self.assertEqual(report.source_id, "runtime-init-route-round55")
        self.assertEqual(report.counts["runtime_initialize_anchor_count"], 1)
        self.assertTrue(report.route_conclusion["global_metadata_protected_wrapper_confirmed"])
        self.assertFalse(report.route_conclusion["init_lua_env_method_address_recovered"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.input_artifacts[0].file_name, "global_metadata_structure_round72.json")
        self.assertTrue(report.evidence_refs[0].startswith("NSLG_RUNTIME_INIT_ROUTE:"))

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_runtime_init_metadata_route import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round164.json"
            output_path = root / "runtime.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_runtime_init_metadata_route",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "runtime-init-route-round55",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.runtime_init_metadata_route.v1")
        self.assertEqual(data["source_id"], "runtime-init-route-round55")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertTrue(summary["runtime_init_anchor_known"])
        self.assertTrue(summary["global_metadata_protected_wrapper_confirmed"])


if __name__ == "__main__":
    unittest.main()
