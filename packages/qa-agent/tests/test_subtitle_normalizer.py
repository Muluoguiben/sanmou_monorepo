"""Unit tests for qa_agent.video.subtitle_normalizer."""
from __future__ import annotations

import unittest
from pathlib import Path

from qa_agent.video.builder import VideoEvidenceBundle, VideoEvidenceSegment, build_video_knowledge_document
from qa_agent.video.models import VideoFrameRef, VideoLineupCandidate, VideoSegment, VideoSource
from qa_agent.video.subtitle_normalizer import (
    AmbiguousPattern,
    NormalizationDictionary,
    NormalizationRule,
    _greedy_replace_exact,
    _levenshtein_le1,
    _neighborhood_has_other_canonical,
    build_dictionary_from_profiles,
    default_homophones_path,
    default_knowledge_sources_dir,
    normalize_candidate_fields,
    normalize_document,
    normalize_text,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _make_dictionary(
    rules: list[NormalizationRule],
    canonical_terms: set[str] | None = None,
    canonical_kind: dict[str, str] | None = None,
    ambiguous: list[AmbiguousPattern] | None = None,
) -> NormalizationDictionary:
    return NormalizationDictionary(
        exact_rules=list(rules),
        canonical_terms=set(canonical_terms or {r.canonical for r in rules}),
        canonical_kind=dict(canonical_kind or {r.canonical: r.kind for r in rules}),
        ambiguous_patterns=list(ambiguous or []),
    )


class LevenshteinTests(unittest.TestCase):
    def test_equal(self) -> None:
        self.assertTrue(_levenshtein_le1("祝融夫人", "祝融夫人"))

    def test_substitution_one_char(self) -> None:
        self.assertTrue(_levenshtein_le1("黄甫嵩", "皇甫嵩"))

    def test_insertion_one_char(self) -> None:
        self.assertTrue(_levenshtein_le1("祝融人", "祝融夫人"))

    def test_deletion_one_char(self) -> None:
        self.assertTrue(_levenshtein_le1("祝融夫夫人", "祝融夫人"))

    def test_two_substitutions(self) -> None:
        self.assertFalse(_levenshtein_le1("黄府松", "皇甫嵩"))

    def test_length_diff_greater_than_one(self) -> None:
        self.assertFalse(_levenshtein_le1("祝融", "祝融夫人"))


class GreedyExactReplaceTests(unittest.TestCase):
    def test_longest_match_wins(self) -> None:
        rules = [
            NormalizationRule(source="黄府", canonical="皇府", kind="other", confidence=0.9, rule_source="homophone"),
            NormalizationRule(source="黄府松", canonical="皇甫嵩", kind="hero", confidence=0.95, rule_source="homophone"),
        ]
        dictionary = _make_dictionary(rules)
        out, applied = _greedy_replace_exact("黄府松带兵", dictionary.sorted_exact_rules())
        self.assertEqual(out, "皇甫嵩带兵")
        self.assertEqual([r.canonical for r in applied], ["皇甫嵩"])

    def test_multi_occurrence_each_logged(self) -> None:
        rules = [
            NormalizationRule(source="屹然不动", canonical="岿然不动", kind="skill", confidence=0.95, rule_source="alias"),
        ]
        dictionary = _make_dictionary(rules)
        out, applied = _greedy_replace_exact("屹然不动 + 屹然不动", dictionary.sorted_exact_rules())
        self.assertEqual(out, "岿然不动 + 岿然不动")
        self.assertEqual(len(applied), 2)


class NeighborhoodGuardTests(unittest.TestCase):
    def test_other_canonical_in_window_blocks_fuzzy(self) -> None:
        canonicals = {"皇甫嵩", "皇甫嵩2"}
        self.assertTrue(
            _neighborhood_has_other_canonical(
                text="皇甫嵩带兵",
                start=0,
                end=4,
                proposed_canonical="皇甫嵩2",
                canonical_terms=canonicals,
            )
        )

    def test_no_other_canonical_allows_fuzzy(self) -> None:
        canonicals = {"皇甫嵩"}
        self.assertFalse(
            _neighborhood_has_other_canonical(
                text="黄甫嵩带兵",
                start=0,
                end=3,
                proposed_canonical="皇甫嵩",
                canonical_terms=canonicals,
            )
        )


class NormalizeTextTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dictionary = _make_dictionary(
            rules=[
                NormalizationRule(source="黄府松", canonical="皇甫嵩", kind="hero", confidence=0.95, rule_source="homophone"),
                NormalizationRule(source="屹然不动", canonical="岿然不动", kind="skill", confidence=0.95, rule_source="alias"),
            ],
            canonical_terms={"皇甫嵩", "岿然不动", "祝融夫人", "诸葛亮", "甘夫人"},
            canonical_kind={"皇甫嵩": "hero", "岿然不动": "skill", "祝融夫人": "hero", "诸葛亮": "hero", "甘夫人": "hero"},
            ambiguous=[
                AmbiguousPattern(
                    pattern="金汤",
                    candidates=["固若金汤", "金城汤池"],
                    kind="skill",
                    confidence=0.6,
                )
            ],
        )

    def test_exact_homophone_logged_as_homophone(self) -> None:
        logs = []
        out = normalize_text(
            "黄府松带兵",
            self.dictionary,
            segment_id="seg-1",
            video_id="BV-test",
            scope="transcript",
            log_sink=logs,
        )
        self.assertEqual(out, "皇甫嵩带兵")
        self.assertEqual(len(logs), 1)
        log = logs[0]
        self.assertEqual(log.before, "黄府松")
        self.assertEqual(log.after, "皇甫嵩")
        self.assertEqual(log.source, "homophone")
        self.assertEqual(log.rule_type, "exact")
        self.assertEqual(log.scope, "transcript")
        self.assertEqual(log.video_id, "BV-test")
        self.assertEqual(log.segment_id, "seg-1")
        self.assertEqual(log.kind, "hero")

    def test_fuzzy_edit_distance_logs_as_fuzzy(self) -> None:
        logs = []
        out = normalize_text(
            "黄甫嵩很强",
            self.dictionary,
            segment_id="seg-2",
            video_id="BV-fuzzy",
            scope="transcript",
            log_sink=logs,
        )
        self.assertEqual(out, "皇甫嵩很强")
        fuzzy_logs = [l for l in logs if l.source == "fuzzy"]
        self.assertEqual(len(fuzzy_logs), 1)
        self.assertEqual(fuzzy_logs[0].before, "黄甫嵩")
        self.assertEqual(fuzzy_logs[0].after, "皇甫嵩")
        self.assertEqual(fuzzy_logs[0].rule_type, "edit_distance")

    def test_two_char_canonical_not_fuzzy_matched(self) -> None:
        # 郭嘉 is 2 chars, never produced; 'guo zhao' 郭昭 should NOT be auto-fixed to 郭嘉
        dictionary = _make_dictionary(
            rules=[],
            canonical_terms={"郭嘉"},
            canonical_kind={"郭嘉": "hero"},
        )
        logs = []
        out = normalize_text(
            "郭昭出场",
            dictionary,
            segment_id="seg-3",
            video_id="BV-2char",
            scope="transcript",
            log_sink=logs,
        )
        # Untouched because canonical len < 3 disables fuzzy
        self.assertEqual(out, "郭昭出场")
        self.assertFalse([l for l in logs if l.source == "fuzzy"])

    def test_neighborhood_blocks_false_fuzzy(self) -> None:
        # 祝融夫人 (canonical) should not be re-fuzzied into 祝甘夫人
        logs = []
        out = normalize_text(
            "祝融夫人很关键",
            self.dictionary,
            segment_id="seg-4",
            video_id="BV-neighbor",
            scope="transcript",
            log_sink=logs,
        )
        self.assertEqual(out, "祝融夫人很关键")
        self.assertFalse([l for l in logs if l.source == "fuzzy"])

    def test_ambiguous_pattern_emits_candidate_no_rewrite(self) -> None:
        logs = []
        out = normalize_text(
            "金汤防御",
            self.dictionary,
            segment_id="seg-5",
            video_id="BV-amb",
            scope="transcript",
            log_sink=logs,
        )
        self.assertEqual(out, "金汤防御")  # not rewritten
        amb_logs = [l for l in logs if l.source == "manual_candidate"]
        self.assertEqual(len(amb_logs), 1)
        self.assertEqual(amb_logs[0].before, "金汤")
        self.assertIn("固若金汤", amb_logs[0].after)
        self.assertEqual(amb_logs[0].rule_type, "manual_review")

    def test_fuzzy_disabled_when_enable_fuzzy_false(self) -> None:
        logs = []
        out = normalize_text(
            "黄甫嵩很强",
            self.dictionary,
            segment_id="seg-6",
            video_id="BV-nofuzzy",
            scope="transcript",
            enable_fuzzy=False,
            log_sink=logs,
        )
        # Not rewritten because fuzzy is off and no exact rule matches
        self.assertEqual(out, "黄甫嵩很强")
        self.assertFalse(logs)

    def test_canonical_already_present_untouched(self) -> None:
        logs = []
        out = normalize_text(
            "皇甫嵩出场",
            self.dictionary,
            segment_id="seg-7",
            video_id="BV-canonical",
            scope="transcript",
            log_sink=logs,
        )
        self.assertEqual(out, "皇甫嵩出场")
        self.assertFalse(logs)


class NormalizeDocumentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dictionary = _make_dictionary(
            rules=[
                NormalizationRule(source="黄府松", canonical="皇甫嵩", kind="hero", confidence=0.95, rule_source="homophone"),
                NormalizationRule(source="屹然不动", canonical="岿然不动", kind="skill", confidence=0.95, rule_source="alias"),
            ],
            canonical_terms={"皇甫嵩", "岿然不动", "祝融夫人"},
            canonical_kind={"皇甫嵩": "hero", "岿然不动": "skill", "祝融夫人": "hero"},
        )

    def _document(self) -> VideoEvidenceBundle:
        source = VideoSource(
            video_id="BV-test",
            title="测试",
            uploader="UP",
            source_url="https://b/test",
            captured_at="2026-05-15T00:00:00",
        )
        bundle = VideoEvidenceBundle(
            source=source,
            segments=[
                VideoEvidenceSegment(
                    start_sec=0,
                    end_sec=10,
                    title="开场",
                    transcript_lines=["黄府松带屹然不动出场"],
                    ocr_lines=["黄府松Lv5", "屹然不动"],
                    visual_summary="黄府松镜头",
                )
            ],
        )
        return build_video_knowledge_document(bundle)

    def test_segments_rewritten_and_logged(self) -> None:
        doc = self._document()
        new_doc, logs, stats = normalize_document(doc, self.dictionary)
        seg = new_doc.segments[0]
        self.assertIn("皇甫嵩", seg.transcript)
        self.assertIn("岿然不动", seg.transcript)
        self.assertNotIn("黄府松", seg.transcript)
        self.assertNotIn("屹然不动", seg.transcript)
        self.assertIn("皇甫嵩Lv5", seg.ocr_lines)
        self.assertIn("岿然不动", seg.ocr_lines)
        self.assertEqual("皇甫嵩镜头", seg.visual_summary)
        self.assertGreaterEqual(stats.exact_replacements, 4)
        self.assertEqual(stats.segments_changed, 1)
        scopes = {l.scope for l in logs}
        self.assertEqual(scopes, {"transcript", "ocr_line", "visual_summary"})


class NormalizeCandidateFieldsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dictionary = _make_dictionary(
            rules=[
                NormalizationRule(source="黄府松", canonical="皇甫嵩", kind="hero", confidence=0.95, rule_source="homophone"),
                NormalizationRule(source="屹然不动", canonical="岿然不动", kind="skill", confidence=0.95, rule_source="alias"),
            ],
            canonical_terms={"皇甫嵩", "岿然不动"},
            canonical_kind={"皇甫嵩": "hero", "岿然不动": "skill"},
        )

    def _doc_with_candidate(self) -> "VideoKnowledgeDocument":  # type: ignore
        from qa_agent.video.models import VideoKnowledgeDocument
        return VideoKnowledgeDocument(
            source=VideoSource(
                video_id="BV-cand",
                title="t",
                uploader="u",
                source_url="https://b/cand",
                captured_at="2026-05-15T00:00:00",
            ),
            segments=[
                VideoSegment(
                    segment_id="seg-1",
                    start_sec=0,
                    end_sec=10,
                    transcript="ok",
                    ocr_lines=[],
                    visual_summary="",
                )
            ],
            lineup_candidates=[
                VideoLineupCandidate(
                    candidate_id="lc-1",
                    segment_id="seg-1",
                    topic="黄府松开荒队",
                    aliases=["黄府松队"],
                    hero_names=["黄府松", "祝融夫人"],
                    core_skills=["屹然不动", "草船借箭"],
                    facts=["黄府松带屹然不动出场"],
                    confidence=0.9,
                )
            ],
        )

    def test_candidate_topic_facts_heroes_skills_normalized(self) -> None:
        doc = self._doc_with_candidate()
        logs: list = []
        new_doc = normalize_candidate_fields(doc, self.dictionary, log_sink=logs)
        cand = new_doc.lineup_candidates[0]
        self.assertEqual(cand.topic, "皇甫嵩开荒队")
        self.assertEqual(cand.hero_names, ["皇甫嵩", "祝融夫人"])
        self.assertEqual(cand.core_skills, ["岿然不动", "草船借箭"])
        self.assertEqual(cand.aliases, ["皇甫嵩队"])
        self.assertEqual(cand.facts, ["皇甫嵩带岿然不动出场"])
        # Original doc untouched
        self.assertEqual(doc.lineup_candidates[0].topic, "黄府松开荒队")


class BuildDictionaryFromProfilesTests(unittest.TestCase):
    """Spot-check that the real on-disk KB profiles produce a sensible dictionary."""

    def test_real_kb_loads_with_homophones(self) -> None:
        dictionary = build_dictionary_from_profiles(
            knowledge_sources_dir=default_knowledge_sources_dir(PACKAGE_ROOT),
            homophones_path=default_homophones_path(PACKAGE_ROOT),
        )
        # Expect at least the chencang batch's known canonical names
        self.assertIn("皇甫嵩", dictionary.canonical_terms)
        self.assertIn("岿然不动", dictionary.canonical_terms)
        # Expect the homophone rule to be loaded
        homophone_sources = {r.source for r in dictionary.exact_rules if r.rule_source == "homophone"}
        self.assertIn("黄府松", homophone_sources)
        # Ambiguous patterns should be loaded
        ambiguous_patterns = {p.pattern for p in dictionary.ambiguous_patterns}
        self.assertIn("金汤", ambiguous_patterns)


if __name__ == "__main__":
    unittest.main()
