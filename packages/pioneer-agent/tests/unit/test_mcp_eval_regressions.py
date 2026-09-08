from __future__ import annotations

from datetime import timedelta
from hashlib import sha256
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from pioneer_agent.app import mcp_eval as cli
from pioneer_agent.mcp_eval.models import EvalSourceBindings, RunManifest, StaticScenarioTranscript, ToolCallRecord
from pioneer_agent.mcp_eval.runner import load_battery, run_battery, write_run_artifacts
from pioneer_agent.mcp_eval.scoring import fold_observed, score_scenario, sensorium_metrics
from pioneer_agent.mcp_server import service
from tests.unit.test_mcp_eval import REPO_SHA, _battery_path


class EvalRegressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.loaded = load_battery(_battery_path())

    def scenario(self, name):
        manifest = next(s for s in self.loaded.manifest.scenarios if s.scenario_id == name)
        return manifest, self.loaded.transcripts[name].model_copy(deep=True)

    def test_failed_payloads_never_supply_observations_or_scores(self) -> None:
        for name in ('home-observation', 'map-filter-no-change', 'map-filter-interrupted'):
            with self.subTest(name=name):
                manifest, transcript = self.scenario(name)
                for call in transcript.calls:
                    call.success = False
                report = score_scenario(manifest, transcript)
                self.assertEqual(report.observability.success_rate, 0)
                self.assertEqual(report.sensorium.critical_domain_query_coverage, 0)
                self.assertEqual(set(report.scores.model_dump().values()), {0.0})
                self.assertEqual(report.observed.state_fields, {})
                self.assertEqual(report.observed.candidates, [])
                self.assertEqual(report.observed.journal_steps, [])
                self.assertIsNone(report.observed.no_change_recognized)
                self.assertTrue(all(v is None for v in report.sensorium.seconds_since_refresh_at_end.values()))
                self.assertEqual(set(report.sensorium.never_queried_critical_domains), set(manifest.sensorium.critical_domains))

    def test_failed_later_output_cannot_overwrite_successful_evidence(self) -> None:
        manifest, transcript = self.scenario('home-observation')
        baseline = fold_observed(transcript)
        failed = transcript.calls[1].model_copy(deep=True)
        failed.call_id = 'failed-retry'
        failed.ordinal = len(transcript.calls)
        failed.started_at = transcript.calls[-1].started_at + timedelta(seconds=1)
        failed.success = False
        failed.result_summary.state_fields = {'page': 'invented'}
        failed.result_summary.unknown_domains = ['popup']
        failed.domain_observed_at = {d: failed.started_at for d in failed.domains_queried}
        transcript.calls.append(failed)
        self.assertEqual(fold_observed(transcript), baseline)
        report = score_scenario(manifest, transcript)
        self.assertEqual(report.observability.failed_tool_call_count, 1)
        self.assertGreater(report.sensorium.seconds_since_refresh_at_end['resource_bar'], 1)

    def test_failed_only_tool_does_not_satisfy_required_tool_coverage(self) -> None:
        manifest, transcript = self.scenario('home-observation')
        transcript.calls[1].success = False
        report = score_scenario(manifest, transcript)
        self.assertLess(report.scores.tool_call_coverage, 1)
        self.assertEqual(report.scores.state_field_accuracy, 0)
        self.assertIsNone(report.sensorium.seconds_since_refresh_at_end['resource_bar'])

    def test_recovery_refresh_preserves_pre_failure_history(self) -> None:
        manifest, transcript = self.scenario('map-filter-interrupted')
        baseline = sensorium_metrics(manifest, transcript)
        self.assertEqual(baseline.missed_risk_domains_before_failure, [])
        recovery = transcript.calls[1].model_copy(deep=True)
        recovery.call_id = 'recovery-observe'
        recovery.ordinal = len(transcript.calls)
        recovery.started_at = transcript.calls[0].started_at + timedelta(milliseconds=60)
        recovery.domain_observed_at = {d: recovery.started_at for d in recovery.domains_queried}
        transcript.calls.append(recovery)
        transcript = StaticScenarioTranscript.model_validate(transcript.model_dump())
        result = sensorium_metrics(manifest, transcript)
        self.assertEqual(result.missed_risk_domains_before_failure, [])
        for age in result.seconds_since_refresh_at_end.values():
            self.assertAlmostEqual(age, recovery.duration_ms / 1000)

    def test_recovery_with_old_timestamp_cannot_retroactively_satisfy_failure(self) -> None:
        manifest, transcript = self.scenario('map-filter-interrupted')
        old = transcript.calls[1].model_copy(deep=True)
        transcript.calls[1].success = False
        old.call_id = 'late-cached-response'
        old.ordinal = len(transcript.calls)
        old.started_at = transcript.calls[-1].started_at + timedelta(seconds=1)
        transcript.calls.append(old)
        result = sensorium_metrics(manifest, transcript)
        self.assertEqual(set(result.missed_risk_domains_before_failure), set(manifest.sensorium.required_before_failure))

    def test_future_observation_is_rejected_by_schema_and_scorer(self) -> None:
        manifest, transcript = self.scenario('home-observation')
        call = transcript.calls[1]
        end_at = call.started_at + timedelta(milliseconds=call.duration_ms)
        call.domain_observed_at = {d: end_at + timedelta(microseconds=1) for d in call.domains_queried}
        with self.assertRaisesRegex(ValidationError, 'postdate'):
            ToolCallRecord.model_validate(call.model_dump())
        with self.assertRaisesRegex(ValueError, 'postdate'):
            sensorium_metrics(manifest, transcript)
        call.domain_observed_at = {d: end_at for d in call.domains_queried}
        ToolCallRecord.model_validate(call.model_dump())

    def test_failure_cutoff_cannot_postdate_transcript(self) -> None:
        _, transcript = self.scenario('map-filter-interrupted')
        data = transcript.model_dump()
        data['failure_at'] = transcript.calls[-1].started_at + timedelta(days=1)
        with self.assertRaisesRegex(ValidationError, 'postdate'):
            StaticScenarioTranscript.model_validate(data)

    def test_end_uses_last_completion_in_overlapping_calls(self) -> None:
        manifest, transcript = self.scenario('home-observation')
        transcript.calls[0].duration_ms = 10_000
        result = sensorium_metrics(manifest, transcript)
        self.assertEqual(result.seconds_since_refresh_at_end['resource_bar'], 9.98)

    def test_golden_binds_exact_evaluator_bytes_without_second_read(self) -> None:
        pioneer_root = _battery_path().parents[3]
        kwargs = dict(
            repo_sha=REPO_SHA,
            golden_expectations=pioneer_root / 'tests/golden/advisor_fixture_expectations.json',
            golden_fixture_root=pioneer_root / 'tests/fixtures',
        )
        first = run_battery(_battery_path(), **kwargs)
        original_read = service._read_fixture
        consumed = {}

        def changed_read(*args, **kw):
            name, payload = original_read(*args, **kw)
            if name == 'chapter_claimable_state.json':
                data = json.loads(payload)
                data['economy']['resources']['wood'] += 1
                payload = json.dumps(data).encode()
            consumed[name] = sha256(payload).hexdigest()
            return name, payload

        with patch.object(service, '_read_fixture', side_effect=changed_read) as read:
            second = run_battery(_battery_path(), **kwargs)
        self.assertEqual(read.call_count, second.run_manifest.source_bindings.golden_fixture_count)
        self.assertEqual(first.run_manifest.source_bindings.golden_match_count, second.run_manifest.source_bindings.golden_match_count)
        self.assertNotEqual(first.run_manifest.fixture_catalog_digest, second.run_manifest.fixture_catalog_digest)
        self.assertEqual(second.run_manifest.source_bindings.golden_fixture_sha256s, consumed)
        self.assertNotEqual(first.run_manifest.source_bindings, second.run_manifest.source_bindings)
        self.assertTrue(second.run_manifest.runtime_fixture_executed)
        self.assertFalse(second.run_manifest.provider_vision_executed)

    def test_golden_manifest_without_consumed_byte_digests_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            EvalSourceBindings(golden_bound=True, golden_expectations_sha256='a' * 64, golden_fixture_count=1)

    def test_static_runner_cannot_claim_provider_vision_or_live_execution(self) -> None:
        for kwargs in ({'model_provider': 'openai'}, {'model_id': 'gpt-6'}):
            with self.subTest(kwargs=kwargs), self.assertRaisesRegex(ValueError, 'cannot claim'):
                run_battery(_battery_path(), repo_sha=REPO_SHA, **kwargs)
        result = run_battery(_battery_path(), repo_sha=REPO_SHA)
        self.assertEqual(result.run_manifest.evaluation_mode, 'static_transcript')
        self.assertFalse(result.run_manifest.runtime_fixture_executed)
        for key, value in (('provider_vision_executed', True), ('live_action_executed', True), ('evaluation_mode', 'provider_vision'), ('runtime_fixture_executed', True), ('model_id', 'gpt-6')):
            data = result.run_manifest.model_dump()
            data[key] = value
            with self.subTest(key=key), self.assertRaises(ValidationError):
                RunManifest.model_validate(data)
        with TemporaryDirectory() as tmp:
            manifest, metrics = write_run_artifacts(Path(tmp), result)
            for path in (manifest, metrics):
                data = json.loads(path.read_text())
                self.assertEqual(data['evaluation_mode'], 'static_transcript')
                self.assertFalse(data['provider_vision_executed'])
                self.assertFalse(data['live_action_executed'])
            with self.assertRaisesRegex(ValueError, 'cannot claim'):
                cli.main(['--battery', str(_battery_path()), '--output-dir', str(Path(tmp) / 'fake'), '--repo-sha', REPO_SHA, '--model-provider', 'openai'])
            self.assertFalse((Path(tmp) / 'fake').exists())


if __name__ == '__main__':
    unittest.main()
