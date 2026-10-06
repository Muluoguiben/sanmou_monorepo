# v4 development baseline

The inherited v3 case fields and labels are unchanged, except `version=4`.
Eight additional developer-authored synthetic season controls use manually
declared ordered IDs/reasons, not evaluator-generated expected results.

`freeze.json` was mechanically produced after production commit
`27b73de689cc5863ed02a0dd30526fde8533d080` existed. It binds the complete
production/KB snapshots and cases content; it does not certify human review.
The old v1/v2/v3 freezes remain unchanged and reject the new production tree.
The new season gate is separate from all inherited quality denominators.
