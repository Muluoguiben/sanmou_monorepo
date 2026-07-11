from __future__ import annotations

import hashlib
import json
import unittest
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from PIL import Image

from pioneer_agent.perception.domains import extract_battle_report


FIXTURES = Path(__file__).resolve().parents[1] / "fixtures"
VISION = FIXTURES / "vision"
REGISTRY = VISION / "real_screenshot_review_registry.json"
BATTLE_FIXTURE = VISION / "battle_report_level5_pending_20260711.json"
ROI_MANIFEST = (
    FIXTURES
    / "screenshots"
    / "pc_client"
    / "live_20260711"
    / "occupation_level5_roi_manifest.json"
)

BEFORE_SOURCE_SHA = (
    "ccd97c670220805be589cf4127a0f20296779136384dc04ddc6164e7841b052f"
)
AFTER_SOURCE_SHA = (
    "52e6982017b83e6c1311fcd32e0f05aaec9fb9a45d99e3d5064de28bd0857b61"
)

ARTIFACTS: dict[str, dict[str, Any]] = {
    "screenshots/pc_client/live_20260711/battle_report_level5_pending_redacted.webp": {
        "sha256": "01a2818d472ac6ba372c6c8d3ad4688fee99da66f5c3f15680257084cf55d27c",
        "size": (1280, 663),
        "bytes": 42630,
        "source_capture_sha256": BEFORE_SOURCE_SHA,
        "transform": {
            "format": "webp",
            "quality": 45,
            "source_dimensions": [2560, 1326],
            "source_crop_rect": [0, 0, 2560, 1326],
            "source_redaction_rects": [[115, 105, 365, 255]],
            "resized_to": [1280, 663],
        },
        "redaction_applied": True,
    },
    "screenshots/pc_client/live_20260711/occupation_level5_target_before.webp": {
        "sha256": "d3a91d69ab7eb12cc8adf11a5ac516cd9ff3d75fc34cc691d036c2cbb0ceed6a",
        "size": (260, 405),
        "bytes": 15010,
        "source_capture_sha256": BEFORE_SOURCE_SHA,
        "transform": {
            "format": "webp",
            "quality": 50,
            "source_crop_rect": [1135, 475, 1395, 880],
            "final_redaction_rects": [[185, 275, 260, 405]],
        },
        "redaction_applied": True,
    },
    "screenshots/pc_client/live_20260711/occupation_level5_target_after.webp": {
        "sha256": "5e1aed86f9659d2e219d711d13fddec2bf615a7cc412812124c0cd3b2ac80efc",
        "size": (260, 405),
        "bytes": 14974,
        "source_capture_sha256": AFTER_SOURCE_SHA,
        "transform": {
            "format": "webp",
            "quality": 50,
            "source_crop_rect": [1135, 475, 1395, 880],
            "final_redaction_rects": [[185, 275, 260, 405]],
        },
        "redaction_applied": True,
    },
    "screenshots/pc_client/live_20260711/occupation_level5_territory_before.webp": {
        "sha256": "04900874c7e97e52a9a9440fd6d2c9a30eb11b35d1b806e48435fef8221b9d48",
        "size": (240, 105),
        "bytes": 2410,
        "source_capture_sha256": BEFORE_SOURCE_SHA,
        "transform": {
            "format": "webp",
            "quality": 50,
            "source_crop_rect": [445, 20, 685, 125],
            "final_redaction_rects": [],
        },
        "redaction_applied": False,
    },
    "screenshots/pc_client/live_20260711/occupation_level5_territory_after.webp": {
        "sha256": "600a4620073db16a551a7450d918a65a678127a9b2d44fcc5644600e3f6d39ef",
        "size": (240, 105),
        "bytes": 2420,
        "source_capture_sha256": AFTER_SOURCE_SHA,
        "transform": {
            "format": "webp",
            "quality": 50,
            "source_crop_rect": [445, 20, 685, 125],
            "final_redaction_rects": [],
        },
        "redaction_applied": False,
    },
}


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


