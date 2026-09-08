"""Controlled SDK-stream shutdown proof; no real process or source mutation."""
import argparse,asyncio,json
from contextlib import asynccontextmanager
from unittest.mock import patch
import anyio
from mcp import StdioServerParameters,types
from mcp.shared.message import SessionMessage
from pioneer_agent.agent_harness.stdio_client import StdioMcpClient

def leaves(error):
 if isinstance(error,BaseExceptionGroup):return [name for child in error.exceptions for name in leaves(child)]
 return [type(error).__name__]
async def scenario(timeout_init=False):
 evidence={'timeout_init':timeout_init,'normal_replies':[],'late_send_completed':False}
 stats_source=None
 @asynccontextmanager
 async def transport(_parameters):
  nonlocal stats_source
  incoming_tx,incoming_rx=anyio.create_memory_object_stream(0)
  stats_source=incoming_tx
  outgoing_tx,outgoing_rx=anyio.create_memory_object_stream(0)
  async def peer():
   async for item in outgoing_rx:
    request=item.message.root
    if not hasattr(request,'id'):continue
    if request.method=='initialize':
     if timeout_init:continue
     result={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'shutdown-probe','version':'1'}}
    elif request.method=='tools/list':result={'tools':[{'name':'session_status','inputSchema':{'type':'object'},'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}}]}
    else:result={'content':[],'isError':False,'structuredContent':{'sequence':request.params.get('arguments',{}).get('sequence')}}
    reply=types.JSONRPCMessage.model_validate({'jsonrpc':'2.0','id':request.id,'result':result})
    await incoming_tx.send(SessionMessage(reply))
  try:
   async with anyio.create_task_group() as group:
    group.start_soon(peer)
    try:yield incoming_rx,outgoing_tx
    finally:
     try:
      evidence['receivers_at_transport_exit']=incoming_tx.statistics().open_receive_streams
      late=types.JSONRPCMessage.model_validate({'jsonrpc':'2.0','method':'notifications/message','params':{'level':'info','data':'synthetic late message'}})
      await incoming_tx.send(SessionMessage(late))
      evidence['late_send_completed']=True
     finally:
      await incoming_tx.aclose();await incoming_rx.aclose();await outgoing_tx.aclose();await outgoing_rx.aclose();group.cancel_scope.cancel()
  finally:
   evidence['transport_final_open_receivers']=incoming_tx.statistics().open_receive_streams
   evidence['transport_final_open_senders']=incoming_tx.statistics().open_send_streams
 client=StdioMcpClient(StdioServerParameters(command='not-executed'),expected_server_name='shutdown-probe',required_tools={'session_status'},exact_tools=True,connect_timeout_s=.03 if timeout_init else 1,request_timeout_s=1)
 try:
  with patch('pioneer_agent.agent_harness.stdio_client.stdio_client',transport):
   async with client:
    for n in range(10):
     result=await client.call_tool('session_status',{'sequence':n});evidence['normal_replies'].append(result['structuredContent']['sequence'])
 except BaseException as exc:evidence.update(exception=type(exc).__name__,leaves=leaves(exc))
 else:evidence.update(exception=None,leaves=[])
 evidence['worker_cleared']=client._worker is None
 evidence['final_open_receivers']=stats_source.statistics().open_receive_streams
 evidence['final_open_senders']=stats_source.statistics().open_send_streams
 return evidence
async def main():
 values=[await scenario(False),await scenario(True)]
 print(json.dumps(values,indent=2))
 if args.expect=='broken':
  assert all('BrokenResourceError' in r['leaves'] for r in values)
  assert values[0]['normal_replies']==list(range(10))
 else:
  assert values[0]['exception'] is None and values[0]['normal_replies']==list(range(10))
  assert values[1]['exception']=='TimeoutError'
  assert all(r['late_send_completed'] and r['worker_cleared'] and r['final_open_receivers']==0 and r['final_open_senders']==0 for r in values)
p=argparse.ArgumentParser();p.add_argument('--expect',choices=['broken','fixed'],required=True);args=p.parse_args();asyncio.run(main())
