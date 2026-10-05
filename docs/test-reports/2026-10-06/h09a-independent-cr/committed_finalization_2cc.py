"""P09 projection fault with the real committed CLI as __main__, not library mode."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import runpy
import sys
import tempfile
import unittest
from unittest.mock import patch
from pioneer_agent.agent_harness import task_eval as ev

ROOT = Path('/tmp/h09a-cr-2cc7b2f8-20261006')
OUT = Path(tempfile.mkdtemp(prefix='h09a-committed-finalization-2cc-'))
print('COMMITTED_FINALIZATION_OUTPUT=' + str(OUT), flush=True)

class CommittedFinalization(unittest.TestCase):
    def test_projection_exception_resets_committed_cli_gate(self):
        output = OUT / 'projection-failure'
        console = StringIO()
        args = ['task_eval', '--source-root', str(ROOT), '--output', str(output)]
        with patch.object(sys, 'argv', args), redirect_stdout(console), patch.object(
                ev, 'stable_projection', side_effect=ValueError('independent projection failure')):
            with self.assertRaises(SystemExit) as exited:
                runpy.run_module('pioneer_agent.app.task_eval', run_name='__main__', alter_sys=True)
        (OUT / 'console.json').write_text(json.dumps({'exit': exited.exception.code, 'stdout': console.getvalue()}))
        report = json.loads((output / 'report.json').read_bytes())
        self.assertEqual(2, exited.exception.code)
        self.assertTrue(report['source_verified'])
        self.assertTrue(report['infra_errors'])
        self.assertFalse(report['gate_pass'], 'committed CLI published a true gate after projection failure')

if __name__ == '__main__':
    unittest.main(verbosity=2)
