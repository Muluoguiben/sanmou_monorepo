from __future__ import annotations

import ast
import base64
from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from datetime import timedelta
from hashlib import sha256
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from pioneer_agent.app.record_replay import build_parser, main
import pioneer_agent.app.record_replay_evaluator as evaluator_app_module
from pioneer_agent.record_replay.annotations import SampleLabel
from pioneer_agent.record_replay.corpus_catalog import audit_corpus_catalog_bundle
from pioneer_agent.record_replay.holdout_eval import (
    HoldoutOracle,
    HoldoutPredictionSubmission,
    EvaluatorTrustPolicy,
    evaluation_input_sha256,
    score_holdout_submission_external,
    verify_holdout_attestation,
    write_attestation_once,
)
import pioneer_agent.record_replay.holdout_eval as holdout_eval_module
from tests.unit.test_record_replay_dataset_registry import (
    NOW,
    _add_sample,
    _file_sha256,
    _registry,
    _roots,
    _write_catalog,
    _write_named_registry,
)


@dataclass(frozen=True)
class _EvalFixture:
    submission_path: Path
    oracle_path: Path
    policy_path: Path
    private_key_path: Path
    catalog_path: Path
    registries_root: Path
    sessions_root: Path
    reviews_root: Path
    artifacts_root: Path
    evaluator_state_root: Path
    holdout_session_ids: tuple[str, ...]


def _write_json(path: Path, value: object) -> Path:
    path.write_text(
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return path


def _build_eval_fixture(base: Path) -> _EvalFixture:
    sessions_root, reviews_root = _roots(base)
    registries_root = base / "registries"
    artifacts_root = base / "artifacts"
    evaluator_state_root = base / "evaluator-state"
    registries_root.mkdir()
    artifacts_root.mkdir()
    evaluator_state_root.mkdir()
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
        for index, (split, label, width, start_state) in enumerate(specs, start=1)
    ]
    registry_path = _write_named_registry(
        registries_root,
        "map-filter.json",
        _registry(samples, split_status="frozen"),
    )
    catalog_path = _write_catalog(
        base,
        registry_paths=[registry_path],
        catalog_status="frozen",
    )
    audited = audit_corpus_catalog_bundle(
        catalog_path,
        registries_root=registries_root,
        sessions_root=sessions_root,
        reviews_root=reviews_root,
        artifacts_root=artifacts_root,
    )
    if not audited.report.coverage_ready:
        raise AssertionError("test corpus must satisfy the frozen coverage floor")

    expected: list[dict[str, object]] = []
    predictions: list[dict[str, object]] = []
    holdout_session_ids: list[str] = []
    for audited_registry in audited.audited_registries:
        dataset_id = audited_registry.loaded_registry.registry.dataset_id
        for identity in audited_registry.session_identities:
            if identity.split != "holdout":
                continue
            outcome = identity.expected_transition_outcome
            if outcome is None:
                continue
            input_digest = evaluation_input_sha256(
                session_id=identity.session_id,
                source_events_sha256=identity.source_events_sha256,
                encoded_frame_sha256s=identity.encoded_frame_sha256s,
            )
            common = {
                "dataset_id": dataset_id,
                "session_id": identity.session_id,
                "source_events_sha256": identity.source_events_sha256,
                "evaluation_input_sha256": input_digest,
            }
            expected.append({**common, "expected_outcome": outcome.value})
            predictions.append(
                {
                    **common,
                    "predicted_outcome": outcome.value,
                    "confidence": 0.95,
                }
            )
            holdout_session_ids.append(identity.session_id)
    expected.sort(key=lambda item: (str(item["dataset_id"]), str(item["session_id"])))
    predictions.sort(
        key=lambda item: (str(item["dataset_id"]), str(item["session_id"]))
    )
    catalog_sha256 = _file_sha256(catalog_path)

    private_key = Ed25519PrivateKey.generate()
    private_key_path = base / "evaluator-private.pem"
    private_key_path.write_bytes(
        private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
    )
    os.chmod(private_key_path, 0o600)
    public_key = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    policy = EvaluatorTrustPolicy(
        policy_id="map-filter-evaluator-policy-v1",
        evaluator_key_id="map-filter-evaluator-key-v1",
        ed25519_public_key_base64=base64.b64encode(public_key).decode("ascii"),
        corpus_id="sanmou-human-recordings-v1",
        catalog_sha256=catalog_sha256,
        valid_from=NOW - timedelta(days=30),
        valid_until=NOW + timedelta(days=30),
        minimum_holdout_count=len(expected),
        minimum_accuracy_ppm=1_000_000,
        maximum_unknown_count=0,
        evaluator_owner="eval-owner",
        approved_by="eval-policy-reviewer",
        approved_at=NOW,
    )
    policy_path = _write_json(
        base / "trust-policy.json", policy.model_dump(mode="json")
    )
    oracle = HoldoutOracle(
        oracle_id=str(uuid4()),
        created_at=NOW + timedelta(seconds=4),
        corpus_id="sanmou-human-recordings-v1",
        catalog_sha256=catalog_sha256,
        reviewed_by="oracle-reviewer",
        sealed_by="oracle-sealer",
        reviewed_at=NOW + timedelta(seconds=5),
        entries=expected,
    )
    oracle_path = _write_json(base / "oracle.json", oracle.model_dump(mode="json"))
    submission = HoldoutPredictionSubmission(
        submission_id=str(uuid4()),
        created_at=NOW + timedelta(seconds=6),
        corpus_id="sanmou-human-recordings-v1",
        catalog_sha256=catalog_sha256,
        predictor_id="map-filter-transition-v1",
        predictor_artifact_sha256=sha256(b"predictor-v1").hexdigest(),
        image_model_exercised_claimed=False,
        predictions=predictions,
    )
    submission_path = _write_json(
        base / "submission.json", submission.model_dump(mode="json")
    )
    return _EvalFixture(
        submission_path=submission_path,
        oracle_path=oracle_path,
        policy_path=policy_path,
        private_key_path=private_key_path,
        catalog_path=catalog_path,
        registries_root=registries_root,
        sessions_root=sessions_root,
        reviews_root=reviews_root,
        artifacts_root=artifacts_root,
        evaluator_state_root=evaluator_state_root,
        holdout_session_ids=tuple(holdout_session_ids),
    )


