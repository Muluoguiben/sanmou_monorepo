from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.derivation.phase import derive_phase_tag
from pioneer_agent.derivation.readiness import compute_combat_readiness


class StateDeriver:
    def derive(self, state: RuntimeState) -> RuntimeState:
        derived = deepcopy(state)

        global_state = derived.global_state
        current_time = self._parse_datetime(global_state.get("current_time"))
        server_open_time = self._parse_datetime(global_state.get("server_open_time"))
        settlement_time = self._parse_datetime(global_state.get("settlement_time"))

        if current_time and server_open_time:
            hours_since = (current_time - server_open_time).total_seconds() / 3600
            global_state["hours_since_server_open"] = round(hours_since, 2)
        if current_time and settlement_time:
            hours_until = (settlement_time - current_time).total_seconds() / 3600
            global_state["hours_until_settlement"] = round(hours_until, 2)

        if global_state.get("hours_since_server_open") is not None and global_state.get("hours_until_settlement") is not None:
            global_state["phase_tag"] = derive_phase_tag(
                float(global_state["hours_since_server_open"]),
                float(global_state["hours_until_settlement"]),
            )

        self._derive_main_lineup_summary(derived)
        self._derive_team_container_readiness(derived)
        self._derive_candidate_land_features(derived)
        self._derive_building_features(derived)
        self._derive_primary_constraint(derived)
        return derived

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _derive_main_lineup_summary(state: RuntimeState) -> None:
        hero_ids = state.main_lineup.get("hero_ids", [])
        if not hero_ids:
            return
        lineup_heroes = [hero for hero in state.heroes if hero.get("hero_id") in hero_ids]
        if not lineup_heroes:
            return
        levels = [float(hero.get("level", 0)) for hero in lineup_heroes]
        state.main_lineup["avg_level"] = round(sum(levels) / len(levels), 2)
        state.main_lineup["min_core_level"] = min(levels)
        state.main_lineup["max_core_level"] = max(levels)

    @staticmethod
    def _derive_team_container_readiness(state: RuntimeState) -> None:
        for container in state.team_containers:
            readiness = compute_combat_readiness(container, state.main_lineup)
            container["combat_readiness_if_hosting_main"] = readiness
            container["host_score"] = readiness["combat_readiness_score"]
            max_soldiers = float(container.get("max_soldiers", 0) or 0)
            if max_soldiers > 0:
                soldiers = float(container.get("soldiers", 0) or 0)
                container["soldier_gap"] = round(max(max_soldiers - soldiers, 0), 2)
                container["soldier_fill_ratio"] = round(soldiers / max_soldiers, 4)

    @staticmethod
    def _derive_candidate_land_features(state: RuntimeState) -> None:
        current_chapter_id = int(state.progress.get("current_chapter_id", 0) or 0)
        task_progress = state.progress.get("task_progress", {})
        target_land_level = 0
        host_team_id = state.main_lineup.get("current_host_team_id")
        host_stamina = 0.0
        for container in state.team_containers:
            if container.get("team_id") == host_team_id:
                host_stamina = float(container.get("container_stamina", 0) or 0)
                break
        for task_id, progress in task_progress.items():
            if "land" in task_id:
                target_land_level = int(progress.get("target_level", 0) or target_land_level)
        if target_land_level == 0:
            target_land_level = current_chapter_id + 2 if current_chapter_id else 6

        for land in state.map_state.get("candidate_lands", []):
            level = int(land.get("level", 0) or 0)
            required_stamina = int(land.get("required_stamina", land.get("stamina_cost", 15)) or 15)
            land["required_stamina"] = required_stamina
            land["host_stamina_gap"] = max(required_stamina - host_stamina, 0)
            if level >= target_land_level:
                land["chapter_relevance"] = "advance_current_task"
            else:
                land.setdefault("chapter_relevance", "none")

            avg_level = float(state.main_lineup.get("avg_level", 0))
            if avg_level >= level * 3:
                land["level_fit"] = "safe"
            elif avg_level >= max(level * 2.5, 1):
                land["level_fit"] = "edge"
            else:
                land["level_fit"] = "overreach"

    @staticmethod
    def _derive_building_features(state: RuntimeState) -> None:
        current_chapter_id = int(state.progress.get("current_chapter_id", 0) or 0)
        resources = state.economy.get("resources", {})
        income_per_hour = state.economy.get("income_per_hour", {})
        for building in state.city.get("upgradeable_buildings", []):
            building_id = building.get("building_id", "")
            if "hall" in building_id:
                building["chapter_relevance"] = "complete_current_task"
                building["economy_gain"] = 5
                building["battle_support_gain"] = 8
            elif current_chapter_id and any(token in building_id for token in ("barrack", "camp", "recruit")):
                building["chapter_relevance"] = "prepare_next_chapter"
                building["economy_gain"] = 2
                building["battle_support_gain"] = 15
            else:
                building["chapter_relevance"] = "low_relevance"
                building["economy_gain"] = 3
                building["battle_support_gain"] = 4
            cost = building.get("cost", {})
            shortages: dict[str, float] = {}
            wait_seconds_by_resource: dict[str, int] = {}
            for resource_type, required_amount in cost.items():
                required_value = float(required_amount or 0)
                current_amount = float(resources.get(resource_type, 0) or 0)
                shortage = max(required_value - current_amount, 0)
                if shortage <= 0:
                    continue
                shortages[resource_type] = round(shortage, 2)
                hourly_income = float(income_per_hour.get(resource_type, 0) or 0)
                if hourly_income > 0:
                    wait_seconds_by_resource[resource_type] = int(round(shortage / hourly_income * 3600))

            if shortages:
                building["resource_shortages"] = shortages
                building["resource_ready"] = False
                if wait_seconds_by_resource:
                    wait_target_resource = min(wait_seconds_by_resource, key=wait_seconds_by_resource.get)
                    building["wait_target_resource"] = wait_target_resource
                    building["wait_seconds_for_resources"] = wait_seconds_by_resource[wait_target_resource]
            else:
                building["resource_shortages"] = {}
                building["resource_ready"] = True

            default_penalty = max(sum(float(amount or 0) for amount in cost.values()) / 4000, 5)
            building.setdefault("resource_cost_penalty", round(default_penalty, 2))

    @staticmethod
    def _derive_primary_constraint(state: RuntimeState) -> None:
        host_team_id = state.main_lineup.get("current_host_team_id")
        for container in state.team_containers:
            if container.get("team_id") == host_team_id:
                readiness = container.get("combat_readiness_if_hosting_main", {})
                state.main_lineup["primary_constraint"] = readiness.get("primary_constraint", "unknown")
                state.main_lineup["combat_readiness_score"] = readiness.get("combat_readiness_score", 0)
                return
