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

from qa_agent.ingestion.client_global_metadata_transform_probe import (
    build_global_metadata_transform_probe_report,
)


class GlobalMetadataTransformProbeTests(unittest.TestCase):
    def _write_input(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "round": 167,
                    "slice": "global_metadata_header_transform_probe",
                    "input_artifacts": [
                        {
                            "file_name": "global_metadata_structure_round72.json",
                            "sha256": "a" * 64,
                        }
                    ],
                    "file_summary": {
                        "file_size": 21182776,
                        "word0": "0xfab11baf",
                        "word1_equals_file_size": True,
                        "protected_size_mod_16": 0,
                    },
                    "transform_probe": {
                        "candidate_count": 1314,
                        "needle_hit_candidate_count": 0,
                        "tested_transform_families": ["single-byte xor/add/sub"],
                        "best_header_candidates": [
                            {
                                "name": "dword_xor_to_inline_version",
                                "params": {"version": 24},
                                "header_score": 20,
                                "best_header_model": {
                                    "model": "payload_starts_with_version",
                                    "valid_pair_count": 0,
                                    "monotonic_pair_count": 0,
                                    "version_standard_int": True,
                                },
                            }
                        ],
                    },
                    "repeated_block_probe": {
                        "by_block_size": [
                            {
                                "block_size": 16,
                                "duplicate_block_kinds": 20744,
                                "duplicate_extra_instances": 143452,
                            }
                        ]
                    },
                    "conclusion": {
                        "protected_wrapper_confirmed": True,
                        "plaintext_metadata_recovered": False,
                        "init_lua_env_method_ownership_recovered": False,
                        "safe_for_publish": False,
                        "publishable_knowledge_entries": 0,
                        "verdict": ["bounded transform probe did not recover metadata"],
                    },
                    "next_static_targets": ["pivot to loader mutation point"],
                    "limitations": ["static transform probe only"],
                    "evidence_refs": [
                        "NSLG_GLOBAL_METADATA_TRANSFORM:round64:transform-probe"
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_report_keeps_global_metadata_probe_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "round167.json"
            self._write_input(input_path)
            report = build_global_metadata_transform_probe_report(
                input_path=input_path,
                source_id="global-metadata-transform-probe-round64",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.global_metadata_transform_probe.v1")
        self.assertEqual(report.source_id, "global-metadata-transform-probe-round64")
        self.assertEqual(report.counts["transform_candidate_count"], 1314)
        self.assertEqual(report.counts["needle_hit_candidate_count"], 0)
        self.assertEqual(report.counts["best_header_valid_pair_count"], 0)
        self.assertFalse(report.route_conclusion["plaintext_metadata_recovered"])
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertEqual(report.input_artifacts[0].file_name, "global_metadata_structure_round72.json")
        self.assertTrue(report.evidence_refs[0].startswith("NSLG_GLOBAL_METADATA_TRANSFORM:"))

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_global_metadata_transform_probe import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = root / "round167.json"
            output_path = root / "metadata-probe.yaml"
            self._write_input(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_global_metadata_transform_probe",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "global-metadata-transform-probe-round64",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.global_metadata_transform_probe.v1")
        self.assertEqual(data["source_id"], "global-metadata-transform-probe-round64")
        self.assertFalse(data["route_conclusion"]["plaintext_metadata_recovered"])
        self.assertEqual(summary["transform_candidate_count"], 1314)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
