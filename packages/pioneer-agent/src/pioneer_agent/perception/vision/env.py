from __future__ import annotations

import os
from pathlib import Path


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_vision_env() -> None:
    """Load local vision credentials without overriding explicit environment.

    Pioneer-agent can use its own `.env`, but the current monorepo convention
    keeps sub2api/OpenAI keys in `packages/qa-agent/.env`, so load that sibling
    file as a fallback.
    """
    package_root = Path(__file__).resolve().parents[4]
    monorepo_root = package_root.parents[1]
    load_dotenv(package_root / ".env")
    load_dotenv(monorepo_root / "packages" / "qa-agent" / ".env")
