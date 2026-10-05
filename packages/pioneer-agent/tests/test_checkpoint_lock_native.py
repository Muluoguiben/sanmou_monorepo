"""Native OS primitive tests, intentionally stdlib-only (not full MCP coverage)."""
import importlib.util
import multiprocessing
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest


def backend():
    source = Path(__file__).parents[1] / "src/pioneer_agent/agent_harness/_checkpoint_lock.py"
    spec = importlib.util.spec_from_file_location("h06a_native_lock", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def child_owner(path, pipe):
    lock = backend().LocalLock(Path(path))
    lock.acquire()
    pipe.send("owned")
    pipe.recv()
    lock.close()


class NativeLockTests(unittest.TestCase):
    def test_native_process_exit_releases_stable_lock(self):
        ctx = multiprocessing.get_context("spawn")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            parent, child_pipe = ctx.Pipe()
            child = ctx.Process(target=child_owner, args=(str(path), child_pipe))
            try:
                child.start()
                self.assertTrue(parent.poll(15))
                self.assertEqual(parent.recv(), "owned")
                with self.assertRaises(BlockingIOError):
                    backend().LocalLock(path).acquire()
                identity = path.with_name("state.json.lock").stat().st_ino
                child.terminate()
                child.join(5)
                self.assertFalse(child.is_alive())
                successor = backend().LocalLock(path)
                successor.acquire()
                successor.close()
                self.assertEqual(path.with_name("state.json.lock").stat().st_ino, identity)
            finally:
                if child.is_alive():
                    child.terminate()
                child.join(5)
                parent.close()
                child_pipe.close()

    def test_native_independent_paths_and_same_process_contention(self):
        with TemporaryDirectory() as tmp:
            module = backend()
            first = module.LocalLock(Path(tmp) / "first.json")
            second = module.LocalLock(Path(tmp) / "second.json")
            first.acquire()
            try:
                with self.assertRaises(BlockingIOError):
                    module.LocalLock(first.path).acquire()
                second.acquire()
                second.close()
            finally:
                first.close()
            first.close()

    def test_native_hardlink_checkpoint_refused(self):
        with TemporaryDirectory() as tmp:
            module = backend()
            original = Path(tmp) / "original.json"
            original.write_text("{}")
            alias = Path(tmp) / "alias.json"
            os.link(original, alias)
            with self.assertRaises(module.UnsupportedCheckpointBackend):
                module.LocalLock(alias).acquire()


if __name__ == "__main__":
    unittest.main()