def _score(fixture: _EvalFixture):
    return score_holdout_submission_external(
        submission_path=fixture.submission_path,
        oracle_path=fixture.oracle_path,
        trust_policy_path=fixture.policy_path,
        private_key_path=fixture.private_key_path,
        catalog_path=fixture.catalog_path,
        registries_root=fixture.registries_root,
        sessions_root=fixture.sessions_root,
        reviews_root=fixture.reviews_root,
        artifacts_root=fixture.artifacts_root,
        evaluator_state_root=fixture.evaluator_state_root,
        attestation_id=str(uuid4()),
        now=NOW + timedelta(seconds=10),
    )


class RecordReplayHoldoutEvalTests(unittest.TestCase):
    def test_eval_modules_have_no_control_or_network_surface(self) -> None:
        forbidden_imports = {
            "socket",
            "subprocess",
            "requests",
            "pioneer_agent.adapters",
            "pioneer_agent.executor",
        }
        forbidden_calls = {
            "SendInput",
            "click",
            "drag",
            "key_press",
            "mouse_event",
            "send",
            "sendall",
        }
        for module in (holdout_eval_module, evaluator_app_module):
            source = Path(module.__file__).read_text(encoding="utf-8")
            tree = ast.parse(source)
            imports = {
                alias.name
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            imports.update(
                node.module or ""
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            )
            self.assertFalse(
                any(
                    imported == forbidden
                    or imported.startswith(f"{forbidden}.")
                    for imported in imports
                    for forbidden in forbidden_imports
                )
            )
            calls = {
                node.func.attr
                for node in ast.walk(tree)
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            }
            self.assertTrue(calls.isdisjoint(forbidden_calls))

    def test_external_scorer_signs_aggregate_without_releasing_labels(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))

            attestation = _score(fixture)
            attestation_path = Path(tmp) / "attestation.json"
            write_attestation_once(attestation_path, attestation)
            report = verify_holdout_attestation(
                submission_path=fixture.submission_path,
                attestation_path=attestation_path,
                trust_policy_path=fixture.policy_path,
                now=NOW + timedelta(seconds=11),
            )

            self.assertEqual(report.holdout_session_count, 5)
            self.assertEqual(report.exact_match_count, 5)
            self.assertEqual(report.accuracy_ppm, 1_000_000)
            self.assertTrue(report.passed_policy)
            self.assertTrue(report.signature_valid)
            self.assertTrue(report.holdout_oracle_verified)
            self.assertFalse(report.oracle_labels_disclosed)
            self.assertFalse(report.evaluator_host_isolation_verified)
            self.assertFalse(report.image_model_execution_verified)
            self.assertFalse(report.independent_eval_ready)
            serialized = attestation.model_dump_json()
            self.assertNotIn("expected_outcome", serialized)
            self.assertNotIn(_file_sha256(fixture.oracle_path), serialized)
            for session_id in fixture.holdout_session_ids:
                self.assertNotIn(session_id, serialized)

    def test_ordinary_cli_inspects_submission_without_oracle_surface(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            stdout = StringIO()

            with redirect_stdout(stdout):
                result = main(
                    ["inspect-holdout-submission", str(fixture.submission_path)]
                )

            self.assertEqual(result, 0)
            summary = json.loads(stdout.getvalue())
            self.assertEqual(summary["prediction_count"], 5)
            self.assertFalse(summary["oracle_accessed"])
            self.assertFalse(summary["oracle_labels_included"])
            self.assertNotIn("expected_outcome", stdout.getvalue())
            for session_id in fixture.holdout_session_ids:
                self.assertNotIn(session_id, stdout.getvalue())
            with redirect_stderr(StringIO()), self.assertRaises(SystemExit):
                build_parser().parse_args(
                    [
                        "inspect-holdout-submission",
                        str(fixture.submission_path),
                        "--oracle",
                        str(fixture.oracle_path),
                    ]
                )

    def test_tampered_signed_aggregate_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            attestation = _score(fixture)
            signature = bytearray(base64.b64decode(attestation.signature_base64))
            signature[0] ^= 0x01
            data = attestation.model_dump(mode="json")
            data["signature_base64"] = base64.b64encode(signature).decode("ascii")
            attestation_path = _write_json(Path(tmp) / "tampered.json", data)

            with self.assertRaisesRegex(ValueError, "signature is invalid"):
                verify_holdout_attestation(
                    submission_path=fixture.submission_path,
                    attestation_path=attestation_path,
                    trust_policy_path=fixture.policy_path,
                    now=NOW + timedelta(seconds=11),
                )

    def test_attestation_binds_the_exact_trust_policy(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            attestation = _score(fixture)
            attestation_path = Path(tmp) / "attestation.json"
            write_attestation_once(attestation_path, attestation)
            policy_data = json.loads(fixture.policy_path.read_text(encoding="utf-8"))
            policy_data["minimum_accuracy_ppm"] = 900_000
            _write_json(fixture.policy_path, policy_data)

            with self.assertRaisesRegex(ValueError, "exact trust policy"):
                verify_holdout_attestation(
                    submission_path=fixture.submission_path,
                    attestation_path=attestation_path,
                    trust_policy_path=fixture.policy_path,
                    now=NOW + timedelta(seconds=11),
                )

    def test_oracle_must_match_approved_holdout_annotations(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            oracle_data = json.loads(fixture.oracle_path.read_text(encoding="utf-8"))
            current = oracle_data["entries"][0]["expected_outcome"]
            oracle_data["entries"][0]["expected_outcome"] = (
                "no_change" if current != "no_change" else "applied"
            )
            _write_json(fixture.oracle_path, oracle_data)

            with self.assertRaisesRegex(
                ValueError, "oracle disagrees with approved holdout evidence"
            ):
                _score(fixture)

    def test_submission_must_cover_exact_holdout_set_and_inputs(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            submission_data = json.loads(
                fixture.submission_path.read_text(encoding="utf-8")
            )
            submission_data["predictions"].pop()
            _write_json(fixture.submission_path, submission_data)

            with self.assertRaisesRegex(
                ValueError, "submission does not contain exactly"
            ):
                _score(fixture)

    def test_valid_but_inaccurate_submission_remains_blocked(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            submission_data = json.loads(
                fixture.submission_path.read_text(encoding="utf-8")
            )
            current = submission_data["predictions"][0]["predicted_outcome"]
            submission_data["predictions"][0]["predicted_outcome"] = (
                "no_change" if current != "no_change" else "applied"
            )
            _write_json(fixture.submission_path, submission_data)
            attestation = _score(fixture)
            attestation_path = Path(tmp) / "failed-attestation.json"
            write_attestation_once(attestation_path, attestation)

            report = verify_holdout_attestation(
                submission_path=fixture.submission_path,
                attestation_path=attestation_path,
                trust_policy_path=fixture.policy_path,
                now=NOW + timedelta(seconds=11),
            )

            self.assertFalse(report.passed_policy)
            self.assertIn(
                "holdout_accuracy_policy_not_met", report.remaining_blockers
            )
            self.assertFalse(report.independent_eval_ready)

    @unittest.skipIf(os.name == "nt", "POSIX permission bits are not Windows ACLs")
    def test_external_private_key_must_not_be_group_or_world_readable(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            os.chmod(fixture.private_key_path, 0o644)

            with self.assertRaisesRegex(ValueError, "group/world accessible"):
                _score(fixture)

    def test_attestation_output_is_create_once(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            attestation = _score(fixture)
            output = Path(tmp) / "attestation.json"
            write_attestation_once(output, attestation)

            with self.assertRaisesRegex(ValueError, "already exists"):
                write_attestation_once(output, attestation)

    def test_external_evaluator_allows_only_one_signed_submission_per_catalog(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            _score(fixture)

            with self.assertRaisesRegex(ValueError, "budget already consumed"):
                _score(fixture)

    @unittest.skipIf(os.name == "nt", "hardlink race probe is POSIX-specific")
    def test_attestation_write_rejects_concurrent_hardlink(self) -> None:
        with TemporaryDirectory() as tmp:
            fixture = _build_eval_fixture(Path(tmp))
            attestation = _score(fixture)
            output = Path(tmp) / "attestation.json"
            linked = Path(tmp) / "linked-attestation.json"
            real_fsync = os.fsync
            linked_once = False

            def link_then_sync(descriptor: int) -> None:
                nonlocal linked_once
                if not linked_once:
                    os.link(output, linked)
                    linked_once = True
                real_fsync(descriptor)

            with patch(
                "pioneer_agent.record_replay.holdout_eval.os.fsync",
                side_effect=link_then_sync,
            ), self.assertRaisesRegex(ValueError, "write failed"):
                write_attestation_once(output, attestation)


if __name__ == "__main__":
    unittest.main()
