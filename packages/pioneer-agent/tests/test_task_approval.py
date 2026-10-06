"""H07a synthetic-only lifecycle; no model, device, provider or dispatch authority."""
import asyncio
import copy
import json
import multiprocessing
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from pioneer_agent.agent_harness.context_builder import BoundedContextBuilder
from pioneer_agent.agent_harness.journal import InMemoryJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.agent_harness.run_store import CheckpointConflict, JsonRunStore, MemoryRunStore
from pioneer_agent.agent_harness.run_trace import InMemoryRunTrace
from pioneer_agent.agent_harness.task_approval import synthetic_response
from pioneer_agent.agent_harness.task_contracts import (
    CheckpointEnvelope, PolicyDecision, RunState, SyntheticApprovalResponse, parse_run_state,
)
from pioneer_agent.agent_harness.task_policy import FakeDecisionPolicy, RuleDecisionPolicy
from pioneer_agent.agent_harness.task_runner import TaskRunner
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from pioneer_agent.app import game_agent
from pioneer_agent.runbook.models import Condition
from test_task_cli import ManagedSequence
import test_task_cli
from test_task_runner import BASE, SequenceClient, task


def make_runner(*, client=None, store=None, policy=None, spec=None, now=None, budget=None, enabled=True):
    client = client or SequenceClient()
    harness = RecommendationHarness(game_client=client, journal_store=InMemoryJournalStore(),
        tool_log=InMemoryToolLog(), agent_session_id="run", model_id="offline-rule",
        clock=(lambda: now[0]) if now else lambda: BASE + timedelta(seconds=client.count + 1))
    return TaskRunner(task=spec or task(), run_id="run", harness=harness,
        store=store or MemoryRunStore(), policy=policy or FakeDecisionPolicy([
            PolicyDecision(action="request_approval", reason="synthetic test handoff")]),
        context_builder=BoundedContextBuilder(),
        budget=budget or RunBudgetLedger(BudgetLimits(max_model_attempts=0)),
        trace=InMemoryRunTrace(), synthetic_approval=enabled)


def response_for(state, *, now=None, decision="approve"):
    return synthetic_response(state.approval.request, decision=decision,
        now=now or state.approval.request.created_at)


def _process_consumer(path, response, start, release, pipe, crash=False):
    """Real OS owner contention / crash, with only offline test clients."""
    if not start.wait(15):
        raise RuntimeError("test start timeout")
    store = JsonRunStore(Path(path))
    original = store._write
    def write(envelope):
        original(envelope)
        if envelope.state.reason == "approval_consumed":
            pipe.send(("consumed", envelope.revision))
            if crash:
                pipe.recv()  # Parent terminates this disposable child at the durable cut.
            elif not release.wait(15):
                raise RuntimeError("test release timeout")
    store._write = write
    client = SequenceClient(count=1)
    try:
        runner = make_runner(client=client, store=store, policy=RuleDecisionPolicy())
        result = asyncio.run(runner.resume_synthetic(SyntheticApprovalResponse.model_validate(response)))
        pipe.send(("result", result.status, client.calls))
    except (CheckpointConflict, ValueError) as exc:
        pipe.send(("rejected", type(exc).__name__, client.calls))


class ApprovalLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_explicit_opt_in_and_policy_cannot_fill_binding(self):
        r = make_runner(enabled=False)
        result = await r.run()
        self.assertEqual(result.reason, "synthetic_approval_disabled")
        self.assertEqual(result.version, 1)
        self.assertNotIn("approval", result.model_dump())
        with self.assertRaises(ValidationError):
            PolicyDecision(action="request_approval", reason="x", request_id="forged")

    async def test_waiting_normal_resume_fresh_runner_and_pause_are_noops(self):
        store = MemoryRunStore()
        first = make_runner(store=store)
        saved = await first.run()
        self.assertEqual((saved.version, saved.status), (2, "awaiting_approval"))
        self.assertEqual(first.budget.summary()["counts"], {"step": 1, "tool": 4, "model": 0})
        self.assertEqual(saved.approval.request.approval_origin, "synthetic")
        self.assertEqual(saved.approval.request.scope, "resume_read_only_task")
        first.pause()
        self.assertEqual(store.load().status, "awaiting_approval")
        count = len(first._client.calls)
        self.assertEqual((await first.run(resume=True)).status, "awaiting_approval")
        self.assertEqual(len(first._client.calls), count)
        fresh = make_runner(store=store, client=SequenceClient(count=1), enabled=False)
        self.assertEqual((await fresh.run(resume=True)).status, "awaiting_approval")
        self.assertEqual(fresh._client.calls, [])
        self.assertEqual(fresh.policy.contexts, [])

    async def test_approved_reobserves_before_policy_and_never_grants_authority(self):
        store = MemoryRunStore()
        saved = await make_runner(store=store).run()
        client = SequenceClient(count=1)
        policy = FakeDecisionPolicy([PolicyDecision(action="continue", reason="more evidence"),
                                     PolicyDecision(action="continue", reason="fresh goal evidence")])
        r = make_runner(store=store, client=client, policy=policy)
        result = await r.resume_synthetic(response_for(saved))
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(policy.contexts[0].observation_id, "obs-2")
        self.assertEqual(client.calls[:2], ["session_status", "observe_game"])
        self.assertEqual(result.approval.revalidated_observation_id, "obs-2")
        self.assertEqual((result.execution_authority, result.executable), ("none", False))
        self.assertEqual(r.budget.summary()["counts"]["model"], 0)
        events = r.trace.events
        consumed = next(i for i, e in enumerate(events) if e.business == "approval_consumed")
        first_tool = next(i for i, e in enumerate(events) if e.event == "tool")
        revalidated = next(i for i, e in enumerate(events) if e.business == "approval_revalidated")
        first_policy = next(i for i, e in enumerate(events) if e.event == "policy")
        self.assertLess(consumed, first_tool)
        self.assertLess(revalidated, first_policy)
        with self.assertRaisesRegex(ValueError, "not awaiting"):
            await r.resume_synthetic(response_for(saved))

    async def test_fresh_goal_can_finish_before_policy(self):
        store = MemoryRunStore()
        spec = task()
        spec.success_when[0].value = 2
        saved = await make_runner(store=store, spec=spec).run()
        r = make_runner(store=store, spec=spec, client=SequenceClient(count=1))
        result = await r.resume_synthetic(response_for(saved))
        self.assertEqual((result.status, result.reason), ("succeeded", "goal_verified"))
        self.assertEqual(r.policy.contexts, [])

    async def test_every_response_binding_is_exact(self):
        fields = {"request_id": "wrong", "run_id": "wrong", "step_id": "wrong",
            "task_digest": "0" * 64, "session_id": "wrong", "window_identity": {"wrong": True},
            "observation_id": "wrong", "frame_sha256": "0" * 64, "evidence_refs": ["wrong"],
            "created_at": BASE, "expires_at": BASE + timedelta(days=1), "reason": "different"}
        for key, value in fields.items():
            with self.subTest(binding=key):
                store = MemoryRunStore()
                saved = await make_runner(store=store).run()
                raw = response_for(saved).model_dump()
                raw["request"][key] = value
                r = make_runner(store=store, client=SequenceClient(count=1))
                result = await r.resume_synthetic(SyntheticApprovalResponse.model_validate(raw))
                self.assertEqual(result.reason, "approval_binding_mismatch")
                self.assertEqual(r._client.calls, [])
                self.assertEqual(r.policy.contexts, [])

    async def test_deny_expiry_rollback_cancel_and_terminal_refuse(self):
        for case in ("deny", "expiry", "rollback", "response_future", "response_past", "cancel"):
            with self.subTest(case=case):
                store = MemoryRunStore()
                now = [BASE + timedelta(seconds=2)]
                saved = await make_runner(store=store, now=now).run()
                response = response_for(saved, decision="deny" if case == "deny" else "approve")
                if case == "expiry": now[0] = saved.approval.request.expires_at
                if case == "rollback": now[0] -= timedelta(seconds=1)
                if case in {"response_future", "response_past"}:
                    response = response_for(saved, now=now[0] + timedelta(seconds=1 if case == "response_future" else -1))
                r = make_runner(store=store, client=SequenceClient(count=1), now=now)
                if case == "cancel":
                    r.cancel()
                    with self.assertRaisesRegex(ValueError, "not awaiting"):
                        await r.resume_synthetic(response)
                    self.assertEqual(store.load().status, "cancelled")
                else:
                    result = await (r.run(resume=True) if case in {"expiry", "rollback"}
                                    else r.resume_synthetic(response))
                    expected = {"deny": "approval_denied", "expiry": "approval_expired",
                        "rollback": "approval_clock_rollback", "response_future": "approval_clock_rollback",
                        "response_past": "approval_clock_rollback"}[case]
                    self.assertEqual(result.reason, expected)
                self.assertEqual(r._client.calls, [])
                self.assertEqual(r.policy.contexts, [])

    async def test_revalidation_replay_time_identity_evidence_and_stop_reject_before_policy(self):
        cases = ("replay", "capture_rollback", "session", "window", "evidence", "stop", "stop_unknown")
        for case in cases:
            with self.subTest(case=case):
                store = MemoryRunStore()
                spec = task(stop_when=[Condition(metric="progress.current_chapter_id", op=">=", value=2)]) if case.startswith("stop") else task()
                saved = await make_runner(store=store, spec=spec).run()
                def mutate(name, payload):
                    if case == "session" and name == "session_status": payload["session"]["session_id"] = "other"
                    if "observation" in payload:
                        if case == "capture_rollback": payload["observation"]["captured_at"] = (BASE + timedelta(seconds=1)).isoformat()
                        if case == "window": payload["observation"]["window_identity"] = None
                    if case == "stop_unknown" and "runtime_state" in payload:
                        del payload["runtime_state"]["progress"]["current_chapter_id"]
                client = SequenceClient(count=0 if case == "replay" else 1, evidence=case != "evidence", mutate=mutate)
                r = make_runner(store=store, spec=spec, client=client)
                result = await r.resume_synthetic(response_for(saved))
                self.assertEqual(result.status, "failed")
                self.assertEqual(r.policy.contexts, [])
                self.assertIsNone(result.approval.revalidated_observation_id)

    async def test_same_frame_hash_is_allowed_with_new_observation(self):
        store = MemoryRunStore()
        saved = await make_runner(store=store).run()
        def mutate(name, payload):
            if "observation" in payload:
                payload["observation"]["frame_sha256"] = saved.approval.request.frame_sha256
        r = make_runner(store=store, client=SequenceClient(count=1, mutate=mutate), policy=RuleDecisionPolicy())
        self.assertEqual((await r.resume_synthetic(response_for(saved))).status, "succeeded")

    async def test_stop_condition_priority_and_ordinary_pause_unchanged(self):
        spec = task(stop_when=[Condition(metric="progress.current_chapter_id", op=">=", value=1)])
        result = await make_runner(spec=spec).run()
        self.assertEqual((result.version, result.reason), (1, "stop_condition"))
        r = make_runner(policy=FakeDecisionPolicy([PolicyDecision(action="pause", reason="pause")]))
        self.assertEqual((await r.run()).version, 1)
        r.policy = RuleDecisionPolicy()
        self.assertEqual((await r.run(resume=True)).status, "succeeded")

    async def test_deadline_and_tool_quota_restore_without_dispatch(self):
        for case in ("deadline", "tools", "steps"):
            with self.subTest(case=case):
                clock = [1000.]
                limits = BudgetLimits(max_steps=1 if case == "steps" else 10,
                    max_tool_calls=4 if case == "tools" else 100, max_model_attempts=0, max_seconds=30.)
                budget = lambda: RunBudgetLedger(limits, clock=lambda: clock[0], monotonic=lambda: clock[0])
                store = MemoryRunStore()
                saved = await make_runner(store=store, budget=budget()).run()
                if case == "deadline": clock[0] += 31
                r = make_runner(store=store, client=SequenceClient(count=1), budget=budget())
                result = await r.resume_synthetic(response_for(saved))
                self.assertEqual(result.reason, "run_deadline" if case == "deadline" else "budget_exhausted")
                self.assertEqual(r._client.calls, [])
                self.assertEqual(r.policy.contexts, [])
                self.assertEqual(r.budget.summary()["counts"]["tool"], 4)
                self.assertEqual(r.budget.summary()["counts"]["model"], 0)

    async def test_save_failures_preserve_original_and_no_followup(self):
        for boundary in ("request", "consume"):
            with self.subTest(boundary=boundary):
                store = MemoryRunStore()
                saved = await make_runner(store=store).run() if boundary == "consume" else None
                r = make_runner(store=store, client=SequenceClient(count=1 if saved else 0))
                original = store._write
                failure = OSError("synthetic persistence fault")
                def write(envelope):
                    if ((boundary == "request" and envelope.state.status == "awaiting_approval")
                            or (boundary == "consume" and envelope.state.status == "revalidating_approval")):
                        raise failure
                    original(envelope)
                store._write = write
                with self.assertRaises(OSError) as caught:
                    await (r.resume_synthetic(response_for(saved)) if saved else r.run())
                self.assertIs(caught.exception, failure)
                self.assertEqual(len(r._client.calls), 0 if saved else 4)
                self.assertEqual(len(r.policy.contexts), 0 if saved else 1)
                self.assertEqual(store.load().status, "awaiting_approval" if saved else "running")

    async def test_cli_short_circuits_before_connection(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = test_task_cli.TaskCliTests().args(root)
            store = JsonRunStore(root / "run.json")
            saved = await make_runner(store=store).run()
            client = ManagedSequence()
            for resume in (False, True):
                args.resume_task = resume
                def harness(**kwargs):
                    return RecommendationHarness(**kwargs, clock=lambda: saved.approval.request.created_at)
                with patch.object(game_agent, "RecommendationHarness", side_effect=harness):
                    result = await game_agent._run_task(args, game_client=client)
                self.assertEqual(result["status"], "awaiting_approval")
            self.assertEqual((client.entries, client.calls), (0, []))

    async def test_cli_consumed_checkpoint_fails_before_connection(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            args = test_task_cli.TaskCliTests().args(root)
            args.resume_task = True
            store = JsonRunStore(root / "run.json")
            saved = await make_runner(store=store).run()
            consumed = parse_run_state({**saved.model_dump(), "status": "revalidating_approval",
                "approval": {**saved.approval.model_dump(), "response": response_for(saved).model_dump(),
                             "consumed_at": saved.approval.request.created_at}})
            with store.acquire() as owner:
                owner.load()
                owner.save(consumed)
            client = ManagedSequence()
            result = await game_agent._run_task(args, game_client=client)
            self.assertEqual(result["reason"], "approval_revalidation_interrupted")
            self.assertEqual((client.entries, client.calls), (0, []))

    async def test_waiting_elapsed_time_and_reservations_are_not_replenished(self):
        clock = [1000.]
        budget = lambda: RunBudgetLedger(BudgetLimits(max_model_attempts=0, max_seconds=60.),
                                        clock=lambda: clock[0], monotonic=lambda: clock[0])
        store = MemoryRunStore()
        saved = await make_runner(store=store, budget=budget()).run()
        reservations = copy.deepcopy(saved.budget_state["reservations"])
        clock[0] += 20
        r = make_runner(store=store, client=SequenceClient(count=1), budget=budget())
        result = await r.run(resume=True)
        self.assertEqual(result.status, "awaiting_approval")
        self.assertEqual(r.budget.remaining_seconds(), 40.)
        self.assertEqual(r.budget.snapshot()["reservations"], reservations)
        self.assertEqual(r._client.calls, [])
        clock[0] += 41
        self.assertEqual((await r.run()).reason, "run_deadline")
        self.assertEqual(r._client.calls, [])

    async def test_waiting_clock_watermark_survives_restart_and_never_regresses(self):
        for restart in (False, True):
            with self.subTest(restart=restart):
                store = MemoryRunStore()
                now = [BASE + timedelta(seconds=2)]
                r = make_runner(store=store, now=now)
                saved = await r.run()
                now[0] += timedelta(seconds=10)
                self.assertEqual((await r.run(resume=True)).status, "awaiting_approval")
                watermark = store.load().approval.last_checked_at
                self.assertEqual(watermark, now[0])
                now[0] -= timedelta(seconds=5)
                if restart:
                    r = make_runner(store=store, now=now, client=SequenceClient(count=1))
                calls, policies = len(r._client.calls), len(r.policy.contexts)
                result = await r.resume_synthetic(response_for(saved))
                self.assertEqual(result.reason, "approval_clock_rollback")
                self.assertEqual((len(r._client.calls), len(r.policy.contexts)), (calls, policies))
                self.assertEqual(store.load().approval.last_checked_at, watermark)

    async def test_waiting_watermark_save_failure_preserves_error_and_no_followup(self):
        store = MemoryRunStore()
        now = [BASE + timedelta(seconds=2)]
        r = make_runner(store=store, now=now)
        saved = await r.run()
        now[0] += timedelta(seconds=10)
        failure = OSError("synthetic waiting watermark failure")
        store._write = lambda envelope: (_ for _ in ()).throw(failure)
        before = len(r._client.calls)
        with self.assertRaises(OSError) as caught:
            await r.run()
        self.assertIs(caught.exception, failure)
        self.assertEqual(len(r._client.calls), before)
        self.assertEqual(store.load().approval.last_checked_at, saved.approval.last_checked_at)

    async def test_both_revalidation_persistence_cuts_recheck_freshness_budget_and_cancel(self):
        for boundary in ("observation", "revalidated", "policy"):
            for expired in ("stale", "deadline", "cancel"):
                with self.subTest(boundary=boundary, expired=expired):
                    clock = [1000.]
                    now = [BASE + timedelta(seconds=2)]
                    budget = lambda: RunBudgetLedger(BudgetLimits(max_model_attempts=0, max_seconds=30.),
                        clock=lambda: clock[0], monotonic=lambda: clock[0])
                    spec = task()
                    if boundary != "policy": spec.success_when[0].value = 2
                    store = MemoryRunStore()
                    saved = await make_runner(store=store, now=now, spec=spec, budget=budget()).run()
                    now[0] += timedelta(seconds=1)
                    r = make_runner(store=store, now=now, spec=spec, client=SequenceClient(count=1), budget=budget())
                    original = store._write
                    delayed = []
                    def write(envelope):
                        original(envelope)
                        state = envelope.state
                        hit = ((boundary == "observation" and state.status == "revalidating_approval"
                                and state.observation_ids[-1] == "obs-2")
                            or (boundary == "revalidated" and state.reason == "approval_revalidated")
                            or (boundary == "policy" and state.pending_call == "policy:fake-script-v1"))
                        if hit and not delayed:
                            delayed.append(True)
                            if expired == "stale": now[0] += timedelta(seconds=120)
                            elif expired == "deadline": clock[0] += 31
                            else: r.cancel()
                    store._write = write
                    result = await r.resume_synthetic(response_for(saved))
                    self.assertTrue(delayed)
                    self.assertEqual(result.status, "cancelled" if expired == "cancel" else "failed")
                    self.assertEqual(result.reason, {"stale": "observation_stale", "deadline": "run_deadline",
                                                     "cancel": "cancel_requested"}[expired])
                    self.assertEqual(r.policy.contexts, [])

    async def test_revalidation_failure_saves_no_permit_for_later_runner(self):
        store = MemoryRunStore()
        saved = await make_runner(store=store).run()
        failure = OSError("synthetic revalidation save failure")
        original = store._write
        def write(envelope):
            if envelope.state.reason == "approval_revalidated":
                raise failure
            original(envelope)
        store._write = write
        r = make_runner(store=store, client=SequenceClient(count=1))
        with self.assertRaises(OSError) as caught:
            await r.resume_synthetic(response_for(saved))
        self.assertIs(caught.exception, failure)
        self.assertEqual(r.policy.contexts, [])
        store._write = original
        fresh = make_runner(store=store, client=SequenceClient(count=2))
        self.assertEqual((await fresh.run(resume=True)).reason, "approval_revalidation_interrupted")
        self.assertEqual((fresh._client.calls, fresh.policy.contexts), ([], []))

    async def test_postconsume_clock_rollback_at_each_revalidation_boundary(self):
        for boundary in ("consumed", "observation", "revalidated", "policy"):
            with self.subTest(boundary=boundary):
                store = MemoryRunStore()
                now = [BASE + timedelta(seconds=2)]
                spec = task()
                if boundary != "policy": spec.success_when[0].value = 2
                saved = await make_runner(store=store, now=now, spec=spec).run()
                now[0] += timedelta(seconds=1)
                r = make_runner(store=store, now=now, spec=spec, client=SequenceClient(count=1))
                write = store._write
                rolled = []
                def rollback(envelope):
                    write(envelope)
                    state = envelope.state
                    hit = ((boundary == "consumed" and state.reason == "approval_consumed")
                        or (boundary == "observation" and state.status == "revalidating_approval"
                            and state.observation_ids[-1] == "obs-2")
                        or (boundary == "revalidated" and state.reason == "approval_revalidated")
                        or (boundary == "policy" and state.pending_call == "policy:fake-script-v1"))
                    if hit and not rolled:
                        rolled.append(True)
                        now[0] -= timedelta(milliseconds=500)
                store._write = rollback
                result = await r.resume_synthetic(response_for(saved))
                self.assertTrue(rolled)
                self.assertEqual((result.status, result.reason), ("failed", "approval_clock_rollback"))
                self.assertEqual(r.policy.contexts, [])
                self.assertEqual(result.approval.last_checked_at, result.approval.consumed_at)

    async def test_revalidation_advances_watermark_then_rejects_rollback_above_consumed(self):
        for boundary in ("watermark_write", "revalidated", "policy", "after_policy"):
            with self.subTest(boundary=boundary):
                store = MemoryRunStore()
                now = [BASE + timedelta(seconds=2)]
                saved = await make_runner(store=store, now=now).run()
                now[0] += timedelta(seconds=1)
                policy = FakeDecisionPolicy([PolicyDecision(action="continue", reason="observe")])
                r = make_runner(store=store, now=now, client=SequenceClient(count=1), policy=policy)
                write = store._write
                advanced, rolled = [], []
                def advance_then_rollback(envelope):
                    write(envelope)
                    state = envelope.state
                    if (state.status == "revalidating_approval" and state.observation_ids[-1] == "obs-2"
                            and not advanced):
                        advanced.append(True)
                        now[0] = BASE + timedelta(seconds=5)
                    if state.approval.last_checked_at != BASE + timedelta(seconds=5):
                        return
                    hit = ((boundary == "watermark_write" and state.status == "revalidating_approval")
                        or (boundary == "revalidated" and state.reason == "approval_revalidated")
                        or (boundary == "policy" and state.pending_call == "policy:fake-script-v1")
                        or (boundary == "after_policy" and len(policy.contexts) == 1 and state.pending_call is None))
                    if hit and not rolled:
                        rolled.append(True)
                        now[0] = BASE + timedelta(seconds=4.5)
                store._write = advance_then_rollback
                result = await r.resume_synthetic(response_for(saved))
                self.assertTrue(advanced and rolled)
                self.assertEqual((result.status, result.reason), ("failed", "approval_clock_rollback"))
                self.assertEqual(result.approval.consumed_at, BASE + timedelta(seconds=3))
                self.assertEqual(result.approval.last_checked_at, BASE + timedelta(seconds=5))
                self.assertEqual(len(policy.contexts), 1 if boundary == "after_policy" else 0)
                self.assertEqual(r._client.count, 2)

    async def test_revalidation_watermark_progress_is_persisted_without_reconsuming(self):
        store = MemoryRunStore()
        now = [BASE + timedelta(seconds=2)]
        spec = task()
        spec.success_when[0].value = 2
        saved = await make_runner(store=store, now=now, spec=spec).run()
        now[0] += timedelta(seconds=1)
        r = make_runner(store=store, now=now, spec=spec, client=SequenceClient(count=1))
        write = store._write
        advanced = []
        def advance(envelope):
            write(envelope)
            if envelope.state.status == "revalidating_approval" and envelope.state.observation_ids[-1] == "obs-2" and not advanced:
                advanced.append(True)
                now[0] += timedelta(seconds=2)
        store._write = advance
        result = await r.resume_synthetic(response_for(saved))
        self.assertEqual(result.status, "succeeded")
        self.assertEqual(store.load().approval.last_checked_at, BASE + timedelta(seconds=5))
        self.assertEqual(store.load().approval.consumed_at, BASE + timedelta(seconds=3))
        self.assertEqual(store.load().approval.request, saved.approval.request)
        self.assertEqual(r.policy.contexts, [])
        self.assertEqual(r.budget.summary()["counts"], {"step": 2, "tool": 8, "model": 0})

    async def test_revalidation_watermark_write_failure_has_no_policy_and_no_reusable_permit(self):
        store = MemoryRunStore()
        now = [BASE + timedelta(seconds=2)]
        saved = await make_runner(store=store, now=now).run()
        now[0] += timedelta(seconds=1)
        r = make_runner(store=store, now=now, client=SequenceClient(count=1))
        write = store._write
        failure = OSError("synthetic revalidation watermark write")
        def fail_watermark(envelope):
            if envelope.state.approval.last_checked_at > envelope.state.approval.consumed_at:
                raise failure
            write(envelope)
            if envelope.state.observation_ids[-1] == "obs-2":
                now[0] = BASE + timedelta(seconds=5)
        store._write = fail_watermark
        with self.assertRaises(OSError) as caught:
            await r.resume_synthetic(response_for(saved))
        self.assertIs(caught.exception, failure)
        self.assertEqual(r.policy.contexts, [])
        store._write = write
        fresh = make_runner(store=store, now=now, client=SequenceClient(count=2))
        self.assertEqual((await fresh.run()).reason, "approval_revalidation_interrupted")
        self.assertEqual((fresh._client.calls, fresh.policy.contexts), ([], []))


class ApprovalStorageTests(unittest.TestCase):
    def test_frozen_v1_compatibility_fixture(self):
        path = Path(__file__).parent / "fixtures/agent_harness/h07a_v1_compat.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(parse_run_state(raw).model_dump(mode="json"), raw)

    def test_v1_exact_fields_and_legacy_flat_envelope_load_does_not_rewrite(self):
        state = RunState(run_id="run", task=task())
        expected = {"version", "run_id", "task", "status", "reason", "completed_steps", "pending_call",
            "observation_ids", "session_id", "window_identity", "last_captured_at", "evidence_refs",
            "budget_state", "execution_authority", "executable"}
        self.assertEqual(set(state.model_dump()), expected)
        self.assertNotIn("approval", state.model_dump_json())
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            for raw in (state.model_dump(mode="json"), CheckpointEnvelope(revision=1, owner_id="old", state=state).model_dump(mode="json")):
                data = (json.dumps(raw, indent=3) + "\n").encode()
                path.write_bytes(data)
                self.assertEqual(JsonRunStore(path).load(), state)
                self.assertEqual(path.read_bytes(), data)
            with JsonRunStore(path).acquire() as owner:
                loaded = owner.load()
                owner.save(loaded)
            raw = json.loads(path.read_text())
            self.assertEqual(raw["storage_version"], 1)
            self.assertEqual(set(raw["state"]), expected)

    def test_v2_roundtrip_strict_versions_states_and_old_model_rejects(self):
        r = make_runner()
        saved = asyncio.run(r.run())
        raw = saved.model_dump(mode="json")
        self.assertEqual(parse_run_state(raw), saved)
        with self.assertRaises(ValidationError): RunState.model_validate(raw)
        for storage, state_version in ((1, 2), (2, 1), (True, 1), (2., 2), (2, True), (2, "2"), (3, 3)):
            with self.subTest(storage=storage, state=state_version), self.assertRaises((ValidationError, ValueError)):
                CheckpointEnvelope.model_validate({"storage_version": storage, "revision": 1, "owner_id": "x",
                    "state": {**raw, "version": state_version}})
        for status in ("running", "paused", "succeeded", "revalidating_approval"):
            with self.subTest(status=status), self.assertRaises(ValidationError):
                parse_run_state({**raw, "status": status})
        with self.assertRaises(ValidationError): parse_run_state({**raw, "version": 1})
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            path.write_text(json.dumps(raw))
            with self.assertRaisesRegex(ValueError, "unsupported checkpoint format"):
                JsonRunStore(path).load()  # No unversioned-storage v2 format.

    def test_timestamp_naive_and_authority_are_rejected(self):
        saved = asyncio.run(make_runner().run())
        response = response_for(saved).model_dump()
        for location, key, value in (("response", "responded_at", BASE.replace(tzinfo=None)),
                ("request", "created_at", BASE.replace(tzinfo=None)),
                ("response", "executable", True), ("request", "execution_authority", "live"),
                ("response", "approval_origin", "human"), ("response", "scope", "dispatch")):
            raw = copy.deepcopy(response)
            (raw if location == "response" else raw["request"])[key] = value
            with self.subTest(location=location, key=key), self.assertRaises(ValidationError):
                SyntheticApprovalResponse.model_validate(raw)

    def test_cas_version_and_terminal_cannot_regress(self):
        store = MemoryRunStore()
        saved = asyncio.run(make_runner(store=store).run())
        with store.acquire() as owner:
            owner.load()
            with self.assertRaisesRegex(CheckpointConflict, "version cannot regress"):
                owner.save(RunState.model_validate({k: v for k, v in saved.model_dump().items() if k != "approval"} | {"version": 1, "status": "paused"}))
            with self.assertRaises(CheckpointConflict):
                store.save(saved, owner=owner, expected_revision=owner.revision - 1)
        r = make_runner(store=store, client=SequenceClient(count=1))
        r.cancel()
        with store.acquire() as owner:
            owner.load()
            with self.assertRaisesRegex(CheckpointConflict, "terminal checkpoint cannot resume"):
                owner.save(saved)

    def test_store_rejects_watermark_rollback(self):
        store = MemoryRunStore()
        now = [BASE + timedelta(seconds=2)]
        r = make_runner(store=store, now=now)
        asyncio.run(r.run())
        now[0] += timedelta(seconds=10)
        asyncio.run(r.run())
        with store.acquire() as owner:
            state = owner.load()
            state.approval.last_checked_at -= timedelta(seconds=5)
            with self.assertRaisesRegex(CheckpointConflict, "watermark cannot regress"):
                owner.save(state)


class ApprovalProcessTests(unittest.TestCase):
    def test_actual_process_race_only_one_consumes(self):
        ctx = multiprocessing.get_context("spawn")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            saved = asyncio.run(make_runner(store=JsonRunStore(path)).run())
            start, release = ctx.Event(), ctx.Event()
            pairs = [ctx.Pipe() for _ in range(2)]
            children = [ctx.Process(target=_process_consumer, args=(str(path), response_for(saved).model_dump(mode="json"),
                start, release, pair[1])) for pair in pairs]
            try:
                for child in children: child.start()
                start.set()
                messages = []
                for parent, _ in pairs:
                    self.assertTrue(parent.poll(20), "child did not report")
                    messages.append(parent.recv())
                self.assertEqual(sorted(m[0] for m in messages), ["consumed", "rejected"])
                self.assertEqual(next(m[2] for m in messages if m[0] == "rejected"), [])
                release.set()
                winner = next(i for i, m in enumerate(messages) if m[0] == "consumed")
                self.assertTrue(pairs[winner][0].poll(20))
                self.assertEqual(pairs[winner][0].recv()[0:2], ("result", "succeeded"))
                for child in children:
                    child.join(10)
                    self.assertEqual(child.exitcode, 0)
                self.assertEqual(JsonRunStore(path).load().status, "succeeded")
            finally:
                release.set()
                for child in children:
                    if child.is_alive(): child.terminate()
                    child.join(5)
                for pair in pairs:
                    for end in pair: end.close()

    def test_actual_process_crash_after_consumption_fresh_runner_fails_without_calls(self):
        ctx = multiprocessing.get_context("spawn")
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "run.json"
            saved = asyncio.run(make_runner(store=JsonRunStore(path)).run())
            start, release = ctx.Event(), ctx.Event()
            parent, child_end = ctx.Pipe()
            child = ctx.Process(target=_process_consumer, args=(str(path), response_for(saved).model_dump(mode="json"),
                start, release, child_end, True))
            try:
                child.start()
                start.set()
                self.assertTrue(parent.poll(20))
                self.assertEqual(parent.recv()[0], "consumed")
                child.terminate()
                child.join(10)
                self.assertFalse(child.is_alive())
                self.assertEqual(JsonRunStore(path).load().status, "revalidating_approval")
                r = make_runner(store=JsonRunStore(path), client=SequenceClient(count=1))
                result = asyncio.run(r.run(resume=True))
                self.assertEqual(result.reason, "approval_revalidation_interrupted")
                self.assertEqual((r._client.calls, r.policy.contexts), ([], []))
            finally:
                if child.is_alive(): child.terminate()
                child.join(5)
                parent.close()
                child_end.close()
