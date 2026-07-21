from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from io import BytesIO, StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from PIL import Image

from pioneer_agent.app.record_replay import main
from pioneer_agent.core.models import CaptureGeometry
from pioneer_agent.record_replay.annotations import (
    RecordingAnnotationManifest,
    RiskClass,
    SampleLabel,
    build_annotation_template,
)
from pioneer_agent.record_replay.dataset_registry import (
    DatasetRegistry,
    audit_dataset_registry,
    load_dataset_registry,
)
from pioneer_agent.record_replay.models import (
    FrameRecord,
    FrameRole,
    ImageFormat,
    InputEventRecord,
    InputKind,
    NormalizedPoint,
    PixelPoint,
    RecordingManifest,
    RecordingStatus,
    TargetWindow,
)
from pioneer_agent.record_replay.session_store import LoadedRecording, load_recording


NOW = datetime(2026, 7, 21, 12, 0, tzinfo=UTC)
WORKFLOW_ID = "map-filter-apply"
WORKFLOW_NAME = "map filter apply"


@dataclass
class _Sample:
    session_id: str
    session_root: Path
    review_path: Path
    review_data: dict[str, object]
    entry: dict[str, object]


def _geometry(width: int) -> CaptureGeometry:
    height = width
    return CaptureGeometry.model_validate(
        {
            "schema_version": 1,
            "capture_backend": "wgc",
            "outer_window": {
                "hwnd": 123,
                "pid": 456,
                "left": 10,
                "top": 20,
                "right": 10 + width,
                "bottom": 20 + height,
                "width": width,
                "height": height,
            },
            "capture_rect": {
                "left": 10,
                "top": 20,
                "right": 10 + width,
                "bottom": 20 + height,
                "width": width,
                "height": height,
            },
            "capture_origin": {"x": 10, "y": 20},
            "frame_size": [width, height],
        }
    )


def _png_bytes(seed: int) -> bytes:
    buffer = BytesIO()
    color = ((seed * 17) % 256, (seed * 37) % 256, (seed * 67) % 256)
    Image.new("RGB", (10, 10), color).save(buffer, format="PNG")
    return buffer.getvalue()


def _frame(
    *,
    session_id: str,
    sequence: int,
    frame_id: str,
    role: FrameRole,
    relative: str,
    payload: bytes,
    captured_at: datetime,
    elapsed_ms: int,
    geometry: CaptureGeometry,
    source_digest: str,
) -> FrameRecord:
    return FrameRecord(
        session_id=session_id,
        sequence=sequence,
        frame_id=frame_id,
        role=role,
        captured_at=captured_at,
        elapsed_ms=elapsed_ms,
        path=relative,
        sha256=sha256(payload).hexdigest(),
        byte_size=len(payload),
        image_format=ImageFormat.PNG,
        image_size=(10, 10),
        source_png_sha256=source_digest,
        capture_geometry=geometry,
    )


