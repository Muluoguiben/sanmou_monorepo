import json, os, subprocess, sys
from pathlib import Path
base=Path('/content/sanmou-resilience-VIMogqbM'); restart=base/'restart-1'; fixture=base/'long-fixture'
mode=sys.argv[1]
if mode not in ('concurrency','timeout','disconnect'):raise SystemExit('invalid_mode')
keys=json.loads((restart/'private-keys.json').read_text()); ready=json.loads((restart/'ready.json').read_text())
env=dict(os.environ,POLICY_GATEWAY_API_KEY=keys['gateway'],SGLANG_API_KEY=keys['service'],PYTHONDONTWRITEBYTECODE='1',PYTHONPATH='/content/sanmou-gateway-xwtp14yk/source/packages/pioneer-agent/src:/content/sanmou-gateway-xwtp14yk/source/packages/sanmou-common/src')
cmd=['/content/sanmou-gateway-xwtp14yk/venv/bin/python',str(base/'gateway-resilience-probe-v2.py'),'--manifest',str(fixture/'native-binding/policy-manifest.json'),'--binding',str(fixture/'native-binding/runtime-receipt.json'),'--prompt-fixture',str(fixture/'prompt-fixture.json'),'--request',str(fixture/'policy-request.json'),'--upstream','http://127.0.0.1:'+str(ready['model_port']),'--output',str(fixture/(mode+'-result.json')),'--mode',mode,'--gateway-timeout','180' if mode=='concurrency' else '15','--exclusive-idle-server']
r=subprocess.run(cmd,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
print('probe_exit',r.returncode)
for line in r.stdout.splitlines():
    try:value=json.loads(line)
    except ValueError:continue
    if isinstance(value,dict) and set(value) >= {'status','mode','engine_abort_verified'}:print(json.dumps(value))
if r.returncode:print('probe_output_saved', (fixture/(mode+'-result.json')).exists())
