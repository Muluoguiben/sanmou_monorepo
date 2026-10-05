"""Independent handoff audit against immutable Git blobs; no author code executed."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path('/tmp/h09a-cr-fece4163-20261006')
SOURCE = 'fece4163d04af5057493549da2db74a8fa65ed06'
HANDOFF = '08c97024b4c0566c26f5c2b0461c1efb3e5d3c23'
BASE = 'docs/test-reports/2026-10-06/h09a-selftest/'
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
def blob(commit, path):
    return git('show', commit + ':' + path)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

changes = git('diff', '--name-status', SOURCE, HANDOFF).decode().splitlines()
assert len(changes) == 299
assert all(line.startswith('A\t' + BASE) for line in changes)
assert git('rev-parse', SOURCE + ':packages') == git('rev-parse', HANDOFF + ':packages')
raw = blob(HANDOFF, BASE + 'evidence-manifest-final.json')
assert sha(raw) == 'a193b156f42a1d36dd9560d924db7f1f5572161c3717e767e86d39073c83b85f'
manifest = json.loads(raw)
assert manifest['source_commit'] == SOURCE
assert manifest['source_tree'] == '4c25f8fa14ea99d8aca09d49cf6c3c911c5c2f8e'
for path, expected in manifest['files'].items():
    raw = blob(HANDOFF, BASE + path)
    assert len(raw) == expected['bytes'] and sha(raw) == expected['sha256'], path

reports = []
for name in ('h09a-fece416-eval1', 'h09a-fece416-eval2', 'h09a-fece416-direct'):
    prefix = BASE + 'raw/' + name + '/'
    report = json.loads(blob(HANDOFF, prefix + 'report.json'))
    assert report['source']['commit'] == SOURCE
    assert report['complete'] and report['source_verified'] and report['gate_pass']
    assert not report['infra_errors'] and not report['artifact_errors']
    for path, expected in report['source']['raw_byte_manifest'].items():
        data = blob(SOURCE, path)
        assert sha(data) == expected['sha256'] and len(data) == expected['bytes'], path
        assert git('rev-parse', SOURCE + ':' + path).decode().strip() == expected['blob'], path
    for path, expected in report['artifacts'].items():
        assert sha(blob(HANDOFF, prefix + path)) == expected, path
    for path, expected in report['inputs'].items():
        data = blob(SOURCE, 'packages/pioneer-agent/evaluation/task/development-v1/' + path)
        assert sha(data) == expected['sha256'] and len(data) == expected['bytes'], path
    reports.append(report)
ours = json.loads(Path('/tmp/h09a-cr-fece4163-eval1/report.json').read_bytes())
assert all(report['stable_projection'] == ours['stable_projection'] for report in reports)
assert all(report['inputs'] == ours['inputs'] for report in reports)

counts = {'regular': 0, 'symlink': 0, 'directory': 0}
observed = set()
with tarfile.open(fileobj=io.BytesIO(blob(HANDOFF, BASE + 'raw/final-probe-replay.tar.gz')), mode='r:gz') as archive:
    for member in archive.getmembers():
        if member.isdir():
            counts['directory'] += 1
            continue
        observed.add(member.name)
        expected = manifest['frozen_probe_replay_members'][member.name]
        if member.issym():
            counts['symlink'] += 1
            assert expected == {'type': 'symlink', 'target': member.linkname}
        else:
            assert member.isfile()
            counts['regular'] += 1
            data = archive.extractfile(member).read()
            assert expected == {'bytes': len(data), 'sha256': sha(data)}
assert observed == set(manifest['frozen_probe_replay_members'])
for name, total in [('pioneer', 990), ('qa', 394), ('common', 2), ('frozen-cr', 19)]:
    summary = manifest['logs']['h09a-fece416-' + name + '.log']
    assert summary['total'] == total and summary['status'] == 'passed'
result = {'source_commit': SOURCE, 'source_tree': manifest['source_tree'], 'handoff_commit': HANDOFF,
          'handoff_tree': git('rev-parse', HANDOFF + '^{tree}').decode().strip(),
          'report_only_additions': len(changes), 'packages_tree_unchanged': True,
          'author_manifest_sha256': sha(blob(HANDOFF, BASE + 'evidence-manifest-final.json')),
          'author_report_sha256': sha(blob(HANDOFF, BASE + 'REPORT.md')),
          'manifest_files_verified': len(manifest['files']), 'source_blobs_per_formal_report': len(reports[0]['source']['raw_byte_manifest']),
          'formal_reports_verified': 3, 'input_blobs_per_report': len(reports[0]['inputs']),
          'author_and_independent_stable_projection_equal': True, 'probe_archive_counts': counts,
          'safe_read': 'regular tar members read in memory; no extraction and no symlink following',
          'h06_windows_accepted': False}
with (Path(__file__).parent / 'author-handoff-audit.json').open('x') as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result, indent=2))
