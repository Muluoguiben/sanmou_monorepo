"""The model gateway can reuse task contracts without loading optional SDKs."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import subprocess
import sys
import unittest


class GatewayImportBoundaryTests(unittest.TestCase):
    def test_gateway_and_budget_import_without_vision_or_mcp_sdks(self):
        root = Path(__file__).resolve().parents[3]
        script = '''
import sys
class NoOptionalSDKs:
    def find_spec(self, fullname, path=None, target=None):
        for blocked in ('mcp', 'google.genai', 'cryptography'):
            if fullname == blocked or fullname.startswith(blocked + '.'):
                raise ModuleNotFoundError('Optional SDK requested: ' + fullname)
sys.meta_path.insert(0, NoOptionalSDKs())
from pioneer_agent.adapters.policy_service import PolicyServiceAdapter
from pioneer_agent.app.policy_gateway import create_app
from pioneer_agent.agent_harness.task_contracts import BudgetRequest, Usage
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
ledger = RunBudgetLedger()
reservation = ledger.reserve(BudgetRequest(run_id='import-check', step_id='one',
    kind='model', name='policy', input_tokens=8, output_tokens=4))
ledger.settle(reservation, Usage(input_tokens=8, output_tokens=2), outcome='ok')
assert ledger.summary()['pending'] == 0
assert 'pioneer_agent.perception.vision.client' not in sys.modules
assert 'pioneer_agent.agent_harness.stdio_client' not in sys.modules
print('gateway-import-ok')
'''
        env = dict(os.environ, PYTHONPATH=os.pathsep.join([
            str(root / 'packages/pioneer-agent/src'), str(root / 'packages/sanmou-common/src'),
        ]), PYTHONDONTWRITEBYTECODE='1')
        result = subprocess.run([sys.executable, '-c', script], env=env,
                                capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), 'gateway-import-ok')

    def test_public_harness_exports_resolve_to_original_objects(self):
        import pioneer_agent.agent_harness as public
        expected = {
            'journal': ('DecisionJournal', 'JsonJournalStore'),
            'loop': ('DecisionWindowResult', 'DecisionWindowStatus', 'RecommendationHarness'),
            'contracts': ('InProcessMcpClient', 'McpClient'),
            'tool_log': ('JsonlToolLog', 'ToolCallRecord'),
            'policy': ('StopPolicy', 'StopReason'),
            'stdio_client': ('StdioMcpClient',),
        }
        names = {name for values in expected.values() for name in values}
        self.assertEqual(set(public.__all__), names)
        self.assertTrue(names <= set(dir(public)))
        for module, values in expected.items():
            original = importlib.import_module(f'pioneer_agent.agent_harness.{module}')
            for name in values:
                self.assertIs(getattr(public, name), getattr(original, name))
        namespace = {}
        exec('from pioneer_agent.agent_harness import *', namespace)
        for name in names:
            self.assertIs(namespace[name], getattr(public, name))

    def test_public_mcp_service_exports_still_work(self):
        import pioneer_agent.mcp_server as public
        from pioneer_agent.mcp_server.service import GameMCPService, ObservedAdvisorCycle
        from pioneer_agent.mcp_server.contracts import GAME_TOOL_ALLOWLIST
        self.assertIs(public.GameMCPService, GameMCPService)
        self.assertIs(public.ObservedAdvisorCycle, ObservedAdvisorCycle)
        self.assertIs(public.GAME_TOOL_ALLOWLIST, GAME_TOOL_ALLOWLIST)
        self.assertIn('GameMCPService', dir(public))

    def test_unknown_public_attributes_raise_attribute_error(self):
        for name in ('pioneer_agent.agent_harness', 'pioneer_agent.mcp_server'):
            with self.subTest(package=name):
                package = importlib.import_module(name)
                with self.assertRaises(AttributeError):
                    getattr(package, 'unlisted_gateway_import')


if __name__ == '__main__':
    unittest.main()
