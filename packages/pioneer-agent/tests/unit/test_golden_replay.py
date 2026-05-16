from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from pioneer_agent.runtime.golden_replay import GoldenReplayRunner


class GoldenReplayTests(unittest.TestCase):
    def test_loop_log_and_screenshot_replay_matches_selector_output(self) -> None:
        fixture = _fixture_path("from_real_sync_log.json")

        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            screenshot = log_dir / "screenshots" / "0000.png"
            screenshot.parent.mkdir(parents=True)
            screenshot.write_bytes(b"png")
            _write_loop_record(
                log_dir,
                screenshot_path="screenshots/0000.png",
                selected_action_type="attack_land",
            )

            result = GoldenReplayRunner().run(log_dir=log_dir, state_fixture=fixture)

            self.assertTrue(result.matched)
            self.assertEqual(result.expected_action_type, "attack_land")
            self.assertEqual(result.actual_action_type, "attack_land")
            self.assertEqual(result.screenshot_paths, (str(screenshot),))

    def test_loop_log_replay_reports_selector_mismatch(self) -> None:
        fixture = _fixture_path("from_real_sync_log.json")

        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            screenshot = log_dir / "screenshots" / "0000.png"
            screenshot.parent.mkdir(parents=True)
            screenshot.write_bytes(b"png")
            _write_loop_record(
                log_dir,
                screenshot_path=str(screenshot),
                selected_action_type="wait_for_resource",
            )

            result = GoldenReplayRunner().run(log_dir=log_dir, state_fixture=fixture)

            self.assertFalse(result.matched)
            self.assertEqual(result.expected_action_type, "wait_for_resource")
            self.assertEqual(result.actual_action_type, "attack_land")

    def test_missing_screenshot_fails_replay(self) -> None:
        fixture = _fixture_path("from_real_sync_log.json")

        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            _write_loop_record(
                log_dir,
                screenshot_path="screenshots/missing.png",
                selected_action_type="attack_land",
            )

            with self.assertRaises(FileNotFoundError):
                GoldenReplayRunner().run(log_dir=log_dir, state_fixture=fixture)


def _fixture_path(name: str) -> Path:
    return Path(__file__).resolve().parents[1] / "fixtures" / name


def _write_loop_record(
    log_dir: Path,
    *,
    screenshot_path: str,
    selected_action_type: str,
) -> None:
    payload = {
        "iteration": 0,
        "started_at": "2026-05-17T00:00:00",
        "elapsed_s": 0.1,
        "screenshot_bytes": 3,
        "screenshot_path": screenshot_path,
        "page_type": "main_map",
        "domains_run": ["resource_bar"],
        "notes": [],
        "selected_action_type": selected_action_type,
        "selected_action_id": "golden-action",
        "selected_action_params": {},
        "execution_status": None,
        "execution_failure_reason": None,
        "sleep_s": 5.0,
    }
    with (log_dir / "loop.jsonl").open("w", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
