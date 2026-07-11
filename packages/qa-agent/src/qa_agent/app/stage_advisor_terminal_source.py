"""Stage one validated raw live trace for explicit human privacy review."""

from __future__ import annotations

import argparse
import ctypes
import errno
import json
import os
from pathlib import Path
import stat
from typing import Any
from uuid import uuid4

from qa_agent.mcp_server.advisor_tools import (
    REVIEWED_LIVE_EVIDENCE_ROOT,
    AdvisorReplayTools,
    RawTerminalSourceCandidate,
    RawTerminalSourceTraceError,
    _directory_identity,
    _normalized_absolute_path,
    _open_directory_no_symlinks,
    _read_regular_file_snapshot_at,
    _secure_dirfd_capable,
)


class PendingReviewStageError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate one raw terminal trace and copy its exact bytes into a "
            "pending_review bundle. This never grants privacy approval or closure."
        )
    )
    parser.add_argument("--trace", required=True, help="Raw live trace JSONL path.")
    parser.add_argument(
        "--action-type",
        required=True,
    )
    parser.add_argument(
        "--output-dir",
        required=True,
        help="Staging root; bundles are written below its pending_review directory.",
    )
    parser.add_argument(
        "--input-root",
        help="Optional allowed source root. Defaults to the trace parent directory.",
    )
    return parser


