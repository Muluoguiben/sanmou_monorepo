from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.vision_sync import VisionSync


@dataclass(frozen=True)
class VisionScreenshotEvalResult:
    screenshot_id: str
    expected_page_type: str | None
    actual_page_type: str | None
    expected_domains: tuple[str, ...]
    actual_domains: tuple[str, ...]

    @property
    def page_correct(self) -> bool:
        return self.expected_page_type == self.actual_page_type

    @property
    def domains_correct(self) -> bool:
        return self.expected_domains == self.actual_domains


@dataclass(frozen=True)
class VisionEntityEvalResult:
    path: str
    expected: Any
    actual: Any
    found: bool

    @property
    def correct(self) -> bool:
        return self.found and self.actual == self.expected


@dataclass(frozen=True)
class VisionEvalSummary:
    screenshots: tuple[VisionScreenshotEvalResult, ...]
    entities: tuple[VisionEntityEvalResult, ...]

    @property
    def page_accuracy(self) -> float:
        return _accuracy(item.page_correct for item in self.screenshots)

    @property
    def domain_accuracy(self) -> float:
        return _accuracy(item.domains_correct for item in self.screenshots)

    @property
    def entity_accuracy(self) -> float:
        return _accuracy(item.correct for item in self.entities)

    def to_report(self) -> dict[str, Any]:
        return {
            "screenshot_count": len(self.screenshots),
            "entity_check_count": len(self.entities),
            "page_accuracy": self.page_accuracy,
            "domain_accuracy": self.domain_accuracy,
            "entity_accuracy": self.entity_accuracy,
            "failed_screenshots": [
                item.screenshot_id
                for item in self.screenshots
                if not item.page_correct or not item.domains_correct
            ],
            "failed_entities": [item.path for item in self.entities if not item.correct],
        }


def run_vision_eval_fixture(path: Path) -> VisionEvalSummary:
    fixture = json.loads(path.read_text(encoding="utf-8"))
    fixture_root = path.parent.parent
    state = RuntimeState.model_validate(fixture.get("initial_state") or {})

    screenshot_results: list[VisionScreenshotEvalResult] = []
    for shot in fixture.get("screenshots", []):
        image_path = fixture_root / shot["image"]
        if not image_path.exists():
            raise FileNotFoundError(f"missing screenshot fixture: {image_path}")

        client = _ReplayVisionClient(shot["payloads"])
        state, summary = VisionSync(client).sync(
            image_path,
            state=state,
            captured_at=datetime.fromisoformat(shot["captured_at"]),
        )
        screenshot_results.append(
            VisionScreenshotEvalResult(
                screenshot_id=str(shot["id"]),
                expected_page_type=_expected_page_type(shot),
                actual_page_type=summary.page_type,
                expected_domains=tuple(shot["expected_domains"]),
                actual_domains=tuple(summary.domains_run),
            )
        )

    state_json = state.model_dump(mode="json")
    entity_results = tuple(
        _check_entity(state_json, item)
        for item in fixture.get("expected_state_checks", [])
    )
    return VisionEvalSummary(
        screenshots=tuple(screenshot_results),
        entities=entity_results,
    )


@dataclass
class _StubResult:
    data: dict[str, Any]
    model: str = "fixture"
    prompt_tokens: int = 0
    output_tokens: int = 0
    elapsed_s: float = 0.0


class _ReplayVisionClient:
    def __init__(self, payloads: list[dict[str, Any]]) -> None:
        self._payloads = payloads
        self.calls = 0

    def extract(self, image, instruction, response_schema, **kwargs):  # noqa: ANN001
        if self.calls >= len(self._payloads):
            raise AssertionError("unexpected extra vision extraction")
        payload = self._payloads[self.calls]
        self.calls += 1
        return _StubResult(data=dict(payload["data"]))


def _expected_page_type(shot: dict[str, Any]) -> str | None:
    for payload in shot.get("payloads", []):
        if payload.get("domain") == "resource_bar":
            page = payload.get("data", {}).get("page_type")
            return str(page) if page is not None else None
    return None


def _check_entity(state: dict[str, Any], check: dict[str, Any]) -> VisionEntityEvalResult:
    found, actual = _get_path(state, str(check["path"]))
    return VisionEntityEvalResult(
        path=str(check["path"]),
        expected=check.get("expected"),
        actual=actual,
        found=found,
    )


def _get_path(state: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = state
    for part in path.split("."):
        if isinstance(current, Mapping):
            if part not in current:
                return False, None
            current = current[part]
            continue
        if _is_sequence(current) and part.isdigit():
            index = int(part)
            if index >= len(current):
                return False, None
            current = current[index]
            continue
        return False, None
    return True, current


def _is_sequence(value: Any) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray))


def _accuracy(values: Iterable[bool]) -> float:
    items = list(values)
    total = len(items)
    if total == 0:
        return 0.0
    return sum(1 for value in items if value) / total
