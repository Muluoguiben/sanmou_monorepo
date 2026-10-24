#!/usr/bin/env python3
"""Export only allowlisted committed regular blobs; never archive Git history."""
from __future__ import annotations

import argparse
import gzip
import io
import os
from pathlib import Path
import re
import subprocess
import tarfile

from colab_gateway_bootstrap import (
    BOOTSTRAP_PATH, EXTRA_FILES, LOCK_PATH, MAX_FILE_BYTES, MAX_FILES, MAX_SOURCE_BYTES,
    MODEL_FILES_PATH, MODEL_ID, MODEL_REVISION, SOURCE_ROOTS, BootstrapError,
    allowed_source, create_directory_at, forbidden_source_name, json_bytes, open_directory, sha256,
    validate_inventory, write_new_at,
)

_SECRET = re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|\b(?:sk-|hf_)[A-Za-z0-9_-]{20,}')


def _git(repository: Path, *args: str) -> bytes:
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    env['GIT_TERMINAL_PROMPT'] = '0'
    env['GIT_NO_REPLACE_OBJECTS'] = '1'
    try:
        result = subprocess.run(['git', '-c', 'core.fsmonitor=false', *args], cwd=repository, env=env,
                                capture_output=True, timeout=30, check=True)
    except (OSError, subprocess.SubprocessError) as exc:
        raise BootstrapError('committed_git_source_unavailable') from exc
    return result.stdout


def collect_source(repository: Path, revision: str) -> tuple[dict, dict[str, bytes], dict[str, int]]:
    if not re.fullmatch(r'[0-9a-f]{40}', revision) or _git(repository, 'cat-file', '-t', revision).strip() != b'commit':
        raise BootstrapError('full_commit_sha_required')
    entries = _git(repository, 'ls-tree', '-rz', '--full-tree', revision, '--', *SOURCE_ROOTS, *EXTRA_FILES)
    payloads, modes, total = {}, {}, 0
    for entry in entries.split(b'\0'):
        if not entry:
            continue
        metadata, raw_path = entry.split(b'\t', 1)
        mode, kind, blob = metadata.decode('ascii').split(' ')
        name = raw_path.decode('utf-8')
        # Dotfiles/credential names are excluded before reading their contents.
        if forbidden_source_name(name):
            continue
        if not allowed_source(name) or kind != 'blob' or mode not in ('100644', '100755'):
            raise BootstrapError('source_not_allowlisted_regular_blob')
        size = int(_git(repository, 'cat-file', '-s', blob))
        total += size
        if size > MAX_FILE_BYTES or total > MAX_SOURCE_BYTES or len(payloads) >= MAX_FILES:
            raise BootstrapError('source_size_limit')
        raw = _git(repository, 'cat-file', 'blob', blob)
        if len(raw) != size or _SECRET.search(raw):
            raise BootstrapError('source_size_or_credential_material')
        payloads[name] = raw
        modes[name] = 0o755 if mode == '100755' else 0o644
    inventory = validate_inventory({'schema': 'sanmou-colab-source-inventory-v1', 'source_commit': revision,
                                    'files': {name: {'bytes': len(raw), 'sha256': sha256(raw)}
                                              for name, raw in sorted(payloads.items())}})
    return inventory, payloads, modes


def build_bundle(repository: Path, revision: str, destination: Path) -> dict:
    inventory, payloads, modes = collect_source(repository, revision)
    inventory_raw = json_bytes(inventory)
    stream = io.BytesIO()
    with gzip.GzipFile(fileobj=stream, mode='wb', filename='', mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w', format=tarfile.USTAR_FORMAT) as archive:
            for name, raw in sorted(payloads.items()):
                entry = tarfile.TarInfo(name)
                entry.size, entry.mode, entry.mtime = len(raw), modes[name], 0
                entry.uid = entry.gid = 0
                entry.uname = entry.gname = ''
                archive.addfile(entry, io.BytesIO(raw))
    archive_raw = stream.getvalue()
    describe = lambda name, raw: {'path': name, 'bytes': len(raw), 'sha256': sha256(raw)}
    manifest = {
        'schema': 'sanmou-colab-gateway-bundle-v1', 'source_commit': revision,
        'source_inventory': describe('source-inventory.json', inventory_raw),
        'archive': describe('source.tar.gz', archive_raw),
        'bootstrap': describe('colab_gateway_bootstrap.py', payloads[BOOTSTRAP_PATH]),
        'requirements_path': LOCK_PATH, 'model_id': MODEL_ID, 'model_revision': MODEL_REVISION,
        'model_files_path': MODEL_FILES_PATH,
    }
    manifest_raw = json_bytes(manifest)
    with open_directory(destination.parent) as parent:
        fd = create_directory_at(parent, destination.name)
        try:
            for name, raw in (
                ('source.tar.gz', archive_raw), ('source-inventory.json', inventory_raw),
                ('colab_gateway_bootstrap.py', payloads[BOOTSTRAP_PATH]),
                ('bundle-manifest.json', manifest_raw), ('bundle-manifest.sha256', (sha256(manifest_raw) + '\n').encode()),
            ):
                write_new_at(fd, name, raw)
        finally:
            os.close(fd)
    return {'status': 'prepared', 'source_commit': revision, 'files': len(payloads),
            'source_bytes': sum(len(raw) for raw in payloads.values()),
            'source_inventory_sha256': sha256(inventory_raw), 'archive_sha256': sha256(archive_raw),
            'bundle_manifest_sha256': sha256(manifest_raw), 'output': str(destination),
            'gpu_or_network_calls': 0, 'git_history_included': False}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', type=Path, required=True)
    parser.add_argument('--revision', required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = build_bundle(args.repository, args.revision, args.output_dir)
    except (BootstrapError, OSError, ValueError):
        print(json_bytes({'status': 'failed', 'error_code': 'source_bundle_failed'}).decode(), end='')
        return 2
    print(json_bytes(result).decode(), end='')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
