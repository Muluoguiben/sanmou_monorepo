#!/usr/bin/env python3
"""Start a fresh task from an existing, provisioned Colab runtime.

No runtime is allocated or deleted. Output must be a new private directory.
"""
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import shutil
import signal
import socket
import stat
import subprocess
import sys
import time
import urllib.error
import urllib.request


class CleanupUnconfirmed(RuntimeError):
    def __init__(self, group_ids):
        self.group_ids = list(group_ids)
        super().__init__('owned_process_groups_not_confirmed_stopped')


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def checked_path(root, relative):
    rel = PurePosixPath(relative)
    if rel.is_absolute() or not rel.parts or any(x in ('', '.', '..') for x in rel.parts):
        raise ValueError('invalid_inventory_path')
    path = root
    for part in rel.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('symlink_in_inventory')
    if not path.is_file():
        raise ValueError('missing_inventory_file')
    return path


def verify_provision(status_path, expected_commit, expected_inventory_sha256):
    status_path = Path(status_path)
    if not status_path.is_absolute() or status_path.resolve() != status_path:
        raise ValueError('invalid_status_path')
    status = json.loads(status_path.read_text())
    if status.get('status') != 'provisioned' or status.get('source_commit') != expected_commit:
        raise ValueError('provision_identity_mismatch')
    root = status_path.parent
    source = root / 'source'
    model = root / 'model'
    python = root / 'venv/bin/python'
    inventory = source / 'source-inventory.json'
    expected_files = source / 'docs/test-reports/2026-10-24/colab-native/model-files.json'
    required = {'source_root': source, 'model_dir': model, 'python': python,
                'source_inventory': inventory, 'expected_model_files': expected_files}
    if any(status.get(k) != str(v) for k, v in required.items()):
        raise ValueError('provision_paths_mismatch')
    if source.is_symlink() or model.is_symlink() or not python.is_file():
        raise ValueError('provision_resources_unavailable')
    if (inventory.is_symlink() or not inventory.is_file() or inventory.stat().st_nlink != 1
            or digest(inventory) != expected_inventory_sha256
            or status.get('source_inventory_sha256') != expected_inventory_sha256):
        raise ValueError('source_inventory_mismatch')
    inv = json.loads(inventory.read_text())
    if inv.get('source_commit') != expected_commit or inv.get('schema') != 'sanmou-colab-source-inventory-v1':
        raise ValueError('source_inventory_identity_mismatch')
    files = inv.get('files')
    if not isinstance(files, dict) or not files:
        raise ValueError('invalid_source_inventory')
    allowed = set(files) | {'source-inventory.json'}
    actual = set()
    def fail_walk(error):
        raise error
    for parent, directories, filenames in os.walk(source, followlinks=False, onerror=fail_walk):
        for name in directories:
            if (Path(parent)/name).is_symlink():
                raise ValueError('symlink_in_source_tree')
        for name in filenames:
            path = Path(parent)/name
            info = path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
                raise ValueError('unsafe_source_file')
            actual.add(path.relative_to(source).as_posix())
    if actual != allowed:
        raise ValueError('source_tree_inventory_mismatch')
    for name, entry in files.items():
        path = checked_path(source, name)
        if path.stat().st_size != entry['bytes'] or digest(path) != entry['sha256']:
            raise ValueError('source_file_mismatch')
    for name in ('scripts/model-serving/colab_gateway_bootstrap.py',
                 'scripts/model-serving/live_gateway_roundtrip.py',
                 'scripts/model-serving/native_runtime_manifest.py',
                 'docs/test-reports/2026-10-24/colab-native/model-files.json'):
        if name not in files:
            raise ValueError('required_source_missing')
    return status, source, model, python


