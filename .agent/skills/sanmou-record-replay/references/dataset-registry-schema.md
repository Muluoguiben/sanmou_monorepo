# Dataset Registry Schema

Schema version 1 groups approved human-recording annotations into one explicit
generation/holdout registry. The implementation in
`pioneer_agent.record_replay.dataset_registry` is authoritative.

## What the audit proves

A valid report proves that the referenced raw sessions and annotations passed
strict binding checks and that no exact duplicate identity or frame lineage was
found **inside that registry**. `coverage_ready=true` means only that the
provisional policy count floor is met in a frozen registry.

It does not yet prove independent eval. Reports deliberately keep these facts
false:

```text
corpus_catalog_verified=false
development_lineage_verified=false
holdout_oracle_verified=false
human_capture_provenance_verified=false
visual_near_duplicate_checked=false
structured_start_state_verified=false
filesystem_race_hardened=false
independent_eval_ready=false
image_model_exercised=false
```

Until a canonical corpus catalog, content-addressed development lineage,
evaluator-only oracle, structured start-state fingerprint, visual-near-duplicate
check, and platform-specific parent-directory-handle-pinned corpus walk exist,
never describe this audit as a leakage-proof independent eval.

`audit-corpus` can now close the first two gaps inside explicitly configured,
closed registry/artifact roots. That scoped result is documented in
`corpus-catalog-schema.md`; it does not change the false fields in this
single-registry report and still does not make the corpus independent-eval ready.

## Registry identity and split unit

The registry names one `corpus_id`, `dataset_id`, canonical `workflow_id`, risk
class, split status, and coordinate-free semantic contract. Each session entry
contains only:

- canonical session UUID;
- exact finalized events SHA-256;
- `generation` or `holdout`;
- stable capture-group lineage ID;
- relative annotation path and exact annotation SHA-256;
- fixed source kind `human_recording`.

The split unit is the complete corpus session/capture group, never an individual
frame or action segment. Do not put one session, clone, re-encoding, or capture
group in both splits. `apply`, `clear`, and `cancel` are separate workflows and
must use separate registries.

The registry must not contain absolute paths, account identifiers, window
titles, coordinates, raw OCR, or unreviewed image data.

## Internal integrity checks

The auditor loads completed raw sessions with image verification, then binds an
explicit approved annotation to the same session, exact manifest bytes, events
digest, workflow, capture group, risk, pages, action name, and semantic target.
It rejects duplicate session IDs, events hashes, annotation IDs/hashes, encoded
frame hashes, declared source-PNG hashes, and capture groups across all entries
in the registry.

Holdout sessions may not appear in the registry's declared development-artifact
sources. This is only a check of declared references; it is not a transitive or
filesystem-wide artifact-lineage proof.

Registry, manifest, events, individual frame, per-session frame, and total
corpus bytes have fixed audit limits. Unsafe relative paths, duplicate JSON
keys, non-finite numbers, symlinks/reparse points, hardlinks, and observed file
changes are rejected. Full concurrent directory-swap hardening remains a
separate platform-specific requirement and is reported as unverified.

## Provisional sample floors

Harmless navigation requires:

- generation: 3 positive sessions across at least 2 capture geometries;
- generation negatives: target missing/ambiguous, popup/interruption, and
  no-change/timeout;
- holdout: 2 positives plus all 3 negative categories;
- at least one holdout geometry or reviewed start-state ID not present in
  generation.

Low-risk mutation requires:

- generation: 5 positives across at least 2 geometries and 5 negatives covering
  all 3 categories;
- holdout: 3 positives and 5 negatives covering all 3 categories;
- the same unseen holdout condition.

High-risk data remains trace-only regardless of sample count. A collecting or
retired registry never reports its provisional coverage floor as ready.

These are eligibility floors, not promotion. Start-state novelty is currently a
reviewer label rather than a machine-derived state fingerprint, so it must not
be the sole basis for an independence claim.

## CLI

Audit one explicit registry without compiling, tuning, publishing, or opening a
live execution path:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  audit-dataset <registry.json> \
  --sessions-root <raw-sessions-root> \
  --reviews-root <review-root>
```

Integrity, privacy, binding, and internal leakage failures return an error.
Missing samples are normal for `collecting`: the command returns a valid report
with blockers. All registry and report safety fields remain no-authority,
non-terminal, non-closure, and non-publishable.
