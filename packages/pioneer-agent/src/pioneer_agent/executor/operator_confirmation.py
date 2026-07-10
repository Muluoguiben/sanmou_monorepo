"""One-shot operator confirmations for live final mutating clicks."""

from __future__ import annotations

import json
import math
import os
import time
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Iterator, Literal, Protocol
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator, model_validator

from pioneer_agent.core.enums import ActionType
from pioneer_agent.core.models import CandidateAction, ObservationSnapshot
from pioneer_agent.executor.semantic_frame_guard import SemanticFrameGuard


class OperatorConfirmationError(ValueError):
    """A confirmation is missing, malformed, stale, ambiguous, or already used."""


class OperatorConfirmationUnavailable(OperatorConfirmationError):
    """No matching active confirmation exists yet."""


class OperatorConfirmationStoreBusy(OperatorConfirmationError):
    """The append-only store is currently locked by another process."""


class OperatorConfirmationRequest(BaseModel):
    """Exact terminal-observation binding shown to the human operator."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    scope: Literal["final_mutating_click"] = "final_mutating_click"
    action_id: str = Field(min_length=1)
    action_type: ActionType
    target_key: str = Field(min_length=1)
    target_identity: dict[str, Any]
    observation_id: str = Field(min_length=1)
    frame_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_frame_guard: SemanticFrameGuard
    observation_captured_at: datetime
    requested_at: datetime
    request_expires_at: datetime
    confirmation_ttl_seconds: float = Field(gt=0, le=30)
    confirmation_store_path: str = Field(min_length=1)

    @field_validator(
        "observation_captured_at",
        "requested_at",
        "request_expires_at",
    )
    @classmethod
    def _require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("operator confirmation request timestamps must be timezone-aware")
        return value

    @field_validator("confirmation_ttl_seconds")
    @classmethod
    def _require_finite_ttl(cls, value: float) -> float:
        if not math.isfinite(value):
            raise ValueError("operator confirmation request TTL must be finite")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> OperatorConfirmationRequest:
        if self.requested_at < self.observation_captured_at:
            raise ValueError("operator confirmation request cannot predate its observation")
        if self.request_expires_at <= self.requested_at:
            raise ValueError("operator confirmation request expiry must follow the request")
        _validate_target_identity(self.action_type, self.target_identity)
        return self


class OperatorConfirmation(BaseModel):
    schema_version: Literal[1] = 1
    confirmation_id: str = Field(min_length=1)
    request_id: str | None = Field(default=None, min_length=1)
    scope: Literal["final_mutating_click"] = "final_mutating_click"
    action_id: str = Field(min_length=1)
    action_type: ActionType
    target_key: str = Field(min_length=1)
    target_identity: dict[str, Any]
    observation_id: str = Field(min_length=1)
    frame_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    semantic_frame_guard: SemanticFrameGuard | None = None
    observation_captured_at: datetime
    confirmed_at: datetime
    expires_at: datetime

    @field_validator(
        "observation_captured_at",
        "confirmed_at",
        "expires_at",
    )
    @classmethod
    def _require_aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("operator confirmation timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def _validate_contract(self) -> OperatorConfirmation:
        if self.confirmed_at < self.observation_captured_at:
            raise ValueError("operator confirmation cannot predate its observation")
        if self.expires_at <= self.confirmed_at:
            raise ValueError("operator confirmation expiry must follow confirmation")
        _validate_target_identity(self.action_type, self.target_identity)
        return self


class OperatorConfirmationReceipt(BaseModel):
    confirmation: OperatorConfirmation
    consumed_at: datetime
    dispatch_at: datetime

    @model_validator(mode="after")
    def _validate_ordering(self) -> OperatorConfirmationReceipt:
        for value in (self.consumed_at, self.dispatch_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("confirmation receipt timestamps must be timezone-aware")
        if self.dispatch_at <= self.confirmation.confirmed_at:
            raise ValueError("dispatch_at must be strictly later than confirmed_at")
        return self

    def to_summary(self) -> dict[str, Any]:
        confirmation = self.confirmation
        return {
            "confirmed": True,
            "requires_operator_confirmation": True,
            "scope": confirmation.scope,
            "confirmation_id": confirmation.confirmation_id,
            "request_id": confirmation.request_id,
            "action_id": confirmation.action_id,
            "action_type": confirmation.action_type.value,
            "target_key": confirmation.target_key,
            "target_identity": dict(confirmation.target_identity),
            "observation_id": confirmation.observation_id,
            "frame_sha256": confirmation.frame_sha256,
            "semantic_frame_guard": (
                confirmation.semantic_frame_guard.model_dump(mode="json")
                if confirmation.semantic_frame_guard is not None
                else None
            ),
            "observation_captured_at": confirmation.observation_captured_at.isoformat(),
            "confirmed_at": confirmation.confirmed_at.isoformat(),
            "expires_at": confirmation.expires_at.isoformat(),
            "consumed_at": self.consumed_at.isoformat(),
            "dispatch_at": self.dispatch_at.isoformat(),
        }


class OperatorConfirmationProvider(Protocol):
    def consume_for_dispatch(
        self,
        *,
        action: CandidateAction,
        observation: ObservationSnapshot,
        target_key: str,
        semantic_frame_guard: SemanticFrameGuard,
        now: datetime | None = None,
    ) -> OperatorConfirmationReceipt: ...


class JsonlOperatorConfirmationStore:
    """Append-only grant/consume channel intended for a separate operator CLI.

    A sidecar exclusive lock serializes read-plus-consume. A stale lock blocks
    dispatch until an operator removes it; it is never auto-bypassed.
    """

    def __init__(self, path: Path, *, max_ttl_seconds: float = 30.0) -> None:
        if (
            isinstance(max_ttl_seconds, bool)
            or not isinstance(max_ttl_seconds, (int, float))
            or not math.isfinite(float(max_ttl_seconds))
            or max_ttl_seconds <= 0
        ):
            raise ValueError("max_ttl_seconds must be finite and positive")
        self.path = path
        self.lock_path = path.with_suffix(path.suffix + ".lock")
        self.max_ttl_seconds = float(max_ttl_seconds)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append_grant(self, confirmation: OperatorConfirmation) -> None:
        confirmation = OperatorConfirmation.model_validate(
            confirmation.model_dump(mode="python")
        )
        if (
            confirmation.expires_at - confirmation.confirmed_at
        ).total_seconds() > self.max_ttl_seconds:
            raise OperatorConfirmationError(
                "operator confirmation TTL exceeds the configured maximum"
            )
        with self._exclusive_lock():
            grants, _ = self._read_records()
            if confirmation.confirmation_id in grants:
                raise OperatorConfirmationError("duplicate operator confirmation id")
            self._append_record(
                {
                    "record_type": "grant",
                    **confirmation.model_dump(mode="json"),
                }
            )

    def consume_for_dispatch(
        self,
        *,
        action: CandidateAction,
        observation: ObservationSnapshot,
        target_key: str,
        semantic_frame_guard: SemanticFrameGuard | None = None,
        now: datetime | None = None,
        request_id: str | None = None,
        confirmed_not_before: datetime | None = None,
    ) -> OperatorConfirmationReceipt:
        checked_at = _aware_utc(now or datetime.now(UTC), field="now")
        if confirmed_not_before is not None:
            confirmed_not_before = _aware_utc(
                confirmed_not_before,
                field="confirmed_not_before",
            )
        if observation.captured_at.tzinfo is None or observation.captured_at.utcoffset() is None:
            raise OperatorConfirmationError("dispatch observation timestamp must be aware")
        expected_identity = target_identity_for_action(action)

        with self._exclusive_lock():
            grants, consumed = self._read_records()
            candidates: list[OperatorConfirmation] = []
            for confirmation in grants.values():
                if confirmation.confirmation_id in consumed:
                    continue
                if request_id is not None and confirmation.request_id != request_id:
                    continue
                if (
                    confirmed_not_before is not None
                    and confirmation.confirmed_at < confirmed_not_before
                ):
                    continue
                if confirmation.action_id != action.action_id:
                    continue
                if confirmation.action_type != action.action_type:
                    continue
                if confirmation.target_key != target_key:
                    continue
                if confirmation.target_identity != expected_identity:
                    continue
                if confirmation.observation_id != observation.observation_id:
                    continue
                if confirmation.frame_sha256 != observation.frame_sha256:
                    continue
                if (
                    semantic_frame_guard is not None
                    and confirmation.semantic_frame_guard != semantic_frame_guard
                ):
                    continue
                if confirmation.observation_captured_at != observation.captured_at:
                    continue
                ttl = (
                    confirmation.expires_at - confirmation.confirmed_at
                ).total_seconds()
                if ttl > self.max_ttl_seconds:
                    continue
                if not (confirmation.confirmed_at <= checked_at < confirmation.expires_at):
                    continue
                candidates.append(confirmation)

            if not candidates:
                raise OperatorConfirmationUnavailable(
                    "no active operator confirmation is bound to the dispatch"
                )
            if len(candidates) != 1:
                raise OperatorConfirmationError(
                    "multiple active operator confirmations are bound to the dispatch"
                )

            confirmation = candidates[0]
            dispatch_at = max(
                checked_at,
                confirmation.confirmed_at + timedelta(microseconds=1),
            )
            if dispatch_at >= confirmation.expires_at:
                raise OperatorConfirmationError("operator confirmation expired before dispatch")
            receipt = OperatorConfirmationReceipt(
                confirmation=confirmation,
                consumed_at=dispatch_at,
                dispatch_at=dispatch_at,
            )
            self._append_record(
                {
                    "record_type": "consume",
                    "schema_version": 1,
                    "confirmation_id": confirmation.confirmation_id,
                    "request_id": confirmation.request_id,
                    "action_id": action.action_id,
                    "action_type": action.action_type.value,
                    "observation_id": observation.observation_id,
                    "frame_sha256": observation.frame_sha256,
                    "semantic_frame_guard": (
                        semantic_frame_guard.model_dump(mode="json")
                        if semantic_frame_guard is not None
                        else None
                    ),
                    "consumed_at": receipt.consumed_at.isoformat(),
                    "dispatch_at": receipt.dispatch_at.isoformat(),
                }
            )
            return receipt

    def _read_records(
        self,
    ) -> tuple[dict[str, OperatorConfirmation], set[str]]:
        if not self.path.exists():
            return {}, set()
        grants: dict[str, OperatorConfirmation] = {}
        consumed: set[str] = set()
        with self.path.open("r", encoding="utf-8") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise OperatorConfirmationError(
                        f"invalid confirmation JSONL at line {line_number}"
                    ) from exc
                if not isinstance(payload, dict):
                    raise OperatorConfirmationError(
                        f"invalid confirmation record at line {line_number}"
                    )
                record_type = payload.get("record_type")
                if record_type == "grant":
                    confirmation = OperatorConfirmation.model_validate(payload)
                    if confirmation.confirmation_id in grants:
                        raise OperatorConfirmationError(
                            "duplicate operator confirmation id"
                        )
                    grants[confirmation.confirmation_id] = confirmation
                    continue
                if record_type == "consume":
                    confirmation_id = payload.get("confirmation_id")
                    if not isinstance(confirmation_id, str) or not confirmation_id:
                        raise OperatorConfirmationError(
                            f"invalid consume record at line {line_number}"
                        )
                    if confirmation_id not in grants or confirmation_id in consumed:
                        raise OperatorConfirmationError(
                            "confirmation consume record is orphaned or duplicated"
                        )
                    grant = grants[confirmation_id]
                    consumed_at = _aware_datetime(
                        payload.get("consumed_at"),
                        field="consumed_at",
                    )
                    dispatch_at = _aware_datetime(
                        payload.get("dispatch_at"),
                        field="dispatch_at",
                    )
                    expected_fields = {
                        "request_id": grant.request_id,
                        "action_id": grant.action_id,
                        "action_type": grant.action_type.value,
                        "observation_id": grant.observation_id,
                        "frame_sha256": grant.frame_sha256,
                    }
                    if any(
                        payload.get(field_name) != expected
                        for field_name, expected in expected_fields.items()
                    ):
                        raise OperatorConfirmationError(
                            "confirmation consume record does not match its grant"
                        )
                    if (
                        dispatch_at <= grant.confirmed_at
                        or dispatch_at < consumed_at
                        or dispatch_at >= grant.expires_at
                    ):
                        raise OperatorConfirmationError(
                            "confirmation consume timestamps are out of order"
                        )
                    consumed.add(confirmation_id)
                    continue
                raise OperatorConfirmationError(
                    f"unknown confirmation record type at line {line_number}"
                )
        return grants, consumed

    def _append_record(self, payload: dict[str, Any]) -> None:
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())

    @contextmanager
    def _exclusive_lock(self) -> Iterator[None]:
        try:
            descriptor = os.open(
                self.lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise OperatorConfirmationStoreBusy(
                "operator confirmation store is locked"
            ) from exc
        try:
            os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
            yield
        finally:
            os.close(descriptor)
            self.lock_path.unlink(missing_ok=True)


class WaitingOperatorConfirmationProvider:
    """Publish an exact request, then wait briefly for an external one-shot grant.

    This provider never creates a grant. The only success path is a matching
    record appended by the separate operator CLI after the request exists.
    """

    def __init__(
        self,
        store: JsonlOperatorConfirmationStore,
        request_path: Path,
        *,
        wait_timeout_seconds: float = 15.0,
        poll_interval_seconds: float = 0.2,
        confirmation_ttl_seconds: float = 10.0,
        max_observation_age_seconds: float = 30.0,
        abort_if: Callable[[], bool] | None = None,
        clock: Callable[[], datetime] | None = None,
        sleeper: Callable[[float], None] | None = None,
    ) -> None:
        for field, value in (
            ("wait_timeout_seconds", wait_timeout_seconds),
            ("poll_interval_seconds", poll_interval_seconds),
            ("confirmation_ttl_seconds", confirmation_ttl_seconds),
            ("max_observation_age_seconds", max_observation_age_seconds),
        ):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or value <= 0
            ):
                raise ValueError(f"{field} must be finite and positive")
        if wait_timeout_seconds > max_observation_age_seconds:
            raise ValueError(
                "operator confirmation wait cannot exceed the observation age limit"
            )
        if confirmation_ttl_seconds > store.max_ttl_seconds:
            raise ValueError(
                "operator confirmation TTL exceeds the store maximum"
            )
        if confirmation_ttl_seconds > 30:
            raise ValueError("operator confirmation TTL cannot exceed 30 seconds")
        self.store = store
        self.request_path = request_path
        self.request_lock_path = request_path.with_suffix(request_path.suffix + ".lock")
        self.wait_timeout_seconds = float(wait_timeout_seconds)
        self.poll_interval_seconds = float(poll_interval_seconds)
        self.confirmation_ttl_seconds = float(confirmation_ttl_seconds)
        self.max_observation_age_seconds = float(max_observation_age_seconds)
        self.abort_if = abort_if or (lambda: False)
        self.clock = clock or (lambda: datetime.now(UTC))
        self.sleeper = sleeper or time.sleep
        self.request_path.parent.mkdir(parents=True, exist_ok=True)

    def consume_for_dispatch(
        self,
        *,
        action: CandidateAction,
        observation: ObservationSnapshot,
        target_key: str,
        semantic_frame_guard: SemanticFrameGuard,
        now: datetime | None = None,
    ) -> OperatorConfirmationReceipt:
        if now is not None:
            raise OperatorConfirmationError(
                "waiting confirmation provider does not accept a fixed dispatch time"
            )
        requested_at = _aware_utc(self.clock(), field="requested_at")
        captured_at = _aware_utc(
            observation.captured_at,
            field="observation_captured_at",
        )
        request_expires_at = min(
            requested_at + timedelta(seconds=self.wait_timeout_seconds),
            captured_at + timedelta(seconds=self.max_observation_age_seconds),
        )
        if request_expires_at <= requested_at:
            raise OperatorConfirmationError(
                "terminal observation is already too old for operator confirmation"
            )
        request = OperatorConfirmationRequest(
            request_id=uuid4().hex,
            action_id=action.action_id,
            action_type=action.action_type,
            target_key=target_key,
            target_identity=target_identity_for_action(action),
            observation_id=observation.observation_id,
            frame_sha256=observation.frame_sha256,
            semantic_frame_guard=semantic_frame_guard,
            observation_captured_at=observation.captured_at,
            requested_at=requested_at,
            request_expires_at=request_expires_at,
            confirmation_ttl_seconds=self.confirmation_ttl_seconds,
            confirmation_store_path=str(self.store.path.resolve()),
        )

        with self._request_session(request):
            while True:
                if self.abort_if():
                    raise OperatorConfirmationError(
                        "operator confirmation wait aborted by kill switch"
                    )
                checked_at = _aware_utc(self.clock(), field="now")
                if checked_at >= request.request_expires_at:
                    raise OperatorConfirmationError(
                        "operator confirmation request timed out"
                    )
                try:
                    receipt = self.store.consume_for_dispatch(
                        action=action,
                        observation=observation,
                        target_key=target_key,
                        semantic_frame_guard=semantic_frame_guard,
                        now=checked_at,
                        request_id=request.request_id,
                        confirmed_not_before=request.requested_at,
                    )
                except (
                    OperatorConfirmationUnavailable,
                    OperatorConfirmationStoreBusy,
                ):
                    remaining = (
                        request.request_expires_at - checked_at
                    ).total_seconds()
                    self.sleeper(min(self.poll_interval_seconds, remaining))
                    continue
                if self.abort_if():
                    raise OperatorConfirmationError(
                        "operator confirmation wait aborted by kill switch"
                    )
                return receipt

    @contextmanager
    def _request_session(
        self,
        request: OperatorConfirmationRequest,
    ) -> Iterator[None]:
        try:
            descriptor = os.open(
                self.request_lock_path,
                os.O_CREAT | os.O_EXCL | os.O_WRONLY,
                0o600,
            )
        except FileExistsError as exc:
            raise OperatorConfirmationError(
                "operator confirmation request channel is locked"
            ) from exc
        try:
            os.write(descriptor, f"pid={os.getpid()}\n".encode("ascii"))
            self._publish_request(request)
            yield
        finally:
            self._retire_request(request.request_id)
            os.close(descriptor)
            self.request_lock_path.unlink(missing_ok=True)

    def _publish_request(self, request: OperatorConfirmationRequest) -> None:
        if self.request_path.exists():
            existing = load_operator_confirmation_request(self.request_path)
            if existing.request_expires_at > request.requested_at:
                raise OperatorConfirmationError(
                    "an active operator confirmation request already exists"
                )
        temporary = self.request_path.with_name(
            f".{self.request_path.name}.{uuid4().hex}.tmp"
        )
        try:
            with temporary.open("x", encoding="utf-8") as handle:
                json.dump(
                    request.model_dump(mode="json"),
                    handle,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, self.request_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _retire_request(self, request_id: str) -> None:
        if not self.request_path.exists():
            return
        try:
            current = load_operator_confirmation_request(self.request_path)
        except OperatorConfirmationError:
            return
        if current.request_id == request_id:
            self.request_path.unlink(missing_ok=True)


def load_operator_confirmation_request(path: Path) -> OperatorConfirmationRequest:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise OperatorConfirmationError(
            "operator confirmation request does not exist"
        ) from exc
    except json.JSONDecodeError as exc:
        raise OperatorConfirmationError(
            "operator confirmation request is not valid JSON"
        ) from exc
    try:
        return OperatorConfirmationRequest.model_validate(payload)
    except (TypeError, ValueError) as exc:
        raise OperatorConfirmationError(
            "operator confirmation request is invalid"
        ) from exc


def grant_operator_confirmation(
    request: OperatorConfirmationRequest,
    *,
    confirmed_at: datetime | None = None,
    confirmation_id: str | None = None,
) -> OperatorConfirmation:
    checked_at = _aware_utc(confirmed_at or datetime.now(UTC), field="confirmed_at")
    if checked_at < request.requested_at:
        raise OperatorConfirmationError(
            "operator confirmation cannot predate its request"
        )
    if checked_at >= request.request_expires_at:
        raise OperatorConfirmationError(
            "operator confirmation request has expired"
        )
    expires_at = min(
        checked_at + timedelta(seconds=request.confirmation_ttl_seconds),
        request.request_expires_at,
    )
    return OperatorConfirmation(
        confirmation_id=confirmation_id or uuid4().hex,
        request_id=request.request_id,
        action_id=request.action_id,
        action_type=request.action_type,
        target_key=request.target_key,
        target_identity=dict(request.target_identity),
        observation_id=request.observation_id,
        frame_sha256=request.frame_sha256,
        semantic_frame_guard=request.semantic_frame_guard,
        observation_captured_at=request.observation_captured_at,
        confirmed_at=checked_at,
        expires_at=expires_at,
    )


def target_identity_for_action(action: CandidateAction) -> dict[str, Any]:
    params = action.params
    if action.action_type == ActionType.CLAIM_CHAPTER_REWARD:
        identity = {"chapter_id": params.get("chapter_id")}
    elif action.action_type == ActionType.RECRUIT_SOLDIERS:
        identity = {"team_id": params.get("team_id")}
    elif action.action_type == ActionType.UPGRADE_BUILDING:
        identity = {
            "building_name": params.get("building_name"),
            "current_level": params.get("current_level"),
            "target_level": params.get("target_level"),
        }
    else:
        raise OperatorConfirmationError(
            f"operator confirmation is unsupported for {action.action_type.value}"
        )
    _validate_target_identity(action.action_type, identity)
    return identity


def validate_confirmation_receipt(
    receipt: OperatorConfirmationReceipt,
    *,
    action: CandidateAction,
    observation: ObservationSnapshot,
    target_key: str,
    semantic_frame_guard: SemanticFrameGuard | None = None,
) -> None:
    if not isinstance(receipt, OperatorConfirmationReceipt):
        raise OperatorConfirmationError(
            "operator confirmation provider returned an invalid receipt"
        )
    confirmation = receipt.confirmation
    expected_identity = target_identity_for_action(action)
    mismatched = (
        confirmation.action_id != action.action_id
        or confirmation.action_type != action.action_type
        or confirmation.target_key != target_key
        or confirmation.target_identity != expected_identity
        or confirmation.observation_id != observation.observation_id
        or confirmation.frame_sha256 != observation.frame_sha256
        or (
            semantic_frame_guard is not None
            and confirmation.semantic_frame_guard != semantic_frame_guard
        )
        or confirmation.observation_captured_at != observation.captured_at
    )
    if mismatched:
        raise OperatorConfirmationError(
            "operator confirmation receipt does not match the dispatch"
        )
    if receipt.dispatch_at <= confirmation.confirmed_at:
        raise OperatorConfirmationError(
            "operator confirmation receipt has invalid timestamp ordering"
        )


def _validate_target_identity(
    action_type: ActionType,
    identity: dict[str, Any],
) -> None:
    if action_type == ActionType.CLAIM_CHAPTER_REWARD:
        valid = (
            set(identity) == {"chapter_id"}
            and isinstance(identity.get("chapter_id"), int)
            and not isinstance(identity.get("chapter_id"), bool)
            and identity["chapter_id"] > 0
        )
    elif action_type == ActionType.RECRUIT_SOLDIERS:
        valid = (
            set(identity) == {"team_id"}
            and isinstance(identity.get("team_id"), str)
            and bool(identity["team_id"].strip())
        )
    elif action_type == ActionType.UPGRADE_BUILDING:
        current = identity.get("current_level")
        target = identity.get("target_level")
        valid = (
            set(identity) == {"building_name", "current_level", "target_level"}
            and isinstance(identity.get("building_name"), str)
            and bool(identity["building_name"].strip())
            and isinstance(current, int)
            and not isinstance(current, bool)
            and current >= 0
            and isinstance(target, int)
            and not isinstance(target, bool)
            and target == current + 1
        )
    else:
        valid = False
    if not valid:
        raise OperatorConfirmationError(
            f"invalid target identity for {action_type.value}"
        )


def _aware_datetime(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str):
        raise OperatorConfirmationError(f"{field} must be an aware ISO-8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise OperatorConfirmationError(
            f"{field} must be an aware ISO-8601 timestamp"
        ) from exc
    return _aware_utc(parsed, field=field)


def _aware_utc(value: datetime, *, field: str) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise OperatorConfirmationError(f"{field} must be timezone-aware")
    return value.astimezone(UTC)
