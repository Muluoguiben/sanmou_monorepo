from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import apply_chapter_panel, extract_chapter_panel


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


class ChapterPanelDomainTests(unittest.TestCase):
    def test_extract_maps_claimable_chapter_panel(self) -> None:
        fragment = extract_chapter_panel(
            b"png",
            client=_StubVision(
                {
                    "current_chapter_id": 3,
                    "current_chapter_title": "开疆拓土",
                    "chapter_claimable": True,
                    "claim_button_visible": True,
                    "claim_button_enabled": True,
                    "claim_x_min": 760,
                    "claim_y_min": 820,
                    "claim_x_max": 920,
                    "claim_y_max": 900,
                    "tasks": [
                        {
                            "name": "占领 4 级地",
                            "completed": True,
                            "current": 1,
                            "required": 1,
                            "reward_claimable": True,
                        }
                    ],
                    "visible_notes": ["章节奖励可领取"],
                }
            ),
            captured_at=datetime(2026, 5, 17, 12, 0, 0),
        )

        self.assertTrue(fragment.progress["chapter_claimable"])
        self.assertEqual(fragment.progress["current_chapter_id"], 3)
        self.assertEqual(fragment.progress["chapter_claim_button"]["bbox"]["x_min"], 760)
        self.assertEqual(fragment.progress["chapter_tasks"][0]["name"], "占领 4 级地")
        self.assertIn("progress.chapter_panel", fragment.field_meta)

    def test_apply_chapter_panel_merges_progress(self) -> None:
        fragment = extract_chapter_panel(
            b"png",
            client=_StubVision(
                {
                    "current_chapter_id": 4,
                    "chapter_claimable": False,
                    "claim_button_visible": False,
                    "claim_button_enabled": False,
                    "tasks": [],
                }
            ),
        )
        state = RuntimeState(progress={"old": "keep"})

        merged = apply_chapter_panel(state, fragment)

        self.assertEqual(merged.progress["old"], "keep")
        self.assertFalse(merged.progress["chapter_claimable"])
        self.assertEqual(merged.progress["current_chapter_id"], 4)


if __name__ == "__main__":
    unittest.main()
