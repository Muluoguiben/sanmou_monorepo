from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState, SelectionResult
from pioneer_agent.scoring.attack_land import score_attack_land
from pioneer_agent.scoring.recruit import score_recruit_soldiers
from pioneer_agent.scoring.transfer import score_transfer
from pioneer_agent.scoring.upgrade_building import score_upgrade_building
from pioneer_agent.scoring.wait import score_wait_for_resource, score_wait_for_stamina
from pioneer_agent.selector.candidate_generator import CandidateGenerator
from pioneer_agent.selector.filters import CandidateFilter
from pioneer_agent.selector.priority_rules import PriorityRules


class ActionSelector:
    def __init__(self) -> None:
        self.candidate_generator = CandidateGenerator()
        self.candidate_filter = CandidateFilter()
        self.priority_rules = PriorityRules()

    def select(self, state: RuntimeState) -> SelectionResult:
        generated = self.candidate_generator.generate(state)
        viable, rejected = self.candidate_filter.filter(state, generated)
        ranked = self._score_candidates(viable)
        priority_decision = self.priority_rules.choose(state, ranked)
        selected = priority_decision.selected_action
        next_replan_time = self._compute_next_replan_time(state, selected)
        top_score_gap = None
        if len(ranked) >= 2:
            top_score_gap = round(ranked[0].score_total - ranked[1].score_total, 2)

        return SelectionResult(
            selected_action=selected,
            ranked_actions=ranked,
            selection_reason={
                "selection_mode": priority_decision.selection_mode,
                "triggered_rules": priority_decision.triggered_rules,
                "summary": self._build_summary(
                    state,
                    selected,
                    priority_decision.selection_mode,
                    priority_decision.triggered_rules,
                ),
                "pipeline": {
                    "generated": len(generated),
                    "viable": len(viable),
                    "rejected": len(rejected),
                    "rejected_by_reason": dict(Counter(item["reason"] for item in rejected)),
                },
                "selected_score": selected.score_total if selected is not None else None,
                "top_score_gap": top_score_gap,
                "primary_constraint": state.main_lineup.get("primary_constraint", "unknown"),
                "phase_tag": state.global_state.get("phase_tag", "unknown"),
                "rejected_candidates": rejected[:10],
            },
            next_replan_time=next_replan_time,
        )

    def _score_candidates(self, candidates: list[CandidateAction]) -> list[CandidateAction]:
        ranked: list[CandidateAction] = []
        for candidate in candidates:
            score_total, score_breakdown = self._score_candidate(candidate)
            ranked.append(
                candidate.model_copy(
                    update={
                        "score_total": score_total,
                        "score_breakdown": score_breakdown,
                    }
                )
            )
        ranked.sort(key=lambda item: item.score_total, reverse=True)
        return ranked

    @staticmethod
    def _score_candidate(candidate: CandidateAction) -> tuple[float, dict[str, float]]:
        if candidate.action_type == ActionType.CLAIM_CHAPTER_REWARD:
            return 10_000.0, {"priority_rule": 10_000.0}
        if candidate.action_type == ActionType.UPGRADE_BUILDING:
            return score_upgrade_building(candidate.params)
        if candidate.action_type == ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM:
            return score_transfer(candidate.params)
        if candidate.action_type == ActionType.ATTACK_LAND:
            return score_attack_land(candidate.params)
        if candidate.action_type == ActionType.RECRUIT_SOLDIERS:
            return score_recruit_soldiers(candidate.params)
        if candidate.action_type == ActionType.WAIT_FOR_RESOURCE:
            return score_wait_for_resource(candidate.params)
        if candidate.action_type == ActionType.WAIT_FOR_STAMINA:
            return score_wait_for_stamina(candidate.params)
        return 0.0, {}

    def _compute_next_replan_time(self, state: RuntimeState, selected: CandidateAction | None) -> datetime:
        current_time = self._get_current_time(state) or datetime.utcnow()
        if selected is None:
            return current_time + timedelta(minutes=5)

        target_time = selected.timing.get("target_time") or selected.params.get("target_time")
        parsed_target_time = self._parse_datetime(target_time)
        if parsed_target_time is not None:
            return parsed_target_time

        if selected.action_type == ActionType.CLAIM_CHAPTER_REWARD:
            return current_time + timedelta(seconds=5)
        if selected.action_type == ActionType.RECRUIT_SOLDIERS:
            return current_time + timedelta(minutes=2)
        return current_time + timedelta(minutes=3)

    @staticmethod
    def _get_current_time(state: RuntimeState) -> datetime | None:
        return ActionSelector._parse_datetime(state.global_state.get("current_time"))

    @staticmethod
    def _parse_datetime(value: Any) -> datetime | None:
        if not value or not isinstance(value, str):
            return None
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None

    @staticmethod
    def _build_summary(
        state: RuntimeState,
        selected: CandidateAction | None,
        selection_mode: str,
        triggered_rules: list[str],
    ) -> str:
        if selected is None:
            return "当前没有可执行的高价值动作，建议等待下一次状态刷新。"

        constraint = state.main_lineup.get("primary_constraint", "unknown")
        prefix = f"命中规则 {', '.join(triggered_rules)}。 " if triggered_rules else ""

        if selected.action_type == ActionType.CLAIM_CHAPTER_REWARD:
            return f"{prefix}当前章节已经可领奖，优先领取第 {selected.params.get('chapter_id')} 章奖励以立刻推进节奏。"
        if selected.action_type == ActionType.ATTACK_LAND:
            return f"{prefix}当前可直接出征土地 {selected.params.get('land_id')}，其综合收益在所有可行动作里最高。"
        if selected.action_type == ActionType.TRANSFER_MAIN_LINEUP_TO_TEAM:
            return (
                f"{prefix}当前主约束是 {constraint}，目标容器 {selected.params.get('target_team_id')} 的体力/兵力承载更优，"
                "建议执行无损置换。"
            )
        if selected.action_type == ActionType.UPGRADE_BUILDING:
            return f"{prefix}建筑 {selected.params.get('building_id')} 可以直接升级，对当前章节推进和成长收益都更优。"
        if selected.action_type == ActionType.RECRUIT_SOLDIERS:
            return f"{prefix}队伍 {selected.params.get('team_id')} 兵力缺口明显，先补兵能更快恢复作战能力。"
        if selected.action_type == ActionType.WAIT_FOR_RESOURCE:
            minutes = round(int(selected.params.get("wait_seconds", 0) or 0) / 60, 1)
            return (
                f"{prefix}当前最短瓶颈是 {selected.params.get('target_resource')} 资源，等待约 {minutes} 分钟后可解锁"
                f" {selected.params.get('building_id')} 升级。"
            )
        if selected.action_type == ActionType.WAIT_FOR_STAMINA:
            minutes = round(int(selected.params.get("wait_seconds", 0) or 0) / 60, 1)
            return (
                f"{prefix}当前主力体力不足，等待约 {minutes} 分钟后可解锁土地 {selected.params.get('land_id')} 的出征窗口。"
            )
        return f"{prefix}根据 {selection_mode} 规则选择了当前最高分动作。"
