from __future__ import annotations

import unittest
from datetime import datetime, timedelta

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.runbook.lineup_binding import (
    LINEUP_BINDING_MAX_AGE,
    OPERATOR_LINEUP_BINDING_SOURCE,
    apply_operator_lineup_bindings,
    operator_lineup_binding_map,
    parse_operator_lineup_binding,
    trusted_lineup_preset,
)


def _state(hero_id: str = "hero-1") -> RuntimeState:
    return RuntimeState(
        team_containers=[{"team_id": "team-1"}],
        teams=[
            {
                "team_id": "team-1",
                "page_type": "team_panel",
                "formation": "wedge",
                "heroes": [
                    {"hero_id": hero_id, "position": 1},
                    {"hero_id": "hero-2", "position": 2},
                    {"hero_id": "hero-3", "position": 3},
                ],
            }
        ],
    )


class RunbookLineupBindingTests(unittest.TestCase):
    def test_parse_and_conflicting_duplicates(self) -> None:
        self.assertEqual(
            parse_operator_lineup_binding(" team-1 = main_team "),
            ("team-1", "main_team"),
        )
        for raw in ("team-1", "=main_team", "team-1="):
            with self.subTest(raw=raw), self.assertRaises(ValueError):
                parse_operator_lineup_binding(raw)
        with self.assertRaises(ValueError):
            operator_lineup_binding_map(
                [("team-1", "main_team"), ("team-1", "other")]
            )

    def test_fresh_binding_has_provenance_and_is_trusted(self) -> None:
        now = datetime.now().astimezone()
        state = _state()
        apply_operator_lineup_bindings(
            state,
            {"team-1": "main_team"},
            bound_at=now,
            now=now,
        )
        team = state.team_containers[0]
        self.assertEqual(team["lineup_preset"], "main_team")
        self.assertEqual(
            team["lineup_preset_source"],
            OPERATOR_LINEUP_BINDING_SOURCE,
        )
        self.assertEqual(trusted_lineup_preset(state, team, now=now), "main_team")
        meta = state.field_meta["team_containers.team-1.lineup_preset"]
        self.assertEqual(meta.source, OPERATOR_LINEUP_BINDING_SOURCE)

    def test_spoofed_stale_and_ambiguous_bindings_fail_closed(self) -> None:
        now = datetime.now().astimezone()
        spoofed = {"team_id": "team-1", "lineup_preset": "main_team"}
        self.assertIsNone(trusted_lineup_preset(_state(), spoofed, now=now))

        stale_state = _state()
        apply_operator_lineup_bindings(
            stale_state,
            {"team-1": "main_team"},
            bound_at=now - LINEUP_BINDING_MAX_AGE - timedelta(seconds=1),
            now=now,
        )
        self.assertNotIn("lineup_preset", stale_state.team_containers[0])

        duplicate_state = RuntimeState(
            team_containers=[{"team_id": "team-1"}, {"team_id": "team-1"}],
            teams=_state().teams,
        )
        apply_operator_lineup_bindings(
            duplicate_state,
            {"team-1": "main_team"},
            bound_at=now,
            now=now,
        )
        self.assertTrue(
            all("lineup_preset" not in team for team in duplicate_state.team_containers)
        )

    def test_same_team_slot_roster_change_invalidates_session_binding(self) -> None:
        now = datetime.now().astimezone()
        captured: dict[str, str] = {}
        first = _state("hero-1")
        apply_operator_lineup_bindings(
            first,
            {"team-1": "main_team"},
            bound_at=now,
            now=now,
            roster_fingerprints=captured,
        )
        self.assertEqual(
            trusted_lineup_preset(first, first.team_containers[0], now=now),
            "main_team",
        )

        changed = _state("hero-2")
        apply_operator_lineup_bindings(
            changed,
            {"team-1": "main_team"},
            bound_at=now,
            now=now,
            roster_fingerprints=captured,
        )
        self.assertNotIn("lineup_preset", changed.team_containers[0])

    def test_partial_or_duplicate_roster_is_not_bound(self) -> None:
        now = datetime.now().astimezone()
        for heroes in (
            [{"hero_id": "hero-1"}],
            [
                {"hero_id": "hero-1"},
                {"hero_id": "hero-1"},
                {"hero_id": "hero-3"},
            ],
        ):
            with self.subTest(heroes=heroes):
                state = RuntimeState(
                    team_containers=[{"team_id": "team-1"}],
                    teams=[
                        {
                            "team_id": "team-1",
                            "page_type": "team_panel",
                            "heroes": heroes,
                        }
                    ],
                )
                apply_operator_lineup_bindings(
                    state,
                    {"team-1": "main_team"},
                    bound_at=now,
                    now=now,
                    roster_fingerprints={},
                )
                self.assertNotIn("lineup_preset", state.team_containers[0])

    def test_hidden_detail_changes_do_not_relabel_same_hero_roster(self) -> None:
        now = datetime.now().astimezone()
        captured: dict[str, str] = {}
        first = _state()
        first.teams[0]["formation"] = "wedge"
        first.teams[0]["heroes"][0]["tactics"] = ["tactic-a"]
        apply_operator_lineup_bindings(
            first,
            {"team-1": "main_team"},
            bound_at=now,
            now=now,
            roster_fingerprints=captured,
        )

        enriched = _state()
        enriched.teams[0]["formation"] = "goose"
        enriched.teams[0]["heroes"][0]["tactics"] = ["tactic-b"]
        apply_operator_lineup_bindings(
            enriched,
            {"team-1": "main_team"},
            bound_at=now,
            now=now,
            roster_fingerprints=captured,
        )
        self.assertEqual(
            trusted_lineup_preset(
                enriched,
                enriched.team_containers[0],
                now=now,
            ),
            "main_team",
        )


if __name__ == "__main__":
    unittest.main()
