"""Budgeted proposal-only service boundary; no game dispatch and no implicit retry.

The transport owns authenticated service metadata. Model-generated JSON never
supplies the manifest, invocation identity, usage, or tool side-effect classes.
This adapter is independent of the v1 TaskRunner (which owns its own budget).
"""
from __future__ import annotations

import asyncio
import json
import math
from collections.abc import Sequence
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from sanmou_common.policy_contracts import (
    GenerationRecord,
    PolicyCallResult,
    PolicyManifest,
    PolicyRequest,
    PolicyTransportResponse,
    PolicyUsage,
    ProposedCall,
    SealedJson,
)
from pioneer_agent.agent_harness.task_contracts import (
    BudgetExceeded,
    BudgetRequest,
    RunBudget,
    Usage,
)


class PolicyTransport(Protocol):
    """One request, with no hidden retries; cancellation must stop local work.

    A future network implementation must obtain manifest/identity metadata from
    the authenticated service, not from assistant content. Unknown remote usage
    stays unknown, including when cancellation cannot prove remote completion.
    """

    async def generate(self, request: PolicyRequest) -> PolicyTransportResponse: ...


class ToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    name: str = Field(min_length=1)
    description: str = ""
    arguments_model: type[BaseModel]
    state_effect: Literal["read_only", "mutating", "control"]
    window_effect: Literal["passive", "ui_navigation", "ui_mutation"]

    @model_validator(mode="after")
    def forbid_unlisted_parameters(self):
        if self.arguments_model.model_config.get("extra") != "forbid":
            raise ValueError("tool arguments_model must set extra='forbid'")
        return self

    @property
    def counts_as_active(self) -> bool:
        return self.state_effect != "read_only" or self.window_effect != "passive"


class ToolRegistry:
    """Trusted classification and argument validation, with no execute method."""

    def __init__(self, definitions: Sequence[ToolDefinition]):
        self._definitions = {item.name: item for item in definitions}
        if len(self._definitions) != len(definitions):
            raise ValueError("duplicate tool definition")
        self._tools = SealedJson.from_value([
            {"type": "function", "function": {
                "name": item.name, "description": item.description,
                "parameters": item.arguments_model.model_json_schema(),
            }} for item in definitions
        ])

    @property
    def tools(self) -> SealedJson:
        return self._tools

    def parse(self, response: SealedJson) -> tuple[ProposedCall, ...]:
        """Validate the complete batch before exposing any proposed call."""
        raw = response.value()
        if not isinstance(raw, dict) or not isinstance(raw.get("choices"), list):
            raise _Rejected("parse_error")
        choices = raw["choices"]
        if len(choices) != 1 or not isinstance(choices[0], dict):
            raise _Rejected("parse_error")
        choice = choices[0]
        if choice.get("finish_reason") != "tool_calls":
            raise _Rejected("incomplete_generation")
        message = choice.get("message")
        if not isinstance(message, dict) or message.get("role") != "assistant":
            raise _Rejected("parse_error")
        calls = message.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            raise _Rejected("parse_error")
        accepted: list[ProposedCall] = []
        identities: set[str] = set()
        active_count = 0
        for call in calls:
            if (not isinstance(call, dict) or set(call) != {"id", "type", "function"}
                    or call.get("type") != "function"
                    or not isinstance(call.get("id"), str) or not call["id"].strip()):
                raise _Rejected("parse_error")
            if call["id"] in identities:
                raise _Rejected("duplicate_call_id")
            identities.add(call["id"])
            function = call["function"]
            if (not isinstance(function, dict) or set(function) != {"name", "arguments"}
                    or not isinstance(function.get("name"), str)):
                raise _Rejected("parse_error")
            definition = self._definitions.get(function["name"])
            if definition is None:
                raise _Rejected("unknown_tool")
            try:
                if not isinstance(function["arguments"], str):
                    raise ValueError("arguments must be JSON text")
                arguments = json.loads(function["arguments"], object_pairs_hook=_unique_keys,
                                       parse_constant=_reject_nonfinite)
                if not isinstance(arguments, dict):
                    raise ValueError("arguments must be an object")
                checked = definition.arguments_model.model_validate(arguments, strict=True)
                sealed_arguments = SealedJson.from_value(checked.model_dump(mode="json"))
            except (ValueError, TypeError, ValidationError) as exc:
                raise _Rejected("invalid_params") from exc
            accepted.append(ProposedCall(call_id=call["id"], tool_name=definition.name,
                                         arguments=sealed_arguments))
            active_count += definition.counts_as_active
        if active_count > 1:
            raise _Rejected("multiple_non_passive_calls_in_step")
        return tuple(accepted)


