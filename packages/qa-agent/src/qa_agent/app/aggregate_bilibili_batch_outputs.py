from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import yaml

from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.models import Domain, EntryKind, KnowledgeEntry
from qa_agent.video import load_video_knowledge_document, stage_all_video_entries
from qa_agent.video.evidence_quality import filter_document_for_evidence_quality, load_evidence_quality_context
from qa_agent.video.heuristic import HeuristicVideoKnowledgeExtractor


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Aggregate frame-gated Bilibili batch outputs.")
    parser.add_argument("--batch-staging-glob", required=True, help="Glob for per-batch staging YAML files.")
    parser.add_argument("--workspace-root", required=True, help="Root containing per-batch temp workspaces.")
    parser.add_argument("--staging-output", required=True, help="Combined staging YAML output.")
    parser.add_argument("--summary-output", required=True, help="Combined Markdown summary output.")
    parser.add_argument("--knowledge-root", default="packages/qa-agent/knowledge_sources")
    parser.add_argument("--min-confidence", type=float, default=0.5)
    parser.add_argument("--publish", action="store_true", help="Update formal knowledge_sources. Default is staging-only.")
    parser.add_argument("--no-publish", action="store_true")
    parser.add_argument("--no-reextract-heuristic", action="store_true", help="Use existing candidates from workspace docs instead of recomputing heuristic candidates.")
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


def _load_staging(path: Path) -> list[dict]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or []
    if not isinstance(data, list):
        raise ValueError(f"staging file must be a list: {path}")
    return data


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


def _stage_entries_from_workspaces(
    workspace_root: Path,
    project_root: Path,
    *,
    reextract_heuristic: bool,
) -> tuple[list[dict], list[KnowledgeEntry], dict[str, object]]:
    package_root = _package_root(project_root)
    quality_context = load_evidence_quality_context(package_root)
    extractor = HeuristicVideoKnowledgeExtractor.from_project_root(package_root) if reextract_heuristic else None
    staged_items: list[dict] = []
    formal_entries: list[KnowledgeEntry] = []
    stats = {
        "workspace_docs": 0,
        "quality_before": {"lineup": 0, "hero": 0, "skill": 0, "combat": 0},
        "quality_after": {"lineup": 0, "hero": 0, "skill": 0, "combat": 0},
        "reject_reasons": {},
        "rejected_segment_kinds": {},
    }
    for path in sorted(workspace_root.glob("batch-*/**/video-knowledge-frame-gated.yaml")):
        document = load_video_knowledge_document(path)
        if extractor is not None:
            document = extractor.enrich_document(
                document.model_copy(
                    update={
                        "lineup_candidates": [],
                        "hero_candidates": [],
                        "skill_candidates": [],
                        "combat_candidates": [],
                    }
                )
            )
        filtered, quality_stats = filter_document_for_evidence_quality(document, quality_context)
        stats["workspace_docs"] = int(stats["workspace_docs"]) + 1
        _merge_count_dict(stats["quality_before"], quality_stats["before"])
        _merge_count_dict(stats["quality_after"], quality_stats["after"])
        _merge_count_dict(stats["reject_reasons"], quality_stats["reject_reasons"])
        _merge_count_dict(stats["rejected_segment_kinds"], quality_stats["rejected_segment_kinds"])
        staged, direct = stage_all_video_entries(filtered, package_root)
        staged_items.extend(
            _with_review_note(item, "evidence_quality_gate: allowed gameplay frame kind + canonical entity + visual/subtitle support").model_dump(mode="json")
            for item in staged
        )
        formal_entries.extend(
            item.entry
            for item in staged
            if item.entry.domain == Domain.SOLUTION and item.entry.entry_kind == EntryKind.LINEUP_SOLUTION
        )
        formal_entries.extend(direct)
    return staged_items, formal_entries, stats


def _merge_count_dict(target: object, source: object) -> None:
    if not isinstance(target, dict) or not isinstance(source, dict):
        return
    for key, value in source.items():
        target[key] = int(target.get(key, 0)) + int(value)


