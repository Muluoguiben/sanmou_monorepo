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

from qa_agent.ingestion.client_lua_crypto import build_lua_crypto_evidence_report


class LuaCryptoEvidenceTests(unittest.TestCase):
    def _evidence(self) -> dict:
        return {
            "binary_string_scan": [
                {
                    "file": "/mnt/d/bilibili Game/NSLG/NSLG Game/GameAssembly.dll",
                    "size": 1000,
                    "term_hits": {"AES": ["0x10"], "xluaL_loadbuffer": ["0x20", "0x30"]},
                    "context_strings": [
                        {"string": "xluaL_loadbuffer"},
                        {"string": "D:\\build\\secret.pdb"},
                        {"string": "luaopen_client_crypt"},
                    ],
                }
            ],
            "payload_block_analysis": [
                {
                    "file": "heros.bytes.bin",
                    "size": 32,
                    "size_mod_16": 0,
                    "entropy": 7.91,
                    "unique_byte_values": 32,
                    "block_count_16": 2,
                    "duplicate_16byte_blocks": 0,
                    "first_block_hex": "aa",
                    "last_block_hex": "bb",
                }
            ],
            "lua_patch_block_analysis": [
                {"file": "/mnt/d/bilibili Game/NSLG/NSLG Game/LocalPersistentData/lua-patches/x"}
            ],
            "runtime_initialize_lua_entries": [
                {
                    "assemblyName": "Assembly-CSharp",
                    "nameSpace": "NSLGame.Patcher",
                    "className": "GameUpdater",
                    "methodName": "InitLuaEnv",
                    "loadTypes": 4,
                }
            ],
            "il2cpp_dumper_probe": {
                "result": "failed_invalid_metadata",
                "evidence": "/mnt/d/bilibili Game/NSLG/NSLG Game/global-metadata.dat invalid",
            },
            "conclusions": [
                "Next useful slice: recover xrefs around xluaL_loadbuffer in /mnt/d/bilibili Game/NSLG/NSLG Game/GameAssembly.dll"
            ],
        }

    def test_report_sanitizes_local_paths_and_counts_block_shape(self) -> None:
        report = build_lua_crypto_evidence_report(
            self._evidence(),
            source_id="fixture-round",
            generated_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
        )
        dumped = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)

        self.assertEqual(report.binary_string_hits[0].binary_name, "GameAssembly.dll")
        self.assertEqual(report.binary_string_hits[0].term_hit_counts["xluaL_loadbuffer"], 2)
        self.assertIn("luaopen_client_crypt", report.binary_string_hits[0].selected_context_strings)
        self.assertEqual(report.payload_status_counts["high_entropy_16byte_aligned"], 1)
        self.assertEqual(report.skipped_runtime_patch_samples, 1)
        self.assertEqual(report.runtime_initialize_lua_entries[0].method_name, "InitLuaEnv")
        self.assertNotIn("LocalPersistentData", dumped)
        self.assertNotIn("/mnt/d", dumped)
        self.assertNotIn("D:\\", dumped)

    def test_summary_cli_writes_yaml(self) -> None:
        from qa_agent.app.summarize_luascripts_crypto_evidence import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            input_path = tmp / "evidence.json"
            output_path = tmp / "evidence.yaml"
            input_path.write_text(json.dumps(self._evidence(), ensure_ascii=False), encoding="utf-8")
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_luascripts_crypto_evidence",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-round",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["source_id"], "fixture-round")
        self.assertEqual(summary["payload_samples"], 1)
        self.assertEqual(summary["skipped_runtime_patch_samples"], 1)


if __name__ == "__main__":
    unittest.main()
