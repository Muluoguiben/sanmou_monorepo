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

from qa_agent.ingestion.client_initializer_dispatch_trace import (
    build_initializer_dispatch_trace_report,
)


class ClientInitializerDispatchTraceTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        path = root / "gameassembly_initializer_dispatch_trace_round183.json"
        path.write_text(
            json.dumps(
                {
                    "round": 183,
                    "slice": "gameassembly_initializer_dispatch_trace",
                    "input_artifacts": [
                        {
                            "role": "module:GameAssembly.dll",
                            "file_name": r"C:\NSLG\GameAssembly.dll",
                            "size_bytes": 94127168,
                            "sha256": "a" * 64,
                        }
                    ],
                    "gameassembly": {
                        "file_name": "GameAssembly.dll",
                        "size_bytes": 94127168,
                        "sha256": "b" * 64,
                        "entry_rva": "0x5faa3c",
                        "pdata_function_count": 290472,
                        "export_count": 386,
                    },
                    "target_summary": {
                        "target_count": 29,
                        "by_category": {
                            "registration": 4,
                            "metadata_candidate": 12,
                            "metadata_family_ref": 8,
                            "string": 3,
                        },
                        "sample": [
                            {
                                "label": "code_registration_struct",
                                "category": "registration",
                                "start": "0x4332730",
                                "end": "0x43327b8",
                            }
                        ],
                    },
                    "roots": {
                        "root_count": 4,
                        "items": [
                            {
                                "label": "pe_entry",
                                "kind": "entry",
                                "rva": "0x5faa3c",
                                "function": {
                                    "begin": "0x5faa3c",
                                    "end": "0x5faa79",
                                    "size": "0x3d",
                                },
                            }
                        ],
                    },
                    "scan_counts": {"instructions": 16265170},
                    "goal_function_summary": {
                        "registration_anchor_ref_functions_count": 0,
                        "metadata_candidate_ref_functions_count": 0,
                        "global_metadata_string_ref_functions_count": 2,
                        "global_metadata_string_ref_functions": [
                            {
                                "function": {
                                    "begin": "0x55f6d0",
                                    "end": "0x55f83a",
                                    "size": "0x16a",
                                },
                                "instruction_count": 73,
                                "direct_callee_count": 3,
                                "direct_caller_count": 1,
                                "indirect_branch_count": 0,
                                "target_ref_counts": {"string": 1},
                                "target_ref_label_counts": {
                                    "string:global-metadata.dat": 1
                                },
                            }
                        ],
                    },
                    "bounded_path_report": {
                        "registration_anchor_ref": {
                            "goal_function_count": 0,
                            "bounded_forward_path": {"found": False, "path": []},
                            "bounded_reverse_paths": [],
                        },
                        "metadata_candidate_ref": {
                            "goal_function_count": 0,
                            "bounded_forward_path": {"found": False, "path": []},
                            "bounded_reverse_paths": [],
                        },
                        "global_metadata_string_ref": {
                            "goal_function_count": 2,
                            "bounded_forward_path": {"found": False, "path": []},
                            "bounded_reverse_paths": [],
                        },
                    },
                    "nonexec_function_pointer_hits": {
                        "target_function_count": 3,
                        "hit_count": 0,
                        "hits": [],
                    },
                    "dispatcher_candidates": [
                        {
                            "function": {
                                "begin": "0xe4ec50",
                                "end": "0xe4f280",
                                "size": "0x630",
                            },
                            "score": 70,
                            "reasons": ["direct-fanout=52", "indirect-branches=18"],
                            "direct_callee_count": 52,
                            "direct_caller_count": 2,
                            "indirect_branch_count": 18,
                        }
                    ],
                    "counts": {
                        "instruction_count": 16265170,
                        "function_row_count": 290472,
                        "registration_anchor_ref_function_count": 0,
                        "metadata_candidate_ref_function_count": 0,
                        "global_metadata_string_ref_function_count": 2,
                        "entry_to_registration_path_found": 0,
                        "entry_to_metadata_candidate_path_found": 0,
                        "entry_to_global_metadata_path_found": 0,
                        "nonexec_pointer_hit_count": 0,
                        "dispatcher_candidate_count": 24,
                        "init_lua_env_method_pointer_recovered": 0,
                        "protected_metadata_method_ownership_recovered": 0,
                    },
                    "route_conclusion": {
                        "initializer_dispatcher_route_recovered": False,
                        "registration_ownership_recovered": False,
                        "metadata_registration_paired_by_dispatch_trace": False,
                        "protected_metadata_method_ownership_recovered": False,
                        "init_lua_env_method_pointer_recovered": False,
                        "safe_for_publish": False,
                        "summary": "Bounded direct-call dispatcher trace did not recover a registration/metadata owner.",
                        "search_policy": [
                            "Treat bounded direct-call dispatcher trace as negative"
                        ],
                    },
                    "evidence_refs": [
                        "NSLG_INITIALIZER_DISPATCH_TRACE:round183:bounded-callgraph-paths"
                    ],
                    "next_static_targets": ["recover protected metadata ownership"],
                    "limitations": ["static route evidence only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return path

    def test_build_initializer_dispatch_trace_report_sanitizes_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            fixture = self._write_fixture(Path(tmp))
            report = build_initializer_dispatch_trace_report(
                input_path=fixture,
                source_id="gameassembly-initializer-dispatch-trace-round112",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.gameassembly_initializer_dispatch_trace.v1")
        self.assertEqual(report.input_artifacts[0].file_name, "GameAssembly.dll")
        self.assertEqual(report.gameassembly["entry_rva"], "0x5faa3c")
        self.assertEqual(report.counts["function_row_count"], 290472)
        self.assertEqual(report.counts["global_metadata_string_ref_function_count"], 2)
        self.assertFalse(report.route_conclusion["initializer_dispatcher_route_recovered"])
        self.assertFalse(report.route_conclusion["init_lua_env_method_pointer_recovered"])
        self.assertEqual(report.dispatcher_candidates[0]["function"]["begin"], "0xe4ec50")

    def test_cli_writes_yaml(self) -> None:
        from qa_agent.app import summarize_gameassembly_initializer_dispatch_trace as cli

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            fixture = self._write_fixture(root)
            output = root / "out.yaml"
            argv = [
                "summarize_gameassembly_initializer_dispatch_trace",
                "--input",
                str(fixture),
                "--output",
                str(output),
                "--source-id",
                "fixture-initializer-dispatch",
            ]
            with patch.object(sys, "argv", argv), patch("sys.stdout", new_callable=io.StringIO) as stdout:
                cli.main()

            data = yaml.safe_load(output.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.gameassembly_initializer_dispatch_trace.v1")
        self.assertEqual(data["source_id"], "fixture-initializer-dispatch")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["global_metadata_string_ref_function_count"], 2)
        self.assertFalse(summary["initializer_dispatcher_route_recovered"])


if __name__ == "__main__":
    unittest.main()
