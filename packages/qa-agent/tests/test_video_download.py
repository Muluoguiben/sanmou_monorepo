from __future__ import annotations

import unittest
from unittest.mock import patch

from qa_agent.video.video_download import fetch_bilibili_video_urls


class BilibiliVideoDownloadTests(unittest.TestCase):
    @patch("qa_agent.video.video_download.requests.get")
    def test_fetch_bilibili_video_urls_returns_base_and_backups_low_quality_first(self, mocked_get) -> None:
        mocked_get.return_value.json.return_value = {
            "data": {
                "dash": {
                    "video": [
                        {
                            "id": 64,
                            "codecs": "hev1",
                            "baseUrl": "https://example.com/high.m4s",
                            "backupUrl": ["https://example.com/high-backup.m4s"],
                        },
                        {
                            "id": 16,
                            "codecs": "avc1.64001F",
                            "baseUrl": "https://example.com/low.m4s",
                            "backupUrl": ["https://example.com/low-backup.m4s"],
                        },
                    ]
                }
            }
        }
        mocked_get.return_value.raise_for_status.return_value = None

        urls = fetch_bilibili_video_urls(
            bvid="BV1TEST",
            cid=123,
            cookie_header="SESSDATA=test",
            source_url="https://www.bilibili.com/video/BV1TEST/",
        )

        self.assertEqual([item.url for item in urls], [
            "https://example.com/low.m4s",
            "https://example.com/low-backup.m4s",
            "https://example.com/high.m4s",
            "https://example.com/high-backup.m4s",
        ])
        self.assertEqual(urls[0].quality_id, 16)
        self.assertEqual(urls[0].source, "base")


if __name__ == "__main__":
    unittest.main()
