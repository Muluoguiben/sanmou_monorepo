# Sanmou hardening batch — 2026-09-08

Six GPT-6 Astra development tasks in isolated worktrees, followed by one unified
adversarial code reviewer. Review baseline: d377ef8bbaa69e6b25928255eac0cb62714e82f8.
R01–R26 refer to the numbered findings in reviews/sanmou-review-20260908.md.

| ID | Ownership | Findings |
|---|---|---|
| A | Observer/controller security, capture and bridge transport | R01/R02/R06/R07 |
| B | Public MCP payloads/projection and entity snapshot merging | R05/R08 |
| C | Recommendation harness lifecycle, timeouts and freshness | R17/R18/R19/R20 |
| D | QA ingestion, publishing gates, chat and knowledge integrity | R04/R09/R10/R11/R12/R25/R26 |
| E | Desktop, Advisor API and Windows packaging foundation | R03/R21/R22/R23/R24 |
| F | Eval/R&R correctness and automated CI regression gates | R13/R14/R15/R16 |
| CR | Unified adversarial review of component and combined SHAs | All |

## Shared boundaries

- Each task works only in its own worktree and pushes its feature branch. No
  developer or reviewer pushes/merges master. Coordinator owns final integration.
- Preserve sanmou-game/v1 seven tools, QA six tools, execution_authority=none,
  executable=false, disabled normal --execute and disabled live replay.
- A owns capture/bridge protocol. B owns public payload types. C/F consume the
  canonical catalog; coordinate changes instead of duplicating contracts.
- F owns CI. E supplies desktop/API commands. Use isolated dependencies, temp
  files and ports, not shared .env/auth or global installations.
- No decoded research expansion or automatic knowledge/privacy approval.

## Client authorization

User reports the game client is running in the game screen, permits elevated
control and operations, and requests notification when actual control is needed.
This is not permission to reuse the known-P1 user-writable Highest controller,
unauthenticated network input, or to bypass security guards. No risky control
prototype, privileged task registration, automatic login or account changes.

Only the coordinator assigns a live observation/control window; never let six
tasks compete for the game. For a state-changing action, request the exact target,
action, quantity/resource effect and safe entry before dispatch. Preserve all
action-bound confirmations and freshness/window/verifier checks. If no safe
entry exists, report the live blocker and continue offline work. This batch does
not enable routine execution, deploy a broker or release a production build.

Real screenshots remain local/private by default. Use one compressed preview
and SHA-bound facts. Do not commit raw screenshots, credentials or account/chat
details; do not upload private images to external models without approval.

## Mandatory self-test and delivery

Each developer commits docs/test-reports/2026-09-08/ID.md containing:

1. Worktree/branch/start SHA, owned changed files, addressed findings.
2. Reproduction and regression proof for each finding, including negative cases.
3. Exact commands, environment/dependency versions, exit codes, pass/fail/skip
   counts, concise output and remaining compatibility limitations.
4. Focused and package tests; E also runs typecheck/build, Windows regressions
   and API tests with FastAPI installed in an isolated environment.
5. Whether evidence is synthetic, replayed, approved real, provider-exercised or
   live. Missing/skipped evidence must never be described as verified success.
6. Accurate tested-tree identity. Final reply supplies immutable final commit
   SHA/URL and report path; do not invent a self-referential report SHA.

Use native test commands or actual log files, not replacement stderr streams
which invalidate subprocess fileno/logging assertions. Stage only owned changes.
Each feature push updates its own task-local TODO section; coordinator reconciles
the main TODO. Missing tests/report or failed push means incomplete delivery.

## Unified adversarial review gate

CR waits for six final SHAs and self-test reports before formal review. It checks
each diff/report independently, reruns adversarial reproductions and verifies
the combined tree in its own worktree without touching master. It records exact
component SHAs and combined SHA, per-finding disposition, commands/results and
unverified boundaries in docs/reviews/2026-09-08-adversarial-review.md.

Findings are sent back to the responsible existing development task; replacement
SHAs require renewed review. CR must not implement production fixes and approve
its own changes. Result is APPROVE or REQUEST CHANGES, not an unsupported
production certificate. No master integration or release before review passes.

## Remaining production evidence

Representative provider-exercised image accuracy/refusal/latency/cost eval,
independent holdout operation, signed clean-machine install/update/rollback,
operational privacy/retention, reviewed R&R human provenance and any future
action-specific live closure remain separately tracked. Unsigned packaging,
static regression or replay success cannot satisfy those gates.
