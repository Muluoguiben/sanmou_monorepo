#!/usr/bin/env python3
"""Bounded real-HTTP gateway probes; engine cancellation needs separate evidence.

Use a dedicated, idle single-model SGLang server. /v1/loads must expose a
single unambiguous running and waiting request gauges. A nonzero gauge after HTTP body
transmission is an isolation-based admission observation, not a native RID
or proof that cancellation stops decoding. No prompts, bodies, or keys are
written. This tool never allocates or stops a runtime or model service.
"""
from __future__ import annotations
import argparse
import asyncio
from contextlib import asynccontextmanager
import contextvars
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import stat
import time
from urllib.parse import urlsplit
import httpx
import uvicorn
from pioneer_agent.adapters.policy_http import SGLangChatBackend
from pioneer_agent.app.policy_gateway import create_app
from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, canonical_json, decode_json

_CURRENT = contextvars.ContextVar('probe_invocation', default='')

class Recorder:
    def __init__(self):
        self.events = []
        self.sent = {}
        self.active = set()
    def record(self, kind, invocation):
        self.events.append({'kind': kind, 'invocation': invocation, 'monotonic': time.monotonic()})
    def sent_event(self, invocation):
        return self.sent.setdefault(invocation, asyncio.Event())

class TraceTransport(httpx.AsyncBaseTransport):
    def __init__(self, recorder, inner=None):
        self.recorder = recorder
        self.inner = inner or httpx.AsyncHTTPTransport(retries=0)
    async def handle_async_request(self, request):
        invocation = _CURRENT.get()
        previous = request.extensions.get('trace')
        async def trace(name, info):
            if previous is not None:
                await previous(name, info)
            if name in ('http11.send_request_body.complete', 'http2.send_request_body.complete'):
                self.recorder.record('native_http_body_sent', invocation)
                self.recorder.sent_event(invocation).set()
        request.extensions['trace'] = trace
        return await self.inner.handle_async_request(request)
    async def aclose(self):
        await self.inner.aclose()

class TrackedBackend:
    def __init__(self, backend, recorder):
        self.backend, self.recorder = backend, recorder
    async def generate(self, request):
        invocation = request.invocation_id
        self.recorder.active.add(invocation)
        self.recorder.record('backend_enter', invocation)
        token = _CURRENT.set(invocation)
        try:
            result = await self.backend.generate(request)
            self.recorder.record('backend_return', invocation)
            return result
        except asyncio.CancelledError:
            self.recorder.record('backend_cancelled', invocation)
            raise
        except Exception:
            self.recorder.record('backend_error', invocation)
            raise
        finally:
            _CURRENT.reset(token)
            self.recorder.active.discard(invocation)
            self.recorder.record('backend_exit', invocation)

@asynccontextmanager
async def loopback(app):
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0)); sock.listen(128)
    server = uvicorn.Server(uvicorn.Config(app, host='127.0.0.1', port=sock.getsockname()[1],
        access_log=False, log_level='critical', lifespan='off'))
    task = asyncio.create_task(server.serve(sockets=[sock]))
    try:
        async with asyncio.timeout(10):
            while not server.started:
                if task.done(): await task
                await asyncio.sleep(.01)
        yield f'http://127.0.0.1:{sock.getsockname()[1]}'
    finally:
        server.should_exit = True
        try: await asyncio.wait_for(task, 10)
        finally: sock.close()

def load_counts(payload):
    """Require exactly one valid running and waiting count, failing closed."""
    values={'num_running_reqs': [], 'num_waiting_reqs': []}
    def visit(obj):
        if isinstance(obj, dict):
            for k,v in obj.items():
                if k in values:
                    if type(v) is not int or v < 0: raise ValueError('invalid_load_gauge')
                    values[k].append(v)
                else: visit(v)
        elif isinstance(obj, list):
            for x in obj: visit(x)
    visit(payload)
    if any(len(v)!=1 for v in values.values()):
        raise ValueError('missing_or_ambiguous_load_gauge')
    return values['num_running_reqs'][0], values['num_waiting_reqs'][0]

