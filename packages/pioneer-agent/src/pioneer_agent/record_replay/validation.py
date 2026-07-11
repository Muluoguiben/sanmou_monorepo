"""Dependency-free validation shared by WSL and standalone Windows entrypoints."""
from __future__ import annotations

import unicodedata


def validate_workflow_name(value: str) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 120:
        raise ValueError("workflow_name must contain between 1 and 120 characters")
    if value.strip() != value or not value:
        raise ValueError("workflow_name must be trimmed and non-empty")
    if len(value.splitlines()) != 1 or any(
        unicodedata.category(character).startswith("C") for character in value
    ):
        raise ValueError("workflow_name cannot be multiline or contain control characters")
    return value
