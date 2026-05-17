from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from qa_agent.chat.env import load_package_env
from qa_agent.ingestion.models import ReviewStatus, StagingEntry
from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.models import Domain, EntryKind, KnowledgeEntry
from qa_agent.video import dump_video_knowledge_document, load_video_knowledge_document, stage_all_video_entries
from qa_agent.video.evidence_quality import filter_document_for_evidence_quality, load_evidence_quality_context


@dataclass(frozen=True)
class ProcessPaths:
    raw_dir: Path
    frame_dir: Path
    workspace_root: Path
    staging_output: Path
    summary_output: Path
    knowledge_root: Path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Process a Bilibili discovery manifest with a strict subtitle+frame gate. "
            "Entries without screenshot/vision evidence are excluded from staging/publish."
        )
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--manifest", help="Discovery manifest YAML path.")
    source.add_argument("--manifest-git-ref", help="Read manifest YAML from git, e.g. <commit>:path/to/file.yaml.")
    parser.add_argument("--limit", type=int, help="Only process the first N candidates.")
    parser.add_argument("--workers", type=int, default=2, help="Concurrent videos to process.")
    parser.add_argument("--extractor", choices=["heuristic", "openai", "gemini", "auto"], default="heuristic")
    parser.add_argument("--frames-per-segment", type=int, default=2)
    parser.add_argument("--frame-interval", type=float, default=120.0)
    parser.add_argument("--frame-start", type=float, default=15.0)
    parser.add_argument("--frame-max-count", type=int, default=6)
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--allow-no-vision", action="store_true", help="Accept segments with a local frame even if vision enrichment returned no text.")
    parser.add_argument("--publish", action="store_true", help="Update formal knowledge_sources. Default is staging-only.")
    parser.add_argument("--no-publish", action="store_true", help="Write staging/summary only; do not update formal knowledge_sources.")
    parser.add_argument("--raw-dir", default="packages/qa-agent/ingestion/raw/videos/bilibili-kaihuang-100-2026-05-17")
    parser.add_argument("--frame-dir", default="packages/qa-agent/ingestion/raw/videos/bilibili-kaihuang-100-2026-05-17-frames")
    parser.add_argument("--workspace-root", default="/tmp/sanmou-bili-kaihuang-100-2026-05-17")
    parser.add_argument("--staging-output", default="packages/qa-agent/ingestion/staging/videos/bilibili-kaihuang-100-2026-05-17.yaml")
    parser.add_argument("--summary-output", default="packages/qa-agent/ingestion/staging/videos/bilibili-kaihuang-100-2026-05-17-summary.md")
    parser.add_argument("--knowledge-root", default="packages/qa-agent/knowledge_sources")
    return parser


def _project_root() -> Path:
    return Path(__file__).resolve().parents[5]


def _package_root(project_root: Path) -> Path:
    return project_root / "packages" / "qa-agent"


def _resolve_path(raw: str, project_root: Path) -> Path:
    path = Path(raw).expanduser()
    if path.is_absolute():
        return path
    return (project_root / path).resolve()


def _load_manifest(args: argparse.Namespace, project_root: Path) -> list[dict[str, Any]]:
    if args.manifest:
        data = yaml.safe_load(_resolve_path(args.manifest, project_root).read_text(encoding="utf-8")) or {}
    else:
        result = subprocess.run(
            ["git", "show", args.manifest_git_ref],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=True,
        )
        data = yaml.safe_load(result.stdout) or {}
    candidates = list(data.get("candidates") or [])
    if args.limit is not None:
        candidates = candidates[: args.limit]
    return candidates


