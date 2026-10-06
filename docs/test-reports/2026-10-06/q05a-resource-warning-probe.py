"""Run the original single crop test and record, never suppress, resource warnings."""
import gc
import json
from pathlib import Path
import sys
import unittest
import warnings

mode = sys.argv[1]
assert mode in {"baseline", "fixed"}
from test_lineup_frame_extractor import CropIntoColumnsTests

gc.collect()
with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always", ResourceWarning)
    suite = unittest.TestSuite([CropIntoColumnsTests("test_splits_and_upscales")])
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    gc.collect()
resources = [{"category": warning.category.__name__, "message": str(warning.message),
              "filename": warning.filename, "lineno": warning.lineno}
             for warning in caught if issubclass(warning.category, ResourceWarning)]
print(json.dumps({"mode": mode, "tests_run": result.testsRun,
    "successful": result.wasSuccessful(), "resource_warnings": resources}, indent=2))
assert result.testsRun == 1 and result.wasSuccessful()
assert len(resources) == (3 if mode == "baseline" else 0), resources
if mode == "baseline":
    assert all(Path(item["filename"]).name == "test_lineup_frame_extractor.py" and
               item["lineno"] == 172 and "unclosed file" in item["message"] for item in resources)
