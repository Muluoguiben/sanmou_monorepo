from __future__ import annotations

import contextlib
import io
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from qa_agent.app import stage_advisor_terminal_source as staging
from qa_agent.app.stage_advisor_terminal_source import (
    PendingReviewStageError,
    main,
    stage_raw_terminal_source,
)
from qa_agent.mcp_server.advisor_tools import (
    REVIEWED_LIVE_EVIDENCE_ROOT,
    AdvisorReplayTools,
    RawTerminalSourceCandidate,
    RawTerminalSourceTraceError,
)
from tests.test_advisor_terminal_source_preflight_cli import _ready_live_evidence
from tests.test_mcp_tools import _write_claim_live_evidence


class StageAdvisorTerminalSourceTests(unittest.TestCase):
    def test_accepts_all_three_existing_low_risk_trace_contracts(self) -> None:
        cases = (
            (
                "claim_chapter_reward",
                "chapter",
                "progress.chapter_claim_button",
                "chapter_claim_button",
            ),
            (
                "recruit_soldiers",
                "recruit",
                "teams[*].recruit_button",
                "recruit_button",
            ),
            (
                "upgrade_building",
                "building_upgrade",
                "city.upgrade_dialog.confirm_button",
                "upgrade_confirm_button",
            ),
        )
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            workspace = root / "workspace"
            workspace.mkdir()
            for action_type, page, semantic_target, target_key in cases:
                with self.subTest(action_type=action_type):
                    raw_root = root / action_type
                    raw_root.mkdir()
                    evidence = _ready_live_evidence(
                        raw_root,
                        action_type=action_type,
                        page=page,
                        semantic_target=semantic_target,
                        target_key=target_key,
                    )
                    result = stage_raw_terminal_source(
                        trace_path=Path(evidence["trace"]),
                        action_type=action_type,
                        output_dir=root / "staging",
                        workspace_root=workspace,
                    )
                    manifest = json.loads(
                        Path(result["manifest_path"]).read_text(encoding="utf-8")
                    )
                    skeleton = manifest["terminal_source_evidence_skeleton"]
                    self.assertEqual(skeleton["page"], page)
                    self.assertEqual(skeleton["semantic_target"], semantic_target)
                    self.assertFalse(manifest["accepted_for_closure"])

    def test_stages_exact_bytes_as_pending_only_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, screenshot_path = _write_claim_live_evidence(raw_root)
            workspace = root / "workspace"
            workspace.mkdir()
            output = root / "staging"

            first = stage_raw_terminal_source(
                trace_path=trace_path,
                action_type="claim_chapter_reward",
                output_dir=output,
                workspace_root=workspace,
            )
            second = stage_raw_terminal_source(
                trace_path=trace_path,
                action_type="claim_chapter_reward",
                output_dir=output,
                workspace_root=workspace,
            )

            self.assertTrue(first["ok"])
            self.assertFalse(first["idempotent"])
            self.assertTrue(second["idempotent"])
            bundle = Path(first["bundle_dir"])
            self.assertEqual((bundle / "terminal.png").read_bytes(), screenshot_path.read_bytes())
            self.assertEqual((bundle / "trace.jsonl").read_bytes(), trace_path.read_bytes())
            manifest = json.loads((bundle / "pending_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "pending_review")
            self.assertEqual(manifest["review_status"], "pending_review")
            self.assertEqual(manifest["privacy_review_status"], "pending")
            self.assertFalse(manifest["accepted_for_closure"])
            self.assertEqual(manifest["closure_authority"]["status"], "not_granted")
            skeleton = manifest["terminal_source_evidence_skeleton"]
            self.assertEqual(skeleton["review_status"], "pending_review")
            self.assertIsNone(skeleton["reviewed_by"])
            self.assertIsNone(skeleton["reviewed_at"])
            self.assertEqual(skeleton["privacy_review"]["status"], "pending")
            self.assertFalse(skeleton["privacy_review"]["approved_for_repo_storage"])
            self.assertIsNone(skeleton["git_provenance"]["trust_boundary"])
            self.assertIsNone(skeleton["git_provenance"]["head_commit"])
            self.assertIsNone(skeleton["git_provenance"]["screenshot_blob"])
            self.assertIsNone(skeleton["git_provenance"]["trace_blob"])
            self.assertIn(
                "reject_or_recapture_if_redaction_needed",
                first["next_steps"],
            )

    def test_cli_emits_machine_readable_success_and_rejection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(raw_root)
            output = root / "staging"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--trace",
                        str(trace_path),
                        "--action-type",
                        "claim_chapter_reward",
                        "--output-dir",
                        str(output),
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertTrue(payload["ok"])
            self.assertFalse(payload["accepted_for_closure"])

            record = json.loads(trace_path.read_text(encoding="utf-8"))
            record["verification"]["post_action_verifier"]["status"] = "unverified"
            trace_path.write_text(json.dumps(record), encoding="utf-8")
            rejected_output = root / "rejected"
            stdout = io.StringIO()
            with contextlib.redirect_stdout(stdout):
                exit_code = main(
                    [
                        "--trace",
                        str(trace_path),
                        "--action-type",
                        "claim_chapter_reward",
                        "--output-dir",
                        str(rejected_output),
                    ]
                )
            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 2)
            self.assertFalse(payload["ok"])
            self.assertEqual(payload["error"]["code"], "trace_semantics")
            self.assertFalse(rejected_output.exists())

    def test_rejects_multiple_records_wrong_action_unverified_and_unconfirmed(self) -> None:
        mutators = {
            "multiple_records": lambda record, trace: trace.write_text(
                json.dumps(record) + "\n" + json.dumps(record) + "\n",
                encoding="utf-8",
            ),
            "multiple_terminal_frames": lambda record, trace: _duplicate_terminal_frame(
                trace,
                record,
            ),
            "missing_capture_geometry": lambda record, trace: _remove_capture_geometry(
                trace,
                record,
            ),
            "unverified": lambda record, trace: _rewrite_trace(
                trace,
                record,
                ("verification", "post_action_verifier", "status"),
                "unverified",
            ),
            "unconfirmed": lambda record, trace: _rewrite_trace(
                trace,
                record,
                ("execution", "summary", "operator_confirmation", "confirmed"),
                False,
            ),
        }
        for label, mutate in mutators.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(root)
                record = json.loads(trace_path.read_text(encoding="utf-8"))
                mutate(record, trace_path)
                with self.assertRaises(RawTerminalSourceTraceError):
                    AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                        action_type="claim_chapter_reward",
                        trace_path=trace_path,
                    )

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(root)
            with self.assertRaises(RawTerminalSourceTraceError):
                AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                    action_type="recruit_soldiers",
                    trace_path=trace_path,
                )

    def test_rejects_path_escape_symlink_hardlink_and_nonregular_sources(self) -> None:
        with self.subTest("path_escape"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, screenshot_path = _write_claim_live_evidence(raw_root)
            outside = root / "outside.png"
            outside.write_bytes(screenshot_path.read_bytes())
            _replace_screenshot_path(trace_path, outside)
            with self.assertRaisesRegex(RawTerminalSourceTraceError, "escapes"):
                AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                    action_type="claim_chapter_reward",
                    trace_path=trace_path,
                )

        with self.subTest("symlink"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _evidence, trace_path, screenshot_path = _write_claim_live_evidence(root)
            linked = root / "linked.png"
            linked.symlink_to(screenshot_path.name)
            _replace_screenshot_path(trace_path, linked)
            with self.assertRaises(RawTerminalSourceTraceError) as raised:
                AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                    action_type="claim_chapter_reward",
                    trace_path=trace_path,
                )
            self.assertEqual(raised.exception.code, "source_symlink")

        with self.subTest("trace_symlink"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(root)
            linked_trace = root / "linked.jsonl"
            linked_trace.symlink_to(trace_path.name)
            with self.assertRaises(RawTerminalSourceTraceError) as raised:
                AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                    action_type="claim_chapter_reward",
                    trace_path=linked_trace,
                )
            self.assertEqual(raised.exception.code, "source_symlink")

        with self.subTest("hardlink"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _evidence, trace_path, screenshot_path = _write_claim_live_evidence(root)
            linked = root / "linked.png"
            os.link(screenshot_path, linked)
            _replace_screenshot_path(trace_path, linked)
            with self.assertRaises(RawTerminalSourceTraceError) as raised:
                AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                    action_type="claim_chapter_reward",
                    trace_path=trace_path,
                )
            self.assertEqual(raised.exception.code, "unsafe_source_file")

        with self.subTest("screenshot_sha"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _evidence, trace_path, screenshot_path = _write_claim_live_evidence(root)
            screenshot_path.write_bytes(screenshot_path.read_bytes() + b"tampered")
            with self.assertRaises(RawTerminalSourceTraceError) as raised:
                AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                    action_type="claim_chapter_reward",
                    trace_path=trace_path,
                )
            self.assertEqual(raised.exception.code, "trace_semantics")

        with self.subTest("nonregular"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            trace_dir = root / "trace.jsonl"
            trace_dir.mkdir()
            with self.assertRaises(RawTerminalSourceTraceError) as raised:
                AdvisorReplayTools(workspace_root=root).prepare_raw_terminal_source_candidate(
                    action_type="claim_chapter_reward",
                    trace_path=trace_dir,
                )
            self.assertEqual(raised.exception.code, "unsafe_source_file")

    def test_rejects_source_drift_reviewed_root_and_tampered_collision(self) -> None:
        with self.subTest("source_drift"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _evidence, trace_path, screenshot_path = _write_claim_live_evidence(root)
            tools = AdvisorReplayTools(workspace_root=root)
            original = tools._live_trace_evidence_validation

            def mutate_after_validation(*args, **kwargs):  # noqa: ANN002, ANN003
                result = original(*args, **kwargs)
                screenshot_path.write_bytes(screenshot_path.read_bytes() + b"drift")
                return result

            tools._live_trace_evidence_validation = mutate_after_validation  # type: ignore[method-assign]
            with self.assertRaises(RawTerminalSourceTraceError) as raised:
                tools.prepare_raw_terminal_source_candidate(
                    action_type="claim_chapter_reward",
                    trace_path=trace_path,
                )
            self.assertEqual(raised.exception.code, "source_drift")

        with self.subTest("reviewed_root"), tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            raw_root = workspace / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(raw_root)
            reviewed = workspace / REVIEWED_LIVE_EVIDENCE_ROOT
            with self.assertRaises(PendingReviewStageError) as raised:
                stage_raw_terminal_source(
                    trace_path=trace_path,
                    action_type="claim_chapter_reward",
                    output_dir=reviewed,
                    workspace_root=workspace,
                )
            self.assertEqual(raised.exception.code, "reviewed_root_forbidden")
            self.assertFalse(reviewed.exists())

        with self.subTest("collision"), tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(raw_root)
            workspace = root / "workspace"
            workspace.mkdir()
            result = stage_raw_terminal_source(
                trace_path=trace_path,
                action_type="claim_chapter_reward",
                output_dir=root / "staging",
                workspace_root=workspace,
            )
            (Path(result["bundle_dir"]) / "terminal.png").write_bytes(b"tampered")
            with self.assertRaises(PendingReviewStageError) as raised:
                stage_raw_terminal_source(
                    trace_path=trace_path,
                    action_type="claim_chapter_reward",
                    output_dir=root / "staging",
                    workspace_root=workspace,
                )
            self.assertEqual(raised.exception.code, "existing_bundle_mismatch")

    def test_pending_root_replacement_cannot_redirect_new_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                raw_root
            )
            workspace = root / "workspace"
            workspace.mkdir()
            output = root / "staging"
            outside = root / "outside"
            outside.mkdir()
            original_uuid4 = staging.uuid4

            def replace_pending_root():
                pending = output / "pending_review"
                pending.rename(output / "pending_review_original")
                pending.symlink_to(outside, target_is_directory=True)
                return original_uuid4()

            with patch.object(staging, "uuid4", replace_pending_root):
                with self.assertRaises(PendingReviewStageError) as raised:
                    stage_raw_terminal_source(
                        trace_path=trace_path,
                        action_type="claim_chapter_reward",
                        output_dir=output,
                        workspace_root=workspace,
                    )

            self.assertEqual(raised.exception.code, "unsafe_output_path")
            self.assertEqual(list(outside.iterdir()), [])
            self.assertEqual(list((output / "pending_review_original").iterdir()), [])

    def test_existing_bundle_replacement_cannot_claim_idempotent_success(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                raw_root
            )
            workspace = root / "workspace"
            workspace.mkdir()
            output = root / "staging"
            first = stage_raw_terminal_source(
                trace_path=trace_path,
                action_type="claim_chapter_reward",
                output_dir=output,
                workspace_root=workspace,
            )
            bundle = Path(first["bundle_dir"])
            outside_bundle = root / "outside_bundle"
            shutil.copytree(bundle, outside_bundle)
            original_assert = RawTerminalSourceCandidate.assert_sources_unchanged
            calls = 0

            def replace_existing_bundle(candidate: RawTerminalSourceCandidate) -> None:
                nonlocal calls
                calls += 1
                original_assert(candidate)
                if calls == 2:
                    bundle.rename(bundle.with_name(bundle.name + "-original"))
                    bundle.symlink_to(outside_bundle, target_is_directory=True)

            with patch.object(
                RawTerminalSourceCandidate,
                "assert_sources_unchanged",
                replace_existing_bundle,
            ):
                with self.assertRaises(PendingReviewStageError) as raised:
                    stage_raw_terminal_source(
                        trace_path=trace_path,
                        action_type="claim_chapter_reward",
                        output_dir=output,
                        workspace_root=workspace,
                    )

            self.assertEqual(raised.exception.code, "existing_bundle_mismatch")

    def test_concurrent_empty_destination_is_not_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                raw_root
            )
            workspace = root / "workspace"
            workspace.mkdir()
            output = root / "staging"
            candidate = AdvisorReplayTools(
                workspace_root=workspace
            ).prepare_raw_terminal_source_candidate(
                action_type="claim_chapter_reward",
                trace_path=trace_path,
            )
            trace_sha = candidate.report["artifacts"]["trace"]["sha256"]
            screenshot_sha = candidate.report["artifacts"]["screenshot"]["sha256"]
            bundle_name = (
                f"claim_chapter_reward-{trace_sha[:12]}-{screenshot_sha[:12]}"
            )
            destination = output / "pending_review" / bundle_name
            original_assert = RawTerminalSourceCandidate.assert_sources_unchanged
            calls = 0

            def reserve_empty_destination(
                staged_candidate: RawTerminalSourceCandidate,
            ) -> None:
                nonlocal calls
                calls += 1
                original_assert(staged_candidate)
                if calls == 3:
                    destination.mkdir()

            with patch.object(
                RawTerminalSourceCandidate,
                "assert_sources_unchanged",
                reserve_empty_destination,
            ):
                with self.assertRaises(PendingReviewStageError) as raised:
                    stage_raw_terminal_source(
                        trace_path=trace_path,
                        action_type="claim_chapter_reward",
                        output_dir=output,
                        workspace_root=workspace,
                    )

            self.assertEqual(raised.exception.code, "existing_bundle_mismatch")
            self.assertEqual(list(destination.iterdir()), [])
            self.assertFalse(
                any(".tmp-" in item.name for item in destination.parent.iterdir())
            )

    def test_input_root_replacement_is_detected_before_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                raw_root
            )
            outside = root / "outside"
            outside.mkdir()
            (outside / trace_path.name).write_text("not valid trace jsonl", encoding="utf-8")

            # Swap immediately after the trace path is lexically bound. The pinned
            # root fd must still read the original bytes, and the final identity
            # check must reject the renamed root before any staging output exists.
            from qa_agent.mcp_server import advisor_tools as advisor_module

            original_path_resolve = advisor_module._resolve_raw_source_path
            swapped = False

            def replace_input_root(*args, **kwargs):  # noqa: ANN002, ANN003
                nonlocal swapped
                resolved = original_path_resolve(*args, **kwargs)
                if not swapped and kwargs.get("field") == "trace":
                    swapped = True
                    raw_root.rename(root / "raw_original")
                    raw_root.symlink_to(outside, target_is_directory=True)
                return resolved

            with patch.object(
                advisor_module,
                "_resolve_raw_source_path",
                replace_input_root,
            ):
                with self.assertRaises(RawTerminalSourceTraceError) as raised:
                    AdvisorReplayTools(
                        workspace_root=root
                    ).prepare_raw_terminal_source_candidate(
                        action_type="claim_chapter_reward",
                        trace_path=trace_path,
                    )

            self.assertTrue(swapped)
            self.assertEqual(raised.exception.code, "source_drift")

    def test_missing_secure_dirfd_capability_fails_closed(self) -> None:
        from qa_agent.mcp_server import advisor_tools as advisor_module

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(
                raw_root
            )
            with patch.object(
                advisor_module,
                "_secure_dirfd_capable",
                return_value=False,
            ):
                with self.assertRaises(RawTerminalSourceTraceError) as raised:
                    AdvisorReplayTools(
                        workspace_root=root
                    ).prepare_raw_terminal_source_candidate(
                        action_type="claim_chapter_reward",
                        trace_path=trace_path,
                    )
            self.assertEqual(raised.exception.code, "unsupported_platform")

            workspace = root / "workspace"
            workspace.mkdir()
            output = root / "staging"
            with patch.object(
                staging,
                "_renameat2_function",
                return_value=None,
            ):
                with self.assertRaises(PendingReviewStageError) as raised:
                    stage_raw_terminal_source(
                        trace_path=trace_path,
                        action_type="claim_chapter_reward",
                        output_dir=output,
                        workspace_root=workspace,
                    )
            self.assertEqual(raised.exception.code, "unsupported_platform")
            self.assertFalse(output.exists())

    def test_atomic_write_failure_leaves_no_bundle_or_temporary_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            raw_root = root / "raw"
            raw_root.mkdir()
            _evidence, trace_path, _screenshot_path = _write_claim_live_evidence(raw_root)
            workspace = root / "workspace"
            workspace.mkdir()
            original_write = staging._write_exact_file
            calls = 0

            def fail_second(
                directory_descriptor: int,
                name: str,
                payload: bytes,
            ) -> None:
                nonlocal calls
                calls += 1
                if calls == 2:
                    raise OSError("simulated staging failure")
                original_write(directory_descriptor, name, payload)

            with patch.object(staging, "_write_exact_file", fail_second), self.assertRaises(OSError):
                stage_raw_terminal_source(
                    trace_path=trace_path,
                    action_type="claim_chapter_reward",
                    output_dir=root / "staging",
                    workspace_root=workspace,
                )
            pending = root / "staging" / "pending_review"
            self.assertEqual(list(pending.iterdir()), [])


def _rewrite_trace(
    path: Path,
    record: dict,
    key_path: tuple[str, ...],
    value: object,
) -> None:
    current = record
    for key in key_path[:-1]:
        current = current[key]
    current[key_path[-1]] = value
    path.write_text(json.dumps(record), encoding="utf-8")


def _replace_screenshot_path(trace_path: Path, screenshot_path: Path) -> None:
    record = json.loads(trace_path.read_text(encoding="utf-8"))
    record["screenshot"]["path"] = str(screenshot_path)
    record["frames"][0]["path"] = str(screenshot_path)
    trace_path.write_text(json.dumps(record), encoding="utf-8")


def _duplicate_terminal_frame(trace_path: Path, record: dict) -> None:
    record["frames"].append(json.loads(json.dumps(record["frames"][0])))
    trace_path.write_text(json.dumps(record), encoding="utf-8")


def _remove_capture_geometry(trace_path: Path, record: dict) -> None:
    del record["execution"]["summary"]["operator_confirmation"][
        "semantic_frame_guard"
    ]["capture_geometry"]
    trace_path.write_text(json.dumps(record), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
