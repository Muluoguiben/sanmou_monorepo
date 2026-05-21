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

from qa_agent.ingestion.client_nep2_provenance import build_nep2_provenance_closure_batch


class Nep2ProvenanceClosureTests(unittest.TestCase):
    def _write_record(
        self,
        root: Path,
        *,
        round_number: int,
        rva: str,
        pointer_refs: list[dict] | None = None,
        strong_provenance: bool = False,
    ) -> None:
        name = f"nep2_{rva[2:]}_provenance_closure_round{round_number}.json"
        path = root / name
        path.write_text(
            json.dumps(
                {
                    "round": round_number,
                    "slice": f"NEP2 {rva} provenance closure",
                    "target": {
                        "rva": rva,
                        "function": {"begin": rva, "end": "0x2000", "size": "0x10"},
                        "direct_caller_count": 0,
                        "direct_callee_count": 0,
                    },
                    "selected_nodes": {"node_count": 1, "upstream_count": 1, "downstream_count": 1},
                    "target_inspected": {
                        "counts": {
                            "instructions": 10,
                            "memory_writes": 2,
                            "non_stack_writes": 1,
                        },
                        "verdict": "metadata/control helper; no current CAB transform proof",
                    },
                    "summary": [
                        "Inspected target plus caller depth 3 and callee depth 2.",
                        f"Strong provenance found: {str(strong_provenance)}.",
                    ],
                    "provenance": {
                        "interesting": [{"rva": "0x999"}] if strong_provenance else []
                    },
                    "paths": {
                        "downstream_to_signal": [{"path": ["a", "b"]}] if strong_provenance else [],
                        "upstream_from_signal": [],
                        "downstream_to_closed": [],
                        "upstream_from_closed": [],
                    },
                    "pointer_refs": pointer_refs or [],
                    "pointer_ref_classification": "internal_rdata_tables_no_asset_owner"
                    if pointer_refs
                    else "none",
                    "pointer_owner_signal_count": 0,
                    "interpretation": [
                        "No CAB/Serialized/global-metadata/AssetBundle/file-buffer provenance reaches target.",
                        "The function remains a shape-only byte/table/vector loop candidate, not a protector-quality lead.",
                    ],
                    "next": [
                        f"Mark NEP2 {rva} as closed: no caller/callee provenance.",
                        "Move to the next top shape-only lead only with caller/callee provenance.",
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (root / name.replace(".json", ".md")).write_text("summary", encoding="utf-8")
        (root / name.replace(".json", ".asm")).write_text("; asm", encoding="utf-8")

    def test_batch_summarizes_closed_rvas_and_next_target_without_paths(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_record(root, round_number=137, rva="0x620670", pointer_refs=[{"section": ".rdata"}])
            self._write_record(root, round_number=138, rva="0x678a20")
            log_path = root / "nslg_local_data_analysis.md"
            log_path.write_text(
                "Next:\n"
                "- Continue with the next highest non-demoted NEP2 shape-only lead: `0x4a471a`.\n"
                "- If continuing NEP2, inspect the next unclosed shape-only lead, `0x4a28e9`, only under the strict provenance gate.\n",
                encoding="utf-8",
            )
            batch = build_nep2_provenance_closure_batch(
                input_dir=root,
                source_id="fixture-provenance",
                analysis_log_path=log_path,
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(batch.schema_version, "nslg.nep2_provenance_closure_batch.v1")
        self.assertEqual(batch.artifact_count, 2)
        self.assertEqual(batch.round_range, {"min": 137, "max": 138})
        self.assertEqual(batch.closure_status_counts["closed_no_file_buffer_provenance"], 2)
        self.assertEqual(batch.pointer_ref_classification_counts["internal_rdata_tables_no_asset_owner"], 1)
        self.assertEqual(batch.next_unclosed_shape_lead, "0x4a28e9")
        self.assertIn("0x620670", batch.closed_rvas)
        self.assertTrue(all("/" not in name for record in batch.records for name in record.artifact_files))
        self.assertFalse(batch.route_conclusion["safe_for_publish"])
        self.assertEqual(batch.route_conclusion["publishable_knowledge_entries"], 0)

    def test_strong_provenance_record_stays_needs_review(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_record(root, round_number=139, rva="0x5e6b10", strong_provenance=True)
            batch = build_nep2_provenance_closure_batch(
                input_dir=root,
                source_id="fixture-provenance",
                generated_at=datetime(2026, 5, 20, tzinfo=timezone.utc),
            )

        self.assertEqual(batch.records[0].closure_status, "needs_review_provenance_signal")
        self.assertEqual(batch.closure_status_counts["needs_review_provenance_signal"], 1)
        self.assertEqual(batch.closed_rvas, [])

    def test_cli_writes_yaml(self) -> None:
        from qa_agent.app.summarize_nep2_provenance_closures import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            root = Path(raw_tmp)
            self._write_record(root, round_number=137, rva="0x620670")
            log_path = root / "nslg_local_data_analysis.md"
            log_path.write_text(
                "Next:\n- If continuing NEP2, inspect the next unclosed shape-only lead, `0x4a28e9`.\n",
                encoding="utf-8",
            )
            output_path = root / "provenance.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "summarize_nep2_provenance_closures",
                    "--input-dir",
                    str(root),
                    "--analysis-log",
                    str(log_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-provenance",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["source_id"], "fixture-provenance")
        self.assertEqual(data["artifact_count"], 1)
        self.assertEqual(data["next_unclosed_shape_lead"], "0x4a28e9")
        self.assertFalse(data["route_conclusion"]["safe_for_publish"])
        self.assertEqual(summary["artifact_count"], 1)


if __name__ == "__main__":
    unittest.main()
