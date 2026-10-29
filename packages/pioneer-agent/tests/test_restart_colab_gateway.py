import hashlib
import importlib.util
import json
import os
from pathlib import Path
import signal
import tempfile
import types
import unittest
from unittest.mock import patch

MODULE_PATH = Path(__file__).resolve().parents[3] / 'scripts/model-serving/restart_colab_gateway.py'
spec = importlib.util.spec_from_file_location('restart_colab_gateway', MODULE_PATH)
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


class VerifyProvisionTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp(prefix='sanmou-restart-test-')).resolve()
        self.source = self.root / 'source'
        self.source.mkdir()
        (self.root/'model').mkdir()
        (self.root/'venv/bin').mkdir(parents=True)
        (self.root/'venv/bin/python').write_text('placeholder')
        self.commit='a'*40
        names=['scripts/model-serving/colab_gateway_bootstrap.py',
               'scripts/model-serving/live_gateway_roundtrip.py',
               'scripts/model-serving/native_runtime_manifest.py',
               'docs/test-reports/2026-10-24/colab-native/model-files.json']
        files={}
        for name in names:
            path=self.source/name
            path.parent.mkdir(parents=True,exist_ok=True)
            path.write_bytes(name.encode())
            files[name]={'bytes':len(name.encode()), 'sha256':hashlib.sha256(name.encode()).hexdigest()}
        inv=self.source/'source-inventory.json'
        inv.write_text(json.dumps({'schema':'sanmou-colab-source-inventory-v1', 'source_commit':self.commit,'files':files}))
        self.status=self.root/'provision-status.json'
        self.data={'status':'provisioned','source_commit':self.commit,'source_root':str(self.source),
            'source_inventory':str(inv),'source_inventory_sha256':m.digest(inv),'model_dir':str(self.root/'model'),
            'python':str(self.root/'venv/bin/python'),'expected_model_files':str(self.source/names[-1])}
        self.status.write_text(json.dumps(self.data))

    def test_reject_tampered_source(self):
        m.verify_provision(self.status,self.commit,self.data['source_inventory_sha256'])
        (self.source/'scripts/model-serving/colab_gateway_bootstrap.py').write_text('changed')
        with self.assertRaisesRegex(ValueError,'source_file_mismatch'):
            m.verify_provision(self.status,self.commit,self.data['source_inventory_sha256'])

    def test_reject_unlisted_sitecustomize_and_symlink(self):
        extra=self.source/'packages/sanmou-common/src/sitecustomize.py'
        extra.parent.mkdir(parents=True)
        extra.write_text('raise RuntimeError("unexpected import")')
        with self.assertRaisesRegex(ValueError,'source_tree_inventory_mismatch'):
            m.verify_provision(self.status,self.commit,self.data['source_inventory_sha256'])
        extra.rename(extra.with_suffix('.retained'))
        extra.symlink_to('sitecustomize.retained')
        with self.assertRaisesRegex(ValueError,'unsafe_source_file'):
            m.verify_provision(self.status,self.commit,self.data['source_inventory_sha256'])

    def test_reject_hardlink_in_source(self):
        original=self.source/'scripts/model-serving/colab_gateway_bootstrap.py'
        alias=self.source/'scripts/model-serving/copied.py'
        os.link(original,alias)
        with self.assertRaisesRegex(ValueError,'unsafe_source_file'):
            m.verify_provision(self.status,self.commit,self.data['source_inventory_sha256'])

    def test_reject_special_file_in_source(self):
        os.mkfifo(self.source/'unexpected_pipe')
        with self.assertRaisesRegex(ValueError,'unsafe_source_file'):
            m.verify_provision(self.status,self.commit,self.data['source_inventory_sha256'])

    def test_reject_wrong_commit_and_path_escape(self):
        with self.assertRaisesRegex(ValueError,'provision_identity_mismatch'):
            m.verify_provision(self.status,'b'*40,self.data['source_inventory_sha256'])
        with self.assertRaisesRegex(ValueError,'source_inventory_mismatch'):
            m.verify_provision(self.status,self.commit,'b'*64)
        with self.assertRaisesRegex(ValueError,'invalid_inventory_path'):
            m.checked_path(self.source,'../escape')

    def test_gpu_preflight_fails_closed(self):
        with patch.object(m.subprocess,'check_output',side_effect=['NVIDIA A100, 81920, 0, 0\n','123\n']):
            with self.assertRaisesRegex(ValueError,'gpu_processes_present'):m.check_gpu()
        with patch.object(m.subprocess,'check_output',return_value='NVIDIA T4, 15360, 0, 0\n'):
            with self.assertRaisesRegex(ValueError,'gpu_precondition_failed'):m.check_gpu()


