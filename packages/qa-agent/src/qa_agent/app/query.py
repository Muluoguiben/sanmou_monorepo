from __future__ import annotations

import argparse
import json
from pathlib import Path

from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.service.query_service import QueryService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Query the Sanguo KB locally.")
    parser.add_argument(
        "mode",
        choices=["lookup_topic", "answer_rule_question", "resolve_term"],
        help="Query mode to run.",
    )
    parser.add_argument("text", help="Topic, question, or term text.")
    parser.add_argument(
        "--domain",
        help="Optional domain filter such as building, chapter, combat, hero, resource, skill, team, or term.",
    )
    parser.add_argument(
        "--sources-dir",
        default="knowledge_sources",
        help="Directory that stores YAML knowledge sources.",
    )
    return parser


def main() -> None:
    parser = _build_parser()
    args = parser.parse_args()
    project_root = Path(__file__).resolve().parents[3]
    source_paths = discover_source_paths(project_root / args.sources_dir)
    service = QueryService.from_source_paths(source_paths)

    if args.mode == "lookup_topic":
        result = service.lookup_topic(args.text, args.domain)
    elif args.mode == "answer_rule_question":
        result = service.answer_rule_question(args.text, args.domain)
    else:
        result = service.resolve_term(args.text, args.domain)

    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
