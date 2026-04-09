from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pioneer_agent.core.models import RuntimeState


RUNTIME_STATE_TOP_LEVEL_FIELDS = tuple(RuntimeState.model_fields.keys())
RUNTIME_STATE_TOP_LEVEL_FIELD_SET = set(RUNTIME_STATE_TOP_LEVEL_FIELDS)


@dataclass(slots=True)
class RuntimeStateRecord:
    state: RuntimeState
    metadata: dict[str, Any] = field(default_factory=dict)
    record_index: int | None = None
    source_path: Path | None = None


def extract_state_payload(payload: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    if not isinstance(payload, dict):
        raise ValueError("Runtime state payload must be a JSON object.")

    if "state" in payload and isinstance(payload["state"], dict):
        return dict(payload["state"]), {key: value for key, value in payload.items() if key != "state"}

    if RUNTIME_STATE_TOP_LEVEL_FIELD_SET.intersection(payload.keys()):
        return dict(payload), {}

    raise ValueError("Payload does not contain a RuntimeState object.")


def coerce_runtime_state(payload: Any) -> RuntimeState:
    state_payload, _ = extract_state_payload(payload)
    return RuntimeState(**state_payload)


def load_runtime_state_record(path: Path, index: int = -1) -> RuntimeStateRecord:
    resolved_path = path.resolve()
    suffix = resolved_path.suffix.lower()

    if suffix == ".jsonl":
        lines = [line for line in resolved_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        if not lines:
            raise ValueError(f"No runtime state records found in: {resolved_path}")

        resolved_index = _resolve_index(len(lines), index)
        payload = json.loads(lines[resolved_index])
        state_payload, metadata = extract_state_payload(payload)
        return RuntimeStateRecord(
            state=RuntimeState(**state_payload),
            metadata=metadata,
            record_index=resolved_index,
            source_path=resolved_path,
        )

    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        if not payload:
            raise ValueError(f"No runtime state records found in: {resolved_path}")
        resolved_index = _resolve_index(len(payload), index)
        state_payload, metadata = extract_state_payload(payload[resolved_index])
        return RuntimeStateRecord(
            state=RuntimeState(**state_payload),
            metadata=metadata,
            record_index=resolved_index,
            source_path=resolved_path,
        )

    state_payload, metadata = extract_state_payload(payload)
    return RuntimeStateRecord(
        state=RuntimeState(**state_payload),
        metadata=metadata,
        record_index=None,
        source_path=resolved_path,
    )


def dump_runtime_state_json(state: RuntimeState, *, indent: int = 2) -> str:
    return json.dumps(state.model_dump(mode="json"), ensure_ascii=False, indent=indent)


def write_runtime_state_fixture(state: RuntimeState, output_path: Path) -> Path:
    resolved_output = output_path.resolve()
    resolved_output.parent.mkdir(parents=True, exist_ok=True)
    resolved_output.write_text(dump_runtime_state_json(state) + "\n", encoding="utf-8")
    return resolved_output


def _resolve_index(length: int, index: int) -> int:
    resolved_index = index if index >= 0 else length + index
    if resolved_index < 0 or resolved_index >= length:
        raise IndexError(f"Index {index} is out of range for {length} runtime state records.")
    return resolved_index
