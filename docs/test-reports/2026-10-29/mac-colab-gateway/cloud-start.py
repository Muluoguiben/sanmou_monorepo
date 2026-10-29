import argparse, importlib.util, json, os, pathlib, secrets, socket, subprocess, sys, time, urllib.request, urllib.error
p=argparse.ArgumentParser(); p.add_argument('--status',required=True); p.add_argument('--bootstrap',required=True); args=p.parse_args()
gw_task=pathlib.Path(args.status).resolve().parent
provision=json.loads(pathlib.Path(args.status).read_text()); assert provision['status']=='provisioned'
source_root=pathlib.Path(provision['source_root']); sg_python=provision['python']; model_dir=pathlib.Path(provision['model_dir'])
spec=importlib.util.spec_from_file_location('bootstrap',args.bootstrap); boot=importlib.util.module_from_spec(spec); spec.loader.exec_module(boot)
def free_port():
    with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
native_port=free_port(); gateway_port=free_port(); assert native_port != gateway_port
public_config={'model-path':str(model_dir),'tokenizer-path':str(model_dir),'chat-template':str(model_dir/'chat_template.jinja'),'served-model-name':'sanmou-qwen35-9b-gateway','host':'127.0.0.1','port':native_port,'dtype':'bfloat16','load-format':'safetensors','tensor-parallel-size':1,'data-parallel-size':1,'context-length':8192,'mem-fraction-static':0.55,'max-running-requests':1,'chunked-prefill-size':1024,'cuda-graph-backend-decode':'disabled','cuda-graph-backend-prefill':'disabled','tool-call-parser':'qwen3_coder','reasoning-parser':'qwen3','log-level':'warning','log-requests':False,'trust-remote-code':False,'limit-mm-data-per-request':{'image':0,'video':0,'audio':0},'skip-server-warmup':True}
def write_new(path,value,mode=0o600):
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,mode)
    with os.fdopen(fd,'w') as f:json.dump(value,f,indent=2)
service_key=secrets.token_urlsafe(32); admin_key=secrets.token_urlsafe(32); gateway_key=secrets.token_urlsafe(32)
write_new(gw_task/'cross-public-runtime.json',public_config)
write_new(gw_task/'cross-private-runtime.yaml',dict(public_config,**{'api-key':service_key,'admin-api-key':admin_key}))
write_new(gw_task/'cross-private-keys.json',{'gateway':gateway_key,'service':service_key})
env=boot.isolated_env(gw_task,source_root); env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',PYTHONDONTWRITEBYTECODE='1')
scenario_run=subprocess.run([sg_python,str(source_root/'scripts/model-serving/live_gateway_roundtrip.py'),'--describe-scenario'],env=env,capture_output=True,text=True,timeout=30,check=True)
scenario=json.loads(scenario_run.stdout); write_new(gw_task/'cross-sampling.json',scenario['sampling'])
cmd=[sg_python,str(source_root/'scripts/model-serving/native_runtime_manifest.py'),'--model-dir',str(model_dir),'--runtime-config',str(gw_task/'cross-public-runtime.json'),'--expected-model-files',provision['expected_model_files'],'--sampling',str(gw_task/'cross-sampling.json'),'--prompt-sha256',scenario['prompt_sha256'],'--source-root',str(source_root),'--source-inventory',provision['source_inventory'],'--output',str(gw_task/'cross-native-binding')]
with (gw_task/'cross-binding.log').open('x') as f: subprocess.run(cmd,env=env,stdout=f,stderr=subprocess.STDOUT,timeout=300,check=True)
assert not subprocess.check_output(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],text=True).strip()
log=(gw_task/'cross-server.log').open('x'); model=subprocess.Popen(['timeout','1500',sg_python,'-m','sglang.launch_server','--config',str(gw_task/'cross-private-runtime.yaml')],env=env,stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
write_new(gw_task/'cross-model-process.json',{'pid':model.pid})
def ready(url,proc,limit):
    deadline=time.monotonic()+limit
    while time.monotonic()<deadline:
        if proc.poll() is not None:raise RuntimeError('owned_process_exited')
        try:
            with urllib.request.urlopen(url,timeout=3) as r:
                if r.status==200:return
        except (OSError,urllib.error.URLError):time.sleep(2)
    raise TimeoutError('readiness_timeout')
try:
    ready(f'http://127.0.0.1:{native_port}/health',model,360)
    gateway_env=dict(env,POLICY_GATEWAY_API_KEY=gateway_key,SGLANG_API_KEY=service_key)
    glog=(gw_task/'cross-gateway.log').open('x'); gateway=subprocess.Popen(['timeout','1500',sg_python,'-m','pioneer_agent.app.policy_gateway','--manifest',str(gw_task/'cross-native-binding/policy-manifest.json'),'--upstream',f'http://127.0.0.1:{native_port}','--port',str(gateway_port),'--timeout','185'],env=gateway_env,stdout=glog,stderr=subprocess.STDOUT,start_new_session=True)
    write_new(gw_task/'cross-gateway-process.json',{'pid':gateway.pid})
    ready(f'http://127.0.0.1:{gateway_port}/health',gateway,30)
    write_new(gw_task/'cross-ready.json',{'status':'ready','gateway_port':gateway_port,'model_port':native_port,'manifest':str(gw_task/'cross-native-binding/policy-manifest.json'),'binding':str(gw_task/'cross-native-binding/runtime-receipt.json'),'keys':str(gw_task/'cross-private-keys.json'),'model_pid':model.pid,'gateway_pid':gateway.pid,'source_root':str(source_root)})
    print(json.dumps({'status':'ready','work_dir':str(gw_task),'gateway_port':gateway_port,'model_port':native_port}),flush=True)
except BaseException:
    import signal
    for proc in (locals().get('gateway'),model):
        if proc and proc.poll() is None:os.killpg(proc.pid,signal.SIGTERM)
    raise
