from __future__ import annotations

from copy import deepcopy
from datetime import datetime
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.derivation.phase import derive_phase_tag
from pioneer_agent.derivation.readiness import compute_combat_readiness
from pioneer_agent.derivation.team_snapshot import apply_team_snapshot_judgements

BUILDING_ALIASES: dict[str, set[str]] = {
    "main_hall": {"main_hall", "main hall", "君王殿"},
    "recruit_office": {"recruit_office", "recruit office", "recruit", "征兵所"},
    "barracks": {"barracks", "camp", "军营"},
    "blacksmith": {"blacksmith", "铁匠铺"},
    "scout_tower": {"scout_tower", "scout tower", "寻访台"},
    "iron_smelter": {"iron_smelter", "iron smelter", "治铁场"},
    "mill": {"mill", "磨坊"},
    "stone_workshop": {"stone_workshop", "stone workshop", "石工所"},
    "wood_workshop": {"wood_workshop", "wood workshop", "木工所"},
    "warehouse": {"warehouse", "仓库"},
    "residence": {"residence", "民居"},
}


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
        apply_team_snapshot_judgements(derived)
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
        state.city["upgradeable_buildings"] = (
            StateDeriver._merge_upgradeable_buildings(
                state.city,
                current_page=state.global_state.get("page_type"),
            )
        )
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

    @classmethod
    def _merge_upgradeable_buildings(
        cls,
        city: dict[str, Any],
        *,
        current_page: Any = None,
    ) -> list[dict[str, Any]]:
        """Merge explicit planning data with strict, current visual targets.

        A named visual target is authoritative for its current level and click
        bbox. Duplicate, malformed, or level-conflicting targets disappear
        entirely instead of falling back to stale explicit metadata.
        """
        observed_groups: dict[str, list[dict[str, Any]]] = {}
        raw_observed = city.get("buildings")
        if isinstance(raw_observed, list):
            for building in raw_observed:
                if not isinstance(building, dict):
                    continue
                name = cls._strict_building_name(building.get("name"))
                if name is None:
                    continue
                key = cls._canonical_building_target(name)
                observed_groups.setdefault(key, []).append(building)

        observed_candidates: dict[str, dict[str, Any]] = {}
        observed_identities: dict[str, dict[str, Any]] = {}
        ambiguous_targets: set[str] = set()
        blocked_targets: set[str] = set()
        for key, buildings in observed_groups.items():
            if len(buildings) != 1:
                ambiguous_targets.add(key)
                continue
            identity = cls._observed_building_identity(buildings[0])
            if identity is not None:
                observed_identities[key] = identity
            candidate = cls._observed_upgrade_candidate(buildings[0])
            if candidate is None:
                blocked_targets.add(key)
                continue
            observed_candidates[key] = candidate

        explicit_groups: dict[str, list[dict[str, Any]]] = {}
        explicit_conflicts: set[str] = set()
        raw_explicit = city.get("upgradeable_buildings")
        if isinstance(raw_explicit, list):
            for building in raw_explicit:
                if not isinstance(building, dict):
                    continue
                targets = cls._explicit_building_targets(building)
                if not targets:
                    continue
                if len(targets) != 1:
                    explicit_conflicts.update(targets)
                    continue
                key = next(iter(targets))
                explicit_groups.setdefault(key, []).append(building)

        dialog_candidate = cls._current_upgrade_dialog_candidate(
            city.get("upgrade_dialog"),
            current_page=current_page,
        )
        dialog_key = (
            cls._canonical_building_target(dialog_candidate["building_name"])
            if dialog_candidate is not None
            else None
        )

        current_snapshot_present = isinstance(raw_observed, list)
        if current_snapshot_present:
            # Once a current city frame exists, planning-only candidates are
            # not live semantic targets. Keep an explicit candidate only when
            # the current frame independently proves the same unique target;
            # its button is always overwritten by the current observation.
            ordered_keys = [
                key
                for key in explicit_groups
                if key in observed_candidates or key == dialog_key
            ]
            ordered_keys.extend(
                key for key in observed_candidates if key not in explicit_groups
            )
        else:
            ordered_keys = list(explicit_groups)
        merged: list[dict[str, Any]] = []
        for key in ordered_keys:
            if key in ambiguous_targets or key in explicit_conflicts:
                continue
            if key in blocked_targets and key != dialog_key:
                continue
            explicit_group = explicit_groups.get(key, [])
            explicit: dict[str, Any] | None = None
            if explicit_group:
                first = explicit_group[0]
                if any(item != first for item in explicit_group[1:]):
                    continue
                explicit = dict(first)
            observed = observed_candidates.get(key)
            if observed is None and key == dialog_key:
                observed = dialog_candidate
                current_identity = observed_identities.get(key)
                if (
                    current_identity is not None
                    and not cls._explicit_levels_match_observation(
                        current_identity,
                        observed,
                    )
                ):
                    continue
            if explicit is None and observed is None:
                continue
            if explicit is None:
                merged.append(dict(observed or {}))
                continue
            if observed is None:
                merged.append(explicit)
                continue
            if not cls._explicit_levels_match_observation(explicit, observed):
                continue
            combined = dict(explicit)
            combined.update(
                {
                    "building_name": observed["building_name"],
                    "current_level": observed["current_level"],
                    "target_level": observed["target_level"],
                }
            )
            observed_button = observed.get("upgrade_button")
            if isinstance(observed_button, dict):
                combined["upgrade_button"] = dict(observed_button)
            else:
                # A current terminal dialog can bind the final confirm target,
                # but it must never revive an explicit/stale entry button.
                combined.pop("upgrade_button", None)
            building_id = combined.get("building_id")
            if not isinstance(building_id, str) or not building_id.strip():
                combined["building_id"] = observed["building_id"]
            merged.append(combined)
        return merged

    @classmethod
    def _current_upgrade_dialog_candidate(
        cls,
        value: Any,
        *,
        current_page: Any,
    ) -> dict[str, Any] | None:
        if current_page not in {"building", "building_upgrade", "upgrade_dialog"}:
            return None
        if (
            not isinstance(value, dict)
            or value.get("visible") is not True
            or value.get("can_upgrade") is not True
        ):
            return None
        name = cls._strict_building_name(value.get("building_name"))
        current = value.get("current_level")
        target = value.get("next_level")
        if (
            name is None
            or isinstance(current, bool)
            or not isinstance(current, int)
            or current <= 0
            or isinstance(target, bool)
            or not isinstance(target, int)
            or target != current + 1
            or cls._strict_upgrade_button(value.get("confirm_button")) is None
        ):
            return None
        return {
            "building_id": name,
            "building_name": name,
            "current_level": current,
            "target_level": target,
        }

    @classmethod
    def _observed_upgrade_candidate(
        cls,
        building: dict[str, Any],
    ) -> dict[str, Any] | None:
        identity = cls._observed_building_identity(building)
        if identity is None:
            return None
        button = cls._strict_upgrade_button(building.get("upgrade_button"))
        if button is None:
            return None
        return {
            **identity,
            "upgrade_button": button,
        }

    @classmethod
    def _observed_building_identity(
        cls,
        building: dict[str, Any],
    ) -> dict[str, Any] | None:
        name = cls._strict_building_name(building.get("name"))
        level = building.get("level")
        if (
            name is None
            or isinstance(level, bool)
            or not isinstance(level, int)
            or level <= 0
        ):
            return None
        building_id = building.get("building_id")
        if not isinstance(building_id, str) or not building_id.strip():
            building_id = name
        return {
            "building_id": building_id.strip(),
            "building_name": name,
            "current_level": level,
            "target_level": level + 1,
        }

    @staticmethod
    def _strict_upgrade_button(value: Any) -> dict[str, Any] | None:
        if (
            not isinstance(value, dict)
            or value.get("visible") is not True
            or value.get("enabled") is not True
        ):
            return None
        bbox = value.get("bbox")
        if not isinstance(bbox, dict):
            return None
        coordinates: dict[str, int] = {}
        for field in ("x_min", "y_min", "x_max", "y_max"):
            coordinate = bbox.get(field)
            if isinstance(coordinate, bool) or not isinstance(coordinate, int):
                return None
            coordinates[field] = coordinate
        if not (
            0 <= coordinates["x_min"] < coordinates["x_max"] <= 1000
            and 0 <= coordinates["y_min"] < coordinates["y_max"] <= 1000
        ):
            return None
        return {"visible": True, "enabled": True, "bbox": coordinates}

    @classmethod
    def _explicit_building_targets(
        cls,
        building: dict[str, Any],
    ) -> set[str]:
        targets: set[str] = set()
        for field in ("building_name", "name"):
            name = cls._strict_building_name(building.get(field))
            if name is not None:
                targets.add(cls._canonical_building_target(name))
        building_id = cls._strict_building_name(building.get("building_id"))
        if building_id is not None:
            id_target = cls._canonical_building_target(building_id)
            # Known canonical IDs participate in conflict detection. Unknown
            # IDs may be opaque storage keys, so use them only when no name is
            # available.
            if id_target in BUILDING_ALIASES or not targets:
                targets.add(id_target)
        return targets

    @staticmethod
    def _explicit_levels_match_observation(
        explicit: dict[str, Any],
        observed: dict[str, Any],
    ) -> bool:
        expected_current = observed["current_level"]
        expected_target = observed["target_level"]
        for field in ("current_level", "level"):
            if field not in explicit:
                continue
            value = explicit.get(field)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value != expected_current
            ):
                return False
        if "target_level" in explicit:
            target = explicit.get("target_level")
            if (
                isinstance(target, bool)
                or not isinstance(target, int)
                or target != expected_target
            ):
                return False
        return True

    @staticmethod
    def _strict_building_name(value: Any) -> str | None:
        if not isinstance(value, str):
            return None
        stripped = value.strip()
        return stripped or None

    @classmethod
    def _canonical_building_target(cls, value: str) -> str:
        normalized = cls._normalize_building_term(value)
        for alias_key, aliases in BUILDING_ALIASES.items():
            normalized_aliases = {
                cls._normalize_building_term(alias_key),
                *(cls._normalize_building_term(alias) for alias in aliases),
            }
            if normalized in normalized_aliases:
                return alias_key
        return normalized

    @staticmethod
    def _normalize_building_term(value: Any) -> str:
        return " ".join(str(value).strip().lower().replace("_", " ").split())

    @staticmethod
    def _derive_primary_constraint(state: RuntimeState) -> None:
        host_team_id = state.main_lineup.get("current_host_team_id")
        for container in state.team_containers:
            if container.get("team_id") == host_team_id:
                readiness = container.get("combat_readiness_if_hosting_main", {})
                state.main_lineup["primary_constraint"] = readiness.get("primary_constraint", "unknown")
                state.main_lineup["combat_readiness_score"] = readiness.get("combat_readiness_score", 0)
                return
