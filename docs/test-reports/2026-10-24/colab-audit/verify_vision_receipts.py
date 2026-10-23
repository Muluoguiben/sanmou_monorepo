"""Offline vision receipt audit; does not issue GPU or network requests."""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
from pathlib import Path
import re
import stat
import struct
import subprocess

from sanmou_common.policy_contracts import PolicyUsage, decode_json
from pioneer_agent.adapters.policy_http import _generation, _validate_native_response

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source-root', type=Path, required=True)
parser.add_argument('--evidence-root', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--expected-source-sha', default='ff121f14758847b897ae4f049cbb8a14cd9b3dfe')
args = parser.parse_args()
source = args.source_root.resolve()
evidence = args.evidence_root.resolve()
checks = []

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def check(value, label):
    if not value:
        raise AssertionError(label)
    checks.append(label)

def read(name):
    return decode_json((evidence / name).read_bytes())

head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=source, text=True).strip()
check(head == args.expected_source_sha, 'source_sha')
source_hashes = {}
for relative in ('packages/sanmou-common/src/sanmou_common/policy_contracts.py',
                 'packages/pioneer-agent/src/pioneer_agent/adapters/policy_http.py'):
    raw = (source / relative).read_bytes()
    check(raw == subprocess.check_output(['git', 'show', head + ':' + relative], cwd=source), 'committed_source:' + relative)
    source_hashes[relative] = sha(raw)

index_raw = (evidence / 'evidence-index.json').read_bytes()
index = decode_json(index_raw)
check(index['schema'] == 'sanmou-colab-vision-evidence-v1', 'index_schema')
check(len(index['files']) == 15, 'index_15_files')
check({p.name for p in evidence.iterdir()} == set(index['files']) | {'evidence-index.json'}, 'exact_inventory')
total = 0
for name, item in index['files'].items():
    path = evidence / name
    check(Path(name).name == name and stat.S_ISREG(path.lstat().st_mode) and not path.is_symlink(), 'flat_regular_file:' + name)
    raw = path.read_bytes()
    check(len(raw) == item['bytes'] and sha(raw) == item['sha256'], 'bytes_hash:' + name)
    total += len(raw)
check(total == 64877, 'total_64877_bytes')

