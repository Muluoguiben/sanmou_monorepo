import asyncio,json,os,sys
from pathlib import Path
from datetime import timedelta
from mcp import ClientSession,StdioServerParameters
from mcp.client.stdio import stdio_client
from pioneer_agent.mcp_server.contracts import GAME_TOOL_ALLOWLIST
ROOT=Path('/mnt/c/Users/Lan/.codex/worktrees/6737/sanmou_monorepo')
P=ROOT/'packages/pioneer-agent';Q=ROOT/'packages/qa-agent'
ENV={'PYTHONPATH':':'.join(str(ROOT/'packages'/x/'src') for x in ['pioneer-agent','sanmou-common','qa-agent']),'PYTHONNOUSERSITE':'1','SANMOU_GAME_FIXTURE_ROOT':str(P/'tests/fixtures')}
async def main():
 output={}
 for name,package,module in [('game',P,'pioneer_agent.mcp_server'),('qa',Q,'qa_agent.mcp_server.stdio_server')]:
  params=StdioServerParameters(command=sys.executable,args=['-m',module],cwd=package,env=ENV)
  async with stdio_client(params) as (read,write):
   async with ClientSession(read,write,read_timeout_seconds=timedelta(seconds=15)) as client:
    initialized=await client.initialize(); listed=await client.list_tools(); tools={t.name:t for t in listed.tools}
    assert all(t.annotations.readOnlyHint is True and t.annotations.destructiveHint is False for t in tools.values())
    if name=='game':
     assert set(tools)==set(GAME_TOOL_ALLOWLIST)
     first=await client.call_tool('get_runtime_state',{})
     fixture=await client.call_tool('evaluate_fixture',{'fixture':'chapter_claimable_state.json','include_details':False})
     after=await client.call_tool('get_runtime_state',{})
     value=fixture.structuredContent
     assert first.structuredContent['status']=='not_observed' and after.structuredContent['status']=='not_observed'
     assert not fixture.isError and value['contract_version']=='sanmou-game/v1' and value['execution_authority']=='none'
     evaluation=value['evaluation']; assert value['live_source_used'] is False
     assert evaluation['selected_action']['executable'] is False
     invalid=await client.call_tool('evaluate_fixture',{'fixture':'chapter_claimable_state.json','include_details':'false'})
     assert invalid.isError
     output[name]={'server':initialized.serverInfo.name,'tools':sorted(tools),'fixture_status':value['status'],'action':evaluation['selected_action']['action_type'],'cache_unchanged':True,'strict_type_error':bool(invalid.isError),'authority':value['execution_authority']}
    else:
     assert set(tools)=={'lookup_topic','answer_rule_question','resolve_term','advisor_golden_replay_status','advisor_fixture_eval','advisor_terminal_source_evidence_eval'}
     required=tools['resolve_term'].inputSchema.get('required',[])
     args={key:'补兵' for key in required}
     answer=await client.call_tool('resolve_term',args);assert not answer.isError
     invalid=await client.call_tool('resolve_term',{**args,'unexpected':True});assert invalid.isError
     output[name]={'server':initialized.serverInfo.name,'tools':sorted(tools),'resolve_status':answer.structuredContent.get('status'),'strict_extra_error':bool(invalid.isError)}
 print(json.dumps(output,ensure_ascii=False,indent=2))
asyncio.run(main())
