"""Tests for merging a resource_bar fragment into RuntimeState."""
from __future__ import annotations

import unittest
from datetime import datetime

from pioneer_agent.core.models import FieldMeta, RuntimeState
from pioneer_agent.perception.domains import (
    ResourceBarFragment,
    apply_resource_bar,
)


class ApplyResourceBarTests(unittest.TestCase):
    def test_merge_preserves_unrelated_global_state_fields(self) -> None:
        state = RuntimeState(
            global_state={
                "server_open_time": "2026-03-29T10:00:00+08:00",
                "current_time": "2026-03-29T16:30:00+08:00",
            }
        )
        fragment = ResourceBarFragment(
            page_type="main_map",
            global_state={"page_type": "main_map", "military_order": 120},
        )

        new_state = apply_resource_bar(state, fragment)

        self.assertEqual(new_state.global_state["server_open_time"], "2026-03-29T10:00:00+08:00")
        self.assertEqual(new_state.global_state["page_type"], "main_map")
        self.assertEqual(new_state.global_state["military_order"], 120)

    def test_economy_resources_merge_per_key_not_replace(self) -> None:
        state = RuntimeState(
            economy={
                "resources": {"wood": 1000, "stone": 2000, "iron": 3000, "grain": 4000},
                "income_per_hour": {"wood": 100, "stone": 200, "iron": 300, "grain": 400},
                "reserve_troops": 5000,
            }
        )
        fragment = ResourceBarFragment(
            page_type="main_map",
            economy={
                "resources": {"wood": 9999, "grain": 8888},
                "currencies": {"yuanbao": 14185},
            },
        )

        new_state = apply_resource_bar(state, fragment)

        self.assertEqual(
            new_state.economy["resources"],
            {"wood": 9999, "stone": 2000, "iron": 3000, "grain": 8888},
        )
        self.assertEqual(new_state.economy["currencies"], {"yuanbao": 14185})
        self.assertEqual(new_state.economy["income_per_hour"]["wood"], 100)
        self.assertEqual(new_state.economy["reserve_troops"], 5000)

    def test_field_meta_is_overwritten_with_fresh_timestamps(self) -> None:
        older = datetime(2026, 4, 13, 9, 0, 0)
        newer = datetime(2026, 4, 13, 12, 0, 0)
        state = RuntimeState(
            field_meta={
                "economy": FieldMeta(value="loaded", source="json_file", updated_at=older),
            }
        )
        fragment = ResourceBarFragment(
            page_type="main_map",
            economy={"resources": {"wood": 1}},
            field_meta={
                "economy": FieldMeta(
                    value="loaded",
                    confidence=0.9,
                    source="vision.resource_bar",
                    updated_at=newer,
                ),
            },
        )

        new_state = apply_resource_bar(state, fragment)

        self.assertEqual(new_state.field_meta["economy"].source, "vision.resource_bar")
        self.assertEqual(new_state.field_meta["economy"].updated_at, newer)

    def test_returns_new_state_original_untouched(self) -> None:
        state = RuntimeState(global_state={"phase_tag": "opening_sprint"})
        fragment = ResourceBarFragment(
            page_type="main_map", global_state={"page_type": "main_map"}
        )

        new_state = apply_resource_bar(state, fragment)

        self.assertIsNot(new_state, state)
        self.assertNotIn("page_type", state.global_state)
        self.assertEqual(new_state.global_state["phase_tag"], "opening_sprint")


if __name__ == "__main__":
    unittest.main()
