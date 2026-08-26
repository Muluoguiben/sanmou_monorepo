from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pioneer_agent.app import game_agent


class GameAgentCliTests(unittest.TestCase):
    def test_game_subprocess_receives_absolute_source_and_read_only_module(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "frame.png"
            screenshot.write_bytes(b"png")
            args = game_agent.build_parser().parse_args(
                [
                    "--screenshot",
                    str(screenshot),
                    "--journal-path",
                    str(root / "journal.json"),
                    "--tool-log-path",
                    str(root / "tools.jsonl"),
                ]
            )

            parameters = game_agent._game_parameters(args)

            self.assertEqual(
                parameters.args[:2],
                ["-m", "pioneer_agent.app.game_mcp"],
            )
            source_index = parameters.args.index("--screenshot") + 1
            self.assertEqual(Path(parameters.args[source_index]), screenshot.resolve())
            self.assertNotIn("execute", " ".join(parameters.args))

    def test_qa_subprocess_does_not_inherit_secret_environment(self) -> None:
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "private",
                "SESSION_TOKEN": "private",
                "SAFE_SETTING": "kept",
            },
            clear=False,
        ):
            qa_env = game_agent._child_env(include_vision_credentials=False)
            game_env = game_agent._child_env(include_vision_credentials=True)

        self.assertNotIn("OPENAI_API_KEY", qa_env)
        self.assertNotIn("SESSION_TOKEN", qa_env)
        self.assertEqual(qa_env["SAFE_SETTING"], "kept")
        self.assertIn("packages/qa-agent/src", qa_env["PYTHONPATH"])
        self.assertEqual(game_env["OPENAI_API_KEY"], "private")
        self.assertNotIn("SESSION_TOKEN", game_env)


if __name__ == "__main__":
    unittest.main()
