"""Gateway tests include real loopback HTTP with a synthetic native upstream."""
from __future__ import annotations

import asyncio
import socket
import unittest
from contextlib import asynccontextmanager

import httpx
import uvicorn
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from sanmou_common.policy_contracts import PolicyTransportResponse, SealedJson
from pioneer_agent.adapters.policy_http import HttpPolicyTransport, PolicyHttpError, SGLangChatBackend, assistant_message
from pioneer_agent.adapters.policy_service import MockPolicyTransport, PolicyServiceAdapter
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.app.policy_gateway import create_app
from test_policy_http import manifest, native_fixtures, registry, request


@asynccontextmanager
async def loopback(app):
    sock = socket.socket()
    try:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
    except BaseException:
        sock.close()
        raise
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
        access_log=False, log_level="critical", lifespan="off"))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(3.0):
            while not server.started:
                if task.done():
                    await task
                await asyncio.sleep(0.005)
        yield f"http://127.0.0.1:{port}"
    finally:
        server.should_exit = True
        await asyncio.wait_for(task, timeout=3.0)
        sock.close()


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    def app(self, backend=None, **kwargs):
        self.backend = backend or MockPolicyTransport([SealedJson.from_value(native_fixtures()[0])])
        return create_app(manifest=manifest(), api_key="gateway-test-key", backend=self.backend, **kwargs)

    async def post(self, app, *, body=None, headers=None):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://127.0.0.1") as client:
            return await client.post("/v1/policy/decide", content=body or request().payload,
                headers=headers or {"Authorization": "Bearer gateway-test-key", "Content-Type": "application/json"})

    async def test_auth_missing_wrong_and_duplicate_reject_before_backend(self):
        app = self.app()
        for headers in ({"Content-Type": "application/json"},
                        {"Content-Type": "application/json", "Authorization": "Bearer wrong"},
                        [("content-type", "application/json"), ("authorization", "Bearer gateway-test-key"),
                         ("authorization", "Bearer gateway-test-key")]):
            response = await self.post(app, headers=headers)
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.json(), {"error": {"code": "unauthorized"}})
        self.assertEqual(self.backend.requests, [])

    async def test_version_mismatch_has_zero_backend_calls(self):
        app = self.app()
        changed = manifest().model_copy(update={"checkpoint_revision": "other"})
        response = await self.post(app, body=request(selected_manifest=changed).payload)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.backend.requests, [])

    async def test_invalid_json_schema_and_orphan_history_rejected(self):
        app = self.app()
        for body in (b'{"schema_version":"policy-service-v1","schema_version":"policy-service-v1"}',
                     b'not-json', b'[]', b'{"schema_version":"unknown"}'):
            response = await self.post(app, body=body)
            self.assertEqual(response.status_code, 400)
            self.assertNotIn("input", response.text)
        self.assertEqual(self.backend.requests, [])

    async def test_request_size_stream_limit_rejects_without_backend(self):
        app = self.app(max_request_bytes=10)
        async def chunks():
            yield b"12345678"
            yield b"12345678"
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://127.0.0.1") as client:
            response = await client.post("/v1/policy/decide", content=chunks(), headers={
                "Authorization": "Bearer gateway-test-key", "Content-Type": "application/json"})
        self.assertEqual(response.status_code, 413)
        self.assertEqual(self.backend.requests, [])

    async def test_slow_body_concurrency_cannot_bypass_max_inflight(self):
        started, release_backend, bodies_ready, release_bodies = (
            asyncio.Event(), asyncio.Event(), asyncio.Event(), asyncio.Event())
        body_count = [0]
        class PausedBackend(MockPolicyTransport):
            calls = 0
            async def generate(self, req):
                self.calls += 1
                started.set()
                await release_backend.wait()
                return await super().generate(req)
        backend = PausedBackend([SealedJson.from_value(native_fixtures()[0])])
        app = self.app(backend, max_inflight=1)
        async def body():
            yield request().payload[:1]
            body_count[0] += 1
            if body_count[0] == 2:
                bodies_ready.set()
            await release_bodies.wait()
            yield request().payload[1:]
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://127.0.0.1") as client:
            tasks = [asyncio.create_task(client.post("/v1/policy/decide", content=body(), headers={
                "Authorization": "Bearer gateway-test-key", "Content-Type": "application/json"})) for _ in range(2)]
            await asyncio.wait_for(bodies_ready.wait(), timeout=1.0)
            release_bodies.set()
            await asyncio.wait_for(started.wait(), timeout=1.0)
            done, _ = await asyncio.wait(tasks, timeout=1.0, return_when=asyncio.FIRST_COMPLETED)
            self.assertEqual(len(done), 1)
            self.assertEqual(next(iter(done)).result().status_code, 503)
            self.assertEqual(backend.calls, 1)
            release_backend.set()
            results = await asyncio.gather(*tasks)
        self.assertEqual(sorted(result.status_code for result in results), [200, 503])
        self.assertEqual(app.state.gateway_counters["accepted"], 1)

    async def test_health_has_no_key_manifest_or_upstream_and_no_docs(self):
        app = self.app()
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://127.0.0.1") as client:
            response = await client.get("/health")
            self.assertEqual(response.json(), {"status": "ok", "service": "policy-gateway"})
            self.assertEqual((await client.get("/docs")).status_code, 404)
            self.assertEqual((await client.get("/openapi.json")).status_code, 404)

    async def test_backend_metadata_mismatch_is_not_rebound_to_request(self):
        class WrongMetadata:
            async def generate(self, req):
                return PolicyTransportResponse(invocation_id="wrong", request_sha256=req.sha256,
                    manifest_sha256=manifest().sha256, provider_response_id="wrong-response",
                    raw_response=SealedJson.from_value(native_fixtures()[0]))
        response = await self.post(self.app(WrongMetadata()))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json()["error"]["code"], "upstream_binding_mismatch")

    async def test_internal_exception_does_not_echo_prompt_or_secrets(self):
        class BrokenBackend:
            calls = 0
            async def generate(self, req):
                self.calls += 1
                raise RuntimeError("private-api-key raw-user-prompt")
        backend = BrokenBackend()
        response = await self.post(self.app(backend))
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json(), {"error": {"code": "upstream_failure"}})
        self.assertEqual(backend.calls, 1)

    async def test_real_http_two_rounds_and_auth_version_errors(self):
        upstream = FastAPI()
        seen = []
        @upstream.post("/v1/chat/completions")
        async def native(incoming: Request):
            seen.append(await incoming.json())
            return native_fixtures()[len(seen) - 1]
        async with loopback(upstream) as upstream_url:
            native_backend = SGLangChatBackend(base_url=upstream_url, manifest=manifest())
            gateway = self.app(native_backend)
            async with loopback(gateway) as gateway_url:
                transport = HttpPolicyTransport(base_url=gateway_url, api_key="gateway-test-key")
                budget = RunBudgetLedger()
                adapter = PolicyServiceAdapter(transport=transport, manifest=manifest(),
                                               registry=registry(), budget=budget)
                first = await adapter.decide(request())
                self.assertEqual(first.status, "ok", first.error_code)
                history = request().messages.value() + [assistant_message(first.raw_response.value()),
                    {"role": "tool", "tool_call_id": first.proposed_calls[0].call_id,
                     "content": '{"source":"synthetic","status":"ok"}'}]
                second = await adapter.decide(request(2, messages=history))
                self.assertEqual(second.status, "ok", second.error_code)
                self.assertEqual(second.proposed_calls[0].tool_name, "complete_task")
                self.assertEqual(seen[1]["messages"], history)
                self.assertEqual(len(seen), 2)
                self.assertEqual(budget.summary()["counts"]["model"], 2)
                self.assertEqual(budget.summary()["pending"], 0)
                wrong = HttpPolicyTransport(base_url=gateway_url, api_key="wrong-key")
                with self.assertRaises(PolicyHttpError) as raised:
                    await wrong.generate(request(3))
                self.assertEqual(raised.exception.status_code, 401)
                changed = manifest().model_copy(update={"prompt_revision": "wrong"})
                with self.assertRaises(PolicyHttpError) as raised:
                    await transport.generate(request(3, selected_manifest=changed))
                self.assertEqual(raised.exception.status_code, 409)
                self.assertEqual(len(seen), 2)
                self.assertEqual(gateway.state.gateway_counters["succeeded"], 2)
                await wrong.aclose()
                await transport.aclose()
            await native_backend.aclose()

    async def test_real_http_timeout_and_disconnect_cancel_backend_no_retry(self):
        class HangingBackend:
            def __init__(self):
                self.calls = 0
                self.started, self.stopped = asyncio.Event(), asyncio.Event()
            async def generate(self, req):
                self.calls += 1
                self.started.set()
                try:
                    await asyncio.Event().wait()
                finally:
                    self.stopped.set()
        for mode in ("gateway_timeout", "client_cancel"):
            with self.subTest(mode=mode):
                backend = HangingBackend()
                gateway = self.app(backend, timeout_seconds=0.03 if mode == "gateway_timeout" else 2.0)
                async with loopback(gateway) as url:
                    transport = HttpPolicyTransport(base_url=url, api_key="gateway-test-key")
                    task = asyncio.create_task(transport.generate(request()))
                    await asyncio.wait_for(backend.started.wait(), timeout=1.0)
                    if mode == "gateway_timeout":
                        with self.assertRaises(PolicyHttpError) as raised:
                            await task
                        self.assertEqual(raised.exception.status_code, 504)
                    else:
                        task.cancel()
                        with self.assertRaises(asyncio.CancelledError):
                            await task
                    await asyncio.wait_for(backend.stopped.wait(), timeout=1.0)
                    self.assertEqual(backend.calls, 1)
                    self.assertEqual(gateway.state.gateway_counters["succeeded"], 0)
                    await transport.aclose()

    async def test_real_http_upstream_error_is_not_retried(self):
        upstream = FastAPI()
        calls = []
        @upstream.post("/v1/chat/completions")
        async def native():
            calls.append(1)
            return JSONResponse({"private": "must not echo"}, status_code=503)
        async with loopback(upstream) as upstream_url:
            backend = SGLangChatBackend(base_url=upstream_url, manifest=manifest())
            async with loopback(self.app(backend)) as url:
                transport = HttpPolicyTransport(base_url=url, api_key="gateway-test-key")
                with self.assertRaises(PolicyHttpError) as raised:
                    await transport.generate(request())
                self.assertEqual(raised.exception.status_code, 502)
                self.assertEqual(len(calls), 1)
                await transport.aclose()
            await backend.aclose()


if __name__ == "__main__":
    unittest.main()
