from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path


class BilibiliWorkflowScriptTests(unittest.TestCase):
    def test_script_shows_usage_without_args(self) -> None:
        project_root = Path(__file__).resolve().parents[3]
        script = project_root / "scripts" / "bilibili_video_knowledge_workflow.sh"
        result = subprocess.run([str(script)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("Usage:", result.stderr)

    def test_script_runs_with_mocked_python_entrypoints(self) -> None:
        project_root = Path(__file__).resolve().parents[3]
        script = project_root / "scripts" / "bilibili_video_knowledge_workflow.sh"

        with tempfile.TemporaryDirectory() as temp_dir:
            mock_bin = Path(temp_dir) / "bin"
            mock_bin.mkdir()
            log_path = Path(temp_dir) / "calls.log"
            python_path = mock_bin / "python3"
            python_path.write_text(
                "#!/usr/bin/env bash\n"
                f"echo \"$@\" >> {log_path}\n"
                "exit 0\n",
                encoding="utf-8",
            )
            python_path.chmod(0o755)

            env = os.environ.copy()
            env["PATH"] = f"{mock_bin}:{env['PATH']}"
            workspace = Path(temp_dir) / "workspace"
            result = subprocess.run(
                [str(script), "BV1TEST123", str(workspace), "heuristic"],
                cwd=project_root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            logged = log_path.read_text(encoding="utf-8")
            self.assertIn("qa_agent.app.fetch_bilibili_bundle --bvid BV1TEST123", logged)
            self.assertIn("qa_agent.app.run_video_pipeline --input", logged)


if __name__ == "__main__":
    unittest.main()
