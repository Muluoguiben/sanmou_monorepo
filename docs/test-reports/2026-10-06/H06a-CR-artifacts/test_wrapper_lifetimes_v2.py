"""Correct fixture policy: enough decisions for same-runner sequential resume.

Original probe/log retained: one-decision FakeDecisionPolicy intentionally returns
stop when exhausted, so expecting success on later resume was a probe setup error.
All production assertions and other lifecycle scenarios remain unchanged.
"""
import unittest
import test_wrapper_lifetimes as original


def pause_then_continue():
    return original.f.FakeDecisionPolicy([
        original.f.PolicyDecision(action="pause", reason="pause"),
        original.f.PolicyDecision(action="continue", reason="resume"),
        original.f.PolicyDecision(action="continue", reason="resume"),
    ])


original.pause_policy = pause_then_continue

if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(original.WrapperLifetimes))
    raise SystemExit(not result.wasSuccessful())
