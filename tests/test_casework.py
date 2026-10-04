import copy
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch,Mock
from legalhub.casework import grounded_records,CaseWorkspace
from legalhub.inference import request
from legalhub import benchmark as b

class CaseMeaningTests(unittest.TestCase):
    def setUp(self):
        self.material={'metadata':{'case_id':'A'},'images':[{'image_id':'i','display_page':1,'file':'tmp/i.jpg','sha256':'x'}],
            'records':[{'id':'m1','case_id':'A','image_id':'i','speaker_local_id':'left','text':'给你转了2000','source_refs':[{'image_id':'i','message_id':'m1','bbox':[1,2,40,50],'evidence_page':None,'quote':'给你转了2000'}]}]}
        support=[{'message_id':'M001','quote':'转了2000'}]
        self.analysis={'summary':'转款沟通','facts':[{'title':'告知转款','description':'发言人称已经转款','support':support,'uncertainties':['款项性质不明']}],
            'meanings':[{'title':'履行陈述','declaration_type':'performance_notice','is_declaration':'uncertain','expression_meaning':'告知已转款',
                'legal_significance':'可能支持已付款的主张','possible_effect':'不当然证明全部债务清偿','conditions_missing':['需支付记录'],'support':support,'law_ids':['law1'],'confidence':'medium'}],
            'questions_to_verify':[],'transcription_issues':[]}
        self.laws=[{'id':'law1','article':'第一条','text':'测试法理'}]

    def test_short_model_ids_resolve_to_real_messages_and_original_boxes(self):
        rows=grounded_records(self.material,self.analysis,'run',self.laws)
        ref=rows[1]['source_refs'][0]
        self.assertEqual(ref['message_id'],'m1');self.assertEqual(ref['bbox'],[1,2,40,50])
        self.assertEqual(ref['quote'],'转了2000');self.assertEqual(rows[1]['interpretation']['is_declaration'],'uncertain')

    def test_prompt_upgrade_preserves_readable_review_but_changed_sources_invalidate_it(self):
        from legalhub.casework import digest,LEGACY_PROMPT_VERSION,LEGACY_LAW_NUMBERS
        refs=[{'id':f'civil-code-2020:{n}','text':str(n)} for n in LEGACY_LAW_NUMBERS]
        expanded=refs+[{'id':'civil-code-2020:488','text':'new reference'}]
        with tempfile.TemporaryDirectory(dir=b.ROOT/'tmp') as d:
            home=Path(d);saved=home/'saved.sqlite3';saved.write_bytes(b'')
            active={'run_id':'saved-review','input_digest':digest({'material':self.material,'laws':refs,'prompt_version':LEGACY_PROMPT_VERSION}),
                    'db':saved.relative_to(b.ROOT).as_posix()}
            b.write(home/'active.json',active)
            with patch('legalhub.casework.default_material',return_value=self.material),patch('legalhub.casework.laws',return_value=expanded),patch('legalhub.casework.build'):
                work=CaseWorkspace(home=home)
            self.assertEqual(work.current['run_id'],'saved-review')
            self.assertNotEqual(work.current['input_digest'],work.input_digest)
            changed=copy.deepcopy(self.material);changed['records'][0]['text']='changed evidence'
            with patch('legalhub.casework.default_material',return_value=changed),patch('legalhub.casework.laws',return_value=expanded),patch('legalhub.casework.build'):
                work=CaseWorkspace(home=home)
            self.assertIsNone(work.current)

    def test_invented_quote_or_unknown_support_cannot_be_published(self):
        bad=copy.deepcopy(self.analysis);bad['meanings'][0]['support'][0]['quote']='已经还清所有借款'
        with self.assertRaisesRegex(ValueError,'Invented'):grounded_records(self.material,bad,'r',self.laws)
        bad['meanings'][0]['support'][0]['message_id']='foreign'
        with self.assertRaisesRegex(ValueError,'Unknown'):grounded_records(self.material,bad,'r',self.laws)

    def test_analysis_snapshot_refreshes_saved_version_without_loading_credentials(self):
        with tempfile.TemporaryDirectory(dir=b.ROOT/'tmp') as d:
            work=CaseWorkspace.__new__(CaseWorkspace);work.home=Path(d);work.lock=threading.RLock()
            work.current={'run_id':'previous'};work.active_mtime=0;work.readable_digests={'valid-input'}
            saved=work.home/'saved.sqlite3';saved.write_bytes(b'')
            active={'run_id':'new-version','input_digest':'valid-input','db':saved.relative_to(b.ROOT).as_posix()}
            b.write(work.home/'active.json',active)
            with patch.object(b,'model_config',side_effect=AssertionError('Review reads must not load provider configuration')):
                snapshot=work.analysis_snapshot()
            self.assertEqual(snapshot['run_id'],'new-version')
            snapshot['run_id']='local edit'
            self.assertEqual(work.analysis_snapshot()['run_id'],'new-version')

    def test_cross_case_message_and_invented_statute_are_rejected(self):
        self.material['records'][0]['case_id']='B'
        with self.assertRaisesRegex(ValueError,'cross-case'):grounded_records(self.material,self.analysis,'r',self.laws)
        self.material['records'][0]['case_id']='A';self.analysis['meanings'][0]['law_ids']=['law999']
        with self.assertRaisesRegex(ValueError,'statute'):grounded_records(self.material,self.analysis,'r',self.laws)

    def test_provider_failure_preserves_previous_analysis(self):
        with tempfile.TemporaryDirectory() as d:
            work=CaseWorkspace.__new__(CaseWorkspace);work.home=Path(d);work.model_alias='fixture';work.lock=threading.RLock()
            work.job={'status':'running'};work.current={'run_id':'previous'};work.input_digest='digest';work.material=self.material;work.references=self.laws
            with (patch.object(b,'model_config',return_value=({'provider':'siliconflow','model_name':'fixture','request_parameters':{}},'secret')),
                  patch('legalhub.casework.request',return_value={'http_status':500,'status':'error'})):
                self.assertIsNone(work.run('failed'))
            self.assertEqual(work.current['run_id'],'previous');self.assertEqual(work.job['status'],'error')
            self.assertIn('HTTP 500',work.job['error'])
            self.assertFalse((Path(d)/'active.json').exists())

    def test_balance_error_429_is_not_retried_as_temporary_rate_limit(self):
        with patch.object(b,'infer_detailed',side_effect=b.ProviderHTTPError(429,{'message':'insufficient balance'})) as call:
            result=request({},'secret','prompt',[],sleeper=lambda _:None)
        self.assertEqual(call.call_count,1);self.assertEqual(result['status'],'error')

    def test_review_preserves_provider_response_and_attributes_corrections(self):
        from legalhub.casework import digest
        with tempfile.TemporaryDirectory(dir=b.ROOT/'tmp') as d:
            work=CaseWorkspace.__new__(CaseWorkspace);work.home=Path(d);work.lock=threading.RLock()
            work.material=self.material;work.references=self.laws;work.input_digest='review-input'
            source=work.home/'runs'/'0123456789abcdef';source.mkdir(parents=True)
            b.write(source/'response.json',{'http_status':200,'response_id':'real-id','raw':'original uncorrected draft'})
            b.write(source/'request-spec.json',{'image_hashes':['x'],'prompt_version':'original-prompt'})
            before=b.sha(source/'response.json')
            with patch('legalhub.casework.build'),patch('legalhub.casework.request') as provider:
                result=work.publish_review('0123456789abcdef',self.analysis,['corrected unsupported inference'])
            provider.assert_not_called()
            self.assertEqual(b.sha(source/'response.json'),before)
            self.assertEqual(result['review']['source_response_sha256'],before)
            self.assertEqual(result['request_proof']['response_id'],'real-id')
            self.assertEqual(result['meanings'][0]['origin_type'],'assistant_source_review')
            self.assertEqual(result['meanings'][0]['review_status'],'assistant_reviewed_not_user_confirmed')

    def test_streamed_unicode_json_is_assembled_with_honest_finish_and_usage(self):
        import json
        response=Mock(status_code=200,headers={})
        response.iter_lines.return_value=iter(['data: '+json.dumps({'id':'real-response','model':'fixture','choices':[{'delta':{'content':'{"summary":"收'},'finish_reason':None}]}),
                                               'data: '+json.dumps({'choices':[{'delta':{'content':'到"}'},'finish_reason':None}]})])
        model={'model_name':'fixture','base_url':'https://fixture.test/v1','stream_response':True,'stop_after_json':True}
        with patch.object(b.requests,'post',return_value=response) as call:
            row=b.infer_detailed(model,'secret','prompt',[])
        self.assertEqual(json.loads(row['raw']),{'summary':'收到'})
        self.assertEqual(row['response_id'],'real-response')
        self.assertTrue(row['stream_closed_after_complete_json']);self.assertFalse(row['usage_complete'])
        self.assertTrue(call.call_args.kwargs['stream']);response.close.assert_called_once()

if __name__=='__main__':unittest.main()
