"""Synthetic transport-only WSL hop audit; no game, real secret or model."""
import argparse,base64,hashlib,io,json,os,pathlib,socket,struct,subprocess,sys,threading,time
from datetime import datetime,timezone
SENTINEL='synthetic-review-capture-token-'+('x'*32)
p=argparse.ArgumentParser(); p.add_argument('--worker'); p.add_argument('--port',type=int); args=p.parse_args()
if args.worker:
    safe={k:v for k,v in os.environ.items() if k in {'PATH','HOME','USER','LOGNAME','WSL_DISTRO_NAME','WSL_INTEROP','PWD','LANG','TERM','LD_LIBRARY_PATH'}}
    os.environ.clear(); os.environ.update(safe)
    os.environ['SANMOU_CAPTURE_TOKEN']=SENTINEL
    if 'manual' in args.worker: os.environ['WSLENV']='SANMOU_CAPTURE_TOKEN/w'
    from pioneer_agent.app.game_agent import _child_env
    child=_child_env(include_vision_credentials=False,include_capture_credentials=True)
    os.environ.clear(); os.environ.update(child)
    from pioneer_agent.adapters.capture_bridge_client import CaptureBridgeClient
    client=CaptureBridgeClient(port=args.port,capture_backend='wgc')
    captures=[]; original_request=client._request
    def traced_request(payload):
        response=original_request(payload); captures.append(response.get('captured_at')); return response
    client._request=traced_request
    result={'case':args.worker,'parent_to_game_has_synthetic_token':os.environ.get('SANMOU_CAPTURE_TOKEN')==SENTINEL,'wslenv_configured':'WSLENV' in os.environ}
    try:
        frame=client.screenshot_capture(); result.update(ok=True,png_bytes=len(frame.png),request_bound=bool(frame.request_id),server_time_bound=frame.captured_at is not None)
    except Exception as exc:
        result.update(ok=False,error_type=type(exc).__name__,error_message=str(exc))
        if captures and captures[-1]:
            captured=datetime.fromisoformat(captures[-1])
            result['server_capture_minus_request_start_ms']=(captured-client._request_started_at).total_seconds()*1000
            result['response_received_minus_server_capture_ms']=(client._response_received_at-captured).total_seconds()*1000
    finally: client.close()
    encoded=json.dumps(result); assert SENTINEL not in encoded; print(encoded); sys.exit(0)
assert os.name=='nt'
from PIL import Image
stop=threading.Event(); events=[]
listener=socket.socket(); listener.bind(('127.0.0.1',0)); listener.listen(4); listener.settimeout(.25)
def exact(conn,n):
    value=b''
    while len(value)<n:
        part=conn.recv(n-len(value))
        if not part: raise EOFError
        value+=part
    return value
def serve():
    while not stop.is_set():
        try: conn,_=listener.accept()
        except socket.timeout: continue
        except OSError: return
        with conn:
            conn.settimeout(5)
            try:
                req=json.loads(exact(conn,struct.unpack('>I',exact(conn,4))[0]))
                authenticated=req.get('auth_token')==SENTINEL; events.append({'authenticated':authenticated,'cmd':req.get('cmd')})
                assert authenticated and req['cmd']=='screenshot'
                captured=datetime.now(timezone.utc).isoformat(); buf=io.BytesIO(); Image.new('RGB',(8,6),(1,2,3)).save(buf,format='PNG'); data=buf.getvalue()
                rect={'left':0,'top':0,'right':8,'bottom':6,'width':8,'height':6}
                geometry={'schema_version':1,'capture_backend':'wgc','outer_window':{'hwnd':101,'pid':202,**rect},'capture_rect':rect,'capture_origin':{'x':0,'y':0},'frame_size':[8,6]}
                reply={'protocol_version':2,'request_id':req['request_id'],'status':'ok','data_b64':base64.b64encode(data).decode(),'size':len(data),'frame_sha256':hashlib.sha256(data).hexdigest(),'captured_at':captured,'capture_geometry':geometry}
                wire=json.dumps(reply).encode(); conn.sendall(struct.pack('>I',len(wire))+wire)
            except Exception as exc: events.append({'error_type':type(exc).__name__})
worker=threading.Thread(target=serve,daemon=True); worker.start()
script='/mnt/c'+str(pathlib.Path(__file__).resolve())[2:].replace('\\','/')
env={k:v for k,v in os.environ.items() if k.upper() in {'SYSTEMROOT','WINDIR','PATH','TEMP','TMP','USERPROFILE','HOMEDRIVE','HOMEPATH','LOCALAPPDATA','APPDATA','COMSPEC','PATHEXT','NUMBER_OF_PROCESSORS','PROCESSOR_ARCHITECTURE'}}
results=[]
try:
    for case in ['default','manual']:
        proc=subprocess.run(['wsl.exe','-d','Ubuntu','--exec','/tmp/sanmou-cr-20260908-venv/bin/python',script,'--worker',case,'--port',str(listener.getsockname()[1])],env=env,capture_output=True,text=True,encoding='utf-8',timeout=35)
        assert SENTINEL not in proc.stdout+proc.stderr
        result=json.loads(proc.stdout.strip()); result['exit_code']=proc.returncode; results.append(result)
finally:
    stop.set(); listener.close(); worker.join(2)
print(json.dumps({'results':results,'fake_server_events':events,'real_credentials_used':False,'game_input':False,'production_server_used':False},indent=2))
assert results[0]['ok'] is False
assert results[1]['ok'] is True
assert events==[{'authenticated':True,'cmd':'screenshot'}]
