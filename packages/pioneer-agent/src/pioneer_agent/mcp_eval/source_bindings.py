"""Bind canonical golden and Record & Replay evidence into MCP eval runs."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any

from pioneer_agent.mcp_eval.models import EvalSourceBindings
from pioneer_agent.mcp_server.service import GameMCPService
from pioneer_agent.record_replay.corpus_catalog import audit_corpus_catalog_bundle
from pioneer_agent.record_replay.validation import (
    load_strict_json_bytes,
    read_bounded_regular_file,
)


MAX_GOLDEN_EXPECTATIONS_BYTES = 2_097_152
MAX_GOLDEN_FIXTURES = 512


@dataclass(frozen=True)
class RecordReplayCorpusPaths:
    catalog: Path
    registries_root: Path
    sessions_root: Path
    reviews_root: Path
    artifacts_root: Path


def build_source_bindings(
    *,
    golden_expectations: Path | None = None,
    golden_fixture_root: Path | None = None,
    record_replay: RecordReplayCorpusPaths | None = None,
) -> EvalSourceBindings:
    values: dict[str, Any] = {}
    if golden_expectations is not None or golden_fixture_root is not None:
        if golden_expectations is None or golden_fixture_root is None:
            raise ValueError("golden expectations and fixture root must be provided together")
        values.update(_bind_golden(golden_expectations, golden_fixture_root))
    if record_replay is not None:
        values.update(_bind_record_replay(record_replay))
    return EvalSourceBindings(**values)


def _bind_golden(expectations_path: Path, fixture_root: Path) -> dict[str, Any]:
    read = read_bounded_regular_file(
        expectations_path,
        max_bytes=MAX_GOLDEN_EXPECTATIONS_BYTES,
        label="Advisor golden expectations",
    )
    payload = load_strict_json_bytes(read.payload)
    if not isinstance(payload, dict) or payload.get("version") != 2:
        raise ValueError("Advisor golden expectations must use version 2")
    fixtures = payload.get("fixtures")
    if not isinstance(fixtures, dict) or not fixtures or len(fixtures) > MAX_GOLDEN_FIXTURES:
        raise ValueError("Advisor golden expectations require a bounded fixture map")

    service = GameMCPService(fixture_root=fixture_root)
    matched = 0
    try:
        for fixture, expectation in fixtures.items():
            _validate_fixture_name(fixture)
            if not isinstance(expectation, dict):
                raise ValueError("Advisor golden fixture expectation must be an object")
            expected = expectation.get("expected_action_type")
            if expected is not None and not isinstance(expected, str):
                raise ValueError("expected_action_type must be a string or null")
            response = service.evaluate_fixture(fixture)
            if response.status != "ok" or response.evaluation is None:
                raise ValueError(f"golden fixture failed MCP evaluation: {fixture}")
            selected = response.evaluation.get("selected_action")
            actual = selected.get("action_type") if isinstance(selected, dict) else None
            if actual == expected:
                matched += 1
    finally:
        service.close()

    fixture_count = len(fixtures)
    return {
        "golden_bound": True,
        "golden_expectations_sha256": read.identity.sha256,
        "golden_fixture_count": fixture_count,
        "golden_match_count": matched,
        "golden_all_matched": matched == fixture_count,
    }


def _bind_record_replay(paths: RecordReplayCorpusPaths) -> dict[str, Any]:
    audited = audit_corpus_catalog_bundle(
        paths.catalog,
        registries_root=paths.registries_root,
        sessions_root=paths.sessions_root,
        reviews_root=paths.reviews_root,
        artifacts_root=paths.artifacts_root,
    )
    splits: dict[str, str] = {}
    for registry in audited.audited_registries:
        for session in registry.loaded_registry.registry.sessions:
            previous = splits.setdefault(session.session_id, session.split)
            if previous != session.split:
                raise ValueError("R&R session crosses generation/holdout split")
    report = audited.report.model_dump(mode="json")
    return {
        "record_replay_bound": True,
        "record_replay_catalog_sha256": audited.loaded_catalog.sha256,
        "record_replay_audit_digest": _canonical_digest(report),
        "record_replay_session_count": len(splits),
        "record_replay_generation_count": sum(
            split == "generation" for split in splits.values()
        ),
        "record_replay_holdout_count": sum(
            split == "holdout" for split in splits.values()
        ),
        "record_replay_coverage_ready": audited.report.coverage_ready,
        "record_replay_blockers": list(audited.report.blockers),
    }


def _validate_fixture_name(value: Any) -> None:
    if not isinstance(value, str):
        raise ValueError("golden fixture name must be a string")
    path = PurePosixPath(value)
    if (
        path.is_absolute()
        or "\\" in value
        or any(part in {"", ".", ".."} for part in path.parts)
        or path.suffix != ".json"
    ):
        raise ValueError("golden fixture name must be a relative JSON path")


def _canonical_digest(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
