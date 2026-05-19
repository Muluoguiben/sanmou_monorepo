from __future__ import annotations

import unittest

from pioneer_agent.runtime.evidence import (
    AdvisorEvidence,
    EvidenceValidationError,
    strategy_snapshot_evidence,
    validate_evidence_entry_ids,
)


class EvidenceValidatorTests(unittest.TestCase):
    def test_accepts_allowed_qa_and_snapshot_entry_ids(self) -> None:
        evidence = [
            AdvisorEvidence(
                evidence_id="qa:building-upgrade",
                source_type="qa",
                ref="qa:building-upgrade",
                entry_id="building-upgrade",
                topic="建筑升级",
            ),
            strategy_snapshot_evidence(
                entry_id="building-main-city",
                topic="主城",
                domain="building",
                summary="主城是多数城建解锁和章节推进的核心建筑之一。",
                source_ref="KB-RULE-BUILDING-001",
                strategy_key="building-main-city",
            ),
        ]

        validate_evidence_entry_ids(
            evidence,
            allowed_entry_ids={"building-upgrade", "building-main-city"},
        )

    def test_rejects_forged_entry_id(self) -> None:
        evidence = [
            strategy_snapshot_evidence(
                entry_id="made-up-entry",
                topic="伪造证据",
                domain="building",
                summary="not in snapshot",
                source_ref=None,
                strategy_key="made-up-entry",
            )
        ]

        with self.assertRaisesRegex(EvidenceValidationError, "not present in allowed"):
            validate_evidence_entry_ids(evidence, allowed_entry_ids={"building-upgrade"})

    def test_rejects_entry_id_from_untrusted_source(self) -> None:
        evidence = [
            AdvisorEvidence(
                evidence_id="state:city.upgradeable_buildings",
                source_type="state",
                ref="city.upgradeable_buildings",
                entry_id="building-upgrade",
            )
        ]

        with self.assertRaisesRegex(EvidenceValidationError, "cannot come from source"):
            validate_evidence_entry_ids(evidence, allowed_entry_ids={"building-upgrade"})


if __name__ == "__main__":
    unittest.main()
