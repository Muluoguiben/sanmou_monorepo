from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests
import yaml

from qa_agent.video.asr import download_audio_file, fetch_bilibili_audio_url, transcribe_audio_with_faster_whisper
from qa_agent.video import VideoEvidenceBundle, VideoEvidenceSegment, VideoSource


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch minimal Bilibili metadata and build a raw video bundle.")
    parser.add_argument("--url", help="Bilibili video URL.")
    parser.add_argument("--bvid", help="Bilibili BV id.")
    parser.add_argument("--output", required=True, help="Path to write the raw bundle YAML.")
    parser.add_argument("--cookie-header", help="Optional Bilibili cookie header. Falls back to BILIBILI_COOKIE env var.")
    parser.add_argument("--asr-fallback", action="store_true", help="When subtitle body is unavailable, try local ASR from the Bilibili audio stream.")
    parser.add_argument("--asr-model", default="small", help="faster-whisper model name for ASR fallback.")
    return parser


def _resolve_path(raw: str, project_root: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return (project_root / path).resolve()


def _extract_bvid(url: str) -> str:
    match = re.search(r"/video/(BV[0-9A-Za-z]+)", url)
    if not match:
        raise ValueError(f"Could not extract BVID from URL: {url}")
    return match.group(1)


def _fetch_view_data(bvid: str) -> dict:
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    response = _get_with_retries(url, headers={"User-Agent": "Mozilla/5.0"})
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili view API returned non-zero code: {payload}")
    return payload["data"]


def _load_video_text_corrections(project_root: Path) -> dict[str, dict[str, str]]:
    path = project_root / "configs" / "video_text_corrections.yaml"
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(data, dict):
        return {}
    normalized: dict[str, dict[str, str]] = {}
    for bvid, payload in data.items():
        if not isinstance(payload, dict):
            continue
        replacements = payload.get("phrase_replacements") or {}
        if isinstance(replacements, dict):
            normalized[str(bvid)] = {str(k): str(v) for k, v in replacements.items()}
    return normalized


def _apply_text_corrections(text: str, replacements: dict[str, str]) -> str:
    corrected = text
    for old, new in replacements.items():
        corrected = corrected.replace(old, new)
    return corrected


def _get_with_retries(url: str, headers: dict[str, str], attempts: int = 3) -> requests.Response:
    last_error: Exception | None = None
    for attempt in range(attempts):
        try:
            return requests.get(url, timeout=20, headers=headers)
        except requests.RequestException as exc:
            last_error = exc
            if attempt + 1 < attempts:
                time.sleep(1 + attempt)
    assert last_error is not None
    raise last_error


def _build_wbi_signature_key(headers: dict[str, str]) -> str:
    nav = _get_with_retries("https://api.bilibili.com/x/web-interface/nav", headers=headers)
    nav.raise_for_status()
    data = nav.json()["data"]["wbi_img"]
    img = data["img_url"].rsplit("/", 1)[1].split(".")[0]
    sub = data["sub_url"].rsplit("/", 1)[1].split(".")[0]
    mixin_key_enc_tab = [
        46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35,
        27, 43, 5, 49, 33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13,
        37, 48, 7, 16, 24, 55, 40, 61, 26, 17, 0, 1, 60, 51, 30, 4,
        22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36, 20, 34, 44, 52,
    ]
    return "".join((img + sub)[i] for i in mixin_key_enc_tab)[:32]


def _fetch_conclusion_data(
    bvid: str,
    cid: int,
    up_mid: int,
    headers: dict[str, str],
) -> dict | None:
    try:
        mixin_key = _build_wbi_signature_key(headers)
        params = {"bvid": bvid, "cid": cid, "up_mid": up_mid, "wts": int(time.time())}
        params = {k: re.sub(r"[!'()*]", "", str(v)) for k, v in params.items()}
        query = urlencode(sorted(params.items()))
        params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
        url = "https://api.bilibili.com/x/web-interface/view/conclusion/get?" + urlencode(params)
        response = _get_with_retries(url, headers=headers)
        response.raise_for_status()
        payload = response.json()
        if payload.get("code") != 0:
            return None
        data = payload.get("data") or {}
        if data.get("code") != 0:
            return None
        return data.get("model_result")
    except Exception:
        return None


def _fetch_subtitle_catalog(bvid: str, cid: int, cookie_header: str | None) -> list[dict]:
    if not cookie_header:
        return []
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": f"https://www.bilibili.com/video/{bvid}/",
        "Cookie": cookie_header,
    }
    # Use wbi/v2 endpoint — player/v2 returns populated subtitle_url inconsistently
    # (often empty for AI subtitles). wbi/v2 is the same response shape but reliably
    # includes the signed aisubtitle.hdslb.com URL.
    response = _get_with_retries(
        f"https://api.bilibili.com/x/player/wbi/v2?bvid={bvid}&cid={cid}",
        headers=headers,
    )
    response.raise_for_status()
    payload = response.json()
    data = payload.get("data") or {}
    subtitle = data.get("subtitle") or {}
    subtitles = subtitle.get("subtitles") or []
    catalog = []
    for item in subtitles:
        if not isinstance(item, dict):
            continue
        catalog.append(
            {
                "lan": item.get("lan") or "",
                "lan_doc": item.get("lan_doc") or "",
                "subtitle_url": item.get("subtitle_url") or "",
            }
        )
    return catalog


