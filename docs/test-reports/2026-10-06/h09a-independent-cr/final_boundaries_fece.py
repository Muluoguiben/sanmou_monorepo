"""Verify newly added finalization boundaries under real committed CLI mode."""
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

ROOT = Path('/tmp/h09a-cr-fece4163-20261006')
OUT = Path(tempfile.mkdtemp(prefix='h09a-final-boundaries-fece-'))
print('FINAL_BOUNDARIES_OUTPUT=' + str(OUT), flush=True)

class FinalBoundaries(unittest.TestCase):
    def invoke(self, output, fault):
        console = StringIO()
        with patch.object(sys, 'argv', ['task_eval', '--output', str(output)]), redirect_stdout(console), fault:
            with self.assertRaises(SystemExit) as exited:
                runpy.run_module('pioneer_agent.app.task_eval', run_name='__main__', alter_sys=True)
        (OUT / (output.name + '-console.json')).write_text(json.dumps({'exit': exited.exception.code, 'stdout': console.getvalue()}))
        return exited.exception.code, json.loads(console.getvalue())

    def test_artifact_enumeration_failure_preserves_cases_without_green(self):
        output = OUT / 'enumeration-fault'
        original = Path.rglob
        def fail_output_only(path, pattern):
            if path == output:
                raise OSError('independent artifact enumeration failure')
            return original(path, pattern)
        code, _ = self.invoke(output, patch.object(Path, 'rglob', fail_output_only))
        report = json.loads((output / 'report.json').read_bytes())
        self.assertEqual(2, code)
        self.assertTrue(report['source_verified'])
        self.assertFalse(report['complete'] or report['gate_pass'])
        self.assertEqual(8, len(report['cases']))
        self.assertEqual(12, len(report['cases'][0]['actual']['phases'][0]['tool_calls']))
        self.assertIn('_enumeration', report['artifact_errors'])

    def test_unwritable_final_report_is_explicit_unavailable(self):
        output = OUT / 'report-write-fault'
        original = ev.write_new
        def fail_report_only(path, value):
            if path.name == 'report.json':
                raise OSError('independent final report write failure')
            return original(path, value)
        code, console = self.invoke(output, patch.object(ev, 'write_new', fail_report_only))
        self.assertEqual(2, code)
        self.assertFalse(console['report_available'] or console['gate_pass'] or console['complete'])
        self.assertFalse((output / 'report.json').exists())
        self.assertTrue(list(output.glob('*/phase-1.json')))

if __name__ == '__main__':
    unittest.main(verbosity=2)
