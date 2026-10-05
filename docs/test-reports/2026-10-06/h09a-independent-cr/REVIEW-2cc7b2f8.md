# H09a re-review: REQUEST CHANGES

Exact code: `2cc7b2f885b3d33b46c719b89fb3c85d2ade2e96`.
Exact tree: `73309b5d5bf61b0c02765eb833e1c308bd04eec0`.
Date: 2026-10-06. This supplements, never replaces, the original frozen plan,
134d73b0 findings and original failures at review commit 2bcd73e.

## Original fixes verified

- CR01: copied/unbound CLI now yields source_verified=false/gate_pass=false/exit2;
  ordinary module and direct committed-file CLI modes both bind their real entry.
- CR02: expected tool-label changes no longer erase actual verified goal success;
  control mismatch still fails. Infra runs do not count as valid goal successes.
- CR03 original phase-write boundary: failed phase writes now retain actual state,
  bottom-level calls, policy and trace in the final failed report.

Unchanged first-round probes: 16 passed, 0 failed, 0 skipped. One check still
validates retained 64adbfbb formal reports and is not new 2cc source evidence.
The other checks execute the new source. No original assertions were weakened.

## Remaining blockers

### CR03b [P2] Artifact hash-read failure still discards the whole report

`packages/pioneer-agent/src/pioneer_agent/agent_harness/task_eval.py:302-303` hashes
artifacts outside the failure-reporting guard. Inject an OSError only for reading
`phase-1.json` during this final hash pass: all eight actual cases have completed,
but evaluate raises and no report.json is saved, although report.json remains
writable. Complete actual results, including in-memory policy/call evidence, are
not delivered in a failed report. This is not the unavoidable final-report-write
failure boundary; only one other artifact cannot be read.

Fix: retain every case result and record artifact-enumeration/hash failures in the
failed report, with incomplete/unavailable digest explicitly marked; force gate
false. Do not silently drop the unreadable artifact from a green manifest.

### CR04 [P2] Projection exception leaves a contradictory green report

`packages/pioneer-agent/src/pioneer_agent/agent_harness/task_eval.py:296-301` sets
complete/gate_pass before stable_projection. Its exception handler appends infra
errors but does not revoke gate success. With the real committed module executed
as __main__ using standard runpy (not an unbound library diagnostic), inject one
ValueError from stable_projection. The CLI exits 2 yet writes:
`source_verified=true`, `complete=true`, `gate_pass=true`, and nonempty infra_errors.
Downstream report consumers can accept the explicit true gate despite failure.

Fix: publish positive completion/gate only after all required finalization succeeds;
on any failure clear gate (and incomplete required-output status) before writing.
An exit code does not repair a contradictory persisted gate.

The first library-mode projection probe passed because library mode is never
green. That original output is retained, not presented as proof of committed-CLI
safety. The separate committed-entry probe reproduces the defect and is also
retained. Both fault boundaries were independently reproduced after static review
and coordinator cross-check; neither claim relies on the coordinator's assertion.

## Verification matrix

| Check | Result |
| --- | --- |
| Dual fresh committed `-m` CLI | 2/2 goals, 6/6 safety, 8/8 controls each |
| Direct committed CLI | Same passing totals; direct_script launcher bound |
| Three stable projections and artifact byte hashes | All equal/verified |
| Actual loaded-module exact file/spec/package mapping | 87 modules for each `-m`, 86 direct; all map exactly |
| Related `test_task*.py` | 60 passed, 0 failed, 0 skipped |
| Original frozen independent probes | 16 passed (one historical-64 comparison) |
| Library-mode finalization probes | 1 passed, 1 failed (CR03b) |
| Committed-entry finalization probe | 1 failed (CR04) |
| Real source byte drift CLI | Exit2, no cases, source/gate/complete false |
| Real untracked source CLI | Exit2, no cases, source/gate/complete false |
| Protected source objects | All 831 unchanged |

Source negatives ran on separate detached worktrees `/tmp/h09a-cr-2cc-byte-drift`
and `/tmp/h09a-cr-2cc-untracked`; only those deliberate negative copies were
mutated. The clean review worktree `/tmp/h09a-cr-2cc7b2f8-20261006` stayed clean.
Windows apply_patch initially rejected the UNC reparse path; explicit scoped
approval then ran the same apply_patch implementation successfully on verified
negative-only roots. No rejected policy was bypassed.

Specific source diagnostic reasons were independently checked:
`source_byte_drift:.../_task_eval_inputs.py` and
`untracked_source:.../independent_untracked_probe.py`.
No ordinary trusted-loader same-root/wrong-module-name counterexample was found;
arbitrary hostile sys.modules mutation is outside this stated threat model and
is not reported as a new defect. Clean-run exact module identities were verified
independently rather than inferred from root containment.

## Reproduction and evidence

All processes use Python 3.12.3 on Ubuntu WSL ext4, existing dependencies only:
`PYTHONPATH=/tmp/h09a-cr-2cc7b2f8-20261006/packages/pioneer-agent/src:/tmp/h09a-cr-2cc7b2f8-20261006/packages/sanmou-common/src:/tmp/sanmou-cr-20261005-6155-deps`;
`PYTHONDONTWRITEBYTECODE=1`. Source-negative child processes substitute their own
absolute negative snapshot source paths, never the clean source path.

```sh
python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr-2cc7b2f8-eval1
python3 -B -m pioneer_agent.app.task_eval --output /tmp/h09a-cr-2cc7b2f8-eval2
python3 -B packages/pioneer-agent/src/pioneer_agent/app/task_eval.py --output /tmp/h09a-cr-2cc7b2f8-direct
# From clean snapshot packages/pioneer-agent:
python3 -B -m unittest discover -s tests -p 'test_task*.py' -v
# REVIEW is the absolute review-report directory:
python3 -B "$REVIEW/replay_2cc.py"
python3 -B "$REVIEW/finalization_probes_2cc.py"
python3 -B "$REVIEW/committed_finalization_2cc.py"
python3 -B "$REVIEW/source_report_checks_2cc.py"
python3 -B "$REVIEW/source_negative_checks_2cc.py"
```

Complete new outputs/logs are in `evidence-2cc7b2f8.tar.gz`, with archive hash and
per-member byte hashes/types in `evidence-2cc7b2f8-typed-inventory.json`.
No prior evidence was rewritten. Critical original red logs:
`/tmp/h09a-cr-2cc7b2f8-finalization-first.log` and
`/tmp/h09a-cr-2cc7b2f8-committed-finalization-first.log`.

## Evidence-type correction and safe inspection

The prior original-evidence.tar.gz contains **403 regular files, 2 symlinks and
136 directories**, not 405 regular files. Its original 405-path digest manifest
followed two `byte-input/linked.json` negative-test symlinks to their original
absolute `/tmp/.../byte-input/input.json` targets. The original tar and manifest
remain unchanged. `original-evidence-typed-inventory.json` now records those
linknames explicitly and hashes regular archive-member bytes without extraction.

For either evidence archive: inspect regular tar members and verify typed inventory;
do not extract wholesale and do not follow archived absolute symlinks. These links
are intentionally retained path-rejection test artifacts, not trusted source or
normal report inputs. Directory/member counts and link metadata are part of the
evidence boundary. Runtime temporary directories are preserved separately.

No provider, .env, network, real MCP, game action, dependency installation,
CI retry, master change or push occurred. Complete author self-test handoff was
not yet available; no approval is issued while these reproducible blockers remain.
H06 hosted Windows acceptance is still separate and incomplete.