def require_cancellation_order(recorder, invocation):
    kinds=[event['kind'] for event in recorder.events if event['invocation']==invocation]
    try:
        running=kinds.index('native_running_observed')
        cancelled=kinds.index('backend_cancelled',running+1)
        exited=kinds.index('backend_exit',cancelled+1)
    except ValueError:
        raise RuntimeError('backend_cancel_order_not_observed') from None
    return running < cancelled < exited

def verify_native_binding(manifest, request, receipt_bytes, upstream):
    """Verify saved native receipt and full-byte request binding; no live attestation."""
    digest=hashlib.sha256(receipt_bytes).hexdigest()
    if request.binding_ref != digest:
        raise ValueError('native_receipt_hash_mismatch')
    spec=importlib.util.spec_from_file_location('resilience_native_manifest',
        Path(__file__).with_name('native_runtime_manifest.py'))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    receipt=decode_json(receipt_bytes)
    rebuilt=module.build_native_policy_manifest(receipt)
    parsed=urlsplit(upstream)
    if (parsed.scheme!='http' or parsed.hostname not in {receipt['public_config']['host'],'localhost'}
            or parsed.port != receipt['public_config']['port']
            or parsed.username or parsed.password or parsed.query or parsed.fragment
            or parsed.path not in ('','/')):
        raise ValueError('native_endpoint_binding_mismatch')
    if rebuilt.sha256 != manifest.sha256 or request.manifest.sha256 != manifest.sha256:
        raise ValueError('native_manifest_mismatch')
    return digest

def verify_request_binding(manifest, request, native_backend, prompt_fixture):
    """Validate bound initial prompt, history prefix, and native mapping without I/O."""
    request=PolicyRequest.from_wire(request.to_wire())
    if request.manifest.sha256 != manifest.sha256:
        raise ValueError('manifest_mismatch')
    if (not isinstance(prompt_fixture,dict) or set(prompt_fixture)!={'messages','tools'}
            or not isinstance(prompt_fixture['messages'],list) or not prompt_fixture['messages']
            or not isinstance(prompt_fixture['tools'],list)):
        raise ValueError('invalid_prompt_fixture')
    digest=hashlib.sha256(canonical_json(prompt_fixture)).hexdigest()
    if manifest.prompt_revision != 'sha256:'+digest:
        raise ValueError('prompt_binding_mismatch')
    messages=request.messages.value(); tools=request.tools.value()
    if (len(messages)<len(prompt_fixture['messages'])
            or canonical_json(messages[:len(prompt_fixture['messages'])]) != canonical_json(prompt_fixture['messages'])
            or canonical_json(tools) != canonical_json(prompt_fixture['tools'])):
        raise ValueError('prompt_prefix_or_tools_mismatch')
    native=decode_json(native_backend.request_payload(request))
    sampling=manifest.sampling.value()
    if any(k not in native or canonical_json(native[k]) != canonical_json(v) for k,v in sampling.items()):
        raise ValueError('sampling_binding_mismatch')
    if (canonical_json(native.get('messages')) != canonical_json(messages)
            or canonical_json(native.get('tools')) != canonical_json(tools)
            or native.get('max_tokens') != request.reserved_output_tokens
            or native.get('model') != manifest.model):
        raise ValueError('native_request_binding_mismatch')
    return digest

async def wait_barrier(task, recorder, invocation, observe, timeout):
    """Require actual client body send AND isolated server running observation."""
    deadline = asyncio.get_running_loop().time()+timeout
    while asyncio.get_running_loop().time()<deadline:
        if task.done(): raise RuntimeError('request_finished_before_native_running')
        if recorder.sent_event(invocation).is_set() and (await observe())[0] > 0:
            recorder.record('native_running_observed', invocation)
            return
        await asyncio.sleep(.05)
    raise TimeoutError('native_running_not_observed')

async def wait_idle(recorder, observe, timeout):
    deadline=asyncio.get_running_loop().time()+timeout
    while asyncio.get_running_loop().time()<deadline:
        if not recorder.active and await observe()==(0,0): return True
        await asyncio.sleep(.1)
    return False

