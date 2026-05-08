from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from qa_agent.app.fetch_bilibili_bundle import main


class FetchBilibiliBundleCliTests(unittest.TestCase):
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_view_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_conclusion_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_catalog")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_body")
    def test_fetch_bilibili_bundle_cli_writes_bundle(self, mocked_subtitle_body, mocked_subtitle_catalog, mocked_conclusion, mocked_fetch_view) -> None:
        mocked_fetch_view.return_value = {
            "bvid": "BV1TEST123",
            "title": "［S1开荒］测试视频",
            "owner": {"name": "测试UP"},
            "desc": "这是描述",
            "pubdate": 1765769779,
            "duration": 305,
            "cid": 123456,
            "pages": [{"first_frame": "http://example.com/frame.jpg"}],
        }
        mocked_conclusion.return_value = None
        mocked_subtitle_catalog.return_value = [{"lan": "ai-zh", "lan_doc": "中文", "subtitle_url": ""}]
        mocked_subtitle_body.return_value = [
            {"from": 0.0, "to": 2.0, "content": "S1开荒阵容推荐"},
            {"from": 2.0, "to": 4.0, "content": "三谋测试字幕"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "bundle.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "fetch_bilibili_bundle",
                    "--url",
                    "https://www.bilibili.com/video/BV1TEST123/",
                    "--output",
                    str(output_path),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["bvid"], "BV1TEST123")
            self.assertEqual(summary["subtitle_catalog_size"], 1)
            self.assertEqual(summary["segment_count"], 1)
            self.assertEqual(summary["subtitle_line_count"], 2)
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["source"]["video_id"], "BV1TEST123")
            self.assertEqual(data["source"]["subtitle_catalog"][0]["lan"], "ai-zh")
            self.assertIn("S1开荒阵容推荐", data["segments"][0]["transcript_lines"])
            self.assertEqual(data["segments"][0]["title"], "subtitle-chunk-1")

    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_view_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_conclusion_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_catalog")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_body")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_asr_body")
    def test_fetch_bilibili_bundle_cli_uses_asr_fallback(
        self,
        mocked_fetch_asr_body,
        mocked_fetch_subtitle_body,
        mocked_subtitle_catalog,
        mocked_conclusion,
        mocked_fetch_view,
    ) -> None:
        mocked_fetch_view.return_value = {
            "bvid": "BV1TEST123",
            "title": "［S1开荒］测试视频",
            "owner": {"name": "测试UP"},
            "desc": "这是描述",
            "pubdate": 1765769779,
            "duration": 305,
            "cid": 123456,
            "pages": [{"first_frame": "http://example.com/frame.jpg"}],
        }
        mocked_conclusion.return_value = None
        mocked_subtitle_catalog.return_value = [{"lan": "ai-zh", "lan_doc": "中文", "subtitle_url": "https://example.com/sub.json"}]
        mocked_fetch_subtitle_body.return_value = []
        mocked_fetch_asr_body.return_value = [
            {"from": 0.0, "to": 3.0, "content": "三谋开荒阵容"},
            {"from": 3.0, "to": 6.0, "content": "诸葛亮刘备黄月英"},
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "bundle.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "fetch_bilibili_bundle",
                    "--url",
                    "https://www.bilibili.com/video/BV1TEST123/",
                    "--output",
                    str(output_path),
                    "--asr-fallback",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            summary = json.loads(stdout.getvalue())
            self.assertTrue(summary["asr_used"])
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(len(data["segments"]), 1)
            self.assertIn("三谋开荒阵容", data["segments"][0]["transcript_lines"])

    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_view_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_conclusion_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_catalog")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_body")
    def test_fetch_bilibili_bundle_cli_prefers_conclusion_subtitles(
        self,
        mocked_subtitle_body,
        mocked_subtitle_catalog,
        mocked_conclusion,
        mocked_fetch_view,
    ) -> None:
        mocked_fetch_view.return_value = {
            "bvid": "BV1TEST123",
            "title": "［S1开荒］测试视频",
            "owner": {"name": "测试UP"},
            "desc": "这是描述",
            "pubdate": 1765769779,
            "duration": 305,
            "cid": 123456,
            "pages": [{"first_frame": "http://example.com/frame.jpg"}],
        }
        mocked_conclusion.return_value = {
            "summary": "S1开荒总结",
            "outline": [{"title": "test"}],
            "subtitle": [
                {
                    "part_subtitle": [
                        {"start_timestamp": 10, "end_timestamp": 12, "content": "S1开荒推荐孙权小乔周瑜"},
                        {"start_timestamp": 12, "end_timestamp": 15, "content": "苦肉弓三十五级以后使用"},
                    ]
                }
            ],
        }
        mocked_subtitle_catalog.return_value = []
        mocked_subtitle_body.return_value = []

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "bundle.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "fetch_bilibili_bundle",
                    "--url",
                    "https://www.bilibili.com/video/BV1TEST123/",
                    "--output",
                    str(output_path),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["subtitle_line_count"], 2)
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["source"]["ai_summary"], "S1开荒总结")
            self.assertEqual(data["segments"][0]["title"], "subtitle-chunk-1")
            self.assertIn("S1开荒推荐孙权小乔周瑜", data["segments"][0]["transcript_lines"])

    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_view_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_conclusion_data")
    def test_fetch_bilibili_bundle_cli_applies_video_text_corrections(self, mocked_conclusion, mocked_fetch_view) -> None:
        mocked_fetch_view.return_value = {
            "bvid": "BV1Z5myBqEGV",
            "title": "［S1开荒］测试视频",
            "owner": {"name": "测试UP"},
            "desc": "这是描述",
            "pubdate": 1765769779,
            "duration": 305,
            "cid": 123456,
            "pages": [{"first_frame": "http://example.com/frame.jpg"}],
        }
        mocked_conclusion.return_value = {
            "summary": "苦肉弓与钟一弓",
            "outline": [],
            "subtitle": [
                {
                    "part_subtitle": [
                        {"start_timestamp": 10, "end_timestamp": 12, "content": "苦肉弓三十五级以后使用"},
                    ]
                }
            ],
        }

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "bundle.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "fetch_bilibili_bundle",
                    "--bvid",
                    "BV1Z5myBqEGV",
                    "--output",
                    str(output_path),
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["source"]["ai_summary"], "忠义弓与忠义弓")
            self.assertIn("忠义弓三十五级以后使用", data["segments"][0]["transcript_lines"])


    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_view_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_conclusion_data")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_catalog")
    @patch("qa_agent.app.fetch_bilibili_bundle._fetch_subtitle_body")
    @patch("qa_agent.app.fetch_bilibili_bundle._sample_frames_for_bundle")
    def test_fetch_bilibili_bundle_cli_with_frames(
        self,
        mocked_sample_frames,
        mocked_fetch_subtitle_body,
        mocked_subtitle_catalog,
        mocked_conclusion,
        mocked_fetch_view,
    ) -> None:
        from qa_agent.video import VideoFrameRef

        mocked_fetch_view.return_value = {
            "bvid": "BV1TESTF00",
            "title": "［S14开荒］测试视频",
            "owner": {"name": "测试UP"},
            "desc": "描述",
            "pubdate": 1765769779,
            "duration": 120,
            "cid": 999,
            "pages": [{"first_frame": "http://example.com/frame.jpg"}],
        }
        mocked_conclusion.return_value = None
        mocked_subtitle_catalog.return_value = [{"lan": "ai-zh", "lan_doc": "中文", "subtitle_url": ""}]
        mocked_fetch_subtitle_body.return_value = [
            {"from": 0.0, "to": 20.0, "content": "三谋开荒第一段"},
            {"from": 20.0, "to": 50.0, "content": "三谋开荒第二段"},
            {"from": 50.0, "to": 110.0, "content": "三谋开荒第三段"},
        ]
        mocked_sample_frames.return_value = [
            VideoFrameRef(timestamp_sec=0.0, image_path="/tmp/frame-1.jpg", notes=[]),
            VideoFrameRef(timestamp_sec=30.0, image_path="/tmp/frame-2.jpg", notes=[]),
            VideoFrameRef(timestamp_sec=60.0, image_path="/tmp/frame-3.jpg", notes=[]),
        ]

        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "bundle.yaml"
            stdout = io.StringIO()
            with patch.object(
                sys,
                "argv",
                [
                    "fetch_bilibili_bundle",
                    "--bvid",
                    "BV1TESTF00",
                    "--output",
                    str(output_path),
                    "--with-frames",
                ],
            ):
                with patch("sys.stdout", stdout):
                    main()
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["frame_count"], 3)
            self.assertTrue(mocked_sample_frames.called)
            data = yaml.safe_load(output_path.read_text(encoding="utf-8"))
            segments = data["segments"]
            all_paths: set[str] = set()
            for segment in segments:
                all_paths.update(segment.get("frame_paths") or [])
            for expected in ("/tmp/frame-1.jpg", "/tmp/frame-2.jpg", "/tmp/frame-3.jpg"):
                self.assertIn(expected, all_paths)
            # Frame at t=60 must land in a segment whose end_sec > 50.
            for segment in segments:
                if "/tmp/frame-3.jpg" in (segment.get("frame_paths") or []):
                    self.assertGreaterEqual(float(segment["end_sec"]), 60.0)
                    break
            else:
                self.fail("frame-3 not attached to any segment")


if __name__ == "__main__":
    unittest.main()
