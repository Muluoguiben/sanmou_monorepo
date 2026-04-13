"""Tests for VisionSync — page-conditional domain routing."""
from __future__ import annotations

import unittest
from dataclasses import dataclass
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.vision_sync import VisionSync


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "stub"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _ScriptedVisionClient:
    """Returns a different payload for each extraction, in order of schema type."""

    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.calls: list[str] = []

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        # Differentiate by instruction prefix — cheap and accurate enough for tests.
        if "resource" in instruction.lower() or "top bar" in instruction.lower() or "page type" in instruction.lower():
            kind = "resource_bar"
        elif "城内" in instruction or "city" in instruction.lower() or "building" in instruction.lower():
            kind = "city_buildings"
        else:
            kind = "other"
        self.calls.append(kind)
        return _StubResult(data=self._payloads[len(self.calls) - 1])


class VisionSyncTests(unittest.TestCase):
    def test_main_map_runs_only_resource_bar(self) -> None:
        client = _ScriptedVisionClient(
            [
                {
                    "page_type": "main_map",
                    "resources": {"copper": 100},
                    "visible_notes": ["banner"],
                }
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png", state=RuntimeState())
        self.assertEqual(summary.page_type, "main_map")
        self.assertEqual(summary.domains_run, ["resource_bar"])
        self.assertEqual(client.calls, ["resource_bar"])
        self.assertEqual(state.global_state.get("page_type"), "main_map")
        self.assertIn("banner", summary.notes)

    def test_city_page_also_runs_city_buildings(self) -> None:
        client = _ScriptedVisionClient(
            [
                {"page_type": "city", "resources": {}},
                {
                    "prosperity": 165883,
                    "territory": "60/60",
                    "buildings": [{"name": "征兵所", "level": 10}],
                },
            ]
        )
        sync = VisionSync(client)
        state, summary = sync.sync(b"png")
        self.assertEqual(summary.page_type, "city")
        self.assertEqual(summary.domains_run, ["resource_bar", "city_buildings"])
        self.assertEqual(client.calls, ["resource_bar", "city_buildings"])
        self.assertEqual(state.city.get("prosperity"), 165883)
        self.assertEqual(len(state.city.get("buildings", [])), 1)

    def test_unknown_page_stops_after_resource_bar(self) -> None:
        client = _ScriptedVisionClient(
            [{"page_type": "unknown", "resources": {}}]
        )
        sync = VisionSync(client)
        _state, summary = sync.sync(b"png")
        self.assertEqual(summary.domains_run, ["resource_bar"])


if __name__ == "__main__":
    unittest.main()
