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

from qa_agent.ingestion.client_textasset_payload_owner_trace import (
    build_textasset_payload_owner_trace_report,
)


class TextAssetPayloadOwnerTraceTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "textasset_payload_owner_trace_round173.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 173,
                    "slice": "textasset_payload_owner_static_trace",
                    "input_artifacts": [
                        {
                            "path": "luascripts_payload_variant_corpus_round172.json",
                            "role": "expanded encrypted LuaScripts payload corpus",
                        }
                    ],
                    "prior_context": {
                        "round172_payload_variant_count": 932,
                        "round163_textasset_to_loadbuffer_owner_proven": False,
                    },
                    "counts": {
                        "module_count": 4,
                        "term_count": 315,
                        "term_hit_count": 706,
                        "exact_asset_path_or_stem_hit_count": 0,
                        "code_ref_count": 0,
                        "candidate_function_count": 0,
                        "payload_owner_candidate_count": 0,
                        "route_candidate_count": 0,
                    },
                    "term_kind_counts": {
                        "asset_filename": 16,
                        "asset_path": 104,
                        "route_keyword": 17,
                    },
                    "module_records": [
                        {
                            "module": "GameAssembly.dll",
                            "counts": {
                                "term_hit_count": 45,
                                "exact_asset_path_or_stem_hit_count": 0,
                                "code_ref_count": 0,
                                "candidate_function_count": 0,
                                "payload_owner_candidate_count": 0,
                            },
                            "term_kind_counts": {"route_keyword": 45},
                            "term_encoding_counts": {"ascii": 45},
                            "term_hit_samples": [
                                {
                                    "kind": "route_keyword",
                                    "value": "xluaL_loadbuffer",
                                    "encoding": "ascii",
                                    "rva": "0x429b458",
                                    "section": ".rdata",
                                }
                            ],
                            "code_ref_samples": [],
                            "candidate_functions": [],
                        }
                    ],
                    "route_conclusion": {
                        "textasset_payload_owner_proven": False,
                        "textasset_payload_owner_candidate_found": False,
                        "exact_asset_path_or_stem_native_hit_found": False,
                        "native_code_refs_to_textasset_terms_found": False,
                        "lua_payload_decoder_recovered": False,
                        "safe_for_publish": False,
                        "strongest_positive_signal": "Native module string hits exist",
                        "strongest_negative_signal": "No candidate is promoted",
                        "search_policy": "retain candidate functions only as route evidence",
                    },
                    "evidence_refs": [
                        "NSLG_TEXTASSET_PAYLOAD_OWNER:round173:summary"
                    ],
                    "next_static_targets": ["recover SerializedFile object layout"],
                    "limitations": ["static PE scan only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_owner_trace_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_textasset_payload_owner_trace_report(
                input_path=input_path,
                source_id="fixture-textasset-owner-trace",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.textasset_payload_owner_trace.v1")
        self.assertEqual(report.source_id, "fixture-textasset-owner-trace")
        self.assertEqual(report.counts["term_hit_count"], 706)
        self.assertEqual(report.counts["payload_owner_candidate_count"], 0)
        self.assertEqual(report.module_records[0]["module"], "GameAssembly.dll")
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertFalse(report.route_conclusion["textasset_payload_owner_proven"])

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_textasset_payload_owner_trace import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "textasset-owner.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_textasset_payload_owner_trace",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-textasset-owner-trace",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.textasset_payload_owner_trace.v1")
        self.assertEqual(data["source_id"], "fixture-textasset-owner-trace")
        self.assertEqual(data["counts"]["term_hit_count"], 706)
        self.assertEqual(summary["code_ref_count"], 0)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
