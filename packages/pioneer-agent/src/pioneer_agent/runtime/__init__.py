"""Public runtime exports without eager cross-layer imports."""

from __future__ import annotations

from importlib import import_module
from typing import Any

_EXPORT_MODULES = {
    "ActionRecommendation": "pioneer_agent.runtime.advisor_loop",
    "AdvisorLoop": "pioneer_agent.runtime.advisor_loop",
    "AdvisorReport": "pioneer_agent.runtime.advisor_loop",
    "build_advisor_report": "pioneer_agent.runtime.advisor_loop",
    "ArchitectureGateDecision": "pioneer_agent.runtime.architecture_gates",
    "ArchitectureGateVerdict": "pioneer_agent.runtime.architecture_gates",
    "AutomationMode": "pioneer_agent.runtime.architecture_gates",
    "AutomationReadiness": "pioneer_agent.runtime.architecture_gates",
    "AutomationReadinessGate": "pioneer_agent.runtime.architecture_gates",
    "LLMJudgeGate": "pioneer_agent.runtime.architecture_gates",
    "validate_explainer_boundary": "pioneer_agent.runtime.architecture_gates",
}


def __getattr__(name: str) -> Any:
    module_name = _EXPORT_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(module_name), name)
    globals()[name] = value
    return value


__all__ = list(_EXPORT_MODULES)
