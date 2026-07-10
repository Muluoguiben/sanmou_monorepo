from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import ValidationError

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import apply_upgrade_dialog, extract_upgrade_dialog


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


class UpgradeDialogDomainTests(unittest.TestCase):
    def test_raw_boolean_cannot_be_coerced_to_upgrade_level(self) -> None:
        with self.assertRaises(ValidationError):
            extract_upgrade_dialog(
                b"png",
                client=_StubVision(
                    {
                        "dialog_visible": True,
                        "building_name": "仓库",
                        "current_level": True,
                        "next_level": 2,
                        "can_upgrade": False,
                    }
                ),
            )

    def test_extract_maps_upgrade_dialog(self) -> None:
        fragment = extract_upgrade_dialog(
            b"png",
            client=_StubVision(
                {
                    "dialog_visible": True,
                    "building_name": "征兵所",
                    "current_level": 9,
                    "next_level": 10,
                    "can_upgrade": False,
                    "cannot_upgrade_reason": "石料不足",
                    "costs": [
                        {"name": "木材", "required": 8000, "available": 12000, "enough": True},
                        {"name": "石料", "required": 12000, "available": 8000, "enough": False},
                    ],
                    "confirm_button_visible": True,
                    "confirm_button_enabled": False,
                    "confirm_x_min": 720,
                    "confirm_y_min": 820,
                    "confirm_x_max": 920,
                    "confirm_y_max": 900,
                    "close_button_visible": True,
                    "close_x_min": 930,
                    "close_y_min": 80,
                    "close_x_max": 980,
                    "close_y_max": 140,
                    "visible_notes": ["升级按钮置灰"],
                }
            ),
            captured_at=datetime(2026, 5, 17, 12, 0, 0),
        )

        dialog = fragment.city["upgrade_dialog"]
        self.assertTrue(dialog["visible"])
        self.assertEqual(dialog["building_name"], "征兵所")
        self.assertEqual(dialog["current_level"], 9)
        self.assertEqual(dialog["next_level"], 10)
        self.assertFalse(dialog["can_upgrade"])
        self.assertEqual(dialog["cannot_upgrade_reason"], "石料不足")
        self.assertFalse(dialog["costs"][1]["enough"])
        self.assertFalse(dialog["confirm_button"]["enabled"])
        self.assertEqual(dialog["confirm_button"]["bbox"]["x_min"], 720)
        self.assertEqual(dialog["close_button"]["bbox"]["x_min"], 930)
        self.assertIn("city.upgrade_dialog", fragment.field_meta)
        self.assertIn("升级按钮置灰", fragment.notes)

    def test_apply_upgrade_dialog_merges_city(self) -> None:
        fragment = extract_upgrade_dialog(
            b"png",
            client=_StubVision(
                {
                    "dialog_visible": True,
                    "building_name": "仓库",
                    "current_level": 6,
                    "next_level": 7,
                    "can_upgrade": True,
                    "costs": [],
                    "confirm_button_visible": True,
                    "confirm_button_enabled": True,
                    "confirm_x_min": 720,
                    "confirm_y_min": 820,
                    "confirm_x_max": 920,
                    "confirm_y_max": 900,
                    "close_button_visible": True,
                    "close_x_min": 930,
                    "close_y_min": 80,
                    "close_x_max": 980,
                    "close_y_max": 140,
                }
            ),
        )
        state = RuntimeState(city={"prosperity": 165883})

        merged = apply_upgrade_dialog(state, fragment)

        self.assertEqual(merged.city["prosperity"], 165883)
        self.assertEqual(merged.city["upgrade_dialog"]["building_name"], "仓库")
        self.assertTrue(merged.city["upgrade_dialog"]["confirm_button"]["enabled"])


if __name__ == "__main__":
    unittest.main()
