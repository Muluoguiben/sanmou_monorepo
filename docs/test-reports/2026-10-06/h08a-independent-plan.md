# H08a independent plan (before author memo/code)

Published baseline: `60e3e002c7b38571e76d344dd100b47d053244e2`.
Frozen contract: `df8447ae8807e2baa97a05ada3b209bfb7e3688b`.
Read complete contract, applicable AGENTS and code-review skill; AGENTS is
unchanged from the published baseline. Clean reviewer worktree is isolated on
`codex/h08a-readonly-skill-registry-cr-20261006`, with prior refs retained.
No author memo or implementation read before freezing this plan.

## Interface and admission

1. Review fixed memo first: public list/resolve/compile signature, strict schema,
   invalid versus typed-blocked outcomes, catalog admission, canonical digest
   content, deep-copy guarantees and precondition result. No private API guesses.
   This is an application task recipe registry, not Codex Skill installation.
2. Exactly one repository builtin chapter-observer@1.0.0. Unknown/missing IDs or
   versions, similar names and implicit latest must fail closed with no usable
   task. External reviewed flags, draft objects, file paths/plugins/scripts,
   replaceable catalogs and natural-language requests confer no admission. No
   loading/eval/dynamic imports, default route, auto-run or R&R draft promotion.
3. target_chapter is the only compilation parameter: actual int, 1..1000. Reject
   bool/float/string/None/out-of-range, extras and tool/budget/condition/authority
   overrides. task_id follows the memo's fixed rule; callers cannot inject paths
   or scripts. Duplicate internal (id,version) keys must fail; testing this
   invariant must not create a public external-registration facility.

## Isolation, digests and precondition controls

4. Freeze independent mutation probes across nested list/resolve/compile outputs.
   Changing one returned object must not affect later lookups, templates, other
   compiled tasks or digests. Verify complete template and actual compiled task
   digest preimages independently, including versions/schema/constraints/params;
   all relevant content changes must affect their corresponding digest. Stable
   content stays deterministic. Hashes never certify authorship or human review.
5. Precheck only supplied progress.current_chapter_id >= 1 using existing
   Condition/evaluate_all. A true int >=1 passes; 0/negative is false; missing,
   None, bool, wrong types/nonfinite numbers are unknown. Do not mutate metrics,
   infer values or change shared DSL. Freeze both missing and malformed controls.
6. False/unknown yields typed blocked, original condition/missing-metric detail,
   task=None, no tool/model/scheduler/refresh/wait calls. Passing precheck returns
   an independent TaskSpec only; supplied metrics have no authenticated freshness
   or source status, and a target already satisfied cannot bypass runtime evidence.

## Fixed TaskSpec and actual runtime integration

7. Exact existing TaskSpec v1: success condition chapter >= target_chapter,
   required_domains=[chapter_panel], max_steps=3, wait_seconds=0, stop_when=[];
   tool set exactly session_status/observe_game/get_runtime_state/list_action_candidates.
   No automatic expansion from global catalog or caller overrides. none/false
   authority throughout; no live approval/grant or new schema/provenance wire.
8. Compile target 3, then run with existing SequenceClient/TaskRunner/Rule policy.
   Independently track three actual fresh observations obs-1/2/3 and goal evidence;
   terminal reentry adds no calls. Precheck success/target-already-met is not a
   substitute for a new runtime observation. Missing/wrong field evidence cannot
   succeed; original budget stop/pause/freshness behavior must still block. No
   second execution loop, model, real game or transport impersonation.

## Compatibility and delivery

9. Only new registry/test (optional tiny builtin definition/fixture needs reason)
   and the single contract Windows H08a step after Q05a. Reverse deletion must
   restore entire baseline workflow bytes and parsed YAML; all other steps,
   dependencies, permissions, environments, jobs/runners/timeouts remain unchanged.
   TaskSpec/runner/policy/context/budget/store/MCP/DSL/QA/KB/R&R/old tests and fixtures
   stay byte-identical. New text I/O is explicit UTF-8; if any, use a real non-UTF
   text/UTF-8-filesystem control without read mocks or PYTHONUTF8=1. Do not extend
   the known strict-C ASCII-filesystem boundary or explore native dependencies.
10. Freeze probes before runs, preserve reds and unchanged repair assertions.
    Bind all evidence to immutable source SHA/tree/actual Git bytes. Run new
    tests/integration, full Pioneer/QA/common, H07/H10/H09 and real QA CLI gates.
    v4 whole SHA stays c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c;
    Q04 stays b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6.
    Old v1-v3 expected rejections remain. Crosscheck author fixed reports/raw hashes
    only after independent execution; no prior component pass proves new source.
11. Native remains pending until coordinator checks exact published SHA/attempt:
    all new test names match AST, each ok/zero skips/exit0, original Windows25/44
    retained, all four jobs green. Report incomplete skill-trace wiring explicitly;
    registry metadata does not establish a completed causal provenance chain.

Reviewer writes no production/CI implementation, main/WIP or push. No Q06 payload/
ancestry or archive body/member reads, new archives, provider/network/game/bridge,
.env/credentials, installs, KB publication or deployment. Evidence bounded plain
text/JSON; no repeated historical probe matrix. Next: send plan SHA, await fixed
memo for narrow feedback, then fixed author source and source-bound report.