def _run_module(
    project_root: Path,
    module: str,
    args: list[str],
    *,
    env: dict[str, str],
    timeout: int,
) -> tuple[bool, dict[str, Any], str]:
    python = project_root / ".venv" / "bin" / "python"
    cmd = [str(python), "-m", module, *args]
    try:
        result = subprocess.run(
            cmd,
            cwd=project_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return False, {}, "timeout"
    if result.returncode != 0:
        return False, {}, (result.stderr or result.stdout)[-1200:]
    try:
        return True, _parse_json_stdout(result.stdout), ""
    except json.JSONDecodeError as exc:
        return False, {}, f"json parse failed: {exc}; stdout_tail={result.stdout[-500:]}"


def _parse_json_stdout(stdout: str) -> dict[str, Any]:
    text = stdout.strip()
    start = text.find("{")
    if start > 0:
        text = text[start:]
    return json.loads(text)


def _localize_bundle_frames(
    bundle_path: Path,
    *,
    project_root: Path,
) -> int:
    data = yaml.safe_load(bundle_path.read_text(encoding="utf-8")) or {}
    source = data.get("source") or {}
    bvid = str(source.get("video_id") or bundle_path.stem)
    referer = source.get("source_url") or f"https://www.bilibili.com/video/{bvid}/"
    changed = False
    count = 0
    for segment_index, segment in enumerate(data.get("segments") or [], start=1):
        localized: list[str] = []
        for frame_index, frame_path in enumerate(segment.get("frame_paths") or [], start=1):
            frame_path = str(frame_path)
            if frame_path.startswith(("http://", "https://")):
                continue
            local_path = Path(frame_path)
            if not local_path.is_file():
                continue
            try:
                localized_path = local_path.relative_to(project_root).as_posix()
            except ValueError:
                localized_path = str(local_path)
            if localized_path not in localized:
                localized.append(localized_path)
                count += 1
            changed = True
        segment["frame_paths"] = localized
    if changed:
        bundle_path.write_text(yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False), encoding="utf-8")
    return count


def _mark_staging_normalized(items: list[StagingEntry], *, frame_count: int, require_vision: bool) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        notes = list(item.metadata.review_notes)
        notes.append("evidence_gate: subtitle/conclusion text combined with localized video screenshot frame")
        notes.append(f"frame_count={frame_count}; require_vision={require_vision}")
        normalized = StagingEntry(
            metadata=item.metadata.model_copy(
                update={
                    "review_status": ReviewStatus.NORMALIZED,
                    "review_notes": notes,
                }
            ),
            entry=item.entry,
        )
        out.append(normalized.model_dump(mode="json"))
    return out


def _slugify_bucket(value: str) -> str:
    return "-".join(part for part in value.lower().replace("/", " ").replace("_", " ").split() if part)


def _target_bucket(entry: KnowledgeEntry, knowledge_root: Path) -> Path | None:
    if entry.domain == Domain.SOLUTION and entry.entry_kind == EntryKind.LINEUP_SOLUTION:
        season_tags = list(getattr(entry.structured_data, "season_tags", []) or [])
        if season_tags:
            return knowledge_root / "solutions" / "lineups" / f"season-{_slugify_bucket(season_tags[0])}.yaml"
        return knowledge_root / "solutions" / "lineups" / "season-misc.yaml"
    if entry.domain == Domain.COMBAT and entry.entry_kind == EntryKind.GENERIC_RULE:
        return knowledge_root / "combat.yaml"
    return None


def _existing_topics(path: Path) -> set[str]:
    if not path.exists():
        return set()
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    return {str(item.get("topic")) for item in data if isinstance(item, dict) and item.get("topic")}


