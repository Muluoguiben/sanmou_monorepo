"""Public memo controls frozen before inspecting Q05a implementation."""
import copy
from datetime import date
import json
import sys
import unittest

from qa_agent.knowledge.models import Domain, EntryKind, KnowledgeEntry, LineupSolutionProfile
from qa_agent.retrieval.retriever import Retriever


def entry(identity, tags=(), *, priority=0, exact=True, relevant=True, lineup=True):
    return KnowledgeEntry(id=identity, domain=Domain.SOLUTION,
        entry_kind=EntryKind.LINEUP_SOLUTION if lineup else EntryKind.GENERIC_RULE,
        topic=identity, aliases=["needle"] if exact and relevant else [],
        facts=["needle fallback support" if relevant else "unrelated payload"],
        source_ref="independent-synthetic:" + identity, updated_at=date(2026, 10, 6),
        confidence=0.8, priority=priority,
        structured_data=LineupSolutionProfile(name=identity, season_tags=list(tags)))


def starvation_entries():
    return [entry("wrong-a", ["S2"], priority=90), entry("wrong-b", ["S2"], priority=80),
            entry("wrong-c", ["S2"], priority=70), entry("right-low", ["S1"], exact=False)]


def ids(chunks):
    return [chunk.entry.id for chunk in chunks]


def projection(chunks):
    return [(chunk.entry.model_dump(mode="json"), chunk.score, chunk.matched_query, chunk.as_prompt_block())
            for chunk in chunks]


def seasonal(entries, query="needle", *, season_tag="S1", top_k=2):
    from qa_agent.retrieval.seasonal import retrieve_lineups_for_season
    return retrieve_lineups_for_season(entries, query, season_tag=season_tag, top_k=top_k)


