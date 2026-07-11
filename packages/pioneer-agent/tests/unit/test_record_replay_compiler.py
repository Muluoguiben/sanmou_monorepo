from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

import yaml

from pioneer_agent.app.record_replay import build_parser, main
from pioneer_agent.record_replay.compiler import compile_recording
from pioneer_agent.record_replay.replayer import build_replay_plan
from pioneer_agent.record_replay.session_store import load_recording
from tests.unit.record_replay_fixtures import create_completed_session


class RecordReplayCompilerTests(unittest.TestCase):
    def test_record_is_raw_only_and_rejects_inline_compile(self) -> None:
        parser = build_parser()

        raw_args = parser.parse_args(
            ["record", "--workflow-name", "open recruit panel"]
        )
        self.assertEqual(raw_args.command, "record")
        with self.assertRaises(SystemExit) as raised:
            parser.parse_args(
                ["record", "--workflow-name", "open recruit panel", "--compile"]
            )
        self.assertEqual(raised.exception.code, 2)

    def test_compiles_candidates_plan_and_non_executable_skill_draft(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest = create_completed_session(
                root, workflow_name="claim chapter reward"
            )

            report = compile_recording(root)

            self.assertEqual(report.candidate_count, 1)
            candidate = json.loads(
                (root / "compiled" / "action_candidates.jsonl").read_text(encoding="utf-8")
            )
            self.assertEqual(candidate["execution_authority"], "none")
            self.assertEqual(candidate["source_events_sha256"], manifest.events_sha256)
            self.assertIsNone(candidate["semantic_target"])
            self.assertIsNone(candidate["proposed_action_type"])
            self.assertFalse(candidate["promotion_gates"]["human_review"])
            plan = json.loads((root / "compiled" / "replay_plan.json").read_text())
            self.assertFalse(plan["live_dispatch_allowed"])
            self.assertEqual(plan["source_events_sha256"], manifest.events_sha256)
            skill = (root / "compiled" / "draft_skill" / "SKILL.md").read_text()
            self.assertIn("Execution authority: none", skill)
            self.assertIn("Sample coordinates are evidence only", skill)
            self.assertIn(manifest.events_sha256, skill)
            self.assertEqual(report.source_events_sha256, manifest.events_sha256)

    def test_offline_replay_plan_never_grants_dispatch(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)
            plan = build_replay_plan(load_recording(root))

            self.assertFalse(plan.live_dispatch_allowed)
            self.assertEqual(plan.execution_authority, "none")
            self.assertGreater(len(plan.blockers), 3)

    def test_cli_validate_and_compile(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            self.assertEqual(main(["validate", str(root)]), 0)
            self.assertEqual(main(["compile", str(root)]), 0)

    def test_cli_explicitly_rejects_live_replay(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            create_completed_session(root)

            with self.assertRaises(SystemExit) as raised:
                main(["replay", str(root), "--execute"])
            self.assertEqual(raised.exception.code, 2)

    def test_draft_frontmatter_quotes_workflow_name_as_data(self) -> None:
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflow_name = 'claim: reward # still data "quoted"'
            create_completed_session(root, workflow_name=workflow_name)

            compile_recording(root)

            skill = (root / "compiled" / "draft_skill" / "SKILL.md").read_text(
                encoding="utf-8"
            )
            frontmatter = skill.split("---", 2)[1]
            metadata = yaml.safe_load(frontmatter)
            self.assertEqual(
                metadata["name"],
                "sanmou-claim-reward-still-data-quoted-recorded-draft",
            )
            self.assertIn(workflow_name, metadata["description"])

    @unittest.skipIf(os.name == "nt", "symlink semantics are covered on the WSL test host")
    def test_rejects_symlinked_compiled_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root)
            outside = base / "outside"
            outside.mkdir()
            (root / "compiled").symlink_to(outside, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "directory cannot be a symlink"):
                compile_recording(root)
            self.assertEqual(list(outside.iterdir()), [])

    @unittest.skipIf(os.name == "nt", "symlink semantics are covered on the WSL test host")
    def test_rejects_symlinked_draft_skill_directory(self) -> None:
        with TemporaryDirectory() as tmp:
            base = Path(tmp)
            root = base / "session"
            create_completed_session(root)
            (root / "compiled").mkdir()
            outside = base / "outside"
            outside.mkdir()
            (root / "compiled" / "draft_skill").symlink_to(
                outside, target_is_directory=True
            )

            with self.assertRaisesRegex(ValueError, "directory cannot be a symlink"):
                compile_recording(root)
            self.assertEqual(list(outside.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
