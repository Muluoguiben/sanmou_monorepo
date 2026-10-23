"""Single-attempt HTTP transports for the versioned policy gateway and SGLang.

No retry, tool execution, prompt persistence, or checkpoint attestation is
provided. Deployment configuration declares the upstream model/manifest.
"""
from __future__ import annotations

import asyncio
import ipaddress
import math
from typing import Literal
from urllib.parse import urlsplit

import httpx
from pydantic import SecretStr, ValidationError

from sanmou_common.policy_contracts import (
    GenerationRecord, PolicyManifest, PolicyRequest, PolicyTransportResponse,
    PolicyUsage, SealedJson, canonical_json, decode_json,
)


class PolicyHttpError(RuntimeError):
    """Redacted failure: never include credentials, prompts, or upstream bodies."""

    def __init__(self, code: str, status_code: int | None = None):
        self.code, self.status_code = code, status_code
        super().__init__(code)


def _endpoint(base_url: str, path: str) -> str:
    parsed = urlsplit(base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.hostname
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in {"", "/"}):
        raise ValueError("base_url must be an origin without credentials or a path")
    if parsed.scheme == "http":
        try:
            loopback = ipaddress.ip_address(parsed.hostname).is_loopback
        except ValueError:
            loopback = parsed.hostname == "localhost"
        if not loopback:
            raise ValueError("plaintext HTTP requires loopback; use TLS or a local tunnel")
    return base_url.rstrip("/") + path


def _secret(value: SecretStr | str | None, *, required: bool) -> SecretStr | None:
    secret = value if isinstance(value, SecretStr) else SecretStr(value or "")
    raw = secret.get_secret_value()
    if not raw:
        if required:
            raise ValueError("api_key is required")
        return None
    if any(char.isspace() for char in raw) or not raw.isascii():
        raise ValueError("api_key must be an ASCII token without whitespace")
    return secret


class _JsonHttpClient:
    def __init__(self, *, base_url: str, path: str, api_key: SecretStr | str | None,
                 client: httpx.AsyncClient | None, timeout_seconds: float,
                 max_response_bytes: int, key_required: bool):
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be finite and positive")
        if type(max_response_bytes) is not int or max_response_bytes < 1:
            raise ValueError("max_response_bytes must be positive")
        self._url = _endpoint(base_url, path)
        self._key = _secret(api_key, required=key_required)
        self._timeout = timeout_seconds
        self._max_response_bytes = max_response_bytes
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            trust_env=False, follow_redirects=False,
            transport=httpx.AsyncHTTPTransport(retries=0),
        )

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _post(self, payload: bytes) -> bytes:
        headers = {"Content-Type": "application/json", "Accept": "application/json"}
        if self._key is not None:
            headers["Authorization"] = "Bearer " + self._key.get_secret_value()
        try:
            async with asyncio.timeout(self._timeout):
                async with self._client.stream("POST", self._url, content=payload, headers=headers,
                                               timeout=self._timeout, follow_redirects=False) as response:
                    if response.status_code != 200:
                        raise PolicyHttpError("http_status_error", response.status_code)
                    media_type = response.headers.get("content-type", "").split(";", 1)[0].strip()
                    if media_type != "application/json":
                        raise PolicyHttpError("invalid_content_type")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > self._max_response_bytes:
                            raise PolicyHttpError("response_too_large")
                    return bytes(body)
        except (TimeoutError, httpx.TimeoutException):
            raise PolicyHttpError("http_timeout") from None
        except httpx.HTTPError:
            raise PolicyHttpError("http_transport_error") from None


class HttpPolicyTransport(_JsonHttpClient):
    """PolicyServiceAdapter transport; one POST and no budget ownership."""

    def __init__(self, *, base_url: str, api_key: SecretStr | str,
                 client: httpx.AsyncClient | None = None, timeout_seconds: float = 30.0,
                 max_response_bytes: int = 8 * 1024 * 1024):
        super().__init__(base_url=base_url, path="/v1/policy/decide", api_key=api_key,
                         client=client, timeout_seconds=timeout_seconds,
                         max_response_bytes=max_response_bytes, key_required=True)

    async def generate(self, request: PolicyRequest) -> PolicyTransportResponse:
        request = PolicyRequest.model_validate_json(request.model_dump_json())
        body = await self._post(request.payload)
        try:
            # Reject duplicate JSON keys before Pydantic's JSON parser.
            decode_json(body)
            response = PolicyTransportResponse.model_validate_json(body)
        except (ValueError, TypeError, ValidationError):
            raise PolicyHttpError("invalid_gateway_response") from None
        if (response.invocation_id != request.invocation_id
                or response.request_sha256 != request.sha256
                or response.manifest_sha256 != request.manifest.sha256):
            raise PolicyHttpError("gateway_binding_mismatch")
        return response


