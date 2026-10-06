# H08a independent review — APPROVE (fixed offline source / Linux)

Approved source `8e0a2a0b370a98824669e5d34bd12576c7822bb5`, tree
`55eb8c863db183e7dbd2fa9cfb6d845876162315`. No actionable finding within the frozen
H08a contract. This is not final combined/native acceptance, semantic-quality
certification, live execution permission or completion of the full H08 roadmap.

Plan d73dd03 preceded author memo/code. Public/runtime probes
`3ce5a9d9d8ad6cd1cf8f5710aa844516a12e4cca` were frozen before implementation review;
published 60e3 runtime oracles and QA hashes were actually rerun and preserved in
bd879ee. After reading fixed source, private-catalog probes
`749ea5fb6649c5b35ef289911d6d00b9e6fd22e3` were frozen before execution. The
code-review skill guided independent source inspection, counterexamples and
source-bound verification; no author-code repair or external paid consultation.

## Scope and substantive review

Read the complete new registry/test, fixed memo, workflow insertion and relevant
existing TaskSpec, condition, store, runner/policy/budget ports. The only package
changes are new skill_registry.py and test_skill_registry.py. All old runtime,
schema, DSL, budget, store, context, policy, trace, MCP, QA/common, KB, fixtures and
old test assertions are byte-identical. QA/common Git trees equal published 60e3.
906 ordinary package Python/JSON/YAML inputs match exact source Git blobs.

The registry is a pure application recipe selector/compiler, not a Codex Skill
installer. There is no registration/loading/catalog argument, dynamic import/eval,
natural-language route, default CLI wiring, file input, task run or model call.
Identity and version lookup are exact. Only target_chapter is accepted, strictly
integer 1..1000; invalid input is not disguised as a blocked valid request.

Independent controls verify the full definition canonical digest excluding only
template_digest (including none/false), full actual TaskSpec digest, deterministic
target changes, and deep isolation across list/resolve/compile nested values.
Mutating returned schemas, templates, conditions or TaskSpec lists does not affect
later results. The private duplicate control places duplicate unrequested peers
after the valid builtin and requires all three APIs to reject; it does not expose
registration. A rehashed but altered private definition is still not allowlisted:
content hash equality is not an admission/authentication mechanism.

The sole compiled TaskSpec matches every contract field exactly: opaque fixed
ID/goal formats, v1, one chapter >= target condition, chapter_panel, fixed ordered
four-tool list, max_steps=3, wait_seconds=0, stop_when=[], none/false. Neither the
global catalog nor caller arguments enlarge it. The @/: task ID also survives
real JsonRunStore persistence at an independent explicit checkpoint path.

Precheck reuses existing evaluate_all with a local chapter-only projection.
Missing/None/bool/float/string/nonfinite/container values are unknown; 0/negative
integers are false. Invalid flat values never borrow a valid nested value. Caller
metrics remain untouched. Blocked outcomes expose task=None and task_digest=None,
correct tri-state/missing-metric details, and no runtime/tool/policy calls.
Successful precheck compiles only; it cannot assert freshness or goal success.

## Independent execution

Fresh LF checkout `/tmp/h08a-cr-8e0a2a0-20261006`, existing dependency runtime only.
Actual commands, cwd/PYTHONPATH, source/tree, exit/count/skip and raw log hashes are
in `h08a-independent-results/summary.json`.

| Gate | Actual result |
| --- | --- |
| Frozen public + original-runner controls | 9 passed, zero skips |
| Independent private-catalog controls | 2 passed, zero skips |
| New module, normal locale / RuntimeWarning-as-error | 23 passed; exact qualified names match Git AST |
| Same module, real non-UTF text locale | 23 passed, zero skips |
| H07 / H10 / Q04 / Q05 targeted | 35 / 32 / 25 / 44 passed, zero skips |
| Full Pioneer | 1108 total: 1106 passed, original 2 Windows-only skips |
| Full QA / common | 440 / 2 passed, zero skips |
| H09 real offline CLI | 8 controls: 2 goal successes, 6 expected safety stops; no infra/safety violation |
| Current QA v1/v2/v3 CLI | Required source-drift rejection, actual exit 1 |
| QA v4 / Q04 CLI | Exit 0; original complete report hashes retained |

The compiled target3 actually ran through obs-1/2/3 and third-frame evidence,
3 steps / 12 offline tool calls / 0 model reservations. Terminal reentry adds no
calls. A precheck claiming chapter99 still cannot skip runtime observations;
missing or wrong field evidence reaches the original failed step limit, stale
observation stops before policy, and existing real budget/pause stop further
dispatch. SequenceClient is an offline fake port, not evidence of real MCP
transport, a game session or provider execution. No second execution loop exists.

New test text I/O is explicitly UTF-8. The locale control starts C.UTF-8 with
utf8_mode=0 and UTF-8 filesystem, then sets LC_CTYPE=C in the actual test process.
A real default-open handle reports ANSI_X3.4-1968 while stdout remains UTF-8.
All 23 tests execute in that process; the metadata makes clear any spawned
interpreter would inherit the C.UTF-8 environment, not the in-memory locale change.
This is not Windows evidence and does not repair the known strict-C ASCII-filesystem
limitation. No PYTHONUTF8=1 or mocked reader is used.

QA v4 SHA256 remains
`c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c`;
Q04 remains `b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6`.
Independent H09 JSON remains `/tmp/h08a-cr-8e0a2a0-results/h09/report.json`, SHA256
`eaed95113d2d6e605432bc504fc3ccf76206a94cdd61c4cab0ce89f3512bf35a`.
Only compact current logs/metadata are committed; no historical large matrix or
per-case checkpoint tree is copied. Raw log whitespace is preserved.

## CI wiring, author audit and retained history

The unique three-line Windows H08a step follows Q05a. Exact reverse deletion
restores whole workflow bytes and parsed YAML; dependencies, actions, jobs,
permissions, environment, runner, timeouts and every old step remain unchanged.

Read author report `1071b52e1266f3dca34f321ce2f68b92c7ba854f`; its package/workflow
trees are identical to tested source. Fifteen final raw Gitblob logs were checked
for byte lengths, SHA256, tests/skips/exits and OK summaries; 23-name inventory,
locale metadata, deterministic QA hashes and H09 totals agree with independent
runs. Three pre-freeze logs were also hash/summary checked, preserving first
23/1error (new test misspelled BudgetLimits field), second 23/1failure (new fake
pause/resume script lacked the third continue), and third 23/23 pass. Those are
test-input corrections, not changes to old runtime semantics or final-source
evidence. No independent probe assertion was changed or unexpected red discarded.
See `author-crosscheck.json` for the exact audit records.

## Remaining gates and authority boundaries

New native23 remains pending exact final published SHA/attempt: all qualified names
each ok, zero skips, exit0, plus existing Windows25/44 and same-run four jobs green.
Source-specific Linux approval does not replace coordinator combination or native
verification. No local native dependency probing or installation occurred.

Caller metrics and content digests are declarations, not authenticated observations,
signed source, human review or live grants. H10 skill provenance is not automatically
wired; this slice does not establish a complete skill causal chain. No runtime/
production repair by reviewer, main/WIP/push, Q06 payload/ancestry, old archive
body/member reads, provider/network/game/bridge/.env/credential/KB publish/install/
deployment actions. Q06 remains paused; all new evidence is bounded plain text/JSON.
