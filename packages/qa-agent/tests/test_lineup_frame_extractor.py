import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qa_agent.video.lineup_frame_extractor import (  # noqa: E402
    BackfillStats,
    FrameRef,
    LineupFrameExtractor,
    collect_frames_from_bundle,
    frames_in_window,
    looks_like_lineup_segment,
    parse_frame_timestamp,
)


@dataclass
class _Ent:
    name: str


@dataclass
class _Vis:
    heroes: list = field(default_factory=list)
    skills: list = field(default_factory=list)
    text_snippets: list = field(default_factory=list)


class _FakeExtractor:
    def __init__(self, mapping=None, fail=False):
        self._mapping = mapping or {}
        self._fail = fail
        self.calls = []

    def extract(self, image_urls, *, question=None):
        self.calls.append(list(image_urls))
        if self._fail:
            raise RuntimeError("simulated vision outage")
        key = tuple(sorted(image_urls))
        h, s = self._mapping.get(key, ([], []))
        return _Vis(heroes=[_Ent(x) for x in h], skills=[_Ent(x) for x in s])


class ParseFrameTimestampTests(unittest.TestCase):
    def test_standard_name(self):
        self.assertEqual(
            parse_frame_timestamp("/t/BV1x-frame-002-20s.jpg"), 20.0
        )

    def test_float_seconds(self):
        self.assertEqual(
            parse_frame_timestamp("/t/BV1x-frame-010-135.5s.png"), 135.5
        )

    def test_non_frame_url_returns_none(self):
        self.assertIsNone(
            parse_frame_timestamp("http://i1.hdslb.com/bfs/storyff/x_firsti.jpg")
        )


class CollectFramesTests(unittest.TestCase):
    def test_skips_story_urls_keeps_local_sorted(self):
        bundle = {
            "segments": [
                {
                    "start_sec": 0.0,
                    "frame_paths": [
                        "http://i1.hdslb.com/bfs/storyff/x_firsti.jpg",
                        "/t/BV1x-frame-003-40s.jpg",
                        "/t/BV1x-frame-001-0s.jpg",
                    ],
                },
                {
                    "start_sec": 60.0,
                    "frame_paths": ["/t/BV1x-frame-004-60s.jpg"],
                },
            ]
        }
        frames = collect_frames_from_bundle(bundle)
        self.assertEqual(
            [f.timestamp_sec for f in frames], [0.0, 40.0, 60.0]
        )
        self.assertTrue(all(f.is_local for f in frames))


class FramesInWindowTests(unittest.TestCase):
    def setUp(self):
        self.frames = [FrameRef(f"/t/f{t}.jpg", float(t)) for t in range(0, 200, 20)]

    def test_window_with_margin(self):
        got = frames_in_window(self.frames, 80, 100, margin_sec=8)
        self.assertEqual(sorted(f.timestamp_sec for f in got), [80.0, 100.0])

    def test_subsamples_when_over_cap(self):
        got = frames_in_window(self.frames, 0, 200, margin_sec=0, max_frames=3)
        self.assertEqual(len(got), 3)


class LooksLikeLineupTests(unittest.TestCase):
    def test_positive(self):
        self.assertTrue(looks_like_lineup_segment("这是第一队首发阵容", []))

    def test_negative(self):
        self.assertFalse(looks_like_lineup_segment("今天天气不错", []))


class BackfillTests(unittest.TestCase):
    def _staging(self):
        return [
            {
                "entry": {
                    "topic": "S14 空队",
                    "source_ref": "BILIBILI:BV1x#40-60",
                    "structured_data": {
                        "name": "S14 空队",
                        "hero_names": [],
                        "core_skills": [],
                    },
                }
            },
            {
                "entry": {
                    "topic": "S14 已满队",
                    "source_ref": "BILIBILI:BV1x#40-60",
                    "structured_data": {
                        "name": "S14 已满队",
                        "hero_names": ["周瑜"],
                        "core_skills": ["践墨随敌"],
                    },
                }
            },
        ]

    def _bundle(self):
        return {
            "segments": [
                {"start_sec": 40.0, "frame_paths": ["/t/BV1x-frame-003-40s.jpg"]},
                {"start_sec": 60.0, "frame_paths": ["/t/BV1x-frame-004-60s.jpg"]},
            ]
        }

    def test_fills_only_empty_and_canonicalizes(self):
        fake = _FakeExtractor(
            mapping={
                ("/t/BV1x-frame-003-40s.jpg", "/t/BV1x-frame-004-60s.jpg"): (
                    ["黄府松"],
                    ["金汤"],
                )
            }
        )
        canon = {"黄府松": "皇甫嵩", "金汤": "金城汤池"}.get
        ex = LineupFrameExtractor(
            fake, canonicalize=lambda s: canon(s) or s
        )
        staging, stats = ex.backfill_entries(
            self._staging(), {"BV1x": self._bundle()}
        )
        empty_sd = staging[0]["entry"]["structured_data"]
        self.assertEqual(empty_sd["hero_names"], ["皇甫嵩"])
        self.assertEqual(empty_sd["core_skills"], ["金城汤池"])
        self.assertTrue(any("阵容图抽取" in n for n in empty_sd["notes"]))
        # existing values untouched
        full_sd = staging[1]["entry"]["structured_data"]
        self.assertEqual(full_sd["hero_names"], ["周瑜"])
        self.assertNotIn("notes", full_sd)
        self.assertEqual(stats.entries_filled_hero, 1)
        self.assertEqual(stats.entries_filled_skill, 1)
        self.assertEqual(stats.entries_targeted, 1)

    def test_vision_failure_is_fail_open(self):
        ex = LineupFrameExtractor(_FakeExtractor(fail=True))
        staging, stats = ex.backfill_entries(
            self._staging(), {"BV1x": self._bundle()}
        )
        self.assertEqual(staging[0]["entry"]["structured_data"]["hero_names"], [])
        self.assertEqual(stats.vision_errors, 1)
        self.assertEqual(stats.entries_filled_hero, 0)

    def test_missing_bundle_skips(self):
        ex = LineupFrameExtractor(_FakeExtractor())
        staging, stats = ex.backfill_entries(self._staging(), {})
        self.assertEqual(stats.entries_targeted, 0)


if __name__ == "__main__":
    unittest.main()