def _unique_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _reject_nonfinite(value):
    raise ValueError("nonfinite JSON number")


class _Rejected(Exception):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def _consume_task(task: asyncio.Task) -> None:
    """Observe late transport failures without treating late results as success."""
    if not task.cancelled():
        task.exception()


class PolicyServiceAdapter:
    """In-process invocation deduplication and one shared RunBudget authority.

    ``records`` retains immutable invocation results, including cancellation.
    The caller owns durable persistence and lifecycle; restarting this adapter
    does not provide durable deduplication. Do not wrap this adapter in another
    model-budget reservation (in particular the v1 model policy path).
    """

    def __init__(self, *, transport: PolicyTransport, manifest: PolicyManifest,
                 registry: ToolRegistry, budget: RunBudget,
                 timeout_seconds: float = 30.0):
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        self._transport = transport
        self._manifest = PolicyManifest.model_validate_json(manifest.model_dump_json())
        self._registry = registry
        self._budget = budget
        self._timeout_seconds = timeout_seconds
        self._invocations: set[str] = set()
        self._responses: set[str] = set()
        self._records: list[PolicyCallResult] = []
        self._quiescing: set[asyncio.Task] = set()
        self._settlement_failed = False

    @property
    def records(self) -> tuple[PolicyCallResult, ...]:
        return tuple(self._records)

    async def decide(self, request: PolicyRequest, *,
                     cancel_event: asyncio.Event | None = None) -> PolicyCallResult:
        # Revalidate before reserving. SealedJson owns bytes; value() is detached.
        request = PolicyRequest.model_validate_json(request.model_dump_json())
        result_fields = dict(invocation_id=request.invocation_id,
                             request_sha256=request.sha256, usage=PolicyUsage())
        rejection = None
        if cancel_event is not None and cancel_event.is_set():
            rejection = "cancelled"
        elif self._settlement_failed:
            rejection = "budget_settlement_failed"
        elif any(not task.done() for task in self._quiescing):
            rejection = "transport_not_quiescent"
        elif request.manifest.sha256 != self._manifest.sha256:
            rejection = "policy_version_mismatch"
        elif request.tools.sha256 != self._registry.tools.sha256:
            rejection = "tool_catalog_mismatch"
        elif request.invocation_id in self._invocations:
            rejection = "duplicate_invocation"
        if rejection:
            return self._record(result_fields, "cancelled" if rejection == "cancelled" else "blocked",
                                rejection)
        try:
            reservation = self._budget.reserve(BudgetRequest(
                run_id=request.run_id, step_id=request.decision_id, kind="model",
                name=self._manifest.policy_id, input_tokens=request.estimated_input_tokens,
                output_tokens=request.reserved_output_tokens,
            ))
        except BudgetExceeded:
            return self._record(result_fields, "blocked", "budget_exceeded")
        self._invocations.add(request.invocation_id)
        outcome = "transport_error"
        usage = Usage()
        status = "failed"
        proposed = ()
        primary: BaseException | None = None
        try:
            response = await self._invoke(request, cancel_event)
            response = PolicyTransportResponse.model_validate_json(response.model_dump_json())
            result_fields.update(raw_response=response.raw_response,
                                 provider_response_id=response.provider_response_id,
                                 generation=response.generation)
            if (response.invocation_id != request.invocation_id
                    or response.request_sha256 != request.sha256):
                raise _Rejected("response_binding_mismatch")
            if response.manifest_sha256 != self._manifest.sha256:
                raise _Rejected("policy_version_mismatch")
            if response.provider_response_id in self._responses:
                raise _Rejected("repeated_response")
            self._responses.add(response.provider_response_id)
            # Only a bound response can account for this request's usage.
            result_fields["usage"] = response.usage
            usage = Usage(**response.usage.model_dump())
            proposed = self._registry.parse(response.raw_response)
            historical_ids = {
                call["id"]
                for message in request.messages.value()
                if message["role"] == "assistant"
                for call in (message.get("tool_calls") or ())
            }
            if any(call.call_id in historical_ids for call in proposed):
                proposed = ()
                raise _Rejected("duplicate_call_id")
            interruption = self._interruption(cancel_event)
            if interruption is not None:
                raise _Rejected(interruption)
            outcome = "ok"
            status = "ok"
        except _Rejected as exc:
            outcome = exc.code
            status = "cancelled" if outcome == "cancelled" else "failed"
            proposed = ()
        except asyncio.CancelledError as exc:
            outcome = "cancelled"
            status = "cancelled"
            primary = exc
        except Exception:
            # Deliberately omit exception messages, which may contain secrets
            # from a future transport. The transport owns redacted diagnostics.
            outcome = "transport_error"
        except BaseException as exc:
            primary = exc
        try:
            self._budget.settle(reservation, usage, outcome=outcome)
        except Exception:
            # Never publish an accepted proposal before its accounting succeeds.
            # The ledger may have failed before or after persistence: do not
            # retry settlement here, and preserve a primary cancellation.
            outcome = "budget_settlement_failed"
            self._settlement_failed = True
            status = "cancelled" if isinstance(primary, asyncio.CancelledError) else "failed"
            proposed = ()
            if primary is not None:
                primary.add_note("budget_settlement_failed")
        if status == "ok":
            interruption = self._interruption(cancel_event)
            if interruption is not None:
                outcome = interruption
                status = "cancelled" if interruption == "cancelled" else "failed"
                proposed = ()
        result = self._record(result_fields, status, None if status == "ok" else outcome, proposed)
        if primary is not None:
            raise primary
        return result

    def _interruption(self, cancel_event: asyncio.Event | None) -> str | None:
        if cancel_event is not None and cancel_event.is_set():
            return "cancelled"
        if self._budget.remaining_seconds() <= 0:
            return "budget_exceeded"
        return None

    def _record(self, fields, status, code, calls=()) -> PolicyCallResult:
        result = PolicyCallResult(**fields, status=status, error_code=code, proposed_calls=calls)
        self._records.append(result)
        return result

    async def _invoke(self, request: PolicyRequest,
                      cancel_event: asyncio.Event | None) -> PolicyTransportResponse:
        remaining = min(self._timeout_seconds, self._budget.remaining_seconds())
        if remaining <= 0:
            raise _Rejected("budget_exceeded")
        task = asyncio.create_task(self._transport.generate(request))
        expires = asyncio.get_running_loop().time() + remaining
        try:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise _Rejected("cancelled")
                if self._budget.remaining_seconds() <= 0:
                    raise _Rejected("budget_exceeded")
                left = expires - asyncio.get_running_loop().time()
                if left <= 0:
                    raise _Rejected("timeout")
                done, _ = await asyncio.wait({task}, timeout=min(left, 0.02))
                if done:
                    # A cancellation/deadline racing a response takes priority.
                    if cancel_event is not None and cancel_event.is_set():
                        raise _Rejected("cancelled")
                    if self._budget.remaining_seconds() <= 0:
                        raise _Rejected("budget_exceeded")
                    if asyncio.get_running_loop().time() >= expires:
                        raise _Rejected("timeout")
                    return task.result()
        finally:
            if not task.done():
                self._quiescing.add(task)
                task.cancel()
                task.add_done_callback(self._quiescing.discard)
            task.add_done_callback(_consume_task)


class MockPolicyTransport:
    """Fixed local responses only; no network, GPU, model tokens, or game input."""

    def __init__(self, responses: Sequence[SealedJson]):
        self._responses = tuple(responses)
        self.requests: list[PolicyRequest] = []

    async def generate(self, request: PolicyRequest) -> PolicyTransportResponse:
        index = len(self.requests)
        self.requests.append(request)
        if index >= len(self._responses):
            raise RuntimeError("mock responses exhausted")
        raw = self._responses[index].value()
        choices = raw.get("choices", []) if isinstance(raw, dict) else []
        finish_reason = (choices[0].get("finish_reason") if len(choices) == 1
                         and isinstance(choices[0], dict) else None)
        return PolicyTransportResponse(
            invocation_id=request.invocation_id, request_sha256=request.sha256,
            manifest_sha256=request.manifest.sha256,
            provider_response_id=f"mock-response-{index + 1}",
            raw_response=self._responses[index], usage=PolicyUsage(),
            generation=GenerationRecord(probability_kind="unavailable",
                                        finish_reason=finish_reason if isinstance(finish_reason, str)
                                        and finish_reason else "unavailable"),
        )
