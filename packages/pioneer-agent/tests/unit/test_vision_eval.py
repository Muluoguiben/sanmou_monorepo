from __future__ import annotations

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from pioneer_agent.perception import vision_eval
from pioneer_agent.perception.vision_eval import (
    VisionEvalFixtureError,
    run_vision_eval_fixture,
)


FIXTURE = Path(__file__).resolve().parents[1] / "fixtures" / "vision" / "team_snapshot_mobile_20260514.json"
INVENTORY = FIXTURE.with_name("map_battle_real_fixture_inventory.json")
REVIEW_REGISTRY = FIXTURE.with_name("real_screenshot_review_registry.json")


class VisionEvalTests(unittest.TestCase):
    def test_team_snapshot_fixture_reports_perfect_offline_baseline(self) -> None:
        summary = run_vision_eval_fixture(FIXTURE)

        report = summary.to_report()
        self.assertEqual(report["evaluation_mode"], "fixture_payload_replay")
        self.assertFalse(report["image_model_exercised"])
        self.assertEqual(report["payload_review_status"], "not_verified")
        self.assertEqual(report["artifact_review_status"], "registry_approved")
        self.assertEqual(report["screenshot_count"], 5)
        self.assertEqual(report["entity_check_count"], 9)
        self.assertEqual(report["verified_artifact_count"], 5)
        self.assertEqual(report["page_accuracy"], 1.0)
        self.assertEqual(report["domain_accuracy"], 1.0)
        self.assertEqual(report["entity_accuracy"], 1.0)
        self.assertEqual(report["failed_screenshots"], [])
        self.assertEqual(report["failed_entities"], [])

    def test_v2_real_fixture_rejects_unapproved_tampered_or_escaping_artifacts(self) -> None:
        cases = (
            ("legacy_schema", {"schema_version": 1}),
            ("empty_screenshot_set", {"include_screenshot": False}),
            ("privacy", {"privacy_status": "rejected"}),
            ("visible_names", {"player_names_visible": True}),
            ("sha256", {"sha256": "0" * 64}),
            ("path", {"image": "../outside.png"}),
            ("registry_denied", {"registry_decision": "denied"}),
        )
        for label, overrides in cases:
            with self.subTest(label=label), tempfile.TemporaryDirectory() as tmp:
                fixture_path = _write_minimal_v2_fixture(Path(tmp), **overrides)
                registry_path = fixture_path.with_name(
                    "real_screenshot_review_registry.json"
                )
                with patch.object(
                    vision_eval, "_CANONICAL_REVIEW_REGISTRY", registry_path
                ), self.assertRaises(VisionEvalFixtureError):
                    run_vision_eval_fixture(fixture_path)

    def test_map_and_battle_inventory_keeps_unreviewed_sources_blocked(self) -> None:
        inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
        map_gap = inventory["domain_gaps"]["map_land"]
        self.assertEqual(map_gap["status"], "blocked_privacy_review")
        self.assertFalse(
            map_gap["privacy_review"]["approved_for_eval_fixture"]
        )
        candidate_path = FIXTURE.parent.parent / map_gap["candidate"]["image"]
        self.assertEqual(
            hashlib.sha256(candidate_path.read_bytes()).hexdigest(),
            map_gap["candidate"]["sha256"],
        )
        registry = json.loads(REVIEW_REGISTRY.read_text(encoding="utf-8"))
        self.assertIn(map_gap["candidate"]["sha256"], registry["denied"])
        self.assertNotIn(map_gap["candidate"]["sha256"], registry["approved"])
        with tempfile.TemporaryDirectory() as tmp:
            rogue_fixture = _write_minimal_v2_fixture(
                Path(tmp), source_image=candidate_path
            )
            with self.assertRaisesRegex(
                VisionEvalFixtureError, "denied by the review registry"
            ):
                run_vision_eval_fixture(rogue_fixture)
        battle_gap = inventory["domain_gaps"]["battle_report"]
        self.assertEqual(battle_gap["status"], "missing_real_screenshot")
        self.assertIsNone(battle_gap["candidate"])


def _write_minimal_v2_fixture(
    root: Path,
    *,
    privacy_status: str = "approved",
    player_names_visible: bool = False,
    sha256: str | None = None,
    image: str = "shot.png",
    schema_version: int = 2,
    include_screenshot: bool = True,
    registry_decision: str = "approved",
    source_image: Path | None = None,
) -> Path:
    fixture_dir = root / "vision"
    fixture_dir.mkdir()
    image_path = root / "shot.png"
    if source_image is None:
        Image.new("RGB", (4, 3), (0, 0, 0)).save(image_path)
    else:
        shutil.copyfile(source_image, image_path)
    with Image.open(image_path) as image_file:
        width, height = image_file.size
    actual_sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
    privacy_review = {
        "status": privacy_status,
        "reviewed_by": "test-reviewer",
        "reviewed_at": "2026-07-10T12:00:00+08:00",
        "account_identifiers_visible": False,
        "chat_visible": False,
        "player_or_alliance_names_visible": player_names_visible,
        "payment_data_visible": False,
        "precise_coordinates_visible": False,
        "approved_for_repo_storage": privacy_status == "approved",
    }
    shot = {
        "id": "shot",
        "image": image,
        "captured_at": "2026-07-10T12:00:00+08:00",
        "expected_domains": ["resource_bar"],
        "artifact": {
            "review_status": "reviewed",
            "sha256": sha256 or actual_sha,
            "width": width,
            "height": height,
            "privacy_review": privacy_review,
        },
        "payloads": [
            {
                "domain": "resource_bar",
                "data": {
                    "page_type": "unknown",
                    "resources": {},
                    "visible_notes": [],
                },
            }
        ],
    }
    payload = {
        "schema_version": schema_version,
        "source": {"kind": "real_screenshot_set"},
        "screenshots": [shot] if include_screenshot else [],
    }
    registry = {
        "schema_version": 1,
        "approved": {},
        "denied": {},
    }
    if registry_decision == "approved":
        registry["approved"][actual_sha] = {
            "width": width,
            "height": height,
            "privacy_review": privacy_review,
        }
    elif registry_decision == "denied":
        registry["denied"][actual_sha] = {"allowed_for_eval": False}
    else:
        raise AssertionError(f"unsupported registry decision: {registry_decision}")
    (fixture_dir / "real_screenshot_review_registry.json").write_text(
        json.dumps(registry), encoding="utf-8"
    )
    fixture_path = fixture_dir / "fixture.json"
    fixture_path.write_text(json.dumps(payload), encoding="utf-8")
    return fixture_path


if __name__ == "__main__":
    unittest.main()
