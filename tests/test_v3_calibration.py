import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from prepare_v3_calibration import author_range, locate, messages_for, legacy_field
from check_v3_calibration import local, check_review, verify_artifacts
ROOT=Path(__file__).resolve().parents[1]

class CalibrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.scenarios=json.loads((ROOT/'configs/v3/calibration_scenarios.json').read_text(encoding='utf-8'))['scenarios']
    def test_no_images_cannot_support_authored_claims(self):
        for case in self.scenarios:
            result=author_range(case,[])
            self.assertEqual(result['observable_claims'],[])
            self.assertEqual(result['answerability'],'partial_or_insufficient')
    def test_missing_identity_cannot_support_sales_total_comparison(self):
        result=author_range(self.scenarios[0],[2,3,4])
        self.assertNotIn('comparison',{n['node_id'] for n in result['observable_claims']})
        self.assertIn('link',{n['node_id'] for n in result['missing_requirements']})
    def test_superseded_notice_is_not_falsely_necessary(self):
        result=author_range(self.scenarios[1],[2,3,4])
        self.assertEqual(result['answerability'],'full_scoped_answer_proposed')
    def test_four_counterfactuals_change_declared_result(self):
        for case in self.scenarios:
            base=author_range(case,[1,2,3,4]);changed=author_range(case,[1,2,3,4],True)
            self.assertNotEqual(base['observable_claims'],changed['observable_claims'])
            self.assertEqual(base['answerability'],changed['answerability'])
    def test_probate_reply_remains_explicit_after_parent_changes(self):
        cf=messages_for(self.scenarios[2],'counterfactual')
        unit=[m['text'] for m in cf if m['unit']==3]
        self.assertEqual(unit,['I have not decided about that proposal.',"I favour Sara's proposal."])
    def test_order_and_pagination_preserve_source_message_facts(self):
        for case in self.scenarios:
            self.assertEqual(messages_for(case,'base'),messages_for(case,'repagination'))
            self.assertEqual(messages_for(case,'base'),messages_for(case,'reverse_order'))
            self.assertEqual(messages_for(case,'base'),messages_for(case,'distractor')[:8])
    def test_locates_legacy_paragraph_and_unique_cross_paragraph_quote(self):
        source=dict(text='prefix alpha beta suffix',paragraphs=[dict(id='p1',text='alpha',char_start=7)])
        self.assertEqual(locate(source,dict(source_id='p1',quote='alpha'))['char_start'],7)
        self.assertEqual(locate(source,dict(source_id='p1',quote='alpha beta'))['char_end'],17)
    def test_ambiguous_quote_not_upgraded_to_verified(self):
        source=dict(text='same same',paragraphs=[])
        self.assertEqual(locate(source,dict(quote='same'))['status'],'unresolved')
    def test_old_scalar_not_converted_to_v3_certification(self):
        self.assertEqual(legacy_field('打分（0-5）'),('legacy_scalar_score',[]))
        self.assertEqual(legacy_field('spearman系数结果')[1],[])
    def test_path_escape_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            with self.assertRaises(ValueError):local(Path(t),'../secret')
    def test_frozen_batch_and_blank_review_cannot_claim_certification(self):
        folder=ROOT/'datasets/v3.0.0/calibration_20261023_003'
        self.assertEqual(verify_artifacts(folder)['subsets'],352)
        result=check_review(folder/'blind_review/reviewer_a',folder/'blind_review/reviewer_a')
        self.assertFalse(result['complete']);self.assertIn('352 incomplete subset reviews',result['blockers'])
    def test_tampered_artifact_is_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t);(folder/'test.txt').write_text('changed')
            entry=dict(path='test.txt',sha256=hashlib.sha256(b'original').hexdigest(),bytes=8)
            (folder/'artifact_manifest.jsonl').write_text(json.dumps(entry)+'\n')
            with self.assertRaisesRegex(ValueError,'Artifact drift'):verify_artifacts(folder)
    def test_review_question_tampering_rejected(self):
        template=ROOT/'datasets/v3.0.0/calibration_20261023_003/blind_review/reviewer_a'
        with tempfile.TemporaryDirectory() as t:
            folder=Path(t)
            (folder/'reviewer.json').write_text((template/'reviewer.json').read_text())
            tasks=json.loads((template/'tasks.json').read_text(encoding='utf-8'));tasks[0]['question']='Changed prompt'
            (folder/'tasks.json').write_text(json.dumps(tasks))
            with self.assertRaisesRegex(ValueError,'Reviewed input changed'):check_review(folder,template)

if __name__=='__main__':unittest.main()
