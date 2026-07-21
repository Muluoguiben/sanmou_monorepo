# External Holdout Eval Protocol

Protocol schema version 1 separates unlabeled predictions from evaluator-only
labels. Signed aggregate schema version 2 adds the bound visual-audit proof; v1
aggregates are not accepted as evidence for that gate. The implementation in
`pioneer_agent.record_replay.holdout_eval` is authoritative.

## Trust boundary

The ordinary Record & Replay CLI can inspect an unlabeled prediction submission
and verify a signed aggregate attestation. It has no oracle argument and cannot
score samples.

The oracle, approved annotations, Ed25519 private key, and persistent release
ledger belong to an external evaluator environment. Do not copy them into the
development artifact root, git, chat/model context, or the predictor process.
The public trust policy contains the evaluator public key, exact corpus/catalog
binding, validity window, aggregate thresholds, and a fixed one-submission
budget.

Code separation alone is not an OS sandbox. The verification report therefore
keeps `evaluator_host_isolation_verified=false`; the evaluation owner must
enforce the external account/host/ACL boundary. A signed attestation can verify
the approved oracle and aggregate result, but cannot prove the host ACL from
inside Python.

## Prediction submission

`record_replay_holdout_prediction_submission` contains:

- exact corpus ID and catalog SHA-256;
- predictor ID and content hash;
- one prediction for every countable holdout session;
- dataset/session identity, events hash, and an unlabeled evaluation-input hash;
- predicted transition outcome and confidence;
- literal `oracle_accessed=false` and `oracle_labels_included=false`.

Unknown fields, duplicate samples, labels, unsafe identifiers, non-finite
confidence, authority flags, and non-canonical inputs are rejected. Inspect the
artifact without an oracle:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  inspect-holdout-submission <submission.json>
```

The summary contains only hashes and counts, never session IDs or outcomes.

## Evaluator-only scoring

Inside the external evaluator environment, run:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m \
  pioneer_agent.app.record_replay_evaluator <submission.json> \
  --oracle <sealed-oracle.json> \
  --trust-policy <public-trust-policy.json> \
  --private-key <evaluator-ed25519-private.pem> \
  --catalog <catalog.json> \
  --registries-root <closed-registry-root> \
  --sessions-root <raw-sessions-root> \
  --reviews-root <approved-review-root> \
  --artifacts-root <closed-development-artifact-root> \
  --evaluator-state-root <private-persistent-ledger-root> \
  --attestation-id <new-canonical-uuid> \
  --attestation-out <new-attestation.json>
```

The scorer requires a frozen coverage-ready corpus. It verifies that the oracle
contains exactly the countable holdout set and that every expected outcome
matches the approved annotation. It verifies the submission binds the same
immutable inputs, checks the private key against the trust policy, and atomically
claims a persistent release budget keyed by evaluator key plus catalog.

Only one signed submission is allowed for that key/catalog pair. Failed schema,
corpus, oracle, input, key, or privacy validation occurs before the budget claim;
after a valid release is claimed, retries fail closed even if later output
delivery fails. This limits adaptive aggregate-query attacks against a small
holdout set.

The private key must be a non-linked Ed25519 PKCS8 PEM. POSIX group/world access
is rejected. Windows ACL isolation remains an evaluator-host responsibility and
is not machine-verified by this implementation. Never commit or transmit the
private key through the ordinary CLI.

## Aggregate verification

The signed attestation contains only total count, exact-match count, unknown
count, scaled accuracy, pass/fail, and the corpus visual-audit algorithm plus
frame/candidate-comparison counts. It binds the exact submission and trust
policy hashes and contains no visual fingerprints, session IDs, expected
outcomes, confusion matrix, or oracle hash. Verify it on the development side
with:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  verify-holdout-attestation <submission.json> <attestation.json> \
  --trust-policy <public-trust-policy.json>
```

A valid report may set `holdout_oracle_verified=true` only for the signed
external attestation. It still keeps `independent_eval_ready=false` while host
isolation, human-capture provenance, structured start-state, parent-handle
filesystem hardening, or image-model execution proof remain missing. It grants
no promotion or execution authority.
