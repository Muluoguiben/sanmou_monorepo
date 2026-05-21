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

from qa_agent.ingestion.client_gameassembly_trace import build_gameassembly_route_trace_batch


class GameAssemblyRouteTraceTests(unittest.TestCase):
    def _write_round160(self, root: Path) -> None:
        path = root / "gameassembly_textasset_loadbuffer_correlation_round160.json"
        path.write_text(
            json.dumps(
                {
                    "round": 160,
                    "slice": "GameAssembly TextAsset/get_bytes/xluaL_loadbuffer static correlation",
                    "inputs": {
                        "binary_name": "GameAssembly.dll",
                        "binary_sha256": "abc123",
                    },
                    "counts": {
                        "target_string_count": 3,
                        "code_ref_count": 0,
                        "function_ref_count": 0,
                        "route_signal_function_count": 0,
                    },
                    "target_strings": [
                        {
                            "rva": "0x43e1e20",
                            "text": "UnityEngine.TextAsset::get_bytes()",
                            "labels": ["textasset", "textasset_get_bytes"],
                        },
                        {
                            "rva": "0x429b458",
                            "text": "xluaL_loadbuffer",
                            "labels": ["xlua_loadbuffer"],
                        },
                    ],
                    "functions": [],
                    "verdict": [
                        "Target strings found: 3.",
                        "No static TextAsset/get_bytes -> xluaL_loadbuffer bridge was proven in this pass.",
                    ],
                    "blockers": ["static string/ref correlation does not prove decoded LuaScripts payload semantics"],
                    "next": ["carry this route evidence into qa-agent only as decoder planning evidence"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / "gameassembly_textasset_loadbuffer_correlation_round160.md").write_text(
            "summary", encoding="utf-8"
        )
        (root / "gameassembly_textasset_loadbuffer_correlation_round160.asm").write_text(
            "; asm", encoding="utf-8"
        )

    def _write_round42(self, root: Path) -> None:
        (root / "gameassembly_anchor_trace_round42.json").write_text(
            json.dumps(
                {
                    "round": 42,
                    "slice": "GameAssembly anchor function trace",
                    "inputs": {"sha256": "abc123"},
                    "pdata_function_count": 10,
                    "watched_string_rvas": {
                        "0x429b45e": "xluaL_loadbuffer",
                        "0x4d88a98": "global-metadata.dat:first",
                    },
                    "hits": [
                        {
                            "label": "xlua_ascii_ref_1",
                            "containing_function": {"begin": "0xc7990", "end": "0xc79f0"},
                        }
                    ],
                    "summary": ["Most xlua references look like registration/binding code."],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_batch_summarizes_gameassembly_routes_without_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_round42(root)
            self._write_round160(root)
            batch = build_gameassembly_route_trace_batch(
                input_dir=root,
                source_id="fixture-gameassembly",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(batch.schema_version, "nslg.gameassembly_route_trace_batch.v1")
        self.assertEqual(batch.artifact_count, 2)
        self.assertEqual(batch.round_range, {"min": 42, "max": 160})
        self.assertEqual(batch.total_target_strings, 5)
        self.assertEqual(batch.total_code_refs, 1)
        self.assertEqual(batch.route_signal_record_count, 0)
        self.assertFalse(batch.route_conclusion["safe_for_publish"])
        self.assertFalse(batch.route_conclusion["textasset_loadbuffer_bridge_proven"])
        self.assertTrue(all("/" not in name for record in batch.records for name in record.artifact_files))
        self.assertIn("NSLG_GAMEASSEMBLY_TRACE:fixture-gameassembly:round=160:kind=textasset_loadbuffer_correlation", batch.evidence_refs)

    def test_cli_writes_yaml(self) -> None:
        from qa_agent.app.summarize_gameassembly_route_trace import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_round160(root)
            output_path = root / "gameassembly.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_gameassembly_route_trace",
                    "--input-dir",
                    str(root),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-gameassembly",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["source_id"], "fixture-gameassembly")
        self.assertEqual(data["artifact_count"], 1)
        self.assertEqual(data["records"][0]["artifact_kind"], "textasset_loadbuffer_correlation")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["artifact_count"], 1)


if __name__ == "__main__":
    unittest.main()
