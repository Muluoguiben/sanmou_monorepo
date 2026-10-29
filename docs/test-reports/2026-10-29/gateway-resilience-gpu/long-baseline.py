import asyncio,hashlib,importlib.util,json,os,time
from pathlib import Path
import httpx
from sanmou_common.policy_contracts import PolicyManifest,PolicyRequest,PolicyTransportResponse,decode_json
from pioneer_agent.adapters.policy_http import SGLangChatBackend
from pioneer_agent.app.policy_gateway import create_app
base=Path('/content/sanmou-resilience-VIMogqbM'); restart=base/'restart-1'; fixture=base/'long-fixture'
spec=importlib.util.spec_from_file_location('resilience_probe',base/'gateway-resilience-probe-v2.py'); mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
ready=json.loads((restart/'ready.json').read_text()); keys=json.loads((restart/'private-keys.json').read_text()); up='http://127.0.0.1:'+str(ready['model_port'])
manifest=PolicyManifest.model_validate_json((fixture/'native-binding/policy-manifest.json').read_bytes());req=PolicyRequest.from_wire(decode_json((fixture/'policy-request.json').read_bytes()));receipt=(fixture/'native-binding/runtime-receipt.json').read_bytes();prompt=decode_json((fixture/'prompt-fixture.json').read_bytes()); mod.verify_native_binding(manifest,req,receipt,up)
async def main():
    rec=mod.Recorder()
    async with httpx.AsyncClient(transport=mod.TraceTransport(rec),trust_env=False,timeout=190) as native:
        native_backend=SGLangChatBackend(base_url=up,manifest=manifest,api_key=keys['service'],client=native,timeout_seconds=180)
        prompt_hash=mod.verify_request_binding(manifest,req,native_backend,prompt)
        backend=mod.TrackedBackend(native_backend,rec)
        app=create_app(manifest=manifest,api_key=keys['gateway'],backend=backend,timeout_seconds=185,max_inflight=1)
        async with mod.loopback(app) as url, httpx.AsyncClient(trust_env=False,timeout=190) as client:
            start=time.monotonic();r=await client.post(url+'/v1/policy/decide',content=req.payload,headers={'content-type':'application/json','authorization':'Bearer '+keys['gateway']});elapsed=time.monotonic()-start
            result={'schema':'long-baseline-v1','http_status':r.status_code,'seconds':round(elapsed,3),'request_sha256':req.sha256,'prompt_sha256':prompt_hash,'manifest_sha256':manifest.sha256,'gateway_counts':dict(app.state.gateway_counters),'game_input_dispatches':0}
            if r.status_code==200:
                x=PolicyTransportResponse.model_validate_json(r.content); raw=x.raw_response.value();choice=raw['choices'][0];calls=choice.get('message',{}).get('tool_calls') or []
                result.update(usage=x.usage.model_dump(mode='json'),finish_reason=choice.get('finish_reason'),tool_names=[c.get('function',{}).get('name') for c in calls],output_token_count=len(x.generation.response_token_ids) if x.generation and x.generation.response_token_ids is not None else None)
            else:
                result['error_code']=r.json().get('error',{}).get('code')
            fd=os.open(fixture/'baseline.json',os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:json.dump(result,f,indent=2)
            print(json.dumps(result),flush=True)
asyncio.run(main())
