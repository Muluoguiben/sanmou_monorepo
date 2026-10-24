"""Recommendation-only harness; optional clients load when explicitly requested.

Importing task contracts or budgets for the model gateway must not initialize
the screenshot/vision or MCP stdio dependency graphs.
"""

from importlib import import_module

__all__ = [
    "DecisionJournal",
    "DecisionWindowResult",
    "DecisionWindowStatus",
    "JsonJournalStore",
    "JsonlToolLog",
    "InProcessMcpClient",
    "McpClient",
    "RecommendationHarness",
    "StopPolicy",
    "StopReason",
    "StdioMcpClient",
    "ToolCallRecord",
]

_EXPORT_MODULES = {
    "DecisionJournal": "journal", "JsonJournalStore": "journal",
    "DecisionWindowResult": "loop", "DecisionWindowStatus": "loop",
    "RecommendationHarness": "loop",
    "JsonlToolLog": "tool_log", "ToolCallRecord": "tool_log",
    "InProcessMcpClient": "contracts", "McpClient": "contracts",
    "StopPolicy": "policy", "StopReason": "policy",
    "StdioMcpClient": "stdio_client",
}


def __getattr__(name: str):
    module = _EXPORT_MODULES.get(name)
    if module is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f"{__name__}.{module}"), name)
    globals()[name] = value
    return value


def __dir__():
    return sorted(set(globals()) | set(__all__))
