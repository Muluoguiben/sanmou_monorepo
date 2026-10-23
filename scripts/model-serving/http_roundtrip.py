#!/usr/bin/env python3
"""Exercise two real loopback HTTP hops with synthetic responses; no GPU/model."""
from __future__ import annotations

import argparse
import asyncio
import json
import secrets
import socket
from contextlib import asynccontextmanager
from pathlib import Path

import uvicorn
from fastapi import FastAPI, Request
from pydantic import BaseModel, ConfigDict

from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, SealedJson
from pioneer_agent.adapters.policy_http import HttpPolicyTransport, PolicyHttpError, SGLangChatBackend, assistant_message
from pioneer_agent.adapters.policy_service import PolicyServiceAdapter, ToolDefinition, ToolRegistry
from pioneer_agent.agent_harness.run_budget import RunBudgetLedger
from pioneer_agent.app.policy_gateway import create_app


class QueryArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str


class CompleteArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str


@asynccontextmanager
async def local_server(app):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        sock.listen(128)
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port,
            access_log=False, log_level="critical", lifespan="off"))
        task = asyncio.create_task(server.serve(sockets=[sock]))
        try:
            async with asyncio.timeout(3):
                while not server.started:
                    if task.done():
                        await task
                    await asyncio.sleep(0.005)
            yield f"http://127.0.0.1:{port}"
        finally:
            server.should_exit = True
            await asyncio.wait_for(task, timeout=3)


async def run() -> dict:
    root = Path(__file__).resolve().parents[2]
    fixture_path = root / "packages/pioneer-agent/tests/fixtures/policy_service/sglang_http_roundtrip.json"
    fixtures = json.loads(fixture_path.read_text(encoding="utf-8"))
    upstream = FastAPI()
    upstream_calls = []

    @upstream.post("/v1/chat/completions")
    async def generate(incoming: Request):
        payload = await incoming.json()
        upstream_calls.append({"message_count": len(payload["messages"]), "stream": payload["stream"]})
        return fixtures[len(upstream_calls) - 1]

    manifest = PolicyManifest(policy_id="http-fixture-policy", model="cpu-fake-qwen",
        checkpoint_revision="synthetic-no-weights", adapter_revision="none", tokenizer_revision="unavailable",
        chat_template_revision="qwen-no-thinking-v1", prompt_revision="synthetic-v1",
        sampling=SealedJson.from_value({"temperature": 0.0, "top_p": 1.0, "top_k": -1,
            "min_p": 0.0, "repetition_penalty": 1.0, "frequency_penalty": 0.0,
            "presence_penalty": 0.0, "seed": 0, "stop": None}), model_context_limit=4096)
    registry = ToolRegistry([
        ToolDefinition(name="query_knowledge", arguments_model=QueryArgs,
                       state_effect="read_only", window_effect="passive"),
        ToolDefinition(name="complete_task", arguments_model=CompleteArgs,
                       state_effect="control", window_effect="passive"),
    ])
    key = secrets.token_urlsafe(32)
    budget = RunBudgetLedger()
    messages = [{"role": "user", "content": "查询建筑升级规则（合成测试）。"}]
    requests = []
    async with local_server(upstream) as upstream_url:
        backend = SGLangChatBackend(base_url=upstream_url, manifest=manifest)
        app = create_app(manifest=manifest, api_key=key, backend=backend)
        try:
            async with local_server(app) as gateway_url:
                transport = HttpPolicyTransport(base_url=gateway_url, api_key=key)
                wrong_key = HttpPolicyTransport(base_url=gateway_url, api_key=secrets.token_urlsafe(32))
                try:
                    adapter = PolicyServiceAdapter(transport=transport, manifest=manifest,
                                                   registry=registry, budget=budget)
                    for index in range(2):
                        req = PolicyRequest(episode_id="synthetic-episode", run_id="synthetic-run",
                            decision_id=f"decision-{index+1}", invocation_id=f"invocation-{index+1}",
                            context_id=f"context-{index+1}", task_ref="synthetic-task",
                            binding_ref="synthetic-binding", observation_ref="synthetic-observation",
                            manifest=manifest, messages=SealedJson.from_value(messages), tools=registry.tools,
                            estimated_input_tokens=256, reserved_output_tokens=128)
                        result = await adapter.decide(req)
                        if result.status != "ok":
                            raise RuntimeError(f"HTTP roundtrip failed: {result.error_code}")
                        requests.append({"request_sha256": req.sha256, "status": result.status,
                            "provider_response_id": result.provider_response_id,
                            "generation_availability": result.generation.availability,
                            "probability_kind": result.generation.probability_kind})
                        if index == 0:
                            messages += [assistant_message(result.raw_response.value()), {
                                "role": "tool", "tool_call_id": result.proposed_calls[0].call_id,
                                "content": '{"source":"synthetic","status":"ok"}'}]
                    try:
                        await wrong_key.generate(req)
                        raise AssertionError("wrong key unexpectedly accepted")
                    except PolicyHttpError as exc:
                        if exc.status_code != 401:
                            raise
                    changed = manifest.model_copy(update={"prompt_revision": "wrong-version"})
                    try:
                        await transport.generate(req.model_copy(update={"manifest": changed}))
                        raise AssertionError("wrong version unexpectedly accepted")
                    except PolicyHttpError as exc:
                        if exc.status_code != 409:
                            raise
                    if len(upstream_calls) != 2:
                        raise AssertionError("unexpected native calls")
                finally:
                    await transport.aclose()
                    await wrong_key.aclose()
        finally:
            await backend.aclose()
    return {"evidence_kind": "loopback_http_synthetic_upstream", "real_model_calls": 0,
        "game_input_dispatches": 0, "native_http_calls": len(upstream_calls), "rounds": requests,
        "checks": {"two_rounds": True, "wrong_key_401": True, "wrong_version_409": True,
                   "failures_no_upstream_call": True}, "budget": budget.summary()}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new evidence JSON file; never overwrites")
    args = parser.parse_args()
    evidence = asyncio.run(run())
    text = json.dumps(evidence, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(json.dumps({"evidence_kind": evidence["evidence_kind"], "native_http_calls": 2,
            "real_model_calls": 0, "checks": evidence["checks"], "output": str(args.output.resolve())}))
    else:
        print(text)


if __name__ == "__main__":
    main()
