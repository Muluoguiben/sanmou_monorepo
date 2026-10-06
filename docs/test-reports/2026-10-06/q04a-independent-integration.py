"""Frozen public CLI/source/fixture controls; no product code modifications."""
import copy
import hashlib
import importlib.util
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
spec = importlib.util.spec_from_file_location("public_controls", Path(__file__).with_name("q04a-independent-probes.py"))
public = importlib.util.module_from_spec(spec)
spec.loader.exec_module(public)


class IntegrationControls(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="q04a-independent-")
        self.addCleanup(self.temp.cleanup)
        self.package = Path(self.temp.name) / "qa-agent"
        # Only ordinary Python source; no KB/archive/config/credentials copied.
        for source in (PACKAGE / "src").rglob("*.py"):
            target = self.package / source.relative_to(PACKAGE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        self.fixture = self.package / "tests/fixtures/quality_eval/claim_spans_v1"
        self.fixture.mkdir(parents=True)
        self.corpus = {"protocol": "qa-claim-spans/v1", "normalization": "utf8-crlf-to-lf-codepoint-v1",
                       "split": "development", "synthetic": True, "label_origin": "developer-authored", "cases": []}
        for name, value, expected in public.controls():
            if name == "human-is-external-declaration":
                continue
            count = sum(len(s["support_spans"]) for s in value["annotation"]["segments"])
            self.corpus["cases"].append({"id": name, **value,
                "annotation_sha256": public.annotation_hash(value["annotation"]),
                "expected": {"mechanical": {"valid_links": {"numerator": count, "denominator": count,
                           "value": 1.0 if count else None}}, "semantic": expected}})
        self.env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        self.env["PYTHONPATH"] = str(self.package / "src") + os.pathsep + "/tmp/sanmou-cr-20261005-6155-deps"
        self.output = Path(self.temp.name) / "result.json"

    def write_fixture(self):
        raw = json.dumps(self.corpus, ensure_ascii=False, indent=2)
        (self.fixture / "cases.json").write_text(raw, encoding="utf-8")
        freeze = {"protocol": self.corpus["protocol"], "normalization": self.corpus["normalization"],
                  "baseline": "claim-spans-v1", "cases_sha256": public.digest(raw)}
        (self.fixture / "freeze.json").write_text(json.dumps(freeze), encoding="utf-8")

    def cli(self, extra=None):
        return subprocess.run([sys.executable, "-B", "-m", "qa_agent.quality_eval.claim_spans",
            "--baseline", "claim-spans-v1", "--output", str(self.output)] if extra is None else extra,
            cwd=self.package, env=self.env, capture_output=True, text=True, timeout=30)

    def test_actual_cli_independent_controls_and_no_clobber(self):
        self.write_fixture()
        first = self.cli()
        self.assertEqual(first.returncode, 0, first.stderr)
        raw = self.output.read_bytes()
        report = json.loads(raw)
        self.assertEqual(report["controls"], {"numerator": 9, "denominator": 9, "value": 1})
        self.assertTrue(report["gate_pass"])
        self.assertEqual(report["provider"], {"calls": 0, "quality": "not_measured"})
        self.assertEqual(report["execution_authority"], "none")
        self.assertIs(report["executable"], False)
        self.assertIs(report["human_review"]["authenticated"], False)
        self.assertIs(report["holdout"]["established"], False)
        second = self.cli()
        self.assertNotEqual(second.returncode, 0)
        self.assertIn("FileExistsError", second.stderr)
        self.assertEqual(self.output.read_bytes(), raw)

    def test_rebound_human_claim_cannot_upgrade_synthetic_suite(self):
        first = self.corpus["cases"][0]
        first["annotation"]["review_status"] = "human-reviewed"
        first["annotation_sha256"] = public.annotation_hash(first["annotation"])
        first["expected"]["semantic"]["review_status"] = "human-reviewed"
        self.write_fixture()  # Rebind freeze so rejection is not stale-hash vacuity.
        result = self.cli()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("synthetic cases cannot claim human review", result.stderr)
        self.assertFalse(self.output.exists())

    def test_fixture_drift_then_rebound_wrong_expected_is_real_failure(self):
        self.write_fixture()
        with (self.fixture / "cases.json").open("a", encoding="utf-8") as stream:
            stream.write(" ")
        drift = self.cli()
        self.assertNotEqual(drift.returncode, 0)
        self.assertIn("fixture drift", drift.stderr)
        self.assertFalse(self.output.exists())
        self.corpus["cases"][0]["expected"]["semantic"]["claims"] = 99
        self.write_fixture()
        failed_control = self.cli()
        self.assertEqual(failed_control.returncode, 1, failed_control.stderr)
        report = json.loads(self.output.read_bytes())
        self.assertFalse(report["gate_pass"])
        self.assertEqual(report["controls"]["numerator"], 8)

    def test_real_mixed_scoring_origin_and_wrong_root_fail(self):
        self.write_fixture()
        code = """import importlib.util, sys
from pathlib import Path
from qa_agent.quality_eval import claim_spans
spec = importlib.util.spec_from_file_location('qa_agent.quality_eval.scoring', sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
sys.modules[spec.name] = module
claim_spans.run(Path(sys.argv[2]))
"""
        result = self.cli([sys.executable, "-B", "-c", code,
            str(PACKAGE / "src/qa_agent/quality_eval/scoring.py"), str(self.package)])
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source mismatch", result.stderr)
        self.assertIn("scoring", result.stderr)
        wrong = self.cli([sys.executable, "-B", "-c",
            "from pathlib import Path; from qa_agent.quality_eval.claim_spans import run; run(Path('.').parent)"])
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("source mismatch", wrong.stderr)


if __name__ == "__main__":
    unittest.main()
