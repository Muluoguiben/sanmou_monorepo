from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.ingestion.client_decoded import (
    ClientDecodedMappings,
    ClientNameMapping,
    load_client_decoded_mappings,
    load_decoded_hero_export,
    stage_decoded_heroes,
)
from qa_agent.ingestion.client_decoded_audit import build_client_decoded_audit_report
from qa_agent.ingestion.loader import load_staging_entries
from qa_agent.ingestion.models import ReviewStatus
from qa_agent.knowledge.models import Domain, EntryKind, HeroStaticProfile, KnowledgeEntry, SkillStaticProfile


class ClientDecodedHeroTests(unittest.TestCase):
    def _write_export(self, path: Path) -> None:
        path.write_text(
            json.dumps(
                {
                    "summary": "test decoded export",
                    "counts": {"total_export_records": 2},
                    "field_semantics": {
                        "lineup.skillSlots": "decoded skill slot semantics",
                        "gvg.warBook.warBookProfileId": "decoded warbook profile id",
                    },
                    "known_limitations": ["ids require review"],
                    "heroes": [
                        {
                            "heroID": 1000,
                            "baseCodename": "caocao",
                            "faction": "wei",
                            "variants": ["caocao", "caocao_gch"],
                            "inStaticMaster": True,
                            "currentRoster": {"uniqueId": 72, "heroID": 1000, "heroTroop": 11000},
                            "lineupDecoded": True,
                            "lineup": {
                                "evolutionLevel": 5,
                                "skillSlots": [
                                    {"position": 1, "skillId": 100001, "orderLevel": 4, "level": 10}
                                ],
                                "attrNonzeroSlots": [],
                            },
                            "gvg": {
                                "present": True,
                                "skillList": [
                                    {"skillId": 100001, "orderLevel": 4},
                                    {"skillId": 20890, "orderLevel": 5},
                                ],
                                "attrNonzeroSlots": [{"slot": 2, "value": 100}],
                                "warBook": {"warBookProfileId": 208023},
                            },
                        },
                        {
                            "heroID": 9999,
                            "baseCodename": "local_only",
                            "faction": "other",
                            "variants": [],
                            "inStaticMaster": False,
                        },
                    ],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    def test_stage_decoded_heroes_sanitizes_account_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "hero_export.json"
            self._write_export(input_path)
            export = load_decoded_hero_export(input_path)
            entries = stage_decoded_heroes(export, source_id="fixture-round")

        self.assertEqual(len(entries), 1)
        staged = entries[0]
        self.assertEqual(staged.metadata.review_status, ReviewStatus.NORMALIZED)
        self.assertEqual(staged.entry.topic, "caocao")
        self.assertEqual(staged.entry.structured_data.faction, "魏")
        self.assertEqual(staged.entry.structured_data.signature_skills[:2], ["100001", "20890"])
        dumped = json.dumps(staged.model_dump(mode="json"), ensure_ascii=False)
        self.assertIn("NSLG_CLIENT_DECODED:fixture-round:heroID=1000", dumped)
        self.assertIn("decoded_warbook_profile_id=208023", dumped)
        self.assertNotIn("uniqueId", dumped)
        self.assertNotIn("heroTroop", dumped)
        self.assertNotIn("11000", dumped)

    def test_stage_decoded_heroes_applies_optional_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "hero_export.json"
            self._write_export(input_path)
            export = load_decoded_hero_export(input_path)
            mappings = ClientDecodedMappings(
                heroes={"1000": ClientNameMapping(canonical_name="曹操", confidence=0.95)},
                skills={
                    "100001": ClientNameMapping(canonical_name="乱世奸雄", confidence=0.9),
                    "20890": ClientNameMapping(canonical_name="测试战法", confidence=0.5),
                },
            )
            entries = stage_decoded_heroes(export, source_id="fixture-round", mappings=mappings)

        staged = entries[0]
        self.assertEqual(staged.entry.topic, "曹操")
        self.assertIn("caocao", staged.entry.aliases)
        self.assertEqual(staged.entry.structured_data.signature_skills[:2], ["乱世奸雄", "测试战法"])
        self.assertIn("映射到 KB 武将 曹操", staged.entry.facts[0])

    def test_cli_writes_loadable_normalized_staging(self) -> None:
        from qa_agent.app.stage_client_decoded_heroes import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            input_path = tmp / "hero_export.json"
            output_path = tmp / "staging.yaml"
            self._write_export(input_path)
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "stage_client_decoded_heroes",
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
            staged = load_staging_entries(output_path)

        self.assertEqual(len(data), 1)
        self.assertEqual(len(staged), 1)
        self.assertIn('"staged_entries": 1', stdout.getvalue())
        self.assertEqual(staged[0].metadata.source_site, "nslg_client_decode")

    def test_cli_accepts_mapping_file(self) -> None:
        from qa_agent.app.stage_client_decoded_heroes import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            input_path = tmp / "hero_export.json"
            mapping_path = tmp / "mappings.yaml"
            output_path = tmp / "staging.yaml"
            self._write_export(input_path)
            mapping_path.write_text(
                yaml.safe_dump(
                    {
                        "heroes": {"1000": {"canonical_name": "曹操", "confidence": 0.95}},
                        "skills": {"100001": {"canonical_name": "乱世奸雄", "confidence": 0.9}},
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            loaded = load_client_decoded_mappings(mapping_path)
            self.assertEqual(loaded.hero(1000).canonical_name, "曹操")
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "stage_client_decoded_heroes",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-round",
                    "--mappings",
                    str(mapping_path),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            staged = load_staging_entries(output_path)

        self.assertEqual(staged[0].entry.topic, "曹操")
        self.assertIn(str(mapping_path), stdout.getvalue())

    def test_audit_report_tracks_mapping_review_and_sanitization(self) -> None:
        with tempfile.TemporaryDirectory() as raw_tmp:
            input_path = Path(raw_tmp) / "hero_export.json"
            self._write_export(input_path)
            export = load_decoded_hero_export(input_path)
            mappings = ClientDecodedMappings(
                heroes={"1000": ClientNameMapping(canonical_name="曹操", confidence=0.95)},
                skills={"100001": ClientNameMapping(canonical_name="乱世奸雄", confidence=0.9)},
            )
            knowledge_entries = [
                KnowledgeEntry(
                    id="hero-caocao",
                    domain=Domain.HERO,
                    entry_kind=EntryKind.HERO_PROFILE,
                    topic="曹操",
                    facts=["fixture"],
                    source_ref="fixture",
                    updated_at=date(2026, 1, 1),
                    confidence=0.9,
                    structured_data=HeroStaticProfile(name="曹操", signature_skills=["乱世奸雄"]),
                ),
                KnowledgeEntry(
                    id="skill-luanshijianxiong",
                    domain=Domain.SKILL,
                    entry_kind=EntryKind.SKILL_PROFILE,
                    topic="乱世奸雄",
                    facts=["fixture"],
                    source_ref="fixture",
                    updated_at=date(2026, 1, 1),
                    confidence=0.9,
                    structured_data=SkillStaticProfile(name="乱世奸雄"),
                ),
            ]
            report = build_client_decoded_audit_report(
                export,
                source_id="fixture-round",
                mappings=mappings,
                knowledge_entries=knowledge_entries,
                generated_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
            )

        self.assertEqual(report.staging["candidate_entries"], 1)
        self.assertEqual(report.staging["publish_default"], "blocked_until_reviewed")
        self.assertEqual(report.hero_coverage["mapped_heroes"], 1)
        self.assertEqual(report.hero_coverage["unmapped_heroes"], [])
        self.assertEqual(report.skill_coverage["unmapped_skill_ids"], [20890])
        self.assertEqual(report.knowledge_validation["hero_mappings_missing_kb_topic"], [])
        self.assertEqual(report.knowledge_validation["skill_mappings_missing_skill_profile"], [])
        self.assertEqual(report.security_scan["sensitive_markers_found"], [])
        self.assertIn("NSLG_CLIENT_DECODED:fixture-round:heroID=1000", report.evidence_refs)
        self.assertTrue(any("decoded skill ids" in blocker for blocker in report.review_blockers))

    def test_audit_cli_writes_yaml_report(self) -> None:
        from qa_agent.app.audit_client_decoded_heroes import main

        with tempfile.TemporaryDirectory() as raw_tmp:
            tmp = Path(raw_tmp)
            input_path = tmp / "hero_export.json"
            mapping_path = tmp / "mappings.yaml"
            output_path = tmp / "audit.yaml"
            self._write_export(input_path)
            mapping_path.write_text(
                yaml.safe_dump(
                    {
                        "heroes": {"1000": {"canonical_name": "曹操", "confidence": 0.95}},
                        "skills": {"100001": {"canonical_name": "乱世奸雄", "confidence": 0.9}},
                    },
                    allow_unicode=True,
                    sort_keys=False,
                ),
                encoding="utf-8",
            )
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "audit_client_decoded_heroes",
                    "--input",
                    str(input_path),
                    "--output",
                    str(output_path),
                    "--source-id",
                    "fixture-round",
                    "--mappings",
                    str(mapping_path),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            summary = json.loads(stdout.getvalue())

        self.assertEqual(data["source_id"], "fixture-round")
        self.assertEqual(data["staging"]["candidate_entries"], 1)
        self.assertEqual(summary["candidate_entries"], 1)
        self.assertEqual(summary["security_hits"], 0)


if __name__ == "__main__":
    unittest.main()