def stage_raw_terminal_source(
    *,
    trace_path: Path,
    action_type: str,
    output_dir: Path,
    input_root: Path | None = None,
    workspace_root: Path | None = None,
    tools: AdvisorReplayTools | None = None,
) -> dict[str, Any]:
    workspace = (
        Path(workspace_root).resolve()
        if workspace_root is not None
        else Path(__file__).resolve().parents[5]
    )
    replay_tools = tools or AdvisorReplayTools(workspace_root=workspace)
    candidate = replay_tools.prepare_raw_terminal_source_candidate(
        action_type=action_type,
        trace_path=Path(trace_path),
        input_root=Path(input_root) if input_root is not None else None,
    )
    output_root, output_descriptor, output_identity = _prepare_output_root(
        Path(output_dir),
        workspace_root=workspace,
    )
    pending_root = output_root / "pending_review"
    pending_descriptor: int | None = None
    try:
        pending_descriptor, pending_identity = _open_or_create_child_directory(
            output_descriptor,
            "pending_review",
        )
        _assert_output_binding(
            output_root,
            output_identity=output_identity,
            pending_identity=pending_identity,
        )

        report = candidate.report
        trace_sha = report["artifacts"]["trace"]["sha256"]
        screenshot_sha = report["artifacts"]["screenshot"]["sha256"]
        bundle_id = f"{action_type}-{trace_sha[:12]}-{screenshot_sha[:12]}"
        destination = pending_root / bundle_id
        manifest = _pending_manifest(candidate, bundle_id=bundle_id)
        if _entry_exists(pending_descriptor, bundle_id):
            result = _existing_bundle_result(
                destination,
                pending_descriptor=pending_descriptor,
                bundle_name=bundle_id,
                expected_manifest=manifest,
                candidate=candidate,
            )
            _assert_output_binding(
                output_root,
                output_identity=output_identity,
                pending_identity=pending_identity,
            )
            return result

        candidate.assert_sources_unchanged()
        temporary_name = f".{bundle_id}.tmp-{uuid4().hex}"
        temporary_descriptor, temporary_identity = _create_owned_temporary(
            pending_descriptor,
            temporary_name,
        )
        published = False
        try:
            _write_exact_file(
                temporary_descriptor,
                "terminal.png",
                candidate.screenshot_bytes,
            )
            _write_exact_file(
                temporary_descriptor,
                "trace.jsonl",
                candidate.trace_bytes,
            )
            manifest_bytes = (
                json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            _write_exact_file(
                temporary_descriptor,
                "pending_manifest.json",
                manifest_bytes,
            )
            _fsync_directory(temporary_descriptor)
            candidate.assert_sources_unchanged()
            _assert_output_binding(
                output_root,
                output_identity=output_identity,
                pending_identity=pending_identity,
            )
            try:
                _rename_directory_noreplace(
                    temporary_name,
                    bundle_id,
                    directory_descriptor=pending_descriptor,
                )
            except OSError:
                if _entry_exists(pending_descriptor, bundle_id):
                    _remove_owned_temporary(
                        temporary_name,
                        temporary_descriptor=temporary_descriptor,
                        temporary_identity=temporary_identity,
                        pending_descriptor=pending_descriptor,
                    )
                    result = _existing_bundle_result(
                        destination,
                        pending_descriptor=pending_descriptor,
                        bundle_name=bundle_id,
                        expected_manifest=manifest,
                        candidate=candidate,
                    )
                    _assert_output_binding(
                        output_root,
                        output_identity=output_identity,
                        pending_identity=pending_identity,
                    )
                    return result
                raise
            published = True
            _fsync_directory(pending_descriptor)
            _existing_bundle_result(
                destination,
                pending_descriptor=pending_descriptor,
                bundle_name=bundle_id,
                expected_manifest=manifest,
                candidate=candidate,
            )
            _assert_output_binding(
                output_root,
                output_identity=output_identity,
                pending_identity=pending_identity,
            )
        except Exception:
            if not published:
                _remove_owned_temporary(
                    temporary_name,
                    temporary_descriptor=temporary_descriptor,
                    temporary_identity=temporary_identity,
                    pending_descriptor=pending_descriptor,
                )
            raise
        finally:
            os.close(temporary_descriptor)

        return _stage_result(destination, manifest=manifest, idempotent=False)
    finally:
        if pending_descriptor is not None:
            os.close(pending_descriptor)
        os.close(output_descriptor)


def _pending_manifest(
    candidate: RawTerminalSourceCandidate,
    *,
    bundle_id: str,
) -> dict[str, Any]:
    report = candidate.report
    fields = report["evidence_fields"]
    trace_artifact = report["artifacts"]["trace"]
    screenshot_artifact = report["artifacts"]["screenshot"]
    return {
        "schema_version": 1,
        "bundle_id": bundle_id,
        "status": "pending_review",
        "action_type": report["action_type"],
        "raw_binding_valid": True,
        "review_status": "pending_review",
        "privacy_review_status": "pending",
        "accepted_for_closure": False,
        "closure_authority": {
            "status": "not_granted",
            "reasons": [
                "human_privacy_review_required",
                "reviewed_repository_paths_not_assigned",
                "git_head_blob_authority_not_checked",
            ],
        },
        "source_paths": report["source_paths"],
        "staged_artifacts": {
            "screenshot": {
                **screenshot_artifact,
                "path": "terminal.png",
                "copied_as_original_bytes": True,
            },
            "trace": {
                **trace_artifact,
                "path": "trace.jsonl",
                "copied_as_original_bytes": True,
            },
        },
        "terminal_source_evidence_skeleton": {
            "source_kind": "live_trace_fixture",
            "review_status": "pending_review",
            "reviewed_by": None,
            "reviewed_at": None,
            "screenshot": None,
            "screenshot_sha256": screenshot_artifact["sha256"],
            "trace": None,
            "trace_sha256": trace_artifact["sha256"],
            "privacy_review": {
                "status": "pending",
                "reviewed_by": None,
                "reviewed_at": None,
                "redaction_applied": None,
                "account_identifiers_visible": None,
                "chat_visible": None,
                "player_or_alliance_names_visible": None,
                "payment_data_visible": None,
                "precise_coordinates_visible": None,
                "approved_for_repo_storage": False,
            },
            "page": fields["page"],
            "semantic_target": fields["semantic_target"],
            "runtime_dispatch": fields["runtime_dispatch"],
            "target_identity": fields["target_identity"],
            "post_action_delta": fields["post_action_delta"],
            "post_action_delta_evidence": {
                "source": "verification_record",
                "post_action_delta": fields["post_action_delta"],
                "supporting_refs": [
                    "terminal_source_evidence.trace",
                    "terminal_source_evidence.verification_record",
                    "operator_confirmation.trace_id",
                ],
            },
            "verification_record": fields["verification_record"],
            "operator_confirmation": fields["operator_confirmation"],
            "git_provenance": {
                "trust_boundary": None,
                "reviewed_root": None,
                "head_commit": None,
                "screenshot_blob": None,
                "trace_blob": None,
            },
        },
        "human_review_checklist": [
            {
                "code": "inspect_full_frame_privacy",
                "required": True,
                "instruction": (
                    "Inspect the entire terminal PNG for account identifiers, chat or "
                    "social text, player/alliance names, payment/secrets, and precise coordinates."
                ),
            },
            {
                "code": "reject_or_recapture_if_redaction_needed",
                "required": True,
                "instruction": (
                    "Do not redact this PNG in place: any pixel change invalidates the "
                    "trace frame SHA and semantic ROI guard. Reject it or recapture a "
                    "privacy-safe terminal frame."
                ),
            },
            {
                "code": "review_trace_paths_and_semantics",
                "required": True,
                "instruction": (
                    "Review absolute/local paths and all action, confirmation, and verifier "
                    "fields before preparing any reviewed trace derivative."
                ),
            },
            {
                "code": "assign_reviewed_repo_paths",
                "required": True,
                "instruction": (
                    "Only after approval, assign repo-relative screenshot/trace paths under "
                    "the reviewed root and record reviewer identity and aware timestamp."
                ),
            },
            {
                "code": "commit_then_run_closure_preflight",
                "required": True,
                "instruction": (
                    "Commit exact reviewed bytes, populate Git blob provenance, then run the "
                    "existing advisor terminal-source preflight."
                ),
            },
        ],
    }


_STAGED_ARTIFACT_NAMES = {
    "pending_manifest.json",
    "terminal.png",
    "trace.jsonl",
}
_RENAME_NOREPLACE = 1


def _renameat2_function():
    if os.name != "posix":
        return None
    try:
        function = getattr(ctypes.CDLL(None, use_errno=True), "renameat2")
    except (AttributeError, OSError):
        return None
    function.argtypes = (
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    )
    function.restype = ctypes.c_int
    return function


def _secure_staging_capable() -> bool:
    return bool(
        _secure_dirfd_capable()
        and os.mkdir in os.supports_dir_fd
        and os.unlink in os.supports_dir_fd
        and os.rmdir in os.supports_dir_fd
        and os.listdir in os.supports_fd
        and _renameat2_function() is not None
    )


def _require_secure_staging_capability() -> None:
    if not _secure_staging_capable():
        raise PendingReviewStageError(
            "unsupported_platform",
            "pending staging requires secure POSIX dir_fd support",
        )


def _prepare_output_root(
    path: Path,
    *,
    workspace_root: Path,
) -> tuple[Path, int, tuple[int, int, int]]:
    _require_secure_staging_capability()
    lexical = _normalized_absolute_path(path)
    reviewed_root = _normalized_absolute_path(
        workspace_root / REVIEWED_LIVE_EVIDENCE_ROOT
    )
    if lexical == reviewed_root or lexical.is_relative_to(reviewed_root):
        raise PendingReviewStageError(
            "reviewed_root_forbidden",
            "pending staging must not write inside the reviewed evidence root",
        )

    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(lexical.anchor, flags)
    try:
        for part in lexical.parts[1:]:
            if part in {"", "."}:
                continue
            if part == "..":
                raise PendingReviewStageError(
                    "unsafe_output_path",
                    "output path must not contain parent traversal",
                )
            try:
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
            except FileNotFoundError:
                try:
                    os.mkdir(part, mode=0o700, dir_fd=descriptor)
                except FileExistsError:
                    pass
                next_descriptor = os.open(part, flags, dir_fd=descriptor)
            except OSError as exc:
                raise PendingReviewStageError(
                    "unsafe_output_path",
                    "output path contains a symlink or non-directory component",
                ) from exc
            os.close(descriptor)
            descriptor = next_descriptor
        opened = os.fstat(descriptor)
        if not stat.S_ISDIR(opened.st_mode):
            raise PendingReviewStageError(
                "unsafe_output_path",
                "output-dir must be a real directory",
            )
        return lexical, descriptor, _directory_identity(opened)
    except Exception:
        os.close(descriptor)
        raise


def _open_or_create_child_directory(
    parent_descriptor: int,
    name: str,
) -> tuple[int, tuple[int, int, int]]:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        os.mkdir(name, mode=0o700, dir_fd=parent_descriptor)
    except FileExistsError:
        pass
    try:
        descriptor = os.open(name, flags, dir_fd=parent_descriptor)
    except OSError as exc:
        raise PendingReviewStageError(
            "unsafe_output_path",
            f"{name} must be a real directory",
        ) from exc
    opened = os.fstat(descriptor)
    if not stat.S_ISDIR(opened.st_mode):
        os.close(descriptor)
        raise PendingReviewStageError(
            "unsafe_output_path",
            f"{name} must be a real directory",
        )
    return descriptor, _directory_identity(opened)


def _assert_output_binding(
    output_root: Path,
    *,
    output_identity: tuple[int, int, int],
    pending_identity: tuple[int, int, int],
) -> None:
    try:
        _path, descriptor, reopened_identity = _open_directory_no_symlinks(
            output_root
        )
    except OSError as exc:
        raise PendingReviewStageError(
            "unsafe_output_path",
            "output-dir changed or became unsafe during staging",
        ) from exc
    try:
        if reopened_identity != output_identity:
            raise PendingReviewStageError(
                "unsafe_output_path",
                "output-dir identity changed during staging",
            )
        try:
            pending_stat = os.stat(
                "pending_review",
                dir_fd=descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise PendingReviewStageError(
                "unsafe_output_path",
                "pending_review changed or became unsafe during staging",
            ) from exc
        if (
            not stat.S_ISDIR(pending_stat.st_mode)
            or _directory_identity(pending_stat) != pending_identity
        ):
            raise PendingReviewStageError(
                "unsafe_output_path",
                "pending_review identity changed during staging",
            )
    finally:
        os.close(descriptor)


def _entry_exists(parent_descriptor: int, name: str) -> bool:
    try:
        os.stat(name, dir_fd=parent_descriptor, follow_symlinks=False)
    except FileNotFoundError:
        return False
    return True


def _create_owned_temporary(
    pending_descriptor: int,
    name: str,
) -> tuple[int, tuple[int, int, int]]:
    try:
        os.mkdir(name, mode=0o700, dir_fd=pending_descriptor)
    except OSError as exc:
        raise PendingReviewStageError(
            "temporary_bundle_collision",
            "could not create a unique pending temporary directory",
        ) from exc
    try:
        return _open_or_create_child_directory(pending_descriptor, name)
    except Exception:
        try:
            os.rmdir(name, dir_fd=pending_descriptor)
        except OSError:
            pass
        raise


def _rename_directory_noreplace(
    source: str,
    destination: str,
    *,
    directory_descriptor: int,
) -> None:
    function = _renameat2_function()
    if function is None:
        raise PendingReviewStageError(
            "unsupported_platform",
            "pending staging requires renameat2(RENAME_NOREPLACE)",
        )
    ctypes.set_errno(0)
    result = function(
        directory_descriptor,
        os.fsencode(source),
        directory_descriptor,
        os.fsencode(destination),
        _RENAME_NOREPLACE,
    )
    if result != 0:
        error_number = ctypes.get_errno() or errno.EIO
        if error_number in {
            errno.ENOSYS,
            errno.EINVAL,
            errno.ENOTSUP,
            errno.EOPNOTSUPP,
        }:
            raise PendingReviewStageError(
                "unsupported_platform",
                "renameat2(RENAME_NOREPLACE) is unavailable on this filesystem",
            )
        raise OSError(error_number, os.strerror(error_number))


def _write_exact_file(
    directory_descriptor: int,
    name: str,
    payload: bytes,
) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    flags |= getattr(os, "O_BINARY", 0)
    descriptor = os.open(name, flags, 0o600, dir_fd=directory_descriptor)
    with os.fdopen(descriptor, "wb", closefd=True) as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())


def _read_unique_regular_file(
    directory_descriptor: int,
    name: str,
) -> bytes:
    snapshot, issues = _read_regular_file_snapshot_at(
        directory_descriptor,
        Path(name),
    )
    if snapshot is None or issues:
        raise PendingReviewStageError(
            "existing_bundle_mismatch",
            f"missing or unsafe staged artifact: {name}",
        )
    return snapshot["bytes"]


def _existing_bundle_result(
    destination: Path,
    *,
    pending_descriptor: int,
    bundle_name: str,
    expected_manifest: dict[str, Any],
    candidate: RawTerminalSourceCandidate,
) -> dict[str, Any]:
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        bundle_descriptor = os.open(
            bundle_name,
            flags,
            dir_fd=pending_descriptor,
        )
    except OSError as exc:
        raise PendingReviewStageError(
            "bundle_collision",
            "deterministic bundle path exists but is not a real directory",
        ) from exc
    bundle_identity = _directory_identity(os.fstat(bundle_descriptor))
    try:
        if set(os.listdir(bundle_descriptor)) != _STAGED_ARTIFACT_NAMES:
            raise PendingReviewStageError(
                "existing_bundle_mismatch",
                "existing bundle contains missing or unexpected entries",
            )
        candidate.assert_sources_unchanged()
        try:
            actual_manifest = json.loads(
                _read_unique_regular_file(
                    bundle_descriptor,
                    "pending_manifest.json",
                ).decode("utf-8", errors="strict")
            )
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise PendingReviewStageError(
                "existing_bundle_mismatch",
                "existing pending manifest is invalid",
            ) from exc
        if actual_manifest != expected_manifest:
            raise PendingReviewStageError(
                "existing_bundle_mismatch",
                "existing pending manifest does not match this source snapshot",
            )
        if (
            _read_unique_regular_file(bundle_descriptor, "trace.jsonl")
            != candidate.trace_bytes
        ):
            raise PendingReviewStageError(
                "existing_bundle_mismatch",
                "existing staged trace bytes differ",
            )
        if (
            _read_unique_regular_file(bundle_descriptor, "terminal.png")
            != candidate.screenshot_bytes
        ):
            raise PendingReviewStageError(
                "existing_bundle_mismatch",
                "existing staged screenshot bytes differ",
            )
        try:
            final_entry = os.stat(
                bundle_name,
                dir_fd=pending_descriptor,
                follow_symlinks=False,
            )
        except OSError as exc:
            raise PendingReviewStageError(
                "existing_bundle_mismatch",
                "existing bundle identity changed during validation",
            ) from exc
        if (
            not stat.S_ISDIR(final_entry.st_mode)
            or _directory_identity(final_entry) != bundle_identity
        ):
            raise PendingReviewStageError(
                "existing_bundle_mismatch",
                "existing bundle identity changed during validation",
            )
        return _stage_result(destination, manifest=expected_manifest, idempotent=True)
    finally:
        os.close(bundle_descriptor)


def _stage_result(
    destination: Path,
    *,
    manifest: dict[str, Any],
    idempotent: bool,
) -> dict[str, Any]:
    return {
        "ok": True,
        "status": "pending_review",
        "idempotent": idempotent,
        "bundle_id": manifest["bundle_id"],
        "bundle_dir": str(destination),
        "manifest_path": str(destination / "pending_manifest.json"),
        "accepted_for_closure": False,
        "privacy_review_status": "pending",
        "next_steps": [item["code"] for item in manifest["human_review_checklist"]],
    }


def _remove_owned_temporary(
    name: str,
    *,
    temporary_descriptor: int,
    temporary_identity: tuple[int, int, int],
    pending_descriptor: int,
) -> None:
    if not name.startswith(".") or ".tmp-" not in name:
        return
    for artifact_name in _STAGED_ARTIFACT_NAMES:
        try:
            os.unlink(artifact_name, dir_fd=temporary_descriptor)
        except FileNotFoundError:
            pass
    if os.listdir(temporary_descriptor):
        return
    try:
        current = os.stat(
            name,
            dir_fd=pending_descriptor,
            follow_symlinks=False,
        )
    except FileNotFoundError:
        return
    if (
        stat.S_ISDIR(current.st_mode)
        and _directory_identity(current) == temporary_identity
    ):
        os.rmdir(name, dir_fd=pending_descriptor)


def _fsync_directory(descriptor: int) -> None:
    os.fsync(descriptor)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    try:
        payload = stage_raw_terminal_source(
            trace_path=Path(args.trace),
            action_type=args.action_type,
            output_dir=Path(args.output_dir),
            input_root=Path(args.input_root) if args.input_root else None,
        )
    except (RawTerminalSourceTraceError, PendingReviewStageError, OSError) as exc:
        error_code = getattr(exc, "code", "io_error")
        payload = {
            "ok": False,
            "status": "rejected",
            "error": {
                "code": error_code,
                "message": str(exc),
                "details": getattr(exc, "details", {}),
            },
            "accepted_for_closure": False,
            "privacy_review_status": "not_reviewed",
        }
        print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
        return 2
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
