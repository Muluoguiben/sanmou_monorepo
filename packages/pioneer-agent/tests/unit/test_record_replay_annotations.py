from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
from datetime import timedelta
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pydantic import ValidationError

from pioneer_agent.app.record_replay import main
from pioneer_agent.record_replay.annotations import (
    COUNTABLE_TRANSITION_OUTCOME_BY_SAMPLE_LABEL,
    MAX_ANNOTATION_BYTES,
    RecordingAnnotationManifest,
    SampleLabel,
    TransitionOutcome,
    annotation_summary,
    build_annotation_template,
    expected_transition_outcome,
    load_recording_annotation,
)
from pioneer_agent.record_replay import validation as record_replay_validation
from pioneer_agent.record_replay.session_store import LoadedRecording, load_recording
from tests.unit.record_replay_fixtures import NOW, create_completed_session


class RecordReplayAnnotationTests(unittest.TestCase):
    def test_sample_label_to_transition_outcome_contract_is_authoritative(self) -> None:
        expected = {
            SampleLabel.POSITIVE: TransitionOutcome.APPLIED,
            SampleLabel.NO_CHANGE: TransitionOutcome.NO_CHANGE,
            SampleLabel.TIMEOUT: TransitionOutcome.NO_CHANGE,
            SampleLabel.MISSING_TARGET: TransitionOutcome.AMBIGUOUS,
            SampleLabel.AMBIGUOUS_TARGET: TransitionOutcome.AMBIGUOUS,
            SampleLabel.POPUP_INTERRUPTION: TransitionOutcome.INTERRUPTED,
            SampleLabel.OPERATOR_CANCELLED: TransitionOutcome.INTERRUPTED,
        }
        self.assertEqual(dict(COUNTABLE_TRANSITION_OUTCOME_BY_SAMPLE_LABEL), expected)
        for label, outcome in expected.items():
            with self.subTest(label=label.value):
                self.assertEqual(expected_transition_outcome(label), outcome)
        self.assertIsNone(
            expected_transition_outcome(SampleLabel.OBSERVATION_ONLY)
        )
        with self.assertRaises(TypeError):
            COUNTABLE_TRANSITION_OUTCOME_BY_SAMPLE_LABEL[
                SampleLabel.NO_CHANGE
            ] = TransitionOutcome.INTERRUPTED

    def test_draft_template_binds_exact_raw_hashes_and_has_no_authority(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)

            template = build_annotation_template(
                recording,
                workflow_id="map-filter-apply",
                annotated_by="reviewer@example.test",
                now=recording.manifest.ended_at + timedelta(seconds=1),
            )

            self.assertEqual(
                template.source_manifest_sha256,
                sha256((root / "manifest.json").read_bytes()).hexdigest(),
            )
            self.assertEqual(
                template.source_events_sha256,
                sha256((root / "events.jsonl").read_bytes()).hexdigest(),
            )
            self.assertEqual(template.source_events_sha256, recording.manifest.events_sha256)
            self.assertEqual(template.review_status.value, "draft")
            self.assertEqual(template.execution_authority, "none")
            self.assertFalse(template.live_dispatch_allowed)
            self.assertFalse(template.safe_for_live_replay)
            self.assertFalse(template.terminal_source_eligible)
            self.assertFalse(template.closure_eligible)
            self.assertFalse(template.knowledge_publication_allowed)
            self.assertIsNone(template.segments[0].observation_schema_id)
            self.assertIsNone(template.segments[0].before_observation_sha256)
            self.assertIsNone(template.segments[0].after_observation_sha256)
            self.assertEqual(
                template.segments[0].source_event_ids,
                [recording.input_events[0].event_id],
            )
            self.assertFalse(recording.manifest.safety.privacy_reviewed)
            self.assertEqual(recording.manifest.safety.execution_authority, "none")

            base = template.model_dump(mode="json")
            forbidden_values = {
                "execution_authority": "live",
                "live_dispatch_allowed": True,
                "safe_for_live_replay": True,
                "terminal_source_eligible": True,
                "closure_eligible": True,
                "knowledge_publication_allowed": True,
            }
            for field, value in forbidden_values.items():
                with self.subTest(field=field):
                    tampered = deepcopy(base)
                    tampered[field] = value
                    with self.assertRaises(ValidationError):
                        RecordingAnnotationManifest.model_validate(tampered)

    def test_approved_annotation_validates_and_summary_remains_no_authority(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            annotation_path = base / "approved.json"
            self._write_json(annotation_path, self._approved_payload(recording))

            loaded = load_recording_annotation(
                recording, annotation_path, require_approved=True
            )
            summary = annotation_summary(recording, loaded)

            self.assertEqual(summary["status"], "valid")
            self.assertEqual(summary["review_status"], "approved")
            self.assertEqual(summary["privacy_status"], "approved")
            self.assertEqual(
                summary["privacy_scope"], "full_raw_session_and_annotation"
            )
            self.assertTrue(summary["approved_for_local_derivation"])
            self.assertTrue(summary["approved_for_eval_candidate"])
            self.assertEqual(summary["execution_authority"], "none")
            self.assertFalse(summary["live_dispatch_allowed"])
            self.assertFalse(summary["safe_for_live_replay"])
            self.assertFalse(summary["terminal_source_eligible"])
            self.assertFalse(summary["closure_eligible"])
            self.assertFalse(summary["knowledge_publication_allowed"])
            self.assertFalse(summary["raw_approved_for_repo_storage"])
            self.assertEqual(loaded.sha256, sha256(annotation_path.read_bytes()).hexdigest())
            self.assertEqual(
                loaded.annotation.segments[0].observation_schema_id,
                "map-land-filter-v1",
            )
            self.assertEqual(
                loaded.annotation.segments[0].before_observation_sha256,
                sha256(b"reviewed-before-observation").hexdigest(),
            )
            self.assertEqual(
                loaded.annotation.segments[0].after_observation_sha256,
                sha256(b"reviewed-after-observation").hexdigest(),
            )

    def test_approved_annotation_revalidates_old_loaded_recording_from_disk(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            annotation_path = base / "approved.json"
            self._write_json(annotation_path, self._approved_payload(recording))

            manifest_path = root / "manifest.json"
            inode = manifest_path.stat().st_ino
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["target"]["title"] = "changed after reviewer loaded evidence"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False),
                encoding="utf-8",
            )
            self.assertEqual(manifest_path.stat().st_ino, inode)

            with self.assertRaisesRegex(ValueError, "changed after it was loaded"):
                load_recording_annotation(
                    recording,
                    annotation_path,
                    require_approved=True,
                )

    def test_review_and_session_labels_fail_closed_when_their_evidence_conflicts(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)

            cases: list[tuple[str, dict[str, object], str]] = []

            eval_without_local = self._approved_payload(recording)
            eval_without_local["privacy_review"][
                "approved_for_local_derivation"
            ] = False
            cases.append(
                (
                    "eval-without-local",
                    eval_without_local,
                    "eval candidate approval requires local derivation approval",
                )
            )

            annotation_text_not_reviewed = self._approved_payload(recording)
            annotation_text_not_reviewed["privacy_review"][
                "scope"
            ] = "full_raw_session"
            cases.append(
                (
                    "annotation-text-not-reviewed",
                    annotation_text_not_reviewed,
                    "full raw session and annotation text",
                )
            )

            raw_events_not_reviewed = self._approved_payload(recording)
            raw_events_not_reviewed["privacy_review"]["events_reviewed"] = False
            cases.append(
                (
                    "raw-events-not-reviewed",
                    raw_events_not_reviewed,
                    "explicit manifest, events, and frame review",
                )
            )

            derivation_on_draft = self._approved_payload(recording)
            derivation_on_draft["review_status"] = "draft"
            cases.append(
                (
                    "derivation-on-draft",
                    derivation_on_draft,
                    "requires an approved annotation",
                )
            )

            unassessed_sensitive_field = self._approved_payload(recording)
            unassessed_sensitive_field["privacy_review"]["chat_visible"] = None
            cases.append(
                (
                    "unassessed-sensitive-field",
                    unassessed_sensitive_field,
                    "must explicitly assess every sensitive field",
                )
            )

            mismatched_sample = self._approved_payload(recording)
            mismatched_sample["sample_label"] = "no_change"
            cases.append(
                (
                    "mismatched-sample",
                    mismatched_sample,
                    "negative sample requires matching negative-only segment evidence",
                )
            )

            understated_risk = self._approved_payload(recording)
            understated_risk["segments"][0]["risk_class"] = "low_risk_mutation"
            cases.append(
                (
                    "understated-risk",
                    understated_risk,
                    "every segment risk class must match the session risk class",
                )
            )

            deny_without_top_level_rejection = self._approved_payload(recording)
            deny_without_top_level_rejection["review_status"] = "draft"
            deny_without_top_level_rejection["semantic_review"]["status"] = "rejected"
            cases.append(
                (
                    "deny-without-top-level-rejection",
                    deny_without_top_level_rejection,
                    "rejecting review must reject the whole annotation",
                )
            )

            review_before_annotation = self._approved_payload(recording)
            review_before_annotation["semantic_review"]["reviewed_at"] = (
                recording.manifest.ended_at
            ).isoformat()
            cases.append(
                (
                    "review-before-annotation",
                    review_before_annotation,
                    "semantic reviewed_at cannot predate annotation creation",
                )
            )

            for name, payload, message in cases:
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValidationError, message):
                        RecordingAnnotationManifest.model_validate(payload)

    def test_countable_segments_require_normalized_action_and_reviewed_pages(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)

            cases: list[tuple[str, dict[str, object], str]] = []

            missing_action = self._approved_payload(recording)
            missing_action["segments"][0]["proposed_action_name"] = None
            cases.append(
                (
                    "missing-action",
                    missing_action,
                    "normalized proposed action name",
                )
            )

            unnormalized_action = self._approved_payload(recording)
            unnormalized_action["segments"][0][
                "proposed_action_name"
            ] = "Apply Map Filter"
            cases.append(
                (
                    "unnormalized-action",
                    unnormalized_action,
                    "lowercase ASCII identifier",
                )
            )

            placeholder_before = self._approved_payload(recording)
            placeholder_before["segments"][0]["page_before"] = "unknown"
            cases.append(
                (
                    "placeholder-before",
                    placeholder_before,
                    "non-placeholder before and after pages",
                )
            )

            placeholder_after = self._approved_payload(recording)
            placeholder_after["segments"][0]["page_after"] = "unreviewed"
            cases.append(
                (
                    "placeholder-after",
                    placeholder_after,
                    "non-placeholder before and after pages",
                )
            )

            for name, payload, message in cases:
                with self.subTest(name=name):
                    with self.assertRaisesRegex(ValidationError, message):
                        RecordingAnnotationManifest.model_validate(payload)

    def test_every_countable_negative_segment_must_match_top_level_label(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            payload = self._approved_payload(recording)
            payload["sample_label"] = "no_change"
            first = payload["segments"][0]
            first.update(
                {
                    "sample_label": "no_change",
                    "outcome": "no_change",
                    "evidence_use": "negative",
                    "observed_delta": ["fresh observation showed no change"],
                }
            )
            mismatched = deepcopy(first)
            mismatched["segment_id"] = "segment-mismatched"
            mismatched["sample_label"] = "timeout"
            payload["segments"].append(mismatched)

            with self.assertRaisesRegex(
                ValidationError,
                "negative sample requires matching negative-only segment evidence",
            ):
                RecordingAnnotationManifest.model_validate(payload)

    def test_countable_observation_binding_is_complete_strict_and_versioned(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)

            missing = self._approved_payload(recording)
            missing["segments"][0].update(
                {
                    "observation_schema_id": None,
                    "before_observation_sha256": None,
                    "after_observation_sha256": None,
                }
            )
            with self.assertRaisesRegex(
                ValidationError,
                "content-addressed before and after observations",
            ):
                RecordingAnnotationManifest.model_validate(missing)

            partial = self._approved_payload(recording)
            partial["segments"][0]["after_observation_sha256"] = None
            with self.assertRaisesRegex(
                ValidationError,
                "observation binding requires schema and both before/after digests",
            ):
                RecordingAnnotationManifest.model_validate(partial)

            placeholder_schema = self._approved_payload(recording)
            placeholder_schema["segments"][0]["observation_schema_id"] = "unknown"
            with self.assertRaisesRegex(
                ValidationError,
                "content-addressed before and after observations",
            ):
                RecordingAnnotationManifest.model_validate(placeholder_schema)

            invalid_values = ("A" * 64, "0" * 63, 0, True)
            for field in (
                "before_observation_sha256",
                "after_observation_sha256",
            ):
                for value in invalid_values:
                    with self.subTest(field=field, value=value):
                        invalid = self._approved_payload(recording)
                        invalid["segments"][0][field] = value
                        with self.assertRaises(ValidationError):
                            RecordingAnnotationManifest.model_validate(invalid)

            partial_trace = self._draft_payload(recording)
            partial_trace["segments"][0][
                "observation_schema_id"
            ] = "map-land-filter-v1"
            with self.assertRaisesRegex(
                ValidationError,
                "observation binding requires schema and both before/after digests",
            ):
                RecordingAnnotationManifest.model_validate(partial_trace)

    def test_schema_version_and_fixed_false_fields_reject_coercion(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            base = self._draft_payload(recording)

            for value in (True, "1", 1.0):
                with self.subTest(field="annotation_schema_version", value=value):
                    payload = deepcopy(base)
                    payload["annotation_schema_version"] = value
                    with self.assertRaises(ValidationError):
                        RecordingAnnotationManifest.model_validate(payload)

            fixed_false_paths = (
                ("live_dispatch_allowed",),
                ("safe_for_live_replay",),
                ("terminal_source_eligible",),
                ("closure_eligible",),
                ("knowledge_publication_allowed",),
                ("privacy_review", "raw_approved_for_repo_storage"),
                ("segments", 0, "causal_verified"),
            )
            for path in fixed_false_paths:
                for value in (True, 0, "false"):
                    with self.subTest(path=path, value=value):
                        payload = deepcopy(base)
                        target = payload
                        for key in path[:-1]:
                            target = target[key]
                        target[path[-1]] = value
                        with self.assertRaises(ValidationError):
                            RecordingAnnotationManifest.model_validate(payload)

    def test_annotation_cannot_supersede_itself(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp) / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            payload = self._draft_payload(recording)
            payload["supersedes_annotation_id"] = payload["annotation_id"]

            with self.assertRaisesRegex(ValidationError, "cannot supersede itself"):
                RecordingAnnotationManifest.model_validate(payload)

    def test_rejects_wrong_manifest_and_events_digests(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)

            cases = (
                ("source_manifest_sha256", "manifest SHA256"),
                ("source_events_sha256", "events SHA256"),
            )
            for field, message in cases:
                with self.subTest(field=field):
                    payload = self._approved_payload(recording)
                    payload[field] = "0" * 64
                    path = base / f"wrong-{field}.json"
                    self._write_json(path, payload)
                    with self.assertRaisesRegex(ValueError, message):
                        load_recording_annotation(recording, path)

    def test_rejects_unknown_missing_duplicate_events_and_wrong_boundaries(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)

            unknown = self._draft_payload(recording)
            unknown["segments"][0]["source_event_ids"] = ["event-unknown"]
            self._assert_payload_rejected(
                recording,
                base / "unknown.json",
                unknown,
                "unknown input event",
            )

            missing = self._draft_payload(recording)
            missing["segments"] = []
            self._assert_payload_rejected(
                recording,
                base / "missing.json",
                missing,
                "cover every recorded input event exactly once",
            )

            duplicate = self._draft_payload(recording)
            duplicate["excluded_events"] = [
                {
                    "source_event_id": recording.input_events[0].event_id,
                    "reason": "duplicated reviewer reference",
                }
            ]
            self._assert_payload_rejected(
                recording,
                base / "duplicate.json",
                duplicate,
                "coverage contains duplicates",
            )

            wrong_boundary = self._draft_payload(recording)
            wrong_boundary["segments"][0]["before_frame_id"] = "frame-end"
            self._assert_payload_rejected(
                recording,
                base / "wrong-boundary.json",
                wrong_boundary,
                "before frame does not match",
            )

    def test_ambiguous_burst_is_grouped_and_cannot_be_positive_or_split(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            self._make_ambiguous_burst(root)
            recording = load_recording(root)

            template = build_annotation_template(
                recording,
                workflow_id="map-filter-apply",
                now=recording.manifest.ended_at + timedelta(seconds=1),
            )
            self.assertEqual(len(template.segments), 1)
            self.assertEqual(
                template.segments[0].source_event_ids,
                ["event-click", "event-click-2"],
            )
            self.assertEqual(template.segments[0].sample_label.value, "ambiguous_target")
            self.assertEqual(template.segments[0].outcome.value, "ambiguous")
            self.assertEqual(template.segments[0].evidence_use.value, "trace_only")

            positive = self._approved_payload(recording)
            self._assert_payload_rejected(
                recording,
                base / "ambiguous-positive.json",
                positive,
                "ambiguous input burst cannot be positive evidence",
            )

            split = template.model_dump(mode="json")
            first = deepcopy(split["segments"][0])
            second = deepcopy(split["segments"][0])
            first["segment_id"] = "segment-0000-a"
            second["segment_id"] = "segment-0000-b"
            first["source_event_ids"] = ["event-click"]
            second["source_event_ids"] = ["event-click-2"]
            split["segments"] = [first, second]
            self._assert_payload_rejected(
                recording,
                base / "ambiguous-split.json",
                split,
                "shared-frame or ambiguous input burst must stay in one annotation segment",
            )

            excluded = template.model_dump(mode="json")
            excluded["segments"] = []
            excluded["excluded_events"] = [
                {
                    "source_event_id": event_id,
                    "reason": "reviewer attempted a per-event exclusion",
                }
                for event_id in ("event-click", "event-click-2")
            ]
            self._assert_payload_rejected(
                recording,
                base / "ambiguous-excluded-per-event.json",
                excluded,
                "cannot be split into per-event exclusions",
            )

    def test_geometry_change_and_capture_error_cannot_be_positive_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)

            geometry_root = base / "geometry-session"
            create_completed_session(geometry_root, workflow_name="apply map filter")
            self._make_geometry_change(geometry_root)
            geometry_recording = load_recording(geometry_root)
            self._assert_payload_rejected(
                geometry_recording,
                base / "geometry-positive.json",
                self._approved_payload(geometry_recording),
                "geometry-changing input cannot be positive evidence",
            )

            error_root = base / "capture-error-session"
            create_completed_session(error_root, workflow_name="apply map filter")
            self._add_capture_error(error_root)
            error_recording = load_recording(error_root)
            self._assert_payload_rejected(
                error_recording,
                base / "capture-error-positive.json",
                self._approved_payload(error_recording),
                "positive sample cannot contain capture or input ambiguity",
            )

    def test_privacy_and_reviewer_gates_fail_closed(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)

            invalid_model_cases: list[tuple[str, dict[str, object]]] = []

            missing_privacy_reviewer = self._approved_payload(recording)
            missing_privacy_reviewer["privacy_review"]["reviewed_by"] = None
            invalid_model_cases.append(
                ("missing-privacy-reviewer", missing_privacy_reviewer)
            )

            missing_semantic_reviewer = self._approved_payload(recording)
            missing_semantic_reviewer["semantic_review"]["reviewed_by"] = None
            invalid_model_cases.append(
                ("missing-semantic-reviewer", missing_semantic_reviewer)
            )

            sensitive_eval = self._approved_payload(recording)
            sensitive_eval["privacy_review"]["chat_visible"] = True
            invalid_model_cases.append(("sensitive-eval", sensitive_eval))

            invalid_annotator = self._approved_payload(recording)
            invalid_annotator["annotated_by"] = "reviewer with spaces"
            invalid_model_cases.append(("invalid-annotator", invalid_annotator))

            for name, payload in invalid_model_cases:
                with self.subTest(name=name):
                    path = base / f"{name}.json"
                    self._write_json(path, payload)
                    with self.assertRaisesRegex(
                        ValueError, "recording annotation is invalid"
                    ):
                        load_recording_annotation(recording, path)

            missing_frame = self._approved_payload(recording)
            missing_frame["privacy_review"]["reviewed_frame_ids"] = [
                recording.frames[0].frame_id
            ]
            self._assert_payload_rejected(
                recording,
                base / "missing-frame-review.json",
                missing_frame,
                "privacy review must cover every recorded frame",
            )

            stale_review = self._approved_payload(recording)
            stale_review["annotated_at"] = (
                recording.manifest.started_at - timedelta(seconds=1)
            ).isoformat()
            self._assert_payload_rejected(
                recording,
                base / "stale-review.json",
                stale_review,
                "annotated_at cannot predate recording completion",
            )

            draft_path = base / "draft.json"
            self._write_json(draft_path, self._draft_payload(recording))
            with self.assertRaisesRegex(ValueError, "annotation is not approved"):
                load_recording_annotation(
                    recording, draft_path, require_approved=True
                )

    def test_rejects_duplicate_json_keys(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            payload = self._approved_payload(recording)
            raw = json.dumps(payload, ensure_ascii=False, indent=2)
            needle = f'"session_id": "{recording.manifest.session_id}",'
            duplicated = raw.replace(needle, f"{needle}\n  {needle}", 1)
            self.assertNotEqual(raw, duplicated)
            path = base / "duplicate-key.json"
            path.write_text(duplicated, encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "recording annotation is invalid"):
                load_recording_annotation(recording, path)

    @unittest.skipIf(os.name == "nt", "symlink creation is not reliable on Windows CI")
    def test_rejects_symlinked_annotation(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            target = base / "approved.json"
            self._write_json(target, self._approved_payload(recording))
            link = base / "annotation-link.json"
            link.symlink_to(target)

            with self.assertRaisesRegex(ValueError, "links|symlink"):
                load_recording_annotation(recording, link)

    def test_rejects_hardlinked_annotation(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            target = base / "approved.json"
            self._write_json(target, self._approved_payload(recording))
            link = base / "annotation-hardlink.json"
            try:
                os.link(target, link)
            except (NotImplementedError, OSError) as exc:
                self.skipTest(f"hardlinks unavailable: {exc}")

            with self.assertRaisesRegex(ValueError, "must not be hard-linked"):
                load_recording_annotation(recording, link)

    def test_rejects_same_inode_annotation_rewrite_during_read(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            path = base / "approved.json"
            self._write_json(path, self._approved_payload(recording))
            original_payload = path.read_bytes()
            original_stat = path.stat()
            original_read = record_replay_validation.os.read
            mutated = False

            def mutate_after_first_read(descriptor: int, size: int) -> bytes:
                nonlocal mutated
                chunk = original_read(descriptor, size)
                if not mutated:
                    mutated = True
                    replacement = original_payload[:-1] + (
                        b" " if original_payload[-1:] != b" " else b"\n"
                    )
                    path.write_bytes(replacement)
                    os.utime(
                        path,
                        ns=(
                            original_stat.st_atime_ns,
                            original_stat.st_mtime_ns + 1_000_000_000,
                        ),
                    )
                return chunk

            with patch.object(
                record_replay_validation.os,
                "read",
                side_effect=mutate_after_first_read,
            ):
                with self.assertRaisesRegex(ValueError, "changed while it was read"):
                    load_recording_annotation(
                        recording,
                        path,
                        require_approved=True,
                    )

    def test_rejects_oversized_annotation_before_parsing(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            recording = load_recording(root)
            path = base / "oversized.json"
            path.touch()
            with path.open("r+b") as handle:
                handle.truncate(MAX_ANNOTATION_BYTES + 1)

            with self.assertRaisesRegex(ValueError, "fixed size limit"):
                load_recording_annotation(recording, path)

    def test_cli_template_and_validate_do_not_mutate_raw_evidence(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root, workflow_name="apply map filter")
            before = self._raw_hashes(root)

            stdout = StringIO()
            with redirect_stdout(stdout):
                result = main(
                    [
                        "annotation-template",
                        str(root),
                        "--workflow-id",
                        "map-filter-apply",
                        "--annotated-by",
                        "reviewer@example.test",
                    ]
                )
            self.assertEqual(result, 0)
            template = json.loads(stdout.getvalue())
            self.assertEqual(template["execution_authority"], "none")
            self.assertFalse(template["live_dispatch_allowed"])
            self.assertEqual(
                template["source_manifest_sha256"], before["manifest.json"]
            )
            self.assertEqual(template["source_events_sha256"], before["events.jsonl"])

            recording = load_recording(root)
            annotation_path = base / "approved.json"
            self._write_json(annotation_path, self._approved_payload(recording))
            stdout = StringIO()
            with redirect_stdout(stdout):
                result = main(
                    [
                        "annotation-validate",
                        str(root),
                        str(annotation_path),
                        "--require-approved",
                    ]
                )
            self.assertEqual(result, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["status"], "valid")
            self.assertEqual(summary["review_status"], "approved")
            self.assertEqual(summary["execution_authority"], "none")
            self.assertFalse(summary["live_dispatch_allowed"])
            self.assertFalse(summary["closure_eligible"])
            self.assertEqual(before, self._raw_hashes(root))

    @staticmethod
    def _draft_payload(recording: LoadedRecording) -> dict[str, object]:
        return build_annotation_template(
            recording,
            workflow_id="map-filter-apply",
            annotated_by="annotator",
            now=recording.manifest.ended_at + timedelta(seconds=1),
        ).model_dump(mode="json")

    @classmethod
    def _approved_payload(cls, recording: LoadedRecording) -> dict[str, object]:
        payload = cls._draft_payload(recording)
        reviewed_at = (recording.manifest.ended_at + timedelta(seconds=1)).isoformat()
        payload.update(
            {
                "annotated_at": reviewed_at,
                "review_status": "approved",
                "sample_label": "positive",
                "risk_class": "read_only",
                "start_page": "main-map",
                "end_page": "main-map",
                "start_state_id": "filter-closed",
            }
        )
        payload["semantic_review"] = {
            "status": "approved",
            "reviewed_by": "semantic-reviewer",
            "reviewed_at": reviewed_at,
            "notes": ["semantic label reviewed against selected frames"],
        }
        payload["privacy_review"] = {
            "status": "approved",
            "reviewed_by": "privacy-reviewer",
            "reviewed_at": reviewed_at,
            "scope": "full_raw_session_and_annotation",
            "manifest_reviewed": True,
            "events_reviewed": True,
            "reviewed_frame_ids": [frame.frame_id for frame in recording.frames],
            "account_identifiers_visible": False,
            "chat_visible": False,
            "player_or_alliance_names_visible": False,
            "payment_or_secret_visible": False,
            "precise_coordinates_visible": False,
            "unrelated_window_visible": False,
            "approved_for_local_derivation": True,
            "approved_for_eval_candidate": True,
            "raw_approved_for_repo_storage": False,
        }
        segment = payload["segments"][0]
        segment.update(
            {
                "sample_label": "positive",
                "risk_class": "read_only",
                "page_before": "main-map",
                "page_after": "main-map-filtered",
                "proposed_action_name": "apply-map-filter",
                "observation_schema_id": "map-land-filter-v1",
                "before_observation_sha256": sha256(
                    b"reviewed-before-observation"
                ).hexdigest(),
                "after_observation_sha256": sha256(
                    b"reviewed-after-observation"
                ).hexdigest(),
                "semantic_target": {
                    "page": "main-map",
                    "target_kind": "button",
                    "target_key": "map-filter-apply",
                    "visible_label": "筛选",
                    "disambiguators": ["right-side filter affordance"],
                    "unique_in_frame": True,
                },
                "observed_preconditions": ["map filter panel is open"],
                "expected_delta_claim": ["selected filters become active"],
                "observed_delta": ["reviewed result marker becomes visible"],
                "outcome": "applied",
                "evidence_use": "positive",
                "unresolved_assumptions": [],
            }
        )
        return payload

    @staticmethod
    def _write_json(path: Path, payload: object) -> None:
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    @classmethod
    def _assert_payload_rejected(
        cls,
        recording: LoadedRecording,
        path: Path,
        payload: object,
        message: str,
    ) -> None:
        cls._write_json(path, payload)
        with unittest.TestCase().assertRaisesRegex(ValueError, message):
            load_recording_annotation(recording, path)

    @staticmethod
    def _raw_hashes(root: Path) -> dict[str, str]:
        paths = [root / "manifest.json", root / "events.jsonl"]
        paths.extend(sorted((root / "frames").iterdir()))
        return {
            path.relative_to(root).as_posix(): sha256(path.read_bytes()).hexdigest()
            for path in paths
        }

    @classmethod
    def _make_ambiguous_burst(cls, root: Path) -> None:
        records = cls._read_records(root)
        first_event = deepcopy(records[1])
        first_event["ambiguous_burst"] = True
        second_event = deepcopy(first_event)
        second_event.update(
            {
                "event_id": "event-click-2",
                "occurred_at": (NOW + timedelta(milliseconds=200)).isoformat(),
                "ended_at": (NOW + timedelta(milliseconds=220)).isoformat(),
                "elapsed_ms": 200,
            }
        )
        cls._rewrite_records(
            root,
            [records[0], first_event, second_event, records[2], records[3]],
        )

    @classmethod
    def _make_geometry_change(cls, root: Path) -> None:
        records = cls._read_records(root)
        changed_geometry = deepcopy(records[2]["capture_geometry"])
        changed_geometry["outer_window"]["right"] = 210
        changed_geometry["outer_window"]["width"] = 110
        changed_geometry["capture_rect"]["right"] = 190
        changed_geometry["capture_rect"]["width"] = 90
        changed_geometry["frame_size"] = [90, 100]
        records[1]["geometry_changed"] = True
        records[2]["capture_geometry"] = changed_geometry
        cls._rewrite_records(root, records)

    @classmethod
    def _add_capture_error(cls, root: Path) -> None:
        records = cls._read_records(root)
        capture_error = {
            "schema_version": 1,
            "record_type": "capture_error",
            "session_id": records[0]["session_id"],
            "sequence": 0,
            "occurred_at": (NOW + timedelta(milliseconds=700)).isoformat(),
            "elapsed_ms": 700,
            "code": "synthetic_capture_error",
            "message": "synthetic capture failure for fail-closed annotation test",
        }
        cls._rewrite_records(
            root,
            [records[0], records[1], records[2], capture_error, records[3]],
        )

    @staticmethod
    def _read_records(root: Path) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in (root / "events.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]

    @classmethod
    def _rewrite_records(cls, root: Path, records: list[dict[str, object]]) -> None:
        for sequence, record in enumerate(records):
            record["sequence"] = sequence
        events_payload = b"".join(
            (json.dumps(record, ensure_ascii=False, separators=(",", ":")) + "\n").encode(
                "utf-8"
            )
            for record in records
        )
        (root / "events.jsonl").write_bytes(events_payload)
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        manifest.update(
            {
                "events_sha256": sha256(events_payload).hexdigest(),
                "record_count": len(records),
                "frame_count": sum(
                    record["record_type"] == "frame" for record in records
                ),
                "input_event_count": sum(
                    record["record_type"] == "input" for record in records
                ),
                "capture_error_count": sum(
                    record["record_type"] == "capture_error" for record in records
                ),
                "total_frame_bytes": sum(
                    int(record["byte_size"])
                    for record in records
                    if record["record_type"] == "frame"
                ),
            }
        )
        cls._write_json(root / "manifest.json", manifest)


if __name__ == "__main__":
    unittest.main()