# Independently read from both displayed original PNGs using view_image before
# running this script. These are synthetic fixture labels, not game outcomes.
visually_observed = [
    {'text': 'CODE 47', 'red_circles': 2, 'blue_squares': 1, 'green_triangles': 1,
     'triangle_relative_to_circles': 'below', 'square_relative_to_circles': 'right'},
    {'text': 'CODE 83', 'red_circles': 1, 'blue_squares': 2, 'green_triangles': 1,
     'triangle_relative_to_circles': 'above', 'square_relative_to_circles': 'left'},
]
cases = (
    ('vision', 'vision-fixture.png', 'vision-expected.json', False),
    ('vision-2', 'vision-fixture-2.png', 'vision-expected-2.json', True),
)
recorded = read('vision-checks.json')
case_results = []
for number, (prefix, fixture_name, expected_name, expected_strict) in enumerate(cases):
    original_png = (evidence / fixture_name).read_bytes()
    check(original_png[:8] == b'\x89PNG\r\n\x1a\n' and original_png[12:16] == b'IHDR', prefix + ':png_header')
    dimensions = struct.unpack('>II', original_png[16:24])
    check(dimensions == (640, 384), prefix + ':png_dimensions')
    expected = read(expected_name)
    check(expected == visually_observed[number] and len(expected) == 6, prefix + ':expected_matches_visual_inspection')
    request, response = read(prefix + '-request.json'), read(prefix + '-response.json')
    timing = read(prefix + '-timing.json')
    check(timing['status'] == 200, prefix + ':http_200_receipt')
    check(len(request['messages']) == 1 and request['messages'][0]['role'] == 'user', prefix + ':single_image_user_request')
    content = request['messages'][0]['content']
    images = [part for part in content if part['type'] == 'image_url']
    texts = [part['text'] for part in content if part['type'] == 'text']
    check(len(images) == 1 and len(texts) == 1 and len(content) == 2, prefix + ':one_image_one_instruction')
    data_uri = images[0]['image_url']['url']
    check(data_uri.startswith('data:image/png;base64,'), prefix + ':png_data_uri')
    decoded = base64.b64decode(data_uri.split(',', 1)[1], validate=True)
    check(decoded == original_png, prefix + ':data_uri_exact_original_png_bytes')
    check(expected['text'] not in texts[0], prefix + ':code_not_in_text_prompt')
    check(request['chat_template_kwargs'] == {'enable_thinking': False}, prefix + ':thinking_disabled')
    if expected_strict:
        check(request['response_format'] == {'type': 'json_object'}, prefix + ':explicit_json_object_format')
    else:
        check('response_format' not in request, prefix + ':first_request_no_json_constraint')
    choice = _validate_native_response(response, request['model'])
    check(choice is not None and choice['finish_reason'] == 'stop', prefix + ':native_response_and_finish')
    answer = choice['message']['content']
    try:
        parsed = decode_json(answer)
        strict_json = True
        fence_removed = False
    except (ValueError, TypeError):
        strict_json = False
        match = re.fullmatch(r'\s*```json\s*\n(.*)\n```\s*', answer, re.DOTALL)
        check(match is not None, prefix + ':exact_json_code_fence')
        parsed = decode_json(match.group(1))
        fence_removed = True
    check(strict_json is expected_strict, prefix + ':strict_json_result')
    check(type(parsed) is dict and set(parsed) == set(expected), prefix + ':exact_six_field_names')
    check(all(type(parsed[key]) is type(expected[key]) and parsed[key] == expected[key] for key in expected),
          prefix + ':all_six_fields_match_with_types')
    usage, meta = response['usage'], choice['meta_info']
    prompt_ids, response_ids = choice['prompt_token_ids'], choice['response_token_ids']
    triples = meta['output_token_logprobs']
    check(all(type(token) is int and token >= 0 for token in prompt_ids + response_ids), prefix + ':valid_token_ids')
    check(len(prompt_ids) == usage['prompt_tokens'] == meta['prompt_tokens'] == 314, prefix + ':prompt_tokens_alignment')
    check(len(response_ids) == usage['completion_tokens'] == meta['completion_tokens'] == len(triples)
          == meta['output_token_logprobs_length'], prefix + ':output_usage_triples_alignment')
    check(usage['total_tokens'] == len(prompt_ids) + len(response_ids), prefix + ':total_tokens_alignment')
    check(usage['prompt_tokens_details']['image_tokens'] == meta['image_tokens'] == 240, prefix + ':240_image_tokens')
    check([item[1] for item in triples] == response_ids, prefix + ':triple_token_ids_exact')
    check(all(len(item) == 3 and type(item[0]) in (float, int) and math.isfinite(item[0])
              and item[0] <= 0 and type(item[1]) is int
              and (item[2] is None or isinstance(item[2], str)) for item in triples), prefix + ':valid_probability_triples')
    public = choice['logprobs']['content']
    check(len(public) == len(triples) and all(p['logprob'] == t[0] for p, t in zip(public, triples)),
          prefix + ':openai_logprobs_match_native')
    generation = _generation(choice, 'unavailable', PolicyUsage(input_tokens=len(prompt_ids), output_tokens=len(response_ids)))
    check(generation.probability_kind == 'unavailable' and generation.policy_token_mask is None,
          prefix + ':no_sampling_or_ppo_inference')
    check(choice['message'].get('reasoning_content') in (None, '') and usage['reasoning_tokens'] == 0,
          prefix + ':no_reasoning_output')
    recorded_case = recorded[prefix]
    check((recorded_case['strict_json'], recorded_case['fields_match'], recorded_case['prompt_ids'],
           recorded_case['output_ids'], recorded_case['logprobs']) == (strict_json, True, 314, len(response_ids), len(triples)),
          prefix + ':recorded_checks_recomputed')
    case_results.append({
        'case': prefix, 'fixture_sha256': sha(original_png), 'dimensions': list(dimensions),
        'request_sha256': sha((evidence / (prefix + '-request.json')).read_bytes()),
        'response_sha256': sha((evidence / (prefix + '-response.json')).read_bytes()),
        'data_uri_matches_fixture_bytes': True, 'visual_fixture_inspection': True,
        'response_format': request.get('response_format'), 'strict_json': strict_json,
        'fence_removed_for_offline_comparison': fence_removed, 'matching_fields': 6, 'total_fields': 6,
        'expected_and_actual': parsed, 'prompt_tokens': len(prompt_ids), 'image_tokens': 240,
        'output_tokens': len(response_ids), 'triples': len(triples), 'finish_reason': choice['finish_reason'],
        'receipt_seconds': timing['seconds'], 'probability_kind': 'unavailable',
    })

for name, item in index['files'].items():
    check(sha((evidence / name).read_bytes()) == item['sha256'], 'original_unchanged:' + name)
summary = {
    'schema': 'sanmou-colab-vision-offline-audit-v1', 'status': 'passed',
    'source_commit': head, 'parser_source_sha256': source_hashes,
    'verifier_script_sha256': sha(Path(__file__).read_bytes()), 'evidence_index_sha256': sha(index_raw),
    'verified_files': 15, 'verified_bytes': total, 'redacted_log_files': ['vision-server.log'],
    'check_count': len(checks), 'cases': case_results,
    'scope': {'mode': 'offline_readback_of_native_image_responses', 'synthetic_fixture_images': 2,
              'real_game_screenshot_quality_validated': False, 'new_gpu_or_network_calls': 0,
              'gateway_or_j2_validated': False, 'ppo_eligible': False, 'original_receipts_modified': False,
              'first_case_is_not_strict_json_success': True},
}
with args.output.open('x', encoding='utf-8') as out:
    json.dump(summary, out, ensure_ascii=False, indent=2)
    out.write('\n')
print(json.dumps({'status': 'passed', 'files': 15, 'bytes': total, 'checks': len(checks),
                  'cases': [{'name': c['case'], 'strict_json': c['strict_json'], 'fields': c['matching_fields'],
                             'image_tokens': c['image_tokens']} for c in case_results], 'output': str(args.output)}))
