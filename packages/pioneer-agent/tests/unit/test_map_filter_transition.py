from __future__ import annotations

from copy import deepcopy
from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pydantic import ValidationError

from pioneer_agent.perception.map_filter_transition import (
    MapFilterSelection,
    MapFilterTransitionOutcome,
    MapFilterTransitionResult,
    ReviewerBoundaryEvidence,
    classify_map_filter_transition,
    map_filter_perception_sha256,
)
from pioneer_agent.perception.vision.prompts import MapLandDetection
from pioneer_agent.record_replay.annotations import (
    build_annotation_template,
    load_recording_annotation,
)
from pioneer_agent.record_replay.session_store import load_recording
from tests.unit.record_replay_fixtures import NOW, create_completed_session


T0 = NOW


class MapFilterTransitionTests(unittest.TestCase):
    def setUp(self) -> None:
        self._temporary = TemporaryDirectory()
        base = Path(self._temporary.name)
        self._base = base
        self._annotation_counter = 0
        root = base / "session"
        create_completed_session(root, workflow_name="apply map filter")
        self.recording = load_recording(root)
        annotation_path = base / "approved.json"
        annotation_path.write_text(
            json.dumps(
                _approved_annotation_payload(
                    self.recording,
                    before=_observation(panel=True),
                    after=_observation(
                        panel=False, resources=("stone",), levels=(5,)
                    ),
                ),
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        self.annotation = load_recording_annotation(
            self.recording, annotation_path, require_approved=True
        )

    def tearDown(self) -> None:
        self._temporary.cleanup()

    def test_panel_opened_is_observation_only(self) -> None:
        result = self._classify(
            _observation(panel=False),
            _observation(panel=True),
            _evidence(),
            contract="panel_opened",
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.PANEL_OPENED)
        self._assert_no_authority(result)

    def test_selection_changed_requires_both_panel_observations(self) -> None:
        result = self._classify(
            _observation(panel=True),
            _observation(panel=True, resources=("stone",), levels=(5,)),
            _evidence(),
            contract="selection_changed",
        )

        self.assertEqual(
            result.outcome, MapFilterTransitionOutcome.SELECTION_CHANGED
        )
        self.assertEqual(
            result.observed_after_filter,
            MapFilterSelection(
                resource_filter_enabled=True,
                resource_types=("stone",),
                levels=(5,),
            ),
        )
        self._assert_no_authority(result)

    def test_reviewed_apply_plus_matching_after_state_is_applied(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=True),
            _observation(panel=False, resources=("stone",), levels=(5,)),
            _evidence(apply="reviewed", requested=requested),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.APPLIED)
        self.assertIn("after_filter_matches_request", result.reasons)
        self._assert_no_authority(result)

    def test_filter_selection_matching_is_order_independent(self) -> None:
        requested = MapFilterSelection(
            resource_filter_enabled=True,
            resource_types=("wood", "stone"),
            levels=(6, 5),
        )
        result = self._classify(
            _observation(panel=True),
            _observation(
                panel=False,
                resources=("stone", "wood"),
                levels=(5, 6),
            ),
            _evidence(apply="reviewed", requested=requested),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.APPLIED)
        self._assert_no_authority(result)

    def test_reviewed_matching_result_marker_can_corroborate_apply_transition(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=True),
            _observation(panel=False, resources=("stone",), levels=(5,)),
            _evidence(
                apply="reviewed",
                requested=requested,
                marker="reviewed",
                marker_filter=requested,
            ),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.APPLIED)
        self.assertIn("reviewed_result_marker_matches_request", result.reasons)
        self._assert_no_authority(result)

    def test_matching_marker_cannot_override_conflicting_after_filter(self) -> None:
        requested = _selection()
        for label, after in (
            ("explicit-empty", _observation(panel=False)),
            (
                "different-selection",
                _observation(panel=False, resources=("wood",), levels=(6,)),
            ),
        ):
            with self.subTest(label=label):
                result = self._classify(
                    _observation(panel=True),
                    after,
                    _evidence(
                        apply="reviewed",
                        requested=requested,
                        marker="reviewed",
                        marker_filter=requested,
                    ),
                )

                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn(
                    "result_marker_conflicts_with_after_filter", result.reasons
                )
                self._assert_no_authority(result)

    def test_fresh_marker_does_not_promote_repeated_apply(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=True, resources=("stone",), levels=(5,)),
            _observation(panel=False, resources=("stone",), levels=(5,)),
            _evidence(
                apply="reviewed",
                requested=requested,
                marker="reviewed",
                marker_filter=requested,
            ),
            contract="no_change",
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.NO_CHANGE)
        self.assertIn(
            "requested_filter_already_observed_before_apply", result.reasons
        )
        self._assert_no_authority(result)

    def test_repeated_apply_with_conflicting_after_filter_is_ambiguous(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=True, resources=("stone",), levels=(5,)),
            _observation(panel=False, resources=("wood",), levels=(6,)),
            _evidence(apply="reviewed", requested=requested),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn(
            "repeated_apply_conflicts_with_after_filter", result.reasons
        )
        self._assert_no_authority(result)

    def test_transition_requires_loaded_recording_and_annotation(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        evidence = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=requested),
        )

        for label, recording, annotation in (
            ("missing-both", None, None),
            ("missing-recording", None, self.annotation),
            ("missing-annotation", self.recording, None),
        ):
            with self.subTest(label=label):
                result = classify_map_filter_transition(
                    before,
                    after,
                    evidence,
                    recording=recording,
                    annotation=annotation,
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn(
                    "missing_validated_source_evidence", result.reasons
                )
                self._assert_no_authority(result)

    def test_transition_requires_complete_content_addressed_binding(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        base = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=requested),
        )
        missing = deepcopy(base)
        missing.pop("source_binding")
        incomplete = deepcopy(base)
        incomplete["source_binding"]["annotation_sha256"] = None

        for label, evidence, reason in (
            ("missing", missing, "missing_source_binding"),
            ("incomplete", incomplete, "incomplete_source_binding"),
        ):
            with self.subTest(label=label):
                result = classify_map_filter_transition(
                    before,
                    after,
                    evidence,
                    recording=self.recording,
                    annotation=self.annotation,
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn(reason, result.reasons)
                self._assert_no_authority(result)

    def test_recording_changed_after_load_cannot_supply_transition_evidence(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        evidence = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=requested),
        )
        frame_path = self.recording.root / self.recording.frames[0].path
        frame_path.write_bytes(b"changed-after-load")

        result = classify_map_filter_transition(
            before,
            after,
            evidence,
            recording=self.recording,
            annotation=self.annotation,
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("stale_or_invalid_loaded_recording", result.reasons)
        self._assert_no_authority(result)

    def test_annotation_changed_after_load_cannot_supply_transition_evidence(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        evidence = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=requested),
        )
        self.annotation.path.write_text(
            '{"tampered":true}\n', encoding="utf-8"
        )

        result = classify_map_filter_transition(
            before,
            after,
            evidence,
            recording=self.recording,
            annotation=self.annotation,
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("stale_or_invalid_loaded_annotation", result.reasons)
        self._assert_no_authority(result)

    def test_missing_annotation_after_load_fails_closed(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        evidence = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=requested),
        )
        self.annotation.path.unlink()

        result = classify_map_filter_transition(
            before,
            after,
            evidence,
            recording=self.recording,
            annotation=self.annotation,
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("stale_or_invalid_loaded_annotation", result.reasons)
        self._assert_no_authority(result)

    def test_link_replacement_of_annotation_after_load_fails_closed(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        evidence = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=requested),
        )
        replacement = self.annotation.path.with_name("replacement.json")
        replacement.write_bytes(self.annotation.path.read_bytes())
        self.annotation.path.unlink()
        self.annotation.path.symlink_to(replacement)

        result = classify_map_filter_transition(
            before,
            after,
            evidence,
            recording=self.recording,
            annotation=self.annotation,
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("stale_or_invalid_loaded_annotation", result.reasons)
        self._assert_no_authority(result)

    def test_source_binding_mismatches_fail_closed(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        base = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=requested),
        )
        cases = {
            "session": (
                {"source_binding": {"session_id": "foreign-session"}},
                "source_session_mismatch",
            ),
            "manifest": (
                {"source_binding": {"source_manifest_sha256": "0" * 64}},
                "source_manifest_digest_mismatch",
            ),
            "events": (
                {"source_binding": {"source_events_sha256": "0" * 64}},
                "source_events_digest_mismatch",
            ),
            "annotation-id": (
                {"source_binding": {"annotation_id": "foreign-annotation"}},
                "annotation_id_mismatch",
            ),
            "annotation-hash": (
                {"source_binding": {"annotation_sha256": "0" * 64}},
                "annotation_digest_mismatch",
            ),
            "annotation-segment": (
                {
                    "source_binding": {
                        "annotation_segment_id": "foreign-segment"
                    }
                },
                "annotation_segment_missing",
            ),
            "input-event": (
                {"source_binding": {"source_event_id": "foreign-event"}},
                "source_input_event_missing",
            ),
            "apply-event": (
                {"apply_event": {"event_id": "foreign-event"}},
                "reviewed_apply_event_source_mismatch",
            ),
            "before-frame-hash": (
                {"before_frame": {"frame_sha256": "0" * 64}},
                "before_frame_digest_mismatch",
            ),
            "after-source-png": (
                {"after_frame": {"source_png_sha256": "0" * 64}},
                "after_source_png_digest_mismatch",
            ),
            "before-perception": (
                {"before_frame": {"perception_sha256": "0" * 64}},
                "before_perception_digest_mismatch",
            ),
            "after-frame-id": (
                {"after_frame": {"frame_id": "frame-end"}},
                "source_input_event_boundary_mismatch",
            ),
        }
        for label, (override, expected_reason) in cases.items():
            with self.subTest(label=label):
                evidence = deepcopy(base)
                _merge(evidence, override)
                result = classify_map_filter_transition(
                    before,
                    after,
                    evidence,
                    recording=self.recording,
                    annotation=self.annotation,
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn(expected_reason, result.reasons)
                self._assert_no_authority(result)

    def test_annotation_semantics_must_describe_map_filter_apply(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        cases = {
            "workflow": (
                {"workflow_id": "attack-land"},
                "annotation_workflow_not_map_filter_apply",
            ),
            "action": (
                {"segments": [{"proposed_action_name": "attack-land"}]},
                "annotation_action_not_map_filter_apply",
            ),
            "target": (
                {
                    "segments": [
                        {"semantic_target": {"target_key": "attack-land"}}
                    ]
                },
                "annotation_target_not_map_filter_apply",
            ),
            "page": (
                {"segments": [{"page_before": "battle-page"}]},
                "annotation_pages_not_map_filter_transition",
            ),
            "risk": (
                {
                    "risk_class": "low_risk_mutation",
                    "segments": [{"risk_class": "low_risk_mutation"}],
                },
                "annotation_risk_not_read_only",
            ),
        }
        for label, (override, expected_reason) in cases.items():
            with self.subTest(label=label):
                annotation = self._load_annotation(
                    before,
                    after,
                    payload_override=override,
                )
                evidence = self._bound_evidence(
                    before,
                    after,
                    _evidence(apply="reviewed", requested=requested),
                    annotation=annotation,
                )
                result = classify_map_filter_transition(
                    before,
                    after,
                    evidence,
                    recording=self.recording,
                    annotation=annotation,
                )

                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn(expected_reason, result.reasons)
                self._assert_no_authority(result)

    def test_annotation_must_bind_exact_canonical_perceptions(self) -> None:
        requested = _selection()
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        cases = (
            (
                "schema",
                self._load_annotation(
                    before,
                    after,
                    payload_override={
                        "segments": [
                            {"observation_schema_id": "map-land-filter-v2"}
                        ]
                    },
                ),
                "annotation_observation_schema_mismatch",
            ),
            (
                "before-digest",
                self._load_annotation(_observation(panel=False), after),
                "annotation_before_observation_digest_mismatch",
            ),
            (
                "after-digest",
                self._load_annotation(before, _observation(panel=False)),
                "annotation_after_observation_digest_mismatch",
            ),
        )
        for label, annotation, expected_reason in cases:
            with self.subTest(label=label):
                evidence = self._bound_evidence(
                    before,
                    after,
                    _evidence(apply="reviewed", requested=requested),
                    annotation=annotation,
                )
                result = classify_map_filter_transition(
                    before,
                    after,
                    evidence,
                    recording=self.recording,
                    annotation=annotation,
                )

                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn(expected_reason, result.reasons)
                self._assert_no_authority(result)

    def test_terminal_outcome_must_match_annotation_contract(self) -> None:
        requested = _selection()
        cases = (
            (
                "applied-vs-negative",
                _observation(panel=True),
                _observation(
                    panel=False, resources=("stone",), levels=(5,)
                ),
                _evidence(apply="reviewed", requested=requested),
                "no_change",
                "annotation_contract_conflicts_with_applied",
            ),
            (
                "no-change-vs-positive",
                _observation(
                    panel=True, resources=("stone",), levels=(5,)
                ),
                _observation(
                    panel=False, resources=("stone",), levels=(5,)
                ),
                _evidence(apply="reviewed", requested=requested),
                "positive",
                "annotation_contract_conflicts_with_no_change",
            ),
            (
                "interrupted-vs-positive",
                _observation(panel=True),
                _observation(panel=True),
                _evidence(interrupted=True),
                "positive",
                "annotation_contract_conflicts_with_interrupted",
            ),
            (
                "panel-opened-vs-positive",
                _observation(panel=False),
                _observation(panel=True),
                _evidence(),
                "positive",
                "annotation_contract_conflicts_with_panel_opened",
            ),
            (
                "selection-changed-vs-positive",
                _observation(panel=True),
                _observation(panel=True, resources=("stone",), levels=(5,)),
                _evidence(),
                "positive",
                "annotation_contract_conflicts_with_selection_changed",
            ),
            (
                "operator-cancelled-cannot-be-no-change",
                _observation(panel=True),
                _observation(panel=False),
                _evidence(),
                "operator_cancelled",
                "annotation_contract_conflicts_with_no_change",
            ),
        )
        for label, before, after, boundary, contract, expected_reason in cases:
            with self.subTest(label=label):
                annotation = self._load_annotation(
                    before,
                    after,
                    contract=contract,
                )
                evidence = self._bound_evidence(
                    before,
                    after,
                    boundary,
                    annotation=annotation,
                )
                result = classify_map_filter_transition(
                    before,
                    after,
                    evidence,
                    recording=self.recording,
                    annotation=annotation,
                )

                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn(expected_reason, result.reasons)
                self._assert_no_authority(result)

    def test_panel_close_alone_does_not_prove_applied(self) -> None:
        result = self._classify(
            _observation(panel=True),
            _observation(panel=False),
            _evidence(),
            contract="no_change",
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.NO_CHANGE)
        self.assertIn("panel_closed_without_reviewed_apply", result.reasons)
        self._assert_no_authority(result)

    def test_map_center_and_land_count_changes_alone_are_no_change(self) -> None:
        before = _observation(panel=False, map_center=(100, 200))
        after = _observation(
            panel=False,
            map_center=(900, 800),
            lands=[
                {
                    "land_id": "different-visible-land",
                    "level": 5,
                    "resource_type": "stone",
                    "occupied": False,
                }
            ],
        )

        result = self._classify(
            before,
            after,
            _evidence(),
            contract="no_change",
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.NO_CHANGE)
        self._assert_no_authority(result)

    def test_reviewed_apply_without_result_evidence_is_no_change(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=True),
            _observation(panel=False),
            _evidence(apply="reviewed", requested=requested),
            contract="no_change",
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.NO_CHANGE)
        self.assertIn("reviewed_apply_without_result_evidence", result.reasons)
        self._assert_no_authority(result)

    def test_reapplying_an_already_observed_filter_is_no_change_without_fresh_marker(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=True, resources=("stone",), levels=(5,)),
            _observation(panel=False, resources=("stone",), levels=(5,)),
            _evidence(apply="reviewed", requested=requested),
            contract="no_change",
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.NO_CHANGE)
        self.assertIn(
            "requested_filter_already_observed_before_apply", result.reasons
        )
        self._assert_no_authority(result)

    def test_reviewed_interruption_is_distinct_from_no_change(self) -> None:
        result = self._classify(
            _observation(panel=True),
            _observation(panel=True),
            _evidence(interrupted=True),
            contract="interrupted",
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.INTERRUPTED)
        self._assert_no_authority(result)

    def test_unexpected_filter_state_after_reviewed_apply_is_ambiguous(self) -> None:
        result = self._classify(
            _observation(panel=True),
            _observation(panel=False, resources=("wood",), levels=(6,)),
            _evidence(apply="reviewed", requested=_selection()),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("unexpected_after_filter_state", result.reasons)
        self._assert_no_authority(result)

    def test_hidden_filter_state_change_without_reviewed_apply_is_ambiguous(self) -> None:
        result = self._classify(
            _observation(panel=True),
            _observation(panel=False, resources=("stone",), levels=(5,)),
            _evidence(),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("filter_state_changed_outside_visible_panel", result.reasons)
        self._assert_no_authority(result)

    def test_result_marker_never_substitutes_for_reviewed_apply_event(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=True),
            _observation(panel=False),
            _evidence(
                requested=requested,
                marker="reviewed",
                marker_filter=requested,
            ),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn(
            "result_marker_without_reviewed_apply_event", result.reasons
        )
        self._assert_no_authority(result)

    def test_reviewed_apply_requires_visible_enabled_apply_control(self) -> None:
        requested = _selection()
        result = self._classify(
            _observation(panel=False),
            _observation(panel=False, resources=("stone",), levels=(5,)),
            _evidence(apply="reviewed", requested=requested),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn(
            "reviewed_apply_without_visible_filter_panel", result.reasons
        )
        self.assertIn(
            "reviewed_apply_without_visible_apply_control", result.reasons
        )
        self._assert_no_authority(result)

    def test_reviewed_apply_requires_coordinate_free_requested_filter(self) -> None:
        result = self._classify(
            _observation(panel=True),
            _observation(panel=True),
            _evidence(apply="reviewed", interrupted=True),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn(
            "reviewed_apply_missing_requested_filter", result.reasons
        )
        self._assert_no_authority(result)

    def test_capture_window_geometry_timing_and_review_fail_closed(self) -> None:
        cases = {
            "capture_error": {"after_frame": {"capture_error": True}},
            "capture_incomplete": {
                "after_frame": {"capture_complete": False}
            },
            "missing_geometry": {"after_frame": {"geometry_id": None}},
            "incomplete_geometry": {
                "after_frame": {"geometry_complete": False}
            },
            "geometry_mismatch": {
                "after_frame": {"geometry_id": "geometry-other"}
            },
            "geometry_changed": {"geometry_changed": True},
            "window_mismatch": {
                "after_frame": {"target_window_id": "window-other"}
            },
            "window_replaced": {"target_window_replaced": True},
            "stale_flag": {"after_frame_fresh": False},
            "same_frame": {"after_frame": {"frame_id": "frame-before"}},
            "reverse_frames": {
                "after_frame": {"captured_at": T0 - timedelta(seconds=1)}
            },
            "unknown_page": {"after_frame": {"page_type": "unknown"}},
            "ambiguous_burst": {"ambiguous_input_burst": True},
            "unreviewed_boundary": {"review_status": "unreviewed"},
            "missing_reviewer": {"reviewed_by": None},
            "premature_review": {
                "reviewed_at": T0 + timedelta(milliseconds=250)
            },
        }
        for label, override in cases.items():
            with self.subTest(label=label):
                evidence = _evidence()
                _merge(evidence, override)
                result = self._classify(
                    _observation(panel=True),
                    _observation(panel=True),
                    evidence,
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self._assert_no_authority(result)

    def test_apply_event_must_be_reviewed_complete_and_within_boundary(self) -> None:
        requested = _selection()
        cases = {
            "unreviewed": {"review_status": "unreviewed"},
            "ambiguous": {"review_status": "ambiguous"},
            "missing_id": {"review_status": "reviewed", "event_id": None},
            "missing_time": {"review_status": "reviewed", "observed_at": None},
            "before_boundary": {
                "review_status": "reviewed",
                "observed_at": T0 - timedelta(seconds=1),
            },
            "equal_to_before_boundary": {
                "review_status": "reviewed",
                "observed_at": T0,
            },
            "after_boundary": {
                "review_status": "reviewed",
                "observed_at": T0 + timedelta(seconds=2),
            },
            "absent_with_fields": {
                "review_status": "not_present",
                "event_id": "event-1",
                "observed_at": T0 + timedelta(seconds=1),
            },
        }
        for label, apply_override in cases.items():
            with self.subTest(label=label):
                evidence = _evidence(apply="reviewed", requested=requested)
                evidence["apply_event"].update(apply_override)
                result = self._classify(
                    _observation(panel=True),
                    _observation(panel=False, resources=("stone",), levels=(5,)),
                    evidence,
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self._assert_no_authority(result)

    def test_marker_mismatch_or_incompleteness_is_ambiguous(self) -> None:
        requested = _selection()
        cases = {
            "unreviewed": {
                "review_status": "unreviewed",
                "observed_filter": requested.model_dump(),
            },
            "ambiguous": {
                "review_status": "ambiguous",
                "observed_filter": requested.model_dump(),
            },
            "missing_filter": {
                "review_status": "reviewed",
                "observed_filter": None,
                "fresh_in_after_frame": True,
            },
            "mismatch": {
                "review_status": "reviewed",
                "observed_filter": _selection(level=6).model_dump(),
                "fresh_in_after_frame": True,
            },
            "not_fresh": {
                "review_status": "reviewed",
                "observed_filter": requested.model_dump(),
                "fresh_in_after_frame": False,
            },
            "absent_with_filter": {
                "review_status": "not_present",
                "observed_filter": requested.model_dump(),
            },
        }
        for label, marker in cases.items():
            with self.subTest(label=label):
                evidence = _evidence(apply="reviewed", requested=requested)
                evidence["result_marker"] = marker
                result = self._classify(
                    _observation(panel=True),
                    _observation(panel=False, resources=("stone",), levels=(5,)),
                    evidence,
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self._assert_no_authority(result)

    def test_unknown_invalid_or_inconsistent_observations_are_ambiguous(self) -> None:
        valid = _observation(panel=True).model_dump()
        cases = {
            "missing": None,
            "unknown": {**valid, "page_type": "unknown"},
            "coerced_bool": {**valid, "filter_panel_visible": 1},
            "invalid_level": {**valid, "selected_levels": [13]},
            "unexpected_field": {**valid, "raw_coordinate_click": [1, 2]},
            "selection_conflict": {
                **valid,
                "resource_filter_enabled": True,
                "selected_resource_types": ["stone"],
                "resource_toggles": [
                    {
                        "resource_type": "stone",
                        "selected": False,
                        "visible": True,
                        "enabled": True,
                        "x_min": 100,
                        "y_min": 100,
                        "x_max": 200,
                        "y_max": 200,
                    }
                ],
            },
        }
        for label, before in cases.items():
            with self.subTest(label=label):
                result = self._classify(
                    before,
                    _observation(panel=True),
                    _evidence(),
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self._assert_no_authority(result)

    def test_mutated_model_instance_is_strictly_revalidated(self) -> None:
        before = _observation(panel=True)
        before.filter_panel_visible = 1

        result = self._classify(
            before,
            _observation(panel=True),
            _evidence(),
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("invalid_map_observation", result.reasons)
        self._assert_no_authority(result)

    def test_boundary_payload_is_strict_and_forbids_extra_fields(self) -> None:
        cases = (
            {"after_frame_fresh": 1},
            {"unexpected": "field"},
            {"schema_version": "1"},
        )
        for override in cases:
            with self.subTest(override=override):
                evidence = _evidence()
                evidence.update(override)
                result = self._classify(
                    _observation(panel=True),
                    _observation(panel=True),
                    evidence,
                )
                self.assertEqual(
                    result.outcome, MapFilterTransitionOutcome.AMBIGUOUS
                )
                self.assertIn("invalid_boundary_evidence", result.reasons)
                self._assert_no_authority(result)

    def test_mutated_boundary_model_is_strictly_revalidated(self) -> None:
        before = _observation(panel=True)
        after = _observation(panel=False, resources=("stone",), levels=(5,))
        annotation = self._load_annotation(before, after)
        payload = self._bound_evidence(
            before,
            after,
            _evidence(apply="reviewed", requested=_selection()),
            annotation=annotation,
        )
        boundary = ReviewerBoundaryEvidence.model_validate(payload)
        object.__setattr__(boundary.after_frame, "capture_complete", 1)

        result = classify_map_filter_transition(
            before,
            after,
            boundary,
            recording=self.recording,
            annotation=annotation,
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.AMBIGUOUS)
        self.assertIn("invalid_boundary_evidence", result.reasons)
        self._assert_no_authority(result)

    def test_json_round_trip_keeps_strict_review_semantics(self) -> None:
        requested = _selection()
        evidence = ReviewerBoundaryEvidence.model_validate(
            _evidence(apply="reviewed", requested=requested)
        )
        json_payload = json.loads(evidence.model_dump_json())

        result = self._classify(
            _observation(panel=True),
            _observation(panel=False, resources=("stone",), levels=(5,)),
            json_payload,
        )

        self.assertEqual(result.outcome, MapFilterTransitionOutcome.APPLIED)
        self._assert_no_authority(result)

    def test_authority_invariants_cannot_be_overridden(self) -> None:
        payload = {
            "outcome": "applied",
            "causal_verified": True,
            "verifier_status": "verified",
            "execution_authority": "live",
            "live_dispatch_allowed": True,
        }
        with self.assertRaises(ValidationError):
            MapFilterTransitionResult.model_validate(payload)

    def _classify(
        self,
        before: MapLandDetection | dict | None,
        after: MapLandDetection | dict | None,
        evidence: dict,
        *,
        contract: str = "positive",
    ) -> MapFilterTransitionResult:
        annotation = self._load_annotation(
            before,
            after,
            contract=contract,
        )
        bound = self._bound_evidence(
            before,
            after,
            evidence,
            annotation=annotation,
        )
        return classify_map_filter_transition(
            before,
            after,
            bound,
            recording=self.recording,
            annotation=annotation,
        )

    def _load_annotation(
        self,
        before: MapLandDetection | dict | None,
        after: MapLandDetection | dict | None,
        *,
        contract: str = "positive",
        payload_override: dict | None = None,
    ):
        payload = _approved_annotation_payload(
            self.recording,
            before=before,
            after=after,
            contract=contract,
        )
        if payload_override:
            override = deepcopy(payload_override)
            segment_overrides = override.pop("segments", [])
            _merge(payload, override)
            for index, segment_override in enumerate(segment_overrides):
                _merge(payload["segments"][index], segment_override)
        self._annotation_counter += 1
        path = self._base / f"approved-{self._annotation_counter}.json"
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return load_recording_annotation(
            self.recording,
            path,
            require_approved=True,
        )

    def _bound_evidence(
        self,
        before: MapLandDetection | dict | None,
        after: MapLandDetection | dict | None,
        evidence: dict,
        *,
        annotation=None,
    ) -> dict:
        annotation = annotation or self.annotation
        bound = deepcopy(evidence)
        frame_by_id = {
            frame.frame_id: frame for frame in self.recording.frames
        }
        for label, expected_id, observation in (
            ("before_frame", "frame-before", before),
            ("after_frame", "frame-after", after),
        ):
            frame = frame_by_id[expected_id]
            if bound[label].get("frame_sha256") is None:
                bound[label]["frame_sha256"] = frame.sha256
            if bound[label].get("source_png_sha256") is None:
                bound[label]["source_png_sha256"] = frame.source_png_sha256
            try:
                perception_sha256 = map_filter_perception_sha256(observation)
            except ValueError:
                perception_sha256 = "0" * 64
            if bound[label].get("perception_sha256") is None:
                bound[label]["perception_sha256"] = perception_sha256
        if bound.get("source_binding") is None:
            bound["source_binding"] = {
                "session_id": self.recording.manifest.session_id,
                "source_manifest_sha256": self.recording.manifest_sha256,
                "source_events_sha256": self.recording.manifest.events_sha256,
                "annotation_id": annotation.annotation.annotation_id,
                "annotation_sha256": annotation.sha256,
                "annotation_segment_id": annotation.annotation.segments[
                    0
                ].segment_id,
                "source_event_id": self.recording.input_events[0].event_id,
            }
        return bound

    def _assert_no_authority(self, result: MapFilterTransitionResult) -> None:
        self.assertFalse(result.causal_verified)
        self.assertEqual(result.verifier_status, "unproven")
        self.assertEqual(result.execution_authority, "none")
        self.assertFalse(result.live_dispatch_allowed)
        self.assertFalse(result.safe_for_live_replay)
        self.assertFalse(result.terminal_source_eligible)
        self.assertFalse(result.closure_eligible)
        self.assertFalse(result.knowledge_publication_allowed)


def _selection(*, level: int = 5) -> MapFilterSelection:
    return MapFilterSelection(
        resource_filter_enabled=True,
        resource_types=("stone",),
        levels=(level,),
    )


def _observation(
    *,
    panel: bool,
    resources: tuple[str, ...] = (),
    levels: tuple[int, ...] = (),
    map_center: tuple[int, int] | None = None,
    lands: list[dict] | None = None,
) -> MapLandDetection:
    payload = {
        "page_type": "main_map",
        "filter_panel_visible": panel,
        "resource_filter_enabled": bool(resources),
        "selected_resource_types": list(resources),
        "selected_levels": list(levels),
        "filter_button_visible": False,
        "filter_button_enabled": False,
        "apply_button_visible": panel,
        "apply_button_enabled": panel,
        "resource_toggles": [],
        "level_toggles": [],
        "lands": lands or [],
        "visible_notes": [],
    }
    if panel:
        payload.update(
            {
                "apply_button_x_min": 800,
                "apply_button_y_min": 800,
                "apply_button_x_max": 900,
                "apply_button_y_max": 900,
            }
        )
    if map_center is not None:
        payload["map_center_x"], payload["map_center_y"] = map_center
    return MapLandDetection.model_validate(payload, strict=True)


def _evidence(
    *,
    apply: str = "not_present",
    requested: MapFilterSelection | None = None,
    marker: str = "not_present",
    marker_filter: MapFilterSelection | None = None,
    interrupted: bool = False,
) -> dict:
    apply_event = {
        "review_status": apply,
        "event_id": "event-click" if apply == "reviewed" else None,
        "observed_at": (
            T0 + timedelta(milliseconds=100) if apply == "reviewed" else None
        ),
    }
    return {
        "schema_version": 1,
        "review_status": "reviewed",
        "reviewed_by": "reviewer-1",
        "reviewed_at": T0 + timedelta(seconds=3),
        "before_frame": {
            "frame_id": "frame-before",
            "captured_at": T0,
            "page_type": "main_map",
            "target_window_id": "game-window",
            "geometry_id": "geometry-1920x1080",
            "geometry_complete": True,
            "capture_complete": True,
            "capture_error": False,
        },
        "after_frame": {
            "frame_id": "frame-after",
            "captured_at": T0 + timedelta(milliseconds=500),
            "page_type": "main_map",
            "target_window_id": "game-window",
            "geometry_id": "geometry-1920x1080",
            "geometry_complete": True,
            "capture_complete": True,
            "capture_error": False,
        },
        "after_frame_fresh": True,
        "apply_event": apply_event,
        "requested_filter": requested.model_dump() if requested else None,
        "result_marker": {
            "review_status": marker,
            "observed_filter": (
                marker_filter.model_dump() if marker_filter is not None else None
            ),
            "fresh_in_after_frame": marker == "reviewed",
        },
        "target_window_replaced": False,
        "geometry_changed": False,
        "ambiguous_input_burst": False,
        "interrupted": interrupted,
    }


def _merge(target: dict, update: dict) -> None:
    for key, value in update.items():
        if isinstance(value, dict) and isinstance(target.get(key), dict):
            _merge(target[key], value)
        else:
            target[key] = deepcopy(value)


def _approved_annotation_payload(
    recording,
    *,
    before: MapLandDetection | dict | None,
    after: MapLandDetection | dict | None,
    contract: str = "positive",
) -> dict[str, object]:
    reviewed_at = (recording.manifest.ended_at + timedelta(seconds=1)).isoformat()
    payload = build_annotation_template(
        recording,
        workflow_id="map-filter-apply",
        annotated_by="annotator",
        now=recording.manifest.ended_at + timedelta(seconds=1),
    ).model_dump(mode="json")
    contract_values = {
        "positive": ("positive", "positive", "applied"),
        "no_change": ("no_change", "negative", "no_change"),
        "interrupted": (
            "popup_interruption",
            "negative",
            "interrupted",
        ),
        "operator_cancelled": (
            "operator_cancelled",
            "negative",
            "interrupted",
        ),
        "panel_opened": (
            "observation_only",
            "trace_only",
            "panel_opened",
        ),
        "selection_changed": (
            "observation_only",
            "trace_only",
            "selection_changed",
        ),
    }
    sample_label, evidence_use, outcome = contract_values[contract]
    semantic_contract = {
        "panel_opened": (
            "map-filter-open-panel",
            "map-filter-control",
            "open-filter-panel",
        ),
        "selection_changed": (
            "map-filter-change-selection",
            "map-filter-selection-control",
            "change-filter-selection",
        ),
    }.get(
        contract,
        ("map-filter-apply", "map-filter-control", "apply-filter"),
    )
    action_name, target_kind, target_key = semantic_contract
    payload.update(
        {
            "review_status": "approved",
            "sample_label": sample_label,
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
        "notes": ["semantic transition reviewed"],
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
    payload["segments"][0].update(
        {
            "sample_label": sample_label,
            "risk_class": "read_only",
            "page_before": "main-map",
            "page_after": "main-map-filtered",
            "proposed_action_name": action_name,
            "observation_schema_id": "map-land-filter-v1",
            "before_observation_sha256": _safe_perception_digest(before),
            "after_observation_sha256": _safe_perception_digest(after),
            "semantic_target": {
                "page": "main-map",
                "target_kind": target_kind,
                "target_key": target_key,
                "visible_label": "筛选",
                "disambiguators": ["reviewed apply control"],
                "unique_in_frame": True,
            },
            "observed_preconditions": ["filter panel is open"],
            "expected_delta_claim": ["selected filters become active"],
            "observed_delta": ["reviewed filter transition"],
            "outcome": outcome,
            "evidence_use": evidence_use,
            "unresolved_assumptions": [],
        }
    )
    return payload


def _safe_perception_digest(
    observation: MapLandDetection | dict | None,
) -> str:
    try:
        return map_filter_perception_sha256(observation)
    except ValueError:
        return "1" * 64


if __name__ == "__main__":
    unittest.main()
