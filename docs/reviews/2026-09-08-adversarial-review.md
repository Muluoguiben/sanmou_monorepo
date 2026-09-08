# Unified adversarial review — 2026-09-08

Status: **WAITING FOR COMPONENT DELIVERIES**. No formal verdict yet. This preparation checklist is not an approval or a completed review. The final patch verdict must be APPROVE or REQUEST CHANGES after all six immutable final SHAs and committed self-test reports are received and independently checked.

## Scope and immutable inputs

- Reviewer worktree: `C:/Users/Lan/.codex/worktrees/6737/sanmou_monorepo`.
- Review branch: `feat/adversarial-review-20260908`; initially clean detached HEAD, then branch created at the frozen baseline.
- Frozen baseline commit: `d377ef8bbaa69e6b25928255eac0cb62714e82f8`.
- Frozen baseline Git tree: `5a7239bcc64689789d7cd7a6b148937ea3184760`.
- Remote: `git@github.com:Muluoguiben/sanmou_monorepo.git`.
- Coordinator task: `019f4a66-e105-7103-ab9d-aef47aa6f8a0`.
- Frozen report: `C:/Users/Lan/.codex/visualizations/2026/07/10/019f4a66-e105-7103-ab9d-aef47aa6f8a0/sanmou-review-20260908.md`, SHA256 `aefac34f2a7811406e33c3ffae60c80a2a3878094c1c7c4f0cc0be862ec628cf`.
- Coordinator report copy: `docs/reviews/sanmou-review-20260908.md`, SHA256 `daa1f4d97f77fd38d1c9c5c43741256b436c3fff9f28f1312589996cea25a249`. Independently diffed: only its final blank line differs from the frozen original.
- Coordinator charter: `docs/development-batch-2026-09-08.md`, SHA256 `d5725ef65ecdcd97b6430b41a0b474be233cd8aa84d462cb07a9dba7cd92a6e8`, read from the coordinator worktree without mutation.
- Observed coordinator `master` / `origin/master`: `dd76d601f6f40d3e4fceaf10cdd360d78af88cb2`; this is not the patch baseline. Reviewer must not merge or push master.
- Combined commit/tree: pending. Only explicitly delivered final component SHAs may be combined; never infer a final SHA from a moving branch head.

## Intake gate

| Owner | Task ID | Final component SHA | Committed test report | Intake status |
|---|---|---|---|---|
| A | 01a07f09-c64c-7852-a533-7db7730a048c | pending | `docs/test-reports/2026-09-08/A.md` | waiting |
| B | 01a07f0b-149e-7160-a896-551165a702a0 | pending | `docs/test-reports/2026-09-08/B.md` | waiting |
| C | 01a07f0b-3787-7f82-ab0c-400a65b4b1a2 | pending | `docs/test-reports/2026-09-08/C.md` | waiting |
| D | 01a07f0b-53b8-74a3-9e61-71dd461bdff8 | pending | `docs/test-reports/2026-09-08/D.md` | waiting |
| E | 01a07f0b-6d25-75c3-bcb1-acd4ca26cd1d | pending | `docs/test-reports/2026-09-08/E.md` | waiting |
| F | 01a07f0b-85e8-7880-bb8f-3845dc01fef2 | pending | `docs/test-reports/2026-09-08/F.md` | waiting |

For each delivery independently verify: SHA exists and is immutable; ancestry and owned diff are correct; report exists in that commit; tested code/tree is identified without a self-referential report SHA; exact commands, runtime/dependency versions, exit codes, counts and skips match reproducible output; no deleted regression, weakened assertion or expectation changes conceal the original failure. Author statements are inputs to audit, not proof. Replacement SHAs invalidate the affected review results.

## R01–R26 adversarial checklist

Every row starts **PENDING**; reproduction descriptions below are planned checks, not claims of execution.

