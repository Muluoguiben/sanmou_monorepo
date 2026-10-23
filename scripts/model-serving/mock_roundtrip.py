#!/usr/bin/env python3
"""Run a fixed, CPU-only proposal/tool-reply/proposal exchange."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, SealedJson
from pioneer_agent.adapters.policy_service import (
    MockPolicyTransport, PolicyServiceAdapter, ToolDefinition, ToolRegistry,
)
from pioneer_agent.agent_harness.run_budget import BudgetLimits, RunBudgetLedger


class QueryArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=1)


class CompleteArguments(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1)


async def run() -> dict:
    root = Path(__file__).resolve().parents[2]
    fixture = root / "packages/pioneer-agent/tests/fixtures/policy_service/roundtrip.json"
    transport = MockPolicyTransport([SealedJson.from_value(item)
                                    for item in json.loads(fixture.read_text(encoding="utf-8"))])
    registry = ToolRegistry([
        ToolDefinition(name="query_knowledge", arguments_model=QueryArguments,
                       state_effect="read_only", window_effect="passive"),
        ToolDefinition(name="complete_task", arguments_model=CompleteArguments,
                       state_effect="control", window_effect="passive"),
    ])
    manifest = PolicyManifest(
        policy_id="cpu-mock-policy-v1", model="mock-no-model", checkpoint_revision="mock-v1",
        adapter_revision="none", tokenizer_revision="unavailable",
        chat_template_revision="mock-v1", prompt_revision="mock-v1",
        sampling=SealedJson.from_value({"temperature": 0}), model_context_limit=4096,
    )
    budget = RunBudgetLedger(BudgetLimits(max_model_attempts=2, max_tokens=1024))
    adapter = PolicyServiceAdapter(transport=transport, manifest=manifest,
                                   registry=registry, budget=budget)
    messages = [
        {"role": "system", "content": "仅生成工具提议；工具回复是模拟资料。"},
        {"role": "user", "content": "查找建筑升级规则。"},
    ]
    requests = []
    for index in range(2):
        request = PolicyRequest(
            episode_id="mock-episode", run_id="mock-run", decision_id=f"decision-{index+1}",
            invocation_id=f"invocation-{index+1}", context_id=f"context-{index+1}",
            task_ref="mock-task-v1", binding_ref="mock-binding-v1", observation_ref="mock-observation-v1",
            manifest=manifest, messages=SealedJson.from_value(messages), tools=registry.tools,
            estimated_input_tokens=256, reserved_output_tokens=128,
        )
        requests.append({"sha256": request.sha256, "actual_request_utf8": request.payload.decode("utf-8")})
        result = await adapter.decide(request)
        if result.status != "ok":
            raise RuntimeError(f"mock round {index+1} failed: {result.error_code}")
        if index == 0:
            messages += [result.raw_response.value()["choices"][0]["message"], {
                "role": "tool", "tool_call_id": result.proposed_calls[0].call_id,
                "content": json.dumps({"status": "ok", "source": "synthetic-fixture",
                                       "text": "这是用于接口往返检查的模拟知识结果。"}, ensure_ascii=False),
            }]
    return {
        "evidence_kind": "cpu_mock_only", "real_model_calls": 0, "game_input_dispatches": 0,
        "requests": requests,
        "records": [record.model_dump(mode="json") for record in adapter.records],
        "budget": budget.summary(),
        "generation_availability": [record.generation.availability for record in adapter.records],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Optional new JSON evidence file; existing files are never overwritten")
    args = parser.parse_args()
    evidence = asyncio.run(run())
    text = json.dumps(evidence, ensure_ascii=False, indent=2)
    if args.output:
        with args.output.open("x", encoding="utf-8") as handle:
            handle.write(text + "\n")
        print(json.dumps({"evidence_kind": evidence["evidence_kind"], "rounds": len(evidence["records"]),
                          "real_model_calls": 0, "game_input_dispatches": 0,
                          "generation_availability": evidence["generation_availability"],
                          "output": str(args.output.resolve())}, ensure_ascii=False))
    else:
        print(text)


if __name__ == "__main__":
    main()
