"""Read-only MCP contract for Sanmou game observation and Advisor data."""

from importlib import import_module

from .contracts import (
    CONTRACT_VERSION,
    EXECUTION_AUTHORITY,
    GAME_TOOL_ALLOWLIST,
    GAME_TOOL_ARGUMENTS,
    GAME_TOOL_REQUIRED_ARGUMENTS,
    GAME_TOOL_RESPONSE_MODELS,
    SERVER_NAME,
)

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


def __getattr__(name: str):
    # The tool catalog is also used by pure task/budget contracts. Loading it
    # must not import the Advisor vision providers or construct the service.
    if name not in {"GameMCPService", "ObservedAdvisorCycle"}:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.service"), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
