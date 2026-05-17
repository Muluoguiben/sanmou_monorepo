from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable, Sequence

from .models import VideoFrameRef


FrameRunner = Callable[[Sequence[str]], None]


@dataclass(frozen=True)
class FrameSampleRequest:
    video_path: Path
    output_dir: Path
    timestamps: tuple[float, ...]
    filename_prefix: str = "frame"
    image_format: str = "jpg"
    quality: int = 2


@dataclass(frozen=True)
class RemoteFrameSampleRequest:
    video_url: str
    source_url: str
    output_dir: Path
    timestamps: tuple[float, ...]
    filename_prefix: str = "frame"
    image_format: str = "jpg"
    quality: int = 2
    timeout_sec: int = 20


def resolve_ffmpeg_binary() -> str:
    env_override = os.getenv("FFMPEG_BINARY")
    if env_override and Path(env_override).exists():
        return env_override
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        pass
    path = shutil.which("ffmpeg")
    if path:
        return path
    raise FileNotFoundError(
        "ffmpeg binary not found. Set FFMPEG_BINARY, pip install imageio-ffmpeg, or install system ffmpeg."
    )


def plan_sample_timestamps(
    duration_sec: float,
    interval_sec: float = 30.0,
    start_sec: float = 0.0,
    end_sec: float | None = None,
    max_frames: int | None = None,
) -> list[float]:
    if duration_sec <= 0:
        return []
    if interval_sec <= 0:
        raise ValueError("interval_sec must be positive")
    upper = duration_sec if end_sec is None else min(end_sec, duration_sec)
    if upper <= start_sec:
        return []
    timestamps: list[float] = []
    current = max(start_sec, 0.0)
    while current < upper:
        timestamps.append(round(current, 3))
        if max_frames is not None and len(timestamps) >= max_frames:
            break
        current += interval_sec
    return timestamps


def _build_ffmpeg_args(
    ffmpeg_path: str,
    video_path: Path,
    timestamp: float,
    output_path: Path,
    quality: int,
) -> list[str]:
    return [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        str(video_path),
        "-frames:v",
        "1",
        "-q:v",
        str(quality),
        "-y",
        str(output_path),
    ]


def _build_remote_ffmpeg_args(
    ffmpeg_path: str,
    video_url: str,
    source_url: str,
    timestamp: float,
    output_path: Path,
    quality: int,
    timeout_sec: int,
) -> list[str]:
    headers = (
        "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36\r\n"
        f"Referer: {source_url}\r\n"
    )
    return [
        ffmpeg_path,
        "-hide_banner",
        "-loglevel",
        "error",
        "-nostdin",
        "-rw_timeout",
        str(max(1, timeout_sec) * 1_000_000),
        "-headers",
        headers,
        "-ss",
        f"{timestamp:.3f}",
        "-i",
        video_url,
        "-frames:v",
        "1",
        "-q:v",
        str(quality),
        "-y",
        str(output_path),
    ]


def sample_frames(
    request: FrameSampleRequest,
    *,
    ffmpeg_path: str | None = None,
    runner: FrameRunner | None = None,
) -> list[VideoFrameRef]:
    """Extract one still frame per requested timestamp using ffmpeg.

    `runner` is injected for tests; default is `subprocess.run` with check=True.
    Returns VideoFrameRef entries in the order of input timestamps, skipping any
    frame whose output file was not produced (e.g. timestamp past EOF).
    """
    if not request.timestamps:
        return []
    binary = ffmpeg_path or resolve_ffmpeg_binary()
    run = runner or _default_runner
    request.output_dir.mkdir(parents=True, exist_ok=True)

    refs: list[VideoFrameRef] = []
    for index, timestamp in enumerate(request.timestamps, start=1):
        filename = f"{request.filename_prefix}-{index:03d}-{int(round(timestamp))}s.{request.image_format}"
        output_path = request.output_dir / filename
        args = _build_ffmpeg_args(binary, request.video_path, timestamp, output_path, request.quality)
        run(args)
        if not output_path.exists():
            continue
        refs.append(
            VideoFrameRef(
                timestamp_sec=float(timestamp),
                image_path=str(output_path),
                notes=[],
            )
        )
    return refs


def sample_remote_frames(
    request: RemoteFrameSampleRequest,
    *,
    ffmpeg_path: str | None = None,
    runner: FrameRunner | None = None,
) -> list[VideoFrameRef]:
    """Extract frames directly from a remote DASH URL.

    This avoids downloading a partial MP4 first. Some Bilibili CDN streams are
    slow or non-seekable when truncated, while ffmpeg can seek the remote DASH
    URL directly and fail fast via `-rw_timeout`.
    """
    if not request.timestamps:
        return []
    binary = ffmpeg_path or resolve_ffmpeg_binary()
    run = runner or _default_runner
    request.output_dir.mkdir(parents=True, exist_ok=True)

    refs: list[VideoFrameRef] = []
    for index, timestamp in enumerate(request.timestamps, start=1):
        filename = f"{request.filename_prefix}-{index:03d}-{int(round(timestamp))}s.{request.image_format}"
        output_path = request.output_dir / filename
        args = _build_remote_ffmpeg_args(
            binary,
            request.video_url,
            request.source_url,
            timestamp,
            output_path,
            request.quality,
            request.timeout_sec,
        )
        try:
            run(args)
        except subprocess.CalledProcessError:
            if output_path.exists():
                output_path.unlink()
            continue
        if not output_path.exists():
            continue
        refs.append(
            VideoFrameRef(
                timestamp_sec=float(timestamp),
                image_path=str(output_path),
                notes=[],
            )
        )
    return refs


def _default_runner(args: Sequence[str]) -> None:
    subprocess.run(list(args), check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)


def attach_frames_to_segments(
    segments: Iterable[dict],
    frame_refs: Sequence[VideoFrameRef],
) -> None:
    """Distribute frame_refs across segments by timestamp range.

    Each frame_ref is appended to the first segment whose [start_sec, end_sec)
    contains its timestamp. Segments are mutated in place. Frames that fall
    outside every range (e.g. intro title card sampled at t=0 before first
    segment) are silently dropped.
    """
    bounds: list[tuple[float, float, dict]] = []
    for segment in segments:
        start = float(segment.get("start_sec") or 0.0)
        end = float(segment.get("end_sec") or 0.0)
        if end > start:
            bounds.append((start, end, segment))
    for frame in frame_refs:
        placed = False
        for start, end, segment in bounds:
            if start <= frame.timestamp_sec < end:
                segment.setdefault("frame_refs", []).append(
                    {
                        "timestamp_sec": frame.timestamp_sec,
                        "image_path": frame.image_path,
                        "notes": list(frame.notes),
                    }
                )
                placed = True
                break
        if not placed and bounds:
            # Trailing frame past last segment — attach to the last segment so it is not lost
            if frame.timestamp_sec >= bounds[-1][1]:
                bounds[-1][2].setdefault("frame_refs", []).append(
                    {
                        "timestamp_sec": frame.timestamp_sec,
                        "image_path": frame.image_path,
                        "notes": ["post-last-segment"],
                    }
                )
