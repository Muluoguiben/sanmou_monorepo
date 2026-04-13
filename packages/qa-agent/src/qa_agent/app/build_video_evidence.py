from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml

from qa_agent.video import VideoEvidenceBundle, build_video_knowledge_document, dump_video_knowledge_document


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a normalized video evidence document from a raw transcript/OCR bundle.")
    parser.add_argument("--input", required=True, help="Path to the raw bundle YAML file.")
    parser.add_argument("--output", required=True, help="Path to the normalized video evidence YAML file.")
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
    output_path = _resolve_path(args.output, project_root)

    data = yaml.safe_load(input_path.read_text(encoding="utf-8")) or {}
    bundle = VideoEvidenceBundle.model_validate(data)
    document = build_video_knowledge_document(bundle)
    dump_video_knowledge_document(output_path, document)
    print(
        json.dumps(
            {
                "video_id": document.source.video_id,
                "segments": len(document.segments),
                "output": str(output_path),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
