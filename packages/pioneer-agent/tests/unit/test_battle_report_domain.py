from __future__ import annotations

import unittest
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.domains import apply_battle_report, extract_battle_report


@dataclass
class _StubResult:
    data: dict[str, Any]


class _StubVision:
    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        return _StubResult(data=self.payload)


def _complete_payload(report_id: str, **updates: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "page_type": "battle",
        "report_id": report_id,
        "result": "win",
        "occupation_result": "occupied",
        "target_x": 128,
        "target_y": 321,
        "land_level": 7,
        "resource_type": "stone",
        "attacker_initial_soldiers": 21000,
        "attacker_remaining_soldiers": 18450,
        "defender_initial_soldiers": 24000,
        "defender_remaining_soldiers": 0,
        "attacker_heroes": [{"name": "attacker"}],
        "defender_heroes": [{"name": "defender"}],
        "key_events": [],
        "visible_sections": ["summary"],
        "visible_notes": [],
    }
    payload.update(updates)
    return payload


class BattleReportDomainTests(unittest.TestCase):
    def test_complete_parse_is_still_not_action_verification(self) -> None:
        fragment = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-1")),
            captured_at=datetime(2026, 7, 10, 12, 0, 0),
        )
        report = fragment.map_state["latest_battle_report"]
        verification = report["verification"]

        self.assertEqual(report["attacker_losses"], 2550)
        self.assertEqual(report["defender_losses"], 24000)
        self.assertEqual(verification["parse_status"], "complete")
        self.assertFalse(verification["action_verification_ready"])
        self.assertEqual(verification["verifier_status"], "unverified")

    def test_partial_parse_is_unverified(self) -> None:
        fragment = extract_battle_report(
            b"png",
            client=_StubVision(
                {
                    "page_type": "battle",
                    "result": "win",
                    "occupation_result": "unknown",
                    "attacker_heroes": [],
                    "defender_heroes": [],
                    "key_events": [],
                    "visible_sections": [],
                    "visible_notes": ["victory marker only"],
                }
            ),
            captured_at=datetime(2026, 7, 10, 12, 0, 0),
        )
        report = fragment.map_state["latest_battle_report"]
        verification = fragment.map_state["battle_report_verification"]

        self.assertEqual(report["result"], "win")
        self.assertEqual(report["occupation_result"], "unknown")
        self.assertEqual(verification["parse_status"], "partial")
        self.assertFalse(verification["action_verification_ready"])
        self.assertEqual(verification["verifier_status"], "unverified")

    def test_older_report_enters_history_but_does_not_replace_latest(self) -> None:
        newer_at = datetime(2026, 7, 10, 12, 0, 0)
        older_at = newer_at - timedelta(seconds=1)
        newer = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-new")),
            captured_at=newer_at,
        )
        older = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-old")),
            captured_at=older_at,
        )

        state = apply_battle_report(RuntimeState(), newer)
        state = apply_battle_report(state, older)

        self.assertEqual(state.map_state["latest_battle_report"]["report_id"], "br-new")
        self.assertEqual(
            {report["report_id"] for report in state.map_state["battle_reports"]},
            {"br-new", "br-old"},
        )
        self.assertEqual(
            state.field_meta["map_state.latest_battle_report"].updated_at,
            newer_at,
        )

    def test_older_same_report_does_not_degrade_history(self) -> None:
        newer_at = datetime(2026, 7, 10, 12, 0, 0)
        newer = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-same", experience_gained=7200)),
            captured_at=newer_at,
        )
        older = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-same", experience_gained=100)),
            captured_at=newer_at - timedelta(seconds=1),
        )

        state = apply_battle_report(RuntimeState(), newer)
        state = apply_battle_report(state, older)

        self.assertEqual(len(state.map_state["battle_reports"]), 1)
        self.assertEqual(state.map_state["battle_reports"][0]["experience_gained"], 7200)
        self.assertEqual(state.map_state["latest_battle_report"]["experience_gained"], 7200)

    def test_unknown_secondary_parse_does_not_mutate_report_state(self) -> None:
        prior = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-prior")),
            captured_at=datetime(2026, 7, 10, 12, 0, 0),
        )
        state = apply_battle_report(RuntimeState(), prior)
        unknown = extract_battle_report(
            b"png",
            client=_StubVision(
                {
                    "page_type": "unknown",
                    "result": "unknown",
                    "occupation_result": "unknown",
                    "attacker_heroes": [],
                    "defender_heroes": [],
                    "key_events": [],
                    "visible_sections": [],
                    "visible_notes": ["secondary classifier disagreed"],
                }
            ),
            captured_at=datetime(2026, 7, 10, 12, 0, 1),
        )

        self.assertEqual(unknown.map_state, {})
        state = apply_battle_report(state, unknown)
        self.assertEqual(state.map_state["latest_battle_report"]["report_id"], "br-prior")
        self.assertEqual(len(state.map_state["battle_reports"]), 1)

    def test_inconsistent_troop_measurement_is_partial_not_safe_zero(self) -> None:
        fragment = extract_battle_report(
            b"png",
            client=_StubVision(
                _complete_payload(
                    "br-conflict",
                    attacker_initial_soldiers=100,
                    attacker_remaining_soldiers=200,
                )
            ),
            captured_at=datetime(2026, 7, 10, 12, 0, 0),
        )
        report = fragment.map_state["latest_battle_report"]

        self.assertNotIn("attacker_losses", report)
        self.assertNotIn("attacker_loss_ratio", report)
        self.assertIn("attacker_total_inconsistent", report["measurement_issues"])
        self.assertEqual(report["verification"]["parse_status"], "partial")
        self.assertEqual(
            report["verification"]["checks"]["loss_consistency"],
            "inconsistent",
        )

    def test_explicit_loss_mismatch_is_partial(self) -> None:
        fragment = extract_battle_report(
            b"png",
            client=_StubVision(
                _complete_payload(
                    "br-mismatch",
                    attacker_initial_soldiers=100,
                    attacker_remaining_soldiers=80,
                    attacker_losses=10,
                    attacker_heroes=[
                        {
                            "name": "a",
                            "initial_soldiers": 50,
                            "remaining_soldiers": 45,
                        },
                        {
                            "name": "b",
                            "initial_soldiers": 50,
                            "remaining_soldiers": 45,
                        },
                    ],
                )
            ),
            captured_at=datetime(2026, 7, 10, 12, 0, 0),
        )
        report = fragment.map_state["latest_battle_report"]

        self.assertIn("attacker_total_inconsistent", report["measurement_issues"])
        self.assertEqual(report["verification"]["parse_status"], "partial")

    def test_hero_loss_sum_mismatch_is_partial(self) -> None:
        fragment = extract_battle_report(
            b"png",
            client=_StubVision(
                _complete_payload(
                    "br-hero-sum",
                    attacker_initial_soldiers=100,
                    attacker_remaining_soldiers=80,
                    attacker_losses=20,
                    attacker_heroes=[
                        {
                            "name": "a",
                            "initial_soldiers": 50,
                            "remaining_soldiers": 45,
                        },
                        {
                            "name": "b",
                            "initial_soldiers": 50,
                            "remaining_soldiers": 45,
                        },
                    ],
                )
            ),
            captured_at=datetime(2026, 7, 10, 12, 0, 0),
        )
        report = fragment.map_state["latest_battle_report"]

        self.assertIn("attacker_hero_loss_sum_mismatch", report["measurement_issues"])
        self.assertEqual(report["verification"]["parse_status"], "partial")

    def test_mixed_timezone_same_report_cannot_overwrite_history_or_latest(self) -> None:
        newer = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-mixed", experience_gained=7200)),
            captured_at=datetime(2026, 7, 10, 4, 0, 0, tzinfo=timezone.utc),
        )
        ambiguous = extract_battle_report(
            b"png",
            client=_StubVision(_complete_payload("br-mixed", experience_gained=100)),
            captured_at=datetime(2026, 7, 10, 13, 0, 0),
        )

        state = apply_battle_report(RuntimeState(), newer)
        state = apply_battle_report(state, ambiguous)

        self.assertEqual(state.map_state["latest_battle_report"]["experience_gained"], 7200)
        self.assertEqual(state.map_state["battle_reports"][0]["experience_gained"], 7200)


if __name__ == "__main__":
    unittest.main()
