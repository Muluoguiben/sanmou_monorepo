from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from qa_agent.video.frame_sampler import (
    FrameSampleRequest,
    RemoteFrameSampleRequest,
    attach_frames_to_segments,
    plan_sample_timestamps,
    sample_frames,
    sample_remote_frames,
)
from qa_agent.video.models import VideoFrameRef


class PlanSampleTimestampsTests(unittest.TestCase):
    def test_empty_when_duration_non_positive(self) -> None:
        self.assertEqual(plan_sample_timestamps(duration_sec=0.0), [])
        self.assertEqual(plan_sample_timestamps(duration_sec=-5.0), [])

    def test_interval_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            plan_sample_timestamps(duration_sec=30.0, interval_sec=0)

    def test_regular_interval(self) -> None:
        self.assertEqual(
            plan_sample_timestamps(duration_sec=120.0, interval_sec=30.0),
            [0.0, 30.0, 60.0, 90.0],
        )

    def test_respects_start_and_end(self) -> None:
        self.assertEqual(
            plan_sample_timestamps(duration_sec=600.0, interval_sec=60.0, start_sec=90.0, end_sec=300.0),
            [90.0, 150.0, 210.0, 270.0],
        )

    def test_max_frames_caps_output(self) -> None:
        result = plan_sample_timestamps(duration_sec=600.0, interval_sec=30.0, max_frames=3)
        self.assertEqual(result, [0.0, 30.0, 60.0])


class SampleFramesTests(unittest.TestCase):
    def test_runner_receives_expected_args_and_refs_produced(self) -> None:
        recorded: list[list[str]] = []

        def fake_runner(args):
            recorded.append(list(args))
            # Create the output file so sample_frames emits a FrameRef for it.
            Path(args[-1]).write_bytes(b"\xff\xd8\xff\xe0")  # fake JPEG magic

        with tempfile.TemporaryDirectory() as temp_dir:
            request = FrameSampleRequest(
                video_path=Path("/fake/video.mp4"),
                output_dir=Path(temp_dir),
                timestamps=(0.0, 30.0),
                filename_prefix="shot",
            )
            refs = sample_frames(request, ffmpeg_path="/usr/bin/ffmpeg", runner=fake_runner)

        self.assertEqual(len(refs), 2)
        self.assertEqual(refs[0].timestamp_sec, 0.0)
        self.assertEqual(refs[1].timestamp_sec, 30.0)
        self.assertTrue(refs[0].image_path.endswith("shot-001-0s.jpg"))
        self.assertTrue(refs[1].image_path.endswith("shot-002-30s.jpg"))
        # Ensure correct ffmpeg argument ordering for fast seek semantics.
        first_args = recorded[0]
        self.assertEqual(first_args[0], "/usr/bin/ffmpeg")
        self.assertIn("-ss", first_args)
        ss_index = first_args.index("-ss")
        self.assertEqual(first_args[ss_index + 1], "0.000")
        self.assertEqual(first_args[first_args.index("-i") + 1], "/fake/video.mp4")

    def test_missing_output_file_is_skipped(self) -> None:
        def fake_runner(args):
            # Do not write any file — simulates ffmpeg timestamp past EOF.
            return None

        with tempfile.TemporaryDirectory() as temp_dir:
            request = FrameSampleRequest(
                video_path=Path("/fake/video.mp4"),
                output_dir=Path(temp_dir),
                timestamps=(999999.0,),
            )
            refs = sample_frames(request, ffmpeg_path="/usr/bin/ffmpeg", runner=fake_runner)
        self.assertEqual(refs, [])

    def test_sample_remote_frames_uses_headers_and_timeout(self) -> None:
        recorded: list[list[str]] = []

        def fake_runner(args):
            recorded.append(list(args))
            Path(args[-1]).write_bytes(b"\xff\xd8\xff\xe0")

        with tempfile.TemporaryDirectory() as temp_dir:
            request = RemoteFrameSampleRequest(
                video_url="https://upos.example/video.m4s",
                source_url="https://www.bilibili.com/video/BV1TEST/",
                output_dir=Path(temp_dir),
                timestamps=(30.0,),
                filename_prefix="remote",
                timeout_sec=8,
            )
            refs = sample_remote_frames(request, ffmpeg_path="/usr/bin/ffmpeg", runner=fake_runner)

        self.assertEqual(len(refs), 1)
        args = recorded[0]
        self.assertIn("-rw_timeout", args)
        self.assertEqual(args[args.index("-rw_timeout") + 1], "8000000")
        self.assertIn("-headers", args)
        headers = args[args.index("-headers") + 1]
        self.assertIn("Referer: https://www.bilibili.com/video/BV1TEST/", headers)
        self.assertEqual(args[args.index("-i") + 1], "https://upos.example/video.m4s")

    def test_empty_timestamps_short_circuits(self) -> None:
        request = FrameSampleRequest(
            video_path=Path("/fake/video.mp4"),
            output_dir=Path("/tmp/unused"),
            timestamps=(),
        )
        # No runner call should be issued; passing a runner that raises proves this.
        refs = sample_frames(request, ffmpeg_path="/usr/bin/ffmpeg", runner=lambda _args: (_ for _ in ()).throw(AssertionError("runner should not be called")))
        self.assertEqual(refs, [])


class AttachFramesToSegmentsTests(unittest.TestCase):
    def test_frames_land_in_matching_segment(self) -> None:
        segments = [
            {"segment_id": "a", "start_sec": 0.0, "end_sec": 30.0, "frame_refs": []},
            {"segment_id": "b", "start_sec": 30.0, "end_sec": 60.0},
        ]
        frames = [
            VideoFrameRef(timestamp_sec=5.0, image_path="/tmp/f1.jpg", notes=[]),
            VideoFrameRef(timestamp_sec=45.0, image_path="/tmp/f2.jpg", notes=[]),
        ]
        attach_frames_to_segments(segments, frames)
        self.assertEqual(len(segments[0]["frame_refs"]), 1)
        self.assertEqual(segments[0]["frame_refs"][0]["image_path"], "/tmp/f1.jpg")
        self.assertEqual(len(segments[1]["frame_refs"]), 1)
        self.assertEqual(segments[1]["frame_refs"][0]["image_path"], "/tmp/f2.jpg")

    def test_trailing_frame_is_attached_to_last_segment(self) -> None:
        segments = [
            {"segment_id": "a", "start_sec": 0.0, "end_sec": 30.0},
        ]
        frames = [VideoFrameRef(timestamp_sec=999.0, image_path="/tmp/late.jpg", notes=[])]
        attach_frames_to_segments(segments, frames)
        self.assertEqual(len(segments[0]["frame_refs"]), 1)
        self.assertIn("post-last-segment", segments[0]["frame_refs"][0]["notes"])

    def test_pre_first_segment_frame_is_dropped(self) -> None:
        segments = [
            {"segment_id": "a", "start_sec": 10.0, "end_sec": 30.0},
        ]
        frames = [VideoFrameRef(timestamp_sec=1.0, image_path="/tmp/intro.jpg", notes=[])]
        attach_frames_to_segments(segments, frames)
        self.assertNotIn("frame_refs", segments[0])


if __name__ == "__main__":
    unittest.main()
