from __future__ import annotations

from pathlib import Path

from sanmou_common.config import ConfigLoader, get_config_dir
from pioneer_agent.perception.sync_service import StateSyncService
from pioneer_agent.runtime.agent_runtime import AgentRuntime
from pioneer_agent.storage.logger import AgentLogger


def build_runtime(
    project_root: Path,
    *,
    sync_input: Path | None = None,
    log_dir: Path | None = None,
) -> AgentRuntime:
    config_loader = ConfigLoader(get_config_dir())
    resolved_log_dir = log_dir or (project_root / "data" / "agent_runs" / "bootstrap_logs")
    resolved_sync_input = sync_input or (project_root / "data" / "perception" / "latest_state.json")
    logger = AgentLogger(resolved_log_dir)
    sync_service = StateSyncService(resolved_sync_input)
    return AgentRuntime(config_loader=config_loader, logger=logger, sync_service=sync_service)
