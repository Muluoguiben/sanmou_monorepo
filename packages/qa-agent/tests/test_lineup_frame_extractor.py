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
    ConsensusLineupExtractor,
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

    def test_route_table_is_summary(self):
        # eval finding: this title was misclassified `other`
        self.assertEqual(
            classify_frame_kind(["三谋 S14·W11·陈仓之战·出队路线5.0-最终版"]),
            FRAME_SUMMARY_TABLE,
        )

    def test_scheme_wins_over_route_when_both_present(self):
        self.assertEqual(
            classify_frame_kind(["六队共存多套方案 出队路线5.0"]),
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
            self._staging(), {"BV1x": self._bundle()},
            allow_canonical_fill=True,
        )
        empty_sd = staging[0]["entry"]["structured_data"]
        self.assertEqual(empty_sd["hero_names"], ["皇甫嵩"])
        self.assertEqual(empty_sd["core_skills"], ["金城汤池"])
        self.assertNotIn("needs_review", empty_sd)
        self.assertTrue(any("阵容图抽取" in n for n in empty_sd["notes"]))
        # existing values untouched
        full_sd = staging[1]["entry"]["structured_data"]
        self.assertEqual(full_sd["hero_names"], ["周瑜"])
        self.assertNotIn("notes", full_sd)
        self.assertEqual(stats.entries_filled_hero, 1)
        self.assertEqual(stats.entries_filled_skill, 1)
        self.assertEqual(stats.entries_targeted, 1)

    def test_default_is_pending_not_canonical(self):
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
        sd = staging[0]["entry"]["structured_data"]
        # canonical slots stay empty; candidates + review flag instead
        self.assertEqual(sd["hero_names"], [])
        self.assertEqual(sd["core_skills"], [])
        self.assertEqual(sd["frame_candidate_hero_names"], ["皇甫嵩"])
        self.assertEqual(sd["frame_candidate_core_skills"], ["金城汤池"])
        self.assertTrue(sd["needs_review"])
        self.assertTrue(any("候选待审" in n for n in sd["notes"]))
        self.assertEqual(stats.entries_filled_hero, 0)
        self.assertEqual(stats.entries_pending, 1)

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


class _ConsensusFake:
    """Answers the cheap classify call with a title, dense calls with a team."""

    def __init__(self, title, heroes, skills=None):
        self._title = title
        self._heroes = heroes
        self._skills = skills or []

    def extract(self, image_urls, *, question=None, **kwargs):
        if question and "标题" in question:
            return _Vis(text_snippets=[self._title])
        return _Vis(
            heroes=[_Ent(x) for x in self._heroes],
            skills=[_Ent(x) for x in self._skills],
        )


class ConsensusExtractorTests(unittest.TestCase):
    def _staging(self):
        return [
            {
                "entry": {
                    "topic": "S14 空队",
                    "source_ref": "BILIBILI:BV1x#40-60",
                    "structured_data": {"hero_names": [], "core_skills": []},
                }
            }
        ]

    def _bundle(self):
        return {
            "segments": [
                {"start_sec": 40.0, "frame_paths": ["/t/BV1x-frame-003-40s.jpg"]},
                {"start_sec": 60.0, "frame_paths": ["/t/BV1x-frame-004-60s.jpg"]},
            ]
        }

    def _run(self, fa, fb):
        ex = ConsensusLineupExtractor(
            fa, fb, prepare_images=lambda paths: paths
        )
        return ex.backfill_entries(self._staging(), {"BV1x": self._bundle()})

    def test_agreement_on_full_team_emits_pending_candidate(self):
        team = ["皇甫嵩", "郝昭", "司马懿"]
        staging, stats = self._run(
            _ConsensusFake("全流程阵容汇总表", team, ["金城汤池"]),
            _ConsensusFake("全流程阵容汇总表", list(reversed(team)), ["金城汤池"]),
        )
        sd = staging[0]["entry"]["structured_data"]
        self.assertEqual(set(sd["frame_candidate_hero_names"]), set(team))
        self.assertEqual(sd["frame_candidate_core_skills"], ["金城汤池"])
        self.assertTrue(sd["needs_review"])
        self.assertEqual(sd["hero_names"], [])
        self.assertEqual(stats.entries_pending, 1)

    def test_disagreement_drops_heroes(self):
        staging, _ = self._run(
            _ConsensusFake("全流程阵容汇总表", ["皇甫嵩", "郝昭", "司马懿"]),
            _ConsensusFake("全流程阵容汇总表", ["陆逊", "鲁肃", "孙坚"]),
        )
        sd = staging[0]["entry"]["structured_data"]
        self.assertNotIn("frame_candidate_hero_names", sd)
        self.assertEqual(sd["hero_names"], [])

    def test_partial_team_dropped(self):
        # both agree but only 2 heroes -> not a complete sanmou team
        staging, _ = self._run(
            _ConsensusFake("全流程阵容汇总表", ["皇甫嵩", "郝昭"]),
            _ConsensusFake("全流程阵容汇总表", ["皇甫嵩", "郝昭"]),
        )
        sd = staging[0]["entry"]["structured_data"]
        self.assertNotIn("frame_candidate_hero_names", sd)

    def test_non_table_frame_skipped_entirely(self):
        team = ["皇甫嵩", "郝昭", "司马懿"]
        staging, stats = self._run(
            _ConsensusFake("主播口播镜头", team),
            _ConsensusFake("主播口播镜头", team),
        )
        sd = staging[0]["entry"]["structured_data"]
        self.assertNotIn("frame_candidate_hero_names", sd)
        self.assertNotIn("needs_review", sd)
        self.assertEqual(stats.entries_pending, 0)

    def test_skill_intersection_only(self):
        team = ["皇甫嵩", "郝昭", "司马懿"]
        staging, _ = self._run(
            _ConsensusFake("方案A", team, ["金城汤池", "步步为营"]),
            _ConsensusFake("方案A", team, ["金城汤池", "未雨绸缪"]),
        )
        sd = staging[0]["entry"]["structured_data"]
        self.assertEqual(sd["frame_candidate_core_skills"], ["金城汤池"])


if __name__ == "__main__":
    unittest.main()
