"""Independent persistence/ownership tests; no implementation substitutions."""
import asyncio
import copy
import json
import multiprocessing as mp
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness.run_store import JsonRunStore, CheckpointConflict
from pioneer_agent.agent_harness.task_contracts import RunState, PolicyDecision
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from test_task_runner import runner, task, SequenceClient


def contender(path, pipe):
    try:
        with JsonRunStore(Path(path)).acquire() as owner:
            owner.load()
            pipe.send("acquired")
            if pipe.poll(5):
                pipe.recv()
    except CheckpointConflict:
        pipe.send("conflict")


class IndependentStore(unittest.TestCase):
    def test_real_spawn_competes_across_replacements(self):
        ctx = mp.get_context("spawn")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            with JsonRunStore(path).acquire() as owner:
                owner.load()
                state = RunState(run_id="run", task=task())
                for _ in range(3):
                    owner.save(state)
                    before = path.read_bytes()
                    a, b = ctx.Pipe()
                    p = ctx.Process(target=contender, args=(str(path), b))
                    p.start()
                    try:
                        self.assertTrue(a.poll(8))
                        self.assertEqual(a.recv(), "conflict")
                        p.join(5)
                        self.assertEqual(p.exitcode, 0)
                        self.assertEqual(path.read_bytes(), before)
                    finally:
                        if p.is_alive():
                            p.terminate()
                            p.join(3)
                        a.close(); b.close()

    def test_stale_identity_revision_are_nonmutating(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            store = JsonRunStore(path)
            with store.acquire() as owner:
                owner.load()
                state = RunState(run_id="run", task=task(), budget_state={"spent": 7})
                owner.save(state)
                old_revision = owner.revision
                owner.save(state)
                original = path.read_bytes()
                for rev in (old_revision, True, 2.0, -1):
                    with self.assertRaises(CheckpointConflict):
                        store.save(state, owner=owner, expected_revision=rev)
                    self.assertEqual(path.read_bytes(), original)
                for update in ({"run_id": "other"}, {"task": task(max_steps=2)}):
                    with self.assertRaises(CheckpointConflict):
                        owner.save(state.model_copy(update=update))
                    self.assertEqual(path.read_bytes(), original)
            with store.acquire() as successor:
                current = successor.load()
                current.status = "succeeded"
                successor.save(current)
                original = path.read_bytes()
                with self.assertRaises(CheckpointConflict):
                    owner.save(state)
                self.assertEqual(path.read_bytes(), original)

    def test_legacy_full_state_roundtrip_and_invalid_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            state = RunState(run_id="run", task=task(), status="paused", reason="operator",
                completed_steps=2, pending_call="observe_game", observation_ids=["o1", "o2"],
                session_id="s", window_identity={"hwnd": 9}, evidence_refs=["frame:x"],
                budget_state={"reservation": {"x": 5}, "deadline": 99})
            path.write_text(state.model_dump_json())
            with JsonRunStore(path).acquire() as owner:
                owner.save(owner.load())
            raw = json.loads(path.read_text())
            self.assertEqual(raw["state"], state.model_dump(mode="json"))
            for change in ({"storage_version": 2}, {"storage_version": True},
                           {"revision": 0}, {"revision": "1"}, {"owner_id": ""}):
                damaged = {**raw, **change}
                path.write_text(json.dumps(damaged))
                before = path.read_bytes()
                with JsonRunStore(path).acquire() as owner:
                    with self.assertRaises(ValueError):
                        owner.load()
                self.assertEqual(path.read_bytes(), before)

    def test_equal_budget_reload_nonbudget_state_is_authoritative(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            client = SequenceClient()
            r = runner(client, store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="pause")]))
            asyncio.run(r.run())
            with JsonRunStore(path).acquire() as owner:
                newer = owner.load()
                newer.session_id = "different-session"
                newer.reason = "another-owner"
                owner.save(newer)
            count = len(client.calls)
            result = asyncio.run(r.run(resume=True))
            self.assertEqual(result.reason, "session_identity_changed")
            self.assertEqual(client.calls[count:], ["session_status"])

    def test_changed_budget_reuse_refuses_without_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            r = runner(store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="pause")]))
            asyncio.run(r.run())
            with JsonRunStore(path).acquire() as owner:
                newer = owner.load()
                newer.budget_state["deadline"] -= 1
                owner.save(newer)
            before = path.read_bytes()
            calls = list(r._client.calls)
            with self.assertRaisesRegex(CheckpointConflict, "fresh runner"):
                asyncio.run(r.run(resume=True))
            self.assertEqual(before, path.read_bytes())
            self.assertEqual(calls, r._client.calls)
            with JsonRunStore(path).acquire():
                pass


if __name__ == "__main__":
    unittest.main(verbosity=2)
