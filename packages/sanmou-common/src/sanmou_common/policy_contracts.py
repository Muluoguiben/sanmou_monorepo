"""CPU-only policy service boundary; no game execution or PPO admission authority.

These envelopes supplement, rather than change, the v1 task/knowledge ports.
The canonical request bytes are the transport input and source of its digest.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from .ports import KnowledgeAnswer


Identifier = Annotated[str, Field(min_length=1, max_length=512)]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
TokenId = Annotated[int, Field(ge=0)]
MaskBit = Annotated[int, Field(ge=0, le=1)]
LogProbability = Annotated[float, Field(le=0, allow_inf_nan=False)]


def _check_json(value: Any) -> None:
    if isinstance(value, dict):
        if any(type(key) is not str for key in value):
            raise ValueError("JSON object keys must be strings")
        for item in value.values():
            _check_json(item)
    elif isinstance(value, list):
        for item in value:
            _check_json(item)
    elif value is not None and type(value) not in (str, int, float, bool):
        raise ValueError("only JSON values are accepted")


def canonical_json(value: Any) -> bytes:
    _check_json(value)
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
                      allow_nan=False).encode("utf-8")


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def decode_json(payload: bytes | str) -> Any:
    def reject_constant(value: str) -> None:
        raise ValueError(f"non-finite JSON number: {value}")

    return json.loads(payload, object_pairs_hook=_unique_pairs, parse_constant=reject_constant)


class _Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True,
                              allow_inf_nan=False, revalidate_instances="always")


class SealedJson(_Contract):
    schema_version: Literal["sealed-json-v1"] = "sealed-json-v1"
    payload: bytes
    sha256: Digest

    @classmethod
    def from_value(cls, value: Any) -> SealedJson:
        payload = canonical_json(value)
        return cls(payload=payload, sha256=hashlib.sha256(payload).hexdigest())

    @model_validator(mode="after")
    def verify(self) -> SealedJson:
        if canonical_json(decode_json(self.payload)) != self.payload:
            raise ValueError("payload is not canonical JSON")
        if hashlib.sha256(self.payload).hexdigest() != self.sha256:
            raise ValueError("payload digest mismatch")
        return self

    def value(self) -> Any:
        """Return a detached view, never mutable authority over the sealed bytes."""
        return decode_json(self.payload)


def seal_knowledge_answer(answer: KnowledgeAnswer, *, query: str,
                          kb_revision: str, retriever_revision: str) -> SealedJson:
    """Snapshot the existing read-only port's actual content, without relabeling it.

    A caller must supply the versions used for this lookup. This does not certify
    provenance, human review, semantic support, or permission to publish.
    """
    if any(not isinstance(value, str) or not value.strip()
           for value in (query, kb_revision, retriever_revision)):
        raise ValueError("query and actual knowledge/retriever revisions are required")
    payload = {"schema_version": "policy-knowledge-v1", "query": query,
               "kb_revision": kb_revision, "retriever_revision": retriever_revision,
               "answer": {"answer": answer.answer, "confidence": answer.confidence,
                          "coverage": answer.coverage, "followups": list(answer.followups),
                          "evidence": [asdict(item) for item in answer.evidence]}}
    return SealedJson.from_value(payload)


class PolicyManifest(_Contract):
    schema_version: Literal["policy-manifest-v1"] = "policy-manifest-v1"
    policy_id: Identifier
    model: Identifier
    checkpoint_revision: Identifier
    adapter_revision: Identifier
    tokenizer_revision: Identifier
    chat_template_revision: Identifier
    prompt_revision: Identifier
    sampling: SealedJson
    model_context_limit: int = Field(gt=0)

    @classmethod
    def from_wire(cls, value: dict[str, Any]) -> PolicyManifest:
        """Decode the explicit transport shape, without mutating caller input."""
        wire = decode_json(canonical_json(value))
        if not isinstance(wire, dict) or wire.get("schema_version") != "policy-manifest-v1":
            raise ValueError("unsupported policy manifest wire version")
        if "sampling" not in wire:
            raise ValueError("missing sampling configuration")
        wire["sampling"] = SealedJson.from_value(wire["sampling"])
        return cls.model_validate(wire)

    @model_validator(mode="after")
    def sampling_object(self) -> PolicyManifest:
        if not isinstance(self.sampling.value(), dict):
            raise ValueError("sampling must be an explicit JSON object")
        return self

    def to_wire(self) -> dict[str, Any]:
        result = self.model_dump(mode="json", exclude={"sampling"})
        result["sampling"] = self.sampling.value()
        return result

    @property
    def sha256(self) -> str:
        return hashlib.sha256(canonical_json(self.to_wire())).hexdigest()


def _validate_messages(messages: Any) -> None:
    if not isinstance(messages, list) or not messages:
        raise ValueError("messages must be a nonempty array")
    pending: list[str] = []
    seen: set[str] = set()
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError("message must be an object")
        if set(message) - {"role", "content", "tool_calls", "tool_call_id", "name"}:
            raise ValueError("unknown message fields")
        role = message.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            raise ValueError("unknown message role")
        if message.get("content") is not None and not isinstance(message["content"], str):
            raise ValueError("this policy protocol accepts text content only")
        if role == "tool":
            call_id = message.get("tool_call_id")
            if not isinstance(call_id, str) or not pending or call_id != pending[0]:
                raise ValueError("orphan, repeated, or out-of-order tool reply")
            if "tool_calls" in message or not isinstance(message.get("content"), str):
                raise ValueError("invalid tool reply")
            pending.pop(0)
            continue
        if pending:
            raise ValueError("all tool replies must precede the next turn")
        if "tool_call_id" in message:
            raise ValueError("tool_call_id belongs only to tool messages")
        calls = message.get("tool_calls")
        if calls is not None:
            if role != "assistant" or not isinstance(calls, list) or not calls:
                raise ValueError("invalid assistant tool call group")
            for call in calls:
                if not isinstance(call, dict) or set(call) != {"id", "type", "function"}:
                    raise ValueError("invalid historical tool call")
                call_id = call["id"]
                function = call["function"]
                if not isinstance(call_id, str) or not call_id or call_id in seen:
                    raise ValueError("tool call IDs must be unique")
                if (call["type"] != "function" or not isinstance(function, dict)
                        or set(function) != {"name", "arguments"}
                        or not isinstance(function["name"], str) or not function["name"]
                        or not isinstance(function["arguments"], str)
                        or not isinstance(decode_json(function["arguments"]), dict)):
                    raise ValueError("invalid historical tool function")
                pending.append(call_id)
                seen.add(call_id)
        elif not isinstance(message.get("content"), str):
            raise ValueError("non-tool message requires text content")
    if pending:
        raise ValueError("incomplete tool roundtrip")


def _validate_tools(tools: Any) -> None:
    if not isinstance(tools, list):
        raise ValueError("tools must be an array")
    names: set[str] = set()
    for tool in tools:
        if not isinstance(tool, dict) or set(tool) != {"type", "function"}:
            raise ValueError("invalid tool definition")
        function = tool["function"]
        if (tool["type"] != "function" or not isinstance(function, dict)
                or set(function) - {"name", "description", "parameters", "strict"}):
            raise ValueError("invalid tool definition")
        name = function.get("name")
        parameters = function.get("parameters")
        if not isinstance(name, str) or not name or name in names:
            raise ValueError("tool names must be unique")
        if not isinstance(parameters, dict) or parameters.get("type") != "object":
            raise ValueError("tool parameters require an object schema")
        names.add(name)


class PolicyRequest(_Contract):
    schema_version: Literal["policy-service-v1"] = "policy-service-v1"
    episode_id: Identifier
    run_id: Identifier
    decision_id: Identifier
    invocation_id: Identifier
    context_id: Identifier
    task_ref: Identifier
    binding_ref: Identifier
    observation_ref: Identifier
    manifest: PolicyManifest
    messages: SealedJson
    tools: SealedJson
    knowledge: SealedJson | None = None
    estimated_input_tokens: int = Field(ge=0)
    reserved_output_tokens: int = Field(gt=0)

    @classmethod
    def from_wire(cls, value: dict[str, Any]) -> PolicyRequest:
        """Read exactly to_wire()/payload; network callers must use decode_json.

        JSON parsing with duplicate-key rejection precedes this method. The
        model's default versions are conveniences for local construction only;
        received wire envelopes must declare their supported versions.
        """
        wire = decode_json(canonical_json(value))
        if not isinstance(wire, dict) or wire.get("schema_version") != "policy-service-v1":
            raise ValueError("unsupported policy request wire version")
        if any(name not in wire for name in ("manifest", "messages", "tools")):
            raise ValueError("missing policy request wire fields")
        wire["manifest"] = PolicyManifest.from_wire(wire["manifest"])
        wire["messages"] = SealedJson.from_value(wire["messages"])
        wire["tools"] = SealedJson.from_value(wire["tools"])
        if wire.get("knowledge") is not None:
            wire["knowledge"] = SealedJson.from_value(wire["knowledge"])
        return cls.model_validate(wire)

    @model_validator(mode="after")
    def validate_input(self) -> PolicyRequest:
        _validate_messages(self.messages.value())
        _validate_tools(self.tools.value())
        if self.estimated_input_tokens + self.reserved_output_tokens > self.manifest.model_context_limit:
            raise ValueError("context_overflow")
        if self.knowledge is not None and not isinstance(self.knowledge.value(), dict):
            raise ValueError("knowledge snapshot must be an object")
        return self

    def to_wire(self) -> dict[str, Any]:
        result = self.model_dump(mode="json", exclude={"manifest", "messages", "tools", "knowledge"})
        result.update(manifest=self.manifest.to_wire(), messages=self.messages.value(),
                      tools=self.tools.value(), knowledge=self.knowledge.value() if self.knowledge else None)
        return result

    @property
    def payload(self) -> bytes:
        return canonical_json(self.to_wire())

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()


class ProposedCall(_Contract):
    call_id: Identifier
    tool_name: Identifier
    arguments: SealedJson

    @model_validator(mode="after")
    def object_arguments(self) -> ProposedCall:
        if not isinstance(self.arguments.value(), dict):
            raise ValueError("tool arguments must be an object")
        return self


class PolicyUsage(_Contract):
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cost: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class GenerationRecord(_Contract):
    schema_version: Literal["policy-generation-v1"] = "policy-generation-v1"
    input_token_ids: tuple[TokenId, ...] | None = None
    response_token_ids: tuple[TokenId, ...] | None = None
    response_logprobs: tuple[LogProbability, ...] | None = None
    policy_token_mask: tuple[MaskBit, ...] | None = None
    probability_kind: Literal["raw", "sampling", "unavailable"] = "unavailable"
    finish_reason: Identifier

    @model_validator(mode="after")
    def aligned(self) -> GenerationRecord:
        response = self.response_token_ids
        for sequence in (self.response_logprobs, self.policy_token_mask):
            if sequence is not None and (response is None or len(sequence) != len(response)):
                raise ValueError("generation arrays must align with response token IDs")
        if (self.response_logprobs is None) != (self.probability_kind == "unavailable"):
            raise ValueError("probability kind must describe the recorded probabilities")
        if self.policy_token_mask is not None and any(type(v) is not int for v in self.policy_token_mask):
            raise ValueError("mask entries must be integer 0 or 1")
        return self

    @property
    def availability(self) -> str:
        return ("complete" if self.input_token_ids and self.response_token_ids
                and self.response_logprobs is not None and self.policy_token_mask is not None
                else "unavailable")


class PolicyTransportResponse(_Contract):
    schema_version: Literal["policy-transport-v1"] = "policy-transport-v1"
    invocation_id: Identifier
    request_sha256: Digest
    manifest_sha256: Digest
    provider_response_id: Identifier
    raw_response: SealedJson
    usage: PolicyUsage = Field(default_factory=PolicyUsage)
    generation: GenerationRecord | None = None


class PolicyCallResult(_Contract):
    schema_version: Literal["policy-result-v1"] = "policy-result-v1"
    invocation_id: Identifier
    request_sha256: Digest
    status: Literal["ok", "blocked", "failed", "cancelled"]
    error_code: str | None = None
    proposed_calls: tuple[ProposedCall, ...] = ()
    raw_response: SealedJson | None = None
    usage: PolicyUsage = Field(default_factory=PolicyUsage)
    generation: GenerationRecord | None = None
    provider_response_id: str | None = None

    @model_validator(mode="after")
    def fail_closed(self) -> PolicyCallResult:
        if self.status == "ok":
            if self.error_code is not None or not self.proposed_calls:
                raise ValueError("ok requires proposals and no error")
        elif self.proposed_calls or not self.error_code:
            raise ValueError("failed calls require an error and zero proposals")
        return self
