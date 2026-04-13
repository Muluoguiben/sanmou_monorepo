"""Tests for per-tick JSONL logger and screenshot archival."""
from __future__ import annotations

import io
import json
import unittest
from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from PIL import Image

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ExecutionResult, SelectionResult
from pioneer_agent.perception.vision_sync import VisionSyncSummary
from pioneer_agent.storage.loop_logger import LoopLogger


def _png() -> bytes:
    img = Image.new("RGB", (10, 10), (0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class LoopLoggerTests(unittest.TestCase):
    def test_archive_and_jsonl_written(self) -> None:
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            logger = LoopLogger(log_dir)
            action = CandidateAction(
                action_id="u1", action_type=ActionType.UPGRADE_BUILDING,
                params={"building_name": "征兵所"},
            )
            record = logger.log_tick(
                iteration=3,
                started_at=datetime(2026, 4, 14, 12, 0, 0),
                elapsed_s=2.5,
                png=_png(),
                vision_summary=VisionSyncSummary(page_type="city", domains_run=["resource_bar", "city_buildings"], notes=["banner"]),
                selection=SelectionResult(selected_action=action, ranked_actions=[action]),
                execution=ExecutionResult(action_id="u1", status="pending", failure_reason="not calibrated"),
                sleep_s=5.0,
            )

            jsonl = (log_dir / "loop.jsonl").read_text(encoding="utf-8").strip()
            payload = json.loads(jsonl)
            self.assertEqual(payload["iteration"], 3)
            self.assertEqual(payload["page_type"], "city")
            self.assertEqual(payload["domains_run"], ["resource_bar", "city_buildings"])
            self.assertEqual(payload["selected_action_type"], "upgrade_building")
            self.assertEqual(payload["selected_action_params"], {"building_name": "征兵所"})
            self.assertEqual(payload["execution_status"], "pending")
            self.assertEqual(payload["sleep_s"], 5.0)

            self.assertIsNotNone(record.screenshot_path)
            self.assertTrue(Path(record.screenshot_path).exists())
            self.assertIn("20260414T120000-0003.png", record.screenshot_path)

    def test_no_archive_skips_pngs(self) -> None:
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            logger = LoopLogger(log_dir, archive_screenshots=False)
            record = logger.log_tick(
                iteration=0,
                started_at=datetime(2026, 4, 14, 12, 0, 0),
                elapsed_s=1.0,
                png=_png(),
                vision_summary=VisionSyncSummary(page_type="main_map", domains_run=["resource_bar"], notes=[]),
                selection=SelectionResult(selected_action=None),
                execution=None,
                sleep_s=30.0,
            )
            self.assertIsNone(record.screenshot_path)
            self.assertFalse((log_dir / "screenshots").exists())
            # JSONL still produced
            self.assertTrue((log_dir / "loop.jsonl").exists())

    def test_appends_multiple_ticks(self) -> None:
        with TemporaryDirectory() as tmp:
            log_dir = Path(tmp)
            logger = LoopLogger(log_dir, archive_screenshots=False)
            for i in range(3):
                logger.log_tick(
                    iteration=i,
                    started_at=datetime(2026, 4, 14, 12, 0, i),
                    elapsed_s=0.1,
                    png=_png(),
                    vision_summary=VisionSyncSummary(page_type=None, domains_run=[], notes=[]),
                    selection=SelectionResult(selected_action=None),
                    execution=None,
                    sleep_s=1.0,
                )
            lines = (log_dir / "loop.jsonl").read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 3)
            self.assertEqual(json.loads(lines[0])["iteration"], 0)
            self.assertEqual(json.loads(lines[2])["iteration"], 2)


if __name__ == "__main__":
    unittest.main()
