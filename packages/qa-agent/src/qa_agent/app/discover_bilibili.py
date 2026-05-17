from __future__ import annotations

import argparse
import html
import json
import os
import re
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import requests
import yaml


_BVID_PATTERN = re.compile(r"BV[0-9A-Za-z]{6,}")
_DEFAULT_KEYWORDS = (
    "三谋 开荒",
    "三国谋定天下 开荒",
    "谋定天下 阵容",
)
_DEFAULT_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36"
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Discover candidate Bilibili videos for Sanmou knowledge ingestion.")
    parser.add_argument("--keyword", action="append", help="Search keyword. Can be passed multiple times.")
    parser.add_argument("--max-pages", type=int, default=2, help="Search pages per keyword.")
    parser.add_argument("--limit", type=int, default=20, help="Maximum candidates to output.")
    parser.add_argument("--order", default="pubdate", choices=["pubdate", "totalrank", "click"], help="Bilibili search order.")
    parser.add_argument("--published-after", help="Only keep videos published on or after YYYY-MM-DD.")
    parser.add_argument("--days", type=int, help="Only keep videos published within the last N days.")
    parser.add_argument("--project-root", help="qa-agent package root. Defaults to the current package root.")
    parser.add_argument("--output", help="Path to write candidate list. Defaults to stdout.")
    parser.add_argument("--format", choices=["yaml", "json"], default="yaml", help="Output format.")
    parser.add_argument("--include-existing", action="store_true", help="Do not exclude BVIDs already found in local sources.")
    parser.add_argument("--cookie-header", help="Optional Bilibili cookie header. Falls back to BILIBILI_COOKIE env var.")
    return parser


def _resolve_project_root(raw: str | None) -> Path:
    if raw:
        return Path(raw).expanduser().resolve()
    return Path(__file__).resolve().parents[3]


def _parse_published_after(value: str | None, days: int | None) -> datetime | None:
    if value:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    if days is not None:
        return datetime.now(timezone.utc) - timedelta(days=days)
    return None


def _clean_html_text(value: Any) -> str:
    text = html.unescape(str(value or ""))
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


