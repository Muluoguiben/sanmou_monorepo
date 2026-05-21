from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.ingestion.client_nep2_luascripts import (
    build_nep2_luascripts_evidence_report,
    load_nep2_luascripts_json,
    write_nep2_luascripts_evidence_report,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sanitize NEP2 LuaScripts/static-protector evidence into qa-agent ingestion evidence."
    )
    parser.add_argument("--candidate-scan", required=True, help="Path to nep2_luascripts_candidate_round34.json.")
    parser.add_argument("--init-scan", required=True, help="Path to nep2_init_luascripts_scan_round34.json.")
    parser.add_argument("--output", required=True, help="YAML evidence output path.")
    parser.add_argument("--source-id", default="nep2-luascripts-round34", help="Stable source id for this report.")
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    candidate_scan = load_nep2_luascripts_json(Path(args.candidate_scan))
    init_scan = load_nep2_luascripts_json(Path(args.init_scan))
    report = build_nep2_luascripts_evidence_report(
        candidate_scan,
        init_scan,
        source_id=args.source_id,
    )
    write_nep2_luascripts_evidence_report(report, Path(args.output))
    print(
        json.dumps(
            {
                "output": args.output,
                "source_id": args.source_id,
                "init_luascripts_occurrences": len(report.init_luascripts_occurrences),
                "selected_candidate_strings": len(report.selected_candidate_strings),
                "xref_count": report.xref_count,
                "next_static_targets": len(report.next_static_targets),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
