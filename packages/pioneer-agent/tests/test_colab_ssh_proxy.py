import builtins
import contextlib
import importlib.util
import io
import logging
import os
from pathlib import Path
import tempfile
import types
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('colab_ssh_proxy', Path(__file__).resolve().parents[3] / 'scripts/model-serving/colab_ssh_proxy.py')
proxy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(proxy)


def assignment(endpoint, accelerator='A100', shape='HIGH_RAM'):
    info = types.SimpleNamespace(token='PRIVATE_TOKEN', url='PRIVATE_URL', expires_at=lambda: None)
    return types.SimpleNamespace(endpoint=endpoint, accelerator=types.SimpleNamespace(value=accelerator),
        machine_shape=types.SimpleNamespace(name=shape), variant=types.SimpleNamespace(name='GPU'), runtime_proxy_info=info)


class ProxyTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name).resolve() / 'target.json'

    def test_unique_only_and_pin_change(self):
        first = assignment('one')
        self.assertIs(proxy.choose_unique([first, assignment('cpu', 'NONE')]), first)
        for values in ([], [first, assignment('two')]):
            with self.assertRaises(ValueError): proxy.choose_unique(values)
        with self.assertRaises(ValueError): proxy.choose_pinned([assignment('two')], 'one')

    def test_private_atomic_pin_and_refuse_existing_or_symlink(self):
        proxy.write_pin(self.target, 'one')
        self.assertEqual(proxy.read_pin(self.target), 'one')
        self.assertEqual(self.target.stat().st_mode & 0o777, 0o600)
        with self.assertRaises(FileExistsError): proxy.write_pin(self.target, 'two')
        self.assertEqual(proxy.read_pin(self.target), 'one')
        link = self.target.parent / 'link'
        link.symlink_to(self.target)
        with self.assertRaises(OSError): proxy.read_pin(link)
        with self.assertRaises(FileExistsError): proxy.write_pin(link, 'two')

    def test_reject_shared_directory_and_symlink_parent(self):
        shared = self.target.parent / 'shared'
        shared.mkdir(mode=0o755)
        shared.chmod(0o755)
        with self.assertRaises(ValueError): proxy.write_pin(shared / 'pin.json', 'one')
        alias = self.target.parent / 'alias'
        alias.symlink_to(self.target.parent, target_is_directory=True)
        with self.assertRaises(ValueError): proxy.write_pin(alias / 'pin.json', 'one')

    def test_pin_and_proxy_only_list_and_do_not_leak_errors(self):
        first = assignment('one')
        calls = []
        class Client:
            def list_assignments(self): return [first]
            def assign(self, *a, **kw): calls.append('assign'); raise AssertionError('unexpected assign')
            def unassign(self, *a, **kw): calls.append('unassign'); raise AssertionError('unexpected unassign')
        common = types.ModuleType('colab_cli.common')
        common.state = types.SimpleNamespace(client=Client())
        state_mod = types.ModuleType('colab_cli.state')
        state_mod.SessionState = lambda **kw: types.SimpleNamespace(**kw)
        ssh_mod = types.ModuleType('colab_cli.commands.ssh')
        def bridge(session, identity, rm):
            self.assertEqual(identity, '/private/key')
            self.assertFalse(rm)
            print(session.token, file=__import__('sys').stderr)
            raise RuntimeError('PRIVATE_TOKEN')
        ssh_mod._run_proxy_bridge = bridge
        modules = {'colab_cli': types.ModuleType('colab_cli'), 'colab_cli.common': common,
            'colab_cli.state': state_mod, 'colab_cli.commands': types.ModuleType('colab_cli.commands'),
            'colab_cli.commands.ssh': ssh_mod}
        out, err = io.StringIO(), io.StringIO()
        original_input = builtins.input
        original_disable = logging.root.manager.disable
        self.addCleanup(logging.disable, original_disable)
        logging.disable(logging.INFO)
        with patch.dict('sys.modules', modules), contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            self.assertEqual(proxy.main(['pin', '--target', str(self.target)]), 0)
            self.assertIs(builtins.input, original_input)
            self.assertEqual(logging.root.manager.disable, logging.INFO)
            self.assertEqual(proxy.main(['proxy', '--target', str(self.target), '--identity', '/private/key']), 1)
            self.assertIs(builtins.input, original_input)
            self.assertEqual(logging.root.manager.disable, logging.INFO)
        self.assertNotIn('PRIVATE_TOKEN', out.getvalue() + err.getvalue())
        self.assertNotIn('PRIVATE_URL', out.getvalue() + err.getvalue())
        self.assertEqual(calls, [])
        with self.assertLogs('colab-proxy-regression', level='WARNING') as captured:
            logging.getLogger('colab-proxy-regression').warning('logging restored')
        self.assertEqual(len(captured.records), 1)


if __name__ == '__main__': unittest.main()
