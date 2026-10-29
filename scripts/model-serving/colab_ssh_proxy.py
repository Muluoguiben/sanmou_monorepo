#!/usr/bin/env python3
"""Bind an existing A100 assignment to an SSH ProxyCommand.

Requires google-colab-cli 0.7.5 and its existing OAuth credentials. This uses
private CLI interfaces; it never provisions or stops a Colab runtime.
"""
import argparse
import builtins
import contextlib
import io
import json
import logging
import os
from pathlib import Path
import stat
import sys
import tempfile


def _private_parent(path):
    path = Path(path)
    if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
        raise ValueError('target_requires_absolute_nonsymlink_parent')
    info = path.parent.stat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
        raise ValueError('target_requires_private_directory')
    return path


def _is_a100(assignment):
    return assignment.accelerator.value == 'A100' and assignment.machine_shape.name == 'HIGH_RAM'


def choose_unique(assignments):
    matches = [a for a in assignments if _is_a100(a)]
    if len(matches) != 1:
        raise ValueError('expected_one_a100_high_ram')
    return matches[0]


def choose_pinned(assignments, endpoint):
    matches = [a for a in assignments if _is_a100(a) and a.endpoint == endpoint]
    if len(matches) != 1:
        raise ValueError('pinned_assignment_missing_or_changed')
    return matches[0]


def write_pin(path, endpoint):
    path = _private_parent(path)
    fd, tmp = tempfile.mkstemp(prefix='.colab-pin-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump({'endpoint': endpoint}, f)
            f.flush()
            os.fsync(f.fileno())
        os.link(tmp, path, follow_symlinks=False)  # Atomic, never replaces an existing path.
    finally:
        os.unlink(tmp)  # This exact file was created by mkstemp above.


def read_pin(path):
    path = _private_parent(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, encoding='utf-8') as f:
        info = os.fstat(f.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError('target_requires_private_regular_file')
        data = json.load(f)
    if set(data) != {'endpoint'} or not isinstance(data['endpoint'], str) or not data['endpoint']:
        raise ValueError('invalid_target')
    return data['endpoint']


def _no_input(*args, **kwargs):
    raise RuntimeError('interactive_auth_unavailable')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('operation', choices=('pin', 'proxy'))
    parser.add_argument('--target', required=True, help='Absolute path in a private task directory')
    parser.add_argument('--identity', help='SSH private key; required for proxy')
    args = parser.parse_args(argv)
    if args.operation == 'proxy' and not args.identity:
        parser.error('--identity is required for proxy')
    captured = io.StringIO()
    old_input = builtins.input
    old_disable = logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        builtins.input = _no_input
        # Keep OAuth prompts, proxy URLs and exception details out of stdout and stderr.
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            from colab_cli.common import state
            assignments = state.client.list_assignments()
            if args.operation == 'pin':
                write_pin(args.target, choose_unique(assignments).endpoint)
                assignment = None
            else:
                assignment = choose_pinned(assignments, read_pin(args.target))
        if assignment is None:
            print('Pinned existing A100 assignment.')
            return 0
        from colab_cli.state import SessionState
        from colab_cli.commands.ssh import _run_proxy_bridge
        info = assignment.runtime_proxy_info
        session = SessionState(name='existing-a100', token=info.token, url=info.url,
            endpoint=assignment.endpoint, token_expires_at=info.expires_at(),
            variant=assignment.variant.name, accelerator=assignment.accelerator.value,
            machine_shape=assignment.machine_shape.name)
        # stdout is reserved for the SSH protocol, so only suppress stderr here.
        with contextlib.redirect_stderr(captured):
            return _run_proxy_bridge(session, identity=args.identity, rm=False)
    except BaseException:
        message = captured.getvalue()
        for indicator in ('HTTP 429', 'HTTP 404', 'HTTP 401', 'HTTP 403', 'HTTP 502'):
            if indicator in message:
                print('Colab SSH proxy failed:', indicator, file=sys.stderr)
                return 1
        print('Colab SSH proxy failed; check authentication, target and identity.', file=sys.stderr)
        return 1
    finally:
        builtins.input = old_input
        logging.disable(old_disable)


if __name__ == '__main__':
    sys.exit(main())
