from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch


PACKAGE = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("verify_e0_review_v2", PACKAGE / "scripts/verify_e0_review_v2.py")
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class E0ReviewV2Tests(unittest.TestCase):
    def test_current_explicit_freeze_is_offline_without_quality_promotion(self):
        with patch("socket.socket.connect", side_effect=AssertionError("network forbidden")), patch(
                "socket.create_connection", side_effect=AssertionError("network forbidden")), patch(
                "qa_agent.chat.llm_client.build_llm_client", side_effect=AssertionError("provider forbidden")):
            report = verifier.verify()
        self.assertEqual(report["protocol"], "qa-e0-review-prep/v2")
        self.assertEqual(report["baseline"], "v5")
        self.assertEqual(report["provider_calls"], 0)
        self.assertEqual(report["human_reviewed_labels"], 0)
        self.assertFalse(report["human_gold"])
        self.assertFalse(report["independent_holdout"])
        self.assertIsNone(report["quality_threshold"])
        self.assertEqual(report["v5"]["counts"], dict(queries=12, scoring_cases=8, assessment_cases=6, multiturn_cases=9, season_cases=8))
        self.assertEqual(report["execution_authority"], "none")

    def test_manifest_cannot_promote_gold_or_replace_the_source_binding(self):
        expected = verifier._json(verifier.FREEZE)
        original = verifier._json
        for field, value in [("human_gold", True), ("independent_holdout", True),
                             ("quality_threshold", 0.9), ("source_manifest", {})]:
            altered = copy.deepcopy(expected)
            altered[field] = value
            def read(path):
                return altered if path == verifier.FREEZE else original(path)
            with self.subTest(field=field), patch.object(verifier, "_json", side_effect=read), self.assertRaisesRegex(ValueError, "manifest mismatch"):
                verifier.verify()

    def test_exact_current_production_drift_still_fails(self):
        with patch("qa_agent.quality_eval.runner.snapshot", return_value={"digest": "changed"}):
            with self.assertRaisesRegex(ValueError, "source drift"):
                verifier.verify()


if __name__ == "__main__":
    unittest.main()
