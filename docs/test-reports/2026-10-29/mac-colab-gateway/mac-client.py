import argparse, asyncio, hashlib, json, os, pathlib, sys, time
p=argparse.ArgumentParser(); p.add_argument('--source',required=True); p.add_argument('--manifest',required=True); p.add_argument('--binding',required=True); p.add_argument('--keys',required=True); p.add_argument('--port',required=True,type=int); p.add_argument('--output',required=True); args=p.parse_args()
source=pathlib.Path(args.source)
sys.path.insert(0,str(source/'packages/pioneer-agent/src')); sys.path.insert(0,str(source/'packages/sanmou-common/src'))
import httpx
from pydantic import BaseModel, ConfigDict, Field
from sanmou_common.policy_contracts import PolicyManifest,PolicyRequest,SealedJson,canonical_json,decode_json
from pioneer_agent.adapters.policy_http import HttpPolicyTransport,assistant_message
from pioneer_agent.adapters.policy_service import PolicyServiceAdapter,ToolDefinition,ToolRegistry
from pioneer_agent.agent_harness.run_budget import BudgetLimits,RunBudgetLedger
class QueryKnowledgeArguments(BaseModel):
    model_config=ConfigDict(extra='forbid'); query:str=Field(min_length=1)
class CompleteTaskArguments(BaseModel):
    model_config=ConfigDict(extra='forbid'); reason:str=Field(min_length=1)
registry=ToolRegistry([ToolDefinition(name='query_knowledge',description='Read the fixed gateway-check fixture.',arguments_model=QueryKnowledgeArguments,state_effect='read_only',window_effect='passive'),ToolDefinition(name='complete_task',description='Propose completion after receiving the fixture response.',arguments_model=CompleteTaskArguments,state_effect='control',window_effect='passive')])
scenario=decode_json((source/'scripts/model-serving/live_gateway_scenario.json').read_bytes())
manifest=PolicyManifest.model_validate_json(pathlib.Path(args.manifest).read_bytes()); binding_bytes=pathlib.Path(args.binding).read_bytes(); key=json.loads(pathlib.Path(args.keys).read_text())['gateway']
prompt_hash=hashlib.sha256(canonical_json({'messages':scenario['messages'],'tools':registry.tools.value()})).hexdigest(); assert manifest.prompt_revision=='sha256:'+prompt_hash; assert manifest.sampling.value()==scenario['sampling']
async def main():
    budget=RunBudgetLedger(BudgetLimits(max_steps=2,max_model_attempts=2,max_tool_calls=0,max_tokens=2432,max_seconds=420.0))
    messages=scenario['messages']; records=[]
    async with httpx.AsyncClient(trust_env=False,follow_redirects=False) as client:
        transport=HttpPolicyTransport(base_url=f'http://127.0.0.1:{args.port}',api_key=key,client=client,timeout_seconds=195)
        adapter=PolicyServiceAdapter(transport=transport,manifest=manifest,registry=registry,budget=budget,timeout_seconds=200)
        for n in (1,2):
            request=PolicyRequest(episode_id='mac-colab-gateway-check',run_id='mac-colab-gateway-check',decision_id=f'decision-{n}',invocation_id=f'invocation-{n}',context_id=f'context-{n}',task_ref=scenario['scenario_id'],binding_ref=hashlib.sha256(binding_bytes).hexdigest(),observation_ref='synthetic-no-game-observation',manifest=manifest,messages=SealedJson.from_value(messages),tools=registry.tools,estimated_input_tokens=1024,reserved_output_tokens=192)
            started=time.monotonic(); result=await adapter.decide(request); elapsed=time.monotonic()-started
            record=result.model_dump(mode='json'); records.append({'result':record,'seconds':elapsed,'request_sha256':request.sha256})
            if result.status!='ok' or len(result.proposed_calls)!=1:raise RuntimeError('policy_round_failed')
            expected=scenario['first_tool'] if n==1 else scenario['second_tool']
            if result.proposed_calls[0].tool_name!=expected:raise RuntimeError('unexpected_tool_sequence')
            if n==1:
                if result.proposed_calls[0].arguments.value()!=scenario['first_arguments']:raise RuntimeError('unexpected_query_arguments')
                messages=messages+[assistant_message(result.raw_response.value()),{'role':'tool','tool_call_id':result.proposed_calls[0].call_id,'content':canonical_json(scenario['tool_reply']).decode('utf-8')}]
    summary=budget.summary(); assert summary['pending']==0 and not summary['overrun']
    output={'status':'passed','records':records,'budget':summary,'manifest_sha256':manifest.sha256,'binding_sha256':hashlib.sha256(binding_bytes).hexdigest(),'game_input_dispatches':0}
    fd=os.open(args.output,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
    with os.fdopen(fd,'w') as f:json.dump(output,f,indent=2)
    print(json.dumps({'status':'passed','rounds':len(records),'seconds':[r['seconds'] for r in records],'pending':summary['pending']}))
asyncio.run(main())
