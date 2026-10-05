# Q02a coordinator integration verification

Date: 2026-10-06. Exact-source independent approval and local combined-tree verification passed. Payload `a071176c799c6e50c42d1d025f8eccf8260e30a0` was pushed to master and explicitly fetched with matching SHA. Exact-final-SHA CI remains a separate gate tracked in iteration state. This is a bounded offline slice, not production readiness.

## Source and approval

- Approved code/eval/tests: `40f46d3ea4525639877ad37a8da4ab6e334523e6`, tree `1351c2432adb0a638997ab9faff7bb22725fba4f`.
- Independent APPROVE: `c68cab94a95731c3e05511d9203e8337e956cd3f`; Q02a-CR01/02 closed. [Decision](../../reviews/2026-10-06-Q02a-adversarial-recheck.md), [independent evidence](Q02a-CR-recheck.md).
- Local integration: `94e1464ba3fcff9b5874868138fa2d9f300fb376`, tree `8fd347c8286ff66061da393d4455779fcf6d9420`.
- Approved code and integration packages tree both equal `3c643ef1d3fd0ae376ebea6b055d0aaba564edf8`. Other differences are docs, todo and iteration state only; no unreviewed business-source change.
- Coordinator independently checked all 25 CR recheck artifact hashes: zero mismatches. Four author-copied original probes also match the raw `eb895ae` Git blobs and SHA256 exactly.
- Tests below ran in clean detached ext4 worktree `/tmp/sanmou-q02a-integration-94e1464`, pinned to the integration commit. It remained clean after tests; this is not a run against a moving developer checkout.

## Coordinator results

| Check | Observed result | Exit | Record / raw evidence |
| --- | --- | --- | --- |
| Full QA | 394 pass, 0 skips | 0 | [record](Q02a-integration-artifacts/qa-full.json), [log](Q02a-integration-artifacts/qa-full.log) |
| Full Pioneer | 934 total: 932 pass, 2 Windows-only skips | 0 | [record](Q02a-integration-artifacts/pioneer-full.json), [log](Q02a-integration-artifacts/pioneer-full.log) |
| Full common | 2 pass, 0 skips | 0 | [record](Q02a-integration-artifacts/common-full.json), [log](Q02a-integration-artifacts/common-full.log) |
| Focused resolver/eval/Q03a/grounding | 71 pass, 0 skips | 0 | [record](Q02a-integration-artifacts/focused.json), [log](Q02a-integration-artifacts/focused.log) |
| Original independent suites | 26 methods pass, 0 skips | 0 | [record](Q02a-integration-artifacts/original-probes.json), [log](Q02a-integration-artifacts/original-probes.log) |
| Additional independent repair scope | 8 pass, 0 skips | 0 | [record](Q02a-integration-artifacts/new-boundaries.json), [log](Q02a-integration-artifacts/new-boundaries.log) |
| Explicit v3 development eval | 12 queries, Recall@5/MRR 10/11; 6 scalar and 9 multi-turn fake controls; provider calls 0 | 0 | [record](Q02a-integration-artifacts/v3-eval.json), [result](Q02a-integration-artifacts/v3-result.json) |

Suites overlap and counts are not additive unique-test totals. The original 26 methods contain a 32-combination positive grammar matrix. Fake multi-turn counters measure the final target turn after mock reset, not entire-conversation usage. Author and independent cross-API runs each passed 6 tests separately; coordinator ran full Pioneer instead of claiming another separate six-test run.

## Reproducibility and retained failures

[run_checks.py](Q02a-integration-artifacts/run_checks.py) pins source/packages identity, records exact argv/cwd/environment paths/runtime/dependencies/time/exit/log and runner hashes, writes artifacts exclusively, and caps subprocesses at 300 seconds. Python 3.12.3, pydantic 2.12.5, PyYAML 6.0.1, MCP 1.29.1 and AnyIO 4.13.0 were observed. Existing API dependencies were reused read-only. QA/focused probes use the reviewed audit-hook launcher denying `.env` reads and Internet connects/DNS. No model, vision, game operation, dependency installation or formal-KB publication occurred.

Integrated v3 result SHA256 `480a448fd7abecfba2f6cd4eb32a46873ff0b8127b6251cd8aeea5e4fe2e82c8` exactly matches the coordinator's premerge replay and author/independent repaired-source results. Historical v1/v2 and original v3 cases remain unchanged; old baselines correctly reject production drift. The actual production commit `90e5168` is independently bound to 186 KB/production entries; format-only commit labels are not authentication or signatures.

[verification.json](Q02a-integration-artifacts/verification.json) binds 17 artifact hashes. Original product red probes, the author's first-full missing-PYTHONPATH error and text-copy trailing-LF mismatch, and the reviewer's pre-test snapshot-default-SHA mistake remain in [author repair](Q02a-repair.md) and [independent recheck](Q02a-CR-recheck.md). The coordinator read the first full log's actual `ModuleNotFoundError: qa_agent` and the separate final 394/OK record; no failure is rewritten as a success. A coordinator log-search command initially used a Windows-incompatible glob path; corrected `rg -g '*full.log'` read the same untouched logs. It was not a test failure or rerun. Raw stdout padding is retained; source/document whitespace checks exclude only raw `.log` files.

## Publication and limitations

Same-repository code/synthetic fixtures/full history/reports/logs/disclosed path metadata are within the independently verified standing user authorization. Initial and repair payload scans found no scoped sensitive-payload blocker; their bounds were fixed commits, not a blanket guarantee about future files. Final CR/coordinator evidence requires the final incremental scan before push. No new confirmation is needed within that authorized route; secrets/private data, other repositories, deployment, account/security changes, paid models and game control remain excluded.

Final incremental scan bound to a071176 completed before push: cumulative 227 Git objects, 16 commits, 119 paths (113 new/six modified); 167 protected paths unchanged, all 42 original raw logs unchanged. No scoped publication blocker was found; finite scanning is not an absolute secret-free proof. Object-set digest: `ba02d741f95f8f507832192fa0c1857d0b6ca5e9b5a29433af58da736ec00685`. Author, independent and coordinator v3 outputs are the same Git blob `a3996426f30053c80754a131863434736ae8ba18`. The payload's initial CI read was run 37351717604/in-progress, not a green result. This status-only successor changes no packages/apps/scripts/workflow source and needs its own final-SHA CI check.

Q02a supports one adjacent text-only follow-up from a finite explicit seed grammar, unique eligible hero citations, full source/history binding and fresh in-memory retrieval. It does not cover arbitrary intent/coreference/refusal semantics, disk KB refresh, whole-KB conflict scanning, real provider quality, human gold, independent holdout, native Windows full-suite validation or production/game execution. After exact-final-SHA CI, the next planned slice is H06a same-checkpoint single-machine ownership/CAS; it has not started.
