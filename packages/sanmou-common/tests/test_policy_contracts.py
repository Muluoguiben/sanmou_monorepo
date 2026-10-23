"""Wire contract tests independent of serving, game clients, and model libraries."""
import hashlib
import unittest

from pydantic import ValidationError

from sanmou_common.policy_contracts import (
    GenerationRecord, PolicyCallResult, PolicyManifest, PolicyRequest,
    PolicyTransportResponse, PolicyUsage, ProposedCall, SealedJson, canonical_json,
    decode_json,
    seal_knowledge_answer,
)
from sanmou_common.ports import Evidence, KnowledgeAnswer


def manifest(**changes):
    values = dict(policy_id="fixture-policy-v1", model="fixture-model",
                  checkpoint_revision="fixture-weights", adapter_revision="none",
                  tokenizer_revision="fixture-tokenizer", chat_template_revision="fixture-template",
                  prompt_revision="fixture-prompt", sampling=SealedJson.from_value({"temperature": 1.0}),
                  model_context_limit=128)
    values.update(changes)
    return PolicyManifest(**values)


def request(**changes):
    values = dict(episode_id="e1", run_id="r1", decision_id="d1", invocation_id="i1",
                  context_id="c1", task_ref="task:1", binding_ref="role:1", observation_ref="obs:1",
                  manifest=manifest(), messages=SealedJson.from_value([{"role": "user", "content": "建议下一步"}]),
                  tools=SealedJson.from_value([]), estimated_input_tokens=32, reserved_output_tokens=16)
    values.update(changes)
    return PolicyRequest(**values)


