"""Read-only MCP contract for Sanmou game observation and Advisor data."""

from .contracts import (
    CONTRACT_VERSION,
    EXECUTION_AUTHORITY,
    SERVER_NAME,
    TOOL_ALLOWLIST,
    TOOL_ARGUMENTS,
)
from .service import GameMCPService, ObservedAdvisorCycle

__all__ = [
    "CONTRACT_VERSION",
    "EXECUTION_AUTHORITY",
    "SERVER_NAME",
    "TOOL_ALLOWLIST",
    "TOOL_ARGUMENTS",
    "GameMCPService",
    "ObservedAdvisorCycle",
]
