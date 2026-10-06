# Encoding repair audit scope correction

Initial audit `95deff4` exited 1 before running tests at line 25, where it expected
the complete 3d-to-e0 Git diff to contain only the two test files. The repair branch
also contains the already-authorized docs-only author evidence commit 17e82.
The corrected check allows docs paths and still requires the entire non-doc diff
to be exactly those two test files. Production/fixture/CI trees and the narrowly
defined TextIO-keyword AST comparison remain independently enforced. No product
assertion, file encoding check, test count or result expectation was relaxed.
Original audit source remains in its immutable commit; this is a reviewer scope
check correction, not a product failure or a reason to discard real locale reds.