def _filter_publishable(
    entries: list[KnowledgeEntry],
    *,
    knowledge_root: Path,
    min_confidence: float,
) -> tuple[list[KnowledgeEntry], int, int]:
    existing_cache: dict[Path, set[str]] = {}
    batch_seen: dict[Path, set[str]] = {}
    selected: list[KnowledgeEntry] = []
    skipped_existing = 0
    skipped_duplicate = 0
    for entry in entries:
        if entry.confidence < min_confidence or "#" not in entry.source_ref:
            continue
        bucket = _target_bucket(entry, knowledge_root)
        if bucket is None:
            continue
        if bucket not in existing_cache:
            existing_cache[bucket] = _existing_topics(bucket)
        if entry.topic in existing_cache[bucket]:
            skipped_existing += 1
            continue
        if entry.topic in batch_seen.setdefault(bucket, set()):
            skipped_duplicate += 1
            continue
        batch_seen[bucket].add(entry.topic)
        selected.append(entry)
    return selected, skipped_existing, skipped_duplicate


def _build_env(project_root: Path) -> dict[str, str]:
    load_package_env()
    env = os.environ.copy()
    src_path = str(project_root / "packages" / "qa-agent" / "src")
    env["PYTHONPATH"] = src_path + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    return env


def _process_one(
    candidate: dict[str, Any],
    *,
    project_root: Path,
    paths: ProcessPaths,
    env: dict[str, str],
    extractor: str,
    frames_per_segment: int,
    frame_interval: float,
    frame_start: float,
    frame_max_count: int,
    require_vision: bool,
    quality_context: Any,
) -> dict[str, Any]:
    started = time.time()
    bvid = str(candidate["bvid"])
    raw_path = paths.raw_dir / f"{bvid}.yaml"
    workspace = paths.workspace_root / bvid
    fetch_ok, fetch_summary, fetch_error = _run_module(
        project_root,
        "qa_agent.app.fetch_bilibili_bundle",
        [
            "--bvid",
            bvid,
            "--output",
            str(raw_path),
            "--with-frames",
            "--frame-interval",
            str(frame_interval),
            "--frame-start",
            str(frame_start),
            "--frame-max-count",
            str(frame_max_count),
            "--frame-output-dir",
            str(paths.frame_dir / bvid),
        ],
        env=env,
        timeout=300,
    )
    frame_count = 0
    if fetch_ok:
        frame_count = _localize_bundle_frames(
            raw_path,
            project_root=project_root,
        )
    pipeline_ok = False
    pipeline_summary: dict[str, Any] = {}
    pipeline_error = ""
    filtered_counts = {"lineup": 0, "hero": 0, "skill": 0, "combat": 0}
    staging_items: list[dict[str, Any]] = []
    publish_entries_for_video: list[KnowledgeEntry] = []
    valid_segment_count = 0
    quality_stats: dict[str, object] = {}
    if fetch_ok and frame_count > 0:
        pipeline_ok, pipeline_summary, pipeline_error = _run_module(
            project_root,
            "qa_agent.app.run_video_pipeline",
            [
                "--input",
                str(raw_path),
                "--workspace",
                str(workspace),
                "--extractor",
                extractor,
                "--enrich-frames",
                "--frames-per-segment",
                str(frames_per_segment),
            ],
            env=env,
            timeout=240,
        )
        if pipeline_ok:
            enriched_path = Path(pipeline_summary["enriched_path"])
            document = load_video_knowledge_document(enriched_path)
            filtered, quality_stats = filter_document_for_evidence_quality(
                document,
                quality_context,
                require_vision=require_vision,
            )
            valid_segment_count = int(quality_stats["allowed_segments"])
            filtered_path = workspace / "video-knowledge-frame-gated.yaml"
            dump_video_knowledge_document(filtered_path, filtered)
            staged, direct_entries = stage_all_video_entries(filtered, _package_root(project_root))
            staging_items = _mark_staging_normalized(staged, frame_count=frame_count, require_vision=require_vision)
            publish_entries_for_video = [
                item.entry
                for item in staged
                if item.entry.domain == Domain.SOLUTION and item.entry.entry_kind == EntryKind.LINEUP_SOLUTION
            ]
            publish_entries_for_video.extend(direct_entries)
            filtered_counts = {
                "lineup": len(filtered.lineup_candidates),
                "hero": len(filtered.hero_candidates),
                "skill": len(filtered.skill_candidates),
                "combat": len(filtered.combat_candidates),
            }
        else:
            quality_stats = {}
    elif fetch_ok:
        pipeline_error = "skipped: no localized screenshot frame"
    return {
        "bvid": bvid,
        "title": candidate.get("title") or fetch_summary.get("title") or "",
        "fetch_ok": fetch_ok,
        "fetch_error": fetch_error,
        "fetch_summary": fetch_summary,
        "frame_count": frame_count,
        "pipeline_ok": pipeline_ok,
        "pipeline_error": pipeline_error,
        "pipeline_summary": pipeline_summary,
        "valid_segment_count": valid_segment_count,
        "quality_stats": quality_stats if fetch_ok and pipeline_ok else {},
        "filtered_counts": filtered_counts,
        "staging_items": staging_items,
        "publish_entries": publish_entries_for_video,
        "elapsed_s": round(time.time() - started, 2),
    }


