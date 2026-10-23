"""Offline read-back audit only: no network, gateway, model, game or training."""
from __future__ import annotations

import argparse
import inspect
import hashlib
import json
import math
from pathlib import Path
import stat
import subprocess

from pydantic import BaseModel, ConfigDict
from sanmou_common.policy_contracts import PolicyManifest, PolicyRequest, PolicyUsage, SealedJson, decode_json
from pioneer_agent.adapters.policy_http import assistant_message, _generation, _validate_native_response
from pioneer_agent.adapters.policy_service import ToolDefinition, ToolRegistry

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--evidence-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--summary-output', type=Path)
parser.add_argument('--expected-source-sha', default='ff121f14758847b897ae4f049cbb8a14cd9b3dfe')
args = parser.parse_args()
SOURCE = args.source_root.resolve()
EVIDENCE = args.evidence_root.resolve()
OUTPUT = args.output
EXPECTED_SHA = args.expected_source_sha
checks = []

def check(condition, name):
    if not condition:
        raise AssertionError(name)
    checks.append(name)

def digest(raw):
    return hashlib.sha256(raw).hexdigest()

def read_json(name):
    return decode_json((EVIDENCE / name).read_bytes())

head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=SOURCE, text=True).strip()
check(head == EXPECTED_SHA, 'parser_source_head')
for component in (PolicyRequest, ToolRegistry, assistant_message):
    check(Path(inspect.getfile(component)).resolve().is_relative_to(SOURCE), 'parser_import_root:' + component.__name__)
source_hashes = {}
for path in (
    'packages/sanmou-common/src/sanmou_common/policy_contracts.py',
    'packages/pioneer-agent/src/pioneer_agent/adapters/policy_http.py',
    'packages/pioneer-agent/src/pioneer_agent/adapters/policy_service.py',
):
    local = (SOURCE / path).read_bytes()
    committed = subprocess.check_output(['git', 'show', f'{EXPECTED_SHA}:{path}'], cwd=SOURCE)
    check(local == committed, 'source_bytes:' + path)
    source_hashes[path] = digest(local)

index_raw = (EVIDENCE / 'evidence-index.json').read_bytes()
index = decode_json(index_raw)
check(index['schema'] == 'sanmou-colab-native-evidence-v1', 'index_schema')
check(len(index['files']) == 29, 'index_29_files')
check({p.name for p in EVIDENCE.iterdir()} == set(index['files']) | {'evidence-index.json'}, 'exact_inventory')
verified_files = []
for name, entry in index['files'].items():
    check(Path(name).name == name, 'flat_path:' + name)
    path = EVIDENCE / name
    before = path.lstat()
    check(stat.S_ISREG(before.st_mode) and not path.is_symlink(), 'regular_original:' + name)
    raw = path.read_bytes()
    check(len(raw) == entry['bytes'] and digest(raw) == entry['sha256'], 'byte_hash:' + name)
    verified_files.append({'path': name, 'bytes': len(raw), 'sha256': digest(raw), 'redacted': entry['redacted']})
check(sum(item['bytes'] for item in verified_files) == 64524, 'total_64524_bytes')

model_files = read_json('model-files.json')
model_proof = read_json('model-revision-proof.json')
check(len(model_files) == model_proof['downloaded_files'] == 13, 'model_manifest_count')
check(sum(item['bytes'] for item in model_files.values()) == model_proof['downloaded_bytes'] == 19329302904,
      'model_manifest_byte_sum')
check(len(model_proof['revision']) == 40, 'full_model_revision')
check(len(model_proof['lfs_sha256_checks']) == 5 and all(v is True for v in model_proof['lfs_sha256_checks'].values()),
      'recorded_lfs_checks_all_true')
check(all(name in model_files for name in model_proof['lfs_sha256_checks']), 'recorded_lfs_files_in_manifest')

class QueryArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    query: str