def _fetch_subtitle_body(subtitle_catalog: list[dict], cookie_header: str | None, referer_url: str) -> list[dict]:
    preferred = None
    for item in subtitle_catalog:
        if item.get("lan") == "ai-zh" and item.get("subtitle_url"):
            preferred = item
            break
    if preferred is None:
        for item in subtitle_catalog:
            if item.get("subtitle_url"):
                preferred = item
                break
    if preferred is None:
        return []
    url = preferred["subtitle_url"]
    if url.startswith("//"):
        url = f"https:{url}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": referer_url,
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    response = _get_with_retries(url, headers=headers)
    response.raise_for_status()
    payload = response.json()
    body = payload.get("body") or []
    items: list[dict] = []
    for item in body:
        if not isinstance(item, dict):
            continue
        content = str(item.get("content") or "").strip()
        if content:
            items.append(
                {
                    "from": float(item.get("from") or 0.0),
                    "to": float(item.get("to") or 0.0),
                    "content": content,
                }
            )
    return items


def _extract_relevance_tokens(title: str, description: str | None) -> list[str]:
    """Produce short (2-char) CJK bigrams + short ASCII tokens from title/description.

    Chinese titles have no word boundaries so a naive `{2,}` regex match produces
    compound spans (e.g. `月卡挑战三谋第一天`) that never appear verbatim in a
    transcript. Sliding 2-char windows over each CJK run guarantees at least one
    bigram (e.g. `三谋`, `月卡`) will match a real transcript, while the stop
    list filters noise.
    """
    stop = {"全网", "最新", "重置", "视频", "这里", "大家", "评论", "关注", "拜托"}
    deduped: list[str] = []
    for run in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z0-9]{2,}", f"{title} {description or ''}"):
        if re.fullmatch(r"[A-Za-z0-9]{2,}", run):
            candidate = run
            if candidate not in stop and candidate not in deduped:
                deduped.append(candidate)
            continue
        for i in range(len(run) - 1):
            bigram = run[i : i + 2]
            if bigram in stop or bigram in deduped:
                continue
            deduped.append(bigram)
    return deduped[:20]


def _subtitle_body_is_relevant(title: str, description: str | None, body: list[dict]) -> bool:
    if not body:
        return False
    tokens = _extract_relevance_tokens(title, description)
    if not tokens:
        return True
    text = "\n".join(item.get("content", "") for item in body[:120])
    hits = sum(1 for token in tokens if token in text)
    return hits >= 1


def _fetch_validated_subtitle_data(
    bvid: str,
    cid: int,
    cookie_header: str | None,
    title: str,
    description: str | None,
    source_url: str,
    conclusion_data: dict | None,
) -> tuple[list[dict], list[dict]]:
    if conclusion_data:
        subtitle_blocks = conclusion_data.get("subtitle") or []
        body: list[dict] = []
        for block in subtitle_blocks:
            for item in block.get("part_subtitle") or []:
                content = str(item.get("content") or "").strip()
                if not content:
                    continue
                body.append(
                    {
                        "from": float(item.get("start_timestamp") or 0.0),
                        "to": float(item.get("end_timestamp") or 0.0),
                        "content": content,
                    }
                )
        if body:
            return [], body
    last_catalog: list[dict] = []
    for _ in range(3):
        catalog = _fetch_subtitle_catalog(bvid, cid, cookie_header)
        last_catalog = catalog
        body = _fetch_subtitle_body(catalog, cookie_header, source_url)
        if _subtitle_body_is_relevant(title, description, body):
            return catalog, body
        time.sleep(1)
    return last_catalog, []


def _fetch_asr_body(
    bvid: str,
    cid: int,
    cookie_header: str | None,
    source_url: str,
    model_name: str,
) -> list[dict]:
    audio_url = fetch_bilibili_audio_url(bvid=bvid, cid=cid, cookie_header=cookie_header, source_url=source_url)
    if not audio_url:
        return []
    audio_path = download_audio_file(audio_url=audio_url, source_url=source_url, cookie_header=cookie_header)
    try:
        return transcribe_audio_with_faster_whisper(audio_path=audio_path, model_name=model_name, language="zh")
    finally:
        if audio_path.exists():
            audio_path.unlink()


