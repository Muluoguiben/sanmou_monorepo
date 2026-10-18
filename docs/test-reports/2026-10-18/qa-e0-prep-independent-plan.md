# Q-E0-dev preparation: independent plan before author memo/code

Contract/source: `88bd5a0fb641d147548ed6a5eb8284106ec3caa2`,
`docs/qa-e0-review-preparation-2026-10-18.md`.
Review branch: `codex/q-e0-review-prep-cr-20261018`, in the existing review tree.
Read complete AGENTS, code-review/caveman-review skills, contract, and existing
v4 runner/freeze plus claim_spans_v1 freeze. No future author implementation read;
`scripts/prepare_e0_review.py` is absent and will not be executed as a fake red.

## Scope and interface-first gate

1. Review the author memo before implementation: exact verify/prepare CLI,
   finite count bound, fixed source allowlist, deterministic stratification and
   duplicate handling, output-root rules, schema/blank human fields, escaping,
   manifest-last/create-only behavior and source/hash version definitions. Do not
   invent an import/approve/publish command or a new scorer in this review.
2. Allowed implementation: new QA preparation script, one new unittest module,
   small frozen reference manifest, protocol documentation and bounded synthetic
   fixtures/reports. Protect all src, formal KB, old fixture bytes/assertions,
   existing scorers, MCP/publisher, Pioneer/common, dependency and CI paths.
   No old output regeneration, no copied baseline masquerading as a new gold set.
3. Confirm current baseline identities from existing files: v4 formal KB snapshot
   34 YAML, non-quality_eval production snapshot 153 Python, 12 exposed queries
   permanently development, and 12 synthetic claim-span controls. Preserve all
   existing fake/synthetic/developer-authored labels and baseline_commit meaning.
   A KB hash is content provenance, not game truth or human review.

## Fixed source and zero-authority negative dimensions

4. verify is read-only; invalid source/count/schema must fail before output
   creation. Verify fixed package/import roots, upstream freezes/cases, their
   exact identities/counts and the new declared manifest. Exercise source edit,
   addition/removal, cases/freeze/metadata drift, duplicate IDs, and mixed/lazy
   QA module origins using isolated synthetic/in-process probes only. No mutation
   of real formal KB or old fixtures to manufacture evidence.
5. Selection/rendered content and recorded hashes must bind the same validated
   source snapshot. Probe a change between verification, loading, selection and
   finalization: do not permit a complete manifest to claim earlier validated
   content for a different later payload. This is bounded local-source binding,
   not a newly requested hostile-loader/filesystem security framework.
6. No real LLM client/configuration, .env/credential read, provider/network call,
   publishing or game/control action. Instrument relevant construction/call
   boundaries; do not confuse existing explicitly fake evaluation calls with
   real provider use. Retrieved instruction-like text remains data, never an
   instruction to execute, approve or fetch a URL.

## Selection, completeness and human review semantics

7. Require exactly requested unique task IDs and valid, deduplicated candidate
   entry IDs under the declared selection model; related evidence may contribute
   multiple IDs without being mistaken for extra tasks. Test default
   50, explicit 50, smallest admissible count, the memo's finite maximum and its
   next value; reject zero/negative/noninteger/overlarge input, including bool or
   float coercion where a callable API exists. An insufficient or duplicate-only
   candidate pool cannot silently shrink a claimed 50-task package.
8. Independently replay the documented stable-ID/domain stratification. Shuffle
   source enumeration and repeat at a second new output location: task selection,
   order, task/Markdown/manifest content must be reproducible as promised. Any
   environmental metadata exclusions must be explicit, not added after a diff.
   Deterministic machine selection is neither random independent sampling nor a
   holdout guarantee; existing exposed queries remain development.
9. Compare every selected task against the full entry representation, not merely
   answer_lines or an excerpt: all facts, constraints, relevant structured fields,
   source_ref, source snapshot/content hash and topic/source-family grouping.
   Include long text, conditional facts, conflicting qualifiers, season limits,
   unknown applicability, multiline strings and empty optional fields. Never
   truncate a limiting condition or turn unknown version into all-version truth.
