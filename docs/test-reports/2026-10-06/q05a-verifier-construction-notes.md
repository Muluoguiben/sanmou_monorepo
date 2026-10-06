# Reviewer verifier construction note

Initial verifier commit `cf4722d` stopped before test execution (exit 1) on:

```text
q05a-independent-verify.py, line 66
assert ast.dump(new_methods[name]) in {ast.dump(old), ast.dump(VersionMigration().visit(copy.deepcopy(old)))}, name
AssertionError: test_manifest_metadata_rejects_version_split_and_duplicate_ids
```

This was a reviewer AST normalization omission, not a product finding. The
approved literal migration includes the exact fixture path string
`tests/fixtures/quality_eval/v3` to `tests/fixtures/quality_eval/v4`, whereas the
initial verifier normalized only the standalone string `v3`. Static diff had
already shown this authorized path update. The correction adds that one exact
literal mapping; old assertion ASTs and all other strings remain protected.
Original verifier source remains in its immutable commit. No product source or
test assertion was changed, and no baseline/source failure was counted as pass.
