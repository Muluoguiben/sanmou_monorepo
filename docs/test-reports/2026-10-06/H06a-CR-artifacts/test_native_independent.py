"""Stdlib primitive only. Does not import or claim native MCP/runner coverage."""
import hashlib
import importlib.util
import multiprocessing as mp
import os
from pathlib import Path
import platform
import sys
import tempfile
import unittest

SOURCE = Path(os.environ["H06A_LOCK_SOURCE"])
spec = importlib.util.spec_from_file_location("review_lock", SOURCE)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def hold(path, pipe):
    lock = module.LocalLock(Path(path))
    lock.acquire()
    pipe.send("held")
    pipe.recv()
    lock.close()


class NativeIndependent(unittest.TestCase):
    def test_exit_reacquire_and_sidecar_stability(self):
        ctx = mp.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "checkpoint.json"
            a, b = ctx.Pipe()
            child = ctx.Process(target=hold, args=(str(path), b))
            child.start()
            try:
                self.assertTrue(a.poll(10))
                self.assertEqual(a.recv(), "held")
                sidecar = path.with_name(path.name + ".lock")
                inode = sidecar.stat().st_ino
                with self.assertRaises(BlockingIOError):
                    module.LocalLock(path).acquire()
                child.terminate()
                child.join(5)
                self.assertFalse(child.is_alive())
                successor = module.LocalLock(path)
                successor.acquire()
                try:
                    for i in range(3):
                        staging = path.with_suffix(".tmp")
                        staging.write_text(str(i))
                        staging.replace(path)
                        with self.assertRaises(BlockingIOError):
                            module.LocalLock(path).acquire()
                    self.assertEqual(sidecar.stat().st_ino, inode)
                finally:
                    successor.close()
            finally:
                if child.is_alive():
                    child.terminate()
                    child.join(3)
                a.close(); b.close()


if __name__ == "__main__":
    print({"python": sys.executable, "version": sys.version, "platform": platform.platform(),
           "helper_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(), "coverage": "primitive-only"}, flush=True)
    unittest.main(verbosity=2)
