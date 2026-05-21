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

from qa_agent.ingestion.client_gameassembly_resolver_trace import (
    build_gameassembly_resolver_trace_report,
)


class GameAssemblyResolverTraceTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 165,
                    "source_id": "gameassembly-resolver-candidate-round165",
                    "slice": "gameassembly_resolver_candidate_static_trace",
                    "input_artifacts": [
                        {
                            "role": "gameassembly_binary",
                            "file_name": "GameAssembly.dll",
                            "sha256": "a" * 64,
                        }
                    ],
                    "target": {
                        "resolver_candidate_rva": "0x5ccc30",
                        "candidate_found": True,
                    },
                    "counts": {
                        "resolver_candidate_direct_callsite_count": 2948,
                        "caller_keyword_ref_function_count": 28,
                        "resolver_candidate_import_call_count": 0,
                    },
                    "target_string_summary": {"xlua_api": 71, "textasset": 12},
                    "resolver_candidate": {
                        "function": {
                            "begin": "0x5ccc30",
                            "end": "0x5cce50",
                            "size": "0x220",
                        },
                        "pdata_function_found": False,
                        "counts": {"instructions": 182},
                    },
                    "notable_caller_functions": [
                        {
                            "function": {
                                "begin": "0xc78b0",
                                "end": "0xc794e",
                                "size": "0x9e",
                            },
                            "counts": {"keyword_refs": 1},
                        }
                    ],
                    "route_conclusion": {
                        "resolver_candidate_function_found": True,
                        "descriptor_resolver_pattern_supported": True,
                        "candidate_has_payload_owner_signal": False,
                        "method_ownership_recovered": False,
                        "textasset_payload_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_current_signal": "descriptor resolver routing",
                        "strongest_negative_signal": "payload owner is not proven",
                        "search_policy": "keep as resolver evidence",
                    },
                    "next_static_targets": ["recover protected metadata"],
                    "limitations": ["static evidence only"],
                    "evidence_refs": [
                        "NSLG_GAMEASSEMBLY_RESOLVER_TRACE:round58:candidate:0x5ccc30"
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_resolver_trace_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round165.json"
            self._write_input(input_path)
            report = build_gameassembly_resolver_trace_report(
                input_path=input_path,
                source_id="gameassembly-resolver-trace-round58",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_resolver_trace.v1")
        self.assertEqual(report.source_id, "gameassembly-resolver-trace-round58")
        self.assertEqual(report.counts["resolver_candidate_direct_callsite_count"], 2948)
        self.assertTrue(report.route_conclusion["descriptor_resolver_pattern_supported"])
        self.assertFalse(report.route_conclusion["textasset_payload_owner_proven"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertTrue(report.evidence_refs[0].startswith("NSLG_GAMEASSEMBLY_RESOLVER_TRACE:"))

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_gameassembly_resolver_trace import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round165.json"
            output_path = root / "resolver.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_gameassembly_resolver_trace",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "gameassembly-resolver-trace-round58",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_resolver_trace.v1")
        self.assertEqual(data["source_id"], "gameassembly-resolver-trace-round58")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertTrue(summary["resolver_candidate_function_found"])
        self.assertTrue(summary["descriptor_resolver_pattern_supported"])


if __name__ == "__main__":
    unittest.main()
