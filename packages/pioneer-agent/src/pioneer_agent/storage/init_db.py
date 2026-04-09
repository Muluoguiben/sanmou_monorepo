from __future__ import annotations

from pathlib import Path

from pioneer_agent.storage.db import connect


def initialize_database(project_root: Path) -> Path:
    db_dir = project_root / "data"
    db_dir.mkdir(parents=True, exist_ok=True)
    db_path = db_dir / "pioneer_agent.db"
    schema_path = project_root / "src" / "pioneer_agent" / "storage" / "schema.sql"

    connection = connect(db_path)
    try:
        schema = schema_path.read_text(encoding="utf-8")
        connection.executescript(schema)
        connection.commit()
    finally:
        connection.close()

    return db_path

