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

from qa_agent.ingestion.client_gameassembly_resolver_caller_trace import (
    build_gameassembly_resolver_caller_trace_report,
)


class GameAssemblyResolverCallerTraceTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 166,
                    "source_id": "gameassembly-resolver-caller-payload-round166",
                    "slice": "gameassembly_resolver_caller_payload_owner_trace",
                    "input_artifacts": [
                        {
                            "role": "gameassembly_binary",
                            "file_name": "GameAssembly.dll",
                            "sha256": "a" * 64,
                        }
                    ],
                    "target": {
                        "resolver_candidate_rva": "0x5ccc30",
                        "search_scope": "all direct rel32 caller functions with pdata coverage",
                    },
                    "counts": {
                        "resolver_candidate_direct_callsite_count": 2948,
                        "unique_direct_caller_function_count": 2870,
                        "caller_with_xlua_api_ref_count": 150,
                        "caller_with_textasset_ref_count": 0,
                        "caller_with_luascripts_or_data_stem_ref_count": 0,
                        "payload_owner_candidate_count": 0,
                    },
                    "category_counts": {"xlua_api": 150},
                    "classification_counts": {
                        "no_payload_signal": 2720,
                        "xlua_descriptor_only": 150,
                    },
                    "xlua_descriptor_only_samples": [
                        {
                            "function": {"begin": "0xc78b0"},
                            "payload_trace": {"classification": "xlua_descriptor_only"},
                        }
                    ],
                    "route_conclusion": {
                        "all_direct_resolver_callers_scanned": True,
                        "textasset_payload_owner_proven": False,
                        "file_buffer_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "resolver_layer_has_payload_owner_candidate": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "descriptor-only shapes",
                        "strongest_negative_signal": "no payload owner candidate",
                        "search_policy": "stop treating resolver callers as payload-owner leads",
                    },
                    "next_static_targets": ["recover protected metadata"],
                    "limitations": ["static evidence only"],
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_RESOLVER_CALLER_TRACE:round61:target:0x5ccc30"
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_resolver_caller_trace_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round166.json"
            self._write_input(input_path)
            report = build_gameassembly_resolver_caller_trace_report(
                input_path=input_path,
                source_id="gameassembly-resolver-caller-trace-round61",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_resolver_caller_trace.v1")
        self.assertEqual(report.source_id, "gameassembly-resolver-caller-trace-round61")
        self.assertEqual(report.counts["unique_direct_caller_function_count"], 2870)
        self.assertEqual(report.counts["payload_owner_candidate_count"], 0)
        self.assertFalse(report.route_conclusion["textasset_payload_owner_proven"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertTrue(report.evidence_refs[0].startswith("NSLG_GAMEASSEMBLY_RESOLVER_CALLER_TRACE:"))

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_gameassembly_resolver_caller_trace import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round166.json"
            output_path = root / "resolver-caller.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_gameassembly_resolver_caller_trace",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "gameassembly-resolver-caller-trace-round61",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_resolver_caller_trace.v1")
        self.assertEqual(data["source_id"], "gameassembly-resolver-caller-trace-round61")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["payload_owner_candidate_count"], 0)
        self.assertFalse(summary["textasset_payload_owner_proven"])


if __name__ == "__main__":
    unittest.main()
