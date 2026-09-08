from pathlib import Path
import json,subprocess,yaml
root=Path.cwd();rel='packages/qa-agent/knowledge_sources/profiles/heroes/minor.yaml';baseline='d377ef8bbaa69e6b25928255eac0cb62714e82f8'
before=yaml.safe_load(subprocess.check_output(['git','show',baseline+':'+rel]));after=yaml.safe_load((root/rel).read_text(encoding='utf-8'))
removed_id='hero-\u7687\u752b\u5d69';expected=[entry for entry in before if entry['id']!=removed_id]
old={e['id']:e for e in expected};new={e['id']:e for e in after}
changed=[key for key in old if key in new and old[key]!=new[key]]
print(json.dumps({'unrelated_changed_ids':changed,'removed_ids':sorted({e['id'] for e in before}-set(new)),'expected_other_records_unchanged':after==expected},ensure_ascii=True))
assert after==expected,'duplicate removal modified unrelated hero records'