# Every allowed key is part of the sealed manifest; caller metadata cannot
# override model, messages, tools, stream, n, token limits or extra body fields.
_SAMPLING_KEYS = frozenset({"temperature", "top_p", "top_k", "min_p", "seed",
                          "repetition_penalty", "frequency_penalty", "presence_penalty", "stop"})


def _validate_sampling(sampling: dict) -> None:
    if set(sampling) != _SAMPLING_KEYS:
        raise ValueError("sampling must explicitly declare all supported fields")
    ranges = {"temperature": (0.0, 2.0), "top_p": (0.0, 1.0), "min_p": (0.0, 1.0),
              "repetition_penalty": (0.0, 2.0), "frequency_penalty": (-2.0, 2.0),
              "presence_penalty": (-2.0, 2.0)}
    for name, (lower, upper) in ranges.items():
        value = sampling[name]
        if type(value) not in (float, int) or not math.isfinite(value) or not lower <= value <= upper:
            raise ValueError("invalid sampling numeric field")
        if name in {"top_p", "repetition_penalty"} and value == 0:
            raise ValueError("sampling value must be positive")
    if type(sampling["top_k"]) is not int or sampling["top_k"] != -1 and sampling["top_k"] < 1:
        raise ValueError("top_k must be -1 or a positive integer")
    seed = sampling["seed"]
    if seed is not None and (type(seed) is not int or not 0 <= seed <= 2**63 - 1):
        raise ValueError("seed must be null or a nonnegative signed 64-bit integer")
    stop = sampling["stop"]
    if stop is not None:
        if isinstance(stop, str):
            valid_stop = bool(stop)
        else:
            valid_stop = (isinstance(stop, list) and bool(stop)
                          and all(isinstance(item, str) and item for item in stop))
        if not valid_stop:
            raise ValueError("stop must be null, nonempty text or a nonempty list of texts")


class SGLangChatBackend(_JsonHttpClient):
    """SGLang non-streaming /v1/chat/completions, text/tools path only.

    ``declared_probability_kind`` is deployment configuration, not GPU proof.
    Its default leaves logprobs in raw_response until semantics are verified.
    Raw logits require the deployed original-logprob setting; sampler logprobs
    are not inferred from the presence of a field called 'logprobs'.
    """

    def __init__(self, *, base_url: str, manifest: PolicyManifest,
                 api_key: SecretStr | str | None = None,
                 client: httpx.AsyncClient | None = None, timeout_seconds: float = 30.0,
                 max_response_bytes: int = 8 * 1024 * 1024,
                 declared_probability_kind: Literal["raw", "unavailable"] = "unavailable"):
        self._manifest = PolicyManifest.model_validate_json(manifest.model_dump_json())
        self._sampling = self._manifest.sampling.value()
        _validate_sampling(self._sampling)
        if declared_probability_kind not in {"raw", "unavailable"}:
            raise ValueError("invalid probability kind")
        self._probability_kind = declared_probability_kind
        super().__init__(base_url=base_url, path="/v1/chat/completions", api_key=api_key,
                         client=client, timeout_seconds=timeout_seconds,
                         max_response_bytes=max_response_bytes, key_required=False)

    def request_payload(self, request: PolicyRequest) -> bytes:
        request = PolicyRequest.model_validate_json(request.model_dump_json())
        if request.manifest.sha256 != self._manifest.sha256:
            raise PolicyHttpError("policy_version_mismatch")
        return canonical_json({
            **self._sampling, "model": self._manifest.model,
            "messages": request.messages.value(), "tools": request.tools.value(),
            "max_tokens": request.reserved_output_tokens, "stream": False, "n": 1,
            "tool_choice": "auto", "logprobs": True,
            "return_token_ids": True, "return_meta_info": True,
            "chat_template_kwargs": {"enable_thinking": False},
        })

    async def generate(self, request: PolicyRequest) -> PolicyTransportResponse:
        request = PolicyRequest.model_validate_json(request.model_dump_json())
        payload = self.request_payload(request)
        body = await self._post(payload)
        try:
            raw = decode_json(body)
            choice = _validate_native_response(raw, self._manifest.model)
            raw_usage = raw.get("usage")
            if raw_usage is None:
                usage = PolicyUsage()
            elif isinstance(raw_usage, dict):
                usage = PolicyUsage(input_tokens=raw_usage.get("prompt_tokens"),
                                    output_tokens=raw_usage.get("completion_tokens"))
            else:
                raise ValueError("invalid usage")
            generation = _generation(choice, self._probability_kind, usage) if choice is not None else None
            return PolicyTransportResponse(
                invocation_id=request.invocation_id, request_sha256=request.sha256,
                manifest_sha256=self._manifest.sha256, provider_response_id=raw["id"],
                raw_response=SealedJson.from_value(raw), usage=usage, generation=generation,
            )
        except PolicyHttpError:
            raise
        except (ValueError, TypeError, KeyError, ValidationError):
            raise PolicyHttpError("invalid_upstream_response") from None


