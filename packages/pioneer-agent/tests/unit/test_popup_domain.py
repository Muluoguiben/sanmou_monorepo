from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import apply_popup, extract_popup


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


class PopupDomainTests(unittest.TestCase):
    def test_extract_maps_blocking_confirmation_popup(self) -> None:
        fragment = extract_popup(
            b"png",
            client=_StubVision(
                {
                    "popup_visible": True,
                    "popup_type": "confirmation",
                    "title": "确认",
                    "message": "是否放弃土地？",
                    "blocking": True,
                    "safe_default_action": "cancel",
                    "buttons": [
                        {
                            "label": "取消",
                            "role": "cancel",
                            "enabled": True,
                            "x_min": 300,
                            "y_min": 700,
                            "x_max": 450,
                            "y_max": 780,
                        },
                        {"label": "确定", "role": "confirm", "enabled": True},
                    ],
                    "visible_notes": ["高风险确认框"],
                }
            ),
            captured_at=datetime(2026, 5, 17, 12, 0, 0),
        )

        popup = fragment.global_state["popup"]
        self.assertTrue(popup["visible"])
        self.assertEqual(popup["safe_default_action"], "cancel")
        self.assertEqual(popup["buttons"][0]["bbox"]["x_min"], 300)
        self.assertEqual(fragment.notes, ["高风险确认框"])
        self.assertIn("global_state.popup", fragment.field_meta)

    def test_apply_popup_merges_into_global_state(self) -> None:
        fragment = extract_popup(
            b"png",
            client=_StubVision(
                {
                    "popup_visible": True,
                    "popup_type": "reward",
                    "blocking": True,
                    "safe_default_action": "close",
                    "buttons": [{"label": "关闭", "role": "close"}],
                }
            ),
        )
        state = RuntimeState(global_state={"page_type": "chapter"})

        merged = apply_popup(state, fragment)

        self.assertEqual(merged.global_state["page_type"], "chapter")
        self.assertEqual(merged.global_state["popup"]["type"], "reward")


if __name__ == "__main__":
    unittest.main()
