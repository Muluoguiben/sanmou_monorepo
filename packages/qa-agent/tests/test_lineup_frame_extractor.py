import sys
import unittest
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from qa_agent.video.lineup_frame_extractor import (  # noqa: E402
    FRAME_COUNTER_GRAPH,
    FRAME_OTHER,
    FRAME_SCHEME_TABLE,
    FRAME_SUMMARY_TABLE,
    BackfillStats,
    FrameRef,
    LineupFrameExtractor,
    classify_frame_kind,
    collect_frames_from_bundle,
    crop_into_columns,
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

    def extract(self, image_urls, *, question=None, **kwargs):
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


class ClassifyFrameKindTests(unittest.TestCase):
    def test_summary_table(self):
        self.assertEqual(
            classify_frame_kind(["三国谋定天下", "全流程阵容汇总"]),
            FRAME_SUMMARY_TABLE,
        )

    def test_scheme_table(self):
        self.assertEqual(
            classify_frame_kind(["S14 陈仓之围 六队共存 方案A"]),
            FRAME_SCHEME_TABLE,
        )

    def test_counter_graph(self):
        self.assertEqual(
            classify_frame_kind(["S14首发队伍克制关系图"]), FRAME_COUNTER_GRAPH
        )

    def test_other(self):
        self.assertEqual(classify_frame_kind(["主播口播镜头"]), FRAME_OTHER)

    def test_summary_precedence_over_counter(self):
        # a 方案 table cell may mention 克制; title cue wins
        self.assertEqual(
            classify_frame_kind(["方案A", "本队克制周瑜"]), FRAME_SCHEME_TABLE
        )


class CropIntoColumnsTests(unittest.TestCase):
    def test_splits_and_upscales(self):
        import tempfile

        from PIL import Image

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "BVx-frame-001-0s.jpg"
            Image.new("RGB", (600, 300), "white").save(src)
            paths = crop_into_columns(
                str(src), 3, str(Path(td) / "cols"), overlap_frac=0.0, upscale=2
            )
            self.assertEqual(len(paths), 3)
            for p in paths:
                self.assertTrue(Path(p).exists())
                w, h = Image.open(p).size
                # 600/3 = 200 col, upscale 2 → ~400 wide, 300*2=600 tall
                self.assertEqual(h, 600)
                self.assertAlmostEqual(w, 400, delta=4)

    def test_invalid_n_cols(self):
        import tempfile

        from PIL import Image

        with tempfile.TemporaryDirectory() as td:
            src = Path(td) / "f.jpg"
            Image.new("RGB", (100, 100), "white").save(src)
            with self.assertRaises(ValueError):
                crop_into_columns(str(src), 0, str(Path(td) / "o"))


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
            fake,
            canonicalize=lambda s: canon(s) or s,
            prepare_images=lambda paths: paths,
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
        ex = LineupFrameExtractor(
            _FakeExtractor(fail=True), prepare_images=lambda paths: paths
        )
        staging, stats = ex.backfill_entries(
            self._staging(), {"BV1x": self._bundle()}
        )
        self.assertEqual(staging[0]["entry"]["structured_data"]["hero_names"], [])
        self.assertEqual(stats.vision_errors, 1)
        self.assertEqual(stats.entries_filled_hero, 0)

    def test_image_prep_failure_is_fail_open(self):
        def _boom(_paths):
            raise FileNotFoundError("frame not on disk")

        ex = LineupFrameExtractor(_FakeExtractor(), prepare_images=_boom)
        staging, stats = ex.backfill_entries(
            self._staging(), {"BV1x": self._bundle()}
        )
        self.assertEqual(staging[0]["entry"]["structured_data"]["hero_names"], [])
        self.assertEqual(stats.vision_errors, 1)
        self.assertEqual(stats.entries_filled_hero, 0)

    def test_missing_bundle_skips(self):
        ex = LineupFrameExtractor(
            _FakeExtractor(), prepare_images=lambda paths: paths
        )
        staging, stats = ex.backfill_entries(self._staging(), {})
        self.assertEqual(stats.entries_targeted, 0)


if __name__ == "__main__":
    unittest.main()
