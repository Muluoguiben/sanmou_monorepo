"""Metric computation for offline MCP transcripts."""
from __future__ import annotations

from collections import Counter
from datetime import timedelta
import math
from typing import Iterable

from pioneer_agent.mcp_eval.models import (
    AggregateMetrics,
    BatteryManifest,
    MetricScores,
    ObservabilityMetrics,
    ObservedScenario,
    ScenarioManifest,
    ScenarioScoreReport,
    SensoriumMetrics,
    StaticScenarioTranscript,
)


def fold_observed(transcript: StaticScenarioTranscript) -> ObservedScenario:
    observed = ObservedScenario()
    for call in transcript.calls:
        result = call.result_summary
        updates: dict[str, object] = {}
        if result.state_fields is not None:
            state_fields = dict(observed.state_fields)
            state_fields.update(result.state_fields)
            updates["state_fields"] = state_fields
        if result.unknown_domains is not None:
            updates["unknown_domains"] = result.unknown_domains
        if result.candidates is not None:
            updates["candidates"] = result.candidates
        if result.no_change_recognized is not None:
            updates["no_change_recognized"] = result.no_change_recognized
        if result.terminal_outcome is not None:
            updates["terminal_outcome"] = result.terminal_outcome
        if result.stop_reason is not None:
            updates["stop_reason"] = result.stop_reason
        if result.journal_steps is not None:
            updates["journal_steps"] = result.journal_steps
        if updates:
            observed = observed.model_copy(update=updates)
    return observed


def score_scenario(
    manifest: ScenarioManifest,
    transcript: StaticScenarioTranscript,
) -> ScenarioScoreReport:
    observed = fold_observed(transcript)
    sensorium = sensorium_metrics(manifest, transcript)
    observability = observability_metrics(transcript)
    if manifest.split == "holdout":
        scores = MetricScores()
        scored = False
    else:
        assert manifest.expectations is not None
        expected = manifest.expectations
        candidates = {item.action_type: item for item in observed.candidates}
        scores = MetricScores(
            state_field_accuracy=_mapping_accuracy(expected.state_fields, observed.state_fields),
            unknown_calibration=_set_accuracy(expected.unknown_domains, observed.unknown_domains),
            tool_call_coverage=_set_recall(
                expected.required_tool_calls,
                [call.tool_name for call in transcript.calls],
            ),
            proposal_grounding=_proposal_grounding(expected.grounded_proposals, candidates),
            blocked_action_correctness=_blocked_correctness(expected.blocked_actions, candidates),
            verifier_readiness=_verifier_readiness(expected.verifier_readiness, candidates),
            no_change_recognition=(
                1.0
                if expected.no_change_recognized is None
                or expected.no_change_recognized == observed.no_change_recognized
                else 0.0
            ),
            recovery_stop_correctness=(
                1.0
                if expected.terminal_outcome == observed.terminal_outcome
                and expected.stop_reason == observed.stop_reason
                else 0.0
            ),
            journal_plan_adherence=_ordered_subsequence_score(
                expected.journal_plan, observed.journal_steps
            ),
        )
        scored = True
    return ScenarioScoreReport(
        scenario_id=manifest.scenario_id,
        split=manifest.split,
        scored=scored,
        scores=scores,
        sensorium=sensorium,
        observability=observability,
        observed=observed,
    )


def sensorium_metrics(
    manifest: ScenarioManifest,
    transcript: StaticScenarioTranscript,
) -> SensoriumMetrics:
    critical = manifest.sensorium.critical_domains
    queried = sorted({domain for call in transcript.calls for domain in call.domains_queried})
    last_refresh = {}
    for call in transcript.calls:
        for domain, observed_at in call.domain_observed_at.items():
            previous = last_refresh.get(domain)
            if previous is None or observed_at > previous:
                last_refresh[domain] = observed_at
    final_call = transcript.calls[-1]
    end_at = final_call.started_at + timedelta(milliseconds=final_call.duration_ms)
    ages: dict[str, float | None] = {}
    stale: list[str] = []
    never: list[str] = []
    for domain in critical:
        refreshed_at = last_refresh.get(domain)
        if refreshed_at is None:
            ages[domain] = None
            never.append(domain)
            continue
        age = max(0.0, (end_at - refreshed_at).total_seconds())
        ages[domain] = round(age, 6)
        if age > manifest.sensorium.stale_after_seconds[domain]:
            stale.append(domain)

    missed_before_failure: list[str] = []
    if transcript.failure_at is not None:
        for domain in manifest.sensorium.required_before_failure:
            refreshed_at = last_refresh.get(domain)
            threshold = manifest.sensorium.stale_after_seconds[domain]
            if (
                refreshed_at is None
                or refreshed_at > transcript.failure_at
                or (transcript.failure_at - refreshed_at).total_seconds() > threshold
            ):
                missed_before_failure.append(domain)

    coverage = (len(set(critical) & set(queried)) / len(critical)) if critical else 1.0
    return SensoriumMetrics(
        queried_domains=queried,
        never_queried_critical_domains=never,
        stale_critical_domains_at_end=stale,
        seconds_since_refresh_at_end=ages,
        missed_risk_domains_before_failure=missed_before_failure,
        critical_domain_query_coverage=coverage,
    )


