from __future__ import annotations

import os
import tempfile
from pathlib import Path

import requests


def fetch_bilibili_audio_url(
    bvid: str,
    cid: int,
    cookie_header: str | None,
    source_url: str,
) -> str | None:
    if not cookie_header:
        return None
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
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
    audio = dash.get("audio") or []
    if not audio:
        return None
    base_url = audio[0].get("baseUrl") or audio[0].get("base_url")
    return str(base_url) if base_url else None


def download_audio_file(audio_url: str, source_url: str, cookie_header: str | None) -> Path:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": source_url,
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    response = requests.get(audio_url, timeout=30, headers=headers, stream=True)
    response.raise_for_status()
    fd, temp_path = tempfile.mkstemp(suffix=".m4a", prefix="bili-audio-")
    os.close(fd)
    path = Path(temp_path)
    with path.open("wb") as handle:
        for chunk in response.iter_content(1024 * 256):
            if chunk:
                handle.write(chunk)
    return path


def transcribe_audio_with_faster_whisper(
    audio_path: Path,
    model_name: str = "small",
    language: str = "zh",
) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_name, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(audio_path), language=language, vad_filter=True)
    items: list[dict] = []
    for segment in segments:
        text = (segment.text or "").strip()
        if not text:
            continue
        items.append(
            {
                "from": float(segment.start),
                "to": float(segment.end),
                "content": text,
            }
        )
    return items
