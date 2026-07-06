"""Runbook YAML loading and RuntimeState -> metrics extraction."""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Mapping

import yaml

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.runbook.models import OpeningRunbook

logger = logging.getLogger(__name__)

DEFAULT_OPENING_RUNBOOK_ENV = "SANMOU_OPENING_RUNBOOK_PATH"
# Ships as package data (pyproject packages pioneer_agent/config/*.yaml), so the
# default resolves inside both editable and wheel installs.
DEFAULT_OPENING_RUNBOOK_PATH = (
    Path(__file__).resolve().parents[1] / "config" / "opening_runbook_s15.yaml"
)


def load_runbook(path: Path) -> OpeningRunbook:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        data = json.loads(text)
    else:
        data = yaml.safe_load(text)
    return OpeningRunbook.model_validate(data)


def load_default_opening_runbook(path: Path | None = None) -> OpeningRunbook | None:
    runbook_path = path or Path(
        os.environ.get(DEFAULT_OPENING_RUNBOOK_ENV, DEFAULT_OPENING_RUNBOOK_PATH)
    )
    if not runbook_path.exists():
        logger.warning(
            "opening runbook not found at %s (set %s to override)",
            runbook_path,
            DEFAULT_OPENING_RUNBOOK_ENV,
        )
        return None
    return load_runbook(runbook_path)


def metrics_from_runtime_state(
    state: RuntimeState,
    *,
    extra_metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Merge the full state payload (for dotted-path conditions) with computed
    flat metrics. Callers own game-specific counters the deriver does not
    produce yet (e.g. owned-land counts) and pass them via extra_metrics.
    """
    payload = state.model_dump(mode="json")
    computed: dict[str, Any] = {}

    avg_level = state.main_lineup.get("avg_level")
    if avg_level is not None:
        computed["main_team_avg_level"] = avg_level

    phase_tag = state.global_state.get("phase_tag")
    if phase_tag is not None:
        computed["phase_tag"] = phase_tag

    hours = state.global_state.get("hours_since_server_open")
    if hours is not None:
        computed["hours_since_server_open"] = hours

    host_team_id = state.main_lineup.get("current_host_team_id")
    if host_team_id is not None:
        for container in state.team_containers:
            if container.get("team_id") == host_team_id:
                if container.get("soldiers") is not None:
                    computed["host_team_soldiers"] = container["soldiers"]
                if container.get("container_stamina") is not None:
                    computed["host_team_stamina"] = container["container_stamina"]
                break

    payload.update(computed)
    if extra_metrics:
        payload.update(extra_metrics)
    return payload