def _write_summary(
    path: Path,
    *,
    manifest_ref: str,
    results: list[dict[str, Any]],
    staging_count: int,
    selected_publish: list[KnowledgeEntry],
    publish_stats: dict[str, int],
    skipped_existing: int,
    skipped_duplicate: int,
    require_vision: bool,
) -> None:
    accepted = [r for r in results if r["pipeline_ok"] and r["valid_segment_count"] > 0]
    lines = [
        "# Bilibili 三谋开荒 100 视频截图+vision 证据化沉淀",
        "",
        f"- 运行时间：{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"- 输入来源：`{manifest_ref}`",
        f"- 候选视频：{len(results)}",
        f"- fetch 成功：{sum(1 for r in results if r['fetch_ok'])}",
        f"- 本地化截图成功视频：{sum(1 for r in results if r['frame_count'] > 0)}",
        f"- 截图+vision 门禁通过视频：{len(accepted)}",
        f"- 聚合 staging entries：{staging_count}",
        f"- formal publishable entries：{len(selected_publish)}",
        f"- skipped_existing_topic：{skipped_existing}",
        f"- skipped_batch_duplicate：{skipped_duplicate}",
        f"- publish stats：`{json.dumps(publish_stats, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## 质量门禁",
        "",
        "- 禁止字幕-only：候选条目必须来自带截图帧的 segment，字幕或结论文本不得单独入库。",
        f"- 当前 require_vision={require_vision}：默认要求截图经过 vision enrichment 后产生视觉补充。",
        "- frame kind 只允许 lineup_table / hero_detail / skill_detail / battle_report / land_risk / gameplay_ui。",
        "- lineup 必须至少包含 2 个 canonical 武将，并同时获得视觉实体与字幕实体支持。",
        "- 默认不写入正式 `knowledge_sources/`；必须显式传 `--publish` 才会发布。",
        "- 自动抽取的 hero/skill 仅进入 staging，不自动覆盖正式静态资料。",
        "- 正式 `knowledge_sources/` 只接收 lineup/combat，且跳过已有 topic，避免把低置信自动抽取覆盖人工知识。",
        "",
        "## 逐视频结果",
        "",
        "| BVID | 状态 | 字幕行 | 本地截图 | 视觉 segment | Lineup | Hero | Skill | Combat | Title |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for result in results:
        counts = result["filtered_counts"]
        fetch_summary = result["fetch_summary"] or {}
        if result["pipeline_ok"] and result["valid_segment_count"] > 0:
            status = "accepted"
        elif result["frame_count"] <= 0:
            status = "skipped_no_frame"
        elif not result["pipeline_ok"]:
            status = "pipeline_failed"
        else:
            status = "skipped_no_vision_segment"
        title = str(result.get("title") or "").replace("|", "\\|")[:90]
        lines.append(
            f"| {result['bvid']} | {status} | {int(fetch_summary.get('subtitle_line_count') or 0)} | "
            f"{result['frame_count']} | {result['valid_segment_count']} | {counts['lineup']} | "
            f"{counts['hero']} | {counts['skill']} | {counts['combat']} | {title} |"
        )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = _project_root()
    paths = ProcessPaths(
        raw_dir=_resolve_path(args.raw_dir, project_root),
        frame_dir=_resolve_path(args.frame_dir, project_root),
        workspace_root=_resolve_path(args.workspace_root, project_root),
        staging_output=_resolve_path(args.staging_output, project_root),
        summary_output=_resolve_path(args.summary_output, project_root),
        knowledge_root=_resolve_path(args.knowledge_root, project_root),
    )
    for directory in [paths.raw_dir, paths.frame_dir, paths.workspace_root]:
        directory.mkdir(parents=True, exist_ok=True)
    env = _build_env(project_root)
    candidates = _load_manifest(args, project_root)
    require_vision = not args.allow_no_vision
    quality_context = load_evidence_quality_context(_package_root(project_root))
    manifest_ref = args.manifest or args.manifest_git_ref

    results: list[dict[str, Any]] = []
    start = time.time()
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        future_map = {
            pool.submit(
                _process_one,
                candidate,
                project_root=project_root,
                paths=paths,
                env=env,
                extractor=args.extractor,
                frames_per_segment=args.frames_per_segment,
                frame_interval=args.frame_interval,
                frame_start=args.frame_start,
                frame_max_count=args.frame_max_count,
                require_vision=require_vision,
                quality_context=quality_context,
            ): candidate
            for candidate in candidates
        }
        for index, future in enumerate(as_completed(future_map), start=1):
            result = future.result()
            results.append(result)
            counts = result["filtered_counts"]
            status = "accepted" if result["pipeline_ok"] and result["valid_segment_count"] > 0 else "skipped"
            print(
                f"[{index:03d}/{len(candidates)}] {status} {result['bvid']} "
                f"frames={result['frame_count']} vision_segments={result['valid_segment_count']} "
                f"lineup={counts['lineup']} hero={counts['hero']} skill={counts['skill']} combat={counts['combat']} "
                f"elapsed={result['elapsed_s']}s",
                flush=True,
            )

    order = {str(candidate["bvid"]): index for index, candidate in enumerate(candidates)}
    results.sort(key=lambda item: order.get(item["bvid"], sys.maxsize))
    staging_items: list[dict[str, Any]] = []
    publish_candidates: list[KnowledgeEntry] = []
    for result in results:
        staging_items.extend(result["staging_items"])
        publish_candidates.extend(result["publish_entries"])

    paths.staging_output.parent.mkdir(parents=True, exist_ok=True)
    paths.staging_output.write_text(
        yaml.dump(staging_items, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    selected_publish, skipped_existing, skipped_duplicate = _filter_publishable(
        publish_candidates,
        knowledge_root=paths.knowledge_root,
        min_confidence=args.min_confidence,
    )
    publish_stats = {} if (args.no_publish or not args.publish) else publish_entries(selected_publish, paths.knowledge_root)
    _write_summary(
        paths.summary_output,
        manifest_ref=str(manifest_ref),
        results=results,
        staging_count=len(staging_items),
        selected_publish=selected_publish,
        publish_stats=publish_stats,
        skipped_existing=skipped_existing,
        skipped_duplicate=skipped_duplicate,
        require_vision=require_vision,
    )
    print(
        json.dumps(
            {
                "elapsed_s": round(time.time() - start, 2),
                "videos": len(results),
                "accepted_videos": sum(1 for result in results if result["pipeline_ok"] and result["valid_segment_count"] > 0),
                "staging_entries": len(staging_items),
                "publishable_entries": len(selected_publish),
                "publish_executed": bool(args.publish and not args.no_publish),
                "publish_stats": publish_stats,
                "staging_output": str(paths.staging_output),
                "summary_output": str(paths.summary_output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
