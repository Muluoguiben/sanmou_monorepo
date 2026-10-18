"""P2 fixed-repository boundary probes; no foreign repository or output writes."""
import importlib.util
import os
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location("qe0_frozen_public_probes",
    Path(__file__).with_name("qa-e0-prep-independent-probes.py"))
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class GitContextBoundaryProbes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.prep = public.load_product()

    def test_inherited_git_context_is_not_forwarded_to_metadata_subprocesses(self):
        inherited = {
            "GIT_DIR": "/synthetic-foreign/.git", "GIT_WORK_TREE": "/synthetic-foreign",
            "GIT_COMMON_DIR": "/synthetic-foreign/common", "GIT_INDEX_FILE": "/synthetic-foreign/index",
            "GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "core.worktree",
            "GIT_CONFIG_VALUE_0": "/synthetic-foreign", "GIT_CONFIG_PARAMETERS": "'core.worktree=/synthetic-foreign'",
            "GIT_CONFIG_GLOBAL": "/synthetic-foreign/global", "GIT_CONFIG_SYSTEM": "/synthetic-foreign/system",
        }
        calls = []
        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            output = str(self.prep.REPOSITORY) + "\n" if "--show-toplevel" in argv else "synthetic-ok\n"
            return subprocess.CompletedProcess(argv, 0, output, "")
        with patch.dict(os.environ, inherited), patch.object(self.prep.subprocess, "run", side_effect=run):
            self.prep._git("rev-parse", "--show-toplevel")
        self.assertTrue(calls)
        for _, kwargs in calls:
            self.assertIsInstance(kwargs.get("env"), dict, "implicit inheritance can redirect repository identity")
            self.assertFalse(set(inherited) & set(kwargs["env"]), "inherited Git context was forwarded")

    def test_initial_metadata_root_must_match_script_repository(self):
        target = public.scratch() / "never-written"
        actual_roots = self.prep._git("worktree", "list", "--porcelain")
        calls = []
        def metadata(*args, **kwargs):
            calls.append(args)
            if "--show-toplevel" in args:
                return str(target.parent) + "\n"  # Synthetic foreign identity; no outside path is touched.
            if args[:2] == ("worktree", "list"):
                return actual_roots
            if args and args[0] == "check-ignore":
                return ""
            raise AssertionError("unexpected metadata query: " + repr(args))
        with patch.object(self.prep, "_git", side_effect=metadata):
            with self.assertRaises(ValueError):
                self.prep._output_root(target)
        self.assertTrue(any("--show-toplevel" in args for args in calls))
        self.assertFalse(target.exists())

    def test_existing_wsl_git_exe_fallback_retains_explicit_cwd_and_clean_environment(self):
        calls = []
        def run(argv, **kwargs):
            calls.append((argv, kwargs))
            if argv[0] == "git":
                return subprocess.CompletedProcess(argv, 128, "", "synthetic Windows gitdir")
            return subprocess.CompletedProcess(argv, 0, "synthetic-fallback-ok\n", "")
        with patch.dict(os.environ, {"GIT_DIR": "/synthetic-foreign/.git"}), \
             patch.object(self.prep.shutil, "which", return_value="existing/git.exe"), \
             patch.object(self.prep.subprocess, "run", side_effect=run):
            result = self.prep._git("worktree", "list", "--porcelain")
        self.assertEqual(result, "synthetic-fallback-ok\n")
        self.assertEqual([argv[0] for argv, _ in calls], ["git", "git.exe"])
        for _, kwargs in calls:
            self.assertEqual(kwargs["cwd"], self.prep.REPOSITORY)
            self.assertIsInstance(kwargs.get("env"), dict)
            self.assertNotIn("GIT_DIR", kwargs["env"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