class CompleteArgs(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    reason: str

registry = ToolRegistry([
    ToolDefinition(name='query_knowledge', arguments_model=QueryArgs, state_effect='read_only', window_effect='passive'),
    ToolDefinition(name='complete_task', arguments_model=CompleteArgs, state_effect='control', window_effect='passive'),
])

sampling_keys = ('temperature', 'top_p', 'top_k', 'min_p', 'seed', 'repetition_penalty',
                 'frequency_penalty', 'presence_penalty', 'stop')
round_results = []
native_requests, native_responses, proposed_calls = {}, {}, {}
captured_checks = read_json('token-checks.json')
for name in ('ready', 'round-1', 'round-2'):
    request = read_json(name + '-request.json')
    response = read_json(name + '-response.json')
    native_requests[name], native_responses[name] = request, response
    timing = read_json(name + '-timing.json')
    check(timing['status'] == 200, name + ':http_200_receipt')
    check(request['stream'] is False and type(request['n']) is int and request['n'] == 1,
          name + ':single_nonstream')
    check(all(request[key] is True for key in ('logprobs', 'return_token_ids', 'return_meta_info')),
          name + ':native_token_fields_requested')
    check(request['chat_template_kwargs'] == {'enable_thinking': False}, name + ':thinking_disabled')
    check(all(key in request for key in sampling_keys), name + ':sampling_all_nine_keys')
    choice = _validate_native_response(response, request['model'])
    check(choice is not None, name + ':existing_native_response_validation')
    usage = response['usage']
    prompt, output = choice['prompt_token_ids'], choice['response_token_ids']
    meta = choice['meta_info']
    triples = meta['output_token_logprobs']
    check(all(type(token) is int and token >= 0 for token in prompt + output), name + ':token_ids_nonnegative_int')
    check(len(prompt) == usage['prompt_tokens'] == meta['prompt_tokens'], name + ':prompt_usage_alignment')
    check(len(output) == usage['completion_tokens'] == meta['completion_tokens'] == len(triples)
          == meta['output_token_logprobs_length'], name + ':output_usage_triples_alignment')
    check(usage['total_tokens'] == len(prompt) + len(output), name + ':total_usage_alignment')
    check(0 < len(output) <= request['max_tokens'], name + ':output_within_budget')
    check(all(isinstance(t, list) and len(t) == 3 and type(t[0]) in (float, int)
              and math.isfinite(t[0]) and t[0] <= 0 and type(t[1]) is int
              and (t[2] is None or isinstance(t[2], str)) for t in triples), name + ':finite_logprob_triples')
    check([t[1] for t in triples] == output, name + ':triple_ids_exact_match')
    public_probs = choice['logprobs']['content']
    check(len(public_probs) == len(output) and all(p['logprob'] == t[0] for p, t in zip(public_probs, triples)),
          name + ':openai_logprobs_match_native_triples')
    check(choice['message'].get('reasoning_content') in (None, '') and usage['reasoning_tokens'] == 0,
          name + ':no_reasoning_output')
    generation = _generation(choice, 'unavailable', PolicyUsage(input_tokens=len(prompt), output_tokens=len(output)))
    check(generation.input_token_ids == tuple(prompt) and generation.response_token_ids == tuple(output),
          name + ':existing_generation_adapter_retains_ids')
    check(generation.probability_kind == 'unavailable' and generation.response_logprobs is None
          and generation.policy_token_mask is None, name + ':no_invented_sampling_or_ppo_mask')
    recorded = captured_checks[name]
    check((recorded['prompt_ids'], recorded['output_ids'], recorded['logprobs'], recorded['finish_reason'])
          == (len(prompt), len(output), len(triples), choice['finish_reason']), name + ':recorded_checks_recomputed')
    parsed = []
    if name == 'ready':
        check(choice['finish_reason'] == 'stop' and choice['message']['content'] == 'READY', 'ready:exact_text')
    else:
        calls = registry.parse(SealedJson.from_value(response))
        check(len(calls) == 1, name + ':exactly_one_parsed_tool')
        proposed_calls[name] = calls[0]
        parsed = [{'call_id': c.call_id, 'tool': c.tool_name, 'arguments': c.arguments.value()} for c in calls]
        check(choice['finish_reason'] == 'tool_calls', name + ':completed_tool_generation')
        native_call = choice['message']['tool_calls'][0]
        check(assistant_message(response)['tool_calls'][0]['function']['arguments'] == native_call['function']['arguments'],
              name + ':assistant_helper_preserves_argument_text')
    round_results.append({'name': name, 'status': 'passed', 'request_sha256': digest((EVIDENCE / f'{name}-request.json').read_bytes()),
                          'response_sha256': digest((EVIDENCE / f'{name}-response.json').read_bytes()),
                          'response_id': response['id'], 'input_tokens': len(prompt), 'output_tokens': len(output),
                          'triples': len(triples), 'finish_reason': choice['finish_reason'], 'parsed_calls': parsed,
                          'receipt_seconds': timing['seconds'], 'probability_kind': generation.probability_kind})

first, second = native_requests['round-1'], native_requests['round-2']
check({k: v for k, v in first.items() if k != 'messages'} == {k: v for k, v in second.items() if k != 'messages'},
      'rounds_same_native_configuration_and_tools')
check(len(first['messages']) == 2 and len(second['messages']) == 4, 'two_round_history_lengths')
check(second['messages'][:2] == first['messages'], 'original_history_unchanged')
check(second['messages'][2] == assistant_message(native_responses['round-1']), 'assistant_helper_matches_actual_second_request')
reply = second['messages'][3]
check(reply['role'] == 'tool' and reply['tool_call_id'] == proposed_calls['round-1'].call_id,
      'tool_reply_bound_to_first_call')
reply_body = decode_json(reply['content'])
check(reply_body['source'] == 'synthetic' and reply_body['status'] == 'ok', 'tool_reply_marked_synthetic')
check(proposed_calls['round-1'].tool_name == 'query_knowledge'
      and proposed_calls['round-1'].arguments.value() == {'query': 'building upgrade rule'}, 'first_tool_parameters')
check(proposed_calls['round-2'].tool_name == 'complete_task'
      and proposed_calls['round-2'].arguments.value() == {'reason': reply_body['rule']}, 'second_tool_uses_exact_synthetic_rule')
check(proposed_calls['round-1'].call_id != proposed_calls['round-2'].call_id, 'distinct_tool_call_ids')

# These envelopes are explicitly reconstructed for offline schema validation;
# they are not records of a gateway invocation at the time of native sampling.
manifest = PolicyManifest(
    policy_id='offline-audit-native-receipts', model=first['model'], checkpoint_revision=model_proof['revision'],
    adapter_revision='none', tokenizer_revision=model_files['tokenizer.json']['sha256'],
    chat_template_revision=model_files['chat_template.jinja']['sha256'],
    prompt_revision=SealedJson.from_value(first['messages']).sha256,
    sampling=SealedJson.from_value({key: first[key] for key in sampling_keys}), model_context_limit=8192,
)
offline_envelopes = []
for index, name in enumerate(('round-1', 'round-2')):
    native = native_requests[name]
    req = PolicyRequest(episode_id='offline-audit-episode', run_id='offline-audit-run',
                        decision_id=f'offline-decision-{index}', invocation_id=f'offline-invocation-{index}',
                        context_id=f'offline-context-{index}', task_ref='offline-audit-task', binding_ref='offline-no-game-role',
                        observation_ref='offline-synthetic-observation', manifest=manifest,
                        messages=SealedJson.from_value(native['messages']), tools=SealedJson.from_value(native['tools']),
                        estimated_input_tokens=round_results[index + 1]['input_tokens'], reserved_output_tokens=native['max_tokens'])
    check(PolicyRequest.from_wire(req.to_wire()).payload == req.payload, name + ':common_policy_request_roundtrip')
    offline_envelopes.append({'name': name, 'context_origin': 'offline_reconstructed_for_schema_check', 'request_sha256': req.sha256})

for entry in verified_files:
    check(digest((EVIDENCE / entry['path']).read_bytes()) == entry['sha256'], 'original_unchanged:' + entry['path'])
result = {
    'schema': 'sanmou-colab-text-offline-audit-v1', 'status': 'passed', 'source_commit': EXPECTED_SHA,
    'parser_source_sha256': source_hashes, 'verifier_script_sha256': digest(Path(__file__).read_bytes()),
    'evidence_index_sha256': digest(index_raw), 'verified_files': 29, 'verified_bytes': 64524,
    'redacted_log_files': [e['path'] for e in verified_files if e['redacted']],
    'check_count': len(checks), 'checks': checks, 'rounds': round_results,
    'offline_envelopes': offline_envelopes,
    'model_manifest': {'revision': model_proof['revision'], 'file_count': 13, 'listed_bytes': 19329302904,
                       'recorded_lfs_checks': 5, 'local_weight_binary_rehash': False},
    'scope': {'mode': 'offline_readback_of_native_gpu_responses', 'new_network_or_model_calls': 0,
              'real_gateway_validated': False, 'j2_validated': False, 'ppo_eligible': False,
              'original_receipts_modified': False, 'synthetic_tool_result': True},
}
with OUTPUT.open('x', encoding='utf-8') as out:
    json.dump(result, out, ensure_ascii=False, indent=2)
    out.write('\n')
if args.summary_output is not None:
    summary = {key: result[key] for key in (
        'schema', 'status', 'source_commit', 'parser_source_sha256', 'verifier_script_sha256',
        'evidence_index_sha256', 'verified_files', 'verified_bytes', 'redacted_log_files',
        'check_count', 'rounds', 'model_manifest', 'scope',
    )}
    summary['detailed_result_sha256'] = digest(OUTPUT.read_bytes())
    summary['history_check'] = 'actual second request equals original messages + assistant_message(actual first response) + correctly ID-bound synthetic tool reply'
    summary['common_schema_check'] = 'both native message/tool arrays pass explicitly offline-reconstructed PolicyRequest to_wire/from_wire roundtrip'
    with args.summary_output.open('x', encoding='utf-8') as out:
        json.dump(summary, out, ensure_ascii=False, indent=2)
        out.write('\n')
print(json.dumps({'status': result['status'], 'checks': result['check_count'], 'files': 29, 'bytes': 64524,
                  'result': str(OUTPUT), 'rounds': [{'name': r['name'], 'input': r['input_tokens'],
                  'output': r['output_tokens'], 'triples': r['triples']} for r in round_results]}))
