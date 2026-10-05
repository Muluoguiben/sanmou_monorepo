"""Stdlib-only local locks. Stable sidecars must never be unlinked/replaced.

Cooperative Linux local filesystems/Windows fixed disks only; not a device lease,
network lock, alias resolver, or malicious-user security boundary.
"""
from __future__ import annotations

import os
from pathlib import Path
import stat
import sys


class UnsupportedCheckpointBackend(RuntimeError):
    pass


class LocalLock:
    def __init__(self, path: Path):
        self.path = path
        self.sidecar = path.with_name(path.name + ".lock")
        self.fd = None

    @staticmethod
    def validate_file(path):
        try:
            info = path.lstat()
        except FileNotFoundError:
            return
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or getattr(info, "st_file_attributes", 0) & 0x400):
            raise UnsupportedCheckpointBackend("checkpoint requires a regular unaliased file")

    def _validate_backend(self):
        for part in (self.path.parent, *self.path.parent.parents):
            if part.is_symlink() or (part.exists() and getattr(part.stat(), "st_file_attributes", 0) & 0x400):
                raise UnsupportedCheckpointBackend("checkpoint parent aliases are unsupported")
        if os.name == "nt":
            import ctypes
            if self.path.drive.startswith("\\\\") or ctypes.windll.kernel32.GetDriveTypeW(self.path.anchor) != 3:
                raise UnsupportedCheckpointBackend("checkpoint requires a local fixed disk")
        elif sys.platform == "linux":
            mounts = []
            for line in Path("/proc/self/mountinfo").read_text().splitlines():
                left, right = line.split(" - ", 1)
                mount = left.split()[4]
                for code, char in (("\\040", " "), ("\\011", "\t"), ("\\134", "\\")):
                    mount = mount.replace(code, char)
                base = Path(mount)
                if self.path.is_relative_to(base):
                    mounts.append((len(base.parts), right.split()[0]))
            if not mounts or max(mounts)[1] not in {"ext4", "ext3", "ext2", "xfs", "btrfs", "tmpfs", "overlay"}:
                raise UnsupportedCheckpointBackend("unsupported local checkpoint filesystem")
        else:
            raise UnsupportedCheckpointBackend("unsupported checkpoint locking platform")

    def acquire(self):
        self._validate_backend()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.validate_file(self.path)
        self.validate_file(self.sidecar)
        fd = os.open(self.sidecar, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            os.close(fd)
            if exc.errno in (11, 13, 35, 36):
                raise BlockingIOError("checkpoint owned") from None
            raise UnsupportedCheckpointBackend("checkpoint locking failed") from exc
        except BaseException:
            os.close(fd)
            raise
        self.fd = fd

    def close(self):
        if self.fd is not None:
            fd, self.fd = self.fd, None
            try:
                if os.name == "nt":
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_UN)
            finally:
                os.close(fd)
