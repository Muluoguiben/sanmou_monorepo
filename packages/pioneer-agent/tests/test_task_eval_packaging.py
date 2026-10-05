"""Only conventional non-executable packaging data may be outside Git binding."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

from pioneer_agent.agent_harness._task_eval_inputs import InputError
from pioneer_agent.agent_harness._task_eval_source import (
    PACKAGING_METADATA_FILES, PACKAGING_METADATA_ROOTS, SourceBinding,
)


class PackagingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        source = self.root / "packages/pioneer-agent/src/pioneer_agent/__init__.py"
        source.parent.mkdir(parents=True)
        source.write_bytes(b'"""fixture source"""\n')
        self.git("init", "-q")
        self.git("add", ".")
        self.git("-c", "user.name=Offline Test", "-c", "user.email=offline@example.invalid", "commit", "-qm", "fixture")

    def git(self, *args):
        return subprocess.run(["git", "-C", str(self.root), *args], check=True, capture_output=True).stdout

    def binding(self):
        binding = SourceBinding.__new__(SourceBinding)
        binding.root, binding.manifest = self.root, {}
        binding.commit = self.git("rev-parse", "HEAD").decode().strip()
        return binding

    def metadata(self):
        for relative in PACKAGING_METADATA_ROOTS:
            directory = self.root / relative
            directory.mkdir(parents=True, exist_ok=True)
            for name in PACKAGING_METADATA_FILES:
                path = directory / name
                path.write_bytes(b"ordinary packaging data\n")
                path.chmod(0o644)

    def test_two_exact_roots_five_standard_files_are_recorded_not_source(self):
        self.metadata()
        binding = self.binding()
        binding.verify_bytes()
        self.assertEqual(len(binding.packaging_metadata), 10)
        self.assertTrue(set(binding.packaging_metadata).isdisjoint(binding.manifest))
        binding.verify_bytes()

    def test_extra_files_and_nested_cache_rejected_in_both_roots(self):
        self.metadata()
        for relative in PACKAGING_METADATA_ROOTS:
            for name in ("extra.py", "native.so", "inject.pth", "entry_points.txt", "unknown.txt", "__pycache__/hidden.py"):
                with self.subTest(root=relative, name=name):
                    path = self.root / relative / name
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_bytes(b"unexpected\n")
                    try:
                        with self.assertRaises(InputError):
                            self.binding().verify_bytes()
                    finally:
                        path.unlink()
                        if path.parent.name == "__pycache__":
                            path.parent.rmdir()

    def test_unknown_metadata_directory_is_not_ignored(self):
        path = self.root / "packages/pioneer-agent/src/other.egg-info/PKG-INFO"
        path.parent.mkdir()
        path.write_bytes(b"not the declared distribution\n")
        with self.assertRaisesRegex(InputError, "untracked_source"):
            self.binding().verify_bytes()

    def test_metadata_byte_change_after_snapshot_rejected(self):
        self.metadata()
        binding = self.binding()
        binding.verify_bytes()
        path = self.root / sorted(PACKAGING_METADATA_ROOTS)[0] / "SOURCES.txt"
        path.write_bytes(b"changed\n")
        with self.assertRaisesRegex(InputError, "packaging_metadata_changed"):
            binding.verify_bytes()

    def test_binary_metadata_rejected(self):
        self.metadata()
        for relative in PACKAGING_METADATA_ROOTS:
            path = self.root / relative / "PKG-INFO"
            for raw in (b"\x00", b"\xff"):
                path.write_bytes(raw)
                with self.assertRaisesRegex(InputError, "nontext_packaging_metadata"):
                    self.binding().verify_bytes()
            path.write_bytes(b"ordinary packaging data\n")

    @unittest.skipIf(os.name == "nt", "POSIX executable metadata bit")
    def test_executable_metadata_rejected(self):
        self.metadata()
        for relative in PACKAGING_METADATA_ROOTS:
            path = self.root / relative / "PKG-INFO"
            path.chmod(0o755)
            with self.assertRaisesRegex(InputError, "unexpected_packaging_metadata"):
                self.binding().verify_bytes()
            path.chmod(0o644)

    def test_hardlinked_metadata_rejected(self):
        self.metadata()
        target = self.root / "outside.txt"
        target.write_bytes(b"linked data\n")
        for relative in PACKAGING_METADATA_ROOTS:
            path = self.root / relative / "PKG-INFO"
            path.unlink()
            path.hardlink_to(target)
            with self.assertRaisesRegex(InputError, "unexpected_packaging_metadata"):
                self.binding().verify_bytes()
            path.unlink()
            path.write_bytes(b"ordinary packaging data\n")

    def test_symlink_metadata_rejected(self):
        self.metadata()
        target = self.root / "outside.txt"
        target.write_bytes(b"linked data\n")
        for relative in PACKAGING_METADATA_ROOTS:
            path = self.root / relative / "PKG-INFO"
            path.unlink()
            try:
                path.symlink_to(target)
            except OSError:
                self.skipTest("host does not grant symlink creation")
            with self.assertRaisesRegex(InputError, "linked_source"):
                self.binding().verify_bytes()
            path.unlink()
            path.write_bytes(b"ordinary packaging data\n")


if __name__ == "__main__":
    unittest.main()
