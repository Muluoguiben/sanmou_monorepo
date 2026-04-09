from pathlib import Path
import tempfile
import unittest

from pydantic import ValidationError

from qa_agent.ingestion.loader import load_raw_batch
from qa_agent.ingestion.models import ReviewStatus
from qa_agent.knowledge.loader import load_entries_from_file
from qa_agent.knowledge.models import EntryKind, KnowledgeEntry
from qa_agent.knowledge.source_paths import discover_source_paths


class LoaderTests(unittest.TestCase):
    def test_load_entries_from_file(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        entries = load_entries_from_file(project_root / "knowledge_sources" / "building.yaml")
        self.assertGreaterEqual(len(entries), 2)
        self.assertEqual(entries[0].domain.value, "building")

    def test_schema_validation_rejects_missing_required_field(self) -> None:
        with self.assertRaises(ValidationError):
            KnowledgeEntry.model_validate(
                {
                    "id": "broken-entry",
                    "domain": "building",
                    "topic": "坏条目",
                    "aliases": [],
                    "facts": ["缺少 source_ref"],
                    "constraints": [],
                    "source_type": "manual_rule",
                    "updated_at": "2026-03-29",
                    "confidence": 0.9,
                }
            )

    def test_invalid_yaml_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "bad.yaml"
            path.write_text("topic: bad", encoding="utf-8")
            with self.assertRaises(ValueError):
                load_entries_from_file(path)

    def test_structured_hero_template_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        entries = load_entries_from_file(project_root / "examples" / "batch_hero_profiles.example.yaml")
        self.assertEqual(entries[0].entry_kind, EntryKind.HERO_PROFILE)
        self.assertEqual(entries[0].structured_data.name, "待录入武将")
        self.assertIn("模板武将别名", entries[0].searchable_terms())

    def test_structured_skill_template_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        entries = load_entries_from_file(project_root / "examples" / "batch_skill_profiles.example.yaml")
        self.assertEqual(entries[0].entry_kind, EntryKind.SKILL_PROFILE)
        self.assertEqual(entries[0].structured_data.name, "待录入战法")
        self.assertIn("模板战法别名", entries[0].searchable_terms())

    def test_structured_status_template_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        entries = load_entries_from_file(project_root / "examples" / "status_profile.example.yaml")
        self.assertEqual(entries[0].entry_kind, EntryKind.STATUS_PROFILE)
        self.assertEqual(entries[0].structured_data.name, "待录入状态")
        self.assertIn("模板状态别名", entries[0].searchable_terms())

    def test_structured_lineup_template_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        entries = load_entries_from_file(project_root / "examples" / "lineup_solution.example.yaml")
        self.assertEqual(entries[0].entry_kind, EntryKind.LINEUP_SOLUTION)
        self.assertEqual(entries[0].structured_data.name, "待录入阵容")
        self.assertIn("模板阵容别名", entries[0].searchable_terms())

    def test_hero_profile_requires_hero_structured_payload(self) -> None:
        with self.assertRaises(ValidationError):
            KnowledgeEntry.model_validate(
                {
                    "id": "bad-hero-profile",
                    "domain": "hero",
                    "entry_kind": "hero_profile",
                    "topic": "错误武将资料",
                    "aliases": [],
                    "facts": ["测试"],
                    "constraints": [],
                    "source_type": "manual_rule",
                    "source_ref": "BAD-001",
                    "updated_at": "2026-03-29",
                    "confidence": 0.9,
                }
            )

    def test_recursive_source_discovery_includes_profile_buckets(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        paths = discover_source_paths(project_root / "knowledge_sources")
        path_strings = {str(path.relative_to(project_root)).replace("\\", "/") for path in paths}
        self.assertIn("knowledge_sources/profiles/heroes/wei.yaml", path_strings)
        self.assertIn("knowledge_sources/profiles/skills/active.yaml", path_strings)
        self.assertIn("knowledge_sources/profiles/heroes/registry.yaml", path_strings)
        self.assertIn("knowledge_sources/glossary/statuses/registry.yaml", path_strings)
        self.assertIn("knowledge_sources/solutions/lineups/registry.yaml", path_strings)

    def test_raw_hero_batch_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_raw_batch(project_root / "ingestion" / "raw" / "heroes" / "sgmdtx-golden-sample.yaml")
        self.assertEqual(document.domain.value, "hero")
        self.assertEqual(len(document.records), 2)

    def test_raw_skill_batch_loads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        document = load_raw_batch(project_root / "ingestion" / "raw" / "skills" / "sgmdtx-golden-sample.yaml")
        self.assertEqual(document.domain.value, "skill")
        self.assertEqual(len(document.records), 2)


if __name__ == "__main__":
    unittest.main()
