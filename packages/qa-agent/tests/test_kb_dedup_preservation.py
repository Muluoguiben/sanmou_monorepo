"""CR04: a record deletion must not reattach its trailing YAML to a neighbor.

The fixture hashes come from d377ef8, before the deduplication change. They
freeze every retained record, not just schema-valid fields or entry counts.
Future reviewed KB changes require a separate, evidence-backed baseline update.
"""
import hashlib
import json
import unittest
from pathlib import Path

import yaml


def semantic_digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class KbDedupPreservationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.package = Path(__file__).resolve().parents[1]
        cls.baseline = json.loads((cls.package / "tests/fixtures/qa_minor_dedup_baseline.json").read_text(encoding="utf-8"))
        cls.hero_dir = cls.package / "knowledge_sources/profiles/heroes"

    def test_minor_removes_only_duplicate_and_preserves_all_neighbors(self):
        entries = yaml.safe_load((self.hero_dir / "minor.yaml").read_text(encoding="utf-8"))
        self.assertEqual([entry["id"] for entry in entries], self.baseline["remaining_ids"])
        self.assertNotIn(self.baseline["removed_id"], [entry["id"] for entry in entries])
        for entry in entries:
            with self.subTest(entry_id=entry["id"]):
                self.assertEqual(semantic_digest(entry), self.baseline["remaining_entry_sha256"][entry["id"]])

    def test_retained_qun_bucket_is_semantically_unchanged(self):
        entries = yaml.safe_load((self.hero_dir / "qun.yaml").read_text(encoding="utf-8"))
        self.assertEqual(semantic_digest(entries), self.baseline["retained_qun_sha256"])
        self.assertEqual(sum(entry["id"] == self.baseline["removed_id"] for entry in entries), 1)


if __name__ == "__main__":
    unittest.main()
