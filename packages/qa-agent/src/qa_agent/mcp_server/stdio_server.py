from __future__ import annotations

import argparse
from pathlib import Path

from qa_agent.knowledge.source_paths import discover_source_paths
from qa_agent.mcp_server.server import create_mcp_server
from qa_agent.mcp_server.tooling import KnowledgeToolHandler
from qa_agent.service.query_service import QueryService

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Sanguo KB MCP stdio server.")
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
    handler = KnowledgeToolHandler(service)
    create_mcp_server(handler).run(transport="stdio")


if __name__ == "__main__":
    main()