class RealLevel5EvidenceFixtureTests(unittest.TestCase):
    def test_registry_locks_sha_dimensions_transforms_and_privacy(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        approved = registry["approved"]

        for relative_path, expected in ARTIFACTS.items():
            with self.subTest(path=relative_path):
                path = FIXTURES / relative_path
                image_bytes = path.read_bytes()
                actual_sha = hashlib.sha256(image_bytes).hexdigest()
                self.assertEqual(actual_sha, expected["sha256"])
                self.assertEqual(len(image_bytes), expected["bytes"])
                with Image.open(path) as image:
                    self.assertEqual(image.format, "WEBP")
                    self.assertEqual(image.size, expected["size"])
                    self.assertEqual(len(image.getexif()), 0)

                self.assertNotIn(actual_sha, registry["denied"])
                entry = approved[actual_sha]
                self.assertEqual(entry["known_path"], relative_path)
                self.assertEqual(
                    (entry["width"], entry["height"]),
                    expected["size"],
                )
                self.assertEqual(entry["bytes"], expected["bytes"])
                self.assertEqual(
                    entry["source_capture_sha256"],
                    expected["source_capture_sha256"],
                )
                self.assertEqual(entry["transform"], expected["transform"])
                crop = entry["transform"]["source_crop_rect"]
                if crop != [0, 0, 2560, 1326]:
                    self.assertEqual(
                        (crop[2] - crop[0], crop[3] - crop[1]),
                        expected["size"],
                    )
                for rect in entry["transform"].get(
                    "final_redaction_rects", []
                ):
                    self.assertGreaterEqual(rect[0], 0)
                    self.assertGreaterEqual(rect[1], 0)
                    self.assertLessEqual(rect[2], expected["size"][0])
                    self.assertLessEqual(rect[3], expected["size"][1])

                privacy = entry["privacy_review"]
                self.assertEqual(privacy["status"], "approved")
                self.assertEqual(
                    privacy["redaction_applied"],
                    expected["redaction_applied"],
                )
                self.assertTrue(privacy["approved_for_repo_storage"])
                self.assertTrue(privacy["reviewed_by"].strip())
                datetime.fromisoformat(privacy["reviewed_at"])
                for field in (
                    "account_identifiers_visible",
                    "chat_visible",
                    "player_or_alliance_names_visible",
                    "payment_data_visible",
                    "precise_coordinates_visible",
                ):
                    self.assertIs(privacy[field], False)

    def test_roi_manifest_locks_visible_transition_and_evidence_boundaries(self) -> None:
        manifest = json.loads(ROI_MANIFEST.read_text(encoding="utf-8"))
        classification = manifest["evidence_classification"]
        self.assertEqual(
            classification["artifact_kind"],
            "paired_real_screenshot_roi_evidence",
        )
        self.assertFalse(classification["action_correlated_live_trace"])
        self.assertFalse(classification["image_model_exercised"])
        self.assertFalse(classification["eligible_as_full_frame_map_fixture"])

        pairs = {pair["id"]: pair for pair in manifest["pairs"]}
        target = pairs["level5_target_state"]
        self.assertEqual(
            target["visible_transition"]["land_level"],
            {"before": 5, "after": 5},
        )
        self.assertEqual(
            target["visible_transition"]["occupation_countdown"],
            {"before": "02:35", "after": None},
        )
        self.assertEqual(
            target["visible_transition"]["occupation_pending"],
            {"before": True, "after": "not_visible"},
        )
        territory = pairs["territory_owned_count"]
        self.assertEqual(
            territory["visible_transition"]["territory_owned"],
            {"before": 54, "after": 55, "capacity": 60},
        )

        for pair in pairs.values():
            for phase in ("before", "after"):
                artifact = pair[phase]
                expected = ARTIFACTS[
                    "screenshots/pc_client/live_20260711/" + artifact["image"]
                ]
                self.assertEqual(artifact["sha256"], expected["sha256"])
                self.assertEqual(
                    (artifact["width"], artifact["height"]),
                    expected["size"],
                )
                self.assertEqual(artifact["bytes"], expected["bytes"])
                self.assertEqual(
                    artifact["source_capture_sha256"],
                    expected["source_capture_sha256"],
                )
                transform = expected["transform"]
                self.assertEqual(
                    artifact["crop"]["source_rect"],
                    transform["source_crop_rect"],
                )
                self.assertEqual(
                    artifact["encoding"],
                    {
                        "format": transform["format"],
                        "quality": transform["quality"],
                    },
                )
                expected_redactions = transform["final_redaction_rects"]
                self.assertEqual(
                    artifact["redaction"]["applied"],
                    bool(expected_redactions),
                )
                if expected_redactions:
                    self.assertEqual(
                        artifact["redaction"]["final_rects"],
                        expected_redactions,
                    )

        annotation = manifest["user_confirmed_annotations"]
        self.assertEqual(
            annotation["status"],
            "user_confirmed_not_visually_derived",
        )
        self.assertIs(annotation["occupation_completed"], True)
        self.assertEqual(annotation["normal_period_seconds"], 180)
        self.assertEqual(annotation["beginner_period_seconds"], 60)
        self.assertIs(annotation["period_lengths_approximate"], True)
        self.assertIn("not an image-only claim", annotation["note"])

    def test_level5_battle_payload_keeps_victory_and_occupation_separate(self) -> None:
        fixture = json.loads(BATTLE_FIXTURE.read_text(encoding="utf-8"))
        shot = fixture["screenshots"][0]
        battle = next(
            payload["data"]
            for payload in shot["payloads"]
            if payload["domain"] == "battle_report"
        )

        self.assertEqual(battle["result"], "win")
        self.assertEqual(battle["land_level"], 5)
        self.assertEqual(battle["resource_type"], "unknown")
        self.assertEqual(battle["occupation_result"], "unknown")
        self.assertNotIn("石头", json.dumps(battle, ensure_ascii=False))
        self.assertNotIn("stone", json.dumps(battle, ensure_ascii=False))
        self.assertEqual(
            (
                battle["attacker_initial_soldiers"],
                battle["attacker_remaining_soldiers"],
                battle["attacker_losses"],
            ),
            (33000, 32992, 8),
        )
        self.assertEqual(
            (
                battle["defender_initial_soldiers"],
                battle["defender_remaining_soldiers"],
                battle["defender_losses"],
            ),
            (10500, 0, 3828),
        )

        fragment = extract_battle_report(
            b"webp",
            client=_StubVision(battle),
            captured_at=datetime.fromisoformat(shot["captured_at"]),
        )
        report = fragment.map_state["latest_battle_report"]
        self.assertEqual(report["result"], "win")
        self.assertEqual(report["occupation_result"], "unknown")
        self.assertEqual(report["attacker_losses"], 8)
        self.assertNotIn("defender_losses", report)
        self.assertEqual(
            report["measurement_issues"],
            ["defender_total_inconsistent"],
        )
        self.assertEqual(report["verification"]["parse_status"], "partial")
        self.assertFalse(
            report["verification"]["action_verification_ready"]
        )

        artifact = shot["artifact"]
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        review = registry["approved"][artifact["sha256"]]
        self.assertEqual(artifact["privacy_review"], review["privacy_review"])
        self.assertEqual(artifact["bytes"], review["bytes"])
        fixture_transform = dict(artifact["transform"])
        source_sha = fixture_transform.pop("source_capture_sha256")
        self.assertEqual(source_sha, review["source_capture_sha256"])
        self.assertEqual(fixture_transform, review["transform"])
        self.assertIn("not an image-model evaluation", fixture["source"]["note"])
        classification = fixture["source"]["evidence_classification"]
        self.assertFalse(classification["action_correlated_live_trace"])
        self.assertFalse(classification["image_model_exercised"])


if __name__ == "__main__":
    unittest.main()
