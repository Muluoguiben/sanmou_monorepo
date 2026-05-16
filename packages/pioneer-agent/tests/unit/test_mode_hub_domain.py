from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import apply_mode_hub, extract_mode_hub


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


class ModeHubDomainTests(unittest.TestCase):
    def test_extract_maps_event_tournament(self) -> None:
        fragment = extract_mode_hub(
            b"png",
            client=_StubVision(
                {
                    "page_type": "event_tournament",
                    "title": "演武大会",
                    "active_tab": "征战",
                    "total_score": 1280,
                    "rank": 36,
                    "phase_status": "报名中",
                    "countdown": "01:23:45",
                    "entries": [
                        {
                            "name": "演武大会",
                            "status": "available",
                            "score": 1280,
                            "rank": 36,
                            "countdown": "01:23:45",
                            "can_enter": True,
                            "can_register": True,
                            "button_label": "前往",
                            "x_min": 700,
                            "y_min": 780,
                            "x_max": 920,
                            "y_max": 900,
                        }
                    ],
                    "visible_notes": ["可报名"],
                }
            ),
            captured_at=datetime(2026, 5, 17, 12, 0, 0),
        )

        event = fragment.global_state["event_tournament"]
        self.assertEqual(event["title"], "演武大会")
        self.assertEqual(event["total_score"], 1280)
        self.assertTrue(event["entries"][0]["can_register"])
        self.assertEqual(event["entries"][0]["bbox"]["x_min"], 700)
        self.assertIn("global_state.event_tournament", fragment.field_meta)

    def test_apply_mode_hub_merges_global_state(self) -> None:
        fragment = extract_mode_hub(
            b"png",
            client=_StubVision(
                {
                    "page_type": "mode_hub",
                    "title": "征战",
                    "entries": [
                        {
                            "name": "远征",
                            "status": "in_progress",
                            "can_enter": True,
                        }
                    ],
                }
            ),
        )
        state = RuntimeState(global_state={"page_type": "mode_hub"})

        merged = apply_mode_hub(state, fragment)

        self.assertEqual(merged.global_state["page_type"], "mode_hub")
        self.assertEqual(merged.global_state["mode_hub"]["entries"][0]["name"], "远征")


if __name__ == "__main__":
    unittest.main()
