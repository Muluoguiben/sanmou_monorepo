"""H06a offline local ownership/CAS contract tests."""
import json
import asyncio
import multiprocessing
import inspect
import hashlib
import sys
import threading
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness.run_store import JsonRunStore, MemoryRunStore, RunOwnership, CheckpointConflict
from pioneer_agent.agent_harness._checkpoint_lock import LocalLock, UnsupportedCheckpointBackend
from pioneer_agent.agent_harness.task_contracts import RunState, PolicyDecision
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.app import game_agent
import test_task_cli
from test_task_runner import BASE, SequenceClient, runner, task


def _race_child(root, start, release, pipe):
    class Client(test_task_cli.ManagedSequence):
        async def __aenter__(self):
            self.entries += 1
            pipe.send(("entered", self.entries))
            if not await asyncio.to_thread(release.wait, 15):
                raise RuntimeError("test rendezvous timed out")
            return self
    client = Client()
    root = Path(root)
    args = game_agent.build_parser().parse_args([
        "--screenshot", str(root / "unused.png"), "--task-spec", str(root / "task.json"),
        "--journal-path", str(root / "journal.json"), "--tool-log-path", str(root / "tools.jsonl"),
        "--run-state-path", str(root / "run.json"), "--run-trace-path", str(root / "trace.jsonl"),
    ])
    def harness(**kwargs):
        return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
    if not start.wait(15):
        raise RuntimeError("test start timed out")
    with patch.object(game_agent, "RecommendationHarness", side_effect=harness):
        result = asyncio.run(game_agent._run_task(args, game_client=client))
    pipe.send(("result", result, client.entries, client.calls))


def _crash_child(path, boundary, pipe):
    store = JsonRunStore(Path(path))
    original_write = store._write
    original_replace = Path.replace
    def parked():
        pipe.send("parked")
        pipe.recv()  # Parent kills only this disposable process at this cut.
    def replace(temporary, target):
        raw = json.loads(temporary.read_text())
        if raw["state"]["pending_call"] == "session_status":
            if boundary == "temp-before-replace":
                parked()
            result = original_replace(temporary, target)
            if boundary == "after-replace":
                parked()
            return result
        return original_replace(temporary, target)
    def write(envelope):
        original_write(envelope)
        if boundary == "reservation-before-dispatch" and envelope.state.pending_call == "session_status":
            parked()
    store._write = write
    with patch.object(Path, "replace", replace):
        asyncio.run(runner(SequenceClient(count=1), store=store,
                           budget=RunBudgetLedger(clock=lambda: 1001., monotonic=lambda: 1001.)).run(resume=True))


