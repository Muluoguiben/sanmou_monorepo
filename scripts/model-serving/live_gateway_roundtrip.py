#!/usr/bin/env python3
"""Run the actual project gateway against an already-running native upstream.

Only tool replies are mocked. Credentials are supplied through environment
variables; this runner never starts a GPU, a game, or an external model server.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import ipaddress
import math
import os
import re
import secrets
import socket
import stat
import time
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import uvicorn
from pydantic import BaseModel, ConfigDict, Field

from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, SealedJson, canonical_json, decode_json
from pioneer_agent.adapters.policy_http import HttpPolicyTransport, PolicyHttpError, SGLangChatBackend, assistant_message
from pioneer_agent.adapters.policy_service import PolicyServiceAdapter, ToolDefinition, ToolRegistry
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger
from pioneer_agent.app.policy_gateway import create_app


class QueryKnowledgeArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)


class CompleteTaskArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1)


def scenario_registry() -> ToolRegistry:
    return ToolRegistry([
        ToolDefinition(name="query_knowledge", description="Read the fixed gateway-check fixture.",
            arguments_model=QueryKnowledgeArguments, state_effect="read_only", window_effect="passive"),
        ToolDefinition(name="complete_task", description="Propose completion after receiving the fixture response.",
            arguments_model=CompleteTaskArguments, state_effect="control", window_effect="passive"),
    ])


def load_scenario() -> dict:
    return decode_json(Path(__file__).with_name("live_gateway_scenario.json").read_bytes())


def scenario_prompt_payload() -> bytes:
    return canonical_json({"messages": load_scenario()["messages"], "tools": scenario_registry().tools.value()})


def scenario_prompt_sha256() -> str:
    return hashlib.sha256(scenario_prompt_payload()).hexdigest()


class RunnerFailure(RuntimeError):
    """Fixed error codes only: error text must never echo an upstream body/key."""


class EvidenceWriter:
    """Create-only, pinned-directory evidence writes; no cleanup or overwrite."""

    def __init__(self, destination: Path, secret_values: tuple[str, ...]):
        destination = Path(destination)
        parent = destination.parent.resolve(strict=True)
        self.path = parent / destination.name
        if destination.name in {"", ".", ".."}:
            raise RunnerFailure("invalid_output_directory")
        self._secrets = tuple(value for value in secret_values if value)
        self._parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        self._fd = None
        try:
            self._parent_identity = os.fstat(self._parent_fd)
            if (self._parent_identity.st_uid != os.getuid()
                    or self._parent_identity.st_mode & 0o022):
                raise RunnerFailure("unsafe_output_parent")
            os.mkdir(destination.name, mode=0o700, dir_fd=self._parent_fd)
            created = os.stat(destination.name, dir_fd=self._parent_fd, follow_symlinks=False)
            self._fd = os.open(destination.name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                               dir_fd=self._parent_fd)
            self._identity = os.fstat(self._fd)
            if ((created.st_dev, created.st_ino) != (self._identity.st_dev, self._identity.st_ino)
                    or not stat.S_ISDIR(self._identity.st_mode) or self._identity.st_uid != os.getuid()
                    or self._identity.st_mode & 0o077 or os.listdir(self._fd)):
                raise RunnerFailure("output_directory_changed")
            self._check_directory()
        except BaseException:
            if self._fd is not None:
                os.close(self._fd)
            os.close(self._parent_fd)
            raise
        self.files: list[dict] = []
        self.errors: list[dict] = []

    def _check_directory(self):
        parent = os.stat(self.path.parent, follow_symlinks=False)
        if ((parent.st_dev, parent.st_ino) != (self._parent_identity.st_dev, self._parent_identity.st_ino)
                or parent.st_uid != os.getuid() or parent.st_mode & 0o022):
            raise RunnerFailure("output_directory_changed")
        current = os.stat(self.path.name, dir_fd=self._parent_fd, follow_symlinks=False)
        if (not stat.S_ISDIR(current.st_mode)
                or (current.st_dev, current.st_ino) != (self._identity.st_dev, self._identity.st_ino)):
            raise RunnerFailure("output_directory_changed")

    def _has_secret(self, payload: bytes) -> bool:
        # Also inspect decoded JSON strings so escaping cannot hide a known key.
        representations = [payload]
        try:
            value = decode_json(payload)
            def strings(item):
                if isinstance(item, str):
                    yield item.encode("utf-8")
                elif isinstance(item, list):
                    for child in item:
                        yield from strings(child)
                elif isinstance(item, dict):
                    for key, child in item.items():
                        yield key.encode("utf-8")
                        yield from strings(child)
            representations.extend(strings(value))
        except (ValueError, TypeError, UnicodeError):
            pass
        return any(secret.encode("utf-8") in representation
                   for secret in self._secrets for representation in representations)

    def write(self, name: str, payload: bytes, *, media_type="application/json") -> dict:
        if not re.fullmatch(r"[a-zA-Z0-9_.-]+", name) or name in {".", ".."}:
            raise RunnerFailure("invalid_artifact_name")
        if self._has_secret(payload):
            self.errors.append({"code": "secret_detected", "artifact": name})
            raise RunnerFailure("secret_detected")
        try:
            self._check_directory()
            file_fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                              0o600, dir_fd=self._fd)
            try:
                with os.fdopen(file_fd, "wb") as stream:
                    stream.write(payload)
                    stream.flush()
                    os.fsync(stream.fileno())
            except BaseException:
                raise
            self._check_directory()
        except Exception:
            self.errors.append({"code": "artifact_write_failed", "artifact": name})
            raise RunnerFailure("artifact_write_failed") from None
        result = {"path": name, "sha256": hashlib.sha256(payload).hexdigest(),
                  "byte_length": len(payload), "media_type": media_type}
        self.files.append(result)
        return result

    def json(self, name: str, value) -> dict:
        return self.write(name, canonical_json(value))

    def publish_summary(self, pending_name: str) -> None:
        """Atomically publish an already-fsynced summary without overwriting.

        The pending alias remains indexed; both names belong to this run.
        Publication is the final filesystem mutation, after every data write.
        """
        if pending_name != "summary.pending.json":
            raise RunnerFailure("invalid_summary_artifact")
        self._check_directory()
        current = os.stat(pending_name, dir_fd=self._fd, follow_symlinks=False)
        if not stat.S_ISREG(current.st_mode) or current.st_nlink != 1:
            raise RunnerFailure("summary_artifact_changed")
        # link() is atomic and fails if summary.json already exists. Unlike
        # rename(), it cannot silently overwrite an independently created file.
        os.link(pending_name, "summary.json", src_dir_fd=self._fd, dst_dir_fd=self._fd,
                follow_symlinks=False)

    def close(self):
        os.close(self._fd)
        os.close(self._parent_fd)


class AuditedHttpTransport(httpx.AsyncBaseTransport):
    """Observe the actual HTTP dispatch and bounded response bytes, including 4xx.

    One underlying transport call per request; the returned response preserves
    status/headers/body for the production client's own checks. Headers are
    never written to evidence. Body reads remain under that client's timeout.
    """

    def __init__(self, component: str, writer: EvidenceWriter, *, max_bytes=8 * 1024 * 1024):
        self.component, self.writer, self.max_bytes = component, writer, max_bytes
        self.inner = httpx.AsyncHTTPTransport(retries=0)
        self.attempts: list[dict] = []

    async def handle_async_request(self, incoming: httpx.Request) -> httpx.Response:
        index = len(self.attempts) + 1
        prefix = f"{self.component}.http.{index:03d}"
        request_artifact = self.writer.write(prefix + ".request.body", incoming.content,
                                              media_type="application/octet-stream")
        attempt = {"number": index, "component": self.component,
                   "loopback_port": incoming.url.port, "method": incoming.method,
                   "path": incoming.url.path, "request": request_artifact,
                   "dispatched": False, "response_complete": False, "status_code": None}
        self.attempts.append(attempt)
        response = None
        body = bytearray()
        start = time.monotonic()
        try:
            attempt["dispatched"] = True
            response = await self.inner.handle_async_request(incoming)
            attempt["status_code"] = response.status_code
            async for chunk in response.aiter_bytes():
                space = self.max_bytes - len(body)
                body.extend(chunk[:space])
                if len(chunk) > space:
                    attempt["error_code"] = "response_too_large"
                    raise PolicyHttpError("response_too_large")
            attempt["response_complete"] = True
            # Response body is decoded by HTTPX, just like production _post.
            # Drop transport encodings because these bytes have been decoded.
            headers = [(name, value) for name, value in response.headers.multi_items()
                       if name.lower() not in {"content-encoding", "content-length", "transfer-encoding"}]
            return httpx.Response(response.status_code, headers=headers, content=bytes(body),
                                  request=incoming, extensions=response.extensions)
        except asyncio.CancelledError:
            attempt["error_code"] = "cancelled"
            raise
        except Exception:
            attempt.setdefault("error_code", "http_failure")
            raise
        finally:
            attempt["elapsed_seconds"] = time.monotonic() - start
            if response is not None:
                await response.aclose()
                try:
                    attempt["response"] = self.writer.write(prefix + ".response.body", bytes(body),
                                                              media_type="application/octet-stream")
                except RunnerFailure:
                    attempt["error_code"] = "evidence_recording_failed"
                    # Don't replace a primary cancellation/network failure.
                    # Writer.errors prevents any successful run summary.

    async def aclose(self):
        await self.inner.aclose()


class AuditedBackend(SGLangChatBackend):
    def __init__(self, *, writer: EvidenceWriter, **kwargs):
        super().__init__(**kwargs)
        self.writer = writer
        self.generate_calls = 0
        self.post_calls = 0
        self.posts: list[dict] = []

    async def generate(self, request):
        self.generate_calls += 1
        return await super().generate(request)

    async def _post(self, payload: bytes) -> bytes:
        self.post_calls += 1
        prefix = f"native.post.{self.post_calls:03d}"
        row = {"number": self.post_calls,
               "request": self.writer.write(prefix + ".request.body", payload,
                                              media_type="application/octet-stream")}
        self.posts.append(row)
        try:
            body = await super()._post(payload)
            row["response"] = self.writer.write(prefix + ".response.body", body,
                                                  media_type="application/octet-stream")
            return body
        except PolicyHttpError as exc:
            row["error_code"] = exc.code
            row["status_code"] = exc.status_code
            raise
        except asyncio.CancelledError:
            row["error_code"] = "cancelled"
            raise
        except Exception:
            row["error_code"] = "native_failure"
            raise


class AuditedBudget(RunBudgetLedger):
    def __init__(self, limits):
        super().__init__(limits)
        self.reserve_calls = 0
        self.settle_calls = 0
        self.events: list[dict] = []

    def reserve(self, request):
        self.reserve_calls += 1
        reservation = super().reserve(request)
        self.events.append({"event": "reserve", "reservation_id": reservation,
                            "request": request.model_dump(mode="json")})
        return reservation

    def settle(self, reservation_id, usage, *, outcome):
        self.settle_calls += 1
        super().settle(reservation_id, usage, outcome=outcome)
        self.events.append({"event": "settle", "reservation_id": reservation_id,
                            "usage": usage.model_dump(mode="json"), "outcome": outcome})


@asynccontextmanager
async def gateway_server(app):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
            access_log=False, log_level="critical", lifespan="on", timeout_graceful_shutdown=2))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(5):
                while not server.started:
                    if task.done():
                        await task
                        raise RunnerFailure("gateway_start_failed")
                    await asyncio.sleep(0.005)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            try:
                await asyncio.wait_for(task, timeout=5)
            except TimeoutError:
                server.force_exit = True
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


def _load_input(path: Path) -> bytes:
    with Path(path).open("rb") as handle:
        payload = handle.read(2 * 1024 * 1024 + 1)
    if len(payload) > 2 * 1024 * 1024:
        raise RunnerFailure("input_file_too_large")
    return payload


def _loopback_port(upstream: str) -> int:
    parsed = urlsplit(upstream)
    try:
        loopback = ipaddress.ip_address(parsed.hostname or "").is_loopback
    except ValueError:
        loopback = parsed.hostname == "localhost"
    if (not loopback or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in {"", "/"}):
        raise RunnerFailure("upstream_must_be_loopback_origin")
    return parsed.port or (443 if parsed.scheme == "https" else 80)


def verify_binding(manifest: PolicyManifest, receipt: dict) -> None:
    # The builder is shared with the native runtime receipt producer. Do not
    # derive a second policy version from ad-hoc receipt fields here.
    from native_runtime_manifest import build_native_policy_manifest
    expected = build_native_policy_manifest(receipt)
    if expected.sha256 != manifest.sha256:
        raise RunnerFailure("native_runtime_binding_mismatch")
    if manifest.prompt_revision != "sha256:" + scenario_prompt_sha256():
        raise RunnerFailure("scenario_prompt_binding_mismatch")
    if manifest.sampling.value() != load_scenario()["sampling"]:
        raise RunnerFailure("scenario_sampling_binding_mismatch")


def verify_native_readback(result) -> dict:
    """Require observed IDs/usage/triples while leaving distribution unknown."""
    generation = result.generation
    if (generation is None or not generation.input_token_ids or not generation.response_token_ids
            or result.usage.input_tokens is None or result.usage.output_tokens is None):
        raise RunnerFailure("native_token_or_usage_readback_missing")
    if (len(generation.input_token_ids) != result.usage.input_tokens
            or len(generation.response_token_ids) != result.usage.output_tokens):
        raise RunnerFailure("native_token_usage_mismatch")
    raw = result.raw_response.value()
    metadata = raw["choices"][0].get("meta_info")
    triples = metadata.get("output_token_logprobs") if isinstance(metadata, dict) else None
    if not isinstance(triples, list) or len(triples) != len(generation.response_token_ids):
        raise RunnerFailure("native_logprob_readback_missing")
    for token, row in zip(generation.response_token_ids, triples):
        if (not isinstance(row, list) or len(row) != 3 or type(row[1]) is not int or row[1] != token
                or type(row[0]) not in (int, float) or not math.isfinite(row[0]) or row[0] > 0):
            raise RunnerFailure("native_logprob_token_mismatch")
    if generation.probability_kind != "unavailable" or generation.policy_token_mask is not None:
        raise RunnerFailure("unexpected_probability_claim")
    return {"input_tokens": result.usage.input_tokens, "output_tokens": result.usage.output_tokens,
            "native_logprob_triples": len(triples), "probability_kind": "unavailable"}


async def run(*, manifest_path: Path, binding_path: Path, upstream: str, output: Path,
              timeout_seconds: float = 180.0, budget_seconds: float = 420.0,
              input_tokens: int = 1024, output_tokens: int = 192,
              synthetic_upstream: bool = False) -> dict:
    gateway_key = os.environ.get("POLICY_GATEWAY_API_KEY", "")
    upstream_key = os.environ.get("SGLANG_API_KEY", "")
    wrong_key = secrets.token_urlsafe(32)
    while wrong_key == gateway_key or wrong_key == upstream_key:
        wrong_key = secrets.token_urlsafe(32)
    writer = EvidenceWriter(output, (gateway_key, upstream_key, wrong_key))
    summary = {"schema_version": "live-gateway-roundtrip-v1", "status": "failed",
               "evidence_kind": "project_gateway_http_roundtrip",
               "upstream_mode": "synthetic" if synthetic_upstream else "live",
               "network_scope": "same_host_loopback", "game_input_dispatches": 0,
               "cross_machine_connection_verified": False,
               "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "scenario_prompt_sha256": scenario_prompt_sha256(), "timeouts_seconds": None}
    budget = None
    backend = None
    app = None
    native_http = None
    gateway_http = None
    records = []
    checks = {}
    try:
        if not gateway_key:
            raise RunnerFailure("gateway_api_key_missing")
        if (not math.isfinite(timeout_seconds) or timeout_seconds <= 0
                or not math.isfinite(budget_seconds) or budget_seconds < max(400, 2 * (timeout_seconds + 15) + 10)
                or type(input_tokens) is not int or input_tokens < 1
                or type(output_tokens) is not int or output_tokens < 1):
            raise RunnerFailure("invalid_time_or_token_budget")
        summary["timeouts_seconds"] = {"native": timeout_seconds, "gateway": timeout_seconds + 5,
            "http_client": timeout_seconds + 10, "adapter": timeout_seconds + 15,
            "global_budget": budget_seconds}
        summary["upstream_loopback_port"] = _loopback_port(upstream)
        manifest_bytes, binding_bytes = _load_input(manifest_path), _load_input(binding_path)
        writer.write("manifest.input.json", manifest_bytes)
        writer.write("native-runtime.input.json", binding_bytes)
        manifest = PolicyManifest.model_validate_json(manifest_bytes)
        receipt = decode_json(binding_bytes)
        verify_binding(manifest, receipt)
        if (summary["upstream_loopback_port"] != receipt["public_config"]["port"]
                or urlsplit(upstream).hostname not in {receipt["public_config"]["host"], "localhost"}):
            raise RunnerFailure("upstream_endpoint_binding_mismatch")
        writer.write("scenario.prompt.json", scenario_prompt_payload())
        scenario = load_scenario()
        writer.json("scenario.json", scenario)
        registry = scenario_registry()
        budget = AuditedBudget(BudgetLimits(max_steps=2, max_model_attempts=2, max_tool_calls=0,
            max_tokens=2 * (input_tokens + output_tokens), max_seconds=float(budget_seconds)))
        native_http = AuditedHttpTransport("native", writer)
        gateway_http = AuditedHttpTransport("gateway", writer)
        async with httpx.AsyncClient(transport=native_http, trust_env=False, follow_redirects=False) as native_client:
            backend = AuditedBackend(writer=writer, base_url=upstream, manifest=manifest,
                api_key=upstream_key or None, client=native_client, timeout_seconds=timeout_seconds,
                declared_probability_kind="unavailable")
            app = create_app(manifest=manifest, api_key=gateway_key, backend=backend,
                             timeout_seconds=timeout_seconds + 5, max_inflight=1)
            messages = scenario["messages"]
            def make_request(number, selected_manifest=manifest):
                return PolicyRequest(episode_id="live-gateway-check", run_id="live-gateway-check-run",
                    decision_id=f"decision-{number}", invocation_id=f"invocation-{number}",
                    context_id=f"context-{number}", task_ref=scenario["scenario_id"],
                    binding_ref=hashlib.sha256(binding_bytes).hexdigest(),
                    observation_ref="synthetic-no-game-observation", manifest=selected_manifest,
                    messages=SealedJson.from_value(messages), tools=registry.tools,
                    estimated_input_tokens=input_tokens, reserved_output_tokens=output_tokens)
            first_request = make_request(1)
            async with gateway_server(app) as gateway_url:
                summary["gateway_loopback_port"] = urlsplit(gateway_url).port
                async with httpx.AsyncClient(transport=gateway_http, trust_env=False,
                                              follow_redirects=False) as gateway_client:
                    # Negative probes go straight to the gateway, outside the
                    # successful adapter's budget. Each must dispatch no native call.
                    mismatched = manifest.model_copy(update={"prompt_revision": "0" * 64})
                    probes = (("missing_key", None, first_request.payload, 401),
                              ("wrong_key", wrong_key, first_request.payload, 401),
                              ("wrong_manifest", gateway_key, make_request("wrong", mismatched).payload, 409))
                    for name, key, payload, expected_status in probes:
                        before = (backend.generate_calls, backend.post_calls, len(native_http.attempts))
                        headers = {"Content-Type": "application/json"}
                        if key is not None:
                            headers["Authorization"] = "Bearer " + key
                        async with asyncio.timeout(min(10.0, timeout_seconds)):
                            response = await gateway_client.post(gateway_url + "/v1/policy/decide",
                                content=payload, headers=headers, timeout=min(10.0, timeout_seconds))
                        after = (backend.generate_calls, backend.post_calls, len(native_http.attempts))
                        if writer.errors:
                            raise RunnerFailure("evidence_recording_failed")
                        checks[name] = {"status_code": response.status_code,
                                        "native_counts_before": list(before), "native_counts_after": list(after),
                                        "passed": response.status_code == expected_status and before == after}
                        if not checks[name]["passed"]:
                            raise RunnerFailure("negative_probe_failed")
                    transport = HttpPolicyTransport(base_url=gateway_url, api_key=gateway_key,
                        client=gateway_client, timeout_seconds=timeout_seconds + 10)
                    adapter = PolicyServiceAdapter(transport=transport, manifest=manifest,
                        registry=registry, budget=budget, timeout_seconds=timeout_seconds + 15)
                    for number in (1, 2):
                        request = make_request(number)
                        writer.write(f"round.{number}.request.json", request.payload)
                        result = await adapter.decide(request)
                        if writer.errors:
                            raise RunnerFailure("evidence_recording_failed")
                        records.append(result.model_dump(mode="json"))
                        writer.json(f"round.{number}.result.json", records[-1])
                        if result.status != "ok":
                            raise RunnerFailure("policy_round_failed")
                        checks[f"round_{number}_native_readback"] = verify_native_readback(result)
                        expected_tool = scenario["first_tool"] if number == 1 else scenario["second_tool"]
                        if len(result.proposed_calls) != 1 or result.proposed_calls[0].tool_name != expected_tool:
                            raise RunnerFailure("unexpected_tool_sequence")
                        if number == 1:
                            if result.proposed_calls[0].arguments.value() != scenario["first_arguments"]:
                                raise RunnerFailure("unexpected_query_arguments")
                            messages = messages + [assistant_message(result.raw_response.value()), {
                                "role": "tool", "tool_call_id": result.proposed_calls[0].call_id,
                                "content": canonical_json(scenario["tool_reply"]).decode("utf-8")}]
            if (backend.generate_calls != 2 or backend.post_calls != 2 or len(native_http.attempts) != 2
                    or budget.reserve_calls != 2 or budget.settle_calls != 2 or budget.summary()["pending"] != 0
                    or budget.summary()["overrun"]):
                raise RunnerFailure("unexpected_call_or_budget_counts")
        if writer.errors:
            raise RunnerFailure("evidence_recording_failed")
        checks["two_model_rounds"] = {"passed": len(records) == 2}
        summary["status"] = "passed"
    except RunnerFailure as exc:
        summary["error_code"] = str(exc)
    except asyncio.CancelledError:
        summary["error_code"] = "runner_cancelled"
    except Exception:
        summary["error_code"] = "runner_failure"
    finally:
        if backend is not None:
            try:
                await backend.aclose()
            except Exception:
                summary["status"] = "failed"
                summary["error_code"] = "backend_close_failed"
        summary["checks"] = checks
        summary["completed_rounds"] = len(records)
        summary["native_generate_calls"] = backend.generate_calls if backend else 0
        summary["native_post_calls"] = backend.post_calls if backend else 0
        summary["native_http_dispatches"] = (sum(item["dispatched"] for item in native_http.attempts)
                                                if native_http else 0)
        summary["gateway_counts"] = dict(app.state.gateway_counters) if app else None
        summary["budget"] = budget.summary() if budget else None
        summary["reserve_calls"] = budget.reserve_calls if budget else 0
        summary["settle_calls"] = budget.settle_calls if budget else 0
        if writer.errors:
            summary["status"] = "failed"
            summary["error_code"] = "evidence_recording_failed"
        try:
            writer.json("http-attempts.json", {"gateway": gateway_http.attempts if gateway_http else [],
                "native": native_http.attempts if native_http else [], "native_posts": backend.posts if backend else []})
            writer.json("budget-events.json", {"events": budget.events if budget else []})
            writer.json("recording-errors.json", writer.errors)
            # Flush/fsync the candidate before publishing its final name. A
            # post-write fsync failure can leave complete pending bytes, but
            # cannot leave a final success summary or a complete passed bundle.
            summary_payload = canonical_json(summary)
            summary_entry = {"path": "summary.json", "sha256": hashlib.sha256(summary_payload).hexdigest(),
                             "byte_length": len(summary_payload), "media_type": "application/json"}
            writer.write("summary.pending.json", summary_payload)
            index = writer.json("artifact-index.json", {"schema_version": "live-gateway-artifact-index-v1",
                "files": list(writer.files) + [summary_entry]})
            writer.publish_summary("summary.pending.json")
            summary["index_sha256"] = index["sha256"]
        finally:
            writer.close()
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe-scenario", action="store_true")
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--binding", type=Path)
    parser.add_argument("--upstream")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--timeout", type=float, default=180.0)
    parser.add_argument("--budget-seconds", type=float, default=420.0)
    parser.add_argument("--input-tokens", type=int, default=1024)
    parser.add_argument("--output-tokens", type=int, default=192)
    parser.add_argument("--synthetic-upstream", action="store_true",
                        help="Label CPU tests honestly; normal runs use the already-running live upstream")
    args = parser.parse_args()
    if args.describe_scenario:
        print(canonical_json({"prompt_sha256": scenario_prompt_sha256(),
                              "prompt": decode_json(scenario_prompt_payload()),
                              "sampling": load_scenario()["sampling"]}).decode("utf-8"))
        return
    if not all((args.manifest, args.binding, args.upstream, args.output)):
        parser.error("--manifest, --binding, --upstream and --output are required")
    try:
        result = asyncio.run(run(manifest_path=args.manifest, binding_path=args.binding,
            upstream=args.upstream, output=args.output, timeout_seconds=args.timeout,
            budget_seconds=args.budget_seconds, input_tokens=args.input_tokens,
            output_tokens=args.output_tokens, synthetic_upstream=args.synthetic_upstream))
        print(canonical_json({"status": result["status"], "index_sha256": result.get("index_sha256"),
                              "native_http_dispatches": result["native_http_dispatches"],
                              "error_code": result.get("error_code")}).decode("utf-8"))
    except Exception:
        print('{"status":"failed","error_code":"runner_setup_or_artifact_failure"}')
        raise SystemExit(1)
    if result["status"] != "passed":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
