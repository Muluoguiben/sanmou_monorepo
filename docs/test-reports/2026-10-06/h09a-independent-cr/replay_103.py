"""Run all original 21 review assertions against CR05-fixed immutable source."""
from pathlib import Path
import unittest
import probes
import supplemental_probes
import finalization_probes_2cc
import committed_finalization_2cc
import final_boundaries_fece

ROOT = Path('/tmp/h09a-cr-103d0d15-20261006')
for module in (probes, supplemental_probes, finalization_probes_2cc, committed_finalization_2cc, final_boundaries_fece):
    module.ROOT = ROOT
    module.DATA = ROOT / 'packages/pioneer-agent/evaluation/task/development-v1'
classes = (probes.Independent, supplemental_probes.Supplements, finalization_probes_2cc.Finalization,
           committed_finalization_2cc.CommittedFinalization, final_boundaries_fece.FinalBoundaries)
suite = unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromTestCase(cls) for cls in classes)
raise SystemExit(not unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful())
