from __future__ import annotations

import unittest

from pydantic import ValidationError

from pioneer_agent.perception.vision.prompts import (
    ChapterPanelDetection,
    ElementBox,
    RecruitTeamDetection,
    CityBuilding,
    TeamDetailDetection,
    TeamPanelDetection,
    UpgradeDialogDetection,
)


class VisionSemanticValidatorTests(unittest.TestCase):
    def test_chapter_claim_button_requires_visible_enabled_bbox(self) -> None:
        with self.assertRaisesRegex(ValidationError, "cannot be enabled when not visible"):
            ChapterPanelDetection.model_validate(
                {
                    "chapter_claimable": True,
                    "claim_button_visible": False,
                    "claim_button_enabled": True,
                    "tasks": [],
                }
            )

        with self.assertRaisesRegex(ValidationError, "bbox must include"):
            ChapterPanelDetection.model_validate(
                {
                    "chapter_claimable": True,
                    "claim_button_visible": True,
                    "claim_button_enabled": True,
                    "claim_x_min": 700,
                    "tasks": [],
                }
            )

    def test_recruit_button_rejects_reversed_bbox(self) -> None:
        with self.assertRaisesRegex(ValidationError, "x_min < x_max"):
            RecruitTeamDetection.model_validate(
                {
                    "team_id": "部队一",
                    "recruit_button_visible": True,
                    "recruit_button_enabled": True,
                    "button_x_min": 920,
                    "button_y_min": 820,
                    "button_x_max": 760,
                    "button_y_max": 900,
                }
            )

    def test_upgrade_dialog_rejects_cross_domain_payload_when_hidden(self) -> None:
        with self.assertRaisesRegex(ValidationError, "dialog_visible=true"):
            UpgradeDialogDetection.model_validate(
                {
                    "dialog_visible": False,
                    "building_name": "仓库",
                    "costs": [],
                    "confirm_button_visible": False,
                    "confirm_button_enabled": False,
                }
            )

    def test_upgrade_dialog_requires_enabled_confirm_for_can_upgrade(self) -> None:
        with self.assertRaisesRegex(ValidationError, "can_upgrade requires"):
            UpgradeDialogDetection.model_validate(
                {
                    "dialog_visible": True,
                    "building_name": "仓库",
                    "can_upgrade": True,
                    "costs": [],
                    "confirm_button_visible": True,
                    "confirm_button_enabled": False,
                    "confirm_x_min": 720,
                    "confirm_y_min": 820,
                    "confirm_x_max": 920,
                    "confirm_y_max": 900,
                    "close_button_visible": False,
                }
            )

    def test_city_building_upgrade_button_requires_visible_bbox(self) -> None:
        with self.assertRaisesRegex(ValidationError, "cannot be enabled when not visible"):
            CityBuilding.model_validate(
                {
                    "name": "君王殿",
                    "upgrade_button_visible": False,
                    "upgrade_button_enabled": True,
                }
            )

        with self.assertRaisesRegex(ValidationError, "bbox must include"):
            CityBuilding.model_validate(
                {
                    "name": "君王殿",
                    "upgrade_button_visible": True,
                    "upgrade_button_enabled": True,
                    "upgrade_button_x_min": 100,
                }
            )

    def test_unknown_team_pages_reject_domain_payload(self) -> None:
        with self.assertRaisesRegex(ValidationError, "unknown team page_type"):
            TeamPanelDetection.model_validate(
                {
                    "page_type": "unknown",
                    "team_id": "部队一",
                    "heroes": [],
                }
            )
        with self.assertRaisesRegex(ValidationError, "unknown team detail page_type"):
            TeamDetailDetection.model_validate(
                {
                    "page_type": "unknown",
                    "detail_tabs_observed": ["装备"],
                    "heroes": [],
                }
            )

    def test_element_box_rejects_reversed_bbox(self) -> None:
        with self.assertRaisesRegex(ValidationError, "x_min < x_max"):
            ElementBox.model_validate(
                {
                    "label": "领取",
                    "y_min": 100,
                    "x_min": 900,
                    "y_max": 120,
                    "x_max": 850,
                }
            )


if __name__ == "__main__":
    unittest.main()