class PolicyContractTests(unittest.TestCase):
    def test_existing_knowledge_port_snapshot_preserves_actual_content(self):
        answer = KnowledgeAnswer(answer="模拟答案", evidence=(Evidence(
            entry_id="e1", topic="模拟", domain="building", summary="当时实际提供的资料",
            source_ref="fixture:1", confidence=0.5),), confidence=0.5, coverage="partial")
        snapshot = seal_knowledge_answer(answer, query="模拟问题", kb_revision="kb1", retriever_revision="lexical1")
        self.assertEqual(snapshot.value()["answer"]["evidence"][0]["summary"], answer.evidence[0].summary)
        self.assertEqual(snapshot.value()["answer"]["coverage"], "partial")
        req = request(knowledge=snapshot)
        changed = seal_knowledge_answer(answer, query="模拟问题", kb_revision="kb2", retriever_revision="lexical1")
        self.assertNotEqual(req.sha256, request(knowledge=changed).sha256)
        with self.assertRaises(ValueError):
            seal_knowledge_answer(answer, query="模拟问题", kb_revision="", retriever_revision="lexical1")

    def test_seal_detaches_and_json_roundtrips(self):
        source = {"a": [{"value": 1}], "中文": "内容"}
        sealed = SealedJson.from_value(source)
        source["a"][0]["value"] = 9
        view = sealed.value()
        view["a"][0]["value"] = 8
        self.assertEqual(sealed.value()["a"][0]["value"], 1)
        self.assertEqual(SealedJson.model_validate_json(sealed.model_dump_json()), sealed)

    def test_reject_invalid_json_and_hash(self):
        for payload in (b'{ "a":1}', b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}'):
            with self.subTest(payload=payload), self.assertRaises(ValueError):
                SealedJson(payload=payload, sha256=hashlib.sha256(payload).hexdigest())
        with self.assertRaises(ValueError):
            SealedJson(payload=b"{}", sha256="0" * 64)
        for value in ({1: "a"}, {"a": float("nan")}, {"a": float("inf")}, {"a": object()}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                SealedJson.from_value(value)

    def test_canonical_order(self):
        self.assertEqual(canonical_json({"b": 2, "a": 1}), canonical_json({"a": 1, "b": 2}))
        with self.assertRaises(ValueError):
            decode_json('{"a":1,"a":2}')

    def test_request_exact_bytes_and_roundtrip(self):
        req = request()
        self.assertEqual(req.sha256, hashlib.sha256(req.payload).hexdigest())
        self.assertEqual(decode_json(req.payload)["messages"], req.messages.value())
        self.assertEqual(PolicyRequest.model_validate_json(req.model_dump_json()).payload, req.payload)
        for changes in ({"binding_ref": "role:2"}, {"observation_ref": "obs:2"},
                        {"manifest": manifest(prompt_revision="new")},
                        {"knowledge": SealedJson.from_value({"kb_version": "k1", "answer": "实际内容"})}):
            with self.subTest(changes=changes):
                self.assertNotEqual(request(**changes).sha256, req.sha256)

    def test_context_limit_and_strict_counts(self):
        for changes in ({"estimated_input_tokens": 120}, {"reserved_output_tokens": 0},
                        {"estimated_input_tokens": True}, {"estimated_input_tokens": "32"}):
            with self.subTest(changes=changes), self.assertRaises(ValidationError):
                request(**changes)

    def test_complete_parallel_tool_history(self):
        calls = [{"id": ident, "type": "function", "function": {"name": "query", "arguments": "{}"}}
                 for ident in ("call1", "call2")]
        history = [{"role": "user", "content": "查资料"}, {"role": "assistant", "tool_calls": calls},
                   {"role": "tool", "tool_call_id": "call1", "content": "first"},
                   {"role": "tool", "tool_call_id": "call2", "content": "second"}]
        self.assertEqual(request(messages=SealedJson.from_value(history)).messages.value(), history)
        for bad in (history[:-1], history[2:], history + [history[-1]],
                    history[:2] + [{"role": "user", "content": "新问题"}],
                    history[:2] + list(reversed(history[2:])),
                    [{"role": "user", "content": "x", "tool_calls": calls}]):
            with self.subTest(history=bad), self.assertRaises(ValueError):
                request(messages=SealedJson.from_value(bad))

    def test_tool_definitions(self):
        tool = {"type": "function", "function": {"name": "query", "parameters": {"type": "object"}}}
        request(tools=SealedJson.from_value([tool]))
        for bad in ([tool, tool], [{"type": "function", "function": {"name": "query"}}], {}):
            with self.subTest(tools=bad), self.assertRaises(ValueError):
                request(tools=SealedJson.from_value(bad))

    def test_generation_alignment_and_unavailable(self):
        record = GenerationRecord(input_token_ids=(1, 2), response_token_ids=(3, 4),
                                  response_logprobs=(-0.1, -0.2), policy_token_mask=(1, 1),
                                  probability_kind="sampling", finish_reason="stop")
        self.assertEqual(record.availability, "complete")
        self.assertEqual(GenerationRecord(finish_reason="stop").availability, "unavailable")
        self.assertEqual(GenerationRecord.model_validate_json(record.model_dump_json()), record)
        for changes in ({"response_logprobs": (-0.1,)}, {"response_logprobs": (float("nan"), -0.2)},
                        {"response_logprobs": (0.1, -0.2)}, {"response_token_ids": (True, 4)},
                        {"probability_kind": "unavailable"}, {"policy_token_mask": (1, 2)},
                        {"policy_token_mask": (True, 1)}):
            values = record.model_dump()
            values.update(changes)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                GenerationRecord(**values)

    def test_failure_has_no_proposals(self):
        proposal = ProposedCall(call_id="call1", tool_name="query", arguments=SealedJson.from_value({}))
        values = dict(invocation_id="i1", request_sha256="0" * 64)
        PolicyCallResult(**values, status="ok", proposed_calls=(proposal,))
        for extra in ({"status": "ok"}, {"status": "blocked"},
                      {"status": "failed", "error_code": "parse_error", "proposed_calls": (proposal,)}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                PolicyCallResult(**values, **extra)

    def test_unknown_envelope_fields_rejected(self):
        for cls, value in ((PolicyUsage, {"input_tokens": 1, "role": "admin"}),
                           (PolicyManifest, {**manifest().model_dump(), "execution_authority": "all"}),
                           (PolicyRequest, {**request().model_dump(), "executable": True})):
            with self.subTest(cls=cls), self.assertRaises(ValueError):
                cls(**value)

    def test_response_binding_requires_hashes(self):
        req = request()
        response = PolicyTransportResponse(invocation_id=req.invocation_id, request_sha256=req.sha256,
                                           manifest_sha256=req.manifest.sha256, provider_response_id="p1",
                                           raw_response=SealedJson.from_value({"choices": []}))
        self.assertEqual(PolicyTransportResponse.model_validate_json(response.model_dump_json()), response)
        with self.assertRaises(ValueError):
            PolicyTransportResponse(**{**response.model_dump(), "manifest_sha256": "unavailable"})


if __name__ == "__main__":
    unittest.main()
