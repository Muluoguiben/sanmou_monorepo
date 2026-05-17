from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

import requests
import yaml

from qa_agent.app import discover_bilibili
from qa_agent.app.discover_bilibili import main


class DiscoverBilibiliCliTests(unittest.TestCase):
    def test_discover_bilibili_cli_writes_candidates_and_excludes_known(self) -> None:
        known_bvid = "BV1KNOWN123"
        new_bvid = "BV1NEW45678"
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            known_path = project_root / "knowledge_sources" / "chapter.yaml"
            known_path.parent.mkdir(parents=True)
            known_path.write_text(f"- source_ref: BILIBILI:{known_bvid}#1-2\n", encoding="utf-8")
            output_path = project_root / "candidates.yaml"

            with patch(
                "qa_agent.app.discover_bilibili._fetch_search_page",
                return_value=[
                    {
                        "bvid": known_bvid,
                        "title": "<em class=\"keyword\">三谋</em> 开荒旧视频",
                        "author": "旧UP",
                        "pubdate": 1778774400,
                        "duration": "12:34",
                    },
                    {
                        "bvid": new_bvid,
                        "title": "<em class=\"keyword\">三谋</em> S14 开荒阵容",
                        "author": "新UP",
                        "pubdate": 1778774400,
                        "duration": "1:02:03",
                    },
                ],
            ):
                stdout = io.StringIO()
                with patch.object(
                    sys,
                    "argv",
                    [
                        "discover_bilibili",
                        "--project-root",
                        str(project_root),
                        "--keyword",
                        "三谋 开荒",
                        "--max-pages",
                        "1",
                        "--output",
                        str(output_path),
                    ],
                ):
                    with patch("sys.stdout", stdout):
                        main()

            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["candidate_count"], 1)
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["candidate_count"], 1)
            self.assertEqual(data["candidates"][0]["bvid"], new_bvid)
            self.assertEqual(data["candidates"][0]["title"], "三谋 S14 开荒阵容")
            self.assertEqual(data["candidates"][0]["duration_sec"], 3723)
            self.assertIn("fetch_bilibili_bundle", data["candidates"][0]["fetch_bundle_command"])
            self.assertIn("run_video_pipeline", data["candidates"][0]["pipeline_command"])

    def test_discover_bilibili_cli_filters_by_published_after(self) -> None:
        old_ts = int(datetime(2026, 4, 30, tzinfo=timezone.utc).timestamp())
        new_ts = int(datetime(2026, 5, 2, tzinfo=timezone.utc).timestamp())
        with tempfile.TemporaryDirectory() as temp_dir:
            project_root = Path(temp_dir)
            output_path = project_root / "candidates.json"
            with patch(
                "qa_agent.app.discover_bilibili._fetch_search_page",
                return_value=[
                    {"bvid": "BV1OLD4567", "title": "三谋 旧开荒", "author": "UP", "pubdate": old_ts},
                    {"bvid": "BV1NEW4567", "title": "三谋 新开荒", "author": "UP", "pubdate": new_ts},
                ],
            ):
                with patch.object(
                    sys,
                    "argv",
                    [
                        "discover_bilibili",
                        "--project-root",
                        str(project_root),
                        "--keyword",
                        "三谋 开荒",
                        "--published-after",
                        "2026-05-01",
                        "--max-pages",
                        "1",
                        "--format",
                        "json",
                        "--output",
                        str(output_path),
                    ],
                ):
                    with patch("sys.stdout", io.StringIO()):
                        main()

            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual([item["bvid"] for item in data["candidates"]], ["BV1NEW4567"])

    def test_search_type_412_falls_back_to_all_search_video_group(self) -> None:
        class FakeResponse:
            def __init__(self, status_code: int, payload: dict) -> None:
                self.status_code = status_code
                self._payload = payload

            def raise_for_status(self) -> None:
                if self.status_code >= 400:
                    raise requests.HTTPError(response=self)

            def json(self) -> dict:
                return self._payload

        responses = [
            FakeResponse(412, {"code": -412, "message": "request was banned"}),
            FakeResponse(
                200,
                {
                    "code": 0,
                    "data": {
                        "result": [
                            {"result_type": "tips", "data": []},
                            {"result_type": "video", "data": [{"bvid": "BV1FALLBACK", "title": "三谋开荒"}]},
                        ]
                    },
                },
            ),
        ]

        with patch("qa_agent.app.discover_bilibili.requests.get", side_effect=responses) as mocked_get:
            results = discover_bilibili._fetch_search_page("三谋开荒", 1, "pubdate", {"User-Agent": "test"})

        self.assertEqual(results[0]["bvid"], "BV1FALLBACK")
        self.assertEqual(mocked_get.call_count, 2)


if __name__ == "__main__":
    unittest.main()
