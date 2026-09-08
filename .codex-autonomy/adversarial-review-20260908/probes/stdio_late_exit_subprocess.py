"""Actual official stdio subprocess emits late messages after stdin EOF.

All input and output are synthetic. Liveness checks never signal the child.
"""
import argparse
import asyncio
import ctypes
import json
import os
import sys
import time

from mcp import StdioServerParameters
from pioneer_agent.agent_harness.stdio_client import StdioMcpClient

SERVER = r'''
import json,os,sys,time
for line in sys.stdin:
 message=json.loads(line);method=message.get('method')
 if 'id' not in message:continue
 if method=='initialize':result={'protocolVersion':'2025-11-25','capabilities':{'tools':{}},'serverInfo':{'name':'late-exit','version':'1'}}
 elif method=='tools/list':result={'tools':[{'name':'session_status','inputSchema':{'type':'object'},'annotations':{'readOnlyHint':True,'destructiveHint':False,'openWorldHint':False}}]}
 else:result={'content':[],'isError':False,'structuredContent':{'pid':os.getpid()}}
 print(json.dumps({'jsonrpc':'2.0','id':message['id'],'result':result}),flush=True)
for n in range(LATE_MESSAGE_COUNT):
 print(json.dumps({'jsonrpc':'2.0','method':'notifications/message','params':{'level':'info','data':'synthetic-late-'+str(n)}}),flush=True)
 time.sleep(.05)
'''


def leaves(exc):
    if isinstance(exc, BaseExceptionGroup):
        return [name for child in exc.exceptions for name in leaves(child)]
    return [type(exc).__name__]


def process_alive(pid):
    if os.name != "nt":
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
    kernel.WaitForSingleObject.restype = ctypes.c_ulong
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    kernel.CloseHandle.restype = ctypes.c_int
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        if ctypes.get_last_error() == 87:
            return False
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        wait = kernel.WaitForSingleObject(handle, 0)
        if wait not in (0, 258):
            raise ctypes.WinError(ctypes.get_last_error())
        return wait == 258
    finally:
        kernel.CloseHandle(handle)


async def trial(persistent):
    before_tasks = set(asyncio.all_tasks())
    child_source = SERVER.replace("LATE_MESSAGE_COUNT", "600" if persistent else "4")
    client = StdioMcpClient(
        StdioServerParameters(command=sys.executable, args=["-u", "-c", child_source]),
        expected_server_name="late-exit",
        required_tools={"session_status"},
        exact_tools=True,
        connect_timeout_s=2,
        request_timeout_s=1,
    )
    result = {"normal_call_ok": False, "persistent_output": persistent}
    started = time.monotonic()
    pid = None
    try:
        async with asyncio.timeout(12):
            async with client:
                response = await client.call_tool("session_status", {})
                pid = response["structuredContent"]["pid"]
                result["normal_call_ok"] = True
    except BaseException as exc:
        result.update(exception=type(exc).__name__, leaves=leaves(exc))
    else:
        result.update(exception=None, leaves=[])
    await asyncio.sleep(0)
    result["elapsed_s"] = round(time.monotonic() - started, 3)
    result["worker_cleared"] = client._worker is None
    result["new_pending_tasks"] = len(
        [task for task in asyncio.all_tasks() - before_tasks if not task.done()]
    )
    if pid:
        result["child_reaped"] = not process_alive(pid)
    return result


async def main(args):
    results = [await trial(args.persistent) for _ in range(3)]
    print(json.dumps(results, indent=2))
    assert all(
        r["normal_call_ok"]
        and r["worker_cleared"]
        and r["child_reaped"]
        and r["new_pending_tasks"] == 0
        and r["elapsed_s"] < 12
        for r in results
    )
    if args.expect == "broken":
        assert all("BrokenResourceError" in r["leaves"] for r in results)
    else:
        assert all(r["exception"] is None for r in results)


parser = argparse.ArgumentParser()
parser.add_argument("--expect", choices=["broken", "fixed"], required=True)
parser.add_argument("--persistent", action="store_true")
asyncio.run(main(parser.parse_args()))
