from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from qa_agent.ingestion.models import ReviewStatus, StagingEntry
from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.loader import load_entries
from qa_agent.service.query_service import QueryService
from qa_agent.video import VideoEvidenceBundle, build_video_knowledge_document, dump_video_knowledge_document, stage_all_video_entries
from qa_agent.knowledge.source_paths import discover_source_paths

from .video_extract import _resolve_enriched_document


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the end-to-end video knowledge pipeline.")
    parser.add_argument("--input", required=True, help="Path to the raw transcript/OCR bundle YAML.")
    parser.add_argument("--workspace", required=True, help="Directory to place generated artifacts.")
    parser.add_argument(
        "--extractor",
        choices=["auto", "gemini", "heuristic", "none"],
        default="heuristic",
        help="Knowledge extraction mode for the pipeline.",
    )
    parser.add_argument("--api-key", help="Gemini API key for extractor=gemini/auto.")
    parser.add_argument("--model", default="gemini-2.0-flash")
    parser.add_argument("--timeout", type=int, default=60)
    return parser


def _resolve_path(raw: str, project_root: Path) -> Path:
    path = Path(raw)
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return (project_root / path).resolve()


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    input_path = _resolve_path(args.input, project_root)
    workspace = _resolve_path(args.workspace, project_root)
    workspace.mkdir(parents=True, exist_ok=True)

    raw_bundle = VideoEvidenceBundle.model_validate(yaml.safe_load(input_path.read_text(encoding="utf-8")) or {})
    evidence_document = build_video_knowledge_document(raw_bundle)
    evidence_path = workspace / "video-evidence.yaml"
    dump_video_knowledge_document(evidence_path, evidence_document)

    enriched = _resolve_enriched_document(
        document=evidence_document,
        project_root=project_root,
        extractor_mode=args.extractor,
        api_key=args.api_key,
        model=args.model,
        timeout=args.timeout,
    )
    enriched_path = workspace / "video-knowledge.yaml"
    dump_video_knowledge_document(enriched_path, enriched)

    staged_entries, direct_entries = stage_all_video_entries(enriched, project_root)
    staged_entries = [
        StagingEntry(
            metadata=staged.metadata.model_copy(update={"review_status": ReviewStatus.REVIEWED}),
            entry=staged.entry,
        )
        for staged in staged_entries
    ]

    staging_path = workspace / "video-staging-reviewed.yaml"
    staging_path.write_text(
        yaml.dump([item.model_dump(mode="json") for item in staged_entries], allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )

    knowledge_root = workspace / "knowledge_sources"
    published_entries = [entry.to_reviewed_entry() for entry in staged_entries]
    published_entries.extend(direct_entries)
    bucket_stats = publish_entries(published_entries, knowledge_root) if published_entries else {}

    query_results = {}
    if published_entries:
        source_paths = discover_source_paths(knowledge_root)
        service = QueryService(load_entries(source_paths))
        if enriched.lineup_candidates:
            query_results["lineup"] = service.lookup_topic(enriched.lineup_candidates[0].topic, domain="solution").model_dump(mode="json")
        if enriched.hero_candidates:
            query_results["hero"] = service.lookup_topic(enriched.hero_candidates[0].hero_name, domain="hero").model_dump(mode="json")
        if enriched.skill_candidates:
            query_results["skill"] = service.lookup_topic(enriched.skill_candidates[0].skill_name, domain="skill").model_dump(mode="json")
        if enriched.combat_candidates:
            query_results["combat"] = service.lookup_topic(enriched.combat_candidates[0].topic, domain="combat").model_dump(mode="json")

    print(
        json.dumps(
            {
                "video_id": enriched.source.video_id,
                "extractor": args.extractor,
                "lineup_candidates": len(enriched.lineup_candidates),
                "hero_candidates": len(enriched.hero_candidates),
                "skill_candidates": len(enriched.skill_candidates),
                "combat_candidates": len(enriched.combat_candidates),
                "evidence_path": str(evidence_path),
                "enriched_path": str(enriched_path),
                "staging_path": str(staging_path),
                "knowledge_root": str(knowledge_root),
                "bucket_stats": bucket_stats,
                "query_results": query_results,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
