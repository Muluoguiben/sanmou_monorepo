"""CPU-only packaging/provision-plan tests: never install or download anything."""
from contextlib import nullcontext
import gzip
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch


ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / 'scripts/model-serving'


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    imported = importlib.util.module_from_spec(spec)
    sys.modules[name] = imported
    spec.loader.exec_module(imported)
    return imported


bootstrap = module('colab_gateway_bootstrap', SCRIPTS / 'colab_gateway_bootstrap.py')
packer = module('prepare_colab_gateway_bundle', SCRIPTS / 'prepare_colab_gateway_bundle.py')


class ColabGatewayBootstrapTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='sanmou-bootstrap-test-')
        self.addCleanup(self.temporary.cleanup)
        self.scratch = Path(self.temporary.name).resolve()
        self.repo = self.scratch / 'repo'
        self.repo.mkdir()
        self.git('init', '--quiet')
        self.tracked = {
            'packages/sanmou-common/src/sanmou_common/ports.py': b'original = True\n',
            'packages/pioneer-agent/src/pioneer_agent/__init__.py': b'"""synthetic source"""\n',
            'scripts/model-serving/native_runtime_manifest.py': b'# synthetic collector fixture\n',
            'scripts/model-serving/live_gateway_roundtrip.py': b'# synthetic runner fixture\n',
            'scripts/model-serving/live_gateway_scenario.json': b'{"synthetic":true}\n',
            bootstrap.BOOTSTRAP_PATH: (SCRIPTS / 'colab_gateway_bootstrap.py').read_bytes(),
            bootstrap.LOCK_PATH: (ROOT / bootstrap.LOCK_PATH).read_bytes(),
            bootstrap.MODEL_FILES_PATH: (ROOT / bootstrap.MODEL_FILES_PATH).read_bytes(),
            'scripts/model-serving/.env': b'SECRET_MUST_NOT_EXPORT=synthetic\n',
            'scripts/model-serving/id_rsa': b'-----BEGIN OPENSSH PRIVATE KEY-----\nsynthetic\n',
            'outside/private.json': b'{"secret":"out_of_scope"}\n',
        }
        for name in bootstrap.REQUIRED_SOURCE_FILES:
            self.tracked.setdefault(name, b'# synthetic required source\n')
        for path, raw in self.tracked.items():
            destination = self.repo / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(raw)
        self.revision = self.commit()

    def git(self, *args):
        env = {name: value for name, value in os.environ.items() if not name.startswith('GIT_')}
        return subprocess.check_output(['git', '-c', 'core.hooksPath=/dev/null', '-c', 'commit.gpgsign=false',
                                        '-c', 'user.name=Synthetic CPU Test', '-c', 'user.email=cpu@example.invalid', *args],
                                       cwd=self.repo, env=env, stderr=subprocess.DEVNULL).decode().strip()

    def commit(self):
        self.git('add', '-f', '.')
        self.git('commit', '--quiet', '-m', 'synthetic source fixture')
        return self.git('rev-parse', 'HEAD')

    def bundle(self, name='bundle'):
        destination = self.scratch / name
        result = packer.build_bundle(self.repo, self.revision, destination)
        return destination, result

    def rewrite_archive(self, directory, modifier):
        _, _, payloads = bootstrap.verify_bundle(directory)
        raw = io.BytesIO()
        with gzip.GzipFile(fileobj=raw, mode='wb', mtime=0) as stream:
            with tarfile.open(fileobj=stream, mode='w', format=tarfile.USTAR_FORMAT) as archive:
                for index, (name, data) in enumerate(sorted(payloads.items())):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode = len(data), 0o644
                    modified = modifier(index, info, data)
                    for entry, content in modified:
                        archive.addfile(entry, io.BytesIO(content) if entry.isfile() else None)
        archive_raw = raw.getvalue()
        (directory / 'source.tar.gz').write_bytes(archive_raw)
        manifest = json.loads((directory / 'bundle-manifest.json').read_bytes())
        manifest['archive'].update(bytes=len(archive_raw), sha256=bootstrap.sha256(archive_raw))
        manifest_raw = bootstrap.json_bytes(manifest)
        (directory / 'bundle-manifest.json').write_bytes(manifest_raw)
        (directory / 'bundle-manifest.sha256').write_text(bootstrap.sha256(manifest_raw) + '\n')

    def test_only_allowlisted_committed_regular_source_and_no_git_history(self):
        original = self.repo / 'packages/sanmou-common/src/sanmou_common/ports.py'
        original.write_bytes(b'uncommitted = True\n')
        (self.repo / 'scripts/model-serving/untracked.py').write_bytes(b'not committed\n')
        path, result = self.bundle()
        manifest, inventory_raw, payloads = bootstrap.verify_bundle(path)
        inventory = json.loads(inventory_raw)
        self.assertEqual(inventory['schema'], 'sanmou-colab-source-inventory-v1')
        self.assertEqual(manifest['source_commit'], self.revision)
        self.assertEqual(payloads['packages/sanmou-common/src/sanmou_common/ports.py'], b'original = True\n')
        self.assertFalse(result['git_history_included'])
        self.assertFalse(any('/.git/' in name or name.endswith(('.env', 'id_rsa', 'untracked.py')) or name.startswith('outside/') for name in payloads))
        self.assertEqual(set(payloads), set(inventory['files']))
        self.assertNotIn('source-inventory.json', payloads)
        self.assertEqual((path / 'colab_gateway_bootstrap.py').read_bytes(), payloads[bootstrap.BOOTSTRAP_PATH])

    def test_same_commit_produces_identical_tar_inventory_and_manifest(self):
        first, _ = self.bundle('first')
        second, _ = self.bundle('second')
        for name in ('source.tar.gz', 'source-inventory.json', 'bundle-manifest.json', 'bundle-manifest.sha256'):
            self.assertEqual((first / name).read_bytes(), (second / name).read_bytes())

    def test_mutable_ref_or_wrong_object_rejected(self):
        for revision in ('HEAD', 'master', self.revision[:8], '0' * 40):
            with self.subTest(revision=revision), self.assertRaises(bootstrap.BootstrapError):
                packer.collect_source(self.repo, revision)

    def test_tracked_symlink_is_rejected(self):
        path = self.repo / 'packages/sanmou-common/src/sanmou_common/linked.py'
        path.symlink_to(self.scratch / 'outside')
        self.revision = self.commit()
        with self.assertRaises(bootstrap.BootstrapError):
            self.bundle()

    def test_tracked_credential_in_ordinary_code_is_rejected(self):
        path = self.repo / 'scripts/model-serving/config.py'
        path.write_text('key="' + 'sk-' + 'a' * 30 + '"\n')
        self.revision = self.commit()
        with self.assertRaises(bootstrap.BootstrapError):
            self.bundle()

    def test_changed_historical_lock_is_not_reused_as_verified_lock(self):
        (self.repo / bootstrap.LOCK_PATH).write_text('sglang==9.9.9\n')
        self.revision = self.commit()
        with self.assertRaisesRegex(bootstrap.BootstrapError, 'previous_verified'):
            self.bundle()

    def test_required_source_set_and_private_names(self):
        directory, _ = self.bundle()
        _, raw, _ = bootstrap.verify_bundle(directory)
        for missing in bootstrap.REQUIRED_SOURCE_FILES:
            inventory = json.loads(raw)
            inventory['files'].pop(missing)
            with self.subTest(missing=missing), self.assertRaises(bootstrap.BootstrapError):
                bootstrap.validate_inventory(inventory)
        for name in ('secrets.py', 'service_credentials.txt', 'api_key.txt', 'private-key.json',
                     'id_ed25519', 'certificate.p12', '.env', '.git/config'):
            path = 'scripts/model-serving/' + name
            self.assertTrue(bootstrap.forbidden_source_name(path))
            inventory = json.loads(raw)
            inventory['files'][path] = {'bytes': 0, 'sha256': bootstrap.sha256(b'')}
            with self.subTest(path=path), self.assertRaises(bootstrap.BootstrapError):
                bootstrap.validate_inventory(inventory)

    def test_native_collector_source_contract_when_integrated(self):
        path = SCRIPTS / 'native_runtime_manifest.py'
        if not path.exists():
            self.skipTest('native collector lives in its parallel branch until integration')
        native = module('native_colab_contract_check', path)
        self.assertEqual(native.REQUIRED_SOURCE_FILES, bootstrap.REQUIRED_SOURCE_FILES)
        self.assertEqual(native.PRIVATE_NAME_RE.pattern, bootstrap.PRIVATE_NAME_RE.pattern)
        directory, _ = self.bundle()
        _, raw, _ = bootstrap.verify_bundle(directory)
        inventory = json.loads(raw)
        self.assertEqual(native._source_inventory(inventory), bootstrap.validate_inventory(inventory))

    def test_output_and_extract_never_overwrite_existing_data(self):
        directory, _ = self.bundle()
        before = {p.name: p.read_bytes() for p in directory.iterdir()}
        with self.assertRaises(FileExistsError):
            packer.build_bundle(self.repo, self.revision, directory)
        self.assertEqual(before, {p.name: p.read_bytes() for p in directory.iterdir()})
        _, raw, payloads = bootstrap.verify_bundle(directory)
        task = self.scratch / 'task'
        task.mkdir()
        (task / 'source').mkdir()
        sentinel = task / 'source/keep.txt'
        sentinel.write_text('user data')
        with self.assertRaises(FileExistsError):
            bootstrap.extract_source(task, raw, payloads)
        self.assertEqual(sentinel.read_text(), 'user data')

    def test_extract_rejects_altered_payload_before_writing(self):
        directory, _ = self.bundle()
        _, raw, payloads = bootstrap.verify_bundle(directory)
        task = self.scratch / 'task'
        task.mkdir()
        payloads[bootstrap.BOOTSTRAP_PATH] = b'bad'
        with self.assertRaises(bootstrap.BootstrapError):
            bootstrap.extract_source(task, raw, payloads)
        self.assertFalse((task / 'source').exists())

    def test_prepare_extracts_without_gpu_subprocess_or_network(self):
        directory, _ = self.bundle()
        with patch.object(bootstrap.subprocess, 'Popen', side_effect=AssertionError('no subprocess')):
            result = bootstrap.prepare(directory, work_root=self.scratch, provision=False)
        self.assertEqual(result['status'], 'prepared')
        self.assertFalse(result['sglang_started'])
        self.assertFalse(result['gateway_started'])
        self.assertEqual(result['model_generation_requests'], 0)
        self.assertFalse(result['venv_ready'])
        self.assertFalse(result['model_files_verified'])
        self.assertIn('--describe-scenario', result['next_command_templates']['describe_scenario'])
        source = Path(result['source_root'])
        inventory = json.loads((source / 'source-inventory.json').read_bytes())
        for name, item in inventory['files'].items():
            raw = (source / name).read_bytes()
            self.assertEqual((len(raw), bootstrap.sha256(raw)), (item['bytes'], item['sha256']))
        self.assertFalse((source / '.git').exists())

    def test_tar_links_escape_duplicate_extra_and_mode_rejected(self):
        for kind in ('symlink', 'hardlink', 'escape', 'duplicate', 'extra', 'setuid', 'missing'):
            directory, _ = self.bundle(kind)
            def modify(index, entry, raw):
                if index:
                    return [(entry, raw)]
                if kind == 'symlink': entry.type, entry.linkname, entry.size = tarfile.SYMTYPE, '/tmp/unrelated', 0
                elif kind == 'hardlink': entry.type, entry.linkname, entry.size = tarfile.LNKTYPE, '/tmp/unrelated', 0
                elif kind == 'escape': entry.name = '../escape.py'
                elif kind == 'duplicate': return [(entry, raw), (entry, raw)]
                elif kind == 'extra': entry.name = 'unlisted.py'
                elif kind == 'setuid': entry.mode = 0o4755
                elif kind == 'missing': return []
                return [(entry, raw)]
            self.rewrite_archive(directory, modify)
            with self.subTest(kind=kind), self.assertRaises(bootstrap.BootstrapError):
                bootstrap.verify_bundle(directory)

    def test_bundle_tamper_extra_file_and_link_rejected(self):
        directory, _ = self.bundle('tampered')
        (directory / 'source.tar.gz').write_bytes(b'not an archive')
        with self.assertRaises(bootstrap.BootstrapError):bootstrap.verify_bundle(directory)
        directory, _ = self.bundle('extra')
        (directory / 'extra.json').write_text('{}')
        with self.assertRaises(bootstrap.BootstrapError):bootstrap.verify_bundle(directory)
        directory, _ = self.bundle('linked')
        alias = self.scratch / 'bundle-link'
        alias.symlink_to(directory, target_is_directory=True)
        with self.assertRaises(OSError):bootstrap.verify_bundle(alias)
        linked_copy = self.scratch / 'manifest-link'
        os.link(directory / 'bundle-manifest.json', linked_copy)
        with self.assertRaises(bootstrap.BootstrapError):bootstrap.verify_bundle(directory)

    def test_subprocess_environment_ignores_package_indexes_and_auth(self):
        old_home = os.environ.get('HOME')
        with patch.dict(os.environ, {'PIP_INDEX_URL': 'https://user:secret@invalid.example/simple',
                                    'PIP_EXTRA_INDEX_URL': 'https://private.example/simple', 'PIP_TRUSTED_HOST': 'bad',
                                    'HF_TOKEN': 'synthetic-secret', 'HTTPS_PROXY': 'https://proxy:password@invalid.example'}):
            env = bootstrap.isolated_env(self.scratch, self.repo)
        self.assertEqual(env.get('HOME'), old_home)
        self.assertEqual(env['PIP_CONFIG_FILE'], os.devnull)
        for forbidden in ('PIP_INDEX_URL', 'PIP_EXTRA_INDEX_URL', 'PIP_TRUSTED_HOST', 'HF_TOKEN', 'HTTPS_PROXY'):
            self.assertNotIn(forbidden, env)
        self.assertTrue(env['PATH'].startswith(str(self.scratch / 'venv/bin') + os.pathsep))
        self.assertEqual(env['HF_HOME'], str(self.scratch / 'hf-home'))
        self.assertEqual(env['HF_HUB_DISABLE_IMPLICIT_TOKEN'], '1')

    def test_exact_pip_plan_and_bounded_steps(self):
        steps = bootstrap.provision_commands(self.scratch, self.repo, '/usr/bin/python3.12', '/usr/local/bin/python')
        commands = {name: command for name, command, _ in steps}
        self.assertIn('--without-pip', commands['create-venv'])
        self.assertIn('--python', commands['bootstrap-pip'])
        self.assertIn('pip==26.2.2', commands['bootstrap-pip'])
        for name in ('bootstrap-pip', 'install-lock'):
            command = commands[name]
            self.assertEqual(command[command.index('--index-url') + 1], 'https://pypi.org/simple')
            self.assertEqual(command[command.index('--cache-dir') + 1], str(self.scratch / 'pip-cache'))
            self.assertNotIn('--pre', command)
            self.assertNotIn('--extra-index-url', command)
        self.assertIn('--no-deps', commands['install-lock'])
        self.assertIn('--only-binary=outlines-core', commands['install-lock'])
        self.assertTrue(all(type(timeout) is int and 0 < timeout <= 3600 for _, _, timeout in steps))
        self.assertTrue(all('sglang.launch_server' not in ' '.join(command) for _, command, _ in steps))
        self.assertIn('pioneer_agent.app.policy_gateway', commands['gateway-import-readiness'][-1])
        self.assertIn("run_name='sanmou_gateway_readiness'", commands['gateway-import-readiness'][-1])
        self.assertNotIn("run_name='__main__'", commands['gateway-import-readiness'][-1])

    def test_download_is_fixed_revision_anonymous_and_private_cache(self):
        command = bootstrap.download_command(self.scratch, self.repo)
        program = command[-1]
        self.assertIn(bootstrap.MODEL_REVISION, program)
        self.assertIn('token=False', program)
        self.assertIn('allow_patterns=list(files)', program)
        self.assertIn(str(self.scratch / 'model-download'), program)
        self.assertIn(str(self.scratch / 'hf-cache'), program)
        self.assertNotIn('token=True', program)

    def test_idle_a100_preflight_rules(self):
        good = '0, NVIDIA A100-SXM4-80GB, 81920, 0, 0\n'
        self.assertEqual(bootstrap.validate_gpu_rows(good, '')['compute_processes'], 0)
        for row, processes in ((good, '1234'), (good + good, ''),
                               ('0, NVIDIA A100-SXM4-40GB, 40960, 0, 0', ''),
                               ('0, NVIDIA L4, 81920, 0, 0', ''),
                               ('0, NVIDIA A100, nan, 0, 0', ''),
                               ('0, NVIDIA A100, 81920, 1024, 0', ''),
                               ('0, NVIDIA A100, 81920, 0, 3', '')):
            with self.subTest(row=row), self.assertRaises(bootstrap.BootstrapError):
                bootstrap.validate_gpu_rows(row, processes)

    def test_preflight_disk_threshold_without_running_nvidia(self):
        answers = [SimpleNamespace(stdout='Python 3.12.3\n'),
                   SimpleNamespace(stdout='0, NVIDIA A100-SXM4-80GB, 81920, 0, 0\n'), SimpleNamespace(stdout='')]
        with patch.object(bootstrap.sys, 'platform', 'linux'), patch.object(bootstrap, 'open_directory', return_value=nullcontext()), \
                patch.object(bootstrap.shutil, 'which', return_value='/usr/bin/python3.12'), \
                patch.object(bootstrap.subprocess, 'run', side_effect=answers) as run, \
                patch.object(bootstrap.shutil, 'disk_usage', return_value=SimpleNamespace(free=79 * 1024**3)):
            with self.assertRaisesRegex(bootstrap.BootstrapError, 'insufficient_disk'):
                bootstrap.preflight(Path('/content'), 100)
        self.assertTrue(all(call.kwargs['timeout'] == 30 for call in run.call_args_list))

    def test_logs_redact_credentials_and_step_failure_has_status(self):
        process = Mock(returncode=1)
        process.communicate.return_value = (b'Bearer abcdef123456\nhttps://user:password@example.invalid/x?token=secret\nhf_abcdefghijklmnopqrstuv\napi_key=secretvalue\n', None)
        with patch.object(bootstrap.subprocess, 'Popen', return_value=process) as popen:
            with self.assertRaisesRegex(bootstrap.BootstrapError, 'stage_failed:install'):
                bootstrap.run_step('install', ['synthetic-command'], timeout=3, task=self.scratch, env={})
        raw = (self.scratch / 'install.log').read_text()
        self.assertNotIn('password', raw)
        self.assertNotIn('secretvalue', raw)
        self.assertNotIn('abcdefghijklmnopqrstuv', raw)
        self.assertIn('[REDACTED]', raw)
        self.assertEqual(json.loads((self.scratch / 'install.json').read_text())['status'], 'failed')
        self.assertTrue(popen.call_args.kwargs['start_new_session'])

    def test_timeout_targets_only_created_process_group(self):
        process = Mock(pid=987654, returncode=-15)
        process.communicate.side_effect = [subprocess.TimeoutExpired(['synthetic'], 1), (b'timed out', None)]
        with patch.object(bootstrap.subprocess, 'Popen', return_value=process), patch.object(bootstrap.os, 'killpg') as killpg:
            with self.assertRaises(bootstrap.BootstrapError):
                bootstrap.run_step('timeout', ['synthetic'], timeout=1, task=self.scratch, env={})
        killpg.assert_called_once_with(987654, bootstrap.signal.SIGTERM)
        self.assertEqual(json.loads((self.scratch / 'timeout.json').read_text())['status'], 'timeout')

    def test_status_fsync_failure_cannot_leave_success_completion_marker(self):
        with patch.object(bootstrap.os, 'fsync', side_effect=OSError('synthetic fsync failure')):
            with self.assertRaises(OSError):
                bootstrap.publish_status(self.scratch, {'status': 'provisioned'})
        self.assertFalse((self.scratch / 'provision-status.json').exists())
        self.assertTrue((self.scratch / 'provision-status.pending.json').exists())

    def test_status_atomic_publication_is_create_only(self):
        bootstrap.publish_status(self.scratch, {'status': 'prepared'})
        self.assertEqual(json.loads((self.scratch / 'provision-status.json').read_text())['status'], 'prepared')
        with self.assertRaises(FileExistsError):
            bootstrap.publish_status(self.scratch, {'status': 'provisioned'})
        self.assertEqual(json.loads((self.scratch / 'provision-status.json').read_text())['status'], 'prepared')


if __name__ == '__main__':
    unittest.main()
