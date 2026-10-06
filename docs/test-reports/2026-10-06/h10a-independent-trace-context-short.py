"""Use a short private marker so validation repr truncation cannot hide leakage."""
import importlib.util
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location("frozen_invocation_context",
    Path(__file__).with_name("h10a-independent-trace-context.py"))
frozen = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frozen)
frozen.SENTINEL = "priv_ctx_17"

if __name__ == "__main__":
    unittest.main(module=frozen, verbosity=2)
