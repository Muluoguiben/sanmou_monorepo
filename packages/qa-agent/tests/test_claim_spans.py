from __future__ import annotations

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

from qa_agent.quality_eval import claim_spans as spans
from qa_agent.quality_eval.scoring import digest, snapshot

PACKAGE = Path(__file__).resolve().parents[1]
FIXTURE = PACKAGE / "tests/fixtures/quality_eval/claim_spans_v1"


class ClaimSpanTests(unittest.TestCase):
    def setUp(self):
        self.corpus = json.loads((FIXTURE / "cases.json").read_text(encoding="utf-8"))
        self.cases = {case["id"]: case for case in self.corpus["cases"]}

    def score(self, case, *, rebind=False):
        if rebind:
            case["annotation_sha256"] = spans.annotation_digest(case["annotation"])
        return spans.score_claim_spans(case["answer"], case["evidence"], case["annotation"],
                                      context=case["context"], annotation_sha256=case["annotation_sha256"])

    def test_frozen_controls_and_no_network(self):
        with patch("socket.socket", side_effect=AssertionError("network forbidden")):
            report = spans.run(PACKAGE)
        self.assertEqual(report["controls"], {"numerator": 12, "denominator": 12, "value": 1})
        self.assertTrue(report["gate_pass"])
        self.assertEqual(report["provider"]["calls"], 0)
        self.assertEqual(report["execution_authority"], "none")
        self.assertFalse(report["executable"])
        self.assertFalse(report["holdout"]["established"])
        self.assertFalse(report["human_review"]["authenticated"])
        self.assertEqual(report["eval_source"], snapshot(PACKAGE, list((PACKAGE / "src/qa_agent/quality_eval").glob("*.py"))))

    def test_valid_links_are_not_semantic_support(self):
        for name in ("wrong-number", "wrong-entity"):
            result = self.score(self.cases[name])
            self.assertEqual(result["mechanical"]["valid_links"]["value"], 1)
            self.assertEqual(result["semantic"]["citation_id_validity"]["value"], 1)
            self.assertEqual(result["semantic"]["claim_support"]["value"], 0)
        conflict = self.score(self.cases["conflicting-sources"])
        self.assertIsNone(conflict["semantic"]["claim_support"]["value"])
        self.assertEqual(len(conflict["segments"][0]["support_spans"]), 2)

    def test_unknown_unreviewed_and_zero_denominators(self):
        for name in ("unreviewed", "unknown-no-links"):
            result = self.score(self.cases[name])["semantic"]
            self.assertEqual(result["claims"], 1)
            self.assertEqual(result["unjudged_claims"], 1)
            self.assertIsNone(result["claim_support"]["value"])
            self.assertEqual(result["supported_citation_completeness"], {"numerator": 0, "denominator": 1, "value": 0})
        for name in ("nonclaim", "empty-answer"):
            result = self.score(self.cases[name])
            self.assertIsNone(result["mechanical"]["valid_links"]["value"])
            self.assertIsNone(result["semantic"]["claim_support"]["value"])
            self.assertIsNone(result["semantic"]["supported_citation_completeness"]["value"])

    def test_bad_or_absent_citations_remain_scored(self):
        for name in ("missing-citation", "wrong-citation"):
            result = self.score(self.cases[name])["semantic"]
            self.assertEqual(result["claim_support"]["value"], 1)
            self.assertEqual(result["supported_citation_completeness"]["value"], 0)
        self.assertEqual(self.score(self.cases["wrong-citation"])["semantic"]["citation_id_validity"]["value"], 0)

    def test_same_id_multiple_spans_do_not_inflate_claim_denominator(self):
        result = self.score(self.cases["multiple-spans-one-id"])
        self.assertEqual(result["mechanical"]["valid_links"]["denominator"], 2)
        self.assertEqual(result["semantic"]["claim_support"]["denominator"], 1)
        self.assertEqual(result["semantic"]["supported_citation_completeness"]["value"], 1)

    def test_partial_citation_remains_in_all_claims_denominator(self):
        case = self.cases["multiple-spans-one-id"]
        cut = len(case["answer"])
        case["answer"] += "另一个声明没有引用。"
        first = case["annotation"]["segments"][0]
        second = copy.deepcopy(first)
        second.update(start=cut, end=len(case["answer"]))
        case["annotation"]["segments"] = [first, second]
        case["annotation"]["answer_sha256"] = digest(case["answer"])
        result = self.score(case, rebind=True)["semantic"]
        self.assertEqual(result["claims"], 2)
        self.assertEqual(result["claim_support"]["value"], 1)
        self.assertEqual(result["supported_citation_completeness"], {"numerator": 1, "denominator": 2, "value": .5})

    def test_codepoint_link_can_address_emoji_and_combining_character(self):
        case = self.cases["unicode-crlf-supported"]
        original = case["annotation"]["segments"][0]["support_spans"][0]
        case["annotation"]["segments"][0]["support_spans"] = [
            {**original, "start": 1, "end": 2}, {**original, "start": 3, "end": 4}]
        self.assertEqual(self.score(case, rebind=True)["mechanical"]["valid_links"]["denominator"], 2)

    def test_unicode_crlf_normalized_before_all_binding_and_offsets(self):
        case = self.cases["unicode-crlf-supported"]
        before = copy.deepcopy(case)
        result = self.score(case)
        self.assertIn("🙂e\u0301\r\n", case["answer"])
        case["answer"] = case["answer"].replace("\r\n", "\n")
        case["context"] = case["context"].replace("\r\n", "\n")
        case["evidence"] = {key: text.replace("\r\n", "\n") for key, text in case["evidence"].items()}
        self.assertEqual(result, self.score(case))
        self.assertEqual(before["annotation"], case["annotation"])

    def test_utf16_byte_or_grapheme_offsets_not_repaired(self):
        for end in (11, 18, 6):
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            case["annotation"]["segments"][0]["end"] = end
            with self.subTest(end=end), self.assertRaises(ValueError):
                self.score(case, rebind=True)

    def test_no_unicode_normalization_or_strip(self):
        for replacement in ("é", "e", " e\u0301"):
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            case["answer"] = case["answer"].replace("e\u0301", replacement)
            with self.subTest(replacement=replacement), self.assertRaises(ValueError):
                self.score(case)

    def test_bare_cr_and_unencodable_text_rejected_everywhere(self):
        for text in ("\r", "\ud800"):
            for target in ("answer", "context", "evidence"):
                case = copy.deepcopy(self.cases["unicode-crlf-supported"])
                if target == "evidence":
                    case[target]["a"] = text
                else:
                    case[target] = text
                with self.subTest(text=repr(text), target=target), self.assertRaises(ValueError):
                    self.score(case)

    def test_context_answer_evidence_and_label_hash_drift(self):
        for target in ("answer", "context", "evidence", "annotation"):
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            if target == "evidence": case[target]["a"] += "changed"
            elif target == "annotation": case[target]["reviewer"] = "another-declaration"
            else: case[target] += "changed"
            with self.subTest(target=target), self.assertRaises(ValueError):
                self.score(case)

    def test_link_bad_identity_hash_offsets_and_exact_duplicate(self):
        mutations = [("entry_id", "missing"), ("content_sha256", "0" * 64),
                     ("start", -1), ("start", 9), ("end", 0), ("end", 999),
                     ("start", True), ("end", False), ("start", 0.0), ("end", "9")]
        for key, value in mutations:
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            case["annotation"]["segments"][0]["support_spans"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                self.score(case, rebind=True)
        case = self.cases["unicode-crlf-supported"]
        links = case["annotation"]["segments"][0]["support_spans"]
        links.append(copy.deepcopy(links[0]))
        with self.assertRaisesRegex(ValueError, "duplicate"):
            self.score(case, rebind=True)

    def test_strict_annotation_segment_and_link_fields(self):
        for level in ("annotation", "segment", "link"):
            for change in ("extra", "missing"):
                case = copy.deepcopy(self.cases["unicode-crlf-supported"])
                target = case["annotation"]
                if level in ("segment", "link"): target = target["segments"][0]
                if level == "link": target = target["support_spans"][0]
                if change == "extra": target["unexpected"] = "not ignored"
                else: target.pop(next(iter(target)))
                with self.subTest(level=level, change=change), self.assertRaises(ValueError):
                    self.score(case, rebind=True)

    def test_versions_types_and_enum_values(self):
        for key, value in (("protocol", "v2"), ("normalization", "NFC"), ("review_status", "approved"),
                           ("context_verdict", "true"), ("segments", ()), ("source", ""),
                           ("reviewer", 42), ("answer_sha256", "A" * 64), ("evidence_sha256", [])):
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            case["annotation"][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): self.score(case, rebind=True)

    def test_answer_gaps_overlaps_and_bool_coordinates(self):
        for key, value in (("start", 1), ("start", -1), ("start", False), ("end", True), ("end", 1), ("end", 999)):
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            case["annotation"]["segments"][0][key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): self.score(case, rebind=True)
        case = self.cases["unicode-crlf-supported"]
        case["annotation"]["segments"] *= 2
        with self.assertRaises(ValueError): self.score(case, rebind=True)

    def test_nonclaim_and_supported_link_rules(self):
        for verdict in ("nonclaim", "supported"):
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            segment = case["annotation"]["segments"][0]
            segment["verdict"] = verdict
            if verdict == "supported": segment["support_spans"] = []
            with self.assertRaises(ValueError): self.score(case, rebind=True)

    def test_evidence_mapping_and_entry_id_validation(self):
        for evidence in ([], {"": "text"}, {"   ": "text"}, {"a\n": "text"}, {"[a]": "text"}, {1: "text"}, {"a": False}):
            case = copy.deepcopy(self.cases["unicode-crlf-supported"])
            case["evidence"] = evidence
            with self.subTest(evidence=evidence), self.assertRaises(ValueError): self.score(case)
        self.score(self.cases["empty-evidence-bad-citation"])

    def test_generic_human_label_is_only_unauthenticated_declaration(self):
        case = self.cases["unicode-crlf-supported"]
        case["annotation"]["review_status"] = "human-reviewed"
        result = self.score(case, rebind=True)
        self.assertEqual(result["semantic"]["review_status"], "human-reviewed")
        self.assertFalse(result["label_declaration"]["authenticated"])
        with self.assertRaisesRegex(ValueError, "cannot claim human"):
            spans._Corpus.model_validate(self.corpus)

    def test_corpus_strictness_duplicates_and_unreviewed_allowed(self):
        spans._Corpus.model_validate(self.corpus)
        for key, value in (("protocol", "v2"), ("synthetic", 1), ("synthetic", False),
                           ("label_origin", "human-reviewed"), ("split", "holdout"), ("cases", []), ("unexpected", 0)):
            corpus = copy.deepcopy(self.corpus)
            corpus[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError): spans._Corpus.model_validate(corpus)
        self.corpus["cases"].append(copy.deepcopy(self.corpus["cases"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate case"):
            spans._Corpus.model_validate(self.corpus)

    def test_frozen_fixture_drift_rejected(self):
        original = spans._json_text
        def changed(path):
            text = original(path)
            return text + " " if path.name == "cases.json" else text
        with patch.object(spans, "_json_text", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "fixture drift"): spans.run(PACKAGE)

    def test_drift_during_scoring_rejected(self):
        original = spans.snapshot
        calls = 0
        def changed(root, paths):
            nonlocal calls
            calls += 1
            result = original(root, paths)
            if calls == 3: result["digest"] = "changed"
            return result
        with patch.object(spans, "snapshot", side_effect=changed):
            with self.assertRaisesRegex(ValueError, "during run"): spans.run(PACKAGE)

    def test_wrong_package_and_mixed_module_origins_rejected(self):
        with self.assertRaisesRegex(ValueError, "source mismatch"): spans.run(PACKAGE / "other")
        fake = types.ModuleType("qa_agent.foreign")
        fake.__file__ = "/tmp/foreign/foreign.py"
        fake.__spec__ = importlib.util.spec_from_file_location(fake.__name__, fake.__file__)
        with patch.dict(sys.modules, {fake.__name__: fake}):
            with self.assertRaisesRegex(ValueError, "source mismatch"): spans.run(PACKAGE)
        with patch.object(spans, "__spec__", None):
            with self.assertRaisesRegex(ValueError, "source mismatch"): spans.run(PACKAGE)

    def test_duplicate_json_keys_and_bare_cr_file_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate JSON"):
            json.loads('{"a":1,"a":2}', object_pairs_hook=spans._unique_object)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "cases.json"
            path.write_bytes(b'{"x": 1}\r')
            with self.assertRaisesRegex(ValueError, "bare CR"): spans._json_text(path)

    def test_real_cli_create_only_and_explicit_version(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "report.json"
            env = dict(os.environ, PYTHONPATH=str(PACKAGE / "src") + os.pathsep + os.environ.get("PYTHONPATH", ""))
            env.pop("SANMOU_CAPTURE_TOKEN", None)
            argv = [sys.executable, "-m", "qa_agent.quality_eval.claim_spans", "--baseline", spans.BASELINE, "--output", str(output)]
            first = subprocess.run(argv, cwd=PACKAGE, env=env, capture_output=True, timeout=30)
            self.assertEqual(first.returncode, 0, first.stderr.decode())
            original = output.read_bytes()
            self.assertTrue(json.loads(original)["gate_pass"])
            second = subprocess.run(argv, cwd=PACKAGE, env=env, capture_output=True, timeout=30)
            self.assertNotEqual(second.returncode, 0)
            self.assertEqual(output.read_bytes(), original)
            missing = subprocess.run(argv[:3] + ["--output", str(output)], cwd=PACKAGE, env=env, capture_output=True, timeout=30)
            self.assertNotEqual(missing.returncode, 0)


if __name__ == "__main__":
    unittest.main()
