from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_decoded import load_client_decoded_mappings, load_decoded_hero_export
from qa_agent.ingestion.client_decoded_audit import (
    build_client_decoded_audit_report,
    load_knowledge_entries_from_dir,
    write_client_decoded_audit_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit a decoded NSLG hero export before qa-agent staging review and publish."
    )
    parser.add_argument("--input", required=True, help="Path to hero_readable_export_round29.json-like input.")
    parser.add_argument("--output", required=True, help="YAML audit report output path.")
    parser.add_argument("--source-id", default="hero-readable-export-round29", help="Stable source id for source_ref.")
    parser.add_argument("--mappings", help="Optional YAML mapping for client hero/skill ids to canonical KB names.")
    parser.add_argument(
        "--knowledge-dir",
        help="Optional knowledge_sources root used to validate mapped canonical topics.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    export = load_decoded_hero_export(Path(args.input))
    mappings = load_client_decoded_mappings(Path(args.mappings)) if args.mappings else None
    knowledge_entries = load_knowledge_entries_from_dir(Path(args.knowledge_dir)) if args.knowledge_dir else []
    report = build_client_decoded_audit_report(
        export,
        source_id=args.source_id,
        mappings=mappings,
        knowledge_entries=knowledge_entries,
    )
    write_client_decoded_audit_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": args.source_id,
                "candidate_entries": report.staging["candidate_entries"],
                "mapped_heroes": report.hero_coverage["mapped_heroes"],
                "unmapped_heroes": len(report.hero_coverage["unmapped_heroes"]),
                "mapped_skill_ids": report.skill_coverage["mapped_skill_ids"],
                "unmapped_skill_ids": len(report.skill_coverage["unmapped_skill_ids"]),
                "security_hits": len(report.security_scan["sensitive_markers_found"]),
                "review_blockers": len(report.review_blockers),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
