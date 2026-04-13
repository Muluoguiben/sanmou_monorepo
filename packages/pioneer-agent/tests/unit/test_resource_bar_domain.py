"""Tests for the resource_bar vision domain extractor.

Uses a stub VisionClient so the real Gemini API is never called.
"""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pioneer_agent.perception.domains import extract_resource_bar


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _StubVisionClient:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.calls = 0

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        self.calls += 1
        return _StubResult(data=self._payload)


class ResourceBarDomainTests(unittest.TestCase):
    def test_full_payload_maps_to_runtime_fragment(self) -> None:
        stub = _StubVisionClient(
            {
                "page_type": "main_map",
                "resources": {
                    "military_order": 147,
                    "military_order_max": 150,
                    "copper": 0,
                    "wood": 5_220_000,
                    "iron": 5_220_000,
                    "stone": 5_180_000,
                    "grain": 3_720_000,
                    "gold_bead": 51_508,
                    "yuanbao": 14_185,
                },
                "visible_notes": ["Prosperity 165883", "Territory 60/60"],
            }
        )
        captured = datetime(2026, 4, 13, 12, 0, 0)

        fragment = extract_resource_bar(b"fake-bytes", client=stub, captured_at=captured)

        self.assertEqual(stub.calls, 1)
        self.assertEqual(fragment.page_type, "main_map")
        self.assertEqual(fragment.global_state["military_order"], 147)
        self.assertEqual(fragment.global_state["military_order_max"], 150)
        self.assertEqual(
            fragment.economy["resources"],
            {"wood": 5_220_000, "iron": 5_220_000, "stone": 5_180_000, "grain": 3_720_000},
        )
        self.assertEqual(
            fragment.economy["currencies"],
            {"copper": 0, "gold_bead": 51_508, "yuanbao": 14_185},
        )
        self.assertEqual(fragment.field_meta["economy"].updated_at, captured)
        self.assertEqual(fragment.field_meta["economy"].source, "vision.resource_bar")
        self.assertIn("Prosperity 165883", fragment.notes)

    def test_missing_fields_are_omitted_not_zero_filled(self) -> None:
        stub = _StubVisionClient(
            {
                "page_type": "hero_list",
                "resources": {"wood": 1000},
                "visible_notes": [],
            }
        )

        fragment = extract_resource_bar(b"fake-bytes", client=stub)

        self.assertEqual(fragment.economy["resources"], {"wood": 1000})
        self.assertNotIn("currencies", fragment.economy)
        self.assertNotIn("military_order", fragment.global_state)
        self.assertEqual(fragment.global_state, {"page_type": "hero_list"})

    def test_empty_resources_still_yields_page_type(self) -> None:
        stub = _StubVisionClient(
            {"page_type": "unknown", "resources": {}, "visible_notes": []}
        )

        fragment = extract_resource_bar(b"fake-bytes", client=stub)

        self.assertEqual(fragment.page_type, "unknown")
        self.assertEqual(fragment.global_state, {"page_type": "unknown"})
        self.assertEqual(fragment.economy, {})
        self.assertIn("global_state", fragment.field_meta)
        self.assertNotIn("economy", fragment.field_meta)


if __name__ == "__main__":
    unittest.main()