def _create_recording(
    sessions_root: Path,
    *,
    seed: int,
    width: int = 100,
    encoded_seed: int | None = None,
    source_namespace: str | None = None,
) -> tuple[Path, LoadedRecording]:
    session_id = str(uuid4())
    root = sessions_root / session_id
    frames_dir = root / "frames"
    frames_dir.mkdir(parents=True)
    geometry = _geometry(width)
    payload_seed = seed if encoded_seed is None else encoded_seed
    payloads = [
        _png_bytes(payload_seed * 10 + 1),
        _png_bytes(payload_seed * 10 + 2),
        _png_bytes(payload_seed * 10 + 3),
    ]
    relatives = [
        "frames/000000-start.png",
        "frames/000002-post.png",
        "frames/000003-end.png",
    ]
    for relative, payload in zip(relatives, payloads, strict=True):
        (root / relative).write_bytes(payload)

    def source_digest(index: int, payload: bytes) -> str:
        if source_namespace is None:
            return sha256(payload).hexdigest()
        return sha256(f"{source_namespace}-{index}".encode()).hexdigest()

    before = _frame(
        session_id=session_id,
        sequence=0,
        frame_id="frame-before",
        role=FrameRole.START,
        relative=relatives[0],
        payload=payloads[0],
        captured_at=NOW,
        elapsed_ms=0,
        geometry=geometry,
        source_digest=source_digest(0, payloads[0]),
    )
    event = InputEventRecord(
        session_id=session_id,
        sequence=1,
        event_id="event-click",
        kind=InputKind.CLICK,
        occurred_at=NOW + timedelta(milliseconds=100),
        ended_at=NOW + timedelta(milliseconds=120),
        elapsed_ms=100,
        duration_ms=20,
        window_hwnd=123,
        window_pid=456,
        capture_geometry=geometry,
        start_point=PixelPoint(x=width // 2, y=width // 2),
        start_normalized=NormalizedPoint(x=0.5, y=0.5),
        button="left",
        before_frame_id="frame-before",
        after_frame_id="frame-after",
    )
    after = _frame(
        session_id=session_id,
        sequence=2,
        frame_id="frame-after",
        role=FrameRole.POST_INPUT,
        relative=relatives[1],
        payload=payloads[1],
        captured_at=NOW + timedelta(milliseconds=500),
        elapsed_ms=500,
        geometry=geometry,
        source_digest=source_digest(1, payloads[1]),
    )
    end = _frame(
        session_id=session_id,
        sequence=3,
        frame_id="frame-end",
        role=FrameRole.END,
        relative=relatives[2],
        payload=payloads[2],
        captured_at=NOW + timedelta(seconds=1),
        elapsed_ms=1_000,
        geometry=geometry,
        source_digest=source_digest(2, payloads[2]),
    )
    records = [before, event, after, end]
    events_payload = b"".join(
        (record.model_dump_json(exclude_none=True) + "\n").encode()
        for record in records
    )
    (root / "events.jsonl").write_bytes(events_payload)
    manifest = RecordingManifest(
        session_id=session_id,
        workflow_name=WORKFLOW_NAME,
        status=RecordingStatus.COMPLETED,
        started_at=NOW,
        ended_at=NOW + timedelta(seconds=1),
        target=TargetWindow(
            hwnd=123,
            pid=456,
            process_started_at=NOW - timedelta(minutes=1),
            title="三国：谋定天下",
        ),
        initial_capture_geometry=geometry,
        events_sha256=sha256(events_payload).hexdigest(),
        record_count=len(records),
        frame_count=3,
        input_event_count=1,
        total_frame_bytes=sum(len(payload) for payload in payloads),
        stop_reason="operator_stop",
    )
    (root / "manifest.json").write_text(
        manifest.model_dump_json(indent=2), encoding="utf-8"
    )
    return root, load_recording(root)


def _approved_annotation(
    recording: LoadedRecording,
    *,
    label: SampleLabel,
    risk: RiskClass,
    capture_group_id: str,
    start_state_id: str,
    annotation_id: str | None = None,
) -> RecordingAnnotationManifest:
    template = build_annotation_template(
        recording,
        workflow_id=WORKFLOW_ID,
        annotated_by="annotator",
        now=NOW + timedelta(seconds=2),
    )
    data = template.model_dump(mode="json")
    if annotation_id is not None:
        data["annotation_id"] = annotation_id
    data.update(
        {
            "capture_group_id": capture_group_id,
            "review_status": "approved",
            "semantic_review": {
                "status": "approved",
                "reviewed_by": "semantic-reviewer",
                "reviewed_at": (NOW + timedelta(seconds=3)).isoformat(),
                "notes": ["reviewed against full session"],
            },
            "privacy_review": {
                "status": "approved",
                "reviewed_by": "privacy-reviewer",
                "reviewed_at": (NOW + timedelta(seconds=3)).isoformat(),
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
            },
            "sample_label": label.value,
            "risk_class": risk.value,
            "start_page": "main-map",
            "end_page": "main-map",
            "start_state_id": start_state_id,
        }
    )
    segment = data["segments"][0]
    segment.update(
        {
            "sample_label": label.value,
            "risk_class": risk.value,
            "page_before": "main-map",
            "page_after": "main-map",
        }
    )
    if risk == RiskClass.HIGH_RISK_TRACE_ONLY:
        segment.update(
            {
                "proposed_action_name": None,
                "semantic_target": None,
                "observed_preconditions": [],
                "expected_delta_claim": [],
                "observed_delta": [],
                "outcome": "unknown",
                "evidence_use": "trace_only",
                "unresolved_assumptions": ["high-risk action remains trace-only"],
            }
        )
    else:
        outcome = "applied"
        evidence_use = "positive"
        unique = True
        observed_delta = "filter selection visibly applied"
        if label != SampleLabel.POSITIVE:
            evidence_use = "negative"
            unique = label not in {
                SampleLabel.MISSING_TARGET,
                SampleLabel.AMBIGUOUS_TARGET,
            }
            if label in {
                SampleLabel.MISSING_TARGET,
                SampleLabel.AMBIGUOUS_TARGET,
            }:
                outcome = "ambiguous"
                observed_delta = "target was missing or ambiguous"
            elif label in {
                SampleLabel.POPUP_INTERRUPTION,
                SampleLabel.OPERATOR_CANCELLED,
            }:
                outcome = "interrupted"
                observed_delta = "workflow was interrupted"
            else:
                outcome = "no_change"
                observed_delta = "fresh observation showed no change"
        segment.update(
            {
                "proposed_action_name": WORKFLOW_ID,
                "observation_schema_id": "map-land-filter-v1",
                "before_observation_sha256": sha256(
                    f"{recording.manifest.session_id}:before".encode("utf-8")
                ).hexdigest(),
                "after_observation_sha256": sha256(
                    f"{recording.manifest.session_id}:after".encode("utf-8")
                ).hexdigest(),
                "semantic_target": {
                    "page": "main-map",
                    "target_kind": "map-filter-control",
                    "target_key": "apply-filter",
                    "visible_label": "应用",
                    "disambiguators": ["filter panel"],
                    "unique_in_frame": unique,
                },
                "observed_preconditions": ["main map and filter panel observed"],
                "expected_delta_claim": ["selected filter should be reflected"],
                "observed_delta": [observed_delta],
                "outcome": outcome,
                "evidence_use": evidence_use,
                "unresolved_assumptions": [],
            }
        )
    return RecordingAnnotationManifest.model_validate(data)


def _add_sample(
    sessions_root: Path,
    reviews_root: Path,
    *,
    seed: int,
    split: str,
    label: SampleLabel,
    risk: RiskClass = RiskClass.READ_ONLY,
    width: int = 100,
    start_state_id: str = "state-default",
    capture_group_id: str | None = None,
    encoded_seed: int | None = None,
    source_namespace: str | None = None,
    annotation_id: str | None = None,
) -> _Sample:
    session_root, recording = _create_recording(
        sessions_root,
        seed=seed,
        width=width,
        encoded_seed=encoded_seed,
        source_namespace=source_namespace,
    )
    session_id = recording.manifest.session_id
    capture_group_id = capture_group_id or f"capture-{session_id}"
    annotation = _approved_annotation(
        recording,
        label=label,
        risk=risk,
        capture_group_id=capture_group_id,
        start_state_id=start_state_id,
        annotation_id=annotation_id,
    )
    review_path = reviews_root / f"{session_id}.json"
    review_data = annotation.model_dump(mode="json")
    review_payload = (json.dumps(review_data, ensure_ascii=False, indent=2) + "\n").encode()
    review_path.write_bytes(review_payload)
    return _Sample(
        session_id=session_id,
        session_root=session_root,
        review_path=review_path,
        review_data=review_data,
        entry={
            "session_id": session_id,
            "source_events_sha256": recording.manifest.events_sha256,
            "split": split,
            "capture_group_id": capture_group_id,
            "review_ref": {
                "path": review_path.name,
                "sha256": sha256(review_payload).hexdigest(),
            },
            "source_kind": "human_recording",
        },
    )


def _registry(
    sessions: list[_Sample],
    *,
    risk_class: str = "harmless_navigation",
    split_status: str = "collecting",
    development_artifacts: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "artifact_type": "record_replay_dataset_registry",
        "corpus_id": "sanmou-human-recordings-v1",
        "dataset_id": "map-filter-apply-v1",
        "workflow_id": WORKFLOW_ID,
        "risk_class": risk_class,
        "split_status": split_status,
        "split_unit": "corpus_session_capture_group",
        "countable_semantic_contract": {
            "action_name": WORKFLOW_ID,
            "page": "main-map",
            "target_kind": "map-filter-control",
            "target_key": "apply-filter",
        },
        "sessions": [sample.entry for sample in sessions],
        "development_artifacts": development_artifacts or [],
        "execution_authority": "none",
        "live_dispatch_allowed": False,
        "knowledge_publication_allowed": False,
    }


def _write_registry(root: Path, data: dict[str, object]) -> Path:
    path = root / "registry.json"
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return path


def _roots(base: Path) -> tuple[Path, Path]:
    sessions_root = base / "sessions"
    reviews_root = base / "reviews"
    sessions_root.mkdir()
    reviews_root.mkdir()
    return sessions_root, reviews_root


class RecordReplayDatasetRegistryTests(unittest.TestCase):
    def test_cli_audits_explicit_registry_without_exposing_local_paths(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            registry_path = _write_registry(base, _registry([sample]))
            stdout = StringIO()

            with redirect_stdout(stdout):
                result = main(
                    [
                        "audit-dataset",
                        str(registry_path),
                        "--sessions-root",
                        str(sessions_root),
                        "--reviews-root",
                        str(reviews_root),
                    ]
                )

            self.assertEqual(result, 0)
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["coverage_scope"], "provisional_policy_floor_only")
            self.assertFalse(report["independent_eval_ready"])
            self.assertEqual(report["execution_authority"], "none")
            self.assertFalse(report["live_dispatch_allowed"])
            self.assertNotIn(str(base), stdout.getvalue())

    def test_collecting_registry_reports_missing_coverage_without_authority(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            registry_path = _write_registry(base, _registry([sample]))

            report = audit_dataset_registry(
                registry_path,
                sessions_root=sessions_root,
                reviews_root=reviews_root,
            )

            self.assertTrue(report.integrity_valid)
            self.assertTrue(report.registry_internal_leak_free)
            self.assertFalse(report.corpus_catalog_verified)
            self.assertFalse(report.development_lineage_verified)
            self.assertFalse(report.holdout_oracle_verified)
            self.assertFalse(report.human_capture_provenance_verified)
            self.assertFalse(report.visual_near_duplicate_checked)
            self.assertFalse(report.structured_start_state_verified)
            self.assertFalse(report.filesystem_race_hardened)
            self.assertFalse(report.independent_eval_ready)
            self.assertEqual(report.coverage_scope, "provisional_policy_floor_only")
            self.assertFalse(report.coverage_ready)
            self.assertIn("generation_positive_below_3", report.blockers)
            self.assertIn("dataset_is_still_collecting", report.blockers)
            self.assertFalse(report.image_model_exercised)
            self.assertEqual(report.execution_authority, "none")
            self.assertFalse(report.live_dispatch_allowed)
            self.assertFalse(report.safe_for_live_replay)
            self.assertTrue(report.manual_promotion_required)
            self.assertFalse(report.terminal_source_eligible)
            self.assertFalse(report.closure_eligible)
            self.assertFalse(report.knowledge_publication_allowed)
            serialized = report.model_dump_json()
            self.assertNotIn(str(base), serialized)
            self.assertNotIn("三国：谋定天下", serialized)

    def test_harmless_navigation_floor_with_unseen_holdout_can_be_ready(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            specs = [
                ("generation", SampleLabel.POSITIVE, 100, "state-a"),
                ("generation", SampleLabel.POSITIVE, 100, "state-b"),
                ("generation", SampleLabel.POSITIVE, 120, "state-a"),
                ("generation", SampleLabel.MISSING_TARGET, 100, "state-a"),
                ("generation", SampleLabel.POPUP_INTERRUPTION, 100, "state-a"),
                ("generation", SampleLabel.NO_CHANGE, 100, "state-a"),
                ("holdout", SampleLabel.POSITIVE, 100, "state-unseen"),
                ("holdout", SampleLabel.POSITIVE, 120, "state-a"),
                ("holdout", SampleLabel.AMBIGUOUS_TARGET, 100, "state-a"),
                ("holdout", SampleLabel.OPERATOR_CANCELLED, 100, "state-a"),
                ("holdout", SampleLabel.TIMEOUT, 100, "state-a"),
            ]
            samples = [
                _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=index,
                    split=split,
                    label=label,
                    width=width,
                    start_state_id=start_state,
                )
                for index, (split, label, width, start_state) in enumerate(
                    specs, start=1
                )
            ]
            registry_data = _registry(samples)
            registry_path = _write_registry(base, registry_data)
            collecting_report = audit_dataset_registry(
                registry_path,
                sessions_root=sessions_root,
                reviews_root=reviews_root,
            )
            self.assertFalse(collecting_report.coverage_ready)
            self.assertEqual(
                collecting_report.blockers, ["dataset_is_still_collecting"]
            )
            registry_data["split_status"] = "frozen"
            _write_registry(base, registry_data)

            report = audit_dataset_registry(
                registry_path,
                sessions_root=sessions_root,
                reviews_root=reviews_root,
            )

            self.assertTrue(report.coverage_ready)
            self.assertEqual(report.blockers, [])
            self.assertEqual(report.generation.positive_count, 3)
            self.assertEqual(report.generation.geometry_count, 2)
            self.assertEqual(report.holdout.positive_count, 2)
            self.assertEqual(report.holdout.negative_count, 3)
            self.assertTrue(report.manual_promotion_required)
            self.assertFalse(report.live_dispatch_allowed)

    def test_low_risk_mutation_uses_five_plus_five_and_three_plus_five_floor(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            negative_labels = [
                SampleLabel.MISSING_TARGET,
                SampleLabel.AMBIGUOUS_TARGET,
                SampleLabel.POPUP_INTERRUPTION,
                SampleLabel.NO_CHANGE,
                SampleLabel.TIMEOUT,
            ]
            specs: list[tuple[str, SampleLabel, str, int]] = []
            specs.extend(
                (
                    "generation",
                    SampleLabel.POSITIVE,
                    "state-a",
                    120 if index == 0 else 100,
                )
                for index in range(5)
            )
            specs.extend(
                ("generation", label, "state-a", 100)
                for label in negative_labels
            )
            specs.extend(
                ("holdout", SampleLabel.POSITIVE, "state-unseen", 100)
                for _ in range(3)
            )
            specs.extend(
                ("holdout", label, "state-a", 100)
                for label in negative_labels
            )
            samples = [
                _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=index,
                    split=split,
                    label=label,
                    risk=RiskClass.LOW_RISK_MUTATION,
                    start_state_id=start_state,
                    width=width,
                )
                for index, (split, label, start_state, width) in enumerate(
                    specs, start=30
                )
            ]
            registry_path = _write_registry(
                base,
                _registry(
                    samples,
                    risk_class="low_risk_mutation",
                    split_status="frozen",
                ),
            )

            report = audit_dataset_registry(
                registry_path,
                sessions_root=sessions_root,
                reviews_root=reviews_root,
            )

            self.assertTrue(report.coverage_ready)
            self.assertEqual(report.generation.positive_count, 5)
            self.assertEqual(report.generation.geometry_count, 2)
            self.assertEqual(report.generation.negative_count, 5)
            self.assertEqual(
                set(report.generation.negative_categories),
                {"target", "interruption", "no_change_timeout"},
            )
            self.assertEqual(report.holdout.positive_count, 3)
            self.assertEqual(report.holdout.negative_count, 5)
            self.assertEqual(
                set(report.holdout.negative_categories),
                {"target", "interruption", "no_change_timeout"},
            )
            self.assertFalse(report.live_dispatch_allowed)

    def test_high_risk_dataset_is_always_trace_only_and_never_ready(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.OBSERVATION_ONLY,
                risk=RiskClass.HIGH_RISK_TRACE_ONLY,
            )
            registry_path = _write_registry(
                base,
                _registry(
                    [sample],
                    risk_class="high_risk_trace_only",
                    split_status="frozen",
                ),
            )

            report = audit_dataset_registry(
                registry_path,
                sessions_root=sessions_root,
                reviews_root=reviews_root,
            )

            self.assertFalse(report.coverage_ready)
            self.assertEqual(report.blockers, ["high_risk_trace_only"])
            self.assertFalse(report.live_dispatch_allowed)

    def test_holdout_must_have_unseen_geometry_or_start_state(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            specs = [
                ("generation", SampleLabel.POSITIVE, 100),
                ("generation", SampleLabel.POSITIVE, 100),
                ("generation", SampleLabel.POSITIVE, 120),
                ("generation", SampleLabel.MISSING_TARGET, 100),
                ("generation", SampleLabel.POPUP_INTERRUPTION, 100),
                ("generation", SampleLabel.NO_CHANGE, 100),
                ("holdout", SampleLabel.POSITIVE, 100),
                ("holdout", SampleLabel.POSITIVE, 120),
                ("holdout", SampleLabel.AMBIGUOUS_TARGET, 100),
                ("holdout", SampleLabel.OPERATOR_CANCELLED, 100),
                ("holdout", SampleLabel.TIMEOUT, 100),
            ]
            samples = [
                _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=index,
                    split=split,
                    label=label,
                    width=width,
                    start_state_id="state-shared",
                )
                for index, (split, label, width) in enumerate(specs, start=60)
            ]
            registry_path = _write_registry(
                base, _registry(samples, split_status="frozen")
            )

            report = audit_dataset_registry(
                registry_path,
                sessions_root=sessions_root,
                reviews_root=reviews_root,
            )

            self.assertFalse(report.coverage_ready)
            self.assertEqual(
                report.blockers, ["holdout_has_no_unseen_geometry_or_start_state"]
            )

    def test_duplicate_capture_group_is_rejected_even_within_one_split(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            samples = [
                _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=index,
                    split="generation",
                    label=SampleLabel.POSITIVE,
                    capture_group_id="shared-capture-group",
                )
                for index in (1, 2)
            ]
            registry_path = _write_registry(base, _registry(samples))

            with self.assertRaisesRegex(ValueError, "duplicate capture group"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_duplicate_encoded_frame_is_rejected_across_splits(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            first = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
                encoded_seed=99,
                source_namespace="source-a",
            )
            second = _add_sample(
                sessions_root,
                reviews_root,
                seed=2,
                split="holdout",
                label=SampleLabel.POSITIVE,
                encoded_seed=99,
                source_namespace="source-b",
            )
            registry_path = _write_registry(base, _registry([first, second]))

            with self.assertRaisesRegex(ValueError, "duplicate encoded frame SHA256"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_reencoded_same_source_png_is_rejected_across_splits(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            first = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
                source_namespace="shared-source",
            )
            second = _add_sample(
                sessions_root,
                reviews_root,
                seed=2,
                split="holdout",
                label=SampleLabel.POSITIVE,
                source_namespace="shared-source",
            )
            registry_path = _write_registry(base, _registry([first, second]))

            with self.assertRaisesRegex(ValueError, "duplicate source PNG SHA256"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_duplicate_annotation_id_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            annotation_id = str(uuid4())
            samples = [
                _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=index,
                    split="generation",
                    label=SampleLabel.POSITIVE,
                    annotation_id=annotation_id,
                )
                for index in (1, 2)
            ]
            registry_path = _write_registry(base, _registry(samples))

            with self.assertRaisesRegex(ValueError, "duplicate annotation id"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_holdout_cannot_feed_a_development_artifact(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="holdout",
                label=SampleLabel.POSITIVE,
            )
            registry_path = _write_registry(
                base,
                _registry(
                    [sample],
                    development_artifacts=[
                        {
                            "artifact_id": "map-filter-prompt-v1",
                            "source_session_ids": [sample.session_id],
                        }
                    ],
                ),
            )

            with self.assertRaisesRegex(ValueError, "holdout session"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_registry_binds_events_review_digest_workflow_and_capture_group(self) -> None:
        mutations = {
            "events": lambda data: data["sessions"][0].update(
                source_events_sha256="0" * 64
            ),
            "review": lambda data: data["sessions"][0]["review_ref"].update(
                sha256="0" * 64
            ),
            "capture": lambda data: data["sessions"][0].update(
                capture_group_id="foreign-capture"
            ),
            "workflow": lambda data: data.update(workflow_id="foreign-workflow"),
        }
        for name, mutate in mutations.items():
            with self.subTest(name=name), TemporaryDirectory() as tmp:
                base = Path(tmp)
                sessions_root, reviews_root = _roots(base)
                sample = _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=1,
                    split="generation",
                    label=SampleLabel.POSITIVE,
                )
                data = _registry([sample])
                mutate(data)
                registry_path = _write_registry(base, data)

                with self.assertRaises(ValueError):
                    audit_dataset_registry(
                        registry_path,
                        sessions_root=sessions_root,
                        reviews_root=reviews_root,
                    )

    def test_unapproved_eval_privacy_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            sample.review_data["privacy_review"]["approved_for_eval_candidate"] = False
            payload = (
                json.dumps(sample.review_data, ensure_ascii=False, indent=2) + "\n"
            ).encode()
            sample.review_path.write_bytes(payload)
            sample.entry["review_ref"]["sha256"] = sha256(payload).hexdigest()
            registry_path = _write_registry(base, _registry([sample]))

            with self.assertRaisesRegex(ValueError, "privacy-approved for eval"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_another_workflow_action_cannot_count_as_this_workflow(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            sample.review_data["segments"][0]["proposed_action_name"] = (
                "map-filter-cancel"
            )
            payload = (
                json.dumps(sample.review_data, ensure_ascii=False, indent=2) + "\n"
            ).encode()
            sample.review_path.write_bytes(payload)
            sample.entry["review_ref"]["sha256"] = sha256(payload).hexdigest()
            registry_path = _write_registry(base, _registry([sample]))

            with self.assertRaisesRegex(ValueError, "action does not match"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_negative_label_must_match_its_transition_outcome(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.NO_CHANGE,
            )
            sample.review_data["segments"][0]["outcome"] = "applied"
            payload = (
                json.dumps(sample.review_data, ensure_ascii=False, indent=2) + "\n"
            ).encode()
            sample.review_path.write_bytes(payload)
            sample.entry["review_ref"]["sha256"] = sha256(payload).hexdigest()
            registry_path = _write_registry(base, _registry([sample]))

            # The annotation model owns the same centralized label/outcome
            # contract and therefore rejects this before dataset auditing can
            # count it.
            with self.assertRaisesRegex(ValueError, "recording annotation is invalid"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_foreign_semantic_target_cannot_count_for_the_workflow(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            target = sample.review_data["segments"][0]["semantic_target"]
            target.update(
                {
                    "target_kind": "mail-button",
                    "target_key": "open-mail",
                    "visible_label": "邮件",
                }
            )
            payload = (
                json.dumps(sample.review_data, ensure_ascii=False, indent=2) + "\n"
            ).encode()
            sample.review_path.write_bytes(payload)
            sample.entry["review_ref"]["sha256"] = sha256(payload).hexdigest()
            registry_path = _write_registry(base, _registry([sample]))

            with self.assertRaisesRegex(ValueError, "semantic contract"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_counted_session_and_segment_pages_must_match_the_contract(self) -> None:
        for field in ("start_page", "segment_page"):
            with self.subTest(field=field), TemporaryDirectory() as tmp:
                base = Path(tmp)
                sessions_root, reviews_root = _roots(base)
                sample = _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=1,
                    split="generation",
                    label=SampleLabel.POSITIVE,
                )
                if field == "start_page":
                    sample.review_data["start_page"] = "battle-report"
                else:
                    sample.review_data["segments"][0]["page_before"] = (
                        "battle-report"
                    )
                payload = (
                    json.dumps(sample.review_data, ensure_ascii=False, indent=2)
                    + "\n"
                ).encode()
                sample.review_path.write_bytes(payload)
                sample.entry["review_ref"]["sha256"] = sha256(payload).hexdigest()
                registry_path = _write_registry(base, _registry([sample]))

                with self.assertRaisesRegex(ValueError, "page violates"):
                    audit_dataset_registry(
                        registry_path,
                        sessions_root=sessions_root,
                        reviews_root=reviews_root,
                    )

    def test_raw_frame_has_fixed_auditor_limit_before_session_load(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            registry_path = _write_registry(base, _registry([sample]))

            with patch(
                "pioneer_agent.record_replay.dataset_registry.MAX_FRAME_BYTES",
                10,
            ), self.assertRaisesRegex(ValueError, "per-frame audit size limit"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_review_path_escape_and_unsafe_registry_values_are_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            cases = [
                ("../review.json", False),
                ("C:/review.json", False),
                ("\\\\server\\share\\review.json", False),
                (sample.review_path.name, 0),
            ]
            for path_value, dispatch_value in cases:
                with self.subTest(path=path_value, dispatch=dispatch_value):
                    data = _registry([sample])
                    data["sessions"][0]["review_ref"]["path"] = path_value
                    data["live_dispatch_allowed"] = dispatch_value
                    registry_path = _write_registry(base, data)
                    with self.assertRaisesRegex(ValueError, "dataset registry is invalid"):
                        load_dataset_registry(registry_path)

    def test_duplicate_json_key_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            path = base / "registry.json"
            path.write_text(
                '{"schema_version":1,"schema_version":1}',
                encoding="utf-8",
            )

            with self.assertRaisesRegex(ValueError, "dataset registry is invalid"):
                load_dataset_registry(path)

    @unittest.skipIf(os.name == "nt", "link semantics are exercised on the WSL host")
    def test_symlinked_or_hardlinked_review_is_rejected(self) -> None:
        for link_kind in ("symlink", "hardlink"):
            with self.subTest(link_kind=link_kind), TemporaryDirectory() as tmp:
                base = Path(tmp)
                sessions_root, reviews_root = _roots(base)
                sample = _add_sample(
                    sessions_root,
                    reviews_root,
                    seed=1,
                    split="generation",
                    label=SampleLabel.POSITIVE,
                )
                outside = base / "outside.json"
                outside.write_bytes(sample.review_path.read_bytes())
                sample.review_path.unlink()
                if link_kind == "symlink":
                    sample.review_path.symlink_to(outside)
                else:
                    os.link(outside, sample.review_path)
                registry_path = _write_registry(base, _registry([sample]))

                with self.assertRaisesRegex(ValueError, "link|hard-linked"):
                    audit_dataset_registry(
                        registry_path,
                        sessions_root=sessions_root,
                        reviews_root=reviews_root,
                    )

    @unittest.skipIf(os.name == "nt", "hardlink semantics are exercised on the WSL host")
    def test_hardlinked_raw_artifact_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            outside = base / "manifest-copy.json"
            outside.write_bytes((sample.session_root / "manifest.json").read_bytes())
            (sample.session_root / "manifest.json").unlink()
            os.link(outside, sample.session_root / "manifest.json")
            registry_path = _write_registry(base, _registry([sample]))

            with self.assertRaisesRegex(ValueError, "hard-linked"):
                audit_dataset_registry(
                    registry_path,
                    sessions_root=sessions_root,
                    reviews_root=reviews_root,
                )

    def test_duplicate_session_cannot_inflate_counts(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            registry_path = _write_registry(base, _registry([sample, sample]))

            with self.assertRaisesRegex(ValueError, "dataset registry is invalid"):
                load_dataset_registry(registry_path)

    def test_retired_dataset_cannot_report_coverage_ready(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            sessions_root, reviews_root = _roots(base)
            sample = _add_sample(
                sessions_root,
                reviews_root,
                seed=1,
                split="generation",
                label=SampleLabel.POSITIVE,
            )
            registry_path = _write_registry(
                base, _registry([sample], split_status="retired")
            )

            report = audit_dataset_registry(
                registry_path,
                sessions_root=sessions_root,
                reviews_root=reviews_root,
            )

            self.assertFalse(report.coverage_ready)
            self.assertIn("dataset_is_retired", report.blockers)


if __name__ == "__main__":
    unittest.main()