def check_gpu():
    cmd = ['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits']
    lines = subprocess.check_output(cmd, text=True, timeout=20).strip().splitlines()
    if len(lines) != 1:
        raise ValueError('expected_one_gpu')
    name, total, used, utilization = [v.strip() for v in lines[0].split(',')]
    if 'A100' not in name or int(total) < 80000 or int(used) > 512 or int(utilization) != 0:
        raise ValueError('gpu_precondition_failed')
    active = subprocess.check_output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'], text=True, timeout=20).strip()
    if active:
        raise ValueError('gpu_processes_present')


def write_json(path, value):
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2)


def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1', 0))
        return s.getsockname()[1]


def start_owned(command, env):
    # Discard child output: it may contain keys, and this launcher exits while
    # its services remain alive, so in-process pipe drainers are unsuitable.
    proc = subprocess.Popen(command, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        proc.sanmou_starttime = process_stat(proc.pid)[2]
    except BaseException:
        if proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
                proc.wait(timeout=20)
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            remaining = live_group(proc.pid)
        except Exception:
            raise CleanupUnconfirmed([proc.pid]) from None
        if remaining:
            # The unverified leader may already have exited. Do not signal
            # a group whose identity can no longer be established.
            raise CleanupUnconfirmed([proc.pid]) from None
        raise
    return proc


def process_stat(pid, proc_root=Path('/proc')):
    # Linux /proc stat: state (field 3), pgrp (5), starttime (22).
    rest = (proc_root/str(pid)/'stat').read_text().rsplit(') ', 1)[1].split()
    return rest[0], int(rest[2]), int(rest[19])


def live_group(group, proc_root=Path('/proc')):
    result = {}
    for path in proc_root.iterdir():
        if path.name.isdigit():
            try:
                state, pgrp, started = process_stat(int(path.name), proc_root)
                if pgrp == group and state != 'Z':
                    result[int(path.name)] = started
            except FileNotFoundError:
                continue
    return result


def listener_owned_by_group(port, process_group, proc_root=Path('/proc')):
    """Require each LISTEN socket on this port to belong to the child group."""
    inodes = set()
    for name in ('tcp', 'tcp6'):
        try:
            lines = (proc_root/'net'/name).read_text().splitlines()[1:]
        except FileNotFoundError:
            if name == 'tcp6':
                continue
            raise
        for line in lines:
            fields = line.split()
            if len(fields) < 10:
                raise ValueError('invalid_socket_table')
            if fields[3] == '0A' and int(fields[1].rsplit(':', 1)[1], 16) == port:
                if name != 'tcp' or fields[1].split(':', 1)[0] != '0100007F':
                    return False
                inodes.add(fields[9])
    if not inodes:
        return False
    owned = set()
    for entry in proc_root.iterdir():
        if not entry.name.isdigit():
            continue
        try:
            if os.getpgid(int(entry.name)) != process_group:
                continue
            for fd in (entry/'fd').iterdir():
                try:
                    target = os.readlink(fd)
                except FileNotFoundError:
                    continue
                if target.startswith('socket:[') and target.endswith(']'):
                    owned.add(target[8:-1])
        except (FileNotFoundError, ProcessLookupError):
            continue
    return inodes <= owned


def wait_ready(url, port, proc, seconds, *, gateway=False):
    deadline = time.monotonic() + seconds
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            raise RuntimeError('owned_process_exited')
        if not listener_owned_by_group(port, proc.pid):
            time.sleep(2)
            continue
        try:
            with opener.open(url, timeout=3) as response:
                valid = response.status == 200
                if gateway:
                    valid = valid and json.loads(response.read(1024)) == {
                        'status': 'ok', 'service': 'policy-gateway'}
                if valid and proc.poll() is None and listener_owned_by_group(port, proc.pid):
                    return
        except (OSError, urllib.error.URLError, ValueError):
            time.sleep(2)
    raise TimeoutError('readiness_timeout')


def stop_owned(processes):
    remaining = []
    for proc in reversed(processes):
        members = live_group(proc.pid)
        if not members:
            continue
        # Refuse to signal an orphaned group or a reused leader PID.
        if members.get(proc.pid) == proc.sanmou_starttime and proc.poll() is None:
            try:
                os.killpg(proc.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        else:
            remaining.append(proc.pid)
            continue
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and live_group(proc.pid):
            time.sleep(0.2)
        members = live_group(proc.pid)
        if members:
            if members.get(proc.pid) == proc.sanmou_starttime and proc.poll() is None:
                os.killpg(proc.pid, signal.SIGKILL)
                deadline = time.monotonic() + 10
                while time.monotonic() < deadline and live_group(proc.pid):
                    time.sleep(0.2)
            if live_group(proc.pid):
                remaining.append(proc.pid)
    if remaining:
        raise CleanupUnconfirmed(remaining)


def run(status_path, output, expected_commit, expected_inventory_sha256):
    if not re.fullmatch(r'[0-9a-f]{40}', expected_commit):
        raise ValueError('full_source_commit_required')
    if not re.fullmatch(r'[0-9a-f]{64}', expected_inventory_sha256):
        raise ValueError('source_inventory_sha256_required')
    output = Path(output)
    if not output.is_absolute() or output.parent.resolve(strict=True) != output.parent:
        raise ValueError('output_requires_absolute_nonsymlink_parent')
    status, source, model_dir, python = verify_provision(status_path, expected_commit, expected_inventory_sha256)
    check_gpu()
    if shutil.disk_usage(output.parent).free < 10 * 1024 ** 3:
        raise ValueError('insufficient_disk_space')
    os.mkdir(output, 0o700)  # fails if any path already exists
    processes = []
    try:
        boot_path = source / 'scripts/model-serving/colab_gateway_bootstrap.py'
        spec = importlib.util.spec_from_file_location('gateway_bootstrap', boot_path)
        boot = importlib.util.module_from_spec(spec)
        previous_bytecode_setting = sys.dont_write_bytecode
        try:
            sys.dont_write_bytecode = True
            spec.loader.exec_module(boot)
        finally:
            sys.dont_write_bytecode = previous_bytecode_setting
        for name in ('tmp','hf-home','hf-cache','xdg-cache','torch-cache',
                     'torch-extensions','cuda-cache','triton-cache'):
            (output/name).mkdir(mode=0o700)
        env = boot.isolated_env(output, source)
        env['PATH'] = str(python.parent) + os.pathsep + env['PATH']
        env.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
        subprocess.run([str(python), '-m', 'pip', 'check'], env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=120)
        version_check = (
            "import torch,importlib.metadata as m; "
            "assert torch.__version__=='2.14.1+cu130' and torch.version.cuda=='13.0'; "
            "assert m.version('sglang')=='0.5.22' and m.version('transformers')=='5.19.0' "
            "and m.version('flashinfer-python')=='0.7.1'"
        )
        subprocess.run([str(python), '-c', version_check], env=env, stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, check=True, timeout=120)
        native_port, gateway_port = free_port(), free_port()
        if native_port == gateway_port:
            raise RuntimeError('port_collision')
        public = {'model-path':str(model_dir),'tokenizer-path':str(model_dir),
          'chat-template':str(model_dir/'chat_template.jinja'),'served-model-name':'sanmou-qwen35-9b-gateway',
          'host':'127.0.0.1','port':native_port,'dtype':'bfloat16','load-format':'safetensors',
          'tensor-parallel-size':1,'data-parallel-size':1,'context-length':8192,'mem-fraction-static':0.55,
          'max-running-requests':1,'chunked-prefill-size':1024,'cuda-graph-backend-decode':'disabled',
          'cuda-graph-backend-prefill':'disabled','tool-call-parser':'qwen3_coder','reasoning-parser':'qwen3',
          'log-level':'warning','log-requests':False,'trust-remote-code':False,
          'limit-mm-data-per-request':{'image':0,'video':0,'audio':0},'skip-server-warmup':True}
        service, admin, gateway = [secrets.token_urlsafe(32) for _ in range(3)]
        write_json(output/'public-runtime.json', public)
        write_json(output/'private-runtime.yaml', dict(public, **{'api-key':service, 'admin-api-key':admin}))
        write_json(output/'private-keys.json', {'gateway':gateway, 'service':service})
        scenario = subprocess.run([str(python),str(source/'scripts/model-serving/live_gateway_roundtrip.py'),
                                   '--describe-scenario'], env=env, capture_output=True, text=True,
                                  timeout=30, check=True)
        scenario = json.loads(scenario.stdout)
        write_json(output/'sampling.json', scenario['sampling'])
        cmd=[str(python),str(source/'scripts/model-serving/native_runtime_manifest.py'),
          '--model-dir',str(model_dir),'--runtime-config',str(output/'public-runtime.json'),
          '--expected-model-files',status['expected_model_files'],'--sampling',str(output/'sampling.json'),
          '--prompt-sha256',scenario['prompt_sha256'],'--source-root',str(source),
          '--source-inventory',status['source_inventory'],'--output',str(output/'native-binding')]
        # Collector verifies the reviewed model hashes, installed dependency versions and source.
        subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=600, check=True)
        check_gpu()  # recheck immediately before starting model
        model = start_owned(['timeout','1500',str(python),'-m','sglang.launch_server',
                             '--config',str(output/'private-runtime.yaml')], env)
        processes.append(model)
        write_json(output/'model-process.json', {'pid':model.pid})
        wait_ready(f'http://127.0.0.1:{native_port}/health', native_port, model, 360)
        genv=dict(env, POLICY_GATEWAY_API_KEY=gateway, SGLANG_API_KEY=service)
        gw = start_owned(['timeout','1500',str(python),'-m','pioneer_agent.app.policy_gateway',
            '--manifest',str(output/'native-binding/policy-manifest.json'),
            '--upstream',f'http://127.0.0.1:{native_port}','--port',str(gateway_port),
            '--timeout','185'], genv)
        processes.append(gw)
        write_json(output/'gateway-process.json', {'pid':gw.pid})
        wait_ready(f'http://127.0.0.1:{gateway_port}/health', gateway_port, gw, 30, gateway=True)
        result={'status':'ready','gateway_port':gateway_port,'model_port':native_port,
                'manifest':str(output/'native-binding/policy-manifest.json'),
                'binding':str(output/'native-binding/runtime-receipt.json'),
                'keys':str(output/'private-keys.json'),'model_pid':model.pid,'gateway_pid':gw.pid,
                'source_commit':expected_commit}
        write_json(output/'ready.json', result)
        return result
    except BaseException as exc:
        unconfirmed = list(exc.group_ids) if isinstance(exc, CleanupUnconfirmed) else []
        try:
            stop_owned(processes)
        except CleanupUnconfirmed as cleanup:
            unconfirmed.extend(cleanup.group_ids)
        except Exception:
            # Enumeration/permission failures also mean no process group can
            # be declared stopped; preserve every owned group for inspection.
            unconfirmed.extend(proc.pid for proc in processes)
        if unconfirmed:
            try:
                write_json(output/'cleanup-unconfirmed.json', {'group_ids': sorted(set(unconfirmed))})
            except OSError:
                pass
            raise CleanupUnconfirmed(unconfirmed) from None
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--status', required=True)
    parser.add_argument('--output', required=True)
    parser.add_argument('--source-commit', required=True)
    parser.add_argument('--source-inventory-sha256', required=True)
    args=parser.parse_args()
    try:
        result=run(args.status,args.output,args.source_commit,args.source_inventory_sha256)
        print(json.dumps({'status':'ready','gateway_port':result['gateway_port']}))
    except CleanupUnconfirmed as exc:
        print('startup_failed: cleanup_unconfirmed; group_ids:', sorted(set(exc.group_ids)))
        raise SystemExit(1)
    except Exception as exc:
        # Do not print child output, credentials, or exception details.
        print('startup_failed:', type(exc).__name__)
        raise SystemExit(1)


if __name__ == '__main__':
    main()
