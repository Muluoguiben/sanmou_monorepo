"""Rebind all frozen independent fault assertions to finalization-fix source."""
from pathlib import Path
import unittest
import probes
import supplemental_probes
import finalization_probes_2cc
import committed_finalization_2cc

ROOT = Path('/tmp/h09a-cr-fece4163-20261006')
modules = (probes, supplemental_probes, finalization_probes_2cc, committed_finalization_2cc)
for module in modules:
    module.ROOT = ROOT
    module.DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
suite = unittest.TestSuite([
    unittest.defaultTestLoader.loadTestsFromTestCase(probes.Independent),
    unittest.defaultTestLoader.loadTestsFromTestCase(supplemental_probes.Supplements),
    unittest.defaultTestLoader.loadTestsFromTestCase(finalization_probes_2cc.Finalization),
    unittest.defaultTestLoader.loadTestsFromTestCase(committed_finalization_2cc.CommittedFinalization),
])
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