def observability_metrics(transcript: StaticScenarioTranscript) -> ObservabilityMetrics:
    durations = sorted(call.duration_ms for call in transcript.calls)
    count = len(durations)
    success_count = sum(1 for call in transcript.calls if call.success)
    rank = max(0, math.ceil(0.95 * count) - 1)
    per_tool = Counter(call.tool_name for call in transcript.calls)
    return ObservabilityMetrics(
        tool_call_count=count,
        successful_tool_call_count=success_count,
        failed_tool_call_count=count - success_count,
        success_rate=success_count / count if count else 1.0,
        total_duration_ms=sum(durations),
        mean_duration_ms=sum(durations) / count if count else 0.0,
        p95_duration_ms=durations[rank] if count else 0.0,
        tool_cost_units=sum(call.tool_cost_units for call in transcript.calls),
        vision_cost_units=sum(call.vision_cost_units for call in transcript.calls),
        per_tool_call_count=dict(sorted(per_tool.items())),
        observation_ref_count=sum(len(call.observation_refs) for call in transcript.calls),
        trace_ref_count=sum(len(call.trace_refs) for call in transcript.calls),
    )


def aggregate_reports(
    battery: BatteryManifest, reports: list[ScenarioScoreReport]
) -> AggregateMetrics:
    scored = [report for report in reports if report.scored]
    score_fields = tuple(MetricScores.model_fields)
    means: dict[str, float] = {}
    for field_name in score_fields:
        values = [getattr(report.scores, field_name) for report in scored]
        numeric = [value for value in values if value is not None]
        means[field_name] = sum(numeric) / len(numeric) if numeric else 0.0
    return AggregateMetrics(
        scenario_count=len(reports),
        scored_generation_count=len(scored),
        unscored_holdout_count=sum(1 for report in reports if report.split == "holdout"),
        mean_scores=means,
        total_tool_calls=sum(report.observability.tool_call_count for report in reports),
        total_duration_ms=sum(report.observability.total_duration_ms for report in reports),
        total_tool_cost_units=sum(report.observability.tool_cost_units for report in reports),
        total_vision_cost_units=sum(report.observability.vision_cost_units for report in reports),
        mean_critical_domain_query_coverage=(
            sum(report.sensorium.critical_domain_query_coverage for report in reports)
            / len(reports)
        ),
        scenarios_with_missed_risk_domains=sum(
            bool(report.sensorium.missed_risk_domains_before_failure)
            for report in reports
        ),
    )


def _mapping_accuracy(expected: dict[str, object], actual: dict[str, object]) -> float:
    if not expected:
        return 1.0
    return sum(actual.get(key) == value for key, value in expected.items()) / len(expected)


def _set_accuracy(expected: Iterable[str], actual: Iterable[str]) -> float:
    expected_set = set(expected)
    actual_set = set(actual)
    union = expected_set | actual_set
    return len(expected_set & actual_set) / len(union) if union else 1.0


def _set_recall(expected: Iterable[str], actual: Iterable[str]) -> float:
    expected_set = set(expected)
    return len(expected_set & set(actual)) / len(expected_set) if expected_set else 1.0


def _proposal_grounding(expected: list[str], candidates: dict[str, object]) -> float:
    if not expected:
        return 1.0
    grounded = 0
    for action in expected:
        candidate = candidates.get(action)
        if candidate is not None and getattr(candidate, "evidence_refs", []):
            grounded += 1
    return grounded / len(expected)


def _blocked_correctness(expected: dict[str, list[str]], candidates: dict[str, object]) -> float:
    if not expected:
        return 1.0
    correct = 0
    for action, blockers in expected.items():
        candidate = candidates.get(action)
        if (
            candidate is not None
            and getattr(candidate, "blocked", False)
            and getattr(candidate, "executable", True) is False
            and set(blockers).issubset(getattr(candidate, "blockers", []))
        ):
            correct += 1
    return correct / len(expected)


def _verifier_readiness(expected: dict[str, bool], candidates: dict[str, object]) -> float:
    if not expected:
        return 1.0
    correct = 0
    for action, readiness in expected.items():
        candidate = candidates.get(action)
        if candidate is not None and getattr(candidate, "verifier_ready", None) is readiness:
            correct += 1
    return correct / len(expected)


def _ordered_subsequence_score(expected: list[str], actual: list[str]) -> float:
    if not expected:
        return 1.0
    cursor = 0
    matched = 0
    for item in actual:
        if cursor < len(expected) and item == expected[cursor]:
            matched += 1
            cursor += 1
    return matched / len(expected)
