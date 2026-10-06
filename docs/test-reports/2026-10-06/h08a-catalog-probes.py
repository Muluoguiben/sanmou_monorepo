"""Fixed-source private-catalog invariants; never exposes public registration."""
import hashlib
import json
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness import skill_registry as registry


class InternalCatalogControls(unittest.TestCase):
    def entrypoints(self):
        return (registry.list_skills,
                lambda: registry.resolve_skill("chapter-observer", "1.0.0"),
                lambda: registry.compile_skill("chapter-observer", "1.0.0", {"target_chapter": 3},
                    metrics={"progress.current_chapter_id": 1}))

    def test_duplicate_unrequested_peer_is_checked_before_lookup(self):
        builtin = registry._BUILTINS[0].model_copy(deep=True)
        peer = builtin.model_copy(deep=True)
        peer.skill_id, peer.version = "unrequested-peer", "9.9.9"
        with patch.object(registry, "_BUILTINS", (builtin, peer, peer.model_copy(deep=True))):
            for entrypoint in self.entrypoints():
                with self.subTest(entrypoint=entrypoint), self.assertRaisesRegex(ValueError, "duplicate"):
                    entrypoint()
        self.assertEqual(len(registry.list_skills()), 1)

    def test_rehashed_altered_definition_is_not_admitted(self):
        changed = registry._BUILTINS[0].model_copy(deep=True)
        changed.preconditions[0].value = 0
        payload = changed.model_dump(mode="json", exclude={"template_digest"})
        changed.template_digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True,
            separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
        with patch.object(registry, "_BUILTINS", (changed,)):
            for entrypoint in self.entrypoints():
                with self.subTest(entrypoint=entrypoint), self.assertRaisesRegex(ValueError, "allowlist"):
                    entrypoint()
        self.assertEqual(registry.resolve_skill("chapter-observer", "1.0.0").preconditions[0].value, 1)


if __name__ == "__main__":
    unittest.main()