def _parse_duration_sec(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.isdigit():
        return int(text)
    parts = text.split(":")
    if not all(part.isdigit() for part in parts):
        return None
    seconds = 0
    for part in parts:
        seconds = seconds * 60 + int(part)
    return seconds


def _format_pubdate(pubdate: Any) -> str | None:
    try:
        timestamp = int(pubdate)
    except (TypeError, ValueError):
        return None
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _find_known_bvids(project_root: Path) -> set[str]:
    roots = [
        project_root / "knowledge_sources",
        project_root / "ingestion",
        project_root / "configs",
        project_root / "docs",
    ]
    suffixes = {".yaml", ".yml", ".json", ".jsonl", ".md", ".txt"}
    known: set[str] = set()
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix not in suffixes:
                continue
            try:
                known.update(_BVID_PATTERN.findall(path.read_text(encoding="utf-8", errors="ignore")))
            except OSError:
                continue
    return known


def _fetch_search_page(keyword: str, page: int, order: str, headers: dict[str, str]) -> list[dict[str, Any]]:
    response = requests.get(
        "https://api.bilibili.com/x/web-interface/search/type",
        params={
            "search_type": "video",
            "keyword": keyword,
            "page": page,
            "order": order,
            "duration": 0,
        },
        headers=headers,
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"Bilibili search API returned non-zero code: {payload}")
    data = payload.get("data") or {}
    result = data.get("result") or []
    return [item for item in result if isinstance(item, dict)]


def _candidate_from_result(item: dict[str, Any], keyword: str, known_bvids: set[str]) -> dict[str, Any] | None:
    bvid = str(item.get("bvid") or "").strip()
    if not bvid:
        arcurl = str(item.get("arcurl") or item.get("url") or "")
        match = _BVID_PATTERN.search(arcurl)
        bvid = match.group(0) if match else ""
    if not bvid:
        return None
    title = _clean_html_text(item.get("title"))
    description = _clean_html_text(item.get("description"))
    url = item.get("arcurl") or f"https://www.bilibili.com/video/{bvid}/"
    if isinstance(url, str) and url.startswith("//"):
        url = f"https:{url}"
    bundle_path = f"packages/qa-agent/ingestion/raw/videos/bilibili-{bvid}.yaml"
    workspace_path = f"packages/qa-agent/ingestion/video_batch/{bvid}"
    return {
        "bvid": bvid,
        "title": title or bvid,
        "uploader": _clean_html_text(item.get("author") or item.get("mid") or "unknown"),
        "published_at": _format_pubdate(item.get("pubdate")),
        "duration_sec": _parse_duration_sec(item.get("duration")),
        "url": str(url),
        "keyword": keyword,
        "already_known": bvid in known_bvids,
        "reason": _build_reason(keyword, title, description),
        "bundle_output": bundle_path,
        "fetch_bundle_command": f"python -m qa_agent.app.fetch_bilibili_bundle --bvid {bvid} --output {bundle_path}",
        "pipeline_command": f"python -m qa_agent.app.run_video_pipeline --input {bundle_path} --workspace {workspace_path}",
    }


def _build_reason(keyword: str, title: str, description: str) -> str:
    haystack = f"{title} {description}"
    hits = [term for term in ("三谋", "谋定天下", "开荒", "阵容", "陈仓", "赛季") if term in haystack]
    if hits:
        return f"keyword={keyword}; matched={','.join(hits)}"
    return f"keyword={keyword}"


def _discover_candidates(
    *,
    keywords: list[str],
    max_pages: int,
    limit: int,
    order: str,
    published_after: datetime | None,
    known_bvids: set[str],
    exclude_existing: bool,
    headers: dict[str, str],
) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    seen: set[str] = set()
    for keyword in keywords:
        for page in range(1, max_pages + 1):
            for item in _fetch_search_page(keyword, page, order, headers):
                candidate = _candidate_from_result(item, keyword, known_bvids)
                if candidate is None or candidate["bvid"] in seen:
                    continue
                seen.add(candidate["bvid"])
                if exclude_existing and candidate["already_known"]:
                    continue
                if published_after and candidate.get("published_at"):
                    published_at = datetime.fromisoformat(candidate["published_at"].replace("Z", "+00:00"))
                    if published_at < published_after:
                        continue
                candidates.append(candidate)
                if len(candidates) >= limit:
                    return candidates
            time.sleep(0.2)
    return candidates


def _serialize_report(report: dict[str, Any], output_format: str) -> str:
    if output_format == "json":
        return json.dumps(report, ensure_ascii=False, indent=2)
    return yaml.dump(report, allow_unicode=True, default_flow_style=False, sort_keys=False)


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = _resolve_project_root(args.project_root)
    keywords = args.keyword or list(_DEFAULT_KEYWORDS)
    published_after = _parse_published_after(args.published_after, args.days)
    cookie_header = args.cookie_header or os.getenv("BILIBILI_COOKIE")
    headers = {
        "User-Agent": _DEFAULT_UA,
        "Referer": "https://www.bilibili.com/",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header

    known_bvids = _find_known_bvids(project_root)
    candidates = _discover_candidates(
        keywords=keywords,
        max_pages=max(1, args.max_pages),
        limit=max(1, args.limit),
        order=args.order,
        published_after=published_after,
        known_bvids=known_bvids,
        exclude_existing=not args.include_existing,
        headers=headers,
    )
    report = {
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "keywords": keywords,
        "order": args.order,
        "known_bvid_count": len(known_bvids),
        "excluded_existing": not args.include_existing,
        "published_after": published_after.replace(microsecond=0).isoformat().replace("+00:00", "Z") if published_after else None,
        "candidate_count": len(candidates),
        "candidates": candidates,
    }
    rendered = _serialize_report(report, args.format)
    if args.output:
        output_path = Path(args.output).expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered, encoding="utf-8")
        print(json.dumps({"candidate_count": len(candidates), "output": str(output_path)}, ensure_ascii=False, indent=2))
        return
    print(rendered)


if __name__ == "__main__":
    main()
