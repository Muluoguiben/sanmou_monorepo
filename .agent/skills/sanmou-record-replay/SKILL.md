---
name: sanmou-record-replay
description: Record a focused workflow in the Windows Sanmou client and compile it into an integrity-checked human-demonstration trace, pending action candidates, an offline replay plan, and a review-only skill draft. Use for Windows UI workflow capture, action-boundary keyframes, trace inspection, candidate skill creation, multi-sample planning, or holdout-eval preparation. Never use it to grant live execution authority, publish game knowledge, or claim M1a closure.
---

# Sanmou Record & Replay

Capture a short human demonstration without dispatching input. Treat every generated action and skill as an unreviewed candidate until it passes the promotion policy.

## Enforce Preconditions

1. Read `../sanmou-computer-use-safety/SKILL.md` and `../sanmou-client-control/SKILL.md` before touching the live client.
2. Ask the operator to restore and foreground the game manually. Do not restore, resize, or foreground it programmatically.
3. Keep chat, credentials, account details, and unrelated windows out of the recording.
4. Record one narrowly named workflow at a time. Stop before purchases, attacks, abandon, transfer, login, or any other high-risk final action.
5. Leave the raw session in `%LOCALAPPDATA%\SanmouRecordReplay\sessions`; do not copy it into fixtures, eval, QA knowledge, or git before privacy review.

## Record a Demonstration

From `packages/pioneer-agent`, run:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay record \
  --workflow-name open-recruit-panel \
  --duration-seconds 60
```

The command launches the standalone Windows recorder. It binds only to one visible `com.bilibili.nslg` `UnityWndClass`, captures compressed WebP keyframes, and observes Raw Input. It does not call a control adapter, start a socket listener, elevate, read the clipboard, or persist printable text.

Stop with `Ctrl+Shift+F12`, `Ctrl+C`, the duration limit, or an empty `STOP` file in the session directory. Treat a minimized, hidden, replaced, or geometrically invalid game window as a hard failure.

Recording always returns a raw session. Use only the separate `compile <session-dir>` command after strict validation and privacy review. Use PNG only for a separately approved evidence capture; keep routine demonstrations on the default WebP settings.

## Inspect and Validate

Run these commands without opening all frames in model context:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay inspect <session-dir>
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay validate <session-dir>
```

Inspect the manifest, event counts, hashes, ignored inputs, capture errors, target identity, geometry, and privacy status first. Open only the smallest relevant keyframe or ROI if visual review is necessary.

Read [recording-schema.md](references/recording-schema.md) when validating fields or diagnosing integrity failures.

## Annotate Without Rewriting Raw Evidence

Generate a reviewer-attributed draft on stdout, copy it to a separate review
location, and validate the exact file explicitly:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  annotation-template <session-dir> --workflow-id map-filter-apply
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  annotation-validate <session-dir> <annotation.json> --require-approved
```

The annotation binds exact manifest and events hashes, full event/frame review,
semantic targets, preconditions, claimed/observed deltas, negative labels,
canonical before/after observation digests, and review attribution. Every
non-ambiguous transition must agree with the annotation's single canonical
label/outcome contract; intermediate panel/selection observations stay
observation-only and trace-only. It is not a cryptographic signature, runtime
verifier, or authority grant. Read
[annotation-schema.md](references/annotation-schema.md) before creating or
approving one.

Audit a frozen generation/holdout registry separately:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  audit-dataset <registry.json> \
  --sessions-root <raw-sessions-root> \
  --reviews-root <review-root>
```

The current audit proves only integrity, declared review binding, exact
within-registry deduplication, and provisional sample-count coverage. It
deliberately reports corpus catalog, development lineage, oracle, visual-near-
duplicate, structured start-state, filesystem-race, independent-eval, and image
model gates as unverified. Read
[dataset-registry-schema.md](references/dataset-registry-schema.md) before using
or interpreting the report.

After every registry and development artifact has been placed in its own
dedicated closed root, audit the canonical corpus separately:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay \
  audit-corpus <catalog.json> \
  --registries-root <closed-registry-root> \
  --sessions-root <raw-sessions-root> \
  --reviews-root <review-root> \
  --artifacts-root <closed-development-artifact-root>
```

This closes exact cross-registry identity leakage and content-addressed lineage
only inside the configured roots. It still leaves oracle, visual-near-duplicate,
structured start-state, human-provenance, handle-pinned filesystem, and real
image-model gates unverified, so `independent_eval_ready` remains false. Read
[corpus-catalog-schema.md](references/corpus-catalog-schema.md) before creating a
catalog or interpreting this scoped proof.

For a frozen coverage-ready corpus, keep predictions and labels in separate
trust domains. The ordinary CLI may inspect an unlabeled submission and verify
an aggregate Ed25519 attestation, but it must never receive an oracle path. Run
the scorer only through the dedicated external evaluator entrypoint with a
sealed oracle, approved reviews, private key, and persistent one-submission
ledger. Never place oracle labels or the private key in git, development
artifacts, chat/model context, or the predictor process. Read
[holdout-eval-protocol.md](references/holdout-eval-protocol.md) before preparing,
scoring, or interpreting a holdout submission.

## Compile Review-Only Candidates

Compile only after strict validation and manual privacy review succeed:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay compile <session-dir>
```

Compilation may write:

- `compiled/action_candidates.jsonl`
- `compiled/replay_plan.json`
- `compiled/draft_skill/SKILL.md`
- `compiled/compilation_report.json`

M0 fixes `proposed_action_type`, `semantic_target`, and `expected_delta` to unset. Put reviewer evidence in a future M1 annotation artifact; never edit the raw trace or treat a draft edit as promotion. Preserve `inferred_from_single_demo=true`, `execution_authority=none`, `closure_eligible=false`, and `review_status=pending_review`.

Read [draft-skill-template.md](references/draft-skill-template.md) before editing a generated draft.

## Replay Offline Only

Generate or inspect the deterministic offline plan with:

```bash
PYTHONPATH=src:../sanmou-common/src python3 -m pioneer_agent.app.record_replay replay <session-dir>
```

Never add or use `--execute`. M0 has no live replay implementation. Coordinates are demonstration evidence, not execution authority.

## Promote Deliberately

Read [promotion-policy.md](references/promotion-policy.md) before moving any artifact into an action implementation, repo skill, fixture, eval, or QA knowledge source.

Use multiple reviewed demonstrations, a semantic target independent of coordinates, explicit preconditions, negative examples, a separate verifier, corpus-wide disjoint holdout sessions, recovery behavior, safety review, and the existing runtime confirmation/kill-switch gates to establish eligibility for a future M1/M3 implementation. A green provisional registry count is not an independent eval or promotion. M0 itself has no promotion or execution path.

Keep human-demonstration traces separate from runtime-dispatch terminal evidence. A demonstration cannot satisfy `live_trace_fixture`, operator-confirmation, same-frame dispatch, or post-action verifier requirements.

## Report the Result

Report:

- session path and UUID;
- status and stop reason;
- event/frame/ignored/error counts;
- events SHA-256 and strict-validation result;
- compression settings;
- candidate and offline-plan counts;
- privacy-review state;
- every remaining promotion blocker.

Do not report a generated candidate as a working skill, a demonstrated transition as causally verified, or an offline plan as a runnable automation.
