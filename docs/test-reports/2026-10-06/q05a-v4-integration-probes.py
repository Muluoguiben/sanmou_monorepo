"""Public v4/CLI controls frozen from accepted memo, before implementation review."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(sys.argv.pop(1)).resolve()
PACKAGE = ROOT / "packages/qa-agent"


class V4IntegrationControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="q05a-v4-cr-")
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name) / "qa-agent"
        # Explicit ordinary-source/KB-file allowlist, no archive/config/credentials.
        sources = list((PACKAGE / "src").rglob("*.py"))
        sources += list((PACKAGE / "knowledge_sources").rglob("*.yaml"))
        sources += [PACKAGE / "tests/fixtures/quality_eval/v4" / name for name in ("cases.json", "freeze.json")]
        for source in sources:
            target = self.package / source.relative_to(PACKAGE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        self.fixture = self.package / "tests/fixtures/quality_eval/v4"
        self.corpus = json.loads((self.fixture / "cases.json").read_text(encoding="utf-8-sig"))
        self.frozen = json.loads((self.fixture / "freeze.json").read_text(encoding="utf-8-sig"))
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        self.env.pop("SANMOU_CAPTURE_TOKEN", None)
        self.env["PYTHONPATH"] = str(self.package / "src") + os.pathsep + "/tmp/sanmou-cr-20261005-6155-deps"

    def rebind(self, corpus):
        raw = json.dumps(corpus, ensure_ascii=False, indent=2)
        frozen = {**self.frozen, "cases_sha256": hashlib.sha256(raw.replace("\r\n", "\n").encode()).hexdigest()}
        (self.fixture / "cases.json").write_text(raw, encoding="utf-8")
        (self.fixture / "freeze.json").write_text(json.dumps(frozen, ensure_ascii=False), encoding="utf-8")

    def cli(self, name):
        output = Path(self.temp.name) / (name + ".json")
        run = subprocess.run([sys.executable, "-B", "-m", "qa_agent.quality_eval.runner", "--baseline", "v4",
            "--output", str(output)], cwd=self.package, env=self.env, capture_output=True, text=True, timeout=60)
        return run, output

    def valid_control(self):
        run, path = self.cli("positive")
        self.assertEqual(run.returncode, 0, run.stderr)
        report = json.loads(path.read_bytes())
        self.assertIs(report["season"]["gate_pass"], True)
        return report

    def test_valid_wrong_expected_saves_failed_report_then_exit1_and_no_clobber(self):
        positive = self.valid_control()
        changed = copy.deepcopy(self.corpus)
        changed["season_cases"][0]["expected"]["match_ids"].append("independent-intentionally-wrong-id")
        self.rebind(changed)  # Valid schema + valid source and fixture binding.
        run, path = self.cli("wrong-expected")
        self.assertEqual(run.returncode, 1, run.stderr)
        self.assertTrue(path.exists(), run.stderr)
        raw = path.read_bytes()
        failed = json.loads(raw)
        self.assertIs(failed["season"]["gate_pass"], False)
        self.assertIsNone(failed["quality_threshold"])
        self.assertEqual({k: v for k, v in failed.items() if k not in {"season", "cases_sha256"}},
                         {k: v for k, v in positive.items() if k not in {"season", "cases_sha256"}})
        again, _ = self.cli("wrong-expected")
        self.assertNotEqual(again.returncode, 0)
        self.assertIn("FileExistsError", again.stderr)
        self.assertEqual(path.read_bytes(), raw)

    def test_v4_required_groups_are_not_masked_by_source_drift(self):
        self.valid_control()
        for group in ("assessment_cases", "multiturn_cases", "season_cases"):
            changed = copy.deepcopy(self.corpus)
            changed.pop(group)
            self.rebind(changed)
            run, path = self.cli("missing-" + group)
            with self.subTest(group=group):
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse(path.exists())
                self.assertIn(group, run.stderr)
                self.assertNotIn("frozen KB/production source drift", run.stderr)
                self.assertNotIn("query/label fixture drift", run.stderr)

    def test_malformed_season_schema_is_not_a_false_control_result(self):
        self.valid_control()
        mutations = [lambda c: c["season_cases"][0].update(top_k=True),
                     lambda c: c["season_cases"][0].update(top_k="2"),
                     lambda c: c["season_cases"][0].update(unexpected_field=1),
                     lambda c: c["season_cases"][0]["expected"].update(unexpected_field=1),
                     lambda c: c["season_cases"].append(copy.deepcopy(c["season_cases"][0]))]
        for index, mutate in enumerate(mutations):
            changed = copy.deepcopy(self.corpus)
            mutate(changed)
            self.rebind(changed)
            run, path = self.cli("malformed-" + str(index))
            with self.subTest(index=index):
                self.assertNotEqual(run.returncode, 0)
                self.assertFalse(path.exists(), "malformed case must not become a scored report")
                self.assertRegex(run.stderr, "ValidationError|ValueError")
                self.assertNotIn("frozen KB/production source drift", run.stderr)
                self.assertNotIn("query/label fixture drift", run.stderr)

    def test_real_foreign_lazy_season_module_origin_is_rejected(self):
        self.valid_control()
        code = """import importlib.util, sys
from pathlib import Path
from qa_agent.quality_eval import runner
name = 'qa_agent.quality_eval.season_cases'
spec = importlib.util.spec_from_file_location(name, sys.argv[1])
module = importlib.util.module_from_spec(spec)
sys.modules[name] = module
spec.loader.exec_module(module)
runner.run(Path(sys.argv[2]), baseline='v4')
"""
        run = subprocess.run([sys.executable, "-B", "-c", code,
            str(PACKAGE / "src/qa_agent/quality_eval/season_cases.py"), str(self.package)],
            cwd=self.package, env=self.env, capture_output=True, text=True, timeout=60)
        self.assertNotEqual(run.returncode, 0)
        self.assertIn("source mismatch: qa_agent.quality_eval.season_cases", run.stderr)
        self.assertNotIn("frozen KB/production source drift", run.stderr)


if __name__ == "__main__":
    unittest.main()
