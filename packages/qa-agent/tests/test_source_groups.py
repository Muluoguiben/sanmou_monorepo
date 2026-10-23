from __future__ import annotations

import unittest

from qa_agent.quality_eval.source_groups import (
    EvaluationSample, SourceDocument, audit_source_groups, require_split_integrity,
)


def document(name, *, parents=(), digest=None, family_ids=(), reviewed=True):
    return SourceDocument(document_id=name, derived_from=parents, content_sha256=digest,
                          family_ids=family_ids, lineage_status="reviewed" if reviewed else "unknown")


def sample(name, source, split="dev", exposed=False):
    return EvaluationSample(sample_id=name, source_ids=(source,), split=split, developer_exposed=exposed)


class SourceGroupTests(unittest.TestCase):
    def test_original_excerpt_and_repost_are_transitively_grouped(self):
        docs = [document("original"), document("excerpt", parents=("original",)),
                document("repost", parents=("excerpt",))]
        samples = [sample("train-a", "original", "train"), sample("held-b", "repost", "holdout")]
        report = audit_source_groups(docs, samples)
        self.assertFalse(report.split_integrity_passed)
        self.assertEqual(len(report.groups), 1)
        self.assertEqual(report.issues[0].code, "cross_split_source_family")
        with self.assertRaisesRegex(ValueError, "cross_split"):
            require_split_integrity(docs, samples)

    def test_exact_content_copies_and_declared_families_join(self):
        docs = [document("original", digest="a" * 64), document("copy", digest="a" * 64),
                document("translation", family_ids=("family-x",)), document("rewrite", family_ids=("family-x",))]
        samples = [sample("a", "original", "dev"), sample("b", "copy", "holdout"),
                   sample("c", "translation", "train"), sample("d", "rewrite", "dev")]
        report = audit_source_groups(docs, samples)
        self.assertEqual(len(report.groups), 2)
        self.assertEqual(len(report.issues), 2)
        self.assertFalse(report.split_integrity_passed)

    def test_unrelated_sources_can_have_different_splits_without_certifying_gold(self):
        report = require_split_integrity([document("one"), document("two")],
                                        [sample("a", "one", "train"), sample("b", "two", "holdout")])
        self.assertTrue(report.split_integrity_passed)
        self.assertFalse(report.independent_holdout_verified)
        self.assertFalse(report.human_gold)

    def test_exposure_in_review_queue_contaminates_related_holdout(self):
        report = audit_source_groups([document("source"), document("rewrite", parents=("source",))],
                                     [sample("review", "source", "review_queue", exposed=True),
                                      sample("holdout", "rewrite", "holdout")])
        self.assertEqual([issue.code for issue in report.issues], ["exposed_holdout"])
        self.assertEqual(report.review_queue_count, 1)

    def test_unknown_lineage_cannot_pass_holdout_check(self):
        report = audit_source_groups([document("source", reviewed=False)], [sample("held", "source", "holdout")])
        self.assertEqual(report.issues[0].code, "unreviewed_holdout_lineage")
        self.assertFalse(report.split_integrity_passed)

    def test_unspecified_exposure_is_not_treated_as_unexposed(self):
        report = audit_source_groups([document("source")],
                                     [EvaluationSample(sample_id="held", source_ids=("source",), split="holdout")])
        self.assertEqual(report.issues[0].code, "unknown_holdout_exposure")
        self.assertFalse(report.split_integrity_passed)

    def test_missing_parent_or_sample_source_fails(self):
        with self.assertRaisesRegex(ValueError, "unknown parent"):
            audit_source_groups([document("child", parents=("absent",))], [])
        with self.assertRaisesRegex(ValueError, "unknown sample source"):
            audit_source_groups([document("known")], [sample("one", "absent")])

    def test_duplicate_document_and_sample_ids_fail(self):
        with self.assertRaisesRegex(ValueError, "duplicate document"):
            audit_source_groups([document("one"), document("one")], [])
        with self.assertRaisesRegex(ValueError, "duplicate sample"):
            audit_source_groups([document("one")], [sample("same", "one"), sample("same", "one")])

    def test_cycles_fail(self):
        with self.assertRaisesRegex(ValueError, "cyclic"):
            audit_source_groups([document("one", parents=("two",)), document("two", parents=("one",))], [])

    def test_order_does_not_change_report(self):
        docs = [document("one"), document("two", parents=("one",)), document("three")]
        samples = [sample("a", "one", "dev"), sample("b", "two", "holdout"), sample("c", "three", "train")]
        self.assertEqual(audit_source_groups(docs, samples), audit_source_groups(list(reversed(docs)), list(reversed(samples))))

    def test_multi_source_sample_checks_every_family(self):
        docs = [document("one"), document("two")]
        samples = [sample("a", "one", "train"),
                   EvaluationSample(sample_id="b", source_ids=("two", "one"), split="holdout")]
        self.assertFalse(audit_source_groups(docs, samples).split_integrity_passed)

    def test_development_material_stays_development(self):
        report = require_split_integrity([document("source", reviewed=False)], [sample("dev", "source", "dev", exposed=True)])
        self.assertTrue(report.split_integrity_passed)
        self.assertFalse(report.independent_holdout_verified)


if __name__ == "__main__":
    unittest.main()
