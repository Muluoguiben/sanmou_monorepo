"""Post-plan supplements prompted by static review; preserve initial probe run."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness import task_eval as ev
from pioneer_agent.agent_harness._task_eval_inputs import Inputs, Suite, decode

ROOT = Path('/tmp/h09a-cr-64adbfbb-20261006')
DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
OUT = Path(tempfile.mkdtemp(prefix='h09a-supplemental-'))
print('SUPPLEMENT_OUTPUT=' + str(OUT), flush=True)

class Supplements(unittest.IsolatedAsyncioTestCase):
    async def test_goal_success_not_redefined_by_expected_tool_labels(self):
        case = Suite.model_validate(decode((DATA / 'suite.json').read_bytes())).cases[0]
        output = OUT / 'goal-label'
        output.mkdir()
        actual = await ev.execute(case.execution, Inputs(DATA), output)
        self.assertEqual('goal_verified', actual['phases'][-1]['state']['reason'])
        before = ev.score(actual, case.expected)
        case.expected.phases[0].tool_calls = []
        after = ev.score(actual, case.expected)
        (output / 'label-probe.json').write_text(json.dumps({'before': before, 'after': after, 'actual': actual}))
        self.assertFalse(after['control_pass'])
        self.assertTrue(after['goal_success'], 'actual verified goal disappeared solely because expected tool labels changed')

    async def test_phase_output_failure_preserves_execution_facts_in_failed_report(self):
        original = ev.write_new
        count = 0
        def fail_one(path, value):
            nonlocal count
            if path.name == 'phase-1.json' and count == 0:
                count += 1
                raise OSError('independent phase-artifact write failure')
            return original(path, value)
        with patch.object(ev, 'write_new', side_effect=fail_one):
            report, code = await ev.evaluate(source_root=ROOT, suite_root=DATA,
                suite_path='suite.json', output=OUT / 'phase-output-failure')
        self.assertEqual(2, code)
        self.assertEqual(8, report['denominators']['control_pass'])
        self.assertTrue(report['cases'][0]['score']['infra_error'])
        self.assertIn('actual', report['cases'][0], 'phase artifact failure discarded the real execution, calls, policy and trace')

    def test_two_formal_runs_stable_and_source_bound(self):
        a = json.loads(Path('/tmp/h09a-cr-64adbfbb-eval1/report.json').read_bytes())
        b = json.loads(Path('/tmp/h09a-cr-64adbfbb-eval2/report.json').read_bytes())
        self.assertEqual(a['stable_projection'], b['stable_projection'])
        self.assertEqual('64adbfbb951754a36cfd9189f4294d70b323eb28', a['source']['commit'])
        self.assertEqual('eb7e0cf117fa39af4cb6d6ba0e3a3c5037371d58', a['source']['tree'])
        self.assertEqual(a['inputs'], b['inputs'])
        self.assertTrue(a['complete'] and a['source_verified'] and a['gate_pass'])
        for base, report in [(Path('/tmp/h09a-cr-64adbfbb-eval1'), a), (Path('/tmp/h09a-cr-64adbfbb-eval2'), b)]:
            for relative, digest in report['artifacts'].items():
                self.assertEqual(digest, hashlib.sha256((base / relative).read_bytes()).hexdigest())

if __name__ == '__main__':
    unittest.main(verbosity=2)