async def one_probe(mode, manifest, template, gateway_key, backend, recorder, observe,
                    gateway_timeout=15, native_observation_timeout=8, idle_timeout=30):
    if await observe()!=(0,0) or recorder.active: raise RuntimeError('server_not_idle')
    app=create_app(manifest=manifest,api_key=gateway_key,backend=backend,
                   timeout_seconds=gateway_timeout,max_inflight=1)
    before=len([e for e in recorder.events if e['kind']=='native_http_body_sent'])
    req=template.model_copy(update={'invocation_id':f'probe-{mode}-a'})
    headers={'Content-Type':'application/json','Authorization':'Bearer '+gateway_key}
    async with loopback(app) as url, httpx.AsyncClient(trust_env=False,timeout=120) as client:
        first=asyncio.create_task(client.post(url+'/v1/policy/decide',content=req.payload,headers=headers))
        try:
            await wait_barrier(first,recorder,req.invocation_id,observe,native_observation_timeout)
            if mode=='concurrency':
                second=template.model_copy(update={'invocation_id':'probe-concurrency-b'})
                response=await client.post(url+'/v1/policy/decide',content=second.payload,headers=headers)
                if response.status_code!=503: raise RuntimeError('busy_not_503')
                first_response=await first
                if first_response.status_code!=200: raise RuntimeError('first_not_200')
                await asyncio.sleep(.1)
                after=len([e for e in recorder.events if e['kind']=='native_http_body_sent'])
                if after-before != 1: raise RuntimeError('unexpected_native_dispatch_count')
                status=503
            elif mode=='timeout':
                response=await first
                if response.status_code!=504 or response.json().get('error',{}).get('code')!='upstream_timeout':
                    raise RuntimeError('gateway_timeout_not_observed')
                status=504
            elif mode=='disconnect':
                first.cancel()
                try: await first
                except asyncio.CancelledError: pass
                status=None
            else: raise ValueError('invalid_mode')
            idle=await wait_idle(recorder,observe,idle_timeout)
            after=len([e for e in recorder.events if e['kind']=='native_http_body_sent'])
            if after-before != 1: raise RuntimeError('unexpected_native_dispatch_count')
            if mode in ('timeout','disconnect'): require_cancellation_order(recorder, req.invocation_id)
            if mode=='timeout' and app.state.gateway_counters['timeout']!=1: raise RuntimeError('timeout_count_mismatch')
            if mode=='disconnect' and app.state.gateway_counters['cancelled']!=1: raise RuntimeError('disconnect_count_mismatch')
            return {'mode':mode,'status':status,'request_sha256':req.sha256,
                    'second_request_sha256':second.sha256 if mode=='concurrency' else None,
                    'gateway_counts':dict(app.state.gateway_counters),
                    'backend_idle_and_native_load_zero':idle,
                    'engine_abort_verified':False,
                    'engine_abort_reason':'native_request_id_and_decode_stop_not_observed'}
        finally:
            if not first.done():
                first.cancel()
                try: await first
                except (asyncio.CancelledError,Exception): pass

def output_path(value):
    path=Path(value)
    if not path.is_absolute() or path.parent.resolve(strict=True)!=path.parent:
        raise ValueError('output_requires_absolute_nonsymlink_parent')
    info=path.parent.stat()
    if info.st_uid!=os.getuid() or not stat.S_ISDIR(info.st_mode) or info.st_mode & 0o077:
        raise ValueError('output_requires_private_directory')
    if path.exists() or path.is_symlink():
        raise ValueError('output_already_exists')
    return path