| ID | Priority / owner | Original trigger and independent negative checks | Required corrected behavior | Disposition |
|---|---|---|---|---|
| R01 | P1 / A | Trace controller install/Highest task and user-writable command paths; inspect every documented entry. Never install or execute the old controller. | Old unsafe installation/control entry fails closed and is no longer recommended; no substitute user-writable elevated trust root. | PENDING |
| R02 | P1 / A | Fake server requests without authentication/window/confirmation; inspect defaults and all click/key input routes. | Loopback default, identity validation, read-only mode rejects all input, no reachable legacy bypass. | PENDING |
| R03 | P1 / E | Missing `py`, invalid `PYTHON`, later valid candidate, all candidates failing. | ENOENT/null output handled; fallback works and startup failure remains visible in a created window. | PENDING |
| R04 | P1 / D | Synthetic/heuristic video extraction through staging and default publisher; forged or absent review provenance. | Machine-generated content remains pending; no automatic human-review claim or publishable artifact. | PENDING |
| R05 | P2 / B | Actual RuntimeState/perception map, battle, timer, progress, risk, unknown/trust payloads; inject nested paths, metadata and oversized content. | Explicit public domain structure preserves necessary facts/risk/unknowns and strips private data; end-to-end MCP parity. | PENDING |
| R06 | P2 / A | Fresh-process import graph for game MCP/fixture/live observation; minimized-window fake capture. | No restore/focus/input side effects, no transitive control/executor/verifier loading through read-only paths. | PENDING |
| R07 | P2 / A | Timeout before header, mid-header/body, delayed previous response, mismatched request ID and capture time. | Broken stream discarded; responses bind request and server capture time; old bytes cannot become fresh frames. | PENDING |
| R08 | P2 / B | Full team A/B/C then A/B/D, empty/full/partial panel and detail updates; inspect dependent readiness evidence. | Complete roster replaces removed heroes; retain detail only for remaining members and invalidate dependent stale facts. | PENDING |
| R09 | P2 / D | Empty retrieval with hallucinating fake LLM; fabricated/missing/mixed citations on nonempty retrieval. | Fixed empty-evidence answer without generation; returned citations constrained to current evidence. | PENDING |
| R10 | P2 / D | Move same canonical ID across faction/skill bucket, stale duplicate load, partial-write failure; inspect existing duplicate. | Whole-library unique ID migration; no stale result or silent overwrite; duplicate loader failure is explicit. | PENDING |
| R11 | P2 / D | Partial/missing base/growth, explicit zero, disjoint known attributes. | Compute each attribute only when both inputs are known; unknown remains None. | PENDING |
| R12 | P2 / D | Whitespace-only/empty/mixed facts and query first answer. | Normalize before nonempty validation; invalid entries rejected without query crash. | PENDING |
| R13 | P2 / F | Normal click followed by later ambiguous burst; partial/split/interleaved segment coverage. | Every pair checked; ambiguous burst complete and separate, trace-only/excluded and never counted as negative. | PENDING |
| R14 | P2 / F | Change evaluator-consumed fixture bytes while preserving expected action; swapped second read and ordering. | Run digest binds exact executed input bytes by name/hash; no reread race or action-only identity claim. | PENDING |
| R15 | P2 / F | Mark all transcript calls failed with plausible payload, mixed successes, successful transport with rejected semantics. | Failed calls supply no trusted observation/candidates/refresh or unjustified perfect scores. | PENDING |
| R16 | P2 / F | Valid pre-failure refresh, append later recovery, future/misaligned timestamps. | Failure and final checkpoints use their own valid history; later recovery does not erase prior checks, future facts rejected. | PENDING |
| R17 | P2 / C | Two real-domain observations 121 seconds apart, no invented `timing` domain; irrelevant page/missing timing. | Timer checkpoints follow actual trusted evidence and applicability; normal fresh loop continues, unsupported evidence cannot refresh. | PENDING |
| R18 | P2 / C | Persist journal then restart empty MCP cache; actual different window, first observation absent/failing. | Unknown identity distinguished from changed identity; verify fresh observation against journal before recommendation. | PENDING |
| R19 | P2 / C | Advance controlled clock 300 seconds during QA or candidates; identity/frame/domain binding changes. | Final recommendation revalidates freshness and identity; stale or mismatched facts stop and request refresh. | PENDING |
| R20 | P2 / C | Bounded fake stdio process hangs in initialization/call; disconnect/cancellation and cleanup. | Finite deadlines, structured failed tool record and stop, process/session cleanup, no infinite wait. | PENDING |
| R21 | P2 / E | Inspect built preload then launch real Electron on isolated mock API/custom port; error bridge availability. | Runtime preload loads, `window.sanmou` works, URL/port/errors preserved. Build alone is insufficient. | PENDING |
| R22 | P2 / E | Analyze A, select B/history, resolve/reject A late; overlap multiple requests and chat. | Stale request cannot overwrite current report/error/busy/chat identity. | PENDING |
| R23 | P2 / E | Full trusted confidence=1 with advisor_mode; unknown/untrusted/zero-confidence evidence with/without recommendation. | Execution permission and evidence quality displayed independently; unknown cannot appear sufficient. | PENDING |
| R24 | P2 / E | Native Windows >10MB upload and interrupted/error paths with realistic file locking. | Handle closes before removal; returns 413, no file residue; API tests run with FastAPI installed. | PENDING |
| R25 | P2 / D | Public alias to excluded cache, file/parent links, hardlink, replacement race and path escape using synthetic markers. | No private bytes emitted; actual opened file identity/root/exclusion validated, unsafe paths fail closed. | PENDING |
| R26 | P2 / D | Windows, UNC, mixed/Posix separators on Windows and Linux through all sanitized exports. | Only safe basename emitted; no machine/private path leakage. | PENDING |

