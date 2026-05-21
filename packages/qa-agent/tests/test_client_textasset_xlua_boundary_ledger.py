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

from qa_agent.ingestion.client_textasset_xlua_boundary_ledger import (
    build_textasset_xlua_boundary_ledger_report,
)


class TextAssetXluaBoundaryLedgerTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "textasset_xlua_boundary_ledger_round177.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 177,
                    "slice": "textasset_xlua_boundary_route_ledger",
                    "input_artifacts": [
                        {
                            "file_name": "native_loadbuffer_boundary_trace_round163.json",
                            "role": "native xLua loadbuffer boundary",
                            "size_bytes": 100,
                            "sha256": "a" * 64,
                        }
                    ],
                    "route_records": [
                        {
                            "route_id": "resolved_payload_native_exact_anchor_scan",
                            "title": "Resolved native exact-anchor scan",
                            "status": "closed_negative",
                            "maturity": "negative_exact_anchor_scan",
                            "source_round": 176,
                            "evidence_refs": [
                                "NSLG_RESOLVED_PAYLOAD_NATIVE_ANCHOR:round176:summary"
                            ],
                            "signal_summary": ["native_strong_anchor_hit_count_capped=0"],
                            "blocking_signals": ["no native strong anchors"],
                            "counts": {"native_strong_anchor_hit_count_capped": 0},
                            "next_actions": ["do not repeat constant scans"],
                        },
                        {
                            "route_id": "protected_metadata_method_ownership_or_boundary_control_flow",
                            "title": "Protected metadata method ownership",
                            "status": "next_viable_target",
                            "maturity": "requires_new_static_ownership_evidence",
                            "source_round": 177,
                            "evidence_refs": [
                                "NSLG_TEXTASSET_XLUA_BOUNDARY_LEDGER:round177:route:protected"
                            ],
                            "counts": {"method_ownership_recovered": 0},
                            "next_actions": ["recover protected metadata method ownership"],
                        },
                    ],
                    "route_status_counts": {
                        "closed_negative": 1,
                        "next_viable_target": 1,
                    },
                    "counts": {
                        "input_artifact_count": 1,
                        "route_record_count": 2,
                        "closed_negative_route_count": 1,
                        "blocked_route_count": 0,
                        "next_viable_route_count": 1,
                        "proven_payload_owner_route_count": 0,
                        "exact_anchor_native_hit_count": 0,
                        "publishable_knowledge_entries": 0,
                    },
                    "route_conclusion": {
                        "native_payload_buffer_owner_proven": False,
                        "lua_payload_decoder_recovered": False,
                        "gameassembly_static_xlua_import_route_closed": True,
                        "resolver_direct_caller_route_closed": True,
                        "exact_native_anchor_route_closed": True,
                        "protected_metadata_method_ownership_recovered": False,
                        "next_viable_route": "protected_metadata_method_ownership_or_boundary_control_flow",
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "strongest_current_signal": "closed routes constrain next search",
                        "strongest_negative_signal": "payload owner is not proven",
                        "search_policy": "continue method ownership recovery",
                    },
                    "evidence_refs": [
                        "NSLG_TEXTASSET_XLUA_BOUNDARY_LEDGER:round177:summary"
                    ],
                    "next_static_targets": ["recover protected metadata method ownership"],
                    "limitations": ["ledger only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_boundary_ledger_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_textasset_xlua_boundary_ledger_report(
                input_path=input_path,
                source_id="fixture-boundary-ledger",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.textasset_xlua_boundary_ledger.v1")
        self.assertEqual(report.source_id, "fixture-boundary-ledger")
        self.assertEqual(report.counts["route_record_count"], 2)
        self.assertFalse(report.route_conclusion["native_payload_buffer_owner_proven"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(
            report.route_records[1].route_id,
            "protected_metadata_method_ownership_or_boundary_control_flow",
        )

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_textasset_xlua_boundary_ledger import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "boundary-ledger.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_textasset_xlua_boundary_ledger",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-boundary-ledger",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.textasset_xlua_boundary_ledger.v1")
        self.assertEqual(data["source_id"], "fixture-boundary-ledger")
        self.assertEqual(data["counts"]["closed_negative_route_count"], 1)
        self.assertEqual(
            summary["next_viable_route"],
            "protected_metadata_method_ownership_or_boundary_control_flow",
        )
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
