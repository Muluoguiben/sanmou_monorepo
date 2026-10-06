# H10b independent plan (before author-code inspection)

Frozen contract `c8b096edc5fce6c87e83198b871ab5c576add1db`, tree
`54c54a47c77c6a0a0368611e2dc5349c6ff941a7`; published baseline
`a45949233dfc666b91fdbf756b8666d96d93fde3`.
Review branch `codex/h10b-native-causal-trace-cr-20261006`, initially clean.
AGENTS.md, code-review skill and the whole contract were read. Baseline workflow,
test module selection and existing local-fixed-disk checkpoint guard were inspected.
The author's fixed commit id was received but its implementation has not been read.

## Small-slice acceptance

1. Only one Windows workflow step may be added: name `Windows H10b causal trace v2`,
   cwd `packages/pioneer-agent/tests`, command
   `python -W error::RuntimeWarning -m unittest test_causal_trace -v`.
   Remove that step and compare the whole workflow structure and original bytes;
   preserve every old step, job, permission, dependency, runner, timeout and LF setting.
   Packages tree and all 32 existing test methods/assertions/fixtures must be unchanged.
2. Confirm the exact cwd/command imports the repository's complete causal module,
   not a subset or default-only stand-in. Verify the 32-method inventory includes
   actual TaskRunner causal_trace opt-in, three observations/two sinks, file recovery,
   errors/cancellation, budgets and F1-F4 controls. Existing dependency installation
   and failure propagation stay intact; no continue-on-error or warning/skip bypass.
3. Native checkpoint paths must be local fixed-disk temporaries. The existing
   JsonRunStore/LocalLock path already rejects UNC/non-fixed Windows checkpoints;
   inspect that path and the actual file-based tests. Do not confuse UNC source
   reading with UNC checkpoint support or install/probe new local native dependencies.
4. On fixed source, independently run the exact causal command on existing Linux,
   H07a35, full Pioneer/QA/common, actual H09 CLI and frozen QA-v3. Record code SHA/tree,
   argv/cwd/exit/count/skip and bounded plain raw hashes. No repeat H10a probe research
   or copying prior matrices. Cross-check the author's fixed report, not WIP.
5. A local code/wiring APPROVE must explicitly say **native pending**. Final native
   acceptance requires the published exact SHA's Hosted Windows run/job/step raw
   logs: all 32 expected method names actually pass, zero skips/errors/failures and
   no RuntimeWarning/unawaited-coroutine warning; step exit 0 and all four old jobs
   green. Recognize unittest's split-line ok after asyncio diagnostics; do not infer
   success from the step label, a bare count or the old H07 Windows35. Warning-as-error
   alone is not proof that no destructor coroutine warning was printed.

Any real native failure is preserved before proposing a minimal fix; old assertions
cannot be removed, skipped, mocked or renamed merely for green. Coordinator owns
exact combined-tree verification, authorized publication and final hosted evidence.

## Boundaries

Reviewer makes no author implementation/main/push changes. Preserve old refs and
the main checkout's three WIP files. No Q06 payload/ancestry or archive body/member
reads, credentials/.env, provider/game/bridge, deployment or dependency installation.
Do not reopen the known pywintypes/rpds local environment limitation. New evidence
is this slice's bounded plain text/JSON only. Keep recommendation-only, none/false
and --execute disabled; even native success is not complete H10 or production proof.

Next: commit this plan, then inspect immutable author source and its report.
