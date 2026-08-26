"""Read-only MCP contract for Sanmou game observation and Advisor data."""

from .contracts import CONTRACT_VERSION, EXECUTION_AUTHORITY
from .service import GameMCPService, ObservedAdvisorCycle

__all__ = [
    "CONTRACT_VERSION",
    "EXECUTION_AUTHORITY",
    "GameMCPService",
    "ObservedAdvisorCycle",
]
