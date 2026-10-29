"""Bounded gateway resilience probes use a real gateway with a fake HTTP upstream."""
import asyncio
import hashlib
import json
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import httpx
from pioneer_agent.adapters.policy_http import SGLangChatBackend, assistant_message
from sanmou_common.policy_contracts import PolicyRequest, SealedJson, canonical_json
from test_policy_http import manifest, native_fixtures, request

ROOT=Path(__file__).resolve().parents[3]
spec=importlib.util.spec_from_file_location('gateway_resilience_probe',ROOT/'scripts/model-serving/gateway_resilience_probe.py')
probe=importlib.util.module_from_spec(spec);spec.loader.exec_module(probe)

class BlockingNative(httpx.AsyncBaseTransport):
    def __init__(self):
        self.running=False;self.release=asyncio.Event();self.calls=0
    async def handle_async_request(self, req):
        self.calls+=1;self.running=True
        try:
            trace=req.extensions.get('trace')
            if trace: await trace('http11.send_request_body.complete',{})
            await self.release.wait()
            return httpx.Response(200,json=native_fixtures()[0],headers={'content-type':'application/json'})
        finally:self.running=False

class ResilienceProbeTests(unittest.IsolatedAsyncioTestCase):
    async def case(self, mode):
        fake=BlockingNative(); rec=probe.Recorder()
        async def observe():return (int(fake.running),0)
        async with httpx.AsyncClient(transport=probe.TraceTransport(rec,fake)) as client:
            backend=probe.TrackedBackend(SGLangChatBackend(base_url='http://127.0.0.1:1',manifest=manifest(),
                api_key='native-key',client=client,timeout_seconds=20),rec)
            if mode=='concurrency':
                async def release():
                    while fake.calls==0: await asyncio.sleep(.001)
                    await asyncio.sleep(1.0); fake.release.set()
                releaser=asyncio.create_task(release())
            out=await probe.one_probe(mode,manifest(),request(),'gateway-key',backend,rec,observe,
                gateway_timeout=1.0 if mode=='timeout' else 4,native_observation_timeout=.8,idle_timeout=2)
            if mode=='concurrency': await releaser
        self.assertEqual(fake.calls,1)
        self.assertTrue(out['backend_idle_and_native_load_zero'])
        self.assertFalse(out['engine_abort_verified'])
        self.assertEqual(len([e for e in rec.events if e['kind']=='native_http_body_sent']),1)
        self.assertEqual(len([e for e in rec.events if e['kind']=='native_running_observed']),1)
        return out
    async def test_concurrency_only_dispatches_one(self):
        out=await self.case('concurrency');self.assertEqual(out['status'],503)
        self.assertEqual(out['gateway_counts']['accepted'],1)
    async def test_gateway_timeout_and_backend_cancel(self):
        out=await self.case('timeout');self.assertEqual(out['status'],504)
        self.assertEqual(out['gateway_counts']['timeout'],1)
    async def test_disconnect_cancels_backend_after_native_running(self):
        out=await self.case('disconnect');self.assertEqual(out['gateway_counts']['cancelled'],1)
    async def test_barrier_fails_closed_if_request_finishes_first(self):
        rec=probe.Recorder();task=asyncio.create_task(asyncio.sleep(0));await task
        async def observe():return (1,0)
        with self.assertRaisesRegex(RuntimeError,'finished_before_native'):
            await probe.wait_barrier(task,rec,'id',observe,.1)
    async def test_prompt_and_native_sampling_bind_before_network(self):
        base=request()
        prompt={'messages':base.messages.value(),'tools':base.tools.value()}
        digest=hashlib.sha256(canonical_json(prompt)).hexdigest()
        pinned=manifest().model_copy(update={'prompt_revision':'sha256:'+digest})
        bound=request(selected_manifest=pinned)
        calls=[]
        async def forbidden(req):
            calls.append(req);raise AssertionError('unexpected_network')
        async with httpx.AsyncClient(transport=httpx.MockTransport(forbidden)) as client:
            backend=SGLangChatBackend(base_url='http://127.0.0.1:1',manifest=pinned,client=client)
            self.assertEqual(probe.verify_request_binding(pinned,bound,backend,prompt),digest)
            assistant=assistant_message(native_fixtures()[0])
            second_messages=prompt['messages']+[assistant,{'role':'tool','tool_call_id':'http-call-1','content':'synthetic reply'}]
            second=PolicyRequest.from_wire(bound.model_copy(update={'messages':SealedJson.from_value(second_messages)}).to_wire())
            self.assertEqual(probe.verify_request_binding(pinned,second,backend,prompt),digest)
            bad_history=second.model_copy(update={'messages':SealedJson.from_value(
                second_messages[:-1]+[{'role':'tool','tool_call_id':'wrong','content':'synthetic reply'}])})
            with self.assertRaises(ValueError):
                probe.verify_request_binding(pinned,bad_history,backend,prompt)
            with self.assertRaisesRegex(ValueError,'prompt_binding_mismatch'):
                probe.verify_request_binding(pinned,bound,backend,{'messages':[{'role':'user','content':'different'}],'tools':prompt['tools']})
            changed=bound.model_copy(update={'messages':SealedJson.from_value([{'role':'user','content':'different'}])})
            with self.assertRaisesRegex(ValueError,'prompt_prefix_or_tools_mismatch'):
                probe.verify_request_binding(pinned,changed,backend,prompt)
            changed=bound.model_copy(update={'tools':SealedJson.from_value([])})
            with self.assertRaisesRegex(ValueError,'prompt_prefix_or_tools_mismatch'):
                probe.verify_request_binding(pinned,changed,backend,prompt)
            class WrongSampling:
                def request_payload(self, req):
                    payload=json.loads(backend.request_payload(req))
                    payload['temperature']=0.5
                    return canonical_json(payload)
            with self.assertRaisesRegex(ValueError,'sampling_binding_mismatch'):
                probe.verify_request_binding(pinned,bound,WrongSampling(),prompt)
        self.assertEqual(calls,[])

    def test_native_receipt_binding_and_mismatches(self):
        evidence=ROOT/'docs/test-reports/2026-10-29/mac-colab-gateway'
        receipt_bytes=(evidence/'runtime-receipt.json').read_bytes()
        pinned=probe.PolicyManifest.model_validate_json((evidence/'policy-manifest.json').read_bytes())
        negatives=json.loads((evidence/'negative-probes.json').read_bytes())
        bound=PolicyRequest.from_wire(negatives['probes'][0]['request_payload'])
        digest=hashlib.sha256(receipt_bytes).hexdigest()
        port=json.loads(receipt_bytes)['public_config']['port']
        upstream=f'http://127.0.0.1:{port}'
        self.assertEqual(probe.verify_native_binding(pinned,bound,receipt_bytes,upstream),digest)
        self.assertEqual(probe.verify_native_binding(pinned,bound,receipt_bytes,f'http://localhost:{port}'),digest)
        for bad in (f'http://127.0.0.1:{port+1}',f'http://127.0.0.2:{port}',f'http://127.0.0.1:{port}/wrong',f'http://user@127.0.0.1:{port}'):
            with self.assertRaisesRegex(ValueError,'native_endpoint_binding_mismatch'):
                probe.verify_native_binding(pinned,bound,receipt_bytes,bad)
        with self.assertRaisesRegex(ValueError,'native_receipt_hash_mismatch'):
            probe.verify_native_binding(pinned,bound,receipt_bytes+b' ',upstream)
        receipt=json.loads(receipt_bytes);receipt['sampling']['temperature']=0.5
        changed=canonical_json(receipt)
        rebound=bound.model_copy(update={'binding_ref':hashlib.sha256(changed).hexdigest()})
        with self.assertRaisesRegex(ValueError,'native_manifest_mismatch'):
            probe.verify_native_binding(pinned,rebound,changed,upstream)
        broken=json.loads(receipt_bytes);broken.pop('checks')
        changed=canonical_json(broken)
        rebound=bound.model_copy(update={'binding_ref':hashlib.sha256(changed).hexdigest()})
        with self.assertRaises(ValueError):
            probe.verify_native_binding(pinned,rebound,changed,upstream)

    async def test_waiting_request_fails_closed_before_dispatch(self):
        rec=probe.Recorder()
        async def observe():return (0,1)
        with self.assertRaisesRegex(RuntimeError,'server_not_idle'):
            await probe.one_probe('concurrency',manifest(),request(),'gateway-key',object(),rec,observe)
        self.assertEqual(rec.events,[])
    def test_cancellation_order_requires_both_events_after_running(self):
        rec=probe.Recorder()
        for kind in ('native_running_observed','backend_exit'):
            rec.record(kind,'id')
        with self.assertRaisesRegex(RuntimeError,'backend_cancel_order_not_observed'):
            probe.require_cancellation_order(rec,'id')
        rec.events=[]
        for kind in ('backend_cancelled','native_running_observed','backend_exit'):
            rec.record(kind,'id')
        with self.assertRaisesRegex(RuntimeError,'backend_cancel_order_not_observed'):
            probe.require_cancellation_order(rec,'id')
        rec.events=[]
        for kind in ('native_running_observed','backend_cancelled','backend_exit'):
            rec.record(kind,'id')
        self.assertTrue(probe.require_cancellation_order(rec,'id'))
    @unittest.skipUnless(hasattr(os, 'getuid'), 'POSIX private-directory permissions required')
    def test_output_path_rejects_existing_or_shared_parent(self):
        with tempfile.TemporaryDirectory() as name:
            parent=Path(name).resolve(); out=parent/'result.json'
            self.assertEqual(probe.output_path(str(out)),out)
            out.write_text('existing')
            with self.assertRaisesRegex(ValueError,'output_already_exists'):
                probe.output_path(str(out))
            shared=parent/'shared';shared.mkdir(mode=0o755)
            with self.assertRaisesRegex(ValueError,'output_requires_private_directory'):
                probe.output_path(str(shared/'result.json'))

    def test_load_gauges_reject_missing_and_ambiguous(self):
        self.assertEqual(probe.load_counts({'loads':[{'num_running_reqs':1,'num_waiting_reqs':0}]}),(1,0))
        for value in ({},{'num_running_reqs':True,'num_waiting_reqs':0},
                      [{'num_running_reqs':1,'num_waiting_reqs':0},{'num_running_reqs':0,'num_waiting_reqs':0}]):
            with self.assertRaises(ValueError):probe.load_counts(value)

if __name__=='__main__':unittest.main()
