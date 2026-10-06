# Q05a independent preimplementation baseline

Source `3711e92d38786418e8e955d19a56cd6c72611389` in fresh LF checkout
`/tmp/q05a-cr-baseline-3711-20261006`. No author implementation inspected.
Public counterexamples frozen first at `356f09f02ba5fb8923e2bf4f706293edfe21b0dd`;
baseline and resource-warning probes frozen before execution at `c5dcdea`.

All five baseline commands exited 0, using existing dependencies only. Full
argv/cwd/PYTHONPATH/log hashes are in `q05a-independent-baseline-results/summary.json`.

- The independent high-priority wrong-season counterexample is real: old global
  top-2 returns wrong-a/wrong-b, so post-filter S1 is empty; original Retriever on
  the prefiltered S1 pool returns right-low. This proves the planned control can
  distinguish the required ordering, without relying on future implementation.
- Original global SearchIndex rejects a duplicate ID spanning S1 and an unrelated
  S2 entry. Public probes will require the new facade to preserve that precondition.
- Old test_quality_eval: 23 tests passed, zero skips.
- Actual old v3 CLI SHA256:
  `db72e1c3616cadb2062c86a676596c21f1412dfa3ce6691a8f22c9576a259aec`.
- Actual Q04 CLI SHA256:
  `c74e39ee833365f3fb3c6d035c52b230c603da9806e8fa347fa15b2b6fc45120`.
- Original CropIntoColumnsTests.test_splits_and_upscales passed with unchanged
  assertions. warnings.catch_warnings recorded exactly three ResourceWarning
  unclosed-file messages at original test_lineup_frame_extractor.py:172. The
  fixed-mode probe requires the same original test to pass with zero such warnings;
  no warning is relabelled as a functional failure or hidden from the record.

Full v3/Q04 JSONs remain respectively at
`/tmp/q05a-cr-baseline-3711-results/v3.json` and `q04.json` for exact later projection
comparison; their hashes above and raw command logs are preserved. No expected
semantic labels were generated from new implementation output. No new module was
imported or run; absence of its interface is not counted as a product red.

No source/old fixture/gold change, no archive/Q06 body/member/ancestry read,
provider/network/game/bridge/.env/install/push/main change. This is Linux baseline
evidence only, not Q05 native coverage or approval of unreviewed future code.