class StartupTests(unittest.TestCase):
    def setUp(self):
        self.root=Path(tempfile.mkdtemp(prefix='sanmou-restart-test-')).resolve()
        self.source=self.root/'source';self.source.mkdir()
        self.model=self.root/'model';self.model.mkdir()
        self.python=self.root/'python'
        self.output=self.root/'run'
        self.status={'source_inventory':str(self.source/'source-inventory.json'),
                     'expected_model_files':str(self.source/'model-files.json')}
        self.boot=types.SimpleNamespace(isolated_env=lambda out,source:{'PATH':'/bin'})
        self.spec=types.SimpleNamespace(loader=types.SimpleNamespace(exec_module=lambda obj:None))
        self.commands=[];self.processes=[];self.stopped=[]
        self.fake=types.SimpleNamespace(stdout=json.dumps({'sampling':{},'prompt_sha256':'a'*64}))
        self.patches=[patch.object(m,'verify_provision',return_value=(self.status,self.source,self.model,self.python)),
            patch.object(m,'check_gpu'),patch.object(m.shutil,'disk_usage',return_value=types.SimpleNamespace(free=100*1024**3)),
            patch.object(m.importlib.util,'spec_from_file_location',return_value=self.spec),
            patch.object(m.importlib.util,'module_from_spec',return_value=self.boot),
            patch.object(m,'free_port',side_effect=[12345,23456,34567,45678]),
            patch.object(m.subprocess,'run',side_effect=self.run_child),
            patch.object(m,'start_owned',side_effect=self.start),patch.object(m,'stop_owned',side_effect=self.stop),
            patch.object(m,'wait_ready')]
        for p in self.patches:p.start();self.addCleanup(p.stop)

    def run_child(self,cmd,**kwargs):
        self.commands.append((cmd,kwargs));return self.fake

    def start(self,cmd,env):
        self.commands.append((cmd,{'env':env}))
        p=types.SimpleNamespace(pid=100+len(self.processes));self.processes.append(p);return p

    def stop(self,processes):self.stopped.extend(processes)

    def test_new_directory_secrets_and_no_secret_in_commands(self):
        result=m.run(str(self.root/'status'),str(self.output),'a'*40,'b'*64)
        self.assertEqual(result['status'],'ready')
        self.assertEqual(len(self.processes),2)
        key=json.loads((self.output/'private-keys.json').read_text())['gateway']
        self.assertEqual((self.output/'private-keys.json').stat().st_mode & 0o777,0o600)
        self.assertTrue(all(key not in ' '.join(cmd) for cmd,_ in self.commands))
        self.assertFalse(self.stopped)
        with self.assertRaises(FileExistsError):m.run(str(self.root/'status'),str(self.output),'a'*40,'b'*64)

    def test_new_run_rotates_keys_and_ports(self):
        first=m.run(str(self.root/'status'),str(self.output),'a'*40,'b'*64)
        second_dir=self.root/'run2'
        second=m.run(str(self.root/'status'),str(second_dir),'a'*40,'b'*64)
        self.assertNotEqual(first['gateway_port'],second['gateway_port'])
        self.assertNotEqual(json.loads((self.output/'private-keys.json').read_text())['gateway'],
                            json.loads((second_dir/'private-keys.json').read_text())['gateway'])

    def test_failure_stops_only_children_started_here(self):
        with patch.object(m,'wait_ready',side_effect=RuntimeError('fail')):
            with self.assertRaises(RuntimeError):m.run(str(self.root/'status'),str(self.output),'a'*40,'b'*64)
        self.assertEqual(self.stopped,self.processes)
        self.assertEqual(len(self.stopped),1)
        self.assertFalse((self.output/'ready.json').exists())

    def test_unconfirmed_cleanup_records_group_for_manual_inspection(self):
        with patch.object(m,'start_owned',side_effect=m.CleanupUnconfirmed([77])):
            with self.assertRaises(m.CleanupUnconfirmed):
                m.run(str(self.root/'status'),str(self.output),'a'*40,'b'*64)
        self.assertEqual(json.loads((self.output/'cleanup-unconfirmed.json').read_text()),{'group_ids':[77]})
        self.assertFalse((self.output/'ready.json').exists())


