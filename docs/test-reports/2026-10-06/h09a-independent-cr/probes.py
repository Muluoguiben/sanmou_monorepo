"""Independent offline probes; source under review is never edited."""
import asyncio
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness import task_eval as ev
from pioneer_agent.agent_harness._task_eval_inputs import Inputs, Suite, Fixture, InputError, decode, safe_path
from pioneer_agent.agent_harness._task_eval_source import SourceBinding

ROOT = Path('/tmp/h09a-cr-64adbfbb-20261006')
DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
OUT = Path(tempfile.mkdtemp(prefix='h09a-independent-probes-'))
print('PROBE_OUTPUT=' + str(OUT), flush=True)

def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(json.dumps(value, ensure_ascii=False, indent=2).encode())

class Independent(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.suite = Suite.model_validate(decode((DATA / 'suite.json').read_bytes()))

    async def run_case(self, case, inputs=None, label=None):
        out = Path(tempfile.mkdtemp(prefix=(label or case.id) + '-', dir=OUT))
        actual = await ev.execute(case.execution, inputs or Inputs(DATA), out)
        scored = ev.score(actual, case.expected)
        save(out / 'independent-actual.json', actual)
        save(out / 'independent-score.json', scored)
        return actual, scored

    async def altered(self, index, mutate):
        case = self.suite.cases[index]
        folder = Path(tempfile.mkdtemp(prefix='input-', dir=OUT))
        for phase in case.execution.phases:
            obj = decode((DATA / phase.fixture.path).read_bytes())
            mutate(obj)
            target = folder / phase.fixture.path
            save(target, obj)
            phase.fixture.sha256 = hashlib.sha256(target.read_bytes()).hexdigest()
        return await self.run_case(case, Inputs(folder))

    async def test_baseline_eight_and_independent_accounting(self):
        for case in self.suite.cases:
            actual, scored = await self.run_case(case)
            self.assertTrue(scored['control_pass'], scored)
            cumulative = 0
            for phase in actual['phases']:
                cumulative += len(phase['tool_calls'])
                self.assertEqual(cumulative, phase['budget']['counts']['tool'])
                self.assertEqual(0, phase['budget']['pending'])
                self.assertEqual(0, phase['budget']['counts']['model'])
                self.assertTrue(phase['repeat_noop'])
            self.assertEqual(case.expected.category == 'goal', scored['goal_success'])

    async def test_expected_and_id_do_not_change_execution(self):
        case = self.suite.cases[0]
        first, _ = await self.run_case(case)
        case.id = 'renamed-unrelated-case'
        case.expected.category = 'safety_stop'
        case.expected.phases[0].reason = 'deliberate-wrong-label'
        case.expected.phases[0].tool_calls = []
        second, scored = await self.run_case(case)
        projection = lambda actual: ev.stable_projection({'cases': [{'id': 'neutral', 'actual': actual}]})
        self.assertEqual(projection(first), projection(second))
        self.assertFalse(scored['control_pass'])
        self.assertTrue(scored['unexpected_goal_success'])

    async def test_new_id_equal_capture_time(self):
        def mutate(obj):
            for call in obj['calls'][4:8]:
                obs = call['response']['structuredContent'].get('observation')
                if obs:
                    obs['captured_at'] = '2026-10-06T00:00:01+00:00'
        actual, scored = await self.altered(0, mutate)
        self.assertEqual('nonincreasing_capture_time', actual['phases'][0]['state']['reason'])
        self.assertEqual(6, len(actual['phases'][0]['tool_calls']))
        self.assertFalse(scored['goal_success'])

    async def test_resume_budget_five_no_sixth_dispatch(self):
        case = self.suite.cases[5]
        case.execution.budget = case.execution.budget.model_copy(update={'max_tool_calls': 5})
        actual, scored = await self.run_case(case)
        self.assertEqual(5, sum(len(p['tool_calls']) for p in actual['phases']))
        self.assertEqual('budget_exhausted', actual['phases'][-1]['state']['reason'])
        self.assertTrue(scored['assertions']['phase_2.resume_no_refill'])
        self.assertFalse(scored['goal_success'])

    async def test_resume_observation_reuse(self):
        case = self.suite.cases[5]
        case.execution.phases[1].fixture = case.execution.phases[0].fixture.model_copy()
        actual, scored = await self.run_case(case)
        self.assertEqual('reused_observation', actual['phases'][-1]['state']['reason'])
        self.assertEqual(2, len(actual['phases'][-1]['tool_calls']))
        self.assertFalse(scored['goal_success'])

    async def test_exhausted_response_is_infra(self):
        actual, scored = await self.altered(0, lambda obj: obj.update(calls=obj['calls'][:1]))
        self.assertTrue(scored['infra_error'])
        self.assertFalse(scored['expected_safety_stop'])
        self.assertEqual(2, len(actual['phases'][0]['tool_calls']))

    async def test_checkpoint_write_failure_preserves_actual(self):
        from pioneer_agent.agent_harness.run_store import JsonRunStore
        with patch.object(JsonRunStore, 'acquire', side_effect=OSError('independent-disk-failure')):
            actual, scored = await self.run_case(self.suite.cases[0])
        self.assertTrue(scored['infra_error'])
        self.assertEqual([], actual['phases'][0]['tool_calls'])
        self.assertFalse(scored['control_pass'])

    def test_schema_empty_duplicate_unknown_tool_and_clock(self):
        for mutate in (lambda o: o.update(cases=[]),
                       lambda o: o['cases'][1].update(id=o['cases'][0]['id']),
                       lambda o: o.update(version='unknown'),
                       lambda o: o['cases'][0]['execution'].update(observation_clock='2026-10-06')):
            obj = self.suite.model_dump(mode='json')
            mutate(obj)
            with self.assertRaises(ValueError):
                Suite.model_validate(obj)
        obj = decode((DATA / 'fixtures/first-observation.json').read_bytes())
        obj['calls'][0]['tool'] = 'game_input'
        with self.assertRaises(ValueError):
            Fixture.model_validate(obj)

    def test_fixture_drift_paths_and_single_buffer(self):
        folder = OUT / 'byte-input'
        folder.mkdir()
        target = folder / 'input.json'
        target.write_bytes(b'{"n":1}')
        inputs = Inputs(folder)
        original = inputs.read('input.json')
        target.write_bytes(b'{"n":2}')
        self.assertEqual(original, inputs.read('input.json'))
        with self.assertRaises(InputError):
            inputs.read('input.json', hashlib.sha256(target.read_bytes()).hexdigest())
        with self.assertRaises(InputError):
            safe_path(folder, '../input.json')
        (folder / 'linked.json').symlink_to(target)
        with self.assertRaises(InputError):
            safe_path(folder, 'linked.json')

    def test_real_lazy_shadow_and_package_path(self):
        binding = SourceBinding(ROOT)
        module = types.ModuleType('pioneer_agent.independent_lazy')
        module.__file__ = '/tmp/not-the-reviewed-source.py'
        module.__spec__ = types.SimpleNamespace(origin=module.__file__)
        with patch.dict(sys.modules, {'pioneer_agent.independent_lazy': module}):
            with self.assertRaisesRegex(InputError, 'shadow_import'):
                binding.verify_imports()
        import pioneer_agent
        with patch.object(pioneer_agent, '__path__', ['/tmp/shadow-package']):
            with self.assertRaisesRegex(InputError, 'shadow_package_path'):
                binding.verify_imports()

    async def test_output_no_clobber(self):
        output = OUT / 'existing'
        output.mkdir()
        sentinel = output / 'sentinel'
        sentinel.write_bytes(b'preserve-exactly')
        with self.assertRaises(FileExistsError):
            await ev.evaluate(source_root=ROOT, suite_root=DATA, suite_path='suite.json', output=output)
        self.assertEqual(b'preserve-exactly', sentinel.read_bytes())
        self.assertEqual(['sentinel'], [p.name for p in output.iterdir()])

    async def test_infra_case_keeps_denominator(self):
        folder = OUT / 'exhaust-suite'
        shutil.copytree(DATA, folder)
        obj = decode((folder / 'suite.json').read_bytes())
        # Change only one case to point at a short independent response file.
        fixture = decode((folder / 'fixtures/three-observations.json').read_bytes())
        fixture['calls'] = fixture['calls'][:1]
        save(folder / 'short.json', fixture)
        ref = obj['cases'][0]['execution']['phases'][0]['fixture']
        ref.update(path='short.json', sha256=hashlib.sha256((folder / 'short.json').read_bytes()).hexdigest())
        save(folder / 'suite.json', obj)
        report, code = await ev.evaluate(source_root=ROOT, suite_root=folder, suite_path='suite.json', output=OUT / 'exhaust-report')
        self.assertEqual(2, code)
        self.assertEqual(8, len(report['cases']))
        self.assertEqual(8, report['denominators']['control_pass'])
        self.assertEqual(1, report['totals']['infra_error'])
        self.assertFalse(report['gate_pass'])

    def test_unbound_executed_cli_must_not_be_source_verified(self):
        folder = OUT / 'unbound/entrypoint/deep/a/b/c'
        folder.mkdir(parents=True)
        cli = folder / 'task_eval.py'
        original = ROOT / 'packages/pioneer-agent/src/pioneer_agent/app/task_eval.py'
        # Ordinary copy, not a hostile module loader or monkeypatch. This is the
        # CLI actually executed, but its bytes are not any reviewed Git blob.
        cli.write_bytes(original.read_bytes() + b'\n# independent uncommitted CLI bytes\n')
        output = OUT / 'unbound-cli-report'
        process = subprocess.run([sys.executable, '-B', str(cli), '--source-root', str(ROOT),
            '--suite-root', str(DATA), '--output', str(output)], capture_output=True, text=True)
        save(OUT / 'unbound-cli-process.json', {'argv': process.args, 'code': process.returncode,
            'stdout': process.stdout, 'stderr': process.stderr, 'executed_cli_sha256': hashlib.sha256(cli.read_bytes()).hexdigest()})
        report = json.loads((output / 'report.json').read_bytes())
        self.assertFalse(report['source_verified'], 'uncommitted executed CLI was omitted from actual-module provenance checks')

if __name__ == '__main__':
    unittest.main(verbosity=2)