10. All human response/answerability/evidence/necessary-fact/no-extrapolation/
    applicability/note/reviewer/reviewed_at fields start unfilled as specified by
    the memo. Assert review_status=unreviewed, independent_holdout=false,
    human_gold=false, execution_authority=none, executable=false at every relevant
    layer. Candidate evidence and template/developer-proposed questions must not
    become prefilled supported labels, reviewer identity or review timestamps.
    Source text containing reviewer/human-reviewed claims cannot alter these
    package/task-level machine-maintained states.
    No actual generated answer means no fabricated answer hash or claim score.

## Rendering and create-only output boundary

11. Test untrusted Markdown/HTML/control delimiters in every rendered slot,
    including question, ID/source_ref, facts, constraints and structured values:
    pipes, brackets, images/links, HTML tags, ampersands, quotes, embedded newlines,
    headings/checkboxes, backtick/fence closers and instruction-like text. The
    human document must retain complete literal content without creating active
    markup/remote fetches or counterfeit reviewer fields. Test Chinese/Unicode
    and actual UTF-8/LF bytes; separately verify existing raw-text/hash semantics.
12. Output is a new directory within an authorized current repository/existing
    worktree, never src/formal KB/.git or an alias into them. Test existing empty
    directory, populated directory, file, invalid parent, prohibited destination,
    outside-root target, and available symlink/junction aliases. Existing bytes
    and unrelated paths must remain unchanged. Do not expand supported roots to
    make a test pass or create a new worktree/install dependencies.
13. Inject failure at directory acquisition, each material write/close and final
    manifest creation. No overwrite, silent recovery, cleanup deletion, or
    complete manifest for partial material. A retry to the same failed directory
    must refuse and preserve it. Check exclusive creation/last-manifest ordering;
    preserve earlier valid files and make the original failure observable rather
    than converting it into success or silently replacing it with recovery.
14. Recompute every material and selected-entry binding independently: upstream
    freeze/cases/KB digest, script content version/hash, selection identities,
    tasks and readable material hashes. Reject missing/mismatched/duplicate/count
    metadata. No self-referential manifest hash or future commit claim. Hash
    equality must not be described as signing, authorship or approval.

## Protocol and regression acceptance

15. Distinguish current development, new review_queue and a future separately
    established holdout. Preserve source/derived/entity/template-family grouping
    and known exposure notes; removing old IDs alone cannot certify independence.
    No human-reviewed string may authenticate itself or close Q07 quality gates.
16. Reuse existing metric definitions and denominators: answerable Recall@k/MRR,
    citation-ID validity, externally labeled claim support/completeness, refusal
    precision/recall and context correctness. Missing measurements remain null/
    unmeasured rather than zero. No graded relevance means no claimed nDCG; no
    provider run means no answer-quality/latency/cost acceptance. Threshold stays
    null until the user confirms it before holdout unblinding.
17. On fixed source, audit allowed Git diff and actual relevant file bytes, run
    independent public probes, the new tests and full QA suite from package cwd.
    Rerun original v4 and Q04 actual CLIs: whole output hashes remain
    c30d4129f16930fd554c502d6a6b7f5787f657367df86e8ace5cd454db58858c and
    b9658bf88a197cf0a6a421dd66133bade253281961acc85f59c744b62732f0b6.
    Preserve v1-v3 expected refusals, prior failures and all unchanged assertions.
18. Root alone creates the real 50-task user package after review. It stays in a
    gitignored authorized work directory; no review-task/label materials enter a
    feature push. Only tool/protocol/reference manifest/synthetic tests/reports
    may be committed. Review approval covers this preparation tool, not human
    gold, independent holdout, Q07 quality or production readiness.

Use only existing WSL dependencies and the root-authorized reviewer-tmp scratch;
all Git commands explicitly use core.autocrlf=false. Keep failures as bounded
plain evidence; no protected Q06 archive/member access, provider/game/credentials,
installation, publication, master merge or deletion. Reviewer writes only its
finite probes/plan/report, commits locally, and never pushes. Next: send this
plan SHA; review author memo with root; freeze executable probes only after the
public helper/error/output shape is fixed; await immutable implementing source.
