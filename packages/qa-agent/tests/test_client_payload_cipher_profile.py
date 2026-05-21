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

from qa_agent.ingestion.client_payload_cipher_profile import (
    build_luascripts_payload_cipher_profile_report,
)


class ClientPayloadCipherProfileTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "luascripts_payload_cipher_profile_round162.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 162,
                    "slice": "luascripts_payload_cipher_profile",
                    "source_id": "luascripts-payload-cipher-profile-round162",
                    "source_url": "local-nslg-client-luascripts-cipher-profile",
                    "source_site": "nslg_client_luascripts_cipher_profile",
                    "input_artifacts": [
                        {"file_name": "luascripts_payload_targets_round31.json", "sha256": "a" * 64}
                    ],
                    "catalog_summary": {"relevant_record_count": 104, "unique_stem_count": 16},
                    "payload_profile_count": 1,
                    "payload_status_counts": {"high_entropy_16byte_aligned": 1},
                    "payload_profiles": [
                        {
                            "file_name": "heros.bytes.bin",
                            "stem": "heros",
                            "asset_path": "Assets/Bundles/LuaScripts/Data/heros.bytes",
                            "size_bytes": 23232,
                            "size_mod_16": 0,
                            "sha1": "b" * 40,
                            "sha256": "c" * 64,
                            "entropy": 7.99,
                            "printable_score": 0.37,
                            "block_count_16": 1452,
                            "duplicate_16byte_blocks": 0,
                            "unique_16byte_blocks": 1452,
                            "compression_magic": "none",
                            "best_single_byte_xor": {
                                "key_hex": "00",
                                "printable_score": 0.4,
                                "term_hits": 0,
                            },
                            "direct_term_hits": {},
                            "status": "high_entropy_16byte_aligned",
                        }
                    ],
                    "cross_file_block_profile": {
                        "cross_file_shared_16byte_block_count": 0,
                        "duplicate_first_block_count": 0,
                    },
                    "simple_transform_summary": {
                        "payload_count": 1,
                        "all_sizes_16byte_aligned": True,
                        "decompression_successes": [],
                        "direct_plaintext_term_file_count": 0,
                    },
                    "xor_crib_probe_summary": {
                        "single_byte_xor_plaintext_like_count": 0,
                        "crib_xor_plaintext_like_count": 0,
                    },
                    "route_conclusion": {
                        "lua_payload_decoder_recovered": False,
                        "simple_compression_ruled_out": True,
                        "single_byte_or_crib_xor_ruled_out": True,
                        "ecb_like_shared_block_signal": False,
                        "safe_for_publish": False,
                    },
                    "next_decoder_targets": ["locate native buffer owner"],
                    "limitations": ["static payload analysis only"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_payload_profile_not_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_luascripts_payload_cipher_profile_report(
                input_path=input_path,
                source_id="fixture-cipher-profile",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.luascripts_payload_cipher_profile.v1")
        self.assertEqual(report.source_id, "fixture-cipher-profile")
        self.assertEqual(report.payload_profile_count, 1)
        self.assertEqual(report.payload_status_counts["high_entropy_16byte_aligned"], 1)
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertFalse(report.route_conclusion["lua_payload_decoder_recovered"])
        self.assertEqual(
            report.evidence_refs[0],
            "NSLG_LUASCRIPT_CIPHER_PROFILE:fixture-cipher-profile:payload:heros.bytes.bin",
        )
        self.assertTrue(
            all(not artifact["file_name"].startswith("/") for artifact in report.input_artifacts)
        )

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_luascripts_payload_cipher_profile import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "cipher-profile.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_luascripts_payload_cipher_profile",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-cipher-profile",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.luascripts_payload_cipher_profile.v1")
        self.assertEqual(data["source_id"], "fixture-cipher-profile")
        self.assertEqual(data["payload_profile_count"], 1)
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