class CheckpointOwnershipTests(unittest.TestCase):
    def test_concurrent_old_close_cannot_release_successor(self):
        lines, start = inspect.getsourcelines(RunOwnership.close)
        cut = next(start + i for i, line in enumerate(lines) if "self.active = False" in line)
        with TemporaryDirectory() as tmp:
            for store in (MemoryRunStore(), JsonRunStore(Path(tmp) / "run.json")):
                with self.subTest(store=type(store).__name__):
                    old = store.acquire()
                    old.load()
                    parked, resume = threading.Event(), threading.Event()
                    errors = []
                    def trace(frame, event, arg):
                        if frame.f_code is RunOwnership.close.__code__ and event == "line" and frame.f_lineno == cut:
                            parked.set()
                            if not resume.wait(5):
                                raise RuntimeError("test rendezvous timeout")
                        return trace
                    def delayed():
                        sys.settrace(trace)
                        try:
                            old.close()
                        except BaseException as exc:
                            errors.append(type(exc).__name__)
                        finally:
                            sys.settrace(None)
                    worker = threading.Thread(target=delayed)
                    worker.start()
                    successor = None
                    try:
                        self.assertTrue(parked.wait(5))
                        old.close()
                        successor = store.acquire()
                        successor.load()
                        resume.set()
                        worker.join(5)
                        self.assertFalse(worker.is_alive())
                        self.assertEqual(errors, [])
                        successor.check()
                        with self.assertRaises(CheckpointConflict):
                            store.acquire()
                    finally:
                        resume.set()
                        worker.join(5)
                        if successor:
                            successor.close()
                        old.close()

    def test_exclusive_owner_revision_and_released_owner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            store = JsonRunStore(path)
            with store.acquire() as owner:
                self.assertIsNone(owner.load())
                state = RunState(run_id="run", task=task())
                owner.save(state)
                original = path.read_bytes()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
                with self.assertRaises(CheckpointConflict):
                    store.save(state, owner=owner, expected_revision=0)
                self.assertEqual(path.read_bytes(), original)
                state.status = "succeeded"
                owner.save(state)
                self.assertEqual(owner.revision, 2)
            with self.assertRaises(CheckpointConflict):
                owner.save(state)
            with store.acquire() as successor:
                self.assertEqual(successor.load().status, "succeeded")
                self.assertEqual(successor.revision, 2)

    def test_identity_and_legacy_migration(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            state = RunState(run_id="run", task=task(), pending_call="observe_game",
                             status="waiting", reason="await_next_observation", completed_steps=2,
                             observation_ids=["obs-1", "obs-2"], session_id="fixture-session",
                             window_identity={"hwnd": 17}, last_captured_at=BASE,
                             evidence_refs=["frame_sha256:" + "a" * 64],
                             budget_state={"reserved": 3, "deadline": 12, "reservations": {"spent": 5}})
            path.write_text(state.model_dump_json(), encoding="utf-8")
            with JsonRunStore(path).acquire() as owner:
                loaded = owner.load()
                self.assertEqual(loaded, state)
                owner.save(loaded)
                encoded = json.loads(path.read_text())
                self.assertEqual(encoded["state"], state.model_dump(mode="json"))
                for changed in (state.model_copy(update={"run_id": "other"}),
                                state.model_copy(update={"task": task(max_steps=2)})):
                    with self.assertRaises(CheckpointConflict):
                        owner.save(changed)

    def test_stale_revision_owner_and_terminal_rollback_preserve_winner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            store = JsonRunStore(path)
            with store.acquire() as old:
                old.load()
                state = RunState(run_id="run", task=task(), budget_state={"deadline": 123, "spent": 5})
                old.save(state)
            with store.acquire() as current:
                latest = current.load()
                latest.status = "succeeded"
                latest.budget_state["spent"] = 6
                current.save(latest)
                winner = path.read_bytes()
                for owner, revision in ((old, old.revision), (current, current.revision - 1)):
                    with self.assertRaises(CheckpointConflict):
                        store.save(state, owner=owner, expected_revision=revision)
                with self.assertRaises(CheckpointConflict):
                    current.save(state)
                self.assertEqual(path.read_bytes(), winner)
                self.assertEqual(current.load().budget_state, {"deadline": 123, "spent": 6})

    def test_foreign_store_owner_cannot_save(self):
        with TemporaryDirectory() as tmp:
            first = JsonRunStore(Path(tmp) / "first.json")
            second = JsonRunStore(Path(tmp) / "second.json")
            with first.acquire() as owner:
                owner.load()
                with self.assertRaises(CheckpointConflict):
                    second.save(RunState(run_id="run", task=task()), owner=owner, expected_revision=0)
            self.assertFalse(second.path.exists())

    def test_malformed_unknown_and_strict_revision_never_rewritten(self):
        for raw in ("{", '{"version":2}', '{"version":true}',
                    json.dumps({"storage_version": 1, "revision": True, "owner_id": "x",
                                "state": RunState(run_id="run", task=task()).model_dump(mode="json")})):
            with self.subTest(raw=raw), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                path.write_text(raw)
                with JsonRunStore(path).acquire() as owner:
                    with self.assertRaises(ValueError):
                        owner.load()
                self.assertEqual(path.read_text(), raw)
                with JsonRunStore(path).acquire():
                    pass

    def test_backend_rejects_without_checkpoint_or_sidecar(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            with patch.object(LocalLock, "_validate_backend", side_effect=UnsupportedCheckpointBackend()):
                with self.assertRaises(UnsupportedCheckpointBackend):
                    JsonRunStore(path).acquire()
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_replaced_checkpoint_does_not_replace_lock(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            with JsonRunStore(path).acquire() as owner:
                owner.load()
                before = path.with_name("run.json.lock").stat().st_ino
                state = RunState(run_id="run", task=task())
                for _ in range(3):
                    owner.save(state)
                self.assertEqual(path.with_name("run.json.lock").stat().st_ino, before)
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
            self.assertTrue(path.with_name("run.json.lock").exists())

    def test_real_process_cli_race_loser_zero_connect_calls_writes(self):
        ctx = multiprocessing.get_context("spawn")
        with TemporaryDirectory() as tmp:
            test_task_cli.TaskCliTests().args(Path(tmp))
            start, release = ctx.Event(), ctx.Event()
            pairs = [ctx.Pipe() for _ in range(2)]
            children = [ctx.Process(target=_race_child, args=(tmp, start, release, pair[1])) for pair in pairs]
            try:
                for child in children:
                    child.start()
                start.set()
                messages = []
                for pair in pairs:
                    self.assertTrue(pair[0].poll(15), "child must report ownership decision")
                    messages.append(pair[0].recv())
                winner = next(i for i, item in enumerate(messages) if item[0] == "entered")
                loser = messages[1 - winner]
                self.assertEqual(loser[0], "result")
                self.assertEqual(loser[1]["reason"], "checkpoint_conflict")
                self.assertEqual(loser[2:], (0, []))
                self.assertFalse((Path(tmp) / "run.json").exists())
                release.set()
                self.assertTrue(pairs[winner][0].poll(15))
                self.assertEqual(pairs[winner][0].recv()[1]["status"], "succeeded")
                for child in children:
                    child.join(15)
                    self.assertEqual(child.exitcode, 0)
            finally:
                release.set()
                for child in children:
                    if child.is_alive():
                        child.terminate()
                    child.join(5)
                for pair in pairs:
                    for endpoint in pair:
                        endpoint.close()

    def test_real_process_crash_boundaries_preserve_budget_and_reobserve(self):
        ctx = multiprocessing.get_context("spawn")
        for boundary in ("reservation-before-dispatch", "temp-before-replace", "after-replace"):
            with self.subTest(boundary=boundary), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                seed = runner(store=JsonRunStore(path),
                              budget=RunBudgetLedger(clock=lambda: 1000., monotonic=lambda: 1000.), policy=FakeDecisionPolicy([
                    PolicyDecision(action="pause", reason="seed")]))
                first = asyncio.run(seed.run())
                initial = first.budget_state
                parent, child_pipe = ctx.Pipe()
                child = ctx.Process(target=_crash_child, args=(str(path), boundary, child_pipe))
                try:
                    child.start()
                    self.assertTrue(parent.poll(15), "crash boundary not reached")
                    self.assertEqual(parent.recv(), "parked")
                    child.terminate()
                    child.join(5)
                    self.assertFalse(child.is_alive())
                    durable = JsonRunStore(path).load()
                    self.assertEqual(durable.budget_state["deadline"], initial["deadline"])
                    self.assertGreaterEqual(len(durable.budget_state["reservations"]), len(initial["reservations"]))
                    self.assertTrue(set(initial["reservations"]).issubset(durable.budget_state["reservations"]))
                    client = SequenceClient(count=1)
                    resumed = runner(client, store=JsonRunStore(path),
                                     budget=RunBudgetLedger(clock=lambda: 1002., monotonic=lambda: 1002.))
                    self.assertEqual(resumed.budget.snapshot()["deadline"], initial["deadline"])
                    result = asyncio.run(resumed.run(resume=True))
                    self.assertEqual(result.status, "succeeded")
                    self.assertEqual(client.calls[:2], ["session_status", "observe_game"])
                    self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
                    self.assertTrue(set(durable.budget_state["reservations"]).issubset(result.budget_state["reservations"]))
                    self.assertLessEqual(result.budget_state["remaining"], durable.budget_state["remaining"])
                finally:
                    if child.is_alive():
                        child.terminate()
                    child.join(5)
                    parent.close()
                    child_pipe.close()


class RunnerOwnershipTests(unittest.IsolatedAsyncioTestCase):
    async def test_cli_primary_survives_owner_cleanup_and_success_exposes_it(self):
        for mode in ("cancel", "conflict", "success"):
            with self.subTest(mode=mode), TemporaryDirectory() as tmp:
                root = Path(tmp)
                args = test_task_cli.TaskCliTests().args(root)
                real_close, real_save = LocalLock.close, JsonRunStore.save
                primary = asyncio.CancelledError() if mode == "cancel" else CheckpointConflict("primary")
                def close(lock):
                    real_close(lock)
                    raise OSError("secondary after release")
                def save(store, state, **kwargs):
                    if mode == "conflict" and state.pending_call == "session_status":
                        raise primary
                    return real_save(store, state, **kwargs)
                class Client(test_task_cli.ManagedSequence):
                    async def call_tool(self, name, arguments):
                        if mode == "cancel":
                            raise primary
                        return await super().call_tool(name, arguments)
                client = Client()
                def harness(**kwargs):
                    return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
                with patch.object(LocalLock, "close", close), patch.object(JsonRunStore, "save", save), patch.object(game_agent, "RecommendationHarness", side_effect=harness):
                    if mode == "conflict":
                        result = await game_agent._run_task(args, game_client=client)
                        self.assertEqual(result["reason"], "checkpoint_conflict")
                        self.assertEqual(result["checkpoint_cleanup_errors"], ["OSError"])
                    else:
                        with self.assertRaises(asyncio.CancelledError if mode == "cancel" else OSError) as caught:
                            await game_agent._run_task(args, game_client=client)
                        if mode == "cancel":
                            self.assertIs(caught.exception, primary)
                            self.assertIsInstance(primary.__cause__, OSError)
                with JsonRunStore(args.run_state_path).acquire() as owner:
                    self.assertEqual(owner.load().status, {"cancel": "cancelled", "conflict": "running", "success": "succeeded"}[mode])

    async def test_direct_primary_survives_owner_cleanup_and_success_exposes_it(self):
        for mode in ("cancel", "conflict", "success"):
            with self.subTest(mode=mode), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                primary = asyncio.CancelledError() if mode == "cancel" else CheckpointConflict("primary")
                real_close, real_save = LocalLock.close, JsonRunStore.save
                def close(lock):
                    real_close(lock)
                    raise OSError("secondary after release")
                def save(store, state, **kwargs):
                    if mode == "conflict" and state.pending_call == "session_status":
                        raise primary
                    return real_save(store, state, **kwargs)
                async def cancel(*args):
                    raise primary
                with patch.object(LocalLock, "close", close), patch.object(JsonRunStore, "save", save):
                    r = runner(store=JsonRunStore(path))
                    if mode == "cancel":
                        r._client.call_tool = cancel
                    with self.assertRaises({"cancel": asyncio.CancelledError, "conflict": CheckpointConflict, "success": OSError}[mode]) as caught:
                        await r.run()
                if mode != "success":
                    self.assertIs(caught.exception, primary)
                    self.assertIsInstance(primary.__cause__, OSError)
                with JsonRunStore(path).acquire():
                    pass

    async def test_constructor_and_reload_primary_survive_owner_cleanup(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path))
            first.pause()
            real_close = LocalLock.close
            def close(lock):
                real_close(lock)
                raise OSError("secondary after release")
            with patch.object(LocalLock, "close", close):
                with self.assertRaisesRegex(ValueError, "identity/task") as caught:
                    runner(store=JsonRunStore(path), spec=task(max_steps=2))
                self.assertIsInstance(caught.exception.__cause__, OSError)
            second = runner(store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="advance")]))
            await second.run(resume=True)
            winner = path.read_bytes()
            with patch.object(LocalLock, "close", close):
                with self.assertRaisesRegex(CheckpointConflict, "fresh runner") as caught:
                    await first.run(resume=True)
                self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertEqual(path.read_bytes(), winner)
            with JsonRunStore(path).acquire():
                pass

    async def test_idle_pause_cancel_primary_survive_owner_cleanup(self):
        for action in ("pause", "cancel"):
            for fail_save in (False, True):
                with self.subTest(action=action, fail_save=fail_save), TemporaryDirectory() as tmp:
                    path = Path(tmp) / "run.json"
                    primary = CheckpointConflict("primary")
                    real_close, real_save = LocalLock.close, JsonRunStore.save
                    def close(lock):
                        real_close(lock)
                        raise OSError("secondary after release")
                    def save(store, state, **kwargs):
                        if fail_save:
                            raise primary
                        return real_save(store, state, **kwargs)
                    with patch.object(LocalLock, "close", close), patch.object(JsonRunStore, "save", save):
                        r = runner(store=JsonRunStore(path))
                        with self.assertRaises(CheckpointConflict if fail_save else OSError) as caught:
                            getattr(r, action)()
                    if fail_save:
                        self.assertIs(caught.exception, primary)
                        self.assertIsInstance(primary.__cause__, OSError)
                        self.assertFalse(path.exists())
                    with JsonRunStore(path).acquire():
                        pass

    async def test_primary_cancel_and_conflict_survive_cleanup_failure(self):
        for primary in ("cancel", "conflict"):
            with self.subTest(primary=primary), TemporaryDirectory() as tmp:
                root = Path(tmp)
                args = test_task_cli.TaskCliTests().args(root)
                original = JsonRunStore.save
                saves = []
                def save(store, state, **kwargs):
                    saves.append(state.pending_call)
                    if primary == "conflict" and state.pending_call == "session_status":
                        raise CheckpointConflict("synthetic conflict")
                    return original(store, state, **kwargs)
                class Client(test_task_cli.ManagedSequence):
                    async def call_tool(self, *args):
                        raise asyncio.CancelledError()
                    async def __aexit__(self, kind, error, traceback):
                        self.primary = error
                        raise RuntimeError("synthetic cleanup")
                client = Client()
                with patch.object(JsonRunStore, "save", save):
                    if primary == "cancel":
                        with self.assertRaises(asyncio.CancelledError) as caught:
                            await game_agent._run_task(args, game_client=client)
                        self.assertIsInstance(caught.exception.__cause__, RuntimeError)
                    else:
                        result = await game_agent._run_task(args, game_client=client)
                        self.assertEqual(result["reason"], "checkpoint_conflict")
                        self.assertEqual(saves, [None, None, "session_status"])
                self.assertIsInstance(client.primary, asyncio.CancelledError if primary == "cancel" else CheckpointConflict)
                with JsonRunStore(args.run_state_path).acquire() as owner:
                    self.assertEqual(owner.load().status, "cancelled" if primary == "cancel" else "running")
                traces = [json.loads(line) for line in args.run_trace_path.read_text().splitlines()]
                cleanup = next(row for row in traces if row["event"] == "transport_cleanup")
                self.assertEqual(cleanup["error_type"], "RuntimeError")
                primary_name = type(client.primary).__name__
                self.assertEqual(cleanup["metadata"]["primary_error_type"], {
                    "type": "string", "length": len(primary_name),
                    "sha256": hashlib.sha256(primary_name.encode()).hexdigest(),
                })

    async def test_cleanup_preservation_keeps_timeout_conversion(self):
        class Trace:
            def _emit(self, *args, **kwargs):
                pass
        class Client(test_task_cli.ManagedSequence):
            async def __aexit__(self, *args):
                raise RuntimeError("cleanup")
        with self.assertRaises(TimeoutError):
            async with asyncio.timeout(0.01):
                async with game_agent._task_client_lifetime(Client(), Trace()):
                    await asyncio.Event().wait()

    async def test_borrowed_owner_cannot_bind_two_runners(self):
        with TemporaryDirectory() as tmp:
            store = JsonRunStore(Path(tmp) / "run.json")
            with store.acquire() as owner:
                template = runner()
                template.close()
                kwargs = dict(task=task(), run_id="run", harness=template.harness,
                              store=store, ownership=owner, policy=template.policy,
                              context_builder=template.context_builder, budget=RunBudgetLedger(),
                              trace=template.trace)
                # Restore the original fake client; do not nest a prior runner wrapper.
                template.harness.game_client = template._client
                first = TaskRunner(**kwargs)
                with self.assertRaisesRegex(CheckpointConflict, "already bound"):
                    TaskRunner(**kwargs)
                self.assertTrue(owner.active)
                self.assertEqual((await first.run()).status, "succeeded")

    async def test_active_close_cannot_release_inflight_owner(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            client = SequenceClient()
            r = runner(client, store=JsonRunStore(path))
            def after_call(name):
                with self.assertRaisesRegex(RuntimeError, "cancel and await"):
                    r.close()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
                r.cancel()
            client.after_call = after_call
            self.assertEqual((await r.run()).status, "cancelled")
            with JsonRunStore(path).acquire():
                pass

    async def test_independent_runner_refused_then_pause_releases(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path))
            with self.assertRaises(CheckpointConflict):
                runner(store=JsonRunStore(path))
            first.pause()
            second = runner(SequenceClient(), store=JsonRunStore(path))
            self.assertEqual((await second.run()).status, "paused")
            first.cancel()
            self.assertEqual(JsonRunStore(path).load().status, "cancelled")

    async def test_conflict_never_settles_or_retries_finish(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            r = runner(store=JsonRunStore(path))
            original = r.store.save
            calls = []
            def conflict(state, **kwargs):
                calls.append(state.pending_call)
                if state.pending_call == "session_status":
                    raise CheckpointConflict("synthetic stale owner")
                return original(state, **kwargs)
            r.store.save = conflict
            with self.assertRaises(CheckpointConflict):
                await r.run()
            self.assertEqual(r._client.calls, [])
            self.assertEqual(calls, [None, None, "session_status"])
            self.assertEqual(r.budget.summary()["pending"], 2)
            self.assertEqual(JsonRunStore(path).load().status, "running")

    async def test_failed_construction_and_explicit_close_release(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path))
            first.pause()
            with self.assertRaises(ValueError):
                runner(store=JsonRunStore(path), spec=task(max_steps=2))
            second = runner(store=JsonRunStore(path))
            second.close()
            with JsonRunStore(path).acquire():
                pass

    async def test_other_owner_progress_requires_fresh_nonterminal_ledger(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="first")]))
            await first.run()
            second = runner(SequenceClient(count=1), store=JsonRunStore(path), policy=FakeDecisionPolicy([
                PolicyDecision(action="pause", reason="second")]))
            await second.run(resume=True)
            winner = path.read_bytes()
            with self.assertRaisesRegex(CheckpointConflict, "fresh runner"):
                await first.run(resume=True)
            self.assertEqual(path.read_bytes(), winner)
            third = runner(SequenceClient(count=2), store=JsonRunStore(path))
            self.assertEqual((await third.run(resume=True)).status, "succeeded")
            count = len(first._client.calls)
            self.assertEqual((await first.run(resume=True)).status, "succeeded")
            self.assertEqual(len(first._client.calls), count)

    async def test_direct_cancel_pause_async_and_runtime_release(self):
        for action in ("cancel", "pause", "async", "runtime"):
            with self.subTest(action=action), TemporaryDirectory() as tmp:
                path = Path(tmp) / "run.json"
                client = SequenceClient()
                r = runner(client, store=JsonRunStore(path))
                if action in ("cancel", "pause"):
                    getattr(r, action)()
                else:
                    async def fail(*args):
                        if action == "async":
                            raise asyncio.CancelledError()
                        raise RuntimeError("synthetic")
                    client.call_tool = fail
                    if action == "async":
                        with self.assertRaises(asyncio.CancelledError):
                            await r.run()
                    else:
                        self.assertEqual((await r.run()).status, "failed")
                with JsonRunStore(path).acquire() as owner:
                    self.assertEqual(owner.load().status,
                                     "paused" if action == "pause" else "failed" if action == "runtime" else "cancelled")

    async def test_cli_holds_through_cleanup_and_releases_on_all_exits(self):
        for phase in ("enter", "call", "exit", "async_enter", "async_call", "async_exit", "pause", "success"):
            with self.subTest(phase=phase), TemporaryDirectory() as tmp:
                root = Path(tmp)
                args = test_task_cli.TaskCliTests().args(root)
                test = self
                class Client(test_task_cli.ManagedSequence):
                    exits = 0
                    async def __aenter__(self):
                        self.entries += 1
                        if phase == "enter":
                            raise RuntimeError("enter")
                        if phase == "async_enter":
                            raise asyncio.CancelledError()
                        return self
                    async def call_tool(self, name, arguments):
                        if phase == "call":
                            raise RuntimeError("call")
                        if phase == "async_call":
                            raise asyncio.CancelledError()
                        return await super().call_tool(name, arguments)
                    async def __aexit__(self, *unused):
                        self.exits += 1
                        with test.assertRaises(CheckpointConflict):
                            JsonRunStore(args.run_state_path).acquire()
                        if phase == "exit":
                            raise RuntimeError("exit")
                        if phase == "async_exit":
                            raise asyncio.CancelledError()
                        return False
                client = Client()
                def harness(**kwargs):
                    return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
                policy = FakeDecisionPolicy([PolicyDecision(action="pause", reason="pause")])
                with patch.object(game_agent, "RecommendationHarness", side_effect=harness):
                    if phase == "pause":
                        with patch("pioneer_agent.agent_harness.task_policy.RuleDecisionPolicy", return_value=policy):
                            result = await game_agent._run_task(args, game_client=client)
                            self.assertEqual(result["status"], "paused")
                    elif phase.startswith("async"):
                        with self.assertRaises(asyncio.CancelledError):
                            await game_agent._run_task(args, game_client=client)
                    else:
                        result = await game_agent._run_task(args, game_client=client)
                        self.assertEqual(result["status"], "failed" if phase in ("enter", "call") else "succeeded")
                with JsonRunStore(args.run_state_path).acquire():
                    pass
                self.assertEqual(client.exits, 0 if phase in ("enter", "async_enter") else 1)