async def main(args):
    path=output_path(args.output)
    if not args.exclusive_idle_server: raise ValueError('exclusive_idle_server_required')
    parsed=urlsplit(args.upstream)
    if parsed.scheme!='http' or parsed.hostname not in ('127.0.0.1','localhost') or not parsed.port:
        raise ValueError('upstream_must_be_local_loopback_http')
    manifest=PolicyManifest.model_validate_json(Path(args.manifest).read_bytes())
    request=PolicyRequest.from_wire(decode_json(Path(args.request).read_bytes()))
    prompt_fixture=decode_json(Path(args.prompt_fixture).read_bytes())
    binding_bytes=Path(args.binding).read_bytes()
    binding_sha256=verify_native_binding(manifest,request,binding_bytes,args.upstream)
    if request.manifest.sha256!=manifest.sha256: raise ValueError('manifest_mismatch')
    gateway_key=os.environ.get('POLICY_GATEWAY_API_KEY','')
    native_key=os.environ.get('SGLANG_API_KEY','')
    if not gateway_key or not native_key: raise ValueError('missing_keys')
    rec=Recorder()
    async with httpx.AsyncClient(transport=TraceTransport(rec),trust_env=False,timeout=120) as native:
        native_backend=SGLangChatBackend(base_url=args.upstream,manifest=manifest,api_key=native_key,
            client=native,timeout_seconds=120)
        prompt_sha256=verify_request_binding(manifest,request,native_backend,prompt_fixture)
        backend=TrackedBackend(native_backend,rec)
        async with httpx.AsyncClient(trust_env=False,timeout=5) as monitoring:
            async def observe():
                response=await monitoring.get(args.upstream.rstrip('/')+'/v1/loads',headers={'Authorization':'Bearer '+native_key})
                response.raise_for_status()
                return load_counts(response.json())
            try:
                result=await one_probe(args.mode,manifest,request,gateway_key,backend,rec,observe,
                    gateway_timeout=args.gateway_timeout)
                result['outcome']='observed' if result['backend_idle_and_native_load_zero'] else 'not_idle'
            except Exception as exc:
                known={'server_not_idle','request_finished_before_native_running','native_running_not_observed',
                       'busy_not_503','first_not_200','unexpected_native_dispatch_count',
                       'gateway_timeout_not_observed','timeout_count_mismatch','disconnect_count_mismatch',
                       'missing_or_ambiguous_load_gauge','invalid_load_gauge','backend_cancel_order_not_observed'}
                code=str(exc) if str(exc) in known else 'unspecified'
                result={'mode':args.mode,'outcome':'failed_or_inconclusive','error_type':type(exc).__name__,
                        'error_code':code,'engine_abort_verified':False}
    result.update({'schema':'gateway-resilience-probe-v1','manifest_sha256':manifest.sha256,'binding_sha256':binding_sha256,'prompt_sha256':prompt_sha256,'sampling_sha256':hashlib.sha256(canonical_json(manifest.sampling.value())).hexdigest(),'events':rec.events,
                   'native_observer':'isolated_v1_loads','game_input_dispatches':0})
    data=(json.dumps(result,indent=2)+'\n').encode()
    if gateway_key.encode() in data or native_key.encode() in data: raise ValueError('secret_in_output')
    fd=os.open(path,os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW,0o600)
    with os.fdopen(fd,'wb') as f:f.write(data)
    print(json.dumps({'status':result['outcome'],'mode':args.mode,'engine_abort_verified':False}))
    if result['outcome'] != 'observed': raise SystemExit(1)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--manifest',required=True);p.add_argument('--request',required=True)
    p.add_argument('--prompt-fixture',required=True,help='Bound initial messages/tools JSON; use prompt field from --describe-scenario, not the whole description')
    p.add_argument('--binding',required=True,help='Saved native runtime receipt; not live attestation')
    p.add_argument('--upstream',required=True);p.add_argument('--output',required=True)
    p.add_argument('--mode',required=True,choices=('concurrency','timeout','disconnect'))
    p.add_argument('--gateway-timeout',type=float,default=15)
    p.add_argument('--exclusive-idle-server',action='store_true')
    a=p.parse_args()
    if not math.isfinite(a.gateway_timeout) or a.gateway_timeout<=8: p.error('gateway timeout must exceed observation window')
    try: asyncio.run(main(a))
    except Exception as exc:
        print('probe_failed:',type(exc).__name__)
        raise SystemExit(1)
