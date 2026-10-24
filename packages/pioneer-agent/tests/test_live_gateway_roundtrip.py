"""Real loopback runner tests with explicitly synthetic model responses.

The receipt fixture is schema-valid metadata, not a new runtime/GPU check.
These tests never load weights, contact Colab, or dispatch game input.
"""
from __future__ import annotations

import asyncio
import hashlib
import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlsplit

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

from sanmou_common.policy_contracts import canonical_json, decode_json
from test_native_runtime_manifest import make_receipt_fixture


ROOT = Path(__file__).resolve().parents[3]
SCRIPT_DIR = ROOT / "scripts/model-serving"
with patch.object(sys, "path", [str(SCRIPT_DIR), *sys.path]):
    import native_runtime_manifest as native
    spec = importlib.util.spec_from_file_location("live_gateway_runner_under_test", SCRIPT_DIR / "live_gateway_roundtrip.py")
    runner = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(runner)

GATEWAY_KEY = "synthetic-gateway-secret-2f6e7b90"
UPSTREAM_KEY = "synthetic-native-secret-a48cc314"


def artifact(raw: bytes) -> dict:
    return {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}


def fixture_receipt(port: int) -> dict:
    receipt = make_receipt_fixture()
    receipt["public_config"]["port"] = port
    receipt["public_config_sha256"] = hashlib.sha256(canonical_json(receipt["public_config"])).hexdigest()
    receipt["public_config_artifact"] = artifact(canonical_json(receipt["public_config"]))
    receipt["prompt_sha256"] = runner.scenario_prompt_sha256()
    receipt["sampling"] = runner.load_scenario()["sampling"]
    return receipt


def native_response(number: int, model: str) -> dict:
    first = number == 1
    arguments = {"query": "gateway_roundtrip_check"} if first else {"reason": "Fixture received."}
    return {"id": f"synthetic-response-{number}", "object": "chat.completion", "model": model,
        "choices": [{"index": 0, "finish_reason": "tool_calls", "message": {
            "role": "assistant", "content": "", "reasoning_content": None,
            "tool_calls": [{"id": f"synthetic-call-{number}", "index": 0, "type": "function",
                "function": {"name": "query_knowledge" if first else "complete_task",
                             "arguments": canonical_json(arguments).decode()}}]},
            "prompt_token_ids": [10, 11, 12], "response_token_ids": [20, 21, 22, 23],
            "meta_info": {"output_token_logprobs": [[-0.1, token, "synthetic"] for token in [20, 21, 22, 23]]}}],
        "usage": {"prompt_tokens": 3, "completion_tokens": 4, "total_tokens": 7}}


class LiveGatewayRunnerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        # Retain task-created test directories for audit; no recursive cleanup.
        self.temp = Path(tempfile.mkdtemp(prefix="sanmou-live-runner-test-")).resolve()
        self.env = patch.dict(os.environ, {"POLICY_GATEWAY_API_KEY": GATEWAY_KEY,
                                          "SGLANG_API_KEY": UPSTREAM_KEY})
        self.env.start()
        self.addCleanup(self.env.stop)

    def inputs(self, receipt, *, manifest=None):
        binding_path = self.temp / "runtime-receipt.json"
        manifest_path = self.temp / "policy-manifest.json"
        binding_path.write_bytes(canonical_json(receipt))
        manifest_path.write_text((manifest or native.build_native_policy_manifest(receipt)).model_dump_json())
        return {"binding_path": binding_path, "manifest_path": manifest_path}

    def verify_index(self, directory):
        index = decode_json((directory / "artifact-index.json").read_bytes())
        indexed = set()
        for entry in index["files"]:
            path = directory / entry["path"]
            payload = path.read_bytes()
            self.assertEqual(len(payload), entry["byte_length"])
            self.assertEqual(hashlib.sha256(payload).hexdigest(), entry["sha256"])
            self.assertNotIn(GATEWAY_KEY.encode(), payload)
            self.assertNotIn(UPSTREAM_KEY.encode(), payload)
            indexed.add(entry["path"])
        self.assertEqual({path.name for path in directory.iterdir()}, indexed | {"artifact-index.json"})

    async def exercise(self, mutate=None, *, status=200):
        app = FastAPI()
        seen = []
        @app.post("/v1/chat/completions")
        async def generate(incoming: Request):
            self.assertEqual(incoming.headers.get("authorization"), "Bearer " + UPSTREAM_KEY)
            payload = await incoming.json()
            seen.append(payload)
            raw = native_response(len(seen), payload["model"])
            if mutate:
                mutate(raw)
            return Response(canonical_json(raw), status_code=status, media_type="application/json")
        async with runner.gateway_server(app) as url:
            options = self.inputs(fixture_receipt(urlsplit(url).port))
            output = self.temp / "evidence"
            result = await runner.run(**options, upstream=url, output=output,
                                      timeout_seconds=2.0, budget_seconds=420.0, synthetic_upstream=True)
        return result, output, seen

    async def test_two_real_http_hops_bind_receipt_capture_actual_bytes_and_reject_three_probes(self):
        result, output, seen = await self.exercise()
        self.assertEqual(result["status"], "passed", result)
        self.assertEqual(result["upstream_mode"], "synthetic")
        self.assertEqual(result["game_input_dispatches"], 0)
        self.assertFalse(result["cross_machine_connection_verified"])
        self.assertEqual(len(seen), 2)
        self.assertEqual(result["reserve_calls"], 2)
        self.assertEqual(result["settle_calls"], 2)
        self.assertEqual(result["budget"]["pending"], 0)
        self.assertEqual(result["budget"]["charged_tokens"], 14)
        for field in ("native_generate_calls", "native_post_calls", "native_http_dispatches"):
            self.assertEqual(result[field], 2)
        self.assertEqual(result["gateway_counts"]["accepted"], 2)
        self.assertEqual(result["gateway_counts"]["succeeded"], 2)
        for probe in ("missing_key", "wrong_key", "wrong_manifest"):
            self.assertTrue(result["checks"][probe]["passed"])
            self.assertEqual(result["checks"][probe]["native_counts_after"], [0, 0, 0])
        attempts = decode_json((output / "http-attempts.json").read_bytes())
        self.assertEqual([row["status_code"] for row in attempts["gateway"]], [401, 401, 409, 200, 200])
        for number in (1, 2):
            post = (output / f"native.post.{number:03d}.request.body").read_bytes()
            dispatched = (output / f"native.http.{number:03d}.request.body").read_bytes()
            self.assertEqual(post, dispatched)
            self.assertEqual(decode_json(dispatched), seen[number - 1])
            envelope = (output / f"round.{number}.request.json").read_bytes()
            self.assertEqual(envelope, (output / f"gateway.http.{number+3:03d}.request.body").read_bytes())
            raw = decode_json((output / f"native.http.{number:03d}.response.body").read_bytes())
            self.assertEqual(raw["choices"][0]["prompt_token_ids"], [10, 11, 12])
            record = decode_json((output / f"round.{number}.result.json").read_bytes())
            self.assertEqual(record["generation"]["probability_kind"], "unavailable")
        self.assertEqual(seen[1]["messages"][-1]["role"], "tool")
        self.assertEqual(decode_json(seen[1]["messages"][-1]["content"])["source"], "synthetic_tool_fixture")
        self.verify_index(output)

    async def test_manifest_receipt_mismatch_stops_before_network(self):
        receipt = fixture_receipt(30000)
        manifest = native.build_native_policy_manifest(receipt).model_copy(update={"checkpoint_revision": "wrong"})
        result = await runner.run(**self.inputs(receipt, manifest=manifest), upstream="http://127.0.0.1:30000",
                                  output=self.temp / "evidence", synthetic_upstream=True)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "native_runtime_binding_mismatch")
        self.assertEqual(result["native_http_dispatches"], 0)
        self.assertEqual(result["reserve_calls"], 0)
        self.verify_index(self.temp / "evidence")

    async def test_wrong_endpoint_port_stops_before_network(self):
        result = await runner.run(**self.inputs(fixture_receipt(30000)), upstream="http://127.0.0.1:30001",
                                  output=self.temp / "evidence", synthetic_upstream=True)
        self.assertEqual(result["error_code"], "upstream_endpoint_binding_mismatch")
        self.assertEqual(result["native_http_dispatches"], 0)

    async def test_wrong_scenario_binding_stops_before_network(self):
        receipt = fixture_receipt(30000)
        receipt["prompt_sha256"] = hashlib.sha256(b"different scenario").hexdigest()
        result = await runner.run(**self.inputs(receipt), upstream="http://127.0.0.1:30000",
                                  output=self.temp / "evidence", synthetic_upstream=True)
        self.assertEqual(result["error_code"], "scenario_prompt_binding_mismatch")
        self.assertEqual(result["native_http_dispatches"], 0)

    async def test_parse_failure_preserves_native_original_and_known_budget_usage(self):
        result, output, seen = await self.exercise(lambda raw: raw["choices"][0].update(finish_reason="length"))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "policy_round_failed")
        self.assertEqual(len(seen), 1)
        record = decode_json((output / "round.1.result.json").read_bytes())
        self.assertEqual(record["error_code"], "incomplete_generation")
        self.assertEqual(record["usage"]["output_tokens"], 4)
        self.assertEqual(result["budget"]["charged_tokens"], 7)
        self.assertEqual(decode_json((output / "native.http.001.response.body").read_bytes())["choices"][0]["finish_reason"], "length")
        self.verify_index(output)

    async def test_missing_token_usage_or_logprob_readback_cannot_pass(self):
        for missing in ("prompt_token_ids", "response_token_ids", "usage", "meta_info"):
            with self.subTest(missing=missing):
                def mutate(raw):
                    if missing == "usage":
                        raw.pop("usage")
                    else:
                        raw["choices"][0].pop(missing)
                # Each run gets fresh input/output names without overwriting.
                self.temp = Path(tempfile.mkdtemp(prefix="sanmou-live-runner-missing-")).resolve()
                result, output, seen = await self.exercise(mutate)
                self.assertEqual(result["status"], "failed")
                self.assertIn(result["error_code"], {"native_token_or_usage_readback_missing", "native_logprob_readback_missing"})
                self.assertEqual(len(seen), 1)
                self.assertTrue((output / "round.1.result.json").exists())
                self.verify_index(output)

    async def test_non_200_original_is_captured_without_retry(self):
        result, output, seen = await self.exercise(status=503)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(seen), 1)
        attempts = decode_json((output / "http-attempts.json").read_bytes())
        self.assertEqual(attempts["native"][0]["status_code"], 503)
        self.assertTrue(attempts["native"][0]["response_complete"])
        self.assertEqual(decode_json((output / "native.http.001.response.body").read_bytes())["id"], "synthetic-response-1")
        self.assertEqual(result["reserve_calls"], 1)
        self.assertEqual(result["settle_calls"], 1)
        self.assertEqual(result["budget"]["unknown_token_attempts"], 1)
        self.verify_index(output)

    async def test_response_containing_key_is_not_saved_and_stops_generation(self):
        result, output, seen = await self.exercise(lambda raw: raw.update(leaked=GATEWAY_KEY))
        self.assertEqual(result["status"], "failed")
        self.assertEqual(result["error_code"], "evidence_recording_failed")
        self.assertEqual(len(seen), 1)
        for path in output.iterdir():
            self.assertNotIn(GATEWAY_KEY.encode(), path.read_bytes())
        self.assertFalse((output / "native.http.001.response.body").exists())

    async def test_index_failure_cannot_leave_success_summary(self):
        original = runner.EvidenceWriter.json
        def fail_index(writer, name, value):
            if name == "artifact-index.json":
                raise runner.RunnerFailure("artifact_write_failed")
            return original(writer, name, value)
        with patch.object(runner.EvidenceWriter, "json", fail_index):
            with self.assertRaises(runner.RunnerFailure):
                await self.exercise()
        self.assertFalse((self.temp / "evidence/summary.json").exists())

    async def test_summary_fsync_after_write_failure_never_publishes_final_success(self):
        original_write = runner.EvidenceWriter.write
        def fail_pending_fsync(writer, name, payload, **kwargs):
            if name == "summary.pending.json":
                with patch.object(runner.os, "fsync", side_effect=OSError("synthetic fsync failure")):
                    return original_write(writer, name, payload, **kwargs)
            return original_write(writer, name, payload, **kwargs)
        with patch.object(runner.EvidenceWriter, "write", fail_pending_fsync):
            with self.assertRaises(runner.RunnerFailure):
                await self.exercise()
        pending = self.temp / "evidence/summary.pending.json"
        self.assertTrue(pending.exists())
        self.assertEqual(decode_json(pending.read_bytes())["status"], "passed")
        self.assertFalse((self.temp / "evidence/summary.json").exists())
        self.assertFalse((self.temp / "evidence/artifact-index.json").exists())

    async def test_native_timeout_retains_partial_response_and_settles_once(self):
        app = FastAPI()
        calls = []
        stopped = asyncio.Event()
        @app.post("/v1/chat/completions")
        async def generate():
            calls.append(1)
            async def partial():
                try:
                    yield b'{"partial_native_body":'
                    await asyncio.Event().wait()
                finally:
                    stopped.set()
            return StreamingResponse(partial(), media_type="application/json")
        async with runner.gateway_server(app) as url:
            result = await runner.run(**self.inputs(fixture_receipt(urlsplit(url).port)),
                upstream=url, output=self.temp / "evidence", timeout_seconds=0.1,
                budget_seconds=420.0, synthetic_upstream=True)
            await asyncio.wait_for(stopped.wait(), timeout=1)
        self.assertEqual(result["status"], "failed")
        self.assertEqual(len(calls), 1)
        self.assertEqual(result["reserve_calls"], 1)
        self.assertEqual(result["settle_calls"], 1)
        self.assertEqual(result["budget"]["pending"], 0)
        self.assertEqual(result["budget"]["unknown_token_attempts"], 1)
        output = self.temp / "evidence"
        self.assertEqual((output / "native.http.001.response.body").read_bytes(), b'{"partial_native_body":')
        attempts = decode_json((output / "http-attempts.json").read_bytes())
        self.assertFalse(attempts["native"][0]["response_complete"])
        self.assertEqual(attempts["native_posts"][0]["error_code"], "http_timeout")
        self.verify_index(output)

    async def test_response_capture_byte_limit_is_bounded_even_for_non_200(self):
        app = FastAPI()
        @app.post("/v1/policy/decide")
        async def generate():
            return Response(b"x" * 100, status_code=503, media_type="application/json")
        writer = runner.EvidenceWriter(self.temp / "evidence", ())
        audit = runner.AuditedHttpTransport("gateway", writer, max_bytes=16)
        try:
            async with runner.gateway_server(app) as url:
                async with httpx.AsyncClient(transport=audit, trust_env=False) as client:
                    with self.assertRaisesRegex(runner.PolicyHttpError, "response_too_large"):
                        await client.post(url + "/v1/policy/decide", content=b"{}")
            self.assertEqual(len(audit.attempts), 1)
            self.assertEqual(audit.attempts[0]["status_code"], 503)
            self.assertFalse(audit.attempts[0]["response_complete"])
            self.assertEqual((self.temp / "evidence/gateway.http.001.response.body").read_bytes(), b"x" * 16)
        finally:
            writer.close()

    def test_prompt_hash_and_sampling_are_stable(self):
        self.assertEqual(runner.scenario_prompt_sha256(), "725ca696214f9e2c924582772b434f7a88e9f5cad2e68f63f8fca46d6dd28674")
        self.assertEqual(set(runner.load_scenario()["sampling"]), {
            "temperature", "top_p", "top_k", "min_p", "seed", "repetition_penalty",
            "frequency_penalty", "presence_penalty", "stop"})

    def test_existing_output_is_never_modified(self):
        destination = self.temp / "existing"
        destination.mkdir(mode=0o700)
        sentinel = destination / "sentinel"
        sentinel.write_bytes(b"preserve")
        with self.assertRaises(FileExistsError):
            runner.EvidenceWriter(destination, ())
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        self.assertEqual([item.name for item in destination.iterdir()], ["sentinel"])

    def test_directory_swap_at_open_is_rejected_without_writing_sentinel_directory(self):
        destination, replacement = self.temp / "output", self.temp / "replacement"
        replacement.mkdir(mode=0o700)
        (replacement / "sentinel").write_bytes(b"preserve")
        original = os.open
        def swap(path, flags, *args, **kwargs):
            if path == destination.name and flags & os.O_DIRECTORY:
                destination.rename(self.temp / "created-directory-retained")
                replacement.rename(destination)
            return original(path, flags, *args, **kwargs)
        with patch.object(runner.os, "open", swap):
            with self.assertRaisesRegex(runner.RunnerFailure, "output_directory_changed"):
                runner.EvidenceWriter(destination, ())
        self.assertEqual([item.name for item in destination.iterdir()], ["sentinel"])
        self.assertEqual((destination / "sentinel").read_bytes(), b"preserve")

    def test_writable_by_other_users_parent_is_rejected(self):
        parent = self.temp / "unsafe-parent"
        parent.mkdir(mode=0o777)
        parent.chmod(0o777)
        with self.assertRaisesRegex(runner.RunnerFailure, "unsafe_output_parent"):
            runner.EvidenceWriter(parent / "output", ())
        self.assertFalse((parent / "output").exists())


if __name__ == "__main__":
    unittest.main()
