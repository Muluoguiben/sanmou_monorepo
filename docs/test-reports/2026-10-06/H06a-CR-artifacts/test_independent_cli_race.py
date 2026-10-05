"""Real independent CLI process contender at connection and cleanup barriers."""
import asyncio
from datetime import timedelta
import multiprocessing as mp
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from pioneer_agent.app import game_agent
from pioneer_agent.agent_harness.loop import RecommendationHarness
from test_task_runner import BASE, task
import test_task_cli as fixture


def cli_process(root, barrier, pipe):
    root = Path(root)
    class Client(fixture.ManagedSequence):
        async def parked(self):
            pipe.send({"event": "parked", "stage": barrier})
            if not await asyncio.to_thread(pipe.poll, 8):
                raise RuntimeError("review parent did not acknowledge barrier")
            await asyncio.to_thread(pipe.recv)
        async def __aenter__(self):
            self.entries += 1
            if barrier == "connect":
                await self.parked()
            return self
        async def __aexit__(self, *args):
            if barrier == "cleanup":
                await self.parked()
    client = Client()
    args = game_agent.build_parser().parse_args([
        "--screenshot", str(root / "unused.png"), "--task-spec", str(root / "task.json"),
        "--journal-path", str(root / "journal.json"), "--tool-log-path", str(root / "tools.jsonl"),
        "--run-state-path", str(root / "run.json"), "--run-trace-path", str(root / "trace.jsonl")])
    def harness(**kwargs):
        return RecommendationHarness(**kwargs, clock=lambda: BASE + timedelta(seconds=client.count + 1))
    with patch.object(game_agent, "RecommendationHarness", side_effect=harness):
        result = asyncio.run(game_agent._run_task(args, game_client=client))
    pipe.send({"event": "done", "result": result, "entries": client.entries, "calls": client.calls})


class IndependentCliRace(unittest.TestCase):
    def test_loser_zero_effects_before_connect_and_during_cleanup(self):
        ctx = mp.get_context("spawn")
        for stage in ("connect", "cleanup"):
            with self.subTest(stage=stage), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                (root / "task.json").write_text(task().model_dump_json())
                pairs = [ctx.Pipe(), ctx.Pipe()]
                children = [ctx.Process(target=cli_process, args=(tmp, stage, pairs[0][1])),
                            ctx.Process(target=cli_process, args=(tmp, "loser", pairs[1][1]))]
                try:
                    children[0].start()
                    self.assertTrue(pairs[0][0].poll(10))
                    self.assertEqual(pairs[0][0].recv()["event"], "parked")
                    path = root / "run.json"
                    before = path.read_bytes() if path.exists() else None
                    children[1].start()
                    self.assertTrue(pairs[1][0].poll(10))
                    loser = pairs[1][0].recv()
                    self.assertEqual(loser["result"]["reason"], "checkpoint_conflict")
                    self.assertEqual((loser["entries"], loser["calls"]), (0, []))
                    self.assertEqual(path.read_bytes() if path.exists() else None, before)
                    pairs[0][0].send("release")
                    self.assertTrue(pairs[0][0].poll(10))
                    self.assertEqual(pairs[0][0].recv()["result"]["status"], "succeeded")
                    for child in children:
                        child.join(5)
                        self.assertEqual(child.exitcode, 0)
                finally:
                    for child in children:
                        if child.pid and child.is_alive():
                            child.terminate()
                            child.join(3)
                    for pair in pairs:
                        for endpoint in pair:
                            endpoint.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
