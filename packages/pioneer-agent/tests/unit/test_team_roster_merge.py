from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.derivation.team_snapshot import evaluate_team_snapshot
from pioneer_agent.perception.domains.merge import apply_team_detail, apply_team_panel
from pioneer_agent.perception.domains.team_panel import _build_fragment as panel
from pioneer_agent.perception.domains.team_detail import _build_fragment as detail
from pioneer_agent.perception.vision.prompts import TeamPanelDetection, TeamDetailDetection


NOW = datetime(2026, 9, 8, tzinfo=UTC)


def snapshot(names, *, at=NOW, team_id="team-1", stamina=True):
    return panel(TeamPanelDetection.model_validate({
        "page_type": "team_panel", "team_id": team_id,
        "heroes": [
            {"name": name, **({"stamina": 80, "soldiers": 1000, "max_soldiers": 1000} if stamina else {})}
            for name in names
        ],
    }), captured_at=at)


def patch(name, *, at=NOW, team_id="team-1"):
    return detail(TeamDetailDetection.model_validate({
        "page_type": "hero_detail", "team_id": team_id,
        "detail_tabs_observed": ["装备", "马匹", "兵书", "属性加点", "战法等级", "兵种适性"],
        "heroes": [{"name": name, "equipment": [{"slot": "武器", "name": f"gear-{name}"}]}],
        "team_effects": ["old-team-effect"],
    }), captured_at=at)


class TeamRosterMergeTests(unittest.TestCase):
    def test_roster_replacement_keeps_only_retained_hero_details(self):
        state = apply_team_panel(RuntimeState(), snapshot(["A", "B", "C"]))
        state = apply_team_detail(state, patch("A"))
        state = apply_team_detail(state, patch("C"))
        old = state.model_dump()
        changed = apply_team_panel(state, snapshot(["A", "B", "D"], at=NOW + timedelta(seconds=1)))
        team = changed.teams[0]
        self.assertEqual([hero["name"] for hero in team["heroes"]], ["A", "B", "D"])
        self.assertEqual(team["heroes"][0]["equipment"][0]["name"], "gear-A")
        self.assertNotIn("equipment", team["heroes"][2])
        self.assertNotIn("old-team-effect", repr(changed.model_dump()))
        self.assertNotIn("gear-C", repr(changed.model_dump()))
        self.assertFalse(team["team_snapshot"]["pvp_pve_basis_ready"])
        self.assertFalse(changed.main_lineup["team_snapshot"]["pvp_pve_basis_ready"])
        self.assertTrue(changed.main_lineup["team_readiness"]["requires_detail_review"])
        self.assertNotIn("teams.team_detail", changed.field_meta)
        self.assertNotIn("main_lineup.team_snapshot", changed.field_meta)
        facts = evaluate_team_snapshot(team)["facts"]
        self.assertEqual(facts["hero_count"], 3)
        self.assertEqual(facts["detailed_hero_count"], 1)
        self.assertEqual(state.model_dump(), old, "merge must not mutate old snapshot")

    def test_delayed_removed_hero_detail_cannot_rejoin_or_restore_readiness(self):
        state = apply_team_panel(RuntimeState(), snapshot(["A", "B", "C"]))
        state = apply_team_panel(state, snapshot(["A", "B", "D"], at=NOW + timedelta(seconds=1)))
        before = state.model_dump()
        for delayed in (NOW, NOW + timedelta(seconds=2)):
            merged = apply_team_detail(state, patch("C", at=delayed))
            self.assertEqual(merged.model_dump(), before)

    def test_detail_patch_for_retained_hero_merges_without_replacing_roster(self):
        state = apply_team_panel(RuntimeState(), snapshot(["A", "B", "C"]))
        merged = apply_team_detail(state, patch("B"))
        self.assertEqual([hero["name"] for hero in merged.teams[0]["heroes"]], ["A", "B", "C"])
        self.assertEqual(merged.teams[0]["heroes"][1]["equipment"][0]["name"], "gear-B")
        self.assertEqual(merged.teams[0]["heroes"][0]["stamina"], 80)

    def test_empty_roster_clears_members_and_container_stamina(self):
        state = apply_team_panel(RuntimeState(), snapshot(["A", "B", "C"]))
        state = apply_team_detail(state, patch("C"))
        merged = apply_team_panel(state, snapshot([], at=NOW + timedelta(seconds=1)))
        self.assertEqual(merged.teams[0]["heroes"], [])
        self.assertNotIn("container_stamina", merged.team_containers[0])
        self.assertNotIn("soldiers", merged.team_containers[0])
        self.assertFalse(merged.main_lineup["team_snapshot"]["pvp_pve_basis_ready"])

    def test_same_roster_alias_and_reorder_preserve_details_but_not_other_teams(self):
        state = apply_team_panel(RuntimeState(), snapshot(["祝融夫人", "孟获"]))
        state = apply_team_detail(state, patch("祝融夫人"))
        state.teams.append({"team_id": "team-2", "heroes": [{"name": "X"}]})
        merged = apply_team_panel(state, snapshot(["孟获", "群祝融夫人"]))
        self.assertEqual(len(merged.teams[0]["heroes"]), 2)
        self.assertEqual(merged.teams[0]["heroes"][1]["equipment"][0]["name"], "gear-祝融夫人")
        self.assertEqual(merged.teams[0]["missing_detail_tabs"], [])
        self.assertEqual(merged.teams[1], state.teams[1])

    def test_different_factions_and_ambiguous_alias_never_inherit_details(self):
        state = apply_team_panel(RuntimeState(), snapshot(["魏关羽", "蜀关羽"]))
        state = apply_team_detail(state, patch("魏关羽"))
        merged = apply_team_panel(state, snapshot(["关羽"]))
        self.assertNotIn("equipment", merged.teams[0]["heroes"][0])
        self.assertFalse(merged.teams[0]["team_snapshot"]["pvp_pve_basis_ready"])

    def test_older_detail_for_retained_hero_is_rejected(self):
        state = apply_team_panel(RuntimeState(), snapshot(["A"], at=NOW + timedelta(seconds=1)))
        self.assertEqual(apply_team_detail(state, patch("A")).model_dump(), state.model_dump())

    def test_older_panel_cannot_restore_removed_roster(self):
        state = apply_team_panel(RuntimeState(), snapshot(["A", "B", "D"], at=NOW + timedelta(seconds=1)))
        self.assertEqual(
            apply_team_panel(state, snapshot(["A", "B", "C"])).model_dump(), state.model_dump(),
        )


if __name__ == "__main__":
    unittest.main()
