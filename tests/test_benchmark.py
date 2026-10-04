import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from legalhub import benchmark as b

class BenchmarkContractTests(unittest.TestCase):
    def test_provider_receives_images_and_prompt_but_no_gold(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'x.jpg';p.write_bytes(b'image bytes')
            class Response:
                status_code=200
                headers={}
                def json(self):return {'choices':[{'message':{'content':'{"answer":"x"}'}}],'model':'returned-id'}
            with patch.object(b.requests,'post',return_value=Response()) as post:
                b.infer({'model_name':'vision-id','base_url':'http://localhost/v1'},'local-key','only visible question',[str(p)])
                payload=post.call_args.kwargs['json']
                self.assertEqual(payload['messages'][1]['content'][0]['text'],'only visible question')
                self.assertEqual(payload['messages'][1]['content'][1]['type'],'image_url')
                self.assertNotIn('answer',payload)

    def test_failures_and_unfinished_tasks_remain_in_denominator(self):
        manifest,tasks=b.dataset()
        selected=[x for x in tasks if x['track']=='classification'][:3]
        with tempfile.TemporaryDirectory() as d:
            out=Path(d)
            b.write(out/'run.json',{'dataset_sha256':manifest['dataset_sha256'],'model':{'model_name':'offline-fixture'},'task_ids':[x['id'] for x in selected]})
            predictions=[{'id':selected[0]['id'],'status':'ok','answer':selected[0]['answer']},{'id':selected[1]['id'],'status':'error'}]
            (out/'predictions.jsonl').write_text('\n'.join(json.dumps(x) for x in predictions),encoding='utf-8')
            b.report(out)
            metrics=b.read(out/'metrics.json')[0]
            self.assertEqual(metrics['planned'],3)
            self.assertEqual(metrics['ok'],1)
            self.assertAlmostEqual(metrics['exact_match'],1/3)
            self.assertEqual(metrics['status_counts'],{'ok':1,'error':1,'missing':1})

    def test_report_rejects_wrong_dataset(self):
        with tempfile.TemporaryDirectory() as d:
            out=Path(d);b.write(out/'run.json',{'dataset_sha256':'wrong','model':{},'task_ids':[]})
            with self.assertRaisesRegex(ValueError,'mismatch'):b.report(out)

    def test_unstructured_response_is_not_successfully_scored(self):
        with self.assertRaises(ValueError):b.parse_answer('arbitrary explanatory prose')
        self.assertEqual(b.parse_answer('```json\n{"answer":["a","b"]}\n```'),['a','b'])

    def test_offline_check_rejects_changed_image_and_source(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); image=root/'image.jpg'; source=root/'source.json'
            image.write_bytes(b'image');source.write_bytes(b'source')
            manifest={'dataset_sha256':'fixture','tracks':{'classification':1},
                      'sources':[{'path':'source.json','sha256':b.sha(source)}],
                      'excluded_missing_images':[]}
            tasks=[{'id':'one','images':['image.jpg'],'image_hashes':[b.sha(image)]}]
            with patch.object(b,'ROOT',root), patch.object(b,'ART',root/'art'), patch.object(b,'dataset',return_value=(manifest,tasks)):
                self.assertEqual(b.check()['model_requests'],0)
                image.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'Image changed'): b.check()
                image.write_bytes(b'image');source.write_bytes(b'changed')
                with self.assertRaisesRegex(ValueError,'Source changed'): b.check()

    def test_dry_configuration_does_not_require_cloud_credentials(self):
        with tempfile.TemporaryDirectory() as d:
            config=Path(d)/'models.yaml'
            config.write_text('models:\n  - name: v\n    model_name: vision\n    vision: true\n    mode: cloud\n    base_url: https://example.com/v1\n    api_key_env: LEGALHUB_TEST_ABSENT_KEY\n',encoding='utf-8')
            with patch.dict(b.os.environ,{},clear=True):
                self.assertEqual(b.model_config(config,'v',require_key=False)[1],'')
                with self.assertRaisesRegex(ValueError,'API key is missing'): b.model_config(config,'v')

    def test_vision_detail_and_reasoning_parameters_reach_provider(self):
        with tempfile.TemporaryDirectory() as d:
            image=Path(d)/'screenshot.jpg';image.write_bytes(b'original image')
            class Response:
                status_code=200
                headers={'x-request-id':'trace'}
                def json(self):
                    return {'id':'response','model':'gpt-6.1-sol','choices':[{'message':{'content':'{"answer":"x"}'},'finish_reason':'stop'}],'usage':{'total_tokens':10}}
            with patch.object(b.requests,'post',return_value=Response()) as post:
                result=b.infer_detailed({'model_name':'gpt-6.1-sol','base_url':'https://example.com/v1',
                                        'image_detail':'high','token_limit_parameter':'max_completion_tokens',
                                        'max_tokens':4096,'request_parameters':{'reasoning_effort':'low'}},
                                       'test-key','question',[str(image)])
                payload=post.call_args.kwargs['json']
                self.assertEqual(payload['messages'][1]['content'][1]['image_url']['detail'],'high')
                self.assertEqual(payload['max_completion_tokens'],4096)
                self.assertNotIn('max_tokens',payload)
                self.assertEqual(payload['reasoning_effort'],'low')
                self.assertEqual(result['request_id'],'trace')
                self.assertEqual(result['image_inputs'],1)
                self.assertEqual(result['provider_response']['id'],'response')

    def test_provider_failure_preserves_status_without_secret(self):
        class Response:
            status_code=402
            def json(self):return {'code':30001,'message':'insufficient balance test-secret'}
        with patch.object(b.requests,'post',return_value=Response()):
            with self.assertRaises(b.ProviderHTTPError) as raised:
                b.infer_detailed({'model_name':'vision','base_url':'https://example.com/v1'},'test-secret','question',[])
            self.assertEqual(raised.exception.http_status,402)
            self.assertNotIn('test-secret',json.dumps(raised.exception.provider_error))

if __name__=='__main__':unittest.main()
