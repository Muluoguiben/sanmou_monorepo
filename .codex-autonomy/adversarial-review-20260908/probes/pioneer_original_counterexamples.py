import argparse,asyncio,json,inspect,sys
from copy import deepcopy
from datetime import datetime,timezone,timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from pioneer_agent.core.models import RuntimeState
from pioneer_agent.mcp_server.privacy import project_runtime_state,project_recommendation
from pioneer_agent.runtime.advisor_loop import ActionRecommendation
from pioneer_agent.perception.domains.team_panel import _build_fragment
from pioneer_agent.perception.vision.prompts import TeamPanelDetection
from pioneer_agent.perception.domains.merge import apply_team_panel
from pioneer_agent.agent_harness.journal import JsonJournalStore
from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.agent_harness.tool_log import InMemoryToolLog
from test_agent_harness import NOW,ScriptedMcpClient,load_fixture
import pioneer_agent.agent_harness.stdio_client as stdio
from mcp import ClientSession
p=argparse.ArgumentParser();p.add_argument('--mode',choices=['baseline','combined'],required=True);args=p.parse_args()
state=RuntimeState(map_state={'map_land_filter':{'visible':True,'selected_levels':[5]},'latest_battle_report':{'result':'win','attacker_losses':100}},timing={'next_action_ready_time':'2026-09-08T12:00:00+00:00'},progress={'chapter_tasks':[{'name':'synthetic','current':1,'required':2}]})
public=project_runtime_state(state); risk=project_recommendation(ActionRecommendation(action_id='synthetic',action_type='upgrade_building',risk={'level':'high','confirmation_required':True}))['risk']
R05={'map_filter_retained':'map_land_filter' in public['map_state'],'battle_retained':'latest_battle_report' in public['map_state'],'timer_retained':'next_action_ready_time' in public['timing'],'tasks_retained':'chapter_tasks' in public['progress'],'risk':risk}
def panel(names,delta):return _build_fragment(TeamPanelDetection.model_validate({'page_type':'team_panel','team_id':'team-1','heroes':[{'name':n,'stamina':80,'soldiers':1000,'max_soldiers':1000} for n in names]}),captured_at=NOW+timedelta(seconds=delta))
s=apply_team_panel(RuntimeState(),panel(['A','B','C'],0));s=apply_team_panel(s,panel(['A','B','D'],1));R08=[h['name'] for h in s.teams[0]['heroes']]
def fixture(now,suffix):
 value=load_fixture('recommendation_ready.json')
 for response in value['game'].values():
  obs=response['structuredContent'].get('observation')
  if obs:
   obs['domains_run']=['resource_bar','chapter_panel','team_panel','map_land','battle_report'];obs['captured_at']=now.isoformat();obs['observation_id']='synthetic-'+suffix
 return value
async def life():
 result={}
 for scenario in ['R17','R18','R19']:
  with TemporaryDirectory() as tmp:
   clock=[NOW];store=JsonJournalStore(Path(tmp)/'journal.json');value=fixture(clock[0],'first')
   def harness(game=None,qa=None):return RecommendationHarness(game_client=game or ScriptedMcpClient(value['game']),qa_client=qa,journal_store=store,tool_log=InMemoryToolLog(),agent_session_id='review-'+scenario,model_id='synthetic',clock=lambda:clock[0])
   if scenario=='R17':
    first=await harness().run_decision_window();clock[0]+=timedelta(seconds=121);value=fixture(clock[0],'second');second=await harness().run_decision_window();result[scenario]={'first':first.status,'second':second.status,'reason':second.stop.reason,'details':second.stop.details}
   elif scenario=='R18':
    await harness().run_decision_window();value['game']['session_status']['structuredContent']['session']['window_identity']=None;game=ScriptedMcpClient(value['game']);second=await harness(game).run_decision_window();result[scenario]={'status':second.status,'reason':second.stop.reason,'calls':[x[0] for x in game.calls]}
   else:
    class SlowQA:
     async def call_tool(self,name,arguments):clock[0]+=timedelta(seconds=300);return {'isError':False,'structuredContent':{'status':'not_found','items':[]}}
    out=await harness(qa=SlowQA()).run_decision_window(qa_questions=['synthetic question']);result[scenario]={'status':out.status,'reason':out.stop.reason,'age_seconds':300}
 return result
life_results=asyncio.run(life());source=Path(stdio.__file__).read_text(encoding='utf-8');R20={'sdk_default_timeout_is_none':inspect.signature(ClientSession).parameters['read_timeout_seconds'].default is None,'explicit_read_deadline':'read_timeout_seconds=' in source,'outer_deadline':'asyncio.timeout(' in source}
result={'mode':args.mode,'runtime_source':str(Path(stdio.__file__)),'R05':R05,'R08':R08,**life_results,'R20_static_path':R20}
if args.mode=='baseline':
 assert not R05['map_filter_retained'] and risk=={};assert R08==['A','B','C','D'];assert life_results['R17']['reason']=='checkpoint_stale';assert life_results['R18']['reason']=='window_identity_changed';assert life_results['R19']['status']=='recommended';assert not R20['explicit_read_deadline']
else:
 assert all(R05[k] for k in ['map_filter_retained','battle_retained','timer_retained','tasks_retained']) and risk=={'level':'high','confirmation_required':True};assert R08==['A','B','D'];assert life_results['R17']['second']=='recommended';assert life_results['R18']['status']=='recommended';assert life_results['R19']['reason']=='observation_stale';assert R20['explicit_read_deadline'] and R20['outer_deadline']
print(json.dumps(result,indent=2,ensure_ascii=False))
