"""Replay unchanged frozen 19+2 assertions against the declared new source."""
import hashlib
import importlib
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(sys.argv[1]).resolve()
FROZEN = Path('/tmp/h09a-frozen-probes-0c40a7b/docs/test-reports/2026-10-06/h09a-independent-cr')
COMMIT = '0c40a7b426f16930dc1928abd903e2d249f14b2a'
SPECS = (('probes', 'Independent'), ('supplemental_probes', 'Supplements'),
         ('finalization_probes_2cc', 'Finalization'), ('committed_finalization_2cc', 'CommittedFinalization'),
         ('final_boundaries_fece', 'FinalBoundaries'))
sys.path.insert(0, str(FROZEN))
tests = unittest.TestSuite()
for name, test_class in SPECS:
    original = subprocess.run(['git', '-C', str(ROOT), 'show',
        f'{COMMIT}:docs/test-reports/2026-10-06/h09a-independent-cr/{name}.py'],
        check=True, capture_output=True).stdout
    raw = (FROZEN / (name + '.py')).read_bytes()
    assert raw == original, name
    print(name, hashlib.sha256(raw).hexdigest(), flush=True)
    module = importlib.import_module(name)
    module.ROOT = ROOT
    module.DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
    tests.addTests(unittest.defaultTestLoader.loadTestsFromTestCase(getattr(module, test_class)))
from pioneer_agent.agent_harness import task_eval
assert Path(task_eval.__file__).resolve().is_relative_to(ROOT)
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(tests).wasSuccessful())
