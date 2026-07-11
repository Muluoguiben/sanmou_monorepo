"""Compile an immutable demonstration into review-only local artifacts."""
from __future__ import annotations

import json
import re
from pathlib import Path

from pioneer_agent.record_replay.models import CompilationReport, ReplayPlan
from pioneer_agent.record_replay.replayer import build_replay_plan
from pioneer_agent.record_replay.session_store import (
    atomic_write_bytes,
    atomic_write_json,
    load_recording,
)


def compile_recording(root: Path) -> CompilationReport:
    recording = load_recording(root, require_complete=True, verify_images=True)
    plan = build_replay_plan(recording)
    compiled_dir = _ensure_confined_directory(
        recording.root, recording.root / "compiled"
    )
    skill_dir = _ensure_confined_directory(
        recording.root, compiled_dir / "draft_skill"
    )

    candidates_path = _confined_output_path(
        recording.root, compiled_dir / "action_candidates.jsonl"
    )
    candidates_payload = b"".join(
        (action.model_dump_json() + "\n").encode("utf-8")
        for action in plan.actions
    )
    atomic_write_bytes(candidates_path, candidates_payload)

    replay_path = _confined_output_path(
        recording.root, compiled_dir / "replay_plan.json"
    )
    atomic_write_json(replay_path, plan.model_dump(mode="json"))

    draft_skill_path = _confined_output_path(
        recording.root, skill_dir / "SKILL.md"
    )
    atomic_write_bytes(
        draft_skill_path,
        _render_draft_skill(recording.manifest.workflow_name, plan).encode("utf-8"),
    )

    report = CompilationReport(
        session_id=recording.manifest.session_id,
        source_events_sha256=plan.source_events_sha256,
        candidate_count=len(plan.actions),
        ambiguous_count=sum(action.ambiguous_burst for action in plan.actions),
        geometry_changed_count=sum(action.geometry_changed for action in plan.actions),
        action_candidates_path=str(candidates_path),
        replay_plan_path=str(replay_path),
        draft_skill_path=str(draft_skill_path),
    )
    report_path = _confined_output_path(
        recording.root, compiled_dir / "compilation_report.json"
    )
    atomic_write_json(report_path, report.model_dump(mode="json"))
    return report


def _render_draft_skill(workflow_name: str, plan: ReplayPlan) -> str:
    slug = _skill_slug(workflow_name)
    description = (
        "Review-only draft inferred from one Windows Sanmou demonstration of "
        f"{workflow_name}. Use to annotate semantic targets, preconditions, verifier "
        "expectations, and holdout eval cases before any replay."
    )
    lines = [
        "---",
        f"name: {slug}-recorded-draft",
        f"description: {json.dumps(description, ensure_ascii=False)}",
        "---",
        "",
        f"# {workflow_name}",
        "",
        "> Status: unreviewed single-demonstration draft. Execution authority: none.",
        f"> Source events SHA-256: `{plan.source_events_sha256}`.",
        "> Sample coordinates are evidence only; never use them as live dispatch authority.",
        "",
        "## Required promotion work",
        "",
        "1. Name every semantic target and define supported start pages.",
        "2. Define observable preconditions and stop on unknown UI state.",
        "3. Replace sample coordinates with reviewed semantic resolution.",
        "4. Define a fresh-frame post-condition verifier and negative cases.",
        "5. Pass safety allowlist review plus an independent holdout eval.",
        "6. Forward-test the reviewed skill without exposing this demonstration as the answer.",
        "",
        "## Recorded steps",
        "",
        "| # | Primitive | Sample input | Before frame | After frame | Flags |",
        "|---:|---|---|---|---|---|",
    ]
    for action in plan.actions:
        flags = []
        if action.ambiguous_burst:
            flags.append("ambiguous-burst")
        if action.geometry_changed:
            flags.append("geometry-changed")
        lines.append(
            "| {order} | `{primitive}` | `{input}` | `{before}` | `{after}` | {flags} |".format(
                order=action.order + 1,
                primitive=action.primitive.value,
                input=json.dumps(action.input, ensure_ascii=False, separators=(",", ":")),
                before=action.before_frame.path,
                after=action.after_frame.path,
                flags=", ".join(flags) or "unreviewed",
            )
        )
    lines.extend(
        [
            "",
            "## Replay boundary",
            "",
            "This M0 draft may only support an offline dry-run plan. Satisfying future evidence gates establishes eligibility for a separate reviewed semantic implementation; it never unlocks live replay in this artifact.",
            "",
        ]
    )
    return "\n".join(lines)


def _skill_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        slug = "sanmou-workflow"
    if not slug.startswith("sanmou-"):
        slug = f"sanmou-{slug}"
    return slug[:48].rstrip("-")


def _ensure_confined_directory(root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"compiler output directory cannot be a symlink: {path.name}")
    try:
        path.mkdir(exist_ok=True)
    except OSError as exc:
        raise ValueError(f"compiler output directory is unavailable: {path.name}") from exc
    if path.is_symlink():
        raise ValueError(f"compiler output directory cannot be a symlink: {path.name}")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"compiler output directory is unavailable: {path.name}") from exc
    if not resolved.is_dir() or not _is_within(root, resolved):
        raise ValueError("compiler output directory escapes the session root")
    return resolved


def _confined_output_path(root: Path, path: Path) -> Path:
    if path.is_symlink():
        raise ValueError(f"compiler output file cannot be a symlink: {path.name}")
    if path.exists() and not path.is_file():
        raise ValueError(f"compiler output path is not a file: {path.name}")
    try:
        resolved_parent = path.parent.resolve(strict=True)
    except OSError as exc:
        raise ValueError(f"compiler output parent is unavailable: {path.name}") from exc
    if not _is_within(root, resolved_parent):
        raise ValueError("compiler output path escapes the session root")
    return path


def _is_within(root: Path, path: Path) -> bool:
    return path == root or root in path.parents
