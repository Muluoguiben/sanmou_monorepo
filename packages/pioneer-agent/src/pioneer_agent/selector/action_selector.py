from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, RuntimeState, SelectionResult
from pioneer_agent.knowledge.strategy_snapshot import StrategySnapshot, load_default_strategy_snapshot
from pioneer_agent.runtime.architecture_gates import LLMJudgeGate
from pioneer_agent.scoring.attack_land import score_attack_land
from pioneer_agent.scoring.recruit import score_recruit_soldiers
from pioneer_agent.scoring.transfer import score_transfer
from pioneer_agent.scoring.upgrade_building import score_upgrade_building
from pioneer_agent.scoring.wait import score_wait_for_resource, score_wait_for_stamina
from pioneer_agent.selector.candidate_generator import CandidateGenerator
from pioneer_agent.selector.filters import CandidateFilter
from pioneer_agent.selector.priority_rules import PriorityRules


class ActionSelector:
    def __init__(
        self,
        *,
        strategy_snapshot: StrategySnapshot | None = None,
        load_default_strategy: bool = True,
        llm_judge_gate: LLMJudgeGate | None = None,
    ) -> None:
        self.candidate_generator = CandidateGenerator()
        self.candidate_filter = CandidateFilter()
        self.priority_rules = PriorityRules()
        self.strategy_snapshot = strategy_snapshot
        if self.strategy_snapshot is None and load_default_strategy:
            self.strategy_snapshot = load_default_strategy_snapshot()
        self.llm_judge_gate = llm_judge_gate or LLMJudgeGate()

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
        llm_judge_gate = self.llm_judge_gate.evaluate(ranked, top_score_gap=top_score_gap)

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
                "llm_judge_gate": llm_judge_gate.to_dict(),
                "primary_constraint": state.main_lineup.get("primary_constraint", "unknown"),
                "phase_tag": state.global_state.get("phase_tag", "unknown"),
                "rejected_candidates": rejected[:10],
            },
            next_replan_time=next_replan_time,
        )

    def _score_candidates(self, candidates: list[CandidateAction]) -> list[CandidateAction]:
        ranked: list[CandidateAction] = []
        for candidate in candidates:
            candidate_for_scoring = self._candidate_with_strategy_snapshot(candidate)
            score_total, score_breakdown = self._score_candidate(candidate_for_scoring)
            ranked.append(
                candidate_for_scoring.model_copy(
                    update={
                        "score_total": score_total,
                        "score_breakdown": score_breakdown,
                    }
                )
            )
        ranked.sort(key=lambda item: item.score_total, reverse=True)
        return ranked

    def _candidate_with_strategy_snapshot(self, candidate: CandidateAction) -> CandidateAction:
        if candidate.action_type != ActionType.UPGRADE_BUILDING:
            return candidate
        enriched_params = self._with_strategy_snapshot(candidate.params)
        if enriched_params is candidate.params:
            return candidate
        return candidate.model_copy(update={"params": enriched_params})

    def _score_candidate(self, candidate: CandidateAction) -> tuple[float, dict[str, float]]:
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
        if candidate.action_type == ActionType.INSPECT_TEAM_READINESS:
            return ActionSelector._score_team_readiness(candidate.params)
        return 0.0, {}

    def _with_strategy_snapshot(self, params: dict[str, Any]) -> dict[str, Any]:
        if self.strategy_snapshot is None:
            return params
        priority = self._find_building_priority(params)
        if not priority:
            return params
        enriched = dict(params)
        enriched["strategy_priority"] = float(priority.get("priority", 0) or 0)
        enriched["strategy_key"] = priority.get("key")
        enriched["strategy_entry_ids"] = self._string_list(priority.get("entry_ids"))
        enriched["strategy_topic"] = priority.get("topic")
        enriched["strategy_source_ref"] = priority.get("source_ref")
        enriched["strategy_rationale"] = priority.get("rationale") or priority.get("rule") or ""
        return enriched

    def _find_building_priority(self, params: dict[str, Any]) -> dict[str, Any] | None:
        if self.strategy_snapshot is None:
            return None
        for term in (
            params.get("building_id"),
            params.get("building_name"),
            params.get("name"),
        ):
            match = self.strategy_snapshot.find_building_priority(str(term) if term else None)
            if match:
                return match
        return None

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
        if selected.action_type == ActionType.INSPECT_TEAM_READINESS:
            return current_time + timedelta(minutes=10)
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
    def _string_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [value] if value else []
        if isinstance(value, (list, tuple, set)):
            return [str(item) for item in value if item]
        return [str(value)]

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
            building_label = selected.params.get("building_name") or selected.params.get("building_id")
            reasons: list[str] = []
            if selected.params.get("resource_ready") is True:
                reasons.append("当前资源和前置条件满足")
            chapter_relevance = selected.params.get("chapter_relevance")
            if chapter_relevance == "complete_current_task":
                reasons.append("可完成当前章节任务")
            elif chapter_relevance == "prepare_next_chapter":
                reasons.append("可准备后续章节")
            if selected.params.get("strategy_rationale"):
                reasons.append(f"知识库依据：{selected.params.get('strategy_rationale')}")
            if not reasons:
                reasons.append("综合评分在可升级建筑中最高")
            normalized_reasons = [reason.rstrip("。") for reason in reasons]
            return f"{prefix}建议升级 {building_label}：" + "；".join(normalized_reasons) + "。"
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
        if selected.action_type == ActionType.INSPECT_TEAM_READINESS:
            review_items = selected.params.get("review_items") or []
            if review_items:
                return f"{prefix}已识别队伍 {selected.params.get('team_id')}，建议先检查：" + "、".join(review_items)
            return f"{prefix}已识别队伍 {selected.params.get('team_id')}，建议进入详情页补齐阵容信息后再判断。"
        return f"{prefix}根据 {selection_mode} 规则选择了当前最高分动作。"

    @staticmethod
    def _score_team_readiness(params: dict[str, Any]) -> tuple[float, dict[str, float]]:
        base = 64.0
        soldier_deficit_ratio = float(params.get("soldier_deficit_ratio") or 0)
        missing_detail_count = len(params.get("missing_detail_tabs") or [])
        review_count = len(params.get("review_items") or [])
        judgement = params.get("readiness_judgement") if isinstance(params.get("readiness_judgement"), dict) else {}
        judgement_status = str(judgement.get("overall_status") or "")
        judgement_weight = {
            "insufficient_basis": 14.0,
            "not_ready": 12.0,
            "needs_review": 8.0,
            "usable": 2.0,
            "ready": 0.0,
        }.get(judgement_status, 0.0)
        score = (
            base
            + min(soldier_deficit_ratio * 120, 24)
            + min(missing_detail_count * 1.5, 9)
            + min(review_count * 2, 8)
            + judgement_weight
        )
        return round(score, 2), {
            "advisor_team_domain": base,
            "soldier_deficit": round(min(soldier_deficit_ratio * 120, 24), 2),
            "missing_details": round(min(missing_detail_count * 1.5, 9), 2),
            "review_items": round(min(review_count * 2, 8), 2),
            "team_snapshot_judgement": judgement_weight,
        }