class SeasonalPublicControls(unittest.TestCase):
    def test_correct_pool_is_filtered_before_top_k(self):
        data = starvation_entries()
        global_top = Retriever(data).retrieve("needle", top_k=2)
        self.assertEqual(ids(global_top), ["wrong-a", "wrong-b"])
        self.assertEqual([c.entry.id for c in global_top if "S1" in c.entry.structured_data.season_tags], [])
        result = seasonal(data)
        self.assertEqual(ids(result.match), ["right-low"])
        self.assertEqual([(d.chunk.entry.id, d.reason) for d in result.mismatch],
                         [("wrong-a", "season_mismatch"), ("wrong-b", "season_mismatch")])
        self.assertEqual(result.unknown, [])
        self.assertEqual(projection(result.match), projection(Retriever([data[-1]]).retrieve("needle", top_k=2)))

    def test_full_input_duplicate_precondition_cannot_be_filtered_away(self):
        for other in (entry("same-id", ["S2"]), entry("same-id", []),
                      entry("same-id", ["S1"], lineup=False),
                      entry("same-id", ["S2"], relevant=False)):
            for query in ("needle", "totally-unmatched-query"):
                data = [entry("same-id", ["S1"]), other]
                with self.subTest(other=other.model_dump(mode="json"), query=query):
                    with self.assertRaisesRegex(ValueError, "Duplicate knowledge entry id"):
                        seasonal(data, query)

    def test_exact_declared_tags_and_unknown_priority(self):
        data = [entry("tag-S1", ["S1"]), entry("tag-S10", ["S10"]),
                entry("tag-lower", ["s1"]), entry("tag-multiple", ["S2", "S1"]),
                entry("tag-absent"), entry("not-lineup", ["S1"], lineup=False)]
        result = seasonal(data, top_k=10)
        self.assertEqual(ids(result.match), ["tag-S1", "tag-multiple"])
        self.assertEqual([(d.chunk.entry.id, d.reason) for d in result.mismatch],
                         [("tag-S10", "season_mismatch"), ("tag-lower", "season_mismatch")])
        self.assertEqual([(d.chunk.entry.id, d.reason) for d in result.unknown],
                         [("tag-absent", "missing_season_tags"), ("not-lineup", "not_lineup_solution")])
        composed = seasonal([entry("tag-composed", ["é"]), entry("tag-decomposed", ["e\u0301"])], season_tag="é")
        self.assertEqual(ids(composed.match), ["tag-composed"])
        self.assertEqual([d.chunk.entry.id for d in composed.mismatch], ["tag-decomposed"])
        stripped_by_model = entry("tag-stripped", [" S1 "])
        self.assertEqual(stripped_by_model.structured_data.season_tags, ["S1"])
        self.assertEqual(ids(seasonal([stripped_by_model]).match), ["tag-stripped"])

    def test_per_pool_caps_relevance_and_source_identity(self):
        data = [entry(f"match-{i}", ["S1"], priority=90-i) for i in range(5)]
        data += [entry(f"mismatch-{i}", ["S2"], priority=90-i) for i in range(5)]
        data += [entry(f"unknown-{i}", [], priority=90-i) for i in range(5)]
        data += [entry("irrelevant-m", ["S1"], relevant=False, priority=100),
                 entry("irrelevant-x", ["S2"], relevant=False, priority=100),
                 entry("irrelevant-u", [], relevant=False, priority=100)]
        before = copy.deepcopy([e.model_dump(mode="json") for e in data])
        baseline = projection(Retriever(data).retrieve("needle", top_k=10))
        result = seasonal(data)
        self.assertEqual(ids(result.match), ["match-0", "match-1"])
        self.assertEqual([d.chunk.entry.id for d in result.mismatch], ["mismatch-0", "mismatch-1"])
        self.assertEqual([d.chunk.entry.id for d in result.unknown], ["unknown-0", "unknown-1"])
        self.assertLessEqual(len(result.match) + len(result.mismatch) + len(result.unknown), 6)
        chunks = result.match + [d.chunk for d in result.mismatch + result.unknown]
        for chunk in chunks:
            original = next(e for e in data if e.id == chunk.entry.id)
            self.assertIs(chunk.entry, original)
            self.assertEqual(chunk.entry.source_ref, original.source_ref)
            self.assertEqual(chunk.matched_query, "needle")
        self.assertEqual([e.model_dump(mode="json") for e in data], before)
        self.assertEqual(projection(Retriever(data).retrieve("needle", top_k=10)), baseline)
        self.assertEqual(result.execution_authority, "none")
        self.assertIs(result.executable, False)

    def test_strict_public_parameter_types_and_empty_pools(self):
        good = [entry("single", ["S1"])]
        for tag in (None, 1, True, [], "", " ", " S1", "S1 ", "\tS1"):
            with self.subTest(tag=tag), self.assertRaises((ValueError, TypeError)):
                seasonal(good, season_tag=tag)
        for query in (None, 1, True, [], "", " \n"):
            with self.subTest(query=query), self.assertRaises((ValueError, TypeError)):
                seasonal(good, query)
        for top_k in (None, True, False, 0, -1, 1.0, "1"):
            with self.subTest(top_k=top_k), self.assertRaises((ValueError, TypeError)):
                seasonal(good, top_k=top_k)
        for values in (tuple(good), {}, None, [good[0], good[0].model_dump()]):
            with self.subTest(values=repr(values)), self.assertRaises((ValueError, TypeError)):
                seasonal(values)
        for values, query in (([], "needle"), (good, "totally-unmatched-query")):
            result = seasonal(values, query)
            self.assertEqual((result.match, result.mismatch, result.unknown), ([], [], []))


def verify_baseline_controls():
    data = starvation_entries()
    global_ids = ids(Retriever(data).retrieve("needle", top_k=2))
    pool_ids = ids(Retriever([data[-1]]).retrieve("needle", top_k=2))
    assert global_ids == ["wrong-a", "wrong-b"] and pool_ids == ["right-low"]
    duplicates = [entry("same-id", ["S1"]), entry("same-id", ["S2"], relevant=False)]
    try:
        Retriever(duplicates)
    except ValueError as error:
        assert "Duplicate knowledge entry id" in str(error)
    else:
        raise AssertionError("baseline global duplicate gate missing")
    print(json.dumps({"global_top_k": global_ids, "post_filter_ids": [], "prefilter_pool_ids": pool_ids,
        "global_duplicate_irrelevant_cross_season_rejected": True,
        "default_projection": projection(Retriever(data).retrieve("needle", top_k=4))}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if sys.argv[1:] == ["--verify-baseline-controls"]:
        verify_baseline_controls()
    else:
        unittest.main()
