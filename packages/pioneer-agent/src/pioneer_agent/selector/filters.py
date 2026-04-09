from __future__ import annotations

from typing import Any

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState
from pioneer_agent.scoring.transfer import is_transfer_candidate_valid


class CandidateFilter:
    def filter(
        self,
        state: RuntimeState,
        candidates: list[CandidateAction],
    ) -> tuple[list[CandidateAction], list[dict[str, Any]]]:
        viable: list[CandidateAction] = []
        rejected: list[dict[str, Any]] = []

        for candidate in candidates:
            reason = self._reject_reason(state, candidate)
            if reason is None:
                viable.append(candidate)
                continue

            rejected.append(
                {
                    "action_id": candidate.action_id,
                    "action_type": candidate.action_type.value,
                    "reason": reason,
                    "params": candidate.params,
                }
            )

        return viable, rejected

    def _reject_reason(self, state: RuntimeState, candidate: CandidateAction) -> str | None:
        if candidate.action_type == ActionType.CLAIM_CHAPTER_REWARD:
            return None if state.progress.get("chapter_claimable") else "chapter_not_claimable"

        if candidate.action_type == ActionType.UPGRADE_BUILDING:
            return self._reject_upgrade(candidate)

        if candidate.action_type == ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM:
            return self._reject_transfer(state, candidate)

        if candidate.action_type == ActionType.ATTACK_LAND:
            return self._reject_attack(state, candidate)

        if candidate.action_type == ActionType.RECRUIT_SOLDIERS:
            return self._reject_recruit(candidate)

        if candidate.action_type == ActionType.WAIT_FOR_RESOURCE:
            return self._reject_wait_for_resource(candidate)

        if candidate.action_type == ActionType.WAIT_FOR_STAMINA:
            return self._reject_wait_for_stamina(candidate)

        return None

    @staticmethod
    def _reject_upgrade(candidate: CandidateAction) -> str | None:
        blocked_by = candidate.params.get("blocked_by") or []
        if blocked_by:
            return "building_blocked"
        if not candidate.params.get("resource_ready", True):
            return "insufficient_resources"
        return None

    @staticmethod
    def _reject_transfer(state: RuntimeState, candidate: CandidateAction) -> str | None:
        current_host = None
        target_host = None
        from_team_id = candidate.params.get("from_team_id")
        target_team_id = candidate.params.get("target_team_id")

        for container in state.team_containers:
            if container.get("team_id") == from_team_id:
                current_host = container
            if container.get("team_id") == target_team_id:
                target_host = container

        if current_host is None or target_host is None:
            return "missing_container"
        if not is_transfer_candidate_valid(current_host, target_host, state.swap_window, state.carrier_pool):
            return "invalid_transfer_state"
        return None

    @staticmethod
    def _reject_attack(state: RuntimeState, candidate: CandidateAction) -> str | None:
        if candidate.params.get("occupied"):
            return "land_occupied"
        if candidate.params.get("reachable") is False:
            return "land_unreachable"
        if float(candidate.params.get("expected_win_rate", 0)) < 0.9:
            return "win_rate_below_threshold"
        if float(candidate.params.get("current_stamina", 0)) < float(candidate.params.get("required_stamina", 0)):
            return "insufficient_stamina"

        team_id = candidate.params.get("team_id")
        for container in state.team_containers:
            if container.get("team_id") != team_id:
                continue
            if container.get("status") not in {None, "idle", "ready"}:
                return "team_busy"
            if container.get("can_march_now") is False:
                return "team_cannot_march"
            break

        return None

    @staticmethod
    def _reject_recruit(candidate: CandidateAction) -> str | None:
        if float(candidate.params.get("soldier_deficit", 0)) <= 0:
            return "no_soldier_deficit"
        if float(candidate.params.get("reserve_troops_available", 0)) <= 0:
            return "no_reserve_troops"
        if float(candidate.params.get("recruit_amount", 0)) <= 0:
            return "recruit_amount_zero"
        if candidate.params.get("status") == "recruiting":
            return "already_recruiting"
        if candidate.params.get("can_recruit_now") is False:
            return "team_cannot_recruit"
        return None

    @staticmethod
    def _reject_wait_for_resource(candidate: CandidateAction) -> str | None:
        if float(candidate.params.get("missing_amount", 0)) <= 0:
            return "resource_gap_missing"
        if int(candidate.params.get("wait_seconds", 0) or 0) <= 0:
            return "resource_already_ready"
        if not candidate.params.get("unlock_action_type"):
            return "missing_unlock_target"
        return None

    @staticmethod
    def _reject_wait_for_stamina(candidate: CandidateAction) -> str | None:
        if int(candidate.params.get("wait_seconds", 0) or 0) <= 0:
            return "stamina_already_ready"
        if float(candidate.params.get("target_stamina", 0)) <= float(candidate.params.get("current_stamina", 0)):
            return "stamina_already_ready"
        if not candidate.params.get("unlock_action_type"):
            return "missing_unlock_target"
        return None
