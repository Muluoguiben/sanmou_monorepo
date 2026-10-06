# H10b independent review

Verdict: **APPROVE CI wiring and independently executed Linux gates; native pending**.
No source/wiring finding remains. This is not a Hosted Windows pass declaration.

Approved code `e062adb7dd45d10bb579165a56f1c0d3ccf901d1`, tree
`2892d9525642bc4e279c1b2f0835f0f7b5913fa1`; frozen contract `c8b096e` and published
baseline `a45949233dfc666b91fdbf756b8666d96d93fde3`.
Independent plan was committed before author-code inspection at
`3f6ce8745f1e762345760947b506b679831bbaee`.

## Scope / actual module selection

The only implementation change is the specified three-line Windows step after H07
and before H09: `Windows H10b causal trace v2`, cwd
`packages/pioneer-agent/tests`, command
`python -W error::RuntimeWarning -m unittest test_causal_trace -v`.
Removing this unique step restores both the complete YAML object and original bytes.
All prior steps/dependencies/permissions/runner/timeouts/LF settings remain intact;
no new install or error-suppression path was added.

Packages tree remains `3d1c4a78faf912f522be764454762601aa1f7409`, so all production,
32 test bodies/assertions, fixtures, budgets/checkpoints/MCP/QA/common are unchanged.
The exact cwd resolves the repository test module with existing editable-package
imports. The helper defaults causal=True and passes causal_trace into TaskRunner;
the selected inventory includes actual three-window/two-sink v2 execution, file
recovery, error/cancel/budget and F1-F4 cases, plus explicit v1 controls. This is not
merely a wire-schema or renamed default-v1 test step.

File tests use TemporaryDirectory for checkpoints; existing LocalLock's Windows
backend rejects UNC and non-fixed drives via GetDriveTypeW, as well as parent
aliases. Hosted native success must exercise these tests on local fixed-disk temp
storage. No UNC checkpoint support is claimed, and no local native probe/install
or mocked dependency workaround was performed.

## Independent results / author cross-check

Fixed LF source `/tmp/h10b-cr-e062adb-20261006`; all seven commands exit 0:

- Causal32 with the exact warning flags: 32 pass, zero skip, no RuntimeWarning or
  unawaited-coroutine text. All 32 emitted test names match the AST inventory.
- H07a: 35 pass. Pioneer: 1085 total, 1083 pass plus two old Windows-only skips.
- QA: 394 pass; common: 2 pass.
- Actual H09 CLI: source-bound, eight controls, two goals, six expected stops and
  zero infra/safety/unexpected-goal errors.
- Frozen QA-v3 SHA256 unchanged:
  `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8`.

Only this slice's seven raw logs plus source/command summary are retained in
`h10b-independent-e062adb/`; full CLI JSON stays at recorded fresh /tmp paths/hash.
No old H10 probe study or matrix was repeated/copied. Prior red histories are untouched.

Report-only author handoff `3b31752ecd5c566c8e995c14834c6b736d71f776` has the same
packages tree and .github tree `29fca0bedd0ea3cefdd1b88c033b8b9a4dd9516a` as the code.
Read-only audit verified its seven raw Git blobs, actual counts/exits/skips, verifier
hash, warning-free 32-name inventory, H09 source/stable result and exact QA-v3 bytes
against independent output. Audit exited 0; author summary SHA256 is
`a44674b7a9e43eb19f0616cef014bb95448b83987409b8b1ac9ef37bd1786bb0`.
Audit result is `h10b-handoff-audit.json`. Counts overlap and are not additive.

## Remaining native gate / boundaries

The coordinator must verify the exact combined tree, publish the authorized single
candidate and inspect that exact SHA's Hosted Windows run/job/new-step raw logs:
all 32 actual method names pass, zero skip/error/failure, no runtime/coroutine
warning, step exit 0 and all four jobs green. Split-line ok after asyncio diagnostics
must be parsed correctly. A green label, bare test total, warning flag alone or old
H07 Windows35 cannot close this gate. **Native remains pending at this review.**

No Q06/archive body/member/credentials/.env/provider/game/bridge/deployment/main WIP
access or push/merge was performed. Existing native dependency limitations were not
reopened. Keep recommendation-only, none/false and --execute disabled. Even later
native success proves this synthetic scope only, not complete H10 or production.
