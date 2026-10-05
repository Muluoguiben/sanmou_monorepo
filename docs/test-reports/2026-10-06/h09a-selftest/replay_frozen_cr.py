"""Replay unchanged CR assertions; only substitute the reviewed source root."""
import hashlib
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(sys.argv[1]).resolve()
FROZEN = Path('/tmp/h09a-frozen-probes-2bcd73e/docs/test-reports/2026-10-06/h09a-independent-cr')
COMMIT = '2bcd73e7b474c32f5aaf28f77e81c5bfc1cd2082'
for name in ('probes.py', 'supplemental_probes.py'):
    original = subprocess.run(['git', '-C', str(ROOT), 'show',
        f'{COMMIT}:docs/test-reports/2026-10-06/h09a-independent-cr/{name}'],
        check=True, capture_output=True).stdout
    raw = (FROZEN / name).read_bytes()
    assert raw == original, name
    print(name, hashlib.sha256(raw).hexdigest(), flush=True)
sys.path.insert(0, str(FROZEN))
import probes
import supplemental_probes
from pioneer_agent.agent_harness import task_eval
assert Path(task_eval.__file__).resolve().is_relative_to(ROOT)
for module in (probes, supplemental_probes):
    module.ROOT = ROOT
    module.DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
tests = unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromTestCase(probes.Independent),
    unittest.defaultTestLoader.loadTestsFromTestCase(supplemental_probes.Supplements),
])
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful())
