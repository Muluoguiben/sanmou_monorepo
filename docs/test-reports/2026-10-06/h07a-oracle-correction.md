# H07a reviewer oracle correction

The original frozen probe commit `339aa56156cced5fe0b8ea274695a943f5cab576`
contains one incorrect expected reason at `h07a-independent-probes.py:61`:
`stale_observation`. Published baseline `110bd7594e095c3ea0e1940ab2fc4bec5f4d7a77`
defines only `StopReason.OBSERVATION_STALE.value == "observation_stale"` in
`agent_harness/policy.py`; its original `test_task_runner.py` stale-policy assertion
also requires `observation_stale`. These exact Git source blobs were read to verify
the correction. An implementation honoring the baseline cannot pass the misspelled
original assertion, even when its behavior is correctly fail-closed.

Do not add an implementation alias or alter baseline assertions. The original file,
its hash `9c047a03ac85df4ba188025fd37225af5e6ed1d90d448d0154253834d3172d12`, and
original failure log remain unchanged. The R1 report's stale reason spelling has the
same reviewer error; this addendum corrects that expected name only.

`h07a-independent-probes-canonical.py` inherits all original tests unchanged except
the stale test. That test keeps the exact same checkpoint latency injection, changes
the expected reason to the established canonical spelling, and additionally checks
zero policy invocations using a transparent AsyncMock wrapper. The deadline and
rollback tests are inherited without any assertion relaxation.

The original observed `succeeded/goal_verified` remains a real F1 defect regardless
of reason spelling. Run both versions after the author fix: keep the original output
as historical evidence, separately report its known oracle-only mismatch, and use
the canonical variant for stale reason acceptance. Renaming this test oracle is not
a production fix and does not establish approval.
