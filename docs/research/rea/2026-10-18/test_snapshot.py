"""Offline regression checks for this research snapshot, not game accuracy."""
import json
from pathlib import Path
import tempfile
import unittest

import snapshot

ROOT = Path(__file__).resolve().parent


def records(name):
    return snapshot.decode((ROOT / "data" / f"{name}.json").read_bytes())["records"]


class SnapshotTests(unittest.TestCase):
    def test_counts_and_unique_identities(self):
        for name, count in snapshot.COUNTS.items():
            rows = records(name)
            self.assertEqual(len(rows), count)
            key = {"heroes": "hero_id", "skills": "skill_id", "reports": "battle_id"}.get(name, "id")
            identities = [(r.get("category", r.get("kind")), r[key]) for r in rows]
            self.assertEqual(len(set(identities)), count)

    def test_public_snapshot_remains_pending(self):
        for name in snapshot.COUNTS:
            value = snapshot.decode((ROOT / "data" / f"{name}.json").read_bytes())
            self.assertEqual(value["review_state"], "pending_domain_review")
            self.assertIs(value["knowledge_publishable"], False)
            self.assertEqual(value["execution_authority"], "none")
            self.assertIs(value["executable"], False)
            snapshot.audit_public(value)

    def test_hero_variants_and_missing_references(self):
        heroes = {r["hero_id"]: r for r in records("heroes")}
        self.assertEqual(heroes[80]["name"], heroes[81]["name"])
        self.assertNotEqual(heroes[80]["hero_id"], heroes[81]["hero_id"])
        self.assertEqual(len(heroes[1000]["attributes"]), 7)
        self.assertEqual(heroes[1000]["annotations"]["season_eligibility"], "not_evaluated")
        self.assertIs(heroes[1006]["innate_skill"]["found"], False)
        self.assertEqual(heroes[1006]["innate_skill"]["reference_id"], 100601)
        self.assertEqual(heroes[3020]["innate_skill"]["reference_id"], 0)

    def test_all_nineteen_fate_conflicts_preserved(self):
        fates = {r["id"]: r for r in records("fates")}
        self.assertEqual(sum(bool(r["conflicts"]) for r in fates.values()), 19)
        self.assertIn("6%", fates[5]["data"]["description"])
        self.assertEqual(fates[5]["data"]["effect_value_one"], [0.05])
        self.assertEqual(fates[5]["conflicts"][0]["classification"], "unadjudicated_mismatch")

    def test_skill_launch_is_not_effect_probability(self):
        skill = next(r for r in records("skills") if r["skill_id"] == 301101)
        first = skill["levels"]["1"]
        self.assertEqual(first["launch_probability_percent"], "100%")
        self.assertIn("45%", first["description"])
        self.assertEqual(skill["annotations"]["availability"]["current_season_available"], "not_evaluated")

    def test_evolution_float_boundary_not_erased(self):
        skill = next(r for r in records("skills") if r["skill_id"] == 301101)
        checks = skill["evolution"]["orders"]["3"]["levels"]["7"]["display_checks"]
        self.assertTrue(any(not c["rational_agrees"] and c["display"] == "79.99"
                            and c["rational_display"] == "80" for c in checks))

    def test_gear_units_and_unknown_random_pool(self):
        gear = records("gear")
        item = next(r for r in gear if r["id"] == 2000010)
        self.assertEqual(item["main_attribute_range"], {"min": 3.6, "max": 11})
        affix = next(r for r in gear if r.get("kind") == "skill" and r["id"] == 100)
        self.assertEqual({v["weight"] for v in affix["variants"]}, {0, 100})
        self.assertTrue(all(v["ban_dianhua"] == 1 for v in affix["variants"]))
        self.assertIn("actual_obtainability", affix)

    def test_ui_observation_not_promoted_to_raw_event(self):
        row = next(r for r in records("mechanics") if r["id"] == "F023")
        self.assertEqual(row["event_references"], [])
        self.assertEqual(len(row["ui_references"]), 5)
        self.assertTrue(all(e["source_json_available"] is False for e in row["ui_references"]))
        self.assertTrue(all(e["raw_event_index_available"] is False for e in row["ui_references"]))
        self.assertIs(row["full_compound_rule_battle_verified"], False)

    def test_report_completeness_is_not_authentication(self):
        reports = records("reports")
        self.assertEqual(sum(r["event_count"] for r in reports), 4503)
        for row in reports:
            self.assertTrue(row["decode_complete"])
            self.assertFalse(row["real_battle_verified"])
            self.assertFalse(row["source_association_independently_authenticated"])
            self.assertFalse(row["complete_tcp_connection"])
            self.assertEqual(len(row["warnings"]), 5)
            self.assertEqual(row["terminal_event_name"], "BattleResult")
            self.assertFalse(row["raw_events_included"])

    def test_json_rejects_duplicate_and_nonfinite(self):
        for payload in (b'{"x":1,"x":2}', b'{"x":NaN}', b'{"x":Infinity}'):
            with self.assertRaises(ValueError):
                snapshot.decode(payload)

    def test_disclosure_guard(self):
        for value in ({"raw_payload": []}, {"teamId": 1}, {"note": "C:/private/example"}):
            with self.assertRaises(ValueError):
                snapshot.audit_public(value)

    def test_manifest_rejects_escape_before_read(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "MANIFEST.json").write_bytes(snapshot.encode({"files": [
                {"path": "../outside", "bytes": 0, "sha256": "0" * 64}]}))
            with self.assertRaisesRegex(ValueError, "unsafe"):
                snapshot.verify(root)

    def test_manifest_rejects_digest_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "x.txt").write_bytes(b"changed")
            (root / "MANIFEST.json").write_bytes(snapshot.encode({"files": [
                {"path": "x.txt", "bytes": 7, "sha256": "0" * 64}]}))
            with self.assertRaisesRegex(ValueError, "digest"):
                snapshot.verify(root)


if __name__ == "__main__":
    unittest.main()
