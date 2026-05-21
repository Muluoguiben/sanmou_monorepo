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

from qa_agent.ingestion.client_luascripts_variant_corpus import (
    build_luascripts_payload_variant_corpus_report,
)


class LuaScriptsVariantCorpusTests(unittest.TestCase):
    def _write_fixture(self, root: Path) -> Path:
        input_path = root / "luascripts_payload_variant_corpus_round172.json"
        input_path.write_text(
            json.dumps(
                {
                    "round": 172,
                    "slice": "luascripts_payload_variant_corpus_probe",
                    "input_artifacts": [
                        {
                            "file_name": "luascripts_textasset_extract_round31.json",
                            "size_bytes": 100,
                            "sha256": "a" * 64,
                        }
                    ],
                    "corpus_summary": {
                        "relevant_record_count": 104,
                        "payload_variant_count": 932,
                        "stem_count": 16,
                        "scenario_count": 23,
                        "all_sizes_16byte_aligned": True,
                        "unique_ciphertext_hash_count": 52,
                        "duplicate_ciphertext_hash_group_count": 40,
                        "offset_skip_decompression_success_count": 0,
                        "offset_skip_plaintext_hit_count": 0,
                    },
                    "stem_summaries": [
                        {
                            "stem": "heros",
                            "record_count": 1,
                            "variant_count": 1,
                            "unique_ciphertext_hash_count": 1,
                            "duplicate_ciphertext_hash_group_count": 0,
                            "duplicate_ciphertext_variant_count": 0,
                            "entropy_avg": 7.99,
                            "printable_score_4k_avg": 0.37,
                            "direct_plaintext_term_variant_count": 0,
                            "sample_scenarios": ["Scenario1"],
                            "sample_paths": [
                                "Assets/Bundles/LuaScripts/Data/Scenario1/heros.bytes"
                            ],
                        }
                    ],
                    "duplicate_ciphertext_groups": [
                        {
                            "sha256": "b" * 64,
                            "variant_count": 23,
                            "stems": ["hero_story"],
                            "script_lens": [2336],
                            "first_block_hex": "00" * 16,
                            "last_block_hex": "11" * 16,
                            "sample_refs": [
                                {
                                    "path": "Assets/Bundles/LuaScripts/Data/Scenario1/story/hero_story.bytes",
                                    "match_index": 0,
                                    "payload_offset": 123,
                                    "scenario": "Scenario1",
                                }
                            ],
                        }
                    ],
                    "block_sharing_summary": {
                        "unique_ciphertext_hash_count": 52,
                        "total_unique_16byte_blocks": 23361,
                        "cross_cipher_shared_16byte_block_count": 55,
                    },
                    "offset_skip_probe_summary": {
                        "skips_tested": [0, 16, 32],
                        "variant_count": 932,
                        "decompression_success_count": 0,
                        "plaintext_hit_count": 0,
                        "high_printable_candidate_count": 0,
                    },
                    "same_length_hamming_summary": [
                        {
                            "stem": "hero_story",
                            "script_len": 2336,
                            "variant_count": 230,
                            "unique_ciphertext_hash_count": 10,
                        }
                    ],
                    "prior_route_context": {
                        "round162_payload_profile_count": 16,
                        "round162_lua_payload_decoder_recovered": False,
                    },
                    "route_conclusion": {
                        "lua_payload_decoder_recovered": False,
                        "duplicate_ciphertext_present": True,
                        "simple_offset_skip_route_ruled_out": True,
                        "safe_for_publish": False,
                        "strongest_current_signal": "expanded corpus",
                        "strongest_negative_signal": "no plaintext layout",
                        "search_policy": "continue with native buffer owner tracing",
                    },
                    "next_decoder_targets": ["locate native buffer owner"],
                    "limitations": ["static payload corpus only"],
                    "evidence_refs": [
                        "NSLG_LUASCRIPT_VARIANT_CORPUS:round172:stem:heros"
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        return input_path

    def test_build_report_keeps_variant_corpus_non_publishable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            report = build_luascripts_payload_variant_corpus_report(
                input_path=input_path,
                source_id="fixture-variant-corpus",
                generated_at=datetime(2026, 5, 21, tzinfo=timezone.utc),
            )

        self.assertEqual(report.schema_version, "nslg.luascripts_payload_variant_corpus.v1")
        self.assertEqual(report.source_id, "fixture-variant-corpus")
        self.assertEqual(report.corpus_summary["payload_variant_count"], 932)
        self.assertEqual(report.stem_summaries[0].stem, "heros")
        self.assertFalse(report.route_conclusion["safe_for_publish"])
        self.assertTrue(report.route_conclusion["simple_offset_skip_route_ruled_out"])
        self.assertEqual(
            report.evidence_refs[0],
            "NSLG_LUASCRIPT_VARIANT_CORPUS:round172:stem:heros",
        )

    def test_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.summarize_luascripts_payload_variant_corpus import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            input_path = self._write_fixture(root)
            output_path = root / "variant-corpus.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_luascripts_payload_variant_corpus",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-variant-corpus",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["schema_version"], "nslg.luascripts_payload_variant_corpus.v1")
        self.assertEqual(data["source_id"], "fixture-variant-corpus")
        self.assertEqual(data["corpus_summary"]["payload_variant_count"], 932)
        self.assertTrue(summary["simple_offset_skip_route_ruled_out"])
        self.assertFalse(summary["safe_for_publish"])


if __name__ == "__main__":
    unittest.main()
