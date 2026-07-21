# Corpus Catalog Schema

Schema version 1 places every reviewed dataset registry for one corpus inside a
single closed registry inventory and every declared development artifact inside
a separate closed artifact inventory. The implementation in
`pioneer_agent.record_replay.corpus_catalog` is authoritative.

## What the audit proves

A valid `audit-corpus` report proves, within the two configured roots:

- every regular registry file is explicitly cataloged and SHA-256 bound;
- every registry independently passes raw, annotation, privacy, semantic, and
  within-registry integrity checks;
- session UUID, events hash, capture group, annotation ID/hash, encoded frame
  hash, and source-PNG hash are unique across all cataloged registries;
- every declared frame is decoded locally under fixed format, dimension,
  single-image, per-frame, total-pixel, frame-count, and comparison-count
  limits, then checked across distinct sessions by the versioned
  `sanmou-multisignal-v1` visual near-duplicate gate;
- every regular development-artifact file is explicitly cataloged and SHA-256
  bound;
- direct source sessions match the union of declarations in the dataset
  registries, are generation-only, and resolve through an acyclic dependency
  graph;
- no undeclared regular file exists in either configured closed root at the
  beginning or end of the audit.

Accordingly the report may set `corpus_catalog_verified=true`,
`cross_registry_exact_leak_free=true`, and
`visual_near_duplicate_checked=true`, and
`development_lineage_verified=true`. Visual fingerprints remain evaluator-local
and are not serialized. The lineage field is explicitly scoped by:

```text
development_lineage_scope=configured_closed_artifacts_root
```

It does not discover development products stored outside that configured root
and must never be described as a machine-wide provenance proof.

## What remains unverified

The catalog does not open an evaluator-only oracle, derive a structured
start-state fingerprint, attest that captures came from a human, pin every
parent-directory handle against concurrent swaps, or exercise an image model.
Reports therefore retain:

```text
holdout_oracle_verified=false
human_capture_provenance_verified=false
structured_start_state_verified=false
filesystem_race_hardened=false
image_model_exercised=false
independent_eval_ready=false
```

The visual proof is an intentionally conservative engineering gate, not proof
that two real captures were independently produced. It combines multiple
center-crop variants of block-mean hash, difference hash, normalized grayscale
MAE, RGB mean, histogram, and aspect ratio. Hash bands only produce bounded
candidates; grayscale and color agreement must also pass before rejection.
Its public evidence is limited to algorithm version plus frame/comparison
counts. Threshold changes require an algorithm-version change and regression
tests for re-encode, resize, crop, distinct scenes, corrupt inputs, and resource
limits.

`coverage_ready=true` remains only the provisional policy floor across frozen
registries, not an independent-eval result.

The separate external protocol in `holdout-eval-protocol.md` can verify a
signed aggregate oracle attestation for a frozen coverage-ready catalog. Its
signed aggregate also binds the catalog auditor's visual algorithm and counts.
That does not expose fingerprints or oracle labels.

## Catalog identity and roots

The catalog contains one `corpus_id`, `catalog_id`, status, registry references,
and development-artifact lineage entries. It must live outside both closed
roots. Each registry reference contains only:

- expected dataset ID;
- normalized relative JSON path beneath `registries_root`;
- exact registry SHA-256.

Each development artifact contains only:

- stable artifact ID;
- normalized relative file path beneath `artifacts_root`;
- exact file SHA-256;
- zero or more direct generation-session UUIDs;
- zero or more dependency artifact IDs.

An artifact requires at least one direct source or dependency. Dependency-only
artifacts are allowed. Cycles, missing dependencies, duplicate content hashes,
holdout ancestry, source sessions outside the catalog, and disagreement with
registry declarations are rejected.

Both roots use `closed_root_all_regular_files`: extra files, symlinks/reparse
points, hardlinks, special files, unsafe paths, excessive depth/count/bytes, and
observed inventory changes fail closed. The auditor repeats the inventory after
all reads, but the absence of a platform-specific parent-handle-pinned walk is
still reported as unverified.

## CLI

Run the corpus audit without compiling, tuning, publishing, exposing oracle
labels, or touching the live client:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  audit-corpus <catalog.json> \
  --registries-root <closed-registry-root> \
  --sessions-root <raw-sessions-root> \
  --reviews-root <review-root> \
  --artifacts-root <closed-development-artifact-root>
```

The report never includes local paths or raw labels and always remains
`execution_authority=none`, non-terminal, non-closure, non-publishable, and
manually promoted.
