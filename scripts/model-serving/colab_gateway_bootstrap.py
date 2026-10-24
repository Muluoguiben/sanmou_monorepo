#!/usr/bin/env python3
"""Verify/extract a committed source bundle and optionally provision Colab.

No runtime creation, service startup, model generation, game input, or cleanup.
All installations, caches, and downloaded model files live in one new task dir.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import signal
import stat
import subprocess
import sys
import tarfile
import tempfile
import time

SOURCE_ROOTS = ('packages/sanmou-common/src/', 'packages/pioneer-agent/src/', 'scripts/model-serving/')
LOCK_PATH = 'docs/test-reports/2026-10-24/colab-native/requirements-py312.lock'
MODEL_FILES_PATH = 'docs/test-reports/2026-10-24/colab-native/model-files.json'
EXTRA_FILES = (LOCK_PATH, MODEL_FILES_PATH)
BOOTSTRAP_PATH = 'scripts/model-serving/colab_gateway_bootstrap.py'
REQUIRED_SOURCE_FILES = {
    'packages/pioneer-agent/src/pioneer_agent/agent_harness/__init__.py',
    'packages/pioneer-agent/src/pioneer_agent/mcp_server/__init__.py',
    'packages/sanmou-common/src/sanmou_common/policy_contracts.py',
    'packages/pioneer-agent/src/pioneer_agent/adapters/policy_http.py',
    'packages/pioneer-agent/src/pioneer_agent/adapters/policy_service.py',
    'packages/pioneer-agent/src/pioneer_agent/app/policy_gateway.py',
    'packages/pioneer-agent/src/pioneer_agent/agent_harness/run_budget.py',
    'packages/pioneer-agent/src/pioneer_agent/agent_harness/task_contracts.py',
    'scripts/model-serving/native_runtime_manifest.py',
    'scripts/model-serving/live_gateway_roundtrip.py',
    'scripts/model-serving/live_gateway_scenario.json',
    BOOTSTRAP_PATH, LOCK_PATH, MODEL_FILES_PATH,
}
PRIVATE_NAME_RE = re.compile(r'(?:^|[/_.-])(?:secrets?|credentials|private[-_]key|api[-_]key)(?:[._/-]|$)', re.I)
MODEL_ID = 'Qwen/Qwen3.5-9B'
MODEL_REVISION = 'c202236235762e1c871ad0ccb60c8ee5ba337b9a'
LOCK_SHA256 = 'df23671ad3932e276ac023a9b6327beac87dc15f1efbbf2bab3f0814bd0dc228'
MODEL_FILES_SHA256 = '46e99d82dbb99e87895ec267b9d5165f513c26cc4e432582aaeeeef66edccb1a'
MAX_FILES = 1024
MAX_FILE_BYTES = 8 * 1024 * 1024
MAX_SOURCE_BYTES = 32 * 1024 * 1024
MAX_ARCHIVE_BYTES = 40 * 1024 * 1024
MAX_TAR_BYTES = 48 * 1024 * 1024
_HEX40 = re.compile(r'[0-9a-f]{40}\Z')
_HEX64 = re.compile(r'[0-9a-f]{64}\Z')
_SAFE_PART = re.compile(r'[A-Za-z0-9_-][A-Za-z0-9_.-]*\Z')


class BootstrapError(ValueError):
    """Stable local failure code; never includes credentials or command output."""


class ProvisionFailure(BootstrapError):
    def __init__(self, task: Path):
        super().__init__('provision_failed')
        self.task = task


def sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def json_bytes(value) -> bytes:
    return (json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False) + '\n').encode()


def json_object(raw: bytes):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise BootstrapError('duplicate_json_key')
            result[key] = value
        return result
    try:
        value = json.loads(raw, object_pairs_hook=pairs,
                           parse_constant=lambda _: (_ for _ in ()).throw(BootstrapError('nonfinite_json')))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise BootstrapError('invalid_json') from exc
    if not isinstance(value, dict):
        raise BootstrapError('json_object_required')
    return value


def safe_relative(name: str) -> str:
    if (not isinstance(name, str) or len(name) > 240 or '\\' in name
            or any(part in ('', '.', '..') or not _SAFE_PART.fullmatch(part) for part in name.split('/'))):
        raise BootstrapError('unsafe_relative_path')
    return name


def allowed_source(name: str) -> bool:
    safe_relative(name)
    return name in EXTRA_FILES or name.startswith(SOURCE_ROOTS)


def forbidden_source_name(name: str) -> bool:
    parts = PurePosixPath(name).parts
    return bool(PRIVATE_NAME_RE.search(name)) or any(part.startswith('.') or part == '__pycache__' or part.lower() in {
        'id_rsa', 'id_ed25519', 'id_ecdsa', 'credentials', 'credentials.json', 'secrets.json',
    } or part.lower().endswith(('.pem', '.key', '.p12', '.pfx', '.pyc', '.pyo')) for part in parts)


def validate_inventory(value: dict) -> dict:
    if set(value) != {'schema', 'source_commit', 'files'} or value['schema'] != 'sanmou-colab-source-inventory-v1':
        raise BootstrapError('source_inventory_schema')
    if not isinstance(value['source_commit'], str) or not _HEX40.fullmatch(value['source_commit']):
        raise BootstrapError('source_commit_not_pinned')
    files = value['files']
    if not isinstance(files, dict) or not 1 <= len(files) <= MAX_FILES:
        raise BootstrapError('source_file_count')
    if not REQUIRED_SOURCE_FILES <= set(files):
        raise BootstrapError('required_source_missing')
    if len({name.casefold() for name in files}) != len(files):
        raise BootstrapError('source_case_collision')
    total = 0
    for name, info in files.items():
        if not allowed_source(name) or forbidden_source_name(name):
            raise BootstrapError('source_path_not_allowed')
        if not isinstance(info, dict) or set(info) != {'bytes', 'sha256'}:
            raise BootstrapError('file_inventory_fields')
        if type(info['bytes']) is not int or not 0 <= info['bytes'] <= MAX_FILE_BYTES:
            raise BootstrapError('source_file_size')
        if not isinstance(info['sha256'], str) or not _HEX64.fullmatch(info['sha256']):
            raise BootstrapError('source_file_digest')
        total += info['bytes']
    if total > MAX_SOURCE_BYTES:
        raise BootstrapError('source_total_size')
    if files[LOCK_PATH]['sha256'] != LOCK_SHA256 or files[MODEL_FILES_PATH]['sha256'] != MODEL_FILES_SHA256:
        raise BootstrapError('previous_verified_dependency_or_model_inventory_changed')
    return value


@contextmanager
def open_directory(path: Path):
    if not all(hasattr(os, item) for item in ('O_DIRECTORY', 'O_NOFOLLOW', 'O_NONBLOCK')) or os.open not in os.supports_dir_fd:
        raise BootstrapError('secure_filesystem_unavailable')
    raw = os.fspath(path)
    if not raw.startswith('/') or any(p in ('', '.', '..') for p in raw.split('/')[1:]):
        raise BootstrapError('absolute_directory_required')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    fd = os.open('/', flags)
    try:
        for part in raw.split('/')[1:]:
            child = os.open(part, flags, dir_fd=fd)
            os.close(fd)
            fd = child
        yield fd
    finally:
        os.close(fd)


def read_regular(path: Path, limit: int) -> bytes:
    with open_directory(path.parent) as parent:
        fd = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        try:
            before = os.fstat(fd)
            if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size > limit:
                raise BootstrapError('not_bounded_regular_file')
            raw = bytearray()
            while len(raw) <= limit:
                chunk = os.read(fd, min(65536, limit + 1 - len(raw)))
                if not chunk:
                    break
                raw.extend(chunk)
            after = os.fstat(fd)
            current = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
            signature = lambda item: (item.st_dev, item.st_ino, item.st_mode, item.st_nlink,
                                      item.st_size, item.st_mtime_ns, item.st_ctime_ns)
            if len(raw) > limit or len(raw) != before.st_size or signature(before) != signature(after) or signature(after) != signature(current):
                raise BootstrapError('file_changed_during_read')
            return bytes(raw)
        finally:
            os.close(fd)


def write_new_at(root_fd: int, name: str, raw: bytes, mode: int = 0o600):
    safe_relative(name)
    parts = name.split('/')
    parent = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o700, dir_fd=parent)
            except FileExistsError:
                pass
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent)
            os.close(parent)
            parent = child
        fd = os.open(parts[-1], os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, mode, dir_fd=parent)
        try:
            view = memoryview(raw)
            while view:
                written = os.write(fd, view)
                if written <= 0:
                    raise BootstrapError('short_write')
                view = view[written:]
            os.fsync(fd)
        finally:
            os.close(fd)
    finally:
        os.close(parent)


def create_directory_at(parent_fd: int, name: str) -> int:
    if safe_relative(name) != Path(name).name:
        raise BootstrapError('new_directory_name_not_literal')
    os.mkdir(name, 0o700, dir_fd=parent_fd)
    created = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
    fd = os.open(name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=parent_fd)
    try:
        current = os.fstat(fd)
        with os.scandir(fd) as entries:
            populated = next(entries, None) is not None
        if (created.st_dev, created.st_ino) != (current.st_dev, current.st_ino) or populated:
            raise BootstrapError('new_directory_replaced_or_populated')
        return fd
    except BaseException:
        os.close(fd)
        raise


def publish_status(task: Path, status: dict):
    """Only the final create-only link commits a successful preparation.

