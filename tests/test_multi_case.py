import copy
import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
from legalhub import benchmark as b
from legalhub.casework import default_material,grounded_terms
from legalhub.case_registry import select_transcripts,retain_successful_images
from legalhub.case_chat import evidence_context,resolve_answer,citation_candidates

class MultiCaseEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.material=default_material()

    def test_citations_resolve_exact_quote_and_original_box(self):
        state,evidence=evidence_context(self.material,'转账')
        key=next(k for k,r in evidence.items() if r['text']=='收到了')
        answer={'answer':'对方确认收到。','verdict':'yes','claims':[{'text':'对方确认收到。','citations':[key]}],'limitations':[]}
        resolved=resolve_answer(answer,evidence,self.material)
        ref=resolved['citations'][0]
        self.assertEqual(ref['quote'],'收到了')
        self.assertEqual(ref['source_refs'][0]['bbox'],evidence[key]['source_refs'][0]['bbox'])
        self.assertEqual(resolved['claims'][0]['citation_ids'],['C1'])

    def test_unknown_or_cross_case_model_ids_cannot_be_published(self):
        _,evidence=evidence_context(self.material,'转账')
        answer={'answer':'付款','verdict':'yes','claims':[{'text':'付款','citations':['M999']}],'limitations':[]}
        with self.assertRaisesRegex(ValueError,'未提供'):resolve_answer(answer,evidence,self.material)
        foreign=copy.deepcopy(evidence);foreign['M001']['case_id']='foreign';answer['claims'][0]['citations']=['M001']
        with self.assertRaisesRegex(ValueError,'跨案件'):resolve_answer(answer,foreign,self.material)

    def test_uncited_definitive_answer_is_rejected_but_uncertainty_can_remain(self):
        _,evidence=evidence_context(self.material,'原告身份')
        a={'answer':'可以确认','verdict':'yes','claims':[{'text':'可以确认','citations':[]}],'limitations':[]}
        with self.assertRaisesRegex(ValueError,'缺少证据'):resolve_answer(a,evidence,self.material)
        a.update(answer='无法确认',verdict='unknown');a['claims'][0]['text']='无法确认'
        self.assertEqual(resolve_answer(a,evidence,self.material)['verdict'],'unknown')

    def test_complete_case_context_and_user_statement_are_distinguished(self):
        m=copy.deepcopy(self.material);m['metadata']['user_context']='用户说左侧是原告，未核实'
        state,refs=evidence_context(m,'原告是否转账')
        self.assertEqual(state['coverage'],'all_available_transcripts')
        self.assertEqual(len(refs),61)
        self.assertEqual(state['user_context_unverified'],m['metadata']['user_context'])
        self.assertTrue(all('原告' not in r['text'] for r in refs.values()))

    def test_decision_candidate_pool_is_bounded_and_keeps_payment_anchor(self):
        _,evidence=evidence_context(self.material,'转账')
        candidates=citation_candidates('现有聊天中是否有人明确称转了2000？',evidence)
        self.assertLessEqual(len(candidates),12)
        self.assertTrue(any('2000' in r['text'] for r in candidates.values()))

    def test_conflicting_transcription_versions_are_not_spliced_and_corruption_is_retained_in_audit(self):
        rows=[{'id':'bad','image_id':'i','text':'\ufffd\ufffd','order':0,'origin_type':'historical_model_prediction','source_index':1},
              {'id':'good','image_id':'i','text':'借款800','order':0,'origin_type':'historical_model_prediction','source_index':2},
              {'id':'other','image_id':'j','text':'\ufffd\ufffd','order':0,'origin_type':'historical_model_prediction','source_index':1}]
        before=copy.deepcopy(rows);selected,audit=select_transcripts(rows)
        self.assertEqual([r['id'] for r in selected],['good'])
        self.assertEqual(audit['alternative_versions_preserved'],1)
        self.assertEqual(audit['corrupted_messages_excluded'],1)
        self.assertEqual(rows,before)

    def test_contract_price_cannot_use_invented_source(self):
        analysis={'contract_terms':[{'key':'price','label':'价款','value':'2000','assessment':'待核','status':'uncertain',
            'support':[{'message_id':'M999','quote':'2000'}]}]}
        with self.assertRaisesRegex(ValueError,'source'):grounded_terms(self.material,analysis)

    def test_missing_contract_term_has_no_fake_reference(self):
        analysis={'contract_terms':[{'key':'delivery','label':'交付','value':'未见','assessment':'待补充','status':'missing','support':[]}]}
        terms=grounded_terms(self.material,analysis);self.assertEqual(terms[0]['sources'],[])
        analysis['contract_terms'][0]['status']='statement'
        analysis['contract_terms'][0]['value']='确认交付'
        term=grounded_terms(self.material,analysis)[0]
        self.assertEqual(term['status'],'missing');self.assertNotIn('确认交付',term['value'])
        self.assertEqual(term['normalization_note'],'unsupported_model_term_text_withheld')

    def test_retry_keeps_complete_image_versions_from_unchanged_originals(self):
        first=self.material['images'][0]['image_id']
        fresh=copy.deepcopy(self.material)
        fresh['records']=[r for r in fresh['records'] if r['image_id']==first]
        fresh['metadata']['ok_images']=1
        prior=copy.deepcopy(self.material)
        old=copy.deepcopy(prior)
        combined=retain_successful_images(fresh,[({'sha256':'recorded-corpus'},prior),({'sha256':'older-version'},prior)])
        self.assertEqual(combined['metadata']['ok_images'],6)
        self.assertEqual(len(combined['records']),len(prior['records']))
        self.assertEqual(prior,old)
        self.assertEqual(len(combined['metadata']['retained_prior_sources']),1)
        self.assertEqual([r for r in combined['records'] if r['image_id']==first],fresh['records'])

    def test_retry_rejects_a_prior_extraction_with_changed_original_hash(self):
        prior=copy.deepcopy(self.material);prior['images'][0]['sha256']='0'*64
        with self.assertRaisesRegex(ValueError,'originals changed'):
            retain_successful_images(self.material,[({},prior)])

    def test_visual_transport_fallback_preserves_original_and_both_provider_attempts(self):
        from legalhub.evidence import extract
        image=copy.deepcopy(self.material['images'][0]);original=b.sha(b.ROOT/image['file'])
        first={'http_status':500,'elapsed_seconds':.1,'status':'provider_error','raw':''}
        last={'http_status':200,'elapsed_seconds':.2,'status':'ok','raw':json.dumps({'dialog_name':'fixture','messages':[{'text':'fixture text','speaker_side':'left','bbox':[10,10,30,30]}],'limitations':[]})}
        with tempfile.TemporaryDirectory(dir=b.ROOT/'tmp') as td:
            path=Path(td);b.write(path/'manifest.json',{'images':[image]})
            with patch('legalhub.evidence.b.model_config',return_value=({'model_name':'fixture','provider':'siliconflow','request_parameters':{}},'fixture')),patch('legalhub.evidence.request',side_effect=[first,last]) as provider:
                result=extract(path/'manifest.json','fixture',path/'out',True,transport_png=True)
            self.assertEqual(result['ok_images'],1)
            self.assertEqual(provider.call_count,2)
            self.assertTrue(all(c.kwargs['retries']==0 for c in provider.call_args_list))
            fallback=provider.call_args_list[1].args[3][0]
            self.assertEqual(b.sha(fallback),original)
            row=json.loads((path/'out/predictions.jsonl').read_text(encoding='utf-8'))
            self.assertEqual([r['response']['http_status'] for r in row['transport_attempts']],[500,200])
            self.assertAlmostEqual(row['elapsed_seconds'],.3)
        self.assertEqual(b.sha(b.ROOT/image['file']),original)

if __name__=='__main__':unittest.main()
