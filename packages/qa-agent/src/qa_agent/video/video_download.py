from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests


_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)


def fetch_bilibili_video_url(
    bvid: str,
    cid: int,
    cookie_header: str | None,
    source_url: str,
) -> str | None:
    """Resolve a direct MP4 stream URL for a Bilibili video via the DASH playurl API.

    Returns the lowest-quality video baseUrl (we only need frames — no need for 1080p)
    or None when cookie is missing / DASH payload is empty.
    """
    if not cookie_header:
        return None
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Referer": source_url,
        "Cookie": cookie_header,
    }
    response = requests.get(
        f"https://api.bilibili.com/x/player/playurl?bvid={bvid}&cid={cid}&fnval=80&fourk=1",
        timeout=20,
        headers=headers,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    dash = data.get("dash") or {}
    video = dash.get("video") or []
    if not video:
        return None
    # Pick the lowest-quality available stream (smallest file) — frames at 360p are
    # plenty for LLM recognition of hero portraits / skill names.
    video.sort(key=lambda entry: int(entry.get("id") or 0))
    base_url = video[0].get("baseUrl") or video[0].get("base_url")
    return str(base_url) if base_url else None


def download_video_file(
    video_url: str,
    source_url: str,
    cookie_header: str | None,
    *,
    max_bytes: int | None = None,
    dest: Path | None = None,
) -> Path:
    """Download a Bilibili video stream to a temp file (or `dest` if provided).

    `max_bytes` caps bytes-on-disk; useful for sampling frames from the first
    few minutes without pulling a 60MB file. The resulting MP4 is still
    seekable because the moov atom is at the head for most bilibili streams.
    """
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Referer": source_url,
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    response = requests.get(video_url, timeout=60, headers=headers, stream=True)
    response.raise_for_status()
    if dest is None:
        fd, temp_path = tempfile.mkstemp(suffix=".mp4", prefix="bili-video-")
        os.close(fd)
        dest = Path(temp_path)
    else:
        dest.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with dest.open("wb") as handle:
        for chunk in response.iter_content(1024 * 256):
            if not chunk:
                continue
            handle.write(chunk)
            written += len(chunk)
            if max_bytes is not None and written >= max_bytes:
                break
    return dest
