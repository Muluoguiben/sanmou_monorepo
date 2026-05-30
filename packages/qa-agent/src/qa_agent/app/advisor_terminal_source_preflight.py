from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qa_agent.mcp_server.advisor_tools import AdvisorReplayTools


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight low-risk Advisor terminal source evidence before writing "
            "it to the golden expectation manifest."
        )
    )
    parser.add_argument(
        "--action-type",
        required=True,
        help="Low-risk action type, such as claim_chapter_reward.",
    )
    parser.add_argument(
        "--evidence-json",
        required=True,
        help="Path to a terminal_source_evidence JSON object.",
    )
    parser.add_argument(
        "--fixture",
        help="Optional fixture name that will own this evidence.",
    )
    parser.add_argument(
        "--page",
        help="Optional manifest page override.",
    )
    parser.add_argument(
        "--workspace-root",
        help="Optional Sanmou monorepo root. Defaults to the parent workspace.",
    )
    return parser


def load_terminal_source_evidence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("terminal source evidence JSON must be an object")
    return payload


def evaluate_terminal_source_evidence(
    *,
    action_type: str,
    terminal_source_evidence: dict[str, Any],
    fixture: str | None = None,
    page: str | None = None,
    workspace_root: Path | None = None,
) -> dict[str, Any]:
    if workspace_root is None:
        qa_project_root = Path(__file__).resolve().parents[3]
        tools = AdvisorReplayTools.from_qa_project_root(qa_project_root)
    else:
        tools = AdvisorReplayTools(workspace_root=workspace_root)
    return tools.terminal_source_evidence_eval(
        action_type=action_type,
        terminal_source_evidence=terminal_source_evidence,
        fixture=fixture,
        page=page,
    )


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    evidence = load_terminal_source_evidence(Path(args.evidence_json))
    payload = evaluate_terminal_source_evidence(
        action_type=args.action_type,
        terminal_source_evidence=evidence,
        fixture=args.fixture,
        page=args.page,
        workspace_root=Path(args.workspace_root) if args.workspace_root else None,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
