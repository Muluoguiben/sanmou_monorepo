from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import yaml

from qa_agent.ingestion.models import ReviewStatus, StagingEntry
from qa_agent.video import (
    GeminiVideoKnowledgeExtractor,
    HeuristicVideoKnowledgeExtractor,
    OpenAIVideoKnowledgeExtractor,
    dump_video_knowledge_document,
    load_video_knowledge_document,
    stage_lineup_candidate,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Extract lineup knowledge candidates from Bilibili video evidence using Gemini.")
    parser.add_argument("--input", required=True, help="Path to the raw video evidence YAML file.")
    parser.add_argument("--output", help="Optional path to write the enriched video knowledge YAML.")
    parser.add_argument("--staging-output", help="Optional path to write lineup staging entries YAML.")
    parser.add_argument(
        "--extractor",
        choices=["auto", "openai", "gemini", "heuristic", "none"],
        default="auto",
        help="How to obtain lineup candidates. 'auto' prefers existing candidates, then OpenAI (sub2api), then Gemini, then heuristic fallback.",
    )
    parser.add_argument(
        "--review-status",
        choices=[status.value for status in ReviewStatus],
        default=ReviewStatus.NORMALIZED.value,
        help="Review status to attach to emitted staging entries.",
    )
    parser.add_argument("--model", default=None, help="Model name (extractor-specific default).")
    parser.add_argument("--timeout", type=int, default=60, help="HTTP timeout in seconds (Gemini only).")
    parser.add_argument("--api-key", help="Gemini API key. Falls back to GEMINI_API_KEY env var.")
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
    output_path = _resolve_path(args.output, project_root) if args.output else None
    staging_output_path = _resolve_path(args.staging_output, project_root) if args.staging_output else None
    document = load_video_knowledge_document(input_path)
    api_key = args.api_key or os.getenv("GEMINI_API_KEY")
    enriched = _resolve_enriched_document(
        document=document,
        project_root=project_root,
        extractor_mode=args.extractor,
        api_key=api_key,
        model=args.model,
        timeout=args.timeout,
    )

    if output_path:
        dump_video_knowledge_document(output_path, enriched)

    review_status = ReviewStatus(args.review_status)
    staged_entries = []
    for candidate in enriched.lineup_candidates:
        staged = stage_lineup_candidate(enriched, candidate)
        if review_status != staged.metadata.review_status:
            staged = StagingEntry(
                metadata=staged.metadata.model_copy(update={"review_status": review_status}),
                entry=staged.entry,
            )
        staged_entries.append(staged)
    if staging_output_path:
        staging_output_path.parent.mkdir(parents=True, exist_ok=True)
        text = yaml.dump([item.model_dump(mode="json") for item in staged_entries], allow_unicode=True, default_flow_style=False, sort_keys=False)
        staging_output_path.write_text(text, encoding="utf-8")

    if not output_path and not staging_output_path:
        print(json.dumps(enriched.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(
            json.dumps(
                {
                    "lineup_candidates": len(enriched.lineup_candidates),
                    "extractor": args.extractor,
                    "output": str(output_path) if output_path else None,
                    "staging_output": str(staging_output_path) if staging_output_path else None,
                },
                ensure_ascii=False,
                indent=2,
            )
        )


def _resolve_enriched_document(
    document,
    project_root: Path,
    extractor_mode: str,
    api_key: str | None,
    model: str | None,
    timeout: int,
):
    if extractor_mode == "none":
        if document.lineup_candidates:
            return document
        raise RuntimeError("Input document does not include lineup_candidates and extractor=none was requested.")

    if extractor_mode == "heuristic":
        extractor = HeuristicVideoKnowledgeExtractor.from_project_root(project_root)
        return extractor.enrich_document(document)

    if extractor_mode == "openai":
        openai_kwargs = {}
        if model:
            openai_kwargs["model"] = model
        extractor = OpenAIVideoKnowledgeExtractor(**openai_kwargs)
        return extractor.enrich_document(document)

    if extractor_mode == "gemini":
        if not api_key:
            raise RuntimeError("Gemini API key is required when extractor=gemini.")
        gemini_model = model or "gemini-2.0-flash"
        extractor = GeminiVideoKnowledgeExtractor(api_key=api_key, model=gemini_model, timeout_sec=timeout)
        return extractor.enrich_document(document)

    if document.lineup_candidates:
        return document
    try:
        extractor = OpenAIVideoKnowledgeExtractor(model=model) if model else OpenAIVideoKnowledgeExtractor()
        return extractor.enrich_document(document)
    except Exception as exc:  # noqa: BLE001
        print(f"OpenAI extraction failed, trying Gemini: {exc}", file=sys.stderr)
    if api_key:
        try:
            gemini_model = model or "gemini-2.0-flash"
            extractor = GeminiVideoKnowledgeExtractor(api_key=api_key, model=gemini_model, timeout_sec=timeout)
            return extractor.enrich_document(document)
        except RuntimeError as exc:
            print(f"Gemini extraction failed, falling back to heuristic extractor: {exc}", file=sys.stderr)
    extractor = HeuristicVideoKnowledgeExtractor.from_project_root(project_root)
    return extractor.enrich_document(document)


if __name__ == "__main__":
    main()
