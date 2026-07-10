from __future__ import annotations

import unittest
from copy import deepcopy
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.runbook.attack_ledger import AttackLedger


def _report(
    report_id: str,
    captured_at: str,
    *,
    result: str = "loss",
    occupation_result: str = "failed",
    loss_ratio: float | None = 0.2,
    land_level: int | None = 6,
    identity_source: str = "explicit",
    identity_confidence: str = "high",
    action_verified: bool = False,
    **updates: Any,
) -> dict[str, Any]:
    verification = {
        "parse_status": "complete",
        "checks": {"loss_consistency": "not_conflicted"},
        "action_verification_ready": action_verified,
        "verifier_status": "verified" if action_verified else "unverified",
    }
    payload: dict[str, Any] = {
        "report_id": report_id,
        "report_id_source": identity_source,
        "report_identity_confidence": identity_confidence,
        "captured_at": captured_at,
        "result": result,
        "occupation_result": occupation_result,
        "attacker_loss_ratio": loss_ratio,
        "land_level": land_level,
        "verification": verification,
    }
    payload.update(updates)
    return payload


class AttackLedgerTests(unittest.TestCase):
    def test_deduplicates_by_report_id_keeps_newest_and_sorts(self) -> None:
        state = RuntimeState(
            map_state={
                "battle_reports": [
                    _report("br-2", "2026-07-10T12:02:00", loss_ratio=0.2),
                    _report("br-1", "2026-07-10T12:00:00", loss_ratio=0.1),
                    _report("br-1", "2026-07-10T12:03:00", loss_ratio=0.3),
                ]
            }
        )

        ledger = AttackLedger.from_runtime_state(state)

        self.assertEqual([report.report_id for report in ledger.reports], ["br-2", "br-1"])
        self.assertEqual(ledger.runbook_metrics()["battle_loss_rate"], 0.3)
        self.assertEqual(ledger.runbook_metrics()["consecutive_defeats"], 2)

    def test_latest_state_copy_participates_in_deduplication(self) -> None:
        state = RuntimeState(
            map_state={
                "battle_reports": [_report("br-1", "2026-07-10T12:00:00", loss_ratio=0.1)],
                "latest_battle_report": _report(
                    "br-1", "2026-07-10T12:01:00", loss_ratio=0.4
                ),
            }
        )

        ledger = AttackLedger.from_runtime_state(state)

        self.assertEqual(len(ledger.reports), 1)
        self.assertEqual(ledger.runbook_metrics()["battle_loss_rate"], 0.4)

    def test_skips_malformed_reports(self) -> None:
        state = RuntimeState(
            map_state={
                "battle_reports": [
                    None,
                    "bad",
                    {},
                    _report("", "2026-07-10T12:00:00"),
                    _report("bad-time", "not-a-time"),
                    _report("bad-result", "2026-07-10T12:00:00", result="victory"),
                    _report("valid", "2026-07-10T12:01:00"),
                ]
            }
        )

        ledger = AttackLedger.from_runtime_state(state)

        self.assertEqual([report.report_id for report in ledger.reports], ["valid"])
        self.assertEqual(ledger.skipped_reports, 6)

    def test_derives_bounded_loss_ratio_from_counts(self) -> None:
        report = _report("br-counts", "2026-07-10T12:00:00", loss_ratio=None)
        report.update(attacker_losses=250, attacker_initial_soldiers=1000)
        metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": [report]})
        ).runbook_metrics()

        self.assertEqual(metrics["battle_loss_rate"], 0.25)

        report["attacker_loss_ratio"] = 1.5
        invalid_metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": [report]})
        ).runbook_metrics()
        self.assertNotIn("battle_loss_rate", invalid_metrics)

    def test_ratio_with_partial_or_conflicting_legacy_counts_is_withheld(self) -> None:
        partial = _report(
            "br-partial-counts",
            "2026-07-10T12:00:00",
            loss_ratio=0.1,
            attacker_losses=100,
        )
        conflicting = _report(
            "br-conflicting-counts",
            "2026-07-10T12:01:00",
            loss_ratio=0.1,
            attacker_losses=500,
            attacker_initial_soldiers=1000,
        )

        partial_metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": [partial]})
        ).runbook_metrics()
        conflicting_metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": [conflicting]})
        ).runbook_metrics()

        self.assertNotIn("battle_loss_rate", partial_metrics)
        self.assertNotIn("battle_loss_rate", conflicting_metrics)

    def test_legacy_ratio_conflicting_with_counts_is_withheld(self) -> None:
        report = _report("br-conflict", "2026-07-10T12:00:00", loss_ratio=0.1)
        report.update(attacker_losses=500, attacker_initial_soldiers=1000)

        metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": [report]})
        ).runbook_metrics()

        self.assertNotIn("battle_loss_rate", metrics)

    def test_latest_unknown_does_not_fabricate_zero_defeats(self) -> None:
        state = RuntimeState(
            map_state={
                "battle_reports": [
                    _report("br-loss", "2026-07-10T12:00:00"),
                    _report(
                        "br-unknown",
                        "2026-07-10T12:01:00",
                        result="unknown",
                        occupation_result="unknown",
                        loss_ratio=None,
                    ),
                ]
            }
        )

        metrics = AttackLedger.from_runtime_state(state).runbook_metrics()

        self.assertNotIn("consecutive_defeats", metrics)

    def test_synthetic_identity_is_not_counted_as_an_exact_attempt(self) -> None:
        synthetic = _report(
            "vision-fingerprint",
            "2026-07-10T12:00:00",
            result="win",
            occupation_result="occupied",
            loss_ratio=0.42,
            land_level=9,
            identity_source="content_fingerprint",
            identity_confidence="low",
            action_verified=True,
        )

        metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": [synthetic]})
        ).runbook_metrics()

        # Loss is a safety observation and does not require exact action identity.
        self.assertEqual(metrics["battle_loss_rate"], 0.42)
        self.assertNotIn("consecutive_defeats", metrics)
        self.assertNotIn("highest_land_level_cleared", metrics)

    def test_confirmed_recent_losses_survive_older_low_confidence_history(self) -> None:
        reports = [
            _report(
                "vision-older",
                "2026-07-10T11:59:00",
                identity_source="content_fingerprint",
                identity_confidence="low",
            ),
            _report("br-loss-1", "2026-07-10T12:00:00"),
            _report("br-loss-2", "2026-07-10T12:01:00"),
        ]

        metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": reports})
        ).runbook_metrics()

        self.assertEqual(metrics["consecutive_defeats"], 2)

    def test_highest_land_requires_precise_identity_and_action_verification(self) -> None:
        reports = [
            _report(
                "unverified-9",
                "2026-07-10T12:00:00",
                result="win",
                occupation_result="occupied",
                land_level=9,
            ),
            _report(
                "verified-7",
                "2026-07-10T12:01:00",
                result="win",
                occupation_result="occupied",
                land_level=7,
                action_verified=True,
            ),
            _report(
                "verified-loss-10",
                "2026-07-10T12:02:00",
                result="loss",
                occupation_result="failed",
                land_level=10,
                action_verified=True,
            ),
        ]

        metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": reports})
        ).runbook_metrics()

        self.assertEqual(metrics["highest_land_level_cleared"], 7)

    def test_mixed_timestamp_kinds_use_risk_conservative_bounds(self) -> None:
        state = RuntimeState(
            map_state={
                "battle_reports": [
                    _report("aware", "2026-07-10T04:00:00+00:00", loss_ratio=0.2),
                    _report("naive", "2026-07-10T13:00:00", loss_ratio=0.5),
                ]
            }
        )

        ledger = AttackLedger.from_runtime_state(state)
        metrics = ledger.runbook_metrics()

        self.assertFalse(ledger.ordering_trusted)
        self.assertEqual(metrics["battle_loss_rate"], 0.5)
        self.assertEqual(metrics["consecutive_defeats"], 2)

    def test_mixed_order_upper_bound_excludes_synthetic_identity(self) -> None:
        reports = [
            _report("explicit", "2026-07-10T04:00:00+00:00", loss_ratio=0.3),
            _report(
                "vision-low",
                "2026-07-10T13:00:00",
                loss_ratio=0.8,
                identity_source="content_fingerprint",
                identity_confidence="low",
            ),
        ]

        metrics = AttackLedger.from_runtime_state(
            RuntimeState(map_state={"battle_reports": reports})
        ).runbook_metrics()

        self.assertEqual(metrics["battle_loss_rate"], 0.8)
        self.assertEqual(metrics["consecutive_defeats"], 1)

    def test_same_id_with_incomparable_timestamps_merges_as_one_risky_attempt(self) -> None:
        state = RuntimeState(
            map_state={
                "battle_reports": [
                    _report(
                        "br-mixed",
                        "2026-07-10T04:00:00+00:00",
                        result="win",
                        occupation_result="occupied",
                        loss_ratio=0.1,
                        land_level=8,
                        action_verified=True,
                    ),
                    _report(
                        "br-mixed",
                        "2026-07-10T13:00:00",
                        result="loss",
                        occupation_result="failed",
                        loss_ratio=0.6,
                    ),
                ]
            }
        )

        ledger = AttackLedger.from_runtime_state(state)
        metrics = ledger.runbook_metrics()

        self.assertEqual(len(ledger.reports), 1)
        self.assertEqual(ledger.ambiguous_report_ids, ("br-mixed",))
        self.assertTrue(ledger.reports[0].time_ambiguous)
        self.assertEqual(ledger.reports[0].result, "loss")
        self.assertFalse(ledger.reports[0].action_verified)
        self.assertEqual(metrics["battle_loss_rate"], 0.6)
        self.assertEqual(metrics["consecutive_defeats"], 1)
        self.assertNotIn("highest_land_level_cleared", metrics)

    def test_aggregation_does_not_mutate_runtime_state(self) -> None:
        state = RuntimeState(
            map_state={"battle_reports": [_report("br-1", "2026-07-10T12:00:00")]}
        )
        before = deepcopy(state.model_dump(mode="python"))

        AttackLedger.from_runtime_state(state).runbook_metrics()

        self.assertEqual(state.model_dump(mode="python"), before)


if __name__ == "__main__":
    unittest.main()
