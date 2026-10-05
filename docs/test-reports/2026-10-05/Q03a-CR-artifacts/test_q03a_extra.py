"""Additional independently scoped boundary reproducers; retained even when red."""
from test_independent_q03a import *


class ApplicabilityBoundaryTests(unittest.TestCase):
    def test_explicit_disjoint_applicability_in_notes_is_not_hard_conflict(self):
        a = profile("review-a", base=20, notes=("本记录数值仅适用于 S1",))
        b = profile("review-b", base=30, notes=("本记录数值仅适用于 S2",))
        reply, client = invoke("丙将初始武力是多少", [a, b])
        self.assertEqual(reply.assessment.check_scope, "unassessed",
            msg=reply.assessment.model_dump_json() + " ANSWER=" + reply.answer)

    def test_historical_commit_label_is_not_verified_by_runner(self):
        result = EvaluationIndependentTests().transformed_run(
            freeze_change=lambda f: f.update(baseline_commit="0" * 40))
        # This records a verified LIMITATION, not a claim that the actual freeze is false.
        self.assertEqual(result["baseline_commit"], "0" * 40)
