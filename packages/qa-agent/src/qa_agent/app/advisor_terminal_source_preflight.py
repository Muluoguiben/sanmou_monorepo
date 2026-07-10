from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from qa_agent.mcp_server.advisor_tools import AdvisorReplayTools, PR6_LOW_RISK_ACTIONS


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Preflight low-risk Advisor terminal source evidence before writing "
            "it to the golden expectation manifest."
        )
    )
    parser.add_argument(
        "--action-type",
        help="Low-risk action type, such as claim_chapter_reward.",
    )
    parser.add_argument(
        "--evidence-json",
        help="Path to a terminal_source_evidence JSON object.",
    )
    parser.add_argument(
        "--batch-json",
        help=(
            "Path to a JSON list, or an object with items, containing action_type "
            "and terminal_source_evidence/evidence_json entries."
        ),
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
    parser.add_argument(
        "--allow-partial-batch",
        action="store_true",
        help="For --batch-json, do not require all low-risk actions to be present.",
    )
    return parser


def load_terminal_source_evidence(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("terminal source evidence JSON must be an object")
    return payload


def load_terminal_source_batch(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items") if isinstance(payload, dict) else payload
    if not isinstance(items, list):
        raise ValueError("terminal source batch JSON must be a list or object with items")
    batch: list[dict[str, Any]] = []
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"batch item {index} must be an object")
        evidence = item.get("terminal_source_evidence")
        evidence_json = item.get("evidence_json")
        if evidence is None and isinstance(evidence_json, str):
            evidence_path = Path(evidence_json)
            if not evidence_path.is_absolute():
                evidence_path = path.parent / evidence_path
            evidence = load_terminal_source_evidence(evidence_path)
        if not isinstance(evidence, dict):
            raise ValueError(
                f"batch item {index} must include terminal_source_evidence or evidence_json"
            )
        batch.append({**item, "terminal_source_evidence": evidence})
    return batch


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


def evaluate_terminal_source_batch(
    *,
    items: list[dict[str, Any]],
    workspace_root: Path | None = None,
    require_all_low_risk_actions: bool = True,
) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    manifest_patch: dict[str, Any] = {}
    for item in items:
        result = evaluate_terminal_source_evidence(
            action_type=str(item.get("action_type")),
            terminal_source_evidence=item["terminal_source_evidence"],
            fixture=item.get("fixture"),
            page=item.get("page"),
            workspace_root=workspace_root,
        )
        results.append(result)
        manifest_patch.update(result.get("suggested_advisor_fixture_expectation_patch") or {})

    accepted_actions = sorted(
        {
            str(result.get("action_type"))
            for result in results
            if result.get("accepted_for_closure")
        }
    )
    staging_actions = sorted(
        {
            str(result.get("action_type"))
            for result in results
            if result.get("ready_for_staging")
        }
    )
    required_actions = list(PR6_LOW_RISK_ACTIONS) if require_all_low_risk_actions else []
    missing_actions = sorted(set(required_actions) - set(accepted_actions))
    failing_results = [
        {
            "action_type": result.get("action_type"),
            "fixture": result.get("fixture"),
            "missing_evidence": (result.get("review") or {}).get("missing_evidence") or [],
            "closure_disqualifiers": (
                (result.get("review") or {}).get("closure_disqualifiers") or []
            ),
        }
        for result in results
        if not result.get("accepted_for_closure")
    ]
    return {
        "checked": True,
        "ready": not failing_results and not missing_actions,
        "required_actions": required_actions,
        "accepted_actions": accepted_actions,
        "staging_actions": staging_actions,
        "missing_actions": missing_actions,
        "failing_results": failing_results,
        "results": results,
        "suggested_advisor_fixture_expectation_patch": manifest_patch,
    }


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    workspace_root = Path(args.workspace_root) if args.workspace_root else None
    if args.batch_json:
        payload = evaluate_terminal_source_batch(
            items=load_terminal_source_batch(Path(args.batch_json)),
            workspace_root=workspace_root,
            require_all_low_risk_actions=not args.allow_partial_batch,
        )
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload.get("ready") else 2
    if not args.action_type or not args.evidence_json:
        parser.error("--action-type and --evidence-json are required unless --batch-json is used")
    evidence = load_terminal_source_evidence(Path(args.evidence_json))
    payload = evaluate_terminal_source_evidence(
        action_type=args.action_type,
        terminal_source_evidence=evidence,
        fixture=args.fixture,
        page=args.page,
        workspace_root=workspace_root,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ready") else 2


if __name__ == "__main__":
    raise SystemExit(main())
