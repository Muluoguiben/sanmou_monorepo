"""Audit CR05 author's immutable Git handoff, metadata and old-evidence preservation."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tarfile

ROOT = Path('/tmp/h09a-cr-103d0d15-20261006')
SOURCE = '103d0d1594a11af905515182913731d2d8bb4ac9'
HANDOFF = '4b1aef41d0265de6ed61062483aecdf41d70ea24'
BASE = 'docs/test-reports/2026-10-06/h09a-cr05-selftest/'
OLD = 'docs/test-reports/2026-10-06/h09a-selftest'
def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args])
def blob(commit, path):
    return git('show', commit + ':' + path)
def sha(raw):
    return hashlib.sha256(raw).hexdigest()

changes = git('diff', '--name-status', SOURCE, HANDOFF).decode().splitlines()
assert len(changes) == 216 and all(row.startswith('A\t' + BASE) for row in changes)
assert git('rev-parse', SOURCE + ':packages') == git('rev-parse', HANDOFF + ':packages')
assert git('rev-parse', '08c97024:' + OLD) == git('rev-parse', HANDOFF + ':' + OLD)
assert len(git('ls-tree', '-r', '--name-only', HANDOFF, '--', OLD).splitlines()) == 299
raw = blob(HANDOFF, BASE + 'evidence-manifest.json')
assert sha(raw) == 'e9a1adea0cbea3fabc9414d6adb4af8eab787ac8db4a8f0d53f0b4a8ca8a1f33'
manifest = json.loads(raw)
assert manifest['source_commit'] == SOURCE
assert manifest['source_tree'] == 'e9b80b3a76b494b73e0266cb383793cacb3e246d'
for path, expected in manifest['files'].items():
    raw = blob(HANDOFF, BASE + path)
    assert len(raw) == expected['bytes'] and sha(raw) == expected['sha256'], path

archive_counts, metadata_bytes = {}, {}
for filename, inventory in manifest['typed_archives'].items():
    counts = {'regular': 0, 'symlink': 0, 'directory': 0}
    seen = set()
    with tarfile.open(fileobj=io.BytesIO(blob(HANDOFF, BASE + 'raw/' + filename)), mode='r:gz') as archive:
        for member in archive.getmembers():
            seen.add(member.name)
            if member.isfile():
                data = archive.extractfile(member).read()
                actual = {'type': 'regular', 'bytes': len(data), 'sha256': sha(data)}
                counts['regular'] += 1
                if filename == 'generated-metadata.tar.gz':
                    metadata_bytes[member.name] = data
            elif member.issym():
                actual = {'type': 'symlink', 'target': member.linkname}
                counts['symlink'] += 1
            else:
                assert member.isdir()
                actual = {'type': 'directory'}
                counts['directory'] += 1
            assert actual == inventory[member.name], member.name
    assert seen == set(inventory)
    archive_counts[filename] = counts

ours = json.loads(Path('/tmp/h09a-cr-103d0d15-eval1/report.json').read_bytes())
positive = negative = 0
for path in manifest['files']:
    if not path.endswith('/report.json'):
        continue
    report = json.loads(blob(HANDOFF, BASE + path))
    prefix = BASE + path.rsplit('/', 1)[0] + '/'
    for relative, expected in report.get('artifacts', {}).items():
        assert sha(blob(HANDOFF, prefix + relative)) == expected
    if not report['gate_pass']:
        negative += 1
        assert not report['complete'] and not report['source_verified'] and not report['cases']
        continue
    positive += 1
    assert report['source']['commit'] == SOURCE and report['source']['tree'] == manifest['source_tree']
    assert report['complete'] and report['source_verified'] and not report['infra_errors']
    assert report['stable_projection'] == ours['stable_projection'] and report['inputs'] == ours['inputs']
    for relative, expected in report['source']['raw_byte_manifest'].items():
        data = blob(SOURCE, relative)
        assert sha(data) == expected['sha256'] and len(data) == expected['bytes']
        assert git('rev-parse', SOURCE + ':' + relative).decode().strip() == expected['blob']
    for relative, expected in report['inputs'].items():
        data = blob(SOURCE, 'packages/pioneer-agent/evaluation/task/development-v1/' + relative)
        assert sha(data) == expected['sha256'] and len(data) == expected['bytes']
    metadata = report['source']['non_source_metadata']
    assert not metadata['git_bound'] and not metadata['interpreted_by_evaluator']
    for relative, expected in metadata['files'].items():
        data = metadata_bytes[relative]
        assert expected == {'bytes': len(data), 'sha256': sha(data)}
assert positive == 6 and negative == 16
for package, total in [('pioneer', 998), ('qa', 394), ('common', 2), ('frozen-cr', 21)]:
    row = manifest['logs']['h09a-cr05-103d0d1-' + package + '.log']
    assert row['total'] == total and not row['failed']

result = {'source_commit': SOURCE, 'source_tree': manifest['source_tree'], 'handoff_commit': HANDOFF,
          'handoff_tree': git('rev-parse', HANDOFF + '^{tree}').decode().strip(), 'report_only_additions': 216,
          'packages_tree_unchanged': True, 'old_08c_report_blobs_unchanged': 299,
          'manifest_sha256': sha(blob(HANDOFF, BASE + 'evidence-manifest.json')),
          'report_sha256': sha(blob(HANDOFF, BASE + 'REPORT.md')), 'manifest_files_verified': len(manifest['files']),
          'positive_reports_verified': positive, 'negative_reports_verified': negative,
          'source_blobs_per_positive_report': 179, 'inputs_per_positive_report': 7,
          'author_and_independent_stable_projection_equal': True, 'archive_counts': archive_counts,
          'archive_policy': 'Read regular members only; no extraction or symlink following',
          'platform': 'Linux ext4 only; native Windows and drvfs compatibility not accepted', 'h06_windows_accepted': False}
with (Path(__file__).parent / 'author-handoff-audit-103.json').open('x') as stream:
    json.dump(result, stream, indent=2)
print(json.dumps(result, indent=2))
