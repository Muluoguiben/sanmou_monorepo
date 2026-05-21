from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.ingestion.client_nep2_luascripts import build_nep2_luascripts_evidence_report


class Nep2LuaScriptsEvidenceTests(unittest.TestCase):
    def _candidate_scan(self) -> dict:
        return {
            "file": {
                "path": "D:\\bilibili Game\\NSLG\\NSLG Game\\NEP2.dll",
                "size": 1234,
                "sha256": "a" * 64,
            },
            "interesting_string_count": 10,
            "interesting_import_or_symbol_strings": [
                "LuaJitLuaSrcLuaSrcEncrytedLuacCompiled",
                "luaL_loadbuffer",
                "D:\\local\\build.pdb",
                "unrelated",
            ],
            "xref_count": 1,
            "xrefs": [
                {
                    "string": "O3P1P1_1P2P3WAES",
                    "ref_rva": "0x1234",
                    "ref_section": ".text",
                    "instruction": "lea rax, [rip + 1]",
                    "window": [
                        {
                            "rva": "0x1234",
                            "bytes": "48 8d 05 01 00 00 00",
                            "mnemonic": "lea",
                            "op_str": "rax, [rip + 1]",
                            "is_ref": True,
                        },
                        {"rva": "0x123b", "bytes": "48 83 c0 0c", "mnemonic": "add", "op_str": "rax, 0xc", "is_ref": False},
                        {"rva": "0x123f", "bytes": "41 b8 04 00 00 00", "mnemonic": "mov", "op_str": "r8d, 4", "is_ref": False},
                        {"rva": "0x1245", "bytes": "48 8b d0", "mnemonic": "mov", "op_str": "rdx, rax", "is_ref": False},
                        {
                            "rva": "0x1248",
                            "bytes": "48 8d 0d 20 00 00 00",
                            "mnemonic": "lea",
                            "op_str": "rcx, [rip + 0x20]",
                            "is_ref": False,
                        },
                        {"rva": "0x124f", "bytes": "e8 ec ff 01 00", "mnemonic": "call", "op_str": "0x180021240", "is_ref": False},
                    ],
                }
            ],
            "interpretation": {"summary": "candidate summary"},
        }

    def _init_scan(self) -> dict:
        return {
            "init_luascripts_occurrences": [
                {
                    "rva": "0x88135e",
                    "section": ".data",
                    "window": [
                        {"ascii": "InitLuaScriptsScan@CGameProtector"},
                        {"ascii": "ThreadPool"},
                    ],
                }
            ],
            "pointer_refs_to_init_luascripts": [],
            "interpretation": {"summary": "init summary", "next_step": "trace call sites"},
        }

    def test_report_selects_targets_and_sanitizes_paths(self) -> None:
        report = build_nep2_luascripts_evidence_report(
            self._candidate_scan(),
            self._init_scan(),
            source_id="fixture-round",
        )
        dumped = json.dumps(report.model_dump(mode="json"), ensure_ascii=False)

        self.assertEqual(report.binary_name, "NEP2.dll")
        self.assertEqual(report.init_luascripts_occurrences[0].rva, "0x88135e")
        self.assertIn("luaL_loadbuffer", report.selected_candidate_strings)
        self.assertEqual(report.xref_count, 1)
        self.assertEqual(report.xrefs[0].ref_rva, "0x1234")
        self.assertEqual(report.string_chunk_registrations[0].chunk_text, "WAES")
        self.assertEqual(report.string_chunk_registrations[0].descriptor_rva, "0x126f")
        self.assertEqual(report.string_chunk_registrations[0].target_helper, "0x180021240")
        self.assertNotIn("D:\\", dumped)
        self.assertNotIn("build.pdb", dumped)

    def test_summary_cli_writes_yaml(self) -> None:
        from qa_agent.app.summarize_nep2_luascripts_evidence import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            candidate_path = tmp / "candidate.json"
            init_path = tmp / "init.json"
            output_path = tmp / "nep2.yaml"
            candidate_path.write_text(json.dumps(self._candidate_scan(), ensure_ascii=False), encoding="utf-8")
            init_path.write_text(json.dumps(self._init_scan(), ensure_ascii=False), encoding="utf-8")
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_luascripts_evidence",
                    "--candidate-scan",
                    str(candidate_path),
                    "--init-scan",
                    str(init_path),
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
        self.assertEqual(summary["init_luascripts_occurrences"], 1)
        self.assertEqual(summary["xref_count"], 1)


if __name__ == "__main__":
    unittest.main()
