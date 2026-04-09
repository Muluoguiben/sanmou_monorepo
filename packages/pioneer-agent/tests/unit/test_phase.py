import unittest

from pioneer_agent.derivation.phase import derive_phase_tag


class PhaseDerivationTests(unittest.TestCase):
    def test_phase_tag_opening_sprint(self) -> None:
        self.assertEqual(derive_phase_tag(4, 60), "opening_sprint")


if __name__ == "__main__":
    unittest.main()
