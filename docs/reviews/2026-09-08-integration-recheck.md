# Coordinator integration recheck — 2026-09-08

Status: integration paused; additional stdio failure sent to owner C and the
same unified adversarial reviewer. No development source was merged/pushed to
master. Earlier APPROVE is historical, not a waiver of this reproducible failure.

## Source and environment

- Clean pre-integration master: 0b21b4162ba41ee2e72bd1c809d80f40ee6eafaa.
- Candidate reviewed commit: 470d92cdc6831f6c9bec4ce99050ccf6056b033c.
- Reviewed code commit: 7f59f00778594accc49fd02a828a08097832c27c.
- Report-only final commit did not change packages/apps/.github/.agent/scripts.
- Preview merge had only a TODO append conflict, resolved retaining both sides.
  Those source areas compared equal to 470d92c after conflict resolution.
- Tests used the main ext4 worktree, not the reviewer's /mnt/c worktree:
  /home/lan/projects/sanmou_monorepo/packages/pioneer-agent.
- Python: /tmp/sanmou-cr-20260908-venv/bin/python (reviewer's isolated environment),
  PYTHONNOUSERSITE=1, PYTHONDONTWRITEBYTECODE=1 and -B.
- PYTHONPATH=src:../sanmou-common/src:../qa-agent/src; focused runs append tests/unit.

## Actual results

Native command: python -B -m unittest discover -s tests -p 'test_*.py' -v.
Result: exit 1, 846 tests in 28.592s, 2 errors and 2 Windows-only skips.
QA/common were not run because this sequential first package failed.

Failing original tests:

- test_silent_tool_call_closes_nested_client_and_is_not_reused
- test_silent_tool_failure_is_persisted_by_harness

Exception escapes during __aenter__ cleanup: _close -> _serve ->
AsyncExitStack.aclose -> MCP stdio stdout_reader -> AnyIO memory stream send,
raising BrokenResourceError inside ExceptionGroup. This is not the earlier
Electron Python-probe deadline or a StringIO/subprocess-wrapper artifact.

The same tests ran unchanged in three fresh processes. All three returned
exit 1 / 2 errors (0.402s, 0.431s, 0.392s). No timeout/expectation/source changed.
An initial diagnostic shell had an EOF syntax error and did not execute tests;
it is not counted as a code failure.

Local original logs:

- /tmp/sanmou-root-integration-pioneer-20260908.log
- /tmp/sanmou-root-integration-stdio-focused-1.log
- /tmp/sanmou-root-integration-stdio-focused-2.log
- /tmp/sanmou-root-integration-stdio-focused-3.log

## Recovery and next gate

git merge --abort restored the originally clean master checkout after the bounded
checks. No user WIP existed before this integration attempt; no user files were
discarded. C investigates on isolated sources. Unified CR must independently
reproduce/classify and review any replacement SHA before a new integration.
Deadlines and cleanup exceptions must not be hidden by retries, relaxed timeouts
or broad exception suppression.

No game/model/real credential/holdout operation occurred. Production readiness
remains unestablished independently of this patch-batch gate.

## Candidate follow-up (not coordinator acceptance)

Unified CR reproduced CR08 with controlled real-SDK streams and real child
processes; its 20 rounds of the old native pair passed, so ext4 alone is not a
proven cause. Those results and the root failures are both preserved.

C delivered 6bdb0276fd24c3eec7f72d838902085d59dd7c32, replacing eb4ecd90. Its report
binds the new stdio implementation and 11 regressions to exact blobs, with
author-run 857-test combined evidence and the original reviewer probes. This
is author evidence; root has not repeated integration on the candidate and
unified review remains reopened until independently revalidated.