No fallible durability operation follows publication. This is a completion
marker for this run, not an assertion about physical disk power-loss recovery.
"""
    raw = json_bytes(status)
    with open_directory(task) as fd:
        write_new_at(fd, 'provision-status.pending.json', raw)
        if read_regular(task / 'provision-status.pending.json', MAX_FILE_BYTES) != raw:
            raise BootstrapError('status_readback_mismatch')
        os.link('provision-status.pending.json', 'provision-status.json',
                src_dir_fd=fd, dst_dir_fd=fd, follow_symlinks=False)


def verify_bundle(bundle: Path) -> tuple[dict, bytes, dict[str, bytes]]:
    bundle = Path(bundle)
    names = {'source.tar.gz', 'source-inventory.json', 'bundle-manifest.json',
             'bundle-manifest.sha256', 'colab_gateway_bootstrap.py'}
    with open_directory(bundle) as fd:
        with os.scandir(fd) as entries:
            observed = set()
            for entry in entries:
                observed.add(entry.name)
                if len(observed) > len(names):
                    raise BootstrapError('unexpected_bundle_file')
        if observed != names:
            raise BootstrapError('bundle_inventory_mismatch')
    raw = read_regular(bundle / 'bundle-manifest.json', 16384)
    if read_regular(bundle / 'bundle-manifest.sha256', 128) != (sha256(raw) + '\n').encode():
        raise BootstrapError('bundle_manifest_digest_mismatch')
    manifest = json_object(raw)
    if (set(manifest) != {'schema', 'source_commit', 'source_inventory', 'archive', 'bootstrap',
                         'requirements_path', 'model_id', 'model_revision', 'model_files_path'}
            or manifest['schema'] != 'sanmou-colab-gateway-bundle-v1'
            or (manifest['requirements_path'], manifest['model_id'], manifest['model_revision'], manifest['model_files_path'])
            != (LOCK_PATH, MODEL_ID, MODEL_REVISION, MODEL_FILES_PATH)):
        raise BootstrapError('bundle_manifest_schema')
    originals = {}
    for key, filename, limit in (('source_inventory', 'source-inventory.json', MAX_FILE_BYTES),
                                 ('archive', 'source.tar.gz', MAX_ARCHIVE_BYTES),
                                 ('bootstrap', 'colab_gateway_bootstrap.py', MAX_FILE_BYTES)):
        entry = manifest[key]
        if not isinstance(entry, dict) or set(entry) != {'path', 'bytes', 'sha256'} or entry['path'] != filename:
            raise BootstrapError('bundle_file_descriptor')
        payload = read_regular(bundle / filename, limit)
        if type(entry['bytes']) is not int or len(payload) != entry['bytes'] or sha256(payload) != entry['sha256']:
            raise BootstrapError('bundle_file_digest_mismatch')
        originals[key] = payload
    inventory = validate_inventory(json_object(originals['source_inventory']))
    if inventory['source_commit'] != manifest['source_commit']:
        raise BootstrapError('bundle_source_commit_mismatch')
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(originals['archive'])) as stream:
            tar_raw = stream.read(MAX_TAR_BYTES + 1)
        if len(tar_raw) > MAX_TAR_BYTES:
            raise BootstrapError('expanded_archive_limit')
        payloads = {}
        with tarfile.open(fileobj=io.BytesIO(tar_raw), mode='r:') as archive:
            for member in archive:
                if len(payloads) >= MAX_FILES or not member.isfile() or member.mode not in (0o644, 0o755):
                    raise BootstrapError('archive_entry_type_or_mode')
                name = safe_relative(member.name)
                if name in payloads or name not in inventory['files'] or member.linkname:
                    raise BootstrapError('archive_path_duplicate_or_unlisted')
                expected = inventory['files'][name]
                if member.size != expected['bytes']:
                    raise BootstrapError('archive_entry_length')
                data = archive.extractfile(member).read(MAX_FILE_BYTES + 1)
                if len(data) != expected['bytes'] or sha256(data) != expected['sha256']:
                    raise BootstrapError('archive_entry_digest')
                payloads[name] = data
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise BootstrapError('invalid_source_archive') from exc
    if set(payloads) != set(inventory['files']):
        raise BootstrapError('archive_missing_files')
    if payloads[BOOTSTRAP_PATH] != originals['bootstrap']:
        raise BootstrapError('bootstrap_not_committed_source')
    return manifest, originals['source_inventory'], payloads


def extract_source(task: Path, inventory_raw: bytes, payloads: dict[str, bytes]) -> Path:
    inventory = validate_inventory(json_object(inventory_raw))
    if set(payloads) != set(inventory['files']):
        raise BootstrapError('extract_inventory_mismatch')
    for name, raw in payloads.items():
        expected = inventory['files'][name]
        if len(raw) != expected['bytes'] or sha256(raw) != expected['sha256']:
            raise BootstrapError('extract_payload_mismatch')
    with open_directory(task) as parent:
        fd = create_directory_at(parent, 'source')
        try:
            for name, raw in sorted(payloads.items()):
                write_new_at(fd, name, raw)
            write_new_at(fd, 'source-inventory.json', inventory_raw)
        finally:
            os.close(fd)
    return task / 'source'


def redact_output(value: str) -> str:
    value = re.sub(r'(?i)(https?://)[^/\s:@]+:[^@\s]+@', r'\1[REDACTED]@', value)
    value = re.sub(r'(https?://[^\s?]+)\?[^\s]+', r'\1?[REDACTED_QUERY]', value)
    value = re.sub(r'(?i)(Bearer\s+)[A-Za-z0-9._~+/-]+', r'\1[REDACTED]', value)
    value = re.sub(r'\b(?:hf_|sk-)[A-Za-z0-9_-]{16,}', '[REDACTED]', value)
    value = re.sub(r'(?i)((?:api_key|access_token|refresh_token|client_secret)\s*[=:]\s*)[^\s,;]+',
                   r'\1[REDACTED]', value)
    return value


def isolated_env(task: Path, source: Path) -> dict[str, str]:
    # Preserve HOME unchanged; do not pass credential, proxy or package-index
    # environment values into installers/downloader. Private caches are explicit.
    env = {name: value for name, value in os.environ.items() if name in {
        'HOME', 'PATH', 'LANG', 'LC_ALL', 'TERM', 'LD_LIBRARY_PATH', 'CUDA_HOME', 'CUDA_PATH',
        'CUDA_VISIBLE_DEVICES', 'NVIDIA_VISIBLE_DEVICES', 'SSL_CERT_FILE',
    }}
    env.update(PATH=str(task / 'venv/bin') + os.pathsep + env.get('PATH', '/usr/local/bin:/usr/bin:/bin'),
               TMPDIR=str(task / 'tmp'), PIP_CONFIG_FILE=os.devnull, PIP_DISABLE_PIP_VERSION_CHECK='1',
               HF_HOME=str(task / 'hf-home'), HF_HUB_CACHE=str(task / 'hf-cache'),
               HF_HUB_DISABLE_IMPLICIT_TOKEN='1', PYTHONDONTWRITEBYTECODE='1',
               XDG_CACHE_HOME=str(task / 'xdg-cache'), TORCH_HOME=str(task / 'torch-cache'),
               TORCH_EXTENSIONS_DIR=str(task / 'torch-extensions'), CUDA_CACHE_PATH=str(task / 'cuda-cache'),
               TRITON_CACHE_DIR=str(task / 'triton-cache'),
               PYTHONPATH=os.pathsep.join(str(source / 'packages' / p / 'src') for p in ('sanmou-common', 'pioneer-agent')))
    return env


def run_step(name: str, command: list[str], *, timeout: int, task: Path, env: dict) -> dict:
    started = time.monotonic()
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               env=env, start_new_session=True)
    timed_out = False
    try:
        output, _ = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        os.killpg(process.pid, signal.SIGTERM)
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            output, _ = process.communicate(timeout=10)
    clean = redact_output(output.decode('utf-8', errors='replace')).encode()
    with open_directory(task) as fd:
        write_new_at(fd, f'{name}.log', clean)
    result = {'step': name, 'status': 'timeout' if timed_out else 'passed' if process.returncode == 0 else 'failed',
              'returncode': process.returncode, 'timeout_seconds': timeout,
              'seconds': round(time.monotonic() - started, 3), 'log': f'{name}.log', 'log_sha256': sha256(clean)}
    with open_directory(task) as fd:
        write_new_at(fd, f'{name}.json', json_bytes(result))
    if result['status'] != 'passed':
        raise BootstrapError('stage_failed:' + name)
    return result


def validate_gpu_rows(gpu_csv: str, compute_pids: str) -> dict:
    rows = [line.strip() for line in gpu_csv.splitlines() if line.strip()]
    if len(rows) != 1 or compute_pids.strip():
        raise BootstrapError('one_idle_gpu_required')
    columns = [item.strip() for item in rows[0].split(',')]
    try:
        index, name, memory_total, memory_used, utilization = columns
        numbers = tuple(float(value) for value in (memory_total, memory_used, utilization))
        if (not all(math.isfinite(value) and value >= 0 for value in numbers) or index != '0' or 'A100' not in name
                or numbers[0] < 80000 or numbers[1] > 512 or numbers[2] != 0):
            raise BootstrapError('idle_a100_80gb_required')
    except (ValueError, TypeError) as exc:
        raise BootstrapError('invalid_gpu_inventory') from exc
    return {'name': name, 'memory_total_mib': float(memory_total), 'memory_used_mib': float(memory_used),
            'utilization_percent': float(utilization), 'compute_processes': 0}


def preflight(work_root: Path, source_bytes: int) -> dict:
    if sys.platform != 'linux' or work_root != Path('/content'):
        raise BootstrapError('provision_requires_existing_linux_colab_content')
    with open_directory(work_root):
        pass
    executable = shutil.which('python3.12')
    if not executable:
        raise BootstrapError('python312_missing')
    def output(command):
        try:
            run = subprocess.run(command, capture_output=True, timeout=30, check=True, text=True)
        except (OSError, subprocess.SubprocessError) as exc:
            raise BootstrapError('preflight_command_failed') from exc
        return run.stdout.strip()
    if not output([executable, '--version']).startswith('Python 3.12.'):
        raise BootstrapError('python312_required')
    gpu = validate_gpu_rows(output(['nvidia-smi', '--query-gpu=index,name,memory.total,memory.used,utilization.gpu',
                                    '--format=csv,noheader,nounits']),
                            output(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader,nounits']))
    required = 80 * 1024**3 + source_bytes
    available = shutil.disk_usage(work_root).free
    if available < required:
        raise BootstrapError('insufficient_disk_space')
    return {'python312': executable, 'gpu': gpu, 'disk_free_bytes': available, 'disk_required_bytes': required}


def provision_commands(task: Path, source: Path, python312: str, base_python: str) -> list[tuple[str, list[str], int]]:
    python = str(task / 'venv/bin/python')
    common_pip = ['--disable-pip-version-check', '--no-input']
    return [
        ('create-venv', [python312, '-m', 'venv', '--without-pip', str(task / 'venv')], 120),
        ('bootstrap-pip', [base_python, '-m', 'pip', '--python', python, *common_pip, 'install',
                           '--cache-dir', str(task / 'pip-cache'), '--index-url', 'https://pypi.org/simple', 'pip==26.2.2'], 300),
        ('install-lock', [python, '-m', 'pip', *common_pip, 'install', '--no-deps', '--only-binary=outlines-core',
                          '--cache-dir', str(task / 'pip-cache'), '--index-url', 'https://pypi.org/simple',
                          '--progress-bar', 'off', '-r', str(source / LOCK_PATH)], 3600),
        ('pip-check', [python, '-m', 'pip', 'check'], 120),
        ('runtime-versions', [python, '-c',
            "import json,torch,importlib.metadata as m; "
            "assert torch.__version__=='2.14.1+cu130' and torch.version.cuda=='13.0'; "
            "assert m.version('sglang')=='0.5.22' and m.version('transformers')=='5.19.0' and m.version('flashinfer-python')=='0.7.1'; "
            "print(json.dumps({'torch':torch.__version__,'cuda':torch.version.cuda,'sglang':m.version('sglang'),"
            "'transformers':m.version('transformers'),'flashinfer-python':m.version('flashinfer-python')}))"], 120),
        ('gateway-import-readiness', [python, '-c',
            "import json,runpy; import pioneer_agent.app.policy_gateway; "
            f"runpy.run_path({str(source / 'scripts/model-serving/native_runtime_manifest.py')!r},run_name='sanmou_native_readiness'); "
            f"runpy.run_path({str(source / 'scripts/model-serving/live_gateway_roundtrip.py')!r},run_name='sanmou_gateway_readiness'); "
            "print(json.dumps({'gateway_import':True,'collector_import':True,'runner_import':True,'services_started':False}))"], 120),
    ]


def download_command(task: Path, source: Path) -> list[str]:
    # No implicit login, no use of user cache, and only the 13 known files.
    code = (
        "import json; from pathlib import Path; from huggingface_hub import snapshot_download; "
        f"files=json.loads(Path({str(source / MODEL_FILES_PATH)!r}).read_text()); "
        f"snapshot_download(repo_id={MODEL_ID!r},revision={MODEL_REVISION!r},token=False,"
        f"local_dir={str(task / 'model-download')!r},cache_dir={str(task / 'hf-cache')!r},"
        "allow_patterns=list(files),max_workers=4); print('download_complete')"
    )
    return [str(task / 'venv/bin/python'), '-c', code]


def materialize_model(task: Path, inventory: dict) -> dict:
    if len(inventory) != 13 or sum(item['bytes'] for item in inventory.values()) != 19329302904:
        raise BootstrapError('model_inventory_not_expected')
    with open_directory(task) as fd:
        model_fd = create_directory_at(fd, 'model')
        os.close(model_fd)
    verified = {}
    for name, expected in sorted(inventory.items()):
        if safe_relative(name) != Path(name).name:
            raise BootstrapError('flat_model_files_required')
        origin = task / 'model-download' / name
        with open_directory(origin.parent) as parent, open_directory(task / 'model') as destination:
            source_fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
            output_fd = None
            try:
                before = os.fstat(source_fd)
                if not stat.S_ISREG(before.st_mode) or before.st_nlink != 1 or before.st_size != expected['bytes']:
                    raise BootstrapError('model_not_expected_regular_file')
                output_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=destination)
                digest, count = hashlib.sha256(), 0
                while chunk := os.read(source_fd, 4 * 1024 * 1024):
                    count += len(chunk)
                    if count > expected['bytes']:
                        raise BootstrapError('model_size_changed')
                    digest.update(chunk)
                    pending = memoryview(chunk)
                    while pending:
                        written = os.write(output_fd, pending)
                        if written <= 0:
                            raise BootstrapError('model_short_write')
                        pending = pending[written:]
                os.fsync(output_fd)
                after = os.fstat(source_fd)
                if (count != expected['bytes'] or digest.hexdigest() != expected['sha256']
                        or (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns)):
                    raise BootstrapError('model_digest_or_stability_mismatch')
                verified[name] = {'bytes': count, 'sha256': digest.hexdigest()}
            finally:
                os.close(source_fd)
                if output_fd is not None:
                    os.close(output_fd)
    return verified


def next_command_templates(task: Path, source: Path) -> dict[str, list[str]]:
    """Commands for the supervisor; placeholders are never executed here."""
    python = str(task / 'venv/bin/python')
    runner = str(source / 'scripts/model-serving/live_gateway_roundtrip.py')
    collector = str(source / 'scripts/model-serving/native_runtime_manifest.py')
    native = task / 'native-binding'
    return {
        'describe_scenario': [python, runner, '--describe-scenario'],
        'collect_native_binding_after_supervisor_starts_sglang': [
            python, collector, '--model-dir', str(task / 'model'), '--runtime-config', '<public-runtime-config.json>',
            '--expected-model-files', str(source / MODEL_FILES_PATH), '--sampling', '<sampling.json>',
            '--prompt-sha256', '<scenario-prompt-sha256>', '--source-root', str(source),
            '--source-inventory', str(source / 'source-inventory.json'), '--output', str(native),
        ],
        'run_gateway_after_native_binding': [python, runner, '--manifest', str(native / 'policy-manifest.json'),
            '--binding', str(native / 'runtime-receipt.json'), '--upstream', 'http://127.0.0.1:<port>',
            '--output', str(task / 'gateway-evidence')],
    }


def prepare(bundle: Path, *, work_root: Path, provision: bool = False) -> dict:
    manifest, inventory_raw, payloads = verify_bundle(bundle)
    inventory = json_object(inventory_raw)
    with open_directory(work_root):
        pass
    status = {'schema': 'sanmou-colab-provision-v1', 'status': 'preparing', 'source_commit': manifest['source_commit'],
              'source_inventory_sha256': sha256(inventory_raw), 'model_revision': MODEL_REVISION,
              'sglang_started': False, 'gateway_started': False, 'model_generation_requests': 0,
              'runtime_created_or_stopped': False, 'steps': []}
    # No existing directory is reused. Even failure artifacts remain isolated.
    task = Path(tempfile.mkdtemp(prefix='sanmou-gateway-', dir=work_root))
    status['work_dir'] = str(task)
    try:
        if provision:
            status['preflight'] = preflight(work_root, sum(info['bytes'] for info in inventory['files'].values()))
        source = extract_source(task, inventory_raw, payloads)
        for name in ('tmp', 'pip-cache', 'hf-cache', 'hf-home'):
            (task / name).mkdir(mode=0o700)
        env = isolated_env(task, source)
        if provision:
            for name, command, timeout in provision_commands(task, source, status['preflight']['python312'], sys.executable):
                status['steps'].append(run_step(name, command, timeout=timeout, task=task, env=env))
            status['steps'].append(run_step('download-model', download_command(task, source), timeout=3600, task=task, env=env))
            status['verified_model_files'] = materialize_model(task, json_object(payloads[MODEL_FILES_PATH]))
        status.update(status='provisioned' if provision else 'prepared', source_root=str(source),
                      source_inventory=str(source / 'source-inventory.json'), python=str(task / 'venv/bin/python'),
                      model_dir=str(task / 'model'), expected_model_files=str(source / MODEL_FILES_PATH),
                      PATH=env['PATH'], PYTHONPATH=env['PYTHONPATH'],
                      venv_ready=provision, model_files_verified=provision,
                      next_command_templates=next_command_templates(task, source),
                      next_step='Supervisor starts the private/public SGLang configuration, then invokes the committed native collector and live gateway runner.')
        status['available_next_entrypoints'] = [name for name in (
            'scripts/model-serving/native_runtime_manifest.py', 'scripts/model-serving/live_gateway_roundtrip.py',
        ) if name in payloads]
        publish_status(task, status)
    except (BootstrapError, OSError, subprocess.SubprocessError) as exc:
        status.update(status='failed', error_code=str(exc) if isinstance(exc, BootstrapError) else type(exc).__name__)
        with open_directory(task) as fd:
            write_new_at(fd, 'provision-failure.json', json_bytes(status))
        raise ProvisionFailure(task) from None
    return status


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle-dir', type=Path, required=True)
    parser.add_argument('--work-root', type=Path, default=Path('/content'))
    parser.add_argument('--mode', choices=('prepare', 'provision'), default='prepare')
    args = parser.parse_args()
    try:
        result = prepare(args.bundle_dir, work_root=args.work_root, provision=args.mode == 'provision')
    except ProvisionFailure as exc:
        print(json.dumps({'status': 'failed', 'error_code': 'provision_failed', 'work_dir': str(exc.task),
                          'failure_record': str(exc.task / 'provision-failure.json'), 'runtime_created_or_stopped': False}))
        return 2
    except (BootstrapError, OSError, ValueError):
        print(json.dumps({'status': 'failed', 'error_code': 'bootstrap_failed', 'runtime_created_or_stopped': False}))
        return 2
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
