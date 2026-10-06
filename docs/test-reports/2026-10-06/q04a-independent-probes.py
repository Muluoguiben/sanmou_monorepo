"""Public-memo claim-span controls with manually chosen legacy expectations."""
import copy
import json
from pathlib import Path
import sys
import unittest

from qa_agent.quality_eval.scoring import digest, score_answer


def normalized(text):
    return text.replace("\r\n", "\n")


def annotation_hash(annotation):
    return digest(json.dumps(annotation, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def ratio(n, d):
    return {"numerator": n, "denominator": d, "value": n / d if d else None}


def expected(review="developer-authored", *, claims=1, unjudged=0, citations=(1, 1),
             support=(1, 1), completeness=(1, 1), context=(1, 1)):
    return {"review_status": review, "claims": claims, "unjudged_claims": unjudged,
        "citation_id_validity": ratio(*citations), "claim_support": ratio(*support),
        "supported_citation_completeness": ratio(*completeness), "context_correctness": ratio(*context),
        "semantic_method": "external-span-adjudication; no automatic entailment"}


def case(answer="粮食10[e1]", evidence=None, *, verdict="supported", review="developer-authored",
         context="问题", context_verdict="correct", spans=None):
    evidence = {"e1": "粮食10"} if evidence is None else evidence
    spans = ([{"entry_id": key, "content_sha256": digest(text), "start": 0, "end": len(normalized(text))}
              for key, text in evidence.items()] if spans is None else spans)
    annotation = {"protocol": "qa-claim-spans/v1", "normalization": "utf8-crlf-to-lf-codepoint-v1",
        "context_sha256": digest(context), "answer_sha256": digest(answer),
        "evidence_sha256": {key: digest(text) for key, text in evidence.items()},
        "review_status": review, "source": "independent synthetic control", "reviewer": "declared developer",
        "context_verdict": context_verdict,
        "segments": [{"start": 0, "end": len(normalized(answer)), "verdict": verdict, "support_spans": spans}]}
    return {"answer": answer, "evidence": evidence, "context": context, "annotation": annotation}


def controls():
    values = [
        ("paraphrase-not-substring", case("粮食为十[e1]"), expected()),
        ("wrong-number-valid-span", case("粮食20[e1]", verdict="unsupported"), expected(support=(0, 1), completeness=(0, 1))),
        ("wrong-citation-is-data", case("粮食10[missing]"), expected(citations=(0, 1), completeness=(0, 1))),
        ("missing-citation-is-data", case("粮食10"), expected(citations=(0, 0), completeness=(0, 1))),
        ("unknown-conflict", case("无法确定[e1][e2]", {"e1": "粮食10", "e2": "粮食20"},
            verdict="unknown", context_verdict="unknown"), expected(unjudged=1, citations=(2, 2), support=(0, 0), completeness=(0, 1), context=(0, 0))),
        ("unreviewed-not-pass", case(review="unreviewed"), expected("unreviewed", unjudged=1, support=(0, 0), completeness=(0, 1), context=(0, 0))),
        ("empty-evidence-nonclaim", case("备注。", {}, verdict="nonclaim", context_verdict="unknown", spans=[]),
            expected(claims=0, citations=(0, 0), support=(0, 0), completeness=(0, 0), context=(0, 0))),
        ("human-is-external-declaration", case(review="human-reviewed"), expected("human-reviewed")),
    ]
    multiple = case(evidence={"e1": "粮食10，奖励20"})
    first = multiple["annotation"]["segments"][0]["support_spans"][0]
    first["end"] = 4
    multiple["annotation"]["segments"][0]["support_spans"].append({**first, "start": 5, "end": 9})
    values.append(("two-spans-one-claim-id", multiple, expected()))
    unicode = case("甲\r\n🙂[e1]", {"e1": "甲\r\n🙂e\u0301"}, context="问\r\n题")
    unicode["annotation"]["segments"][0]["support_spans"][0].update(start=2, end=5)
    values.append(("codepoints-crlf-combining", unicode, expected()))
    return values


def legacy_projection(value):
    a = copy.deepcopy(value["annotation"])
    a.pop("protocol")
    a.pop("normalization")
    for segment in a["segments"]:
        segment["support_ids"] = list(dict.fromkeys(link["entry_id"] for link in segment.pop("support_spans")))
    return a


def legacy_component(value):
    # Memo promises the unchanged scorer result, not a private container name.
    if hasattr(value, "model_dump"):
        value = value.model_dump(mode="json")
    keys = set(expected())
    matches = []
    def visit(item):
        if isinstance(item, dict):
            if keys <= set(item): matches.append({key: item[key] for key in keys})
            for child in item.values(): visit(child)
        elif isinstance(item, (list, tuple)):
            for child in item: visit(child)
    visit(value)
    if len(matches) != 1:
        raise AssertionError("Public result must contain one unambiguous legacy scoring result")
    return matches[0]


def score(value, supplied_hash=None):
    from qa_agent.quality_eval.claim_spans import score_claim_spans
    return score_claim_spans(value["answer"], value["evidence"], value["annotation"], context=value["context"],
        annotation_sha256=supplied_hash or annotation_hash(value["annotation"]))


class PublicSpanControls(unittest.TestCase):
    def test_manual_semantic_and_denominator_controls(self):
        for name, value, oracle in controls():
            with self.subTest(case=name):
                self.assertEqual(legacy_component(score(value)), oracle)

    def test_schema_offsets_duplicates_and_label_constraints(self):
        mutations = [
            ("protocol", lambda a: a.update(protocol="qa-claim-spans/v2")),
            ("normalization", lambda a: a.update(normalization="utf16")),
            ("extra", lambda a: a.update(trusted=True)),
            ("missing", lambda a: a.pop("context_sha256")),
            ("wrong-review", lambda a: a.update(review_status="verified-by-system")),
            ("bool-answer-offset", lambda a: a["segments"][0].update(start=False)),
            ("gap", lambda a: a["segments"][0].update(start=1)),
            ("uncovered", lambda a: a["segments"][0].update(end=3)),
            ("supported-no-link", lambda a: a["segments"][0].update(support_spans=[])),
            ("nonclaim-has-link", lambda a: a["segments"][0].update(verdict="nonclaim")),
            ("duplicate-link", lambda a: a["segments"][0]["support_spans"].append(copy.deepcopy(a["segments"][0]["support_spans"][0]))),
        ]
        for key, bad in (("start", True), ("start", 0.0), ("end", "4"), ("start", -1),
                         ("end", 99), ("end", 0), ("entry_id", "missing"), ("content_sha256", "0" * 64)):
            mutations.append((key + repr(bad), lambda a, k=key, v=bad: a["segments"][0]["support_spans"][0].update({k: v})))
        for name, mutate in mutations:
            with self.subTest(case=name):
                value = case()
                mutate(value["annotation"])
                with self.assertRaises((ValueError, TypeError)):
                    score(value)  # Repin annotation hash to isolate the changed schema/link.

    def test_each_content_binding_rejects_drift_independently(self):
        values = []
        v = case(); v["context"] = "变题"; values.append(v)
        v = case(); v["answer"] = "粮食11[e1]"; values.append(v)
        v = case(); v["evidence"]["e1"] = "粮食11"; values.append(v)
        v = case(); v["annotation"]["evidence_sha256"]["e1"] = "0" * 64; values.append(v)
        for value in values:
            with self.subTest(value=value), self.assertRaises((ValueError, TypeError)):
                score(value)
        with self.assertRaises((ValueError, TypeError)):
            score(case(), "0" * 64)

    def test_unicode_is_codepoint_not_byte_utf16_or_nfc(self):
        value = case("🙂[e1]", {"e1": "🙂"})
        self.assertEqual(legacy_component(score(value)), expected())
        for bad_end in (2, 4):
            bad = copy.deepcopy(value)
            bad["annotation"]["segments"][0]["support_spans"][0]["end"] = bad_end
            with self.subTest(end=bad_end), self.assertRaises((ValueError, TypeError)):
                score(bad)
        decomposed = case("说明[e1]", {"e1": "e\u0301"})
        self.assertEqual(legacy_component(score(decomposed)), expected())
        decomposed["evidence"]["e1"] = "é"
        with self.assertRaises((ValueError, TypeError)): score(decomposed)

    def test_bare_cr_and_unencodable_text_are_rejected(self):
        for field in ("answer", "context", "evidence"):
            for suffix in ("\r", "\ud800"):
                value = case()
                if field == "evidence": value[field]["e1"] += suffix
                else: value[field] += suffix
                with self.subTest(field=field, suffix=repr(suffix)), self.assertRaises((ValueError, TypeError)):
                    score(value)


if __name__ == "__main__":
    if sys.argv[1:] == ["--verify-legacy-oracles"]:
        rows = []
        for name, value, oracle in controls():
            actual = score_answer(normalized(value["answer"]), {k: normalized(v) for k, v in value["evidence"].items()},
                legacy_projection(value), context=normalized(value["context"]))
            if actual != oracle: raise AssertionError((name, actual, oracle))
            rows.append({"id": name, "expected_legacy": oracle})
        print(json.dumps({"manual_controls": len(rows), "all_match_unchanged_legacy_scorer": True, "controls": rows}, ensure_ascii=False, indent=2))
    else:
        unittest.main(verbosity=2)
