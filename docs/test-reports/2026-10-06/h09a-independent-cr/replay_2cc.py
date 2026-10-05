"""Replay the unchanged first-round probes against the three-fix candidate."""
from pathlib import Path
import unittest
import probes
import supplemental_probes

ROOT = Path('/tmp/h09a-cr-2cc7b2f8-20261006')
for module in (probes, supplemental_probes):
    module.ROOT = ROOT
    module.DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
suite = unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromTestCase(probes.Independent),
    unittest.defaultTestLoader.loadTestsFromTestCase(supplemental_probes.Supplements),
])
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
