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

from qa_agent.ingestion.client_nep2_bridge import build_nep2_init_bridge_report


class ClientNep2BridgeTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "nep2_init_luascripts_bridge_summary_round161.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 161,
                    "slice": "nep2_init_luascripts_bridge_summary",
                    "source_id": "nep2-init-bridge-round161",
                    "source_url": "local-nslg-client-nep2-init-bridge",
                    "source_site": "nslg_client_nep2_init_bridge",
                    "binary_name": "NEP2.dll",
                    "input_artifacts": [
                        {
                            "key": "round97_bridge_expansion",
                            "file_name": "nep2_threadpool_bridge_expansion_round97.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "summary": ["Round97 confirmed InitLuaScriptsScan bridge metadata."],
                    "counts": {
                        "bridge_record_count": 1,
                        "candidate_function_count": 1,
                        "round97_executable_bridge_ref_count": 0,
                    },
                    "status_counts": {"confirmed_rtti_lambda_metadata": 1},
                    "candidate_verdict_counts": {
                        "tiny metadata/lambda helper; no CAB transform proof": 1
                    },
                    "bridge_records": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_BRIDGE:fixture:bridge:0x881320",
                            "rva": "0x881320",
                            "label": "InitLuaScriptsScan@CGameProtector",
                            "type_descriptor_rva": "0x881320",
                            "name_rva": "0x881330",
                            "code_pointers": [{"target_rva": "0x4040"}],
                            "status": "confirmed_rtti_lambda_metadata",
                            "verdict": "metadata bridge only; no payload decoder proven",
                        }
                    ],
                    "range_summaries": [],
                    "constructor_enqueue_seeds": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_BRIDGE:fixture:seed:0x86ab0",
                            "function_rva": "0x86ab0",
                        }
                    ],
                    "candidate_functions": [
                        {
                            "evidence_ref": "NSLG_NEP2_INIT_BRIDGE:fixture:candidate:0x4040",
                            "function_rva": "0x4040",
                            "function_size": "0xaa",
                            "sources": ["round97_inspected_candidate"],
                            "verdict": "tiny metadata/lambda helper; no CAB transform proof",
                            "score": 16,
                            "counts": {"instructions": 10},
                            "file_import_names": [],
                            "keyword_xref_count": 0,
                            "closed_route_neighbor_count": 0,
                        }
                    ],
                    "route_conclusion": {
                        "bridge_metadata_confirmed": True,
                        "decryptor_body_proven": False,
                        "file_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                    },
                    "negative_signals": ["no executable instruction references"],
                    "next_static_targets": ["trace InitLuaScriptsScan"],
                    "limitations": ["static evidence only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_bridge_as_static_trace(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_nep2_init_bridge_report(
                input_path=input_path,
                source_id="fixture-nep2-init-bridge",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.nep2_init_bridge.v1")
        self.assertEqual(report.source_id, "fixture-nep2-init-bridge")
        self.assertEqual(report.round, 161)
        self.assertEqual(report.counts["bridge_record_count"], 1)
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertFalse(report.route_conclusion["decryptor_body_proven"])
        self.assertEqual(len(report.evidence_refs), 3)
        self.assertTrue(
            all(not artifact["file_name"].startswith("/") for artifact in report.input_artifacts)
        )

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_nep2_init_bridge import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "nep2-init-bridge.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_init_bridge",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-nep2-init-bridge",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.nep2_init_bridge.v1")
        self.assertEqual(data["source_id"], "fixture-nep2-init-bridge")
        self.assertEqual(data["counts"]["candidate_function_count"], 1)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