def _build_segments_from_subtitle_body(body: list[dict], first_frame: str | None) -> list[VideoEvidenceSegment]:
    if not body:
        return []
    chunks: list[list[dict]] = []
    current: list[dict] = []
    for item in body:
        current.append(item)
        if len(current) >= 12 or (current[-1]["to"] - current[0]["from"]) >= 45:
            chunks.append(current)
            current = []
    if current:
        chunks.append(current)

    segments: list[VideoEvidenceSegment] = []
    for index, chunk in enumerate(chunks, start=1):
        start_sec = float(chunk[0]["from"])
        end_sec = max(float(chunk[-1]["to"]), start_sec + 1)
        lines = [entry["content"] for entry in chunk]
        frame_paths = [first_frame] if first_frame and index == 1 else []
        segments.append(
            VideoEvidenceSegment(
                title=f"subtitle-chunk-{index}",
                start_sec=start_sec,
                end_sec=end_sec,
                transcript_lines=lines,
                visual_summary="B站 AI 中文字幕切片。",
                frame_paths=frame_paths,
            )
        )
    return segments


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    output_path = _resolve_path(args.output, project_root)

    if not args.url and not args.bvid:
        raise RuntimeError("Either --url or --bvid is required.")
    bvid = args.bvid or _extract_bvid(args.url)
    source_url = args.url or f"https://www.bilibili.com/video/{bvid}/"
    cookie_header = args.cookie_header or os.getenv("BILIBILI_COOKIE")
    video_text_corrections = _load_video_text_corrections(project_root)
    replacements = video_text_corrections.get(bvid, {})
    request_headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
        "Referer": source_url,
    }
    if cookie_header:
        request_headers["Cookie"] = cookie_header

    view = _fetch_view_data(bvid)
    owner = view.get("owner") or {}
    pages = view.get("pages") or []
    first_page = pages[0] if pages else {}
    conclusion_data = _fetch_conclusion_data(
        bvid=bvid,
        cid=view["cid"],
        up_mid=owner.get("mid") or 0,
        headers=request_headers,
    )
    if conclusion_data and replacements:
        if conclusion_data.get("summary"):
            conclusion_data["summary"] = _apply_text_corrections(conclusion_data["summary"], replacements)
        for outline_item in conclusion_data.get("outline") or []:
            if outline_item.get("title"):
                outline_item["title"] = _apply_text_corrections(str(outline_item["title"]), replacements)
            for part in outline_item.get("part_outline") or []:
                if part.get("content"):
                    part["content"] = _apply_text_corrections(str(part["content"]), replacements)
        for subtitle_block in conclusion_data.get("subtitle") or []:
            for item in subtitle_block.get("part_subtitle") or []:
                if item.get("content"):
                    item["content"] = _apply_text_corrections(str(item["content"]), replacements)
    subtitle_catalog, subtitle_body = _fetch_validated_subtitle_data(
        bvid=bvid,
        cid=view["cid"],
        cookie_header=cookie_header,
        title=view.get("title") or bvid,
        description=view.get("desc") or None,
        source_url=source_url,
        conclusion_data=conclusion_data,
    )
    asr_used = False
    if not subtitle_body and args.asr_fallback:
        subtitle_body = _fetch_asr_body(
            bvid=bvid,
            cid=view["cid"],
            cookie_header=cookie_header,
            source_url=source_url,
        model_name=args.asr_model,
        )
        asr_used = bool(subtitle_body)
    if replacements and subtitle_body:
        for item in subtitle_body:
            item["content"] = _apply_text_corrections(item["content"], replacements)
    published_at = datetime.fromtimestamp(view["pubdate"], tz=timezone.utc).replace(tzinfo=None)
    captured_at = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    segments = _build_segments_from_subtitle_body(subtitle_body, first_page.get("first_frame"))
    if not segments:
        segments = [
            VideoEvidenceSegment(
                title="metadata-summary",
                start_sec=0,
                end_sec=float(view.get("duration") or 1),
                transcript_lines=[view.get("title") or "", view.get("desc") or ""],
                visual_summary=f"B站元数据导入。首帧：{first_page.get('first_frame') or '无'}",
                frame_paths=[first_page["first_frame"]] if first_page.get("first_frame") else [],
            )
        ]
    bundle = VideoEvidenceBundle(
        source=VideoSource(
            video_id=bvid,
            title=view.get("title") or bvid,
            uploader=owner.get("name") or "unknown",
            source_url=source_url,
            description=view.get("desc") or None,
            ai_summary=(conclusion_data or {}).get("summary"),
            ai_outline=(conclusion_data or {}).get("outline") or [],
            subtitle_catalog=subtitle_catalog,
            published_at=published_at,
            captured_at=captured_at,
        ),
        segments=segments,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        yaml.dump(bundle.model_dump(mode="json"), allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "bvid": bvid,
                "title": bundle.source.title,
                "duration": view.get("duration"),
                "subtitle_catalog_size": len(subtitle_catalog),
                "subtitle_line_count": len(subtitle_body),
                "segment_count": len(segments),
                "asr_used": asr_used,
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
