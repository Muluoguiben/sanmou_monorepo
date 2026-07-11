# Artifact Promotion Policy

Record & Replay uses four trust layers. Promotion is explicit; generation alone never advances an artifact.

## Layer 1: Raw Demonstration Trace

The trace proves only what was captured during one human session. Accept it after strict integrity validation and privacy review. It does not prove causality, game rules, optimal strategy, locator stability, verifier quality, or execution safety.

## Layer 2: Action Candidate

Keep every compiler output at `pending_review` with `execution_authority=none`. Before accepting an action candidate, require:

- multiple reviewed sessions covering distinct window sizes, relevant pages, and UI states;
- holdout sessions not used to infer or tune the action;
- a unique semantic target and target identity independent of stored coordinates;
- explicit observed preconditions and unresolved conditions;
- positive, no-change, ambiguous-target, interruption, timeout, and popup examples;
- a verifier based on a new observation and an action-specific expected delta;
- recovery and stop behavior;
- risk classification and safety review.

Use this provisional floor for M1 dataset design; increase it when risk or UI variability is higher:

- harmless navigation: at least 3 reviewed positive generation sessions across 2 capture geometries, plus 3 reviewed generation negatives covering missing/ambiguous target, popup/interruption, and no-change/timeout;
- independent holdout: at least 2 positive and 3 negative sessions, with disjoint session IDs and at least one unseen geometry or start state;
- mutating claim/recruit/upgrade: at least 5 positive and 5 negative generation sessions, then at least 3 positive and 5 negative holdouts before runtime integration is considered.

These counts are eligibility floors, not automatic approval. The workflow owner approves semantic meaning and privacy; an implementation reviewer approves locator/verifier/safety evidence. The account operator remains the only authority for any future live confirmation.

Coordinates, delays, and one visual transition remain evidence only. They are never the locator, verifier, or permission by themselves.

## Layer 3: Skill

A reviewed skill may orchestrate reviewed actions. It still grants no new authority. Require:

- no raw coordinate dispatch;
- only reviewed action APIs;
- preflight, stop, recovery, and reporting instructions;
- fresh-agent forward testing;
- independent holdout eval with session IDs disjoint from generation data;
- explicit privacy and knowledge-publication boundaries.

Do not publish a generated draft under an authoritative skill name until these checks pass.

## Layer 4: Live Execution

Live execution remains behind the existing runtime controls:

- allowlisted action and capability flags;
- current-page and same-frame observation binding;
- semantic ROI uniqueness and geometry guard;
- one-shot operator confirmation where required;
- final mutating-click scope;
- new-frame post-action verifier and expected delta;
- kill switch, timeout, and recovery;
- action-specific live evidence review.

An R&R trace is a human demonstration, not a runtime dispatch trace. It cannot satisfy M1a `live_trace_fixture`, terminal-source evidence, confirmation receipt, dispatch binding, or post-verifier closure.

## Knowledge Publication

UI text visible in a recording is not automatically a game fact. Extracted terms, timings, mechanics, lineups, or strategy claims must enter the QA staging pipeline with source, date, uncertainty, privacy review, and independent evidence review. Never publish directly from the compiler.

## M0 Limitation

M0 intentionally has no promotion command and no authority-bearing privacy-review record. The raw manifest remains immutable with `privacy_reviewed=false`; a human review only permits local derivation, not promotion. M1 must add a separate signed/reviewer-attributed annotation manifest instead of editing raw evidence. Until that exists, every action and skill remains `pending_review` with no execution authority.

## Suitable First Candidates

Prefer harmless, observable workflows: open a stable panel, switch a read-only tab, inspect a battle report, return to a known page, or close a known non-mutating popup.

Treat claim, recruit, and upgrade as candidates only until multi-sample and verifier gates pass. Keep attack, abandon, transfer, purchase, login, account, and unknown-popup actions outside single-demonstration promotion.
