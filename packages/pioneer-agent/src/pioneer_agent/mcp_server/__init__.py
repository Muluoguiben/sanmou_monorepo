"""Read-only MCP contract for Sanmou game observation and Advisor data."""

from .contracts import (
    CONTRACT_VERSION,
    EXECUTION_AUTHORITY,
    GAME_TOOL_ALLOWLIST,
    GAME_TOOL_ARGUMENTS,
    GAME_TOOL_REQUIRED_ARGUMENTS,
    GAME_TOOL_RESPONSE_MODELS,
    SERVER_NAME,
)
from .service import GameMCPService, ObservedAdvisorCycle

__all__ = [
    "CONTRACT_VERSION",
    "EXECUTION_AUTHORITY",
    "GAME_TOOL_ALLOWLIST",
    "GAME_TOOL_ARGUMENTS",
    "GAME_TOOL_REQUIRED_ARGUMENTS",
    "GAME_TOOL_RESPONSE_MODELS",
    "SERVER_NAME",
    "GameMCPService",
    "ObservedAdvisorCycle",
]