class HarnessBindingTests(unittest.IsolatedAsyncioTestCase):
    def fresh(self, prior, store, **overrides):
        kwargs = dict(task=prior.state.task, run_id=prior.state.run_id,
                      harness=prior.harness, store=store, policy=RuleDecisionPolicy(),
                      context_builder=prior.context_builder, budget=RunBudgetLedger(), trace=prior.trace)
        kwargs.update(overrides)
        return TaskRunner(**kwargs)

    def paused_runner(self, client, path):
        return runner(client, store=JsonRunStore(path), policy=FakeDecisionPolicy([
            PolicyDecision(action="pause", reason="pause")]))

    async def test_same_harness_fresh_runner_resumes_without_retired_wrapper(self):
        with TemporaryDirectory() as tmp:
            path, client = Path(tmp) / "run.json", SequenceClient()
            first = self.paused_runner(client, path)
            self.assertEqual((await first.run()).status, "paused")
            self.assertIs(first.harness.game_client, client)
            fresh = self.fresh(first, JsonRunStore(path))
            self.assertIs(fresh._client, client)
            result = await fresh.run(resume=True)
            self.assertEqual(result.status, "succeeded")
            self.assertEqual(result.observation_ids, ["obs-1", "obs-2", "obs-3"])
            self.assertEqual(len(client.calls), 12)
            self.assertEqual(fresh.budget.summary()["counts"]["tool"], 12)
            self.assertIs(first.harness.game_client, client)

    async def test_same_runner_reinstalls_wrapper_without_budget_bypass(self):
        with TemporaryDirectory() as tmp:
            path, client = Path(tmp) / "run.json", SequenceClient()
            first = self.paused_runner(client, path)
            await first.run()
            before = first.state.budget_state["deadline"]
            first.policy = RuleDecisionPolicy()
            self.assertEqual((await first.run(resume=True)).status, "succeeded")
            self.assertEqual(first.budget.summary()["counts"]["tool"], len(client.calls))
            self.assertEqual(first.state.budget_state["deadline"], before)
            self.assertIs(first.harness.game_client, client)

    async def test_delayed_old_close_cannot_clobber_successor_wrapper(self):
        with TemporaryDirectory() as tmp:
            path, client = Path(tmp) / "run.json", SequenceClient()
            first = self.paused_runner(client, path)
            await first.run()
            second = self.fresh(first, JsonRunStore(path))
            wrapper = second.harness.game_client
            def check(name=None):
                first.close()
                first.close()
                self.assertIs(second.harness.game_client, wrapper)
                second._ownership.check()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
            check()
            client.after_call = check
            self.assertEqual((await second.run(resume=True)).status, "succeeded")
            self.assertIs(second.harness.game_client, client)

    async def test_third_party_replacement_survives_old_close_and_reentry(self):
        with TemporaryDirectory() as tmp:
            path, client = Path(tmp) / "run.json", SequenceClient()
            first = self.paused_runner(client, path)
            await first.run()
            third_party = SequenceClient(count=1)
            first.harness.game_client = third_party
            before, calls = path.read_bytes(), list(client.calls)
            first.close()
            self.assertIs(first.harness.game_client, third_party)
            with self.assertRaises(CheckpointConflict):
                await first.run(resume=True)
            self.assertEqual(path.read_bytes(), before)
            self.assertEqual(client.calls, calls)
            self.assertEqual(third_party.calls, [])
            self.assertIs(first.harness.game_client, third_party)

    async def test_occupied_harness_rejected_before_checkpoint_acquire(self):
        with TemporaryDirectory() as tmp:
            first = runner(store=JsonRunStore(Path(tmp) / "first.json"))
            wrapper = first.harness.game_client
            other = JsonRunStore(Path(tmp) / "other.json")
            try:
                with patch.object(other, "acquire", side_effect=AssertionError("must reject before acquire")):
                    with self.assertRaisesRegex(CheckpointConflict, "harness already bound"):
                        self.fresh(first, other)
                self.assertIs(first.harness.game_client, wrapper)
                first._ownership.check()
                self.assertFalse(other.path.exists())
                self.assertFalse(other.path.with_name("other.json.lock").exists())
                self.assertEqual(first._client.calls, [])
            finally:
                first.close()

    async def test_constructor_failure_does_not_replace_harness_client(self):
        with TemporaryDirectory() as tmp:
            path, client = Path(tmp) / "run.json", SequenceClient()
            first = self.paused_runner(client, path)
            await first.run()
            before = path.read_bytes()
            real_close = LocalLock.close
            def close(lock):
                real_close(lock)
                raise OSError("secondary teardown")
            with patch.object(LocalLock, "close", close):
                with self.assertRaisesRegex(ValueError, "identity/task") as caught:
                    self.fresh(first, JsonRunStore(path), task=task(max_steps=2))
                self.assertIsInstance(caught.exception.__cause__, OSError)
            self.assertIs(first.harness.game_client, client)
            self.assertEqual(path.read_bytes(), before)
            with JsonRunStore(path).acquire():
                pass

    async def test_owner_cleanup_failure_still_detaches_own_wrapper(self):
        with TemporaryDirectory() as tmp:
            path, client = Path(tmp) / "run.json", SequenceClient()
            real_close = LocalLock.close
            def close(lock):
                real_close(lock)
                raise OSError("secondary teardown")
            with patch.object(LocalLock, "close", close):
                first = self.paused_runner(client, path)
                with self.assertRaises(OSError):
                    await first.run()
            self.assertIs(first.harness.game_client, client)
            second = self.fresh(first, JsonRunStore(path))
            self.assertEqual((await second.run(resume=True)).status, "succeeded")

    async def test_external_owner_is_held_after_wrapper_detaches(self):
        with TemporaryDirectory() as tmp:
            path, client = Path(tmp) / "run.json", SequenceClient()
            template = runner(client)
            template.close()
            store = JsonRunStore(path)
            with store.acquire() as owner:
                first = self.fresh(template, store, ownership=owner, policy=FakeDecisionPolicy([
                    PolicyDecision(action="pause", reason="pause")]))
                await first.run()
                self.assertIs(first.harness.game_client, client)
                owner.check()
                with self.assertRaises(CheckpointConflict):
                    JsonRunStore(path).acquire()
                with self.assertRaises(CheckpointConflict):
                    self.fresh(first, store, ownership=owner)
                owner.check()
                self.assertIs(first.harness.game_client, client)
            second = self.fresh(first, JsonRunStore(path))
            self.assertEqual((await second.run(resume=True)).status, "succeeded")

    async def test_replaced_client_before_run_rejects_without_persistence(self):
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            first = runner(store=JsonRunStore(path))
            replacement = SequenceClient()
            first.harness.game_client = replacement
            with self.assertRaises(CheckpointConflict):
                await first.run()
            self.assertIs(first.harness.game_client, replacement)
            self.assertFalse(path.exists())
            self.assertEqual(first.budget.summary()["counts"], {"step": 0, "tool": 0, "model": 0})
            self.assertEqual(replacement.calls, [])
            with JsonRunStore(path).acquire():
                pass


if __name__ == "__main__":
    unittest.main()
