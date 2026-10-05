import json
from datetime import timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from pioneer_agent.agent_harness.loop import RecommendationHarness
from pioneer_agent.app import game_agent
from test_task_runner import BASE, SequenceClient, task


class ManagedSequence(SequenceClient):
    def __init__(self):
        super().__init__()
        self.entries = 0
    async def __aenter__(self):
        self.entries += 1
        return self
    async def __aexit__(self, *args):
        return False


class TaskCliTests(unittest.IsolatedAsyncioTestCase):
    def args(self, root):
        spec = root / "task.json"
        spec.write_text(task().model_dump_json(), encoding="utf-8")
        return game_agent.build_parser().parse_args([
            "--screenshot", str(root / "unused.png"), "--task-spec", str(spec),
            "--journal-path", str(root / "journal.json"),
            "--tool-log-path", str(root / "tools.jsonl"),
            "--run-state-path", str(root / "run.json"),
            "--run-trace-path", str(root / "trace.jsonl"),
        ])

    async def test_cli_real_services_and_terminal_restart_without_connection(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            client = ManagedSequence()
            def make_harness(**kwargs):
                return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
            with patch.object(game_agent, "RecommendationHarness", side_effect=make_harness):
                first = await game_agent._run_task(self.args(root), game_client=client)
                self.assertEqual(first["status"], "succeeded")
                self.assertEqual(first["completed_steps"], 3)
                second = await game_agent._run_task(self.args(root), game_client=client)
            self.assertEqual(second["status"], "succeeded")
            self.assertEqual(client.entries, 1)
            state = json.loads((root / "run.json").read_text())
            self.assertEqual(len(state["budget_state"]["reservations"]), 15)
            traces = [json.loads(line) for line in (root / "trace.jsonl").read_text().splitlines()]
            self.assertEqual(sum(row["event"] == "policy" for row in traces), 3)

    async def test_task_paths_required_before_any_connection(self):
        with TemporaryDirectory() as tmp:
            args = self.args(Path(tmp))
            args.run_state_path = None
            client = ManagedSequence()
            with self.assertRaises(ValueError):
                await game_agent._run_task(args, game_client=client)
            self.assertEqual(client.entries, 0)

    async def test_qa_questions_not_silently_ignored(self):
        with TemporaryDirectory() as tmp:
            args = self.args(Path(tmp))
            args.qa_question = ["question"]
            client = ManagedSequence()
            with self.assertRaises(ValueError):
                await game_agent._run_task(args, game_client=client)
            self.assertEqual(client.entries, 0)


if __name__ == "__main__":
    unittest.main()
