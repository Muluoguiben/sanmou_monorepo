# Q03a coordinator integration verification

Date: 2026-10-06. Local integration passes. Code and evidence published as `49ffe2d918c4c45cc0db3f8de273f4cdd84c1fdc`; remote master readback matched. Exact-final-SHA CI is tracked separately in the iteration state. This is bounded offline acceptance, not production readiness.

## Immutable source and independent decision

- Independent approved code: `3b2b137679bd6b72a5681874bf9ab6ea0ac8f0c9`, tree `ec1d8f04ff42156c90a151b4d0e4c3fbddf765c6`.
- Independent APPROVE report: `146433ffef1d087bdbf72148a21d7d8746e90d3e`; Q03a-CR01/02/03 closed. [Review](../../reviews/2026-10-05-Q03a-adversarial-recheck.md).
- Coordinator integration: `4b158253ab12a0eb9e0600df6d0e95c33b69a603`, tree `9366aa8237706b67d6887a0ed543a73b7bba72fd`.
- Both approved code and integrated source have packages tree `575745075210e7e27c13fb3c18d7d31cb62d11a2`. All other differences are reports, task documentation, todo and iteration state. No production source was modified after approval.
- Tests ran in the clean detached ext4 worktree `/tmp/sanmou-q03a-integration-4b158253`, not the report checkout. Git status remained clean after testing. The coordinator independently checked all 30 CR recheck artifact hashes with zero mismatches before integration.

## Coordinator results

| Check | Observed result | Exit | Command record and raw evidence |
| --- | --- | --- | --- |
| Full QA | 367 pass, 0 skips | 0 | [record](Q03a-integration-artifacts/qa-full.json), [log](Q03a-integration-artifacts/qa-full.log) |
| Full Pioneer | 934 total: 932 pass, 2 Windows-only skips | 0 | [record](Q03a-integration-artifacts/pioneer-full.json), [log](Q03a-integration-artifacts/pioneer-full.log) |
| Full common | 2 pass, 0 skips | 0 | [record](Q03a-integration-artifacts/common-full.json), [log](Q03a-integration-artifacts/common-full.log) |
| Focused repair regression | 44 pass, 0 skips | 0 | [record](Q03a-integration-artifacts/focused.json), [log](Q03a-integration-artifacts/focused.log) |
| Original independent probes, exact selector | 17 pass, 0 skips | 0 | [record](Q03a-integration-artifacts/original-probes-exact.json), [log](Q03a-integration-artifacts/original-probes-exact.log) |
| New lazy-origin / scope boundaries | 8 pass, 0 skips | 0 | [record](Q03a-integration-artifacts/new-boundaries.json), [log](Q03a-integration-artifacts/new-boundaries.log) |
| Explicit v2 development eval | 12 queries, Recall@5/MRR 10/11, 6 synthetic gate cases, 0 provider calls | 0 | [record](Q03a-integration-artifacts/v2-eval.json), [result](Q03a-integration-artifacts/v2-result.json) |

An earlier green original-probes invocation selected the entire `test_q03a_extra` module and ran 32 test executions, including 15 imported duplicate TestCase cases. Its [record](Q03a-integration-artifacts/original-probes.json) and [log](Q03a-integration-artifacts/original-probes.log) are retained but are **not** counted as extra coverage. The exact selector is `test_independent_q03a test_q03a_extra.ApplicabilityBoundaryTests`. These suites overlap with the full QA run; counts must not be added into a unique-test total.

## Reproducibility and restrictions

[run_checks.py](Q03a-integration-artifacts/run_checks.py) pins the integration commit/packages tree, records argv/cwd/environment paths/runtime/dependencies/time/exit/log and runner SHA256, uses exclusive artifact writes, and caps each subprocess at 300 seconds. The recorded Python is 3.12.3; pydantic 2.12.5, PyYAML 6.0.1, MCP 1.29.1, AnyIO 4.13.0. Existing API dependencies were reused, not installed. QA and focused unittest processes use the reviewed audit-hook guard denying `.env` reads and Internet connects/DNS. Fake clients are used; no paid model, real vision, game input or formal-KB publication occurred.

The v2 output SHA256 is `66b7b504951f69c0bcc19de7d699d8cc00a506cddc74c3ce4894ee14740ae425`, byte-identical to the premerge repaired-source replay. Original v1 on untouched `f879915` reproduced SHA256 `86a8a8f8fbcc04793e506d4f14d06d0aa664699bd91e88eff13f83b9a1edfc67`. Historical v1 remains unchanged and correctly rejects new production drift. No expected hash was rewritten to pass a test. Original CR red evidence and reviewer setup-failure diagnosis remain preserved in the [independent report](../2026-10-05/Q03a-CR-recheck.md).

[verification.json](Q03a-integration-artifacts/verification.json) binds the records and raw artifact hashes. Local tests do not replace the exact final pushed SHA's GitHub CI. Previous baseline `f879915` run 37321475905 succeeded in all four jobs; the older `d6b5a36` run 37321087930 was cancelled and remains classified as such.

The initial staged whitespace check stopped before commit because raw Rich-formatted stdout has trailing padding. Raw logs are deliberately preserved byte-for-byte. The subsequent source/document whitespace check excludes only `*.log`; no test result or log hash is changed.

## Publication authority and remaining work

The coordinator independently verified the user's actual standing authorization for this same repository's existing Review implementation/test/CR/integration/push/CI route, including the disclosed report/log/history/path metadata. No repeat publication question is needed within that scope. This does not grant other-repository transfer, credentials/private-data publication, paid-model use, deployment, account/security changes or game operations.

Before publication a separate read-only payload audit bound its result to `49ffe2d`: 12 commits, 114 changed files (110 new, four modified), prior 92 historical blob versions plus the 24-file evidence successor examined. No scoped publication blocker or credential/private-screenshot/model-inventory payload was found; this is a finite scan, not an absolute secret-free proof. All 36 raw logs match their first-added Git blobs. The payload's first CI read was run 37341366281, in progress; it is not recorded as successful. This report/status-only successor changes no packages, apps, scripts or workflow source.

Q03a covers explicit single-hero base/max/growth scalar assessment and conservative applicability degradation. It does not complete general Q03 semantic sufficiency, Q05 condition resolution, answer entailment, human-reviewed gold, independent holdout, real provider quality, native Windows full-suite coverage or game closed-loop execution. Following publication and exact-SHA CI, select the next small unfinished Review slice; the overall route remains in progress.
