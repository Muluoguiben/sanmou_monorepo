import unittest

from pioneer_agent.derivation.readiness import compute_combat_readiness


class ReadinessTests(unittest.TestCase):
    def test_compute_combat_readiness_returns_primary_constraint(self) -> None:
        result = compute_combat_readiness(
            {"container_stamina": 10, "soldiers": 10000, "position_context": "outer", "status": "idle"},
            {"avg_level": 20},
        )
        self.assertIn("combat_readiness_score", result)
        self.assertIn("primary_constraint", result)


if __name__ == "__main__":
    unittest.main()
