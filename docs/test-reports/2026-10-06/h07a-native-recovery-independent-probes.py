"""Frozen offline boundary and anti-vacuity checks; production files untouched."""
import json
import multiprocessing.process
import unittest
from unittest.mock import patch

import test_task_approval as tests
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.agent_harness.task_runner import TaskRunner


DISK = "ApprovalDiskRecoveryTests."
PROCESS = "ApprovalProcessTests."
NAMES = [
    DISK + "test_json_waiting_new_reader_preserves_watermark_deadline_and_reservations",
    DISK + "test_json_waiting_fresh_runner_clock_rollback_stops_without_calls",
    DISK + "test_json_waiting_fresh_runner_expired_deadline_stops_without_calls",
    PROCESS + "test_actual_process_crash_after_revalidated_fresh_runner_reobserves_and_keeps_charges",
    PROCESS + "test_actual_process_crash_after_revalidated_replayed_observation_never_reaches_policy",
]


def suite(names):
    return unittest.defaultTestLoader.loadTestsFromNames(names, tests)


def main():
    events = []
    start = multiprocessing.process.BaseProcess.start
    join = multiprocessing.process.BaseProcess.join
    def observed_start(process):
        start(process)
        events.append({"event": "spawn", "pid": process.pid, "method": process._start_method})
    def observed_join(process, timeout=None):
        join(process, timeout)
        events.append({"event": "join", "pid": process.pid, "exitcode": process.exitcode,
                       "alive": process.is_alive()})
    with patch.object(multiprocessing.process.BaseProcess, "start", observed_start), \
            patch.object(multiprocessing.process.BaseProcess, "join", observed_join):
        actual = unittest.TextTestRunner(verbosity=2).run(suite(NAMES))
    assert actual.testsRun == 5 and actual.wasSuccessful() and not actual.skipped
    spawned = {event["pid"] for event in events if event["event"] == "spawn"}
    assert len(spawned) == 2
    assert all(any(event["event"] == "join" and event["pid"] == pid
                   and event["exitcode"] not in (None, 0) and not event["alive"]
                   for event in events) for pid in spawned)

    # Mutations affect this validation process only. Spawn children import pristine source.
    restore = RunBudgetLedger.restore
    def refund_reservations(ledger, snapshot):
        restore(ledger, snapshot)
        ledger._reservations.clear()
    with patch.object(RunBudgetLedger, "restore", refund_reservations):
        refund = unittest.TextTestRunner(verbosity=2).run(suite([NAMES[0]]))
    assert refund.testsRun == 1 and len(refund.failures) == 1 and not refund.errors

    step = TaskRunner._step
    async def skip_fresh_observation(runner):
        approval = getattr(runner.state, "approval", None)
        if approval is not None and approval.revalidated_observation_id is not None:
            return runner._finish("succeeded", "goal_verified")
        return await step(runner)
    with patch.object(TaskRunner, "_step", skip_fresh_observation):
        bypass = unittest.TextTestRunner(verbosity=2).run(suite([NAMES[3]]))
    assert bypass.testsRun == 1 and len(bypass.failures) == 1 and not bypass.errors
    print(json.dumps({"new_boundaries_passed": 5, "skips": 0, "spawn_events": events,
        "negative_controls": {"refund_reservations": "detected_by_unchanged_new_assertion",
                              "skip_fresh_observation": "detected_by_unchanged_new_assertion"},
        "native": False, "live_transport": False, "provider_calls": 0}, indent=2))


if __name__ == "__main__":
    main()