def _with_review_note(item, note: str):
    notes = list(item.metadata.review_notes)
    if note not in notes:
        notes.append(note)
    return item.model_copy(update={"metadata": item.metadata.model_copy(update={"review_notes": notes})})


def _count_entries_by_kind(items: list[dict]) -> dict[str, int]:
    counts = {"lineup": 0, "hero": 0, "skill": 0}
    for item in items:
        entry = item.get("entry") or {}
        kind = entry.get("entry_kind")
        if kind == "lineup_solution":
            counts["lineup"] += 1
        elif kind == "hero_profile":
            counts["hero"] += 1
        elif kind == "skill_profile":
            counts["skill"] += 1
    return counts


def main() -> None:
    args = _build_parser().parse_args()
    project_root = _project_root()
    knowledge_root = _resolve_path(args.knowledge_root, project_root)
    workspace_root = _resolve_path(args.workspace_root, project_root)
    staging_output = _resolve_path(args.staging_output, project_root)
    summary_output = _resolve_path(args.summary_output, project_root)
    staging_paths = sorted(project_root.glob(args.batch_staging_glob))

    combined, formal_entries, quality_stats = _stage_entries_from_workspaces(
        workspace_root,
        project_root,
        reextract_heuristic=not args.no_reextract_heuristic,
    )
    if not combined:
        for path in staging_paths:
            combined.extend(_load_staging(path))
    staging_output.parent.mkdir(parents=True, exist_ok=True)
    staging_output.write_text(
        yaml.dump(combined, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    selected, skipped_existing, skipped_duplicate = _filter_publishable(
        formal_entries,
        knowledge_root=knowledge_root,
        min_confidence=args.min_confidence,
    )
    publish_stats = {} if (args.no_publish or not args.publish) else publish_entries(selected, knowledge_root)
    counts = _count_entries_by_kind(combined)
    summary_lines = [
        "# Bilibili 三谋开荒 100 视频聚合结果",
        "",
        f"- 运行时间：{datetime.now(timezone.utc).replace(microsecond=0).isoformat()}",
        f"- batch staging 文件数：{len(staging_paths)}",
        f"- combined staging entries：{len(combined)}",
        f"- staging counts：`{json.dumps(counts, ensure_ascii=False, sort_keys=True)}`",
        f"- formal candidates before filter：{len(formal_entries)}",
        f"- formal publishable selected：{len(selected)}",
        f"- formal publish executed：{bool(args.publish and not args.no_publish)}",
        f"- skipped_existing_topic：{skipped_existing}",
        f"- skipped_batch_duplicate：{skipped_duplicate}",
        f"- publish stats：`{json.dumps(publish_stats, ensure_ascii=False, sort_keys=True)}`",
        f"- quality stats：`{json.dumps(quality_stats, ensure_ascii=False, sort_keys=True)}`",
        "",
        "## 门禁",
        "",
        "- 聚合阶段从 workspace 的 `video-knowledge-frame-gated.yaml` 重新生成 staging，不再盲信旧 batch staging。",
        "- frame kind 只允许 lineup_table / hero_detail / skill_detail / battle_report / land_risk / gameplay_ui。",
        "- lineup 必须至少包含 2 个 canonical 武将，并同时获得视觉实体与字幕实体支持。",
        "- 默认不写入正式 `knowledge_sources/`；必须显式传 `--publish` 才会发布。",
        "- hero/skill 自动抽取只保留在 staging，不自动覆盖正式静态资料。",
    ]
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text("\n".join(summary_lines) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "batch_staging_files": len(staging_paths),
                "combined_staging_entries": len(combined),
                "formal_candidates": len(formal_entries),
                "formal_publishable_selected": len(selected),
                "formal_publish_executed": bool(args.publish and not args.no_publish),
                "publish_stats": publish_stats,
                "quality_stats": quality_stats,
                "staging_output": str(staging_output),
                "summary_output": str(summary_output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