## Dependency and combination review

| Producer / consumer | Contract boundary | Combination checks |
|---|---|---|
| A → B/C | Request/frame/capture timestamp, geometry, identity, no-side-effect capture | Stale/unbound observations never become fresh public state or valid harness recommendations. |
| B → C/F | Canonical seven-tool payload schema and privacy projection | Domain/trust/risk/timer fields survive while private inputs stay hidden; consumers do not copy a second schema. |
| B merge → C | Full versus partial roster and freshness | Removed heroes and stale readiness do not survive into recommendations. |
| D → C/E | Six QA tools, citation and knowledge review boundary | Empty/unreviewed knowledge cannot ground a harness or desktop recommendation. |
| E → F | API/Windows/desktop regression commands and dependencies | CI installs FastAPI, executes meaningful Windows regressions and actual desktop bridge checks where required. |
| F → all | CI, transcript trust, fixture digest, R&R boundaries | Independent runner uses identical tested tree; synthetic/replay/static proof is not promoted to live/vision accuracy. |

Order components only after intake; inspect ancestry first to avoid double-applying prerequisite commits. Use explicit final SHAs on this isolated branch. Mechanical or semantic conflicts are returned to owners; reviewer must not invent a production conflict resolution. Record ordered component SHAs and the combined commit/tree before running final regressions.

## Independent validation ledger

| Check | Command / evidence | Result |
|---|---|---|
| Worktree/base | `Get-Location`, `git status --short --branch`, `git rev-parse HEAD` | Initial clean detached baseline verified. |
| Baseline tree | `git rev-parse 'HEAD^{tree}'` | `5a7239bcc64689789d7cd7a6b148937ea3184760`. Unquoted PowerShell brace syntax first failed; quoted command is authoritative. |
| Report provenance | `Get-FileHash -Algorithm SHA256`; `git diff --no-index` original/copy | Hashes above; only trailing blank line differs. |
| Local isolation | `git switch -c feat/adversarial-review-20260908` | Exit 0, created at frozen baseline; no other checkout changed. |
| Required skills/rules | Root AGENTS, coordinator charter, code-review/security-review/caveman-review | Read; explicit single-reviewer instruction overrides skill delegation. |
| Full Python regressions | Native unittest commands, real output files and exit codes on combined tree | NOT RUN; historical 775/307/2 counts are not current evidence. |
| Official MCP transport | Official `ClientSession` + `stdio_client`, game seven tools and QA six tools, strict invalid arguments, fixture/error parity | NOT RUN; direct handlers do not substitute for stdio. |
| Desktop | Typecheck, build, native Electron preload/custom-port smoke, concurrency/evidence regressions | NOT RUN. |
| Windows API/upload/capture | Native Windows synthetic tests, FastAPI installed; no game operation | NOT RUN. |
| Read-only boundary | Fresh-process transitive imports plus offline side-effect instrumentation | NOT RUN. |

Tool environment: ordinary shell and Node sandbox initialization failed with `helper_unknown_error: setup refresh had errors`. Automatically approved scoped `require_escalated` shell commands worked. This is an execution-environment limitation, not a passing or failing source-code result.

## Evidence limits and final decision

Patch verdict: **PENDING — no APPROVE issued**. Production readiness: **NOT ESTABLISHED** independently of any future patch approval.

No game input, old Highest controller execution, unauthenticated bridge dispatch, privileged task installation, raw private screenshot collection/publication, external holdout oracle access, global auth edits or master mutation is permitted in this review. Live validation belongs to the coordinator's explicitly scheduled safe window.

Missing representative provider-exercised image accuracy/refusal/latency/cost evidence, independent holdout operation, signed clean-machine install/update/rollback, operational privacy/retention, reviewed human R&R provenance and action-specific live closure remain separate production gates. Do not turn missing evidence into success or a new code finding without a reproducible defect.
