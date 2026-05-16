from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from qa_agent.ingestion.models import ReviewStatus, StagingEntry
from qa_agent.ingestion.publish import publish_entries
from qa_agent.knowledge.loader import load_entries
from qa_agent.retrieval.retriever import Retriever
from qa_agent.service.query_service import QueryService
from qa_agent.video import VideoEvidenceBundle, build_video_knowledge_document, dump_video_knowledge_document, stage_all_video_entries
from qa_agent.video.subtitle_normalizer import (
    build_dictionary_from_profiles,
    default_homophones_path,
    default_knowledge_sources_dir,
    normalize_candidate_fields,
    normalize_document,
)
from qa_agent.video.vision_enrichment import enrich_document_with_vision
from qa_agent.vision.extractor import ImageExtractor
from qa_agent.knowledge.source_paths import discover_source_paths

from .video_extract import _resolve_enriched_document


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the end-to-end video knowledge pipeline.")
    parser.add_argument("--input", required=True, help="Path to the raw transcript/OCR bundle YAML.")
    parser.add_argument("--workspace", required=True, help="Directory to place generated artifacts.")
    parser.add_argument(
        "--extractor",
        choices=["auto", "openai", "gemini", "heuristic", "none"],
        default="openai",
        help="Knowledge extraction mode for the pipeline. Default 'openai' uses sub2api gpt-5.4.",
    )
    parser.add_argument("--api-key", help="Gemini API key for extractor=gemini/auto.")
    parser.add_argument("--model", default=None, help="Model name (extractor-specific default).")
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument(
        "--enrich-frames",
        action="store_true",
        help="Pre-process segments that have frame_refs with ImageExtractor before running the LLM extractor.",
    )
    parser.add_argument(
        "--frames-per-segment",
        type=int,
        default=3,
        help="Max frames sent to the vision model per segment (default 3).",
    )
    parser.add_argument(
        "--normalize-subtitles",
        dest="normalize_subtitles",
        action="store_true",
        default=True,
        help="(Default on) Normalize Bilibili AI-subtitle 同音/形近错字 against KB hero/skill profiles + manual homophones before LLM extraction.",
    )
    parser.add_argument(
        "--no-normalize-subtitles",
        dest="normalize_subtitles",
        action="store_false",
        help="Disable subtitle normalization (e.g. when sources are already clean).",
    )
    parser.add_argument(
        "--no-fuzzy-normalize",
        dest="fuzzy_normalize",
        action="store_false",
        default=True,
        help="Disable ≥3-char edit-distance-≤1 fuzzy fallback inside subtitle normalization (keep only exact homophone + alias).",
    )
    parser.add_argument(
        "--homophones",
        default=None,
        help="Path to subtitle homophones YAML. Defaults to packages/qa-agent/config/subtitle_homophones.yaml.",
    )
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

    # Subtitle normalization: rewrite Bilibili 中文 AI 字幕的同音/形近错字到 KB 正字。
    normalization_log_entries: list = []
    normalization_stats = None
    normalization_log_path: Path | None = None
    if args.normalize_subtitles:
        homophones_path = (
            Path(args.homophones).expanduser().resolve()
            if args.homophones
            else default_homophones_path(project_root / "packages" / "qa-agent")
        )
        knowledge_sources_dir = default_knowledge_sources_dir(project_root / "packages" / "qa-agent")
        dictionary = build_dictionary_from_profiles(
            knowledge_sources_dir=knowledge_sources_dir,
            homophones_path=homophones_path,
        )
        evidence_document, segment_logs, normalization_stats = normalize_document(
            evidence_document,
            dictionary,
            enable_fuzzy=args.fuzzy_normalize,
        )
        normalization_log_entries.extend(segment_logs)
        # Stash dictionary for post-extraction sweep below.
        normalization_dictionary = dictionary
    else:
        normalization_dictionary = None

    evidence_path = workspace / "video-evidence.yaml"
    dump_video_knowledge_document(evidence_path, evidence_document)

    vision_stats = None
    if args.enrich_frames:
        knowledge_dir = project_root / "knowledge_sources"
        retriever = Retriever.from_knowledge_dir(knowledge_dir) if knowledge_dir.exists() else None
        image_extractor = ImageExtractor(retriever=retriever)
        evidence_document, vision_stats = enrich_document_with_vision(
            evidence_document,
            extractor=image_extractor,
            max_frames_per_segment=args.frames_per_segment,
        )
        dump_video_knowledge_document(evidence_path, evidence_document)

    enriched = _resolve_enriched_document(
        document=evidence_document,
        project_root=project_root,
        extractor_mode=args.extractor,
        api_key=args.api_key,
        model=args.model,
        timeout=args.timeout,
    )

    # Post-extraction sweep: even with normalized transcript, LLM may still emit
    # 同音错字 (especially in `hero_names` / `core_skills`). Re-apply the same
    # dictionary to all candidate fields so the staging YAML lands as canonical.
    if normalization_dictionary is not None:
        enriched = normalize_candidate_fields(
            enriched,
            normalization_dictionary,
            enable_fuzzy=args.fuzzy_normalize,
            log_sink=normalization_log_entries,
        )

    enriched_path = workspace / "video-knowledge.yaml"
    dump_video_knowledge_document(enriched_path, enriched)

    if normalization_log_entries:
        normalization_log_path = workspace / "subtitle-normalization-log.yaml"
        normalization_log_path.write_text(
            yaml.dump(
                [entry.model_dump(mode="json") for entry in normalization_log_entries],
                allow_unicode=True,
                default_flow_style=False,
                sort_keys=False,
            ),
            encoding="utf-8",
        )

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
                "vision_stats": (
                    {
                        "segments_processed": vision_stats.segments_processed,
                        "segments_enriched": vision_stats.segments_enriched,
                        "frames_analyzed": vision_stats.frames_analyzed,
                        "hero_hits": vision_stats.hero_hits,
                        "skill_hits": vision_stats.skill_hits,
                        "errors": vision_stats.errors,
                    }
                    if vision_stats is not None
                    else None
                ),
                "normalization_stats": (
                    {
                        "segments_processed": normalization_stats.segments_processed,
                        "segments_changed": normalization_stats.segments_changed,
                        "exact_replacements": normalization_stats.exact_replacements,
                        "fuzzy_replacements": normalization_stats.fuzzy_replacements,
                        "ambiguous_candidates": normalization_stats.ambiguous_candidates,
                        "log_path": str(normalization_log_path) if normalization_log_path else None,
                    }
                    if normalization_stats is not None
                    else None
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
