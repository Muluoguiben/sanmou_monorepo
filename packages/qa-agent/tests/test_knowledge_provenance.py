from __future__ import annotations

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import yaml
from pydantic import ValidationError

from qa_agent.app.knowledge_inventory import build_inventory, main
from qa_agent.knowledge.models import KnowledgeEntry
from qa_agent.knowledge.provenance import (
    KnowledgeProvenance, audit_imports, content_digest, entry_digest, load_provenance_json,
)

PACKAGE = Path(__file__).resolve().parents[1]
FIXTURE = PACKAGE / "tests/fixtures/knowledge_provenance_v1/synthetic_records.json"


def example(index: int = 0) -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))[index]


def legacy_entry() -> dict:
    return {"id": "synthetic-legacy", "domain": "building", "topic": "合成建筑",
            "facts": ["仅供测试"], "source_type": "manual_rule", "source_ref": "TEST",
            "updated_at": "2026-10-23", "confidence": 0.8}


class KnowledgeProvenanceTests(unittest.TestCase):
    def test_three_explicit_synthetic_sources_have_no_authority(self):
        records = load_provenance_json(FIXTURE.read_text(encoding="utf-8"))
        self.assertEqual({r.source.category.value for r in records}, {"basic_knowledge", "rea_export", "player_guide"})
        for record in records:
            self.assertTrue(record.synthetic)
            self.assertEqual(record.review.status, "unreviewed")
            self.assertFalse(record.knowledge_publishable)
            self.assertFalse(record.human_gold)
            self.assertEqual(record.execution_authority, "none")
            self.assertEqual(record, KnowledgeProvenance.model_validate_json(record.model_dump_json()))

    def test_missing_unknown_reason_is_rejected(self):
        for section, field in [("source", "revision"), ("source", "original_sha256")]:
            value = example()
            value[section][field] = None
            with self.assertRaises(ValidationError):
                KnowledgeProvenance.model_validate(value)
        value = example()
        value["applicability"].pop("unknown_reason")
        with self.assertRaises(ValidationError):
            KnowledgeProvenance.model_validate(value)

    def test_exact_hash_detects_text_change_and_unicode_difference(self):
        value = example()
        value["content"] += " "
        with self.assertRaises(ValidationError):
            KnowledgeProvenance.model_validate(value)
        self.assertNotEqual(content_digest("é"), content_digest("e\u0301"))

    def test_unknown_protocol_fields_and_authority_are_rejected(self):
        for key, value in [("protocol", "knowledge-provenance-v2"), ("human_gold", True),
                           ("human_gold", 0), ("knowledge_publishable", True),
                           ("execution_authority", "game"), ("unexpected", 1)]:
            raw = example()
            raw[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                KnowledgeProvenance.model_validate(raw)

    def test_duplicate_json_keys_cannot_hide_metadata(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON key"):
            load_provenance_json('[{"human_gold":true,"human_gold":false}]')

    def test_reviewed_is_declared_metadata_not_gold_or_publish_permission(self):
        value = example()
        value["nature"] = "confirmed_rule"
        with self.assertRaises(ValidationError):
            KnowledgeProvenance.model_validate(value)
        value["review"] = {"status": "reviewed", "reviewer": "synthetic-reviewer",
                           "reviewed_at": "2026-10-23T00:00:00Z"}
        record = KnowledgeProvenance.model_validate(value)
        self.assertFalse(record.human_gold)
        self.assertFalse(record.knowledge_publishable)
        value["review"]["reviewed_at"] = "2026-10-23T00:00:00"
        with self.assertRaises(ValidationError):
            KnowledgeProvenance.model_validate(value)

    def test_client_field_cannot_be_promoted_to_game_rule(self):
        value = example(1)
        value["nature"] = "confirmed_rule"
        value["review"] = {"status": "reviewed", "reviewer": "synthetic-reviewer",
                           "reviewed_at": "2026-10-23T00:00:00Z"}
        with self.assertRaises(ValidationError):
            KnowledgeProvenance.model_validate(value)

    def test_video_range_and_dates_are_checked(self):
        for start, end in [(20, 10), (float("nan"), 10), (None, 10), (-1, 2)]:
            value = example(2)
            value["location"].update(start_seconds=start, end_seconds=end)
            with self.subTest(start=start), self.assertRaises(ValidationError):
                KnowledgeProvenance.model_validate(value)
        value = example()
        value["applicability"].update(valid_from="2026-10-24", valid_until="2026-10-23")
        with self.assertRaises(ValidationError):
            KnowledgeProvenance.model_validate(value)

    def test_exact_reimports_are_idempotent(self):
        record = KnowledgeProvenance.model_validate(example())
        report = audit_imports([record, record, record])
        self.assertEqual(len(report.records), 1)
        self.assertEqual(report.exact_duplicates, 2)
        self.assertFalse(report.conflicts)

    def test_same_identity_changed_content_preserves_conflicting_variants(self):
        old = KnowledgeProvenance.model_validate(example())
        value = example()
        value["content"] = "合成相反说法：条件乙不需要。"
        value["content_sha256"] = content_digest(value["content"])
        new = KnowledgeProvenance.model_validate(value)
        report = audit_imports([old, new, old])
        self.assertEqual(len(report.records), 2)
        self.assertEqual(len(report.conflicts), 1)
        self.assertEqual(report.exact_duplicates, 1)
        self.assertEqual(audit_imports([new, old, old]), report)

    def test_same_name_different_entity_and_revisions_keep_separate_identity(self):
        value = example()
        original = KnowledgeProvenance.model_validate(value)
        value["entity_id"] = "different-object"
        other = KnowledgeProvenance.model_validate(value)
        self.assertNotEqual(original.import_identity, other.import_identity)
        value = example()
        value["source"]["revision"] = "synthetic-r2"
        revised = KnowledgeProvenance.model_validate(value)
        self.assertNotEqual(original.import_identity, revised.import_identity)
        self.assertFalse(audit_imports([original, other, revised]).conflicts)

    def test_document_revision_hash_conflict_survives_different_excerpt_identity(self):
        original = KnowledgeProvenance.model_validate(example())
        value = example()
        value["location"]["reference"] = "/0/facts/1"
        value["entity_id"] = "different-entity"
        value["source"]["original_sha256"] = "a" * 64
        other = KnowledgeProvenance.model_validate(value)
        report = audit_imports([original, other])
        self.assertNotEqual(original.import_identity, other.import_identity)
        self.assertEqual(len(report.records), 2)
        self.assertEqual([item.reason for item in report.conflicts], ["same_document_revision_different_original_hash"])
        value["source"]["revision"] = "synthetic-r2"
        self.assertFalse(audit_imports([original, KnowledgeProvenance.model_validate(value)]).conflicts)

    def test_legacy_binding_requires_id_and_exact_digest(self):
        value = example()
        value["legacy_entry_id"] = "synthetic-legacy"
        with self.assertRaises(ValidationError):
            KnowledgeProvenance.model_validate(value)
        value["legacy_entry_sha256"] = entry_digest(KnowledgeEntry.model_validate(legacy_entry()))
        self.assertEqual(KnowledgeProvenance.model_validate(value).legacy_entry_id, "synthetic-legacy")


class KnowledgeInventoryTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.root = Path(self.scratch.name)
        self.path = self.root / "source.yaml"
        self.path.write_text(yaml.safe_dump([legacy_entry()], allow_unicode=True), encoding="utf-8")

    def test_legacy_inventory_does_not_infer_review_or_source_category(self):
        before = self.path.read_bytes()
        report = build_inventory(self.root)
        self.assertEqual(report["entry_count"], 1)
        self.assertEqual(report["by_domain"], {"building": 1})
        self.assertEqual(report["entries_without_provenance"], 1)
        self.assertEqual(report["entries"][0]["source_categories"], [])
        self.assertEqual(report["entries"][0]["gaps"], ["provenance_not_recorded"])
        self.assertEqual(report["source_manifest"][0]["sha256"], hashlib.sha256(before).hexdigest())
        self.assertEqual(self.path.read_bytes(), before)
        self.assertEqual(report, build_inventory(self.root))

    def bound_record(self):
        value = example()
        value.update(synthetic=False, legacy_entry_id="synthetic-legacy",
                     legacy_entry_sha256=entry_digest(KnowledgeEntry.model_validate(legacy_entry())))
        return KnowledgeProvenance.model_validate(value)

    def test_bound_provenance_reports_unknowns_without_promoting_review(self):
        report = build_inventory(self.root, [self.bound_record()])
        self.assertEqual(report["entries_with_provenance"], 1)
        self.assertIn("game_version_unknown", report["entries"][0]["gaps"])
        self.assertIn("review_not_declared", report["entries"][0]["gaps"])
        self.assertFalse(report["review_identity_authenticated"])
        self.assertFalse(report["knowledge_publishable"])

    def test_drifted_sidecar_fails_without_changing_source(self):
        record = self.bound_record()
        changed = legacy_entry()
        changed["facts"] = ["changed"]
        self.path.write_text(yaml.safe_dump([changed]), encoding="utf-8")
        before = self.path.read_bytes()
        with self.assertRaisesRegex(ValueError, "digest mismatch"):
            build_inventory(self.root, [record])
        self.assertEqual(self.path.read_bytes(), before)

    def test_synthetic_sidecar_cannot_count_as_formal_coverage(self):
        value = self.bound_record().model_dump(mode="json")
        value["synthetic"] = True
        with self.assertRaisesRegex(ValueError, "synthetic"):
            build_inventory(self.root, [KnowledgeProvenance.model_validate(value)])

    def test_duplicate_entry_and_symlinks_fail(self):
        self.path.write_text(yaml.safe_dump([legacy_entry(), legacy_entry()]), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "duplicate knowledge"):
            build_inventory(self.root)
        self.path.write_text(yaml.safe_dump([legacy_entry()]), encoding="utf-8")
        link = self.root / "linked.yaml"
        link.symlink_to(self.path)
        with self.assertRaisesRegex(ValueError, "symlink"):
            build_inventory(self.root)

    def test_cli_reads_formal_kb_and_writes_stdout_only(self):
        before = {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in (PACKAGE / "knowledge_sources").rglob("*.yaml")}
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch("socket.create_connection", side_effect=AssertionError("network forbidden")):
            self.assertEqual(main([]), 0)
        report = json.loads(output.getvalue())
        self.assertGreater(report["entry_count"], 0)
        self.assertEqual(report["entries_with_provenance"], 0)
        self.assertEqual(before, {p: hashlib.sha256(p.read_bytes()).hexdigest() for p in before})


if __name__ == "__main__":
    unittest.main()
