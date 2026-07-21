"""Windows Record & Replay CLI.

The ``record`` command starts a read-only Windows helper. ``replay`` is an
offline plan only; M0 intentionally has no live input-dispatch path.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path, PureWindowsPath
import re
import subprocess
from uuid import uuid4

from pioneer_agent.app.cli_utils import user_path
from pioneer_agent.record_replay.annotations import (
    annotation_summary,
    build_annotation_template,
    load_recording_annotation,
)
from pioneer_agent.record_replay.compiler import compile_recording
from pioneer_agent.record_replay.corpus_catalog import audit_corpus_catalog
from pioneer_agent.record_replay.dataset_registry import audit_dataset_registry
from pioneer_agent.record_replay.replayer import build_replay_plan
from pioneer_agent.record_replay.session_store import load_recording
from pioneer_agent.record_replay.validation import validate_workflow_name


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Record, validate, compile, or dry-run a Sanmou Windows demonstration."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    record_parser = subparsers.add_parser("record", help="Record a focused Windows demonstration.")
    record_parser.add_argument("--workflow-name", required=True)
    record_parser.add_argument("--duration-seconds", type=float, default=0.0)
    record_parser.add_argument("--backend", choices=("auto", "wgc", "dxgi"), default="auto")
    record_parser.add_argument("--settle-ms", type=int, default=350)
    record_parser.add_argument("--long-edge", type=int, default=1280)
    record_parser.add_argument("--image-format", choices=("webp", "png"), default="webp")
    record_parser.add_argument("--webp-quality", type=int, default=60)
    record_parser.add_argument("--max-events", type=int, default=500)
    record_parser.add_argument("--max-bytes", type=int, default=268_435_456)

    inspect_parser = subparsers.add_parser("inspect", help="Inspect manifest and integrity state.")
    inspect_parser.add_argument("session", type=user_path)

    validate_parser = subparsers.add_parser("validate", help="Strictly validate a completed session.")
    validate_parser.add_argument("session", type=user_path)

    compile_parser = subparsers.add_parser("compile", help="Compile review-only candidates and skill draft.")
    compile_parser.add_argument("session", type=user_path)

    annotation_template_parser = subparsers.add_parser(
        "annotation-template",
        help="Print a draft reviewer-annotation template without modifying raw evidence.",
    )
    annotation_template_parser.add_argument("session", type=user_path)
    annotation_template_parser.add_argument("--workflow-id", required=True)
    annotation_template_parser.add_argument(
        "--annotated-by", default="unreviewed-template"
    )

    annotation_validate_parser = subparsers.add_parser(
        "annotation-validate",
        help="Validate an explicit annotation against immutable raw evidence.",
    )
    annotation_validate_parser.add_argument("session", type=user_path)
    annotation_validate_parser.add_argument("annotation", type=user_path)
    annotation_validate_parser.add_argument("--require-approved", action="store_true")

    audit_dataset_parser = subparsers.add_parser(
        "audit-dataset",
        help="Audit one explicit reviewed generation/holdout registry without compiling it.",
    )
    audit_dataset_parser.add_argument("registry", type=user_path)
    audit_dataset_parser.add_argument("--sessions-root", type=user_path, required=True)
    audit_dataset_parser.add_argument("--reviews-root", type=user_path, required=True)

    audit_corpus_parser = subparsers.add_parser(
        "audit-corpus",
        help="Audit a closed multi-registry corpus and development-artifact lineage.",
    )
    audit_corpus_parser.add_argument("catalog", type=user_path)
    audit_corpus_parser.add_argument(
        "--registries-root", type=user_path, required=True
    )
    audit_corpus_parser.add_argument("--sessions-root", type=user_path, required=True)
    audit_corpus_parser.add_argument("--reviews-root", type=user_path, required=True)
    audit_corpus_parser.add_argument("--artifacts-root", type=user_path, required=True)

    replay_parser = subparsers.add_parser("replay", help="Build an offline dry-run replay plan.")
    replay_parser.add_argument("session", type=user_path)
    replay_parser.add_argument(
        "--execute",
        action="store_true",
        help="Unsupported safety sentinel; live replay is intentionally disabled.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "record":
            return _record(args)
        if args.command == "inspect":
            return _inspect(args.session)
        if args.command == "validate":
            recording = load_recording(args.session, require_complete=True, verify_images=True)
            _print_json(_summary(recording, integrity="valid"))
            return 0
        if args.command == "compile":
            report = compile_recording(args.session)
            _print_json(report.model_dump(mode="json"))
            return 0
        if args.command == "annotation-template":
            recording = load_recording(
                args.session, require_complete=True, verify_images=True
            )
            template = build_annotation_template(
                recording,
                workflow_id=args.workflow_id,
                annotated_by=args.annotated_by,
            )
            _print_json(template.model_dump(mode="json"))
            return 0
        if args.command == "annotation-validate":
            recording = load_recording(
                args.session, require_complete=True, verify_images=True
            )
            annotation = load_recording_annotation(
                recording,
                args.annotation,
                require_approved=args.require_approved,
            )
            _print_json(annotation_summary(recording, annotation))
            return 0
        if args.command == "audit-dataset":
            report = audit_dataset_registry(
                args.registry,
                sessions_root=args.sessions_root,
                reviews_root=args.reviews_root,
            )
            _print_json(report.model_dump(mode="json"))
            return 0
        if args.command == "audit-corpus":
            report = audit_corpus_catalog(
                args.catalog,
                registries_root=args.registries_root,
                sessions_root=args.sessions_root,
                reviews_root=args.reviews_root,
                artifacts_root=args.artifacts_root,
            )
            _print_json(report.model_dump(mode="json"))
            return 0
        if args.command == "replay":
            if args.execute:
                parser.error(
                    "live_replay_disabled: M0 only emits an offline plan; review semantic targets, safety gates, and verifier eval first"
                )
            recording = load_recording(args.session, require_complete=True, verify_images=True)
            _print_json(build_replay_plan(recording).model_dump(mode="json"))
            return 0
    except (OSError, RuntimeError, ValueError) as exc:
        _print_json({"status": "failed", "error": str(exc)})
        return 2
    return 2


def _record(args: argparse.Namespace) -> int:
    _validate_record_args(args)
    helper = Path(__file__).resolve().parents[1] / "adapters" / "win_record_replay.py"
    if not helper.is_file():
        raise RuntimeError("Windows recorder helper is missing")
    local_app_data = _windows_local_app_data()
    session_id = str(uuid4())
    session_windows = PureWindowsPath(local_app_data) / "SanmouRecordReplay" / "sessions" / session_id
    session_wsl = _windows_to_wsl(session_windows)
    command = [
        "python.exe",
        _to_windows_unc(helper),
        "--session-id",
        session_id,
        "--workflow-name",
        args.workflow_name,
        "--duration-seconds",
        str(args.duration_seconds),
        "--backend",
        args.backend,
        "--settle-ms",
        str(args.settle_ms),
        "--long-edge",
        str(args.long_edge),
        "--image-format",
        args.image_format,
        "--webp-quality",
        str(args.webp_quality),
        "--max-events",
        str(args.max_events),
        "--max-bytes",
        str(args.max_bytes),
    ]
    process = subprocess.Popen(
        command,
        cwd="/mnt/c",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        stdout, stderr = process.communicate()
    except KeyboardInterrupt:
        if session_wsl.is_dir():
            (session_wsl / "STOP").write_text(
                "stop requested by WSL operator\n", encoding="utf-8"
            )
        else:
            process.terminate()
        try:
            stdout, stderr = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            process.terminate()
            stdout, stderr = process.communicate(timeout=5)
    if process.returncode != 0:
        error = _last_nonempty_line(stderr) or _last_nonempty_line(stdout) or "Windows recorder failed"
        raise RuntimeError(error)
    if not session_wsl.is_dir():
        raise RuntimeError("Windows recorder completed without a session directory")
    recording = load_recording(
        session_wsl,
        require_complete=True,
        verify_images=True,
    )
    if recording.manifest.session_id != session_id:
        raise RuntimeError("Windows recorder returned a foreign session id")
    payload: dict[str, object] = {
        "status": "completed",
        "session_id": session_id,
        "session_dir": str(session_wsl),
        "windows_session_dir": str(session_windows),
        "integrity": "valid",
        "events_sha256": recording.manifest.events_sha256,
        "record_count": recording.manifest.record_count,
        "frame_count": recording.manifest.frame_count,
        "input_event_count": recording.manifest.input_event_count,
        "ignored_event_count": recording.manifest.ignored_event_count,
    }
    _print_json(payload)
    return 0


def _inspect(session: Path) -> int:
    recording = load_recording(session, require_complete=False, verify_images=True)
    integrity = "pending" if recording.manifest.status.value == "recording" else "valid"
    _print_json(_summary(recording, integrity=integrity))
    return 0


def _summary(recording: object, *, integrity: str) -> dict[str, object]:
    manifest = recording.manifest
    return {
        "status": manifest.status.value,
        "integrity": integrity,
        "session_id": manifest.session_id,
        "workflow_name": manifest.workflow_name,
        "started_at": manifest.started_at.isoformat(),
        "ended_at": manifest.ended_at.isoformat() if manifest.ended_at else None,
        "record_count": manifest.record_count,
        "events_sha256": manifest.events_sha256,
        "frame_count": manifest.frame_count,
        "input_event_count": manifest.input_event_count,
        "ignored_event_count": manifest.ignored_event_count,
        "capture_error_count": manifest.capture_error_count,
        "total_frame_bytes": manifest.total_frame_bytes,
        "image_format": manifest.capture.image_format.value,
        "long_edge": manifest.capture.long_edge,
        "webp_quality": manifest.capture.webp_quality,
        "stop_reason": manifest.stop_reason,
        "privacy_reviewed": manifest.safety.privacy_reviewed,
        "execution_authority": manifest.safety.execution_authority,
        "safe_for_live_replay": manifest.safety.safe_for_live_replay,
        "closure_eligible": manifest.closure_eligible,
        "replayable": manifest.status.value == "completed",
    }


def _validate_record_args(args: argparse.Namespace) -> None:
    validate_workflow_name(args.workflow_name)
    if args.duration_seconds < 0 or args.duration_seconds > 3_600:
        raise ValueError("duration must be between 0 and 3600 seconds")
    if not 100 <= args.settle_ms <= 2_000:
        raise ValueError("settle-ms must be between 100 and 2000")
    if not 320 <= args.long_edge <= 2_560:
        raise ValueError("long-edge must be between 320 and 2560")
    if not 20 <= args.webp_quality <= 90:
        raise ValueError("webp-quality must be between 20 and 90")
    if not 1 <= args.max_events <= 10_000:
        raise ValueError("max-events must be between 1 and 10000")
    if args.max_bytes < 1_048_576:
        raise ValueError("max-bytes must be at least 1 MiB")


def _windows_local_app_data() -> str:
    result = subprocess.run(
        ["cmd.exe", "/d", "/c", "echo", "%LOCALAPPDATA%"],
        check=True,
        capture_output=True,
        text=True,
        cwd="/mnt/c",
    )
    value = result.stdout.strip()
    if not re.match(r"^[A-Za-z]:\\", value):
        raise RuntimeError("could not resolve Windows LOCALAPPDATA")
    return value


def _windows_to_wsl(path: PureWindowsPath) -> Path:
    drive = path.drive.rstrip(":").lower()
    if len(drive) != 1 or not drive.isalpha():
        raise ValueError("only local Windows drive paths can be mapped into WSL")
    parts = path.parts[1:]
    return Path("/mnt") / drive / Path(*parts)


def _to_windows_unc(path: Path) -> str:
    resolved = path.resolve()
    raw = str(resolved)
    if raw.startswith("/mnt/") and len(raw) > 6:
        drive = raw[5]
        tail = raw[7:].replace("/", "\\")
        return f"{drive.upper()}:\\{tail}"
    if not raw.startswith("/"):
        raise ValueError("helper path must be absolute")
    distro = os.environ.get("WSL_DISTRO_NAME", "Ubuntu")
    if not re.fullmatch(r"[A-Za-z0-9._-]+", distro):
        raise ValueError("WSL distro name contains unsupported characters")
    return f"\\\\wsl$\\{distro}" + raw.replace("/", "\\")


def _last_nonempty_line(value: str) -> str | None:
    return next((line.strip() for line in reversed(value.splitlines()) if line.strip()), None)


def _print_json(value: object) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    raise SystemExit(main())
