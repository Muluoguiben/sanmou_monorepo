from pathlib import Path
import io
import sys
import unittest
from unittest.mock import patch

from qa_agent.ingestion.config import load_alias_config, load_enum_config
from qa_agent.ingestion.loader import load_raw_batch
from qa_agent.ingestion.models import ReviewStatus
from qa_agent.ingestion.normalize import normalize_hero_record, normalize_skill_record


class IngestionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.project_root = Path(__file__).resolve().parents[1]
        cls.hero_aliases = load_alias_config(cls.project_root / "configs" / "hero_aliases.yaml")
        cls.skill_aliases = load_alias_config(cls.project_root / "configs" / "skill_aliases.yaml")
        cls.enums = load_enum_config(cls.project_root / "configs" / "enums.yaml")

    def test_normalize_hero_record_into_staging_entry(self) -> None:
        batch = load_raw_batch(self.project_root / "ingestion" / "raw" / "heroes" / "sgmdtx-golden-sample.yaml")
        staged = normalize_hero_record(batch.records[0], self.hero_aliases, self.enums)
        self.assertEqual(staged.entry.domain.value, "hero")
        self.assertEqual(staged.entry.topic, "诸葛亮")
        self.assertEqual(staged.metadata.review_status, ReviewStatus.NORMALIZED)
        self.assertEqual(staged.entry.structured_data.faction, "蜀")

    def test_normalize_skill_record_into_staging_entry(self) -> None:
        batch = load_raw_batch(self.project_root / "ingestion" / "raw" / "skills" / "sgmdtx-golden-sample.yaml")
        staged = normalize_skill_record(batch.records[1], self.skill_aliases, self.enums)
        self.assertEqual(staged.entry.domain.value, "skill")
        self.assertEqual(staged.entry.topic, "盛气凌敌")
        self.assertEqual(staged.entry.structured_data.trigger_type, "指挥")
        self.assertEqual(staged.metadata.review_status, ReviewStatus.NORMALIZED)

    def test_staging_metadata_does_not_appear_in_query_contract(self) -> None:
        batch = load_raw_batch(self.project_root / "ingestion" / "raw" / "heroes" / "sgmdtx-golden-sample.yaml")
        staged = normalize_hero_record(batch.records[0], self.hero_aliases, self.enums)
        dumped = staged.entry.model_dump(mode="json")
        self.assertNotIn("source_url", dumped)
        self.assertNotIn("review_status", dumped)

    def test_normalize_cli_accepts_project_relative_input(self) -> None:
        from qa_agent.app.normalize_ingestion import main

        stdout = io.StringIO()
        with patch.object(
            sys,
            "argv",
            [
                "normalize_ingestion",
                "--input",
                "ingestion/raw/heroes/sgmdtx-golden-sample.yaml",
            ],
        ):
            with patch("sys.stdout", stdout):
                main()
        self.assertIn("诸葛亮", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
