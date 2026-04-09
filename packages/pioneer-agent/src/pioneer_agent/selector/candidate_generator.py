from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState


class CandidateGenerator:
    def generate(self, state: RuntimeState) -> list[CandidateAction]:
        candidates: list[CandidateAction] = []
        candidates.extend(self._generate_claim_actions(state))
        candidates.extend(self._generate_upgrade_actions(state))
        candidates.extend(self._generate_transfer_actions(state))
        candidates.extend(self._generate_attack_actions(state))
        candidates.extend(self._generate_recruit_actions(state))
        candidates.extend(self._generate_wait_for_resource_actions(state))
        candidates.extend(self._generate_wait_for_stamina_actions(state))
        return candidates

    def _generate_claim_actions(self, state: RuntimeState) -> list[CandidateAction]:
        if not state.progress.get("chapter_claimable"):
            return []

        chapter_id = state.progress.get("current_chapter_id")
        return [
            CandidateAction(
                action_id=self._build_action_id(ActionType.CLAIM_CHAPTER_REWARD, chapter_id or "current"),
                action_type=ActionType.CLAIM_CHAPTER_REWARD,
                params={"chapter_id": chapter_id},
                preconditions=["chapter_claimable"],
                expected_gain={"chapter_progress": 1},
                source_state_refs=["progress.chapter_claimable", "progress.current_chapter_id"],
            )
        ]

    def _generate_upgrade_actions(self, state: RuntimeState) -> list[CandidateAction]:
        actions: list[CandidateAction] = []
        for building in state.city.get("upgradeable_buildings", []):
            building_id = building.get("building_id")
            target_level = building.get("target_level")
            shortages = self._positive_float_map(building.get("resource_shortages", {}))
            total_shortage = round(sum(shortages.values()), 2)

            actions.append(
                CandidateAction(
                    action_id=self._build_action_id(ActionType.UPGRADE_BUILDING, building_id or "unknown", target_level or "next"),
                    action_type=ActionType.UPGRADE_BUILDING,
                    params={
                        "building_id": building_id,
                        "target_level": target_level,
                        "chapter_relevance": building.get("chapter_relevance", "low_relevance"),
                        "economy_gain": float(building.get("economy_gain", 0)),
                        "battle_support_gain": float(building.get("battle_support_gain", 0)),
                        "resource_cost_penalty": float(building.get("resource_cost_penalty", 0)),
                        "blocked_by": list(building.get("blocked_by", [])),
                        "resource_shortages": shortages,
                        "resource_ready": not shortages,
                        "wait_seconds_for_resources": building.get("wait_seconds_for_resources"),
                        "wait_target_resource": building.get("wait_target_resource"),
                        "cost": building.get("cost", {}),
                    },
                    preconditions=["building_upgradeable", "resources_satisfied", "prerequisites_satisfied"],
                    expected_gain={
                        "chapter_relevance": building.get("chapter_relevance"),
                        "economy_gain": building.get("economy_gain", 0),
                        "battle_support_gain": building.get("battle_support_gain", 0),
                    },
                    expected_cost={
                        "cost": building.get("cost", {}),
                        "resource_total_shortage": total_shortage,
                    },
                    source_state_refs=[
                        "city.upgradeable_buildings",
                        "economy.resources",
                        "economy.income_per_hour",
                    ],
                )
            )
        return actions

    def _generate_transfer_actions(self, state: RuntimeState) -> list[CandidateAction]:
        current_host = self._get_current_host_container(state)
        if current_host is None:
            return []

        actions: list[CandidateAction] = []
        for target in state.team_containers:
            actions.append(
                CandidateAction(
                    action_id=self._build_action_id(
                        ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
                        current_host.get("team_id", "unknown"),
                        target.get("team_id", "unknown"),
                    ),
                    action_type=ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
                    params={
                        "from_team_id": current_host.get("team_id"),
                        "target_team_id": target.get("team_id"),
                        "current_stamina": float(current_host.get("container_stamina", 0)),
                        "target_stamina": float(target.get("container_stamina", 0)),
                        "current_soldiers": float(current_host.get("soldiers", 0)),
                        "target_soldiers": float(target.get("soldiers", 0)),
                        "current_position_context": current_host.get("position_context"),
                        "target_position_context": target.get("position_context"),
                        "current_host_score": float(current_host.get("host_score", 0)),
                        "target_host_score": float(target.get("host_score", 0)),
                        "carrier_available": any(carrier.get("usable_for_swap") for carrier in state.carrier_pool),
                        "hours_remaining": state.swap_window.get("hours_remaining"),
                    },
                    preconditions=["swap_window_enabled", "target_container_hostable", "carrier_path_ready"],
                    expected_gain={
                        "stamina_delta": round(
                            float(target.get("container_stamina", 0)) - float(current_host.get("container_stamina", 0)),
                            2,
                        ),
                        "soldier_delta": round(
                            float(target.get("soldiers", 0)) - float(current_host.get("soldiers", 0)),
                            2,
                        ),
                        "host_score_delta": round(
                            float(target.get("host_score", 0)) - float(current_host.get("host_score", 0)),
                            2,
                        ),
                    },
                    risk={"macro_action": True},
                    source_state_refs=["swap_window.enabled", "team_containers", "carrier_pool"],
                )
            )
        return actions

    def _generate_attack_actions(self, state: RuntimeState) -> list[CandidateAction]:
        current_host = self._get_current_host_container(state)
        if current_host is None:
            return []

        team_id = state.main_lineup.get("current_host_team_id")
        actions: list[CandidateAction] = []
        for land in state.map_state.get("candidate_lands", []):
            required_stamina = int(land.get("required_stamina", land.get("stamina_cost", 15)) or 15)
            actions.append(
                CandidateAction(
                    action_id=self._build_action_id(ActionType.ATTACK_LAND, team_id or "unknown", land.get("land_id", "unknown")),
                    action_type=ActionType.ATTACK_LAND,
                    params={
                        "team_id": team_id,
                        "land_id": land.get("land_id"),
                        "level": int(land.get("level", 0) or 0),
                        "reachable": land.get("reachable", True),
                        "occupied": land.get("occupied", False),
                        "yield_per_hour": float(land.get("yield_per_hour", 0)),
                        "chapter_relevance": land.get("chapter_relevance", "none"),
                        "strategic_tags": list(land.get("strategic_tags", [])),
                        "expected_battle_loss": float(land.get("expected_battle_loss", 0)),
                        "march_seconds": float(land.get("march_seconds", 0)),
                        "expected_win_rate": float(land.get("expected_win_rate", 0)),
                        "required_stamina": required_stamina,
                        "current_stamina": float(current_host.get("container_stamina", 0)),
                        "level_fit": land.get("level_fit", "unknown"),
                    },
                    preconditions=["target_land_reachable", "target_land_safe", "current_host_can_march"],
                    expected_gain={
                        "yield_per_hour": land.get("yield_per_hour", 0),
                        "chapter_relevance": land.get("chapter_relevance", "none"),
                    },
                    expected_cost={
                        "expected_battle_loss": land.get("expected_battle_loss", 0),
                        "required_stamina": required_stamina,
                        "march_seconds": land.get("march_seconds", 0),
                    },
                    risk={"expected_win_rate": land.get("expected_win_rate", 0)},
                    source_state_refs=["map_state.candidate_lands", "main_lineup.current_host_team_id", "team_containers"],
                )
            )
        return actions

    def _generate_recruit_actions(self, state: RuntimeState) -> list[CandidateAction]:
        reserve_troops = float(state.economy.get("reserve_troops", 0) or 0)
        actions: list[CandidateAction] = []

        for team in self._iter_team_contexts(state):
            max_soldiers = float(team.get("max_soldiers", 0) or 0)
            soldiers = float(team.get("soldiers", 0) or 0)
            if max_soldiers <= 0:
                continue

            deficit = max(max_soldiers - soldiers, 0)
            if deficit <= 0:
                continue

            recruit_amount = min(deficit, reserve_troops) if reserve_troops > 0 else deficit
            actions.append(
                CandidateAction(
                    action_id=self._build_action_id(ActionType.RECRUIT_SOLDIERS, team.get("team_id", "unknown")),
                    action_type=ActionType.RECRUIT_SOLDIERS,
                    params={
                        "team_id": team.get("team_id"),
                        "soldiers": soldiers,
                        "max_soldiers": max_soldiers,
                        "soldier_deficit": round(deficit, 2),
                        "recruit_amount": round(recruit_amount, 2),
                        "reserve_troops_available": reserve_troops,
                        "is_main_host": team.get("team_id") == state.main_lineup.get("current_host_team_id"),
                        "primary_constraint": state.main_lineup.get("primary_constraint"),
                        "status": team.get("status"),
                        "can_recruit_now": team.get("can_recruit_now", True),
                        "recruit_finish_time": team.get("recruit_finish_time"),
                    },
                    preconditions=["team_exists", "soldier_deficit_positive", "reserve_troops_available"],
                    expected_gain={
                        "soldier_fill_ratio_after": round((soldiers + recruit_amount) / max_soldiers, 4),
                        "combat_support": team.get("team_id") == state.main_lineup.get("current_host_team_id"),
                    },
                    expected_cost={"reserve_troops": round(recruit_amount, 2)},
                    source_state_refs=["team_containers", "teams", "economy.reserve_troops"],
                )
            )
        return actions

    def _generate_wait_for_resource_actions(self, state: RuntimeState) -> list[CandidateAction]:
        actions: list[CandidateAction] = []
        current_time = self._get_current_time(state)
        for building in state.city.get("upgradeable_buildings", []):
            shortages = self._positive_float_map(building.get("resource_shortages", {}))
            if not shortages:
                continue

            wait_target_resource = building.get("wait_target_resource") or min(shortages, key=shortages.get)
            missing_amount = float(shortages.get(wait_target_resource, 0))
            wait_seconds = self._coerce_positive_int(building.get("wait_seconds_for_resources"))
            if wait_seconds is None:
                continue

            target_time = None
            if current_time is not None:
                target_time = (current_time + timedelta(seconds=wait_seconds)).isoformat()

            actions.append(
                CandidateAction(
                    action_id=self._build_action_id(
                        ActionType.WAIT_FOR_RESOURCE,
                        building.get("building_id", "unknown"),
                        wait_target_resource,
                    ),
                    action_type=ActionType.WAIT_FOR_RESOURCE,
                    params={
                        "unlock_action_type": ActionType.UPGRADE_BUILDING.value,
                        "building_id": building.get("building_id"),
                        "target_level": building.get("target_level"),
                        "chapter_relevance": building.get("chapter_relevance", "low_relevance"),
                        "target_resource": wait_target_resource,
                        "missing_amount": missing_amount,
                        "wait_seconds": wait_seconds,
                        "target_time": target_time,
                        "unlock_score_hint": self._estimate_upgrade_value(building),
                    },
                    preconditions=["higher_value_action_blocked_by_resource"],
                    expected_gain={"unlock_action_type": ActionType.UPGRADE_BUILDING.value},
                    expected_cost={"idle_seconds": wait_seconds},
                    timing={"target_time": target_time},
                    interruptibility={"interruptible": True},
                    source_state_refs=["city.upgradeable_buildings", "economy.resources", "economy.income_per_hour"],
                )
            )
        return actions

    def _generate_wait_for_stamina_actions(self, state: RuntimeState) -> list[CandidateAction]:
        current_host = self._get_current_host_container(state)
        if current_host is None:
            return []

        current_stamina = float(current_host.get("container_stamina", 0))
        regen_per_hour = float(state.swap_constraints.get("stamina_regen_per_hour", 12) or 12)
        if regen_per_hour <= 0:
            return []

        current_time = self._get_current_time(state)
        actions: list[CandidateAction] = []
        for land in state.map_state.get("candidate_lands", []):
            if land.get("occupied") or land.get("reachable") is False:
                continue
            if float(land.get("expected_win_rate", 0)) < 0.9:
                continue

            required_stamina = int(land.get("required_stamina", land.get("stamina_cost", 15)) or 15)
            stamina_gap = max(required_stamina - current_stamina, 0)
            if stamina_gap <= 0:
                continue

            wait_seconds = int(round(stamina_gap / regen_per_hour * 3600))
            target_time = None
            if current_time is not None:
                target_time = (current_time + timedelta(seconds=wait_seconds)).isoformat()

            actions.append(
                CandidateAction(
                    action_id=self._build_action_id(
                        ActionType.WAIT_FOR_STAMINA,
                        current_host.get("team_id", "unknown"),
                        land.get("land_id", "unknown"),
                    ),
                    action_type=ActionType.WAIT_FOR_STAMINA,
                    params={
                        "team_id": current_host.get("team_id"),
                        "land_id": land.get("land_id"),
                        "unlock_action_type": ActionType.ATTACK_LAND.value,
                        "unlock_land_level": int(land.get("level", 0) or 0),
                        "unlock_chapter_relevance": land.get("chapter_relevance", "none"),
                        "wait_seconds": wait_seconds,
                        "target_time": target_time,
                        "current_stamina": current_stamina,
                        "target_stamina": required_stamina,
                        "stamina_gap": stamina_gap,
                        "unlock_score_hint": self._estimate_land_value(land),
                    },
                    preconditions=["higher_value_action_blocked_by_stamina"],
                    expected_gain={"unlock_action_type": ActionType.ATTACK_LAND.value, "land_id": land.get("land_id")},
                    expected_cost={"idle_seconds": wait_seconds},
                    timing={"target_time": target_time},
                    interruptibility={"interruptible": True},
                    source_state_refs=["team_containers", "map_state.candidate_lands", "swap_constraints.stamina_regen_per_hour"],
                )
            )
        return actions

    @staticmethod
    def _build_action_id(action_type: ActionType, *parts: object) -> str:
        normalized_parts = [str(part) for part in parts if part is not None and str(part) != ""]
        return "::".join([action_type.value, *normalized_parts])

    @staticmethod
    def _positive_float_map(payload: Any) -> dict[str, float]:
        if not isinstance(payload, dict):
            return {}
        result: dict[str, float] = {}
        for key, value in payload.items():
            amount = float(value or 0)
            if amount > 0:
                result[str(key)] = round(amount, 2)
        return result

    @staticmethod
    def _coerce_positive_int(value: Any) -> int | None:
        if value is None:
            return None
        amount = int(round(float(value)))
        return amount if amount > 0 else None

    @staticmethod
    def _get_current_host_container(state: RuntimeState) -> dict[str, Any] | None:
        host_team_id = state.main_lineup.get("current_host_team_id")
        for container in state.team_containers:
            if container.get("team_id") == host_team_id:
                return container
        return None

    @staticmethod
    def _iter_team_contexts(state: RuntimeState) -> list[dict[str, Any]]:
        merged: dict[Any, dict[str, Any]] = {}
        for payload in state.team_containers:
            team_id = payload.get("team_id")
            if team_id is None:
                continue
            merged[team_id] = dict(payload)

        for payload in state.teams:
            team_id = payload.get("team_id")
            if team_id is None:
                continue
            merged.setdefault(team_id, {}).update(payload)

        return list(merged.values())

    @staticmethod
    def _get_current_time(state: RuntimeState) -> datetime | None:
        raw_value = state.global_state.get("current_time")
        if not raw_value or not isinstance(raw_value, str):
            return None
        try:
            return datetime.fromisoformat(raw_value)
        except ValueError:
            return None

    @staticmethod
    def _estimate_upgrade_value(building: dict[str, Any]) -> float:
        chapter_relevance = building.get("chapter_relevance")
        chapter_gain = 42.0 if chapter_relevance == "complete_current_task" else 22.0 if chapter_relevance == "prepare_next_chapter" else 10.0
        return round(
            chapter_gain
            + float(building.get("economy_gain", 0))
            + float(building.get("battle_support_gain", 0))
            - float(building.get("resource_cost_penalty", 0)),
            2,
        )

    @staticmethod
    def _estimate_land_value(land: dict[str, Any]) -> float:
        chapter_gain = 26.0 if land.get("chapter_relevance") in {"advance_current_task", "complete_current_task"} else 10.0
        strategic_gain = len(land.get("strategic_tags", [])) * 4.0
        loss_penalty = float(land.get("expected_battle_loss", 0)) / 120
        risk_penalty = (1 - float(land.get("expected_win_rate", 1.0))) * 100
        return round(float(land.get("yield_per_hour", 0)) / 12 + chapter_gain + strategic_gain - loss_penalty - risk_penalty, 2)
