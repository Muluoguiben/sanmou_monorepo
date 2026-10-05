from __future__ import annotations

import copy
import json
import tempfile
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from qa_agent.quality_eval.runner import run
from qa_agent.quality_eval.runner import _validate_corpus
from qa_agent.quality_eval.scoring import digest, refusal_score, retrieval_score, score_answer, snapshot

PACKAGE = Path(__file__).resolve().parents[1]
FIXTURES = PACKAGE / 'tests/fixtures/quality_eval/v1'


class QualityEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.cases = {c['id']: c for c in json.loads((FIXTURES / 'cases.json').read_text())['scoring_cases']}

    def score(self, name):
        c = self.cases[name]
        return score_answer(c['answer'], c['evidence'], c['annotation'], context=c['context'])

    def test_supported_synthetic_control(self):
        r = self.score('supported')
        self.assertEqual(r['claim_support']['value'], 1)
        self.assertEqual(r['supported_citation_completeness']['value'], 1)

    def test_correct_id_does_not_establish_fact_or_context_support(self):
        for name in ('wrong_number', 'wrong_entity', 'stale_coreference'):
            with self.subTest(name=name):
                r = self.score(name)
                self.assertEqual(r['citation_id_validity']['value'], 1)
                self.assertEqual(r['claim_support']['value'], 0)

    def test_true_but_off_topic_is_context_failure_not_false_fact(self):
        r = self.score('topic_switch_old_answer')
        self.assertEqual(r['claim_support']['value'], 1)
        self.assertEqual(r['context_correctness']['value'], 0)

    def test_candidate_evidence_does_not_count_as_citation(self):
        r = self.score('missing_citation')
        self.assertIsNone(r['citation_id_validity']['value'])
        self.assertEqual(r['citation_id_validity']['denominator'], 0)
        self.assertEqual(r['supported_citation_completeness']['value'], 0)

    def test_empty_evidence_invalidates_id(self):
        r = self.score('no_evidence')
        self.assertEqual(r['citation_id_validity']['value'], 0)
        self.assertEqual(r['claim_support']['value'], 0)

    def test_unknown_and_unreviewed_are_not_semantic_passes(self):
        self.assertIsNone(self.score('unknown')['claim_support']['value'])
        c = self.cases['supported']
        c['annotation']['review_status'] = 'unreviewed'
        r = self.score('supported')
        self.assertEqual(r['unjudged_claims'], 1)
        self.assertIsNone(r['claim_support']['value'])

    def test_context_binding(self):
        c = self.cases['stale_coreference']
        with self.assertRaisesRegex(ValueError, 'context binding'):
            score_answer(c['answer'], c['evidence'], c['annotation'], context='different question')

    def test_answer_and_evidence_binding(self):
        c = self.cases['supported']
        with self.assertRaisesRegex(ValueError, 'answer binding'):
            score_answer(c['answer'] + '额外无依据事实', c['evidence'], c['annotation'])
        with self.assertRaisesRegex(ValueError, 'evidence binding'):
            score_answer(c['answer'], {'synthetic-a': 'changed'}, c['annotation'])

    def test_unannotated_gaps_and_overlap_rejected(self):
        for start, end in ((1, 4), (0, 4), (-1, 4), (0, 999)):
            c = copy.deepcopy(self.cases['supported'])
            c['annotation']['segments'][0].update(start=start, end=end)
            with self.assertRaises(ValueError):
                score_answer(c['answer'], c['evidence'], c['annotation'], context=c['context'])

    def test_supported_label_requires_bound_evidence(self):
        for refs in ([], ['absent']):
            c = copy.deepcopy(self.cases['supported'])
            c['annotation']['segments'][0]['support_ids'] = refs
            with self.assertRaises(ValueError):
                score_answer(c['answer'], c['evidence'], c['annotation'])

    def test_mixed_claim_missing_citation_not_hidden_by_first_claim(self):
        answer = '甲的上限为20。[synthetic-a]乙的上限为30。'
        c = self.cases['supported']
        a = c['annotation']
        cut = len(c['answer'])
        a.update(answer_sha256=digest(answer), segments=[
            dict(start=0,end=cut,verdict='supported',support_ids=['synthetic-a']),
            dict(start=cut,end=len(answer),verdict='supported',support_ids=['synthetic-b'])])
        r = score_answer(answer,c['evidence'],a)
        self.assertEqual(r['claim_support']['denominator'], 2)
        self.assertEqual(r['supported_citation_completeness']['value'], .5)

    def test_retrieval_denominators_and_duplicates(self):
        r = retrieval_score(['a','b'], ['x','a'])
        self.assertEqual(r['recall']['value'], .5)
        self.assertEqual(r['reciprocal_rank'], .5)
        self.assertIsNone(retrieval_score([],[])['recall']['value'])
        with self.assertRaises(ValueError):
            retrieval_score(['a'], ['a','a'])

    def test_refusal_precision_recall_distinct(self):
        r = refusal_score([True,True,False], [True,False,False])
        self.assertEqual(r['precision']['value'], 1)
        self.assertEqual(r['recall']['value'], .5)
        self.assertIsNone(refusal_score([],[])['precision']['value'])
        with self.assertRaises(ValueError):
            refusal_score([True], [])

    def test_portable_snapshot_binds_paths_and_content(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            p=root/'a.py'
            p.write_bytes(b'a\r\nb\r\n')
            before=snapshot(root,[p])
            p.write_bytes(b'a\nb\n')
            self.assertEqual(before,snapshot(root,[p]))
            p.rename(root/'b.py')
            self.assertNotEqual(before,snapshot(root,[root/'b.py']))

    def test_frozen_retrieval_baseline_runs_without_model_or_network(self):
        with patch('socket.socket', side_effect=AssertionError('network forbidden')):
            result=run(PACKAGE, baseline='v2')
        self.assertEqual(result['retrieval']['query_count'],12)
        self.assertEqual(result['retrieval']['macro_recall']['denominator'],11)
        self.assertEqual(result['provider']['calls'],0)
        self.assertEqual(result['human_reviewed_labels'],0)
        self.assertEqual(result['holdout']['status'],'not_established')
        self.assertIsNone(result['quality_threshold'])

    def test_production_or_fixture_drift_is_rejected(self):
        with patch('qa_agent.quality_eval.runner.snapshot', return_value={'digest':'drift'}):
            with self.assertRaisesRegex(ValueError,'source drift'):
                run(PACKAGE, baseline='v2')
        with patch('qa_agent.quality_eval.runner.digest', return_value='drift'):
            with self.assertRaisesRegex(ValueError,'fixture drift'):
                run(PACKAGE, baseline='v2')

    def test_v1_remains_frozen_and_rejects_new_production(self):
        with self.assertRaisesRegex(ValueError,'source drift'):
            run(PACKAGE)

    def test_invalid_version_and_loaded_source_rejected(self):
        with self.assertRaisesRegex(ValueError,'version'):
            run(PACKAGE,baseline='latest')
        with self.assertRaisesRegex(ValueError,'source mismatch'):
            run(PACKAGE/'other',baseline='v2')

    def test_real_file_add_delete_and_change_rejected(self):
        for operation in ('add','delete','change'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as d:
                root=Path(d)
                for directory in ('src','knowledge_sources','tests/fixtures/quality_eval'):
                    shutil.copytree(PACKAGE/directory,root/directory)
                target=root/'src/qa_agent/chat/evidence_assessment.py'
                if operation == 'add':
                    (target.parent/'unexpected.py').write_text('# unexpected production file\n')
                elif operation == 'delete':
                    target.unlink()
                else:
                    target.write_text(target.read_text()+'\n# changed\n')
                with patch('qa_agent.quality_eval.runner.__file__',str(root/'src/qa_agent/quality_eval/runner.py')):
                    with self.assertRaisesRegex(ValueError,'source drift'):
                        run(root,baseline='v2')

    def test_manifest_metadata_rejects_version_split_and_duplicate_ids(self):
        fixtures=PACKAGE/'tests/fixtures/quality_eval/v2'
        corpus=json.loads((fixtures/'cases.json').read_text())
        frozen=json.loads((fixtures/'freeze.json').read_text())
        for change, message in (('version','version/split'),('split','version/split'),('duplicate','duplicate case')):
            edited=copy.deepcopy(corpus)
            if change == 'duplicate':
                edited['queries'].append(edited['queries'][0])
            else:
                edited[change]='invalid'
            with patch('qa_agent.quality_eval.runner.json.loads',side_effect=[edited,frozen]):
                with self.assertRaisesRegex(ValueError,message):
                    run(PACKAGE,baseline='v2')

    def test_strict_schema_is_separate_from_hash_binding(self):
        corpus=json.loads((PACKAGE/'tests/fixtures/quality_eval/v2/cases.json').read_text())
        for key, value in [('top_k',0),('top_k',-1),('top_k',True),('top_k',2.0),
                ('version',2.0),('version',True),('assessment_cases',[]),('assessment_cases',None)]:
            with self.subTest(key=key,value=value), self.assertRaises(ValueError):
                _validate_corpus({**corpus,key:value},'v2')
        missing=copy.deepcopy(corpus)
        missing.pop('assessment_cases')
        with self.assertRaises(ValueError):
            _validate_corpus(missing,'v2')
        for group in ('queries','scoring_cases','assessment_cases'):
            for identifier in ('', '   ', None, 3):
                changed=copy.deepcopy(corpus)
                changed[group][0]['id']=identifier
                with self.subTest(group=group,identifier=identifier), self.assertRaises(ValueError):
                    _validate_corpus(changed,'v2')
        for change in ({'expected':{}},{'values':[True]},{'values':[float('nan')]},{'question':''}):
            changed=copy.deepcopy(corpus)
            changed['assessment_cases'][0].update(change)
            with self.assertRaises(ValueError):
                _validate_corpus(changed,'v2')

    def test_lazy_assessment_module_from_another_tree_is_rejected(self):
        import importlib.util
        import types
        from unittest.mock import MagicMock
        name='qa_agent.quality_eval.assessment_cases'
        fake=types.ModuleType(name)
        fake.__file__='/tmp/another-qa-tree/assessment_cases.py'
        fake.__spec__=importlib.util.spec_from_file_location(name,fake.__file__)
        fake.evaluate_cases=MagicMock(side_effect=AssertionError('must not execute foreign code'))
        with patch.dict('sys.modules',{name:fake}):
            with self.assertRaisesRegex(ValueError,'execution source mismatch'):
                run(PACKAGE,baseline='v2')
        fake.evaluate_cases.assert_not_called()
