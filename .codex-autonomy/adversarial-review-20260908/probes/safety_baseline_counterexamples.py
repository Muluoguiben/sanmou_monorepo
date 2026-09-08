import ast,base64,hashlib,hmac,importlib.util,json,struct,types,inspect
from pathlib import Path
BASE=Path('C:/Users/Lan/AppData/Local/Temp/sanmou-cr-baseline-20260908'); ROOT=Path.cwd(); REL=Path('packages/pioneer-agent/src/pioneer_agent/adapters')
def functions(root):
 source=(root/REL/'win_bridge_server.py').read_text(encoding='utf-8'); tree=ast.parse(source)
 selected=[]
 for node in tree.body:
  if isinstance(node,ast.FunctionDef) and node.name in {'handle_client','_valid_token','_ensure_window_onscreen','_restore_window','capture_window_wgc'}: selected.append(node)
  elif isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and t.id in {'PROTOCOL_VERSION','READ_ONLY_COMMANDS'} for t in node.targets): selected.append(node)
 module=ast.Module(body=[ast.ImportFrom(module='__future__',names=[ast.alias(name='annotations')],level=0),*selected],type_ignores=[]); ast.fix_missing_locations(module)
 effects=[]; replies=[]; state={'iconic':True}
 def restore(*args): effects.append(['restore',*args]);state['iconic']=False
 gui=types.SimpleNamespace(IsWindow=lambda _:True,IsIconic=lambda _:state['iconic'],GetWindowRect=lambda _:(0,0,100,80),SendMessage=restore)
 def capture(*args,**kwargs):
  if state['iconic']:raise RuntimeError('minimized synthetic')
  return (b'',{})
 context={'_capture':types.SimpleNamespace(capture_window_wgc=capture),'win32gui':gui,'win32con':types.SimpleNamespace(WM_SYSCOMMAND=274,SC_RESTORE=61728),'time':types.SimpleNamespace(sleep=lambda _:None),'_usable_rect':lambda *a:True,'socket':types.SimpleNamespace(socket=object),'hmac':hmac,'CaptureSanityError':type('SyntheticSanity',(Exception,),{}),'WM_SYSCOMMAND':274,'SC_RESTORE':61728}
 exec(compile(module,str(root/REL/'win_bridge_server.py'),'exec'),context)
 return context,effects,replies
def server_case(root):
 c,e,replies=functions(root); request={'cmd':'click','x':800,'y':500,'protocol_version':2,'request_id':'a'*32,'auth_token':'synthetic-offline-auth-'+('x'*32)}; messages=[request]
 def recv(_):
  if messages:return messages.pop(0)
  raise ConnectionError
 c.update(recv_msg=recv,send_json=lambda _,value:replies.append(value),_resolve_window=lambda *a:101,click_window_relative=lambda *a,**k:(e.append(['click',*a]) or {}))
 kwargs={'auth_token':request['auth_token']} if 'auth_token' in inspect.signature(c['handle_client']).parameters else {}
 c['handle_client'](object(),'synthetic','wgc',**kwargs)
 return {'effects':e,'statuses':[v['status'] for v in replies]}
def restore_case(root):
 c,e,_=functions(root)
 try:c['capture_window_wgc'](101); error=None
 except Exception as exc:error=type(exc).__name__+': '+str(exc)
 return {'effects':e,'error':error}
class FakeSocket:
 def __init__(self):
  body=json.dumps({'status':'ok','marker':'OLD_FIRST_RESPONSE'}).encode(); self.chunks=iter([TimeoutError('synthetic timeout'),struct.pack('>I',len(body)),body]); self.closed=False
 def recv(self,n):
  v=next(self.chunks)
  if isinstance(v,Exception):raise v
  return v
 def settimeout(self,n):pass
 def sendall(self,data):
  if self.closed:raise ConnectionError('closed')
 def close(self):self.closed=True
def proxy(root):
 spec=importlib.util.spec_from_file_location('synthetic_'+root.name,root/REL/'bridge_proxy.py'); m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def timeout_case(root):
 m=proxy(root);s=FakeSocket(); req={'cmd':'screenshot','protocol_version':2,'request_id':'b'*32}
 def call():
  if hasattr(m,'exchange'):return m.exchange(s,req,'synthetic-auth-only')
  m.send_cmd(s,req);return json.loads(m.recv_frame(s))
 try:call()
 except TimeoutError:pass
 try:second=call()
 except Exception as exc:second=type(exc).__name__
 return {'stream_closed':s.closed,'second':second}
result={rid:{'baseline':fn(BASE),'combined':fn(ROOT)} for rid,fn in [('R02',server_case),('R06',restore_case),('R07',timeout_case)]}
print(json.dumps(result,indent=2))
assert result['R02']['baseline']['effects']==[['click',101,800,500,'left']]
assert result['R02']['combined']['effects']==[] and result['R02']['combined']['statuses']==['error']
assert result['R06']['baseline']['effects'] and result['R06']['combined']['effects']==[]
assert result['R06']['combined']['error'].startswith('RuntimeError')
assert result['R07']['baseline']['second']['marker']=='OLD_FIRST_RESPONSE'
assert result['R07']['combined']['stream_closed'] and isinstance(result['R07']['combined']['second'],str)
print(json.dumps(result,indent=2))
