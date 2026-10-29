#!/usr/bin/env python3
"""Prepare a synthetic long-output policy fixture; never launch a model.

The reason text is requested, not guaranteed: early completion or failure to
observe active work makes any cancellation experiment inconclusive.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys


def new_json(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(value, f, indent=2, ensure_ascii=False)
        f.write('\n')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--ready', required=True)
    p.add_argument('--provision', required=True)
    p.add_argument('--output', required=True)
    args = p.parse_args()
    ready_path, provision_path, output = map(Path, (args.ready, args.provision, args.output))
    for path in (ready_path, provision_path):
        if not path.is_absolute() or path.resolve(strict=True) != path or not path.is_file():
            raise ValueError('invalid_input_path')
    if not output.is_absolute() or output.parent.resolve(strict=True) != output.parent:
        raise ValueError('invalid_output_parent')
    ready, provision = json.loads(ready_path.read_text()), json.loads(provision_path.read_text())
    if ready.get('status') != 'ready' or provision.get('status') != 'provisioned':
        raise ValueError('invalid_ready_or_provision')
    if ready.get('source_commit') != provision.get('source_commit'):
        raise ValueError('source_commit_mismatch')
    task, root = ready_path.parent, provision_path.parent
    source = Path(provision['source_root'])
    model_dir = Path(provision['model_dir'])
    python = Path(provision['python'])
    if source != root/'source' or model_dir != root/'model' or python != root/'venv/bin/python':
        raise ValueError('unexpected_provision_paths')
    for key in ('manifest', 'binding', 'keys'):
        if Path(ready[key]).parent != (task/'native-binding' if key in ('manifest','binding') else task):
            raise ValueError('unexpected_ready_paths')
    public = json.loads((task/'public-runtime.json').read_text())
    sampling = json.loads((task/'sampling.json').read_text())
    old_receipt = json.loads(Path(ready['binding']).read_text())
    if public != old_receipt.get('public_config') or sampling != old_receipt.get('sampling'):
        raise ValueError('live_config_binding_mismatch')
    if public.get('host') != '127.0.0.1' or public.get('port') != ready.get('model_port'):
        raise ValueError('model_listener_binding_mismatch')
    if public.get('model-path') != str(model_dir):
        raise ValueError('model_path_mismatch')
    sys.path[:0] = [str(source/'packages/sanmou-common/src'), str(source/'packages/pioneer-agent/src')]
    from pydantic import BaseModel, ConfigDict, Field
    from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, SealedJson, canonical_json
    from pioneer_agent.adapters.policy_service import ToolDefinition, ToolRegistry

    class QueryKnowledgeArguments(BaseModel):
        model_config = ConfigDict(extra='forbid')
        query: str = Field(min_length=1)

    class CompleteTaskArguments(BaseModel):
        model_config = ConfigDict(extra='forbid')
        reason: str = Field(min_length=1)

    registry = ToolRegistry([
        ToolDefinition(name='query_knowledge', description='Read the fixed gateway-check fixture.',
                       arguments_model=QueryKnowledgeArguments, state_effect='read_only', window_effect='passive'),
        ToolDefinition(name='complete_task', description='Propose completion after receiving the fixture response.',
                       arguments_model=CompleteTaskArguments, state_effect='control', window_effect='passive'),
    ])
    messages = [
        {'role':'system', 'content':
         'This is a synthetic performance test, unrelated to any game or user data. '
         'Return exactly one complete_task tool call, with no prose outside the tool call. '
         'In its reason string, write 180 numbered, distinct, fictional observations. '
         'Each observation should be a full sentence of roughly 10 words about imaginary '
         'colors, shapes, weather, and numbers. Include all 180 observations in the '
         'single reason field. Never request or execute any game input.'},
        {'role':'user','content':'Produce the long synthetic reason now; use one complete_task call.'},
    ]
    tools = registry.tools.value()
    prompt_hash = hashlib.sha256(canonical_json({'messages':messages,'tools':tools})).hexdigest()
    os.mkdir(output, 0o700)
    new_json(output/'sampling.json', sampling)
    new_json(output/'scenario.json', {'scenario_id':'synthetic-longrun-v1', 'messages':messages,
        'tools':tools, 'prompt_sha256':prompt_hash, 'reserved_output_tokens':2048,
        'expected_tool':'complete_task', 'early_end_result':'inconclusive',
        'note':'A long response is requested but cannot be guaranteed; observe active work before cancellation.'})
    env = {k:v for k,v in os.environ.items() if k in {'HOME','PATH','LANG','LC_ALL','TERM','LD_LIBRARY_PATH',
           'CUDA_HOME','CUDA_PATH','CUDA_VISIBLE_DEVICES','NVIDIA_VISIBLE_DEVICES','SSL_CERT_FILE'}}
    env.update(PYTHONPATH=os.pathsep.join([str(source/'packages/sanmou-common/src'),str(source/'packages/pioneer-agent/src')]),
        PYTHONDONTWRITEBYTECODE='1',HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
        PATH=str(python.parent)+os.pathsep+env.get('PATH','/usr/local/bin:/usr/bin:/bin'))
    cmd=[str(python),str(source/'scripts/model-serving/native_runtime_manifest.py'),
         '--model-dir',str(model_dir),'--runtime-config',str(task/'public-runtime.json'),
         '--expected-model-files',provision['expected_model_files'],'--sampling',str(output/'sampling.json'),
         '--prompt-sha256',prompt_hash,'--source-root',str(source),'--source-inventory',provision['source_inventory'],
         '--output',str(output/'native-binding')]
    # Collector logs and exception text are suppressed; no key or model call is made.
    subprocess.run(cmd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True, timeout=600)
    receipt = output/'native-binding/runtime-receipt.json'
    manifest = PolicyManifest.model_validate_json((output/'native-binding/policy-manifest.json').read_bytes())
    binding_hash = hashlib.sha256(receipt.read_bytes()).hexdigest()
    if manifest.prompt_revision != 'sha256:'+prompt_hash or manifest.sampling.value() != sampling:
        raise ValueError('new_manifest_mismatch')
    request=PolicyRequest(episode_id='synthetic-longrun',run_id='synthetic-longrun',decision_id='decision-longrun',
        invocation_id='invocation-longrun',context_id='context-longrun',task_ref='synthetic-longrun-v1',
        binding_ref=binding_hash,observation_ref='synthetic-no-game-observation',manifest=manifest,
        messages=SealedJson.from_value(messages),tools=registry.tools,estimated_input_tokens=1024,reserved_output_tokens=2048)
    wire=request.to_wire()
    if PolicyRequest.from_wire(wire).sha256 != request.sha256:
        raise ValueError('request_roundtrip_mismatch')
    if hashlib.sha256(canonical_json({'messages':wire['messages'],'tools':wire['tools']})).hexdigest() != prompt_hash:
        raise ValueError('request_prompt_mismatch')
    new_json(output/'policy-request.json',wire)
    new_json(output/'fixture-status.json', {'schema':'synthetic-longrun-fixture-v1','status':'prepared',
        'manifest_sha256':manifest.sha256,'request_sha256':request.sha256,'binding_sha256':binding_hash,
        'prompt_sha256':prompt_hash,'reserved_output_tokens':2048,'actual_generation':'not_run',
        'early_end_result':'inconclusive','model_calls':0})
    print(json.dumps({'status':'prepared','output':str(output),'reserved_output_tokens':2048,
                      'actual_generation':'not_run','early_end_result':'inconclusive'}))


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('fixture_prepare_failed:',type(exc).__name__,file=sys.stderr)
        raise SystemExit(1)
