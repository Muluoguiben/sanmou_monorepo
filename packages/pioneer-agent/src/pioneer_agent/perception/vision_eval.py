from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from PIL import Image

from pioneer_agent.core.models import RuntimeState
from pioneer_agent.perception.vision_sync import VisionSync


class VisionEvalFixtureError(ValueError):
    """The offline fixture is not integrity- or privacy-safe to replay."""


_CANONICAL_REVIEW_REGISTRY = (
    Path(__file__).resolve().parents[3]
    / "tests"
    / "fixtures"
    / "vision"
    / "real_screenshot_review_registry.json"
)


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
    verified_artifact_count: int = 0

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
        artifacts_approved = bool(self.screenshots) and (
            self.verified_artifact_count == len(self.screenshots)
        )
        return {
            "evaluation_mode": "fixture_payload_replay",
            "image_model_exercised": False,
            "payload_review_status": "not_verified",
            "artifact_review_status": (
                "registry_approved" if artifacts_approved else "not_verified"
            ),
            "screenshot_count": len(self.screenshots),
            "entity_check_count": len(self.entities),
            "verified_artifact_count": self.verified_artifact_count,
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
    schema_version = fixture.get("schema_version")
    if schema_version != 2 or isinstance(schema_version, bool):
        raise VisionEvalFixtureError("vision eval fixtures require schema_version=2")
    source = fixture.get("source")
    if not isinstance(source, Mapping) or source.get("kind") != "real_screenshot_set":
        raise VisionEvalFixtureError(
            "schema v2 requires source.kind=real_screenshot_set"
        )
    screenshots = fixture.get("screenshots")
    if not isinstance(screenshots, list) or not screenshots:
        raise VisionEvalFixtureError("schema v2 requires at least one screenshot")
    fixture_root = path.parent.parent
    review_registry = _load_review_registry()
    state = RuntimeState.model_validate(fixture.get("initial_state") or {})

    screenshot_results: list[VisionScreenshotEvalResult] = []
    verified_artifact_count = 0
    for shot in screenshots:
        if not isinstance(shot, Mapping):
            raise VisionEvalFixtureError("each screenshot must be an object")
        image_path = _fixture_image_path(fixture_root, shot)
        if not image_path.exists():
            raise FileNotFoundError(f"missing screenshot fixture: {image_path}")
        image_bytes = _validate_real_screenshot_artifact(
            image_path, shot, review_registry
        )
        verified_artifact_count += 1

        client = _ReplayVisionClient(shot["payloads"])
        state, summary = VisionSync(client).sync(
            image_bytes,
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
        verified_artifact_count=verified_artifact_count,
    )


def _fixture_image_path(fixture_root: Path, shot: Mapping[str, Any]) -> Path:
    raw_path = shot.get("image")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise VisionEvalFixtureError("screenshot image must be a non-empty relative path")
    root = fixture_root.resolve()
    image_path = (root / raw_path).resolve()
    if not image_path.is_relative_to(root):
        raise VisionEvalFixtureError(
            f"screenshot path escapes fixture root: {raw_path}"
        )
    return image_path


def _load_review_registry() -> Mapping[str, Any]:
    registry_path = _CANONICAL_REVIEW_REGISTRY
    if not registry_path.is_file():
        raise VisionEvalFixtureError(
            f"missing real screenshot review registry: {registry_path}"
        )
    registry = json.loads(registry_path.read_text(encoding="utf-8"))
    if not isinstance(registry, Mapping) or registry.get("schema_version") != 1:
        raise VisionEvalFixtureError("unsupported real screenshot review registry")
    if not isinstance(registry.get("approved"), Mapping) or not isinstance(
        registry.get("denied"), Mapping
    ):
        raise VisionEvalFixtureError("invalid real screenshot review registry")
    return registry


def _validate_real_screenshot_artifact(
    image_path: Path,
    shot: Mapping[str, Any],
    review_registry: Mapping[str, Any],
) -> bytes:
    screenshot_id = str(shot.get("id") or image_path.name)
    artifact = shot.get("artifact")
    if not isinstance(artifact, Mapping):
        raise VisionEvalFixtureError(f"{screenshot_id}: missing artifact review")
    if artifact.get("review_status") != "reviewed":
        raise VisionEvalFixtureError(f"{screenshot_id}: artifact is not reviewed")

    expected_sha = artifact.get("sha256")
    if not isinstance(expected_sha, str) or len(expected_sha) != 64:
        raise VisionEvalFixtureError(f"{screenshot_id}: invalid sha256 metadata")
    image_bytes = image_path.read_bytes()
    actual_sha = hashlib.sha256(image_bytes).hexdigest()
    if actual_sha != expected_sha.lower():
        raise VisionEvalFixtureError(f"{screenshot_id}: screenshot sha256 mismatch")

    denied = review_registry["denied"]
    approved = review_registry["approved"]
    if actual_sha in denied:
        raise VisionEvalFixtureError(
            f"{screenshot_id}: screenshot is denied by the review registry"
        )
    registry_review = approved.get(actual_sha)
    if not isinstance(registry_review, Mapping):
        raise VisionEvalFixtureError(
            f"{screenshot_id}: screenshot is not approved by the review registry"
        )

    with Image.open(BytesIO(image_bytes)) as image:
        actual_size = image.size
    expected_size = (artifact.get("width"), artifact.get("height"))
    if expected_size != actual_size:
        raise VisionEvalFixtureError(
            f"{screenshot_id}: screenshot dimensions mismatch"
        )
    if (registry_review.get("width"), registry_review.get("height")) != actual_size:
        raise VisionEvalFixtureError(
            f"{screenshot_id}: review registry dimensions mismatch"
        )

    privacy = artifact.get("privacy_review")
    if not isinstance(privacy, Mapping):
        raise VisionEvalFixtureError(f"{screenshot_id}: missing privacy review")
    if privacy.get("status") != "approved" or privacy.get(
        "approved_for_repo_storage"
    ) is not True:
        raise VisionEvalFixtureError(f"{screenshot_id}: privacy review not approved")
    for field in (
        "account_identifiers_visible",
        "chat_visible",
        "player_or_alliance_names_visible",
        "payment_data_visible",
        "precise_coordinates_visible",
    ):
        if privacy.get(field) is not False:
            raise VisionEvalFixtureError(
                f"{screenshot_id}: privacy field {field} is not explicitly false"
            )
    registry_privacy = registry_review.get("privacy_review")
    if not isinstance(registry_privacy, Mapping):
        raise VisionEvalFixtureError(
            f"{screenshot_id}: registry privacy review is missing"
        )
    for field in (
        "account_identifiers_visible",
        "chat_visible",
        "player_or_alliance_names_visible",
        "payment_data_visible",
        "precise_coordinates_visible",
    ):
        if registry_privacy.get(field) is not False:
            raise VisionEvalFixtureError(
                f"{screenshot_id}: registry privacy field {field} is not false"
            )
        if privacy.get(field) != registry_privacy.get(field):
            raise VisionEvalFixtureError(
                f"{screenshot_id}: fixture privacy review disagrees with registry"
            )
    for field in ("status", "approved_for_repo_storage", "reviewed_by", "reviewed_at"):
        if privacy.get(field) != registry_privacy.get(field):
            raise VisionEvalFixtureError(
                f"{screenshot_id}: fixture privacy metadata disagrees with registry"
            )
    if not isinstance(privacy.get("reviewed_by"), str) or not privacy[
        "reviewed_by"
    ].strip():
        raise VisionEvalFixtureError(f"{screenshot_id}: missing privacy reviewer")
    reviewed_at = privacy.get("reviewed_at")
    if not isinstance(reviewed_at, str):
        raise VisionEvalFixtureError(f"{screenshot_id}: missing privacy review time")
    try:
        parsed_reviewed_at = datetime.fromisoformat(reviewed_at)
    except ValueError as exc:
        raise VisionEvalFixtureError(
            f"{screenshot_id}: invalid privacy review time"
        ) from exc
    if parsed_reviewed_at.tzinfo is None or parsed_reviewed_at.utcoffset() is None:
        raise VisionEvalFixtureError(
            f"{screenshot_id}: privacy review time must include timezone"
        )
    return image_bytes


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
