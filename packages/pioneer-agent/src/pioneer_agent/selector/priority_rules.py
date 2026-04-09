from __future__ import annotations

from dataclasses import dataclass

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState


@dataclass(slots=True)
class PriorityDecision:
    selected_action: CandidateAction | None
    selection_mode: str
    triggered_rules: list[str]


class PriorityRules:
    def choose(self, state: RuntimeState, ranked: list[CandidateAction]) -> PriorityDecision:
        if not ranked:
            return PriorityDecision(
                selected_action=None,
                selection_mode="no_viable_action",
                triggered_rules=[],
            )

        claim_action = self._first_of_type(ranked, ActionType.CLAIM_CHAPTER_REWARD)
        if claim_action is not None:
            return PriorityDecision(
                selected_action=claim_action,
                selection_mode="priority_rule.chapter_claimable",
                triggered_rules=["chapter_claimable"],
            )

        top_action = ranked[0]
        attack_action = self._first_of_type(ranked, ActionType.ATTACK_LAND)
        transfer_action = self._first_of_type(ranked, ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM)
        building_action = self._first_of_type(ranked, ActionType.UPGRADE_BUILDING)
        recruit_action = self._first_main_host_recruit(ranked)

        if transfer_action is not None and self._should_force_transfer(state, transfer_action, attack_action):
            return PriorityDecision(
                selected_action=transfer_action,
                selection_mode="priority_rule.transfer_to_preserve_tempo",
                triggered_rules=["transfer_to_preserve_tempo"],
            )

        if recruit_action is not None and self._should_force_main_host_recruit(state, top_action, recruit_action, attack_action):
            return PriorityDecision(
                selected_action=recruit_action,
                selection_mode="priority_rule.recruit_main_host_before_risky_attack",
                triggered_rules=["recruit_main_host_before_risky_attack"],
            )

        if building_action is not None and self._should_force_chapter_building(top_action, building_action):
            return PriorityDecision(
                selected_action=building_action,
                selection_mode="priority_rule.chapter_bottleneck_building",
                triggered_rules=["chapter_bottleneck_building"],
            )

        if attack_action is not None and self._should_preserve_attack_window(top_action, attack_action):
            return PriorityDecision(
                selected_action=attack_action,
                selection_mode="priority_rule.preserve_attack_window",
                triggered_rules=["preserve_attack_window"],
            )

        return PriorityDecision(
            selected_action=top_action,
            selection_mode="highest_score_after_scoring",
            triggered_rules=[],
        )

    @staticmethod
    def _first_of_type(ranked: list[CandidateAction], action_type: ActionType) -> CandidateAction | None:
        for action in ranked:
            if action.action_type == action_type:
                return action
        return None

    @staticmethod
    def _first_main_host_recruit(ranked: list[CandidateAction]) -> CandidateAction | None:
        for action in ranked:
            if action.action_type != ActionType.RECRUIT_SOLDIERS:
                continue
            if action.params.get("is_main_host"):
                return action
        return None

    @staticmethod
    def _should_force_transfer(
        state: RuntimeState,
        transfer_action: CandidateAction,
        attack_action: CandidateAction | None,
    ) -> bool:
        if state.main_lineup.get("primary_constraint") != "stamina":
            return False
        if float(transfer_action.params.get("target_stamina", 0)) < 15:
            return False
        if float(transfer_action.params.get("target_stamina", 0)) - float(transfer_action.params.get("current_stamina", 0)) < 8:
            return False
        if not transfer_action.params.get("carrier_available"):
            return False
        if attack_action is not None and attack_action.score_total >= transfer_action.score_total + 12:
            return False
        return True

    @staticmethod
    def _should_force_main_host_recruit(
        state: RuntimeState,
        top_action: CandidateAction,
        recruit_action: CandidateAction,
        attack_action: CandidateAction | None,
    ) -> bool:
        deficit = float(recruit_action.params.get("soldier_deficit", 0))
        max_soldiers = max(float(recruit_action.params.get("max_soldiers", 1) or 1), 1.0)
        deficit_ratio = deficit / max_soldiers

        if deficit <= 0 or float(recruit_action.params.get("reserve_troops_available", 0)) <= 0:
            return False
        if top_action.action_type == ActionType.RECRUIT_SOLDIERS:
            return False
        if deficit_ratio < 0.2 and state.main_lineup.get("primary_constraint") != "soldiers":
            return False

        if top_action.action_type in {
            ActionType.WAIT_FOR_RESOURCE,
            ActionType.WAIT_FOR_STAMINA,
            ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM,
        }:
            return True

        if attack_action is None:
            return top_action.score_total - recruit_action.score_total <= 8

        if top_action.action_type != ActionType.ATTACK_LAND:
            return top_action.score_total - recruit_action.score_total <= 6

        win_rate = float(attack_action.params.get("expected_win_rate", 0))
        expected_loss = float(attack_action.params.get("expected_battle_loss", 0))
        if win_rate >= 0.95 and expected_loss <= 1800:
            return False
        return True

    @staticmethod
    def _should_force_chapter_building(top_action: CandidateAction, building_action: CandidateAction) -> bool:
        if building_action.params.get("chapter_relevance") != "complete_current_task":
            return False
        if top_action.action_type == ActionType.UPGRADE_BUILDING:
            return False
        if top_action.action_type in {ActionType.WAIT_FOR_RESOURCE, ActionType.WAIT_FOR_STAMINA, ActionType.RECRUIT_SOLDIERS}:
            return True
        return top_action.score_total - building_action.score_total <= 12

    @staticmethod
    def _should_preserve_attack_window(top_action: CandidateAction, attack_action: CandidateAction) -> bool:
        if top_action.action_type == ActionType.ATTACK_LAND:
            return False
        if attack_action.score_total < 90:
            return False
        if float(attack_action.params.get("expected_win_rate", 0)) < 0.95:
            return False
        if float(attack_action.params.get("expected_battle_loss", 0)) > 2000:
            return False
        return top_action.score_total - attack_action.score_total <= 18
