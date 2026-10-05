"""Additional P09 failure boundaries found during 2cc7b2f8 source review."""
from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness import task_eval as ev

ROOT = Path('/tmp/h09a-cr-2cc7b2f8-20261006')
DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
OUT = Path(tempfile.mkdtemp(prefix='h09a-finalization-2cc-'))
print('FINALIZATION_OUTPUT=' + str(OUT), flush=True)

class Finalization(unittest.IsolatedAsyncioTestCase):
    async def test_artifact_hash_read_failure_keeps_failed_report(self):
        output = OUT / 'hash-read-failure'
        original = Path.read_bytes
        def fail_phase_read(path):
            if path.name == 'phase-1.json' and path.is_relative_to(output):
                raise OSError('independent artifact hash read failure')
            return original(path)
        error = None
        with patch.object(Path, 'read_bytes', fail_phase_read):
            try:
                await ev.evaluate(source_root=ROOT, suite_root=DATA, suite_path='suite.json', output=output)
            except Exception as exc:
                error = {'type': type(exc).__name__, 'message': str(exc)}
        (OUT / 'hash-read-process.json').write_text(json.dumps({'exception': error, 'report_exists': (output / 'report.json').exists()}))
        self.assertTrue((output / 'report.json').exists(), 'one unreadable artifact discarded all 8 completed case results despite writable report destination')
        report = json.loads((output / 'report.json').read_bytes())
        self.assertFalse(report['gate_pass'])
        self.assertEqual(8, len(report['cases']))
        self.assertTrue(report['infra_errors'])

    async def test_projection_failure_cannot_leave_green_gate(self):
        output = OUT / 'projection-failure'
        with patch.object(ev, 'stable_projection', side_effect=ValueError('independent projection failure')):
            report, code = await ev.evaluate(source_root=ROOT, suite_root=DATA, suite_path='suite.json', output=output)
        self.assertEqual(2, code)
        self.assertTrue(report['infra_errors'])
        self.assertFalse(report['gate_pass'])

if __name__ == '__main__':
    unittest.main(verbosity=2)
