"""Freeze a real thread interleaving with tracing, not private-field mutation."""
import inspect
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import threading
import unittest
from pioneer_agent.agent_harness.run_store import JsonRunStore, MemoryRunStore, RunOwnership, CheckpointConflict


class ConcurrentClose(unittest.TestCase):
    def test_delayed_concurrent_old_close_does_not_invalidate_successor(self):
        lines, start = inspect.getsourcelines(RunOwnership.close)
        stop_line = next(start + i for i, line in enumerate(lines) if "self.active = False" in line)
        with TemporaryDirectory() as tmp:
            for kind in ("memory", "json"):
                with self.subTest(kind=kind):
                    store = MemoryRunStore() if kind == "memory" else JsonRunStore(Path(tmp) / "state.json")
                    old = store.acquire()
                    old.load()
                    parked, resume = threading.Event(), threading.Event()
                    errors = []
                    def trace(frame, event, arg):
                        if frame.f_code is RunOwnership.close.__code__ and event == "line" and frame.f_lineno == stop_line:
                            parked.set()
                            if not resume.wait(5):
                                raise RuntimeError("review barrier timed out")
                        return trace
                    def delayed():
                        sys.settrace(trace)
                        try:
                            old.close()
                        except BaseException as error:
                            errors.append(type(error).__name__)
                        finally:
                            sys.settrace(None)
                    thread = threading.Thread(target=delayed)
                    thread.start()
                    successor = third = None
                    try:
                        self.assertTrue(parked.wait(5))
                        old.close()
                        successor = store.acquire()
                        successor.load()
                        resume.set()
                        thread.join(5)
                        self.assertFalse(thread.is_alive())
                        try:
                            successor.check()
                            intact = True
                        except CheckpointConflict:
                            intact = False
                        try:
                            third = store.acquire()
                            acquired = True
                        except CheckpointConflict:
                            acquired = False
                        print({"backend": kind, "successor_intact": intact, "third_acquired": acquired,
                               "delayed_errors": errors}, flush=True)
                        self.assertTrue(intact, "old delayed close invalidated current successor")
                        self.assertFalse(acquired, "old delayed close unlocked current successor")
                    finally:
                        resume.set()
                        thread.join(5)
                        for owner in (third, successor, old):
                            if owner:
                                try:
                                    owner.close()
                                except RuntimeError:
                                    pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
