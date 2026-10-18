# Q-E0 preparation interface admission and independent probe freeze

Contract `88bd5a0`; independent plan `78c74b4`; author interface memo
`b02ebbdef0bbe0f9b0b8b3b0c8b32e66ff537afe` was read via Git, not merged.
Interface decision: no blocking issue; admission is for the minimal preparation
slice, not human gold, independent holdout, Q07 quality or production completion.
No implementation/WIP or author test results were inspected before these probes.

Root's clarifications are part of the review expectations:

- Keep the evidence package immutable in use. The user's filled replies go into
  a separate copy/file outside it; no automatic import/approve/publish command.
- manifest.pending.json has no complete-package authority. Its final hard link
  is create-only publication of local material, not signing, identity proof,
  immutable filesystem enforcement or hostile-concurrency protection.
- Raw fields cannot overwrite machine identity/authority. Unknown raw fields
  are preserved in their namespace or explicitly rejected, never silently lost.
  Raw YAML dates/datetimes have explicit ISO8601 JSON representation; ordinary
  scalar/list types are not generically stringified. Original source text/hash
  and locator remain separate from normalized model data.
- Answerability/not_found/conflicting judgments concern the displayed frozen
  anchor/one-hop candidate set. They are not whole-KB completeness/no-conflict
  gold. A human rewrite needing external evidence is marked for supplementation,
  not automatically admitted as Q07 gold. Final REVIEW needs Chinese quick-start
  guidance, separate-reply instructions and explicit unknown applicability.

## Declared test seams, not new public APIs

The author supplied only these signatures/schemas in coordination messages:

- verify() -> dict; _load_verified() -> dict with report/records/sources/seal.
- _build_tasks(records, *, count, development_queries, development_evidence_ids)
  -> {selection, tasks}.
- _render_review(bundle) -> str.
- _write_bundle(output, bundle, *, revalidate) -> file/hash summary.
- Expected refusals: ValueError; I/O faults retain OSError classification;
  public CLI data/I/O exit 1, argument errors exit 2.

Record: source_path, record_index, source_text_sha256, raw_record and full
KnowledgeEntry JSON entry. Candidate records add separate entry_content_sha256
and raw_record_sha256. Selection declares algorithm/count/anchor_entry_ids/
domain_order/domain_counts/excluded_development_evidence_ids/exposure plus
excluded_development_query_anchor_ids and duplicate_question_anchor_ids.
family_hints.candidate_match_reasons records anchor, topic_or_alias_overlap,
related_topic_outbound or related_topic_inbound. No transitive closure or
same-source-only inclusion is implied by the fixed one-hop algorithm.

Bundle protocol is qa-e0-review-prep/v1. raw_record_encoding at its root is
yaml-safe-data-json/date-and-datetime-iso8601-v1. Synthetic private writer tests
may use an opaque upstream dict with a 64-zero script_sha256; real public CLI
still requires its fixed verified KB/freeze path. The human_review object has
the exact nine memo-listed fields, all null; no invented tenth field.

Renderer declaration: complete bundle JSON, html.escape(quote=False), a dynamic
backtick fence longer than every content run, and static Chinese guidance/safe
IDs outside. Probes validate literal round-trip/full evidence and safety without
prescribing unrelated layout.

## Frozen executable checks

qa-e0-prep-independent-probes.py contains eight synthetic checks plus one CLI
argument-rejection check. It covers strict finite count/global duplicates,
round-robin after exclusions, exposed-question dedup, exact one-hop candidates,
raw/machine collisions, complete long structured evidence and literal rendering,
deterministic create-only output, pending/final hard-link identity, callback
source failure, changed written REVIEW bytes, final-marker collision and retries.
It never generates a real 50-task package. All scratch is unique under the
already authorized reviewer-tmp directory; failed artifacts are not deleted.

Before fixed implementing source, only AST/fixture-construction checks are run.
The absent product script is not invoked to create a fake failure. Remaining
source/import drift, supported raw-date loading, early write failures, path
restrictions, verify read-only behavior and Chinese/scope wording will be checked
on fixed code with the frozen plan; these probes do not claim complete coverage.
Original v4/Q04 CLI hashes and QA baseline/new-test/probe counts remain separate.
