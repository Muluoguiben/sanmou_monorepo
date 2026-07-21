# Reviewer Annotation Schema

Use schema version 1 to describe human-reviewed meaning without modifying the
raw Record & Replay session. The implementation in
`pioneer_agent.record_replay.annotations` is authoritative.

## Trust boundary

An annotation is reviewer-attributed, not cryptographically signed. It records
who made a decision and when, but it does not authenticate that identity. Keep
the raw `manifest.json`, `events.jsonl`, and `frames/` immutable. A revision must
receive a new annotation UUID and may point to the prior UUID through
`supersedes_annotation_id`.

Every annotation is bound to all of the following:

- canonical raw `session_id`;
- exact-byte SHA-256 of `manifest.json`;
- finalized `events_sha256` from the raw manifest;
- exact raw `workflow_name` plus one canonical `workflow_id`;
- a stable, coordinate-free `capture_group_id` used for dataset lineage.

Changing a legal manifest field still changes `source_manifest_sha256` and
invalidates the old annotation. Matching only the session UUID is insufficient.

## Review sections

`semantic_review` records the workflow owner's decision. `privacy_review`
always covers the full raw session and must explicitly list every reviewed
frame plus the manifest and events file. Local derivation or eval-candidate
approval additionally requires
`scope=full_raw_session_and_annotation`, which records that the reviewer also
inspected every free-text annotation field. A final decision requires a
reviewer ID and a timezone-aware timestamp no earlier than annotation creation
or recording completion.

An approved privacy review must explicitly assess:

- account identifiers;
- chat;
- player or alliance names;
- payment or secret material;
- precise account-identifying coordinates;
- unrelated windows.

`approved_for_local_derivation` permits local review tooling only and is
invalid unless annotation text is included in the privacy-review scope.
`approved_for_eval_candidate` additionally requires every sensitive flag to be
false and implies local derivation approval. Raw session storage in git remains
fixed to false even after review. Either approval flag also requires an approved
top-level annotation and explicit manifest, events, and complete frame review;
a draft cannot carry forward privacy-derived eligibility.

One rejecting semantic or privacy review rejects the whole annotation. Approval
is deny-wins; a draft cannot hide a recorded rejection.

## Segments and event coverage

Every persisted input event must appear exactly once, either inside one ordered
segment or in `excluded_events` with a reason. A shared-frame or ambiguous burst
must be represented atomically by one segment; its individual events cannot be
listed separately in `excluded_events`. Segments must:

- follow raw event order and contain only contiguous events;
- use the exact before frame of their first event and after frame of their last;
- keep every shared-frame or `ambiguous_burst` group together;
- describe page, action, target, preconditions, expected claim, observed delta,
  outcome, and unresolved assumptions independently of stored coordinates.

Countable evidence is additionally bound to the exact reviewed perception on
both sides of the transition:

- `observation_schema_id` names the versioned canonical observation schema;
- `before_observation_sha256` is the lowercase SHA-256 of the exact canonical
  before-observation bytes reviewed by the annotator;
- `after_observation_sha256` is the equivalent digest for the after observation.

All three fields are required together for positive and negative evidence. A
trace-only or excluded segment may leave all three null, but partial bindings
are invalid. Downstream classifiers must recompute the same canonical digests
and compare them to these annotation fields; a caller-supplied digest by itself
does not establish the binding.

`SemanticTarget` forbids extra fields, so bbox, pixel point, normalized point,
delay, and dispatch parameters cannot be smuggled into the semantic label.

Positive evidence requires a unique semantic target, explicit preconditions,
an expected-delta claim, an observed delta, and outcome `applied`. Geometry
changes, capture errors, ambiguous bursts, and high-risk workflows cannot be
positive evidence. Every positive or negative (countable) segment also requires
a normalized lowercase-ASCII `proposed_action_name` and reviewed,
non-placeholder `page_before` / `page_after` values, plus the complete
content-addressed observation binding above. Every countable negative segment
must use the same label as the top-level negative sample; one matching segment
cannot mask other mismatched negative evidence. Top-level sample and risk labels
must agree with their segments.

Countable labels use one canonical outcome mapping shared by annotation,
dataset audit, and transition classification: `positive -> applied`,
`no_change|timeout -> no_change`,
`missing_target|ambiguous_target -> ambiguous`, and
`popup_interruption|operator_cancelled -> interrupted`. In particular,
operator cancellation is never accepted as `no_change`. `panel_opened` and
`selection_changed` are intermediate observations only: they require an
`observation_only` top-level/segment label, `trace_only` evidence, and their own
reviewed semantic action/target instead of borrowing an `applied` annotation.

The expected delta is still a reviewer claim. Every segment remains
`verifier_status=unproven` and `causal_verified=false`.

## Permanent no-authority fields

The schema fixes these values and rejects attempts to override them:

```text
execution_authority=none
live_dispatch_allowed=false
safe_for_live_replay=false
terminal_source_eligible=false
closure_eligible=false
knowledge_publication_allowed=false
```

Schema version and fixed-false safety fields use strict integer/boolean types;
JSON values such as `true`, `0`, `1.0`, or `"false"` cannot pass by coercion.
An annotation revision must use a different UUID and cannot supersede itself.

Consequently, an approved annotation is not a live trace, terminal source,
runtime verifier result, permission to click, or QA knowledge source.

## CLI

Generate a draft on stdout without touching raw evidence:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  annotation-template <session-dir> --workflow-id map-filter-apply
```

Edit the copied draft as a separate review artifact, then validate that exact
file explicitly:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  annotation-validate <session-dir> <annotation.json> --require-approved
```

The loader rejects duplicate JSON keys, non-finite numbers, oversized or
non-regular files, symlinks/reparse points in any path component, hardlinks,
ordinary leaf replacement or same-inode changes observed during a bounded read,
stale raw snapshots, stale hashes, incomplete review scope, and inconsistent
event or frame references. Before binding an annotation, it reopens every raw
artifact and compares the exact digest plus retained file identity from the
caller's `LoadedRecording`. Neither command writes to the raw session.

This does not yet pin every parent directory by an OS-specific handle across the
entire multi-file validation. The dataset audit must continue to report
`filesystem_race_hardened=false` until that stronger cross-platform guarantee is
implemented and verified.