class OwnershipTests(unittest.TestCase):
    def test_startup_leader_already_gone_reports_orphan_without_signal(self):
        proc=types.SimpleNamespace(pid=77,poll=lambda:0)
        with patch.object(m.subprocess,'Popen',return_value=proc), \
             patch.object(m,'process_stat',side_effect=FileNotFoundError), \
             patch.object(m,'live_group',return_value={78:6}), \
             patch.object(m.os,'killpg') as kill:
            with self.assertRaisesRegex(RuntimeError,'owned_process_groups_not_confirmed_stopped'):
                m.start_owned(['example'],{})
            kill.assert_not_called()

    def test_reject_foreign_listener_and_verify_owned_socket(self):
        root=Path(tempfile.mkdtemp(prefix='sanmou-restart-test-')).resolve()
        (root/'net').mkdir(); (root/'77/fd').mkdir(parents=True)
        (root/'net/tcp').write_text('header\n0: 0100007F:3039 00000000:0000 0A 0 0 0 0 0 123\n')
        (root/'77/fd/3').symlink_to('socket:[456]')
        with patch.object(m.os,'getpgid',return_value=77):
            self.assertFalse(m.listener_owned_by_group(12345,77,root))
            (root/'77/fd/4').symlink_to('socket:[123]')
            self.assertTrue(m.listener_owned_by_group(12345,77,root))
            (root/'net/tcp').write_text('header\n0: 00000000:3039 00000000:0000 0A 0 0 0 0 0 123\n')
            self.assertFalse(m.listener_owned_by_group(12345,77,root))

    def test_foreign_listener_never_receives_health_request(self):
        proc=types.SimpleNamespace(pid=77,poll=lambda:None)
        opener=types.SimpleNamespace(open=lambda *a,**k:self.fail('foreign listener was contacted'))
        with patch.object(m.urllib.request,'build_opener',return_value=opener), \
             patch.object(m,'listener_owned_by_group',return_value=False), \
             patch.object(m.time,'monotonic',side_effect=[0,0,2]), \
             patch.object(m.time,'sleep'):
            with self.assertRaises(TimeoutError):m.wait_ready('http://127.0.0.1:12345/health',12345,proc,1)

    def test_cleanup_does_not_claim_or_kill_orphaned_child(self):
        proc=types.SimpleNamespace(pid=77,sanmou_starttime=5,poll=lambda:None)
        with patch.object(m,'live_group',side_effect=[{77:5,78:6},{78:6},{78:6}]), \
             patch.object(m.time,'monotonic',side_effect=[0,21]), \
             patch.object(m.os,'killpg') as kill:
            with self.assertRaisesRegex(RuntimeError,'owned_process_groups_not_confirmed_stopped'):
                m.stop_owned([proc])
            kill.assert_called_once_with(77,signal.SIGTERM)

if __name__=='__main__':unittest.main()