def _validate_native_response(raw: object, expected_model: str) -> dict | None:
    if not isinstance(raw, dict) or raw.get("object") != "chat.completion":
        raise PolicyHttpError("invalid_upstream_response")
    if raw.get("model") != expected_model:
        raise PolicyHttpError("upstream_model_mismatch")
    if not isinstance(raw.get("id"), str) or not raw["id"].strip():
        raise PolicyHttpError("invalid_upstream_response")
    choices = raw.get("choices")
    if not isinstance(choices, list) or len(choices) != 1 or not isinstance(choices[0], dict):
        return None
    choice = choices[0]
    if choice.get("index") != 0 or type(choice.get("index")) is not int:
        raise PolicyHttpError("invalid_upstream_response")
    # Parsing/tool errors (including truncation) belong to PolicyServiceAdapter.
    # Keep the returned raw output and measured usage for failed decisions.
    return choice


def assistant_message(raw: dict) -> dict:
    """Explicit historical-message projection; native raw response is preserved.

    SGLang's reasoning_content and per-tool index are transport metadata; neither
    is silently inserted into common's separately versioned message contract.
    """
    try:
        message = raw["choices"][0]["message"]
        if (not isinstance(message, dict) or message.get("role") != "assistant"
                or message.get("content") is not None and not isinstance(message["content"], str)):
            raise ValueError("invalid assistant message")
        if message.get("reasoning_content") not in (None, ""):
            raise PolicyHttpError("unsupported_reasoning_output")
        calls = message.get("tool_calls")
        if not isinstance(calls, list) or not calls:
            raise ValueError("missing tool calls")
        projected = []
        for call in calls:
            if (not isinstance(call, dict) or set(call) - {"id", "type", "function", "index"}
                    or call.get("type") != "function"
                    or not isinstance(call.get("id"), str) or not call["id"].strip()):
                raise ValueError("invalid tool call")
            if "index" in call and (type(call["index"]) is not int or call["index"] < 0):
                raise ValueError("invalid tool index")
            function = call["function"]
            if (not isinstance(function, dict) or set(function) != {"name", "arguments"}
                    or not isinstance(function["name"], str) or not function["name"].strip()
                    or not isinstance(function["arguments"], str)
                    or not isinstance(decode_json(function["arguments"]), dict)):
                raise ValueError("invalid function")
            projected.append({"id": call["id"], "type": "function", "function": dict(function)})
        return {"role": "assistant", "content": message.get("content"), "tool_calls": projected}
    except (ValueError, TypeError, KeyError, IndexError):
        raise PolicyHttpError("invalid_upstream_response") from None


def _generation(choice: dict, kind: str, usage: PolicyUsage) -> GenerationRecord:
    input_ids, output_ids = choice.get("prompt_token_ids"), choice.get("response_token_ids")
    metadata = choice.get("meta_info")
    logprobs = None
    if metadata is not None and not isinstance(metadata, dict):
        raise ValueError("invalid generation metadata")
    triples = (metadata or {}).get("output_token_logprobs")
    if triples is not None:
        if not isinstance(triples, list):
            raise ValueError("invalid native logprobs")
        # Validate any provided native triples, even if the probability kind is
        # not yet declared. Their unmodified source stays in raw_response.
        values, token_ids = [], []
        for item in triples:
            if (not isinstance(item, list) or len(item) != 3
                    or type(item[0]) not in (int, float) or not math.isfinite(item[0]) or item[0] > 0
                    or type(item[1]) is not int or item[1] < 0
                    or item[2] is not None and not isinstance(item[2], str)):
                raise ValueError("invalid native logprob triple")
            values.append(float(item[0]))
            token_ids.append(item[1])
        if output_ids is not None and output_ids != token_ids:
            raise ValueError("native token IDs and logprobs disagree")
        if usage.output_tokens is not None and len(triples) != usage.output_tokens:
            raise ValueError("native logprobs and completion usage disagree")
        if kind != "unavailable" and output_ids is not None:
            logprobs = tuple(values)
    if input_ids is not None and not isinstance(input_ids, list):
        raise ValueError("invalid input token IDs")
    if output_ids is not None and not isinstance(output_ids, list):
        raise ValueError("invalid response token IDs")
    if input_ids is not None and usage.input_tokens is not None and len(input_ids) != usage.input_tokens:
        raise ValueError("input token IDs and prompt usage disagree")
    if output_ids is not None and usage.output_tokens is not None and len(output_ids) != usage.output_tokens:
        raise ValueError("response token IDs and completion usage disagree")
    finish = choice.get("finish_reason")
    return GenerationRecord(
        input_token_ids=tuple(input_ids) if input_ids is not None else None,
        response_token_ids=tuple(output_ids) if output_ids is not None else None,
        response_logprobs=logprobs, policy_token_mask=None,
        probability_kind=kind if logprobs is not None else "unavailable",
        finish_reason=finish if isinstance(finish, str) and finish else "unavailable",
    )
