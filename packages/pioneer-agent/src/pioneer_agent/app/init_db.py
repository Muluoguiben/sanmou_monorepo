from __future__ import annotations

from pathlib import Path

from pioneer_agent.storage.init_db import initialize_database


def main() -> None:
    project_root = Path(__file__).resolve().parents[3]
    db_path = initialize_database(project_root)
    print(f"Initialized database at: {db_path}")


if __name__ == "__main__":
    main()

