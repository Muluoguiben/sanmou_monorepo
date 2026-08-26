"""Bounded static runner for the MCP-native scenario battery."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any
from uuid import uuid4

from pydantic import ValidationError

from pioneer_agent.mcp_eval.models import (
    BatteryManifest,
    McpEvalRun,
    RunManifest,
    StaticScenarioTranscript,
    StaticTranscriptBundle,
)
from pioneer_agent.mcp_eval.scoring import aggregate_reports, score_scenario
from pioneer_agent.record_replay.validation import load_strict_json_bytes, read_bounded_regular_file


MAX_BATTERY_BYTES = 2_097_152
MAX_TRANSCRIPT_BUNDLE_BYTES = 8_388_608


class LoadedBattery:
    def __init__(
        self,
        *,
        manifest: BatteryManifest,
        battery_sha256: str,
        transcripts: dict[str, StaticScenarioTranscript],
        fixture_sha256s: tuple[str, ...],
    ) -> None:
        self.manifest = manifest
        self.battery_sha256 = battery_sha256
        self.transcripts = transcripts
        self.fixture_sha256s = fixture_sha256s


def load_battery(path: Path) -> LoadedBattery:
    battery_path = path.absolute()
    battery_read = read_bounded_regular_file(
        battery_path, max_bytes=MAX_BATTERY_BYTES, label="MCP eval battery"
    )
    try:
        manifest = BatteryManifest.model_validate(load_strict_json_bytes(battery_read.payload))
    except (ValueError, ValidationError) as exc:
        raise ValueError("invalid MCP eval battery") from exc

    root = battery_path.parent
    bundle_cache: dict[str, tuple[str, StaticTranscriptBundle]] = {}
    transcripts: dict[str, StaticScenarioTranscript] = {}
    for scenario in manifest.scenarios:
        fixture_path = _resolve_under(root, scenario.fixture_path)
        cached = bundle_cache.get(scenario.fixture_path)
        if cached is None:
            fixture_read = read_bounded_regular_file(
                fixture_path,
                max_bytes=MAX_TRANSCRIPT_BUNDLE_BYTES,
                label="MCP static transcript bundle",
            )
            if fixture_read.identity.sha256 != scenario.fixture_sha256:
                raise ValueError(
                    f"fixture digest mismatch for scenario {scenario.scenario_id}"
                )
            try:
                bundle = StaticTranscriptBundle.model_validate(
                    load_strict_json_bytes(fixture_read.payload)
                )
            except (ValueError, ValidationError) as exc:
                raise ValueError("invalid MCP static transcript bundle") from exc
            bundle_cache[scenario.fixture_path] = (scenario.fixture_sha256, bundle)
        else:
            cached_sha256, bundle = cached
            if cached_sha256 != scenario.fixture_sha256:
                raise ValueError("one fixture path cannot declare multiple digests")
        if bundle.split != scenario.split:
            raise ValueError(f"scenario split does not match transcript bundle: {scenario.scenario_id}")
        matches = [item for item in bundle.transcripts if item.scenario_id == scenario.scenario_id]
        if len(matches) != 1:
            raise ValueError(f"scenario requires exactly one static transcript: {scenario.scenario_id}")
        transcript = matches[0]
        if (
            transcript.session_id != scenario.session_id
            or transcript.capture_group_id != scenario.capture_group_id
        ):
            raise ValueError(f"scenario identity does not bind its transcript: {scenario.scenario_id}")
        transcripts[scenario.scenario_id] = transcript

    referenced = set(transcripts)
    available = {
        item.scenario_id
        for _, bundle in bundle_cache.values()
        for item in bundle.transcripts
    }
    if referenced != available:
        raise ValueError("transcript bundles contain unreferenced or missing scenarios")
    return LoadedBattery(
        manifest=manifest,
        battery_sha256=battery_read.identity.sha256,
        transcripts=transcripts,
        fixture_sha256s=tuple(sorted(scenario.fixture_sha256 for scenario in manifest.scenarios)),
    )


def run_battery(
    battery_path: Path,
    *,
    repo_sha: str,
    model_provider: str = "static-fixture",
    model_id: str = "static-tool-calls-v1",
    random_seed: int = 0,
    now: datetime | None = None,
) -> McpEvalRun:
    loaded = load_battery(battery_path)
    started_at = now or datetime.now(timezone.utc)
    reports = [
        score_scenario(scenario, loaded.transcripts[scenario.scenario_id])
        for scenario in loaded.manifest.scenarios
    ]
    aggregate = aggregate_reports(loaded.manifest, reports)
    ended_at = datetime.now(timezone.utc) if now is None else now
    catalog_digest = _canonical_digest(
        {
            "battery_sha256": loaded.battery_sha256,
            "fixture_sha256s": sorted(set(loaded.fixture_sha256s)),
        }
    )
    tool_log_digest = _canonical_digest(
        [
            loaded.transcripts[scenario.scenario_id].model_dump(mode="json")
            for scenario in loaded.manifest.scenarios
        ]
    )
    run_manifest = RunManifest(
        run_id=f"run-{uuid4().hex}",
        battery_id=loaded.manifest.battery_id,
        repo_sha=repo_sha,
        contract_version=loaded.manifest.contract_version,
        fixture_catalog_digest=catalog_digest,
        model_provider=model_provider,
        model_id=model_id,
        prompt_version=loaded.manifest.prompt_version,
        playbook_version=loaded.manifest.playbook_version,
        random_seed=random_seed,
        started_at=started_at,
        ended_at=ended_at,
        start_state={
            "scenario_count": len(loaded.manifest.scenarios),
            "generation_count": sum(
                scenario.split == "generation" for scenario in loaded.manifest.scenarios
            ),
            "holdout_count": sum(
                scenario.split == "holdout" for scenario in loaded.manifest.scenarios
            ),
        },
        end_state={
            "completed_scenarios": len(reports),
            "scored_generation_count": aggregate.scored_generation_count,
            "unscored_holdout_count": aggregate.unscored_holdout_count,
            "split_isolation_verified": True,
        },
        tool_log_digest=tool_log_digest,
    )
    return McpEvalRun(
        run_manifest=run_manifest,
        aggregate=aggregate,
        scenario_reports=reports,
    )


def write_run_artifacts(output_dir: Path, result: McpEvalRun) -> tuple[Path, Path]:
    output_dir = output_dir.absolute()
    output_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = output_dir / "run-manifest.json"
    report_path = output_dir / "metrics-report.json"
    manifest_payload = result.run_manifest.model_dump(mode="json")
    report_payload = {
        "schema_version": 1,
        "artifact_type": "sanmou_mcp_eval_metrics_report",
        "run_id": result.run_manifest.run_id,
        "aggregate": result.aggregate.model_dump(mode="json"),
        "scenario_reports": [
            report.model_dump(mode="json") for report in result.scenario_reports
        ],
        "execution_authority": "none",
        "live_control_used": False,
        "holdout_oracle_accessed": False,
    }
    _write_json_once(manifest_path, manifest_payload)
    _write_json_once(report_path, report_payload)
    return manifest_path, report_path


def _resolve_under(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("fixture path must stay under the battery root")
    candidate = root.joinpath(*pure.parts).absolute()
    if not candidate.is_relative_to(root.absolute()):
        raise ValueError("fixture path escapes the battery root")
    return candidate


def _canonical_digest(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _write_json_once(path: Path, value: Any) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
        "utf-8"
    )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    descriptor = os.open(path, flags, 0o600)
    try:
        offset = 0
        while offset < len(payload):
            offset += os.write(descriptor, payload[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
