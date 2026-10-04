import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from PIL import Image
from legalhub import retrieval as r
from legalhub import evidence as e
from legalhub.inference import request, validate_answer
from legalhub import benchmark as b


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        Image.new('RGB', (100, 200)).save(self.root / 'a.png')
        self.image = {'image_id': 'a', 'case_id': 'A', 'file': 'a.png', 'size': [100, 200],
                      'sha256': hashlib.sha256((self.root / 'a.png').read_bytes()).hexdigest(), 'evidence_page': 3, 'conversation_id': 'unconfirmed:a'}
        msg = {'id': 'm1', 'kind': 'message', 'case_id': 'A', 'image_id': 'a', 'conversation_id': 'unconfirmed:a', 'order': 0,
               'text': '借款500元，明天还款', 'person': 'a:right', 'timestamp_normalized': '2026-10-04T12:30:00', 'timestamp_raw': '2026-10-04 12:30',
               'source_refs': [{'image_id': 'a', 'bbox': [10, 20, 90, 50], 'evidence_page': 3, 'message_id': 'm1', 'quote': '借款500元，明天还款'}]}
        second = copy.deepcopy(msg); second.update(id='m2', text='好的', order=1, timestamp_normalized=None, timestamp_raw='12:31')
        second['source_refs'][0].update(message_id='m2', quote='好的', bbox=[10, 60, 90, 90])
        law = {'id': 'law', 'kind': 'statute', 'text': '借款人应当按照约定的期限返还借款', 'source_refs': []}
        self.corpus = {'images': [self.image], 'records': [msg, second, law]}
        self.patcher = patch.object(r, 'ROOT', self.root); self.patcher.start(); self.addCleanup(self.patcher.stop)
        self.db = self.root / 'index.sqlite3'; r.build(self.corpus, self.db); self.search = r.Retriever(self.db)

    def test_chinese_retrieval_keeps_citations_and_never_calls_model(self):
        with patch.object(b, 'infer_detailed', side_effect=AssertionError('retrieval invoked a model')):
            result = self.search.search('还款', 'A')
        self.assertEqual(result['results'][0]['id'], 'm1')
        self.assertEqual(result['model_requests'], 0)
        self.assertEqual(result['results'][0]['source_refs'][0]['evidence_page'], 3)

    def test_case_scope_required_and_isolation_survives_query_syntax(self):
        with self.assertRaises(ValueError): self.search.search('借款')
        self.assertEqual(self.search.search('借款', 'B')['results'], [])
        self.search.search('" OR 1=1 --', 'B')
        self.assertEqual(self.search.search('借款', scope='statute')['results'][0]['id'], 'law')

    def test_unknown_time_is_not_fabricated_or_in_date_filter(self):
        result = self.search.search('', 'A', after='2026-10-04', before='2026-10-04')
        self.assertEqual([x['id'] for x in result['results']], ['m1'])
        self.assertEqual(e.normalize_display_time('12:10'), (None, 'clock_only'))
        self.assertEqual(e.normalize_display_time('昨天12:10')[0], None)
        self.assertEqual(e.normalize_display_time('2026年10月4日 12:10')[0], '2026-10-04T12:10:00')

    def test_person_filter_is_exact_and_context_is_same_image(self):
        self.assertEqual(self.search.search('借款', 'A', person='other')['results'], [])
        self.assertEqual([x['id'] for x in self.search.context('m1')], ['m1', 'm2'])

    def test_bbox_and_changed_image_rejected_before_indexing(self):
        bad = copy.deepcopy(self.corpus); bad['records'][0]['source_refs'][0]['bbox'][2] = 101
        with self.assertRaises(ValueError): r.build(bad, self.db)
        # Previous committed index remains intact.
        self.assertEqual(self.search.search('借款', 'A')['results'][0]['id'], 'm1')
        (self.root / 'a.png').write_bytes(b'changed')
        with self.assertRaises(ValueError): r.build(self.corpus, self.db)

    def test_context_does_not_mix_competing_extraction_versions(self):
        first = copy.deepcopy(self.corpus['records'][0]); first['id'] = 'new1'
        first['source_refs'][0]['message_id'] = 'new1'
        first.update(origin_type='fresh_model_extraction', extraction_origin={'run_id': 'v1'})
        second = copy.deepcopy(first); second['id'] = 'new2'; second['source_refs'][0]['message_id'] = 'new2'
        second['extraction_origin']['run_id'] = 'v2'
        r.merge({'images': [], 'records': [first, second]}, self.db)
        self.assertEqual([x['id'] for x in self.search.context('new1')], ['new1'])

    def test_citation_cross_case_and_fabricated_quote_rejected(self):
        event = {'id': 'ev', 'kind': 'event', 'case_id': 'A', 'text': '还款承诺', 'source_refs': copy.deepcopy(self.corpus['records'][0]['source_refs'])}
        event['source_refs'][0]['quote'] = '已经偿还500元'
        bad = copy.deepcopy(self.corpus); bad['records'].append(event)
        with self.assertRaisesRegex(ValueError, 'Quote'): r.build(bad, self.db)
        event['source_refs'][0]['quote'] = '借款500元'; event['case_id'] = 'B'
        with self.assertRaisesRegex(ValueError, 'outside case'): r.build(bad, self.db)

    def test_paths_cannot_escape_workspace(self):
        with self.assertRaises(ValueError): r.workspace_file('../private.txt')

    def test_incremental_import_preserves_existing_results_and_failed_graph_is_atomic(self):
        extra = copy.deepcopy(self.corpus['records'][0]); extra['id'] = 'm3'; extra['text'] = '退款到账'
        extra['source_refs'][0].update(message_id='m3', quote='退款到账')
        r.merge({'images': [], 'records': [extra]}, self.db)
        self.assertEqual(self.search.search('退款', 'A')['results'][0]['id'], 'm3')
        self.assertEqual(self.search.search('借款', 'A')['results'][0]['id'], 'm1')
        extra['source_refs'][0]['image_id'] = 'absent'
        with self.assertRaises(ValueError): r.merge({'images': [], 'records': [extra]}, self.db)
        self.assertEqual(self.search.search('退款', 'A')['results'][0]['source_refs'][0]['image_id'], 'a')

    def test_timeline_keeps_unknown_date_events_separate_with_sources(self):
        first = {'id': 'e1', 'kind': 'event', 'case_id': 'A', 'text': '还款提议', 'timestamp_normalized': '2026-10-04T12:30:00',
                 'source_refs': copy.deepcopy(self.corpus['records'][0]['source_refs'])}
        second = dict(first, id='e2', timestamp_normalized=None)
        r.merge({'images': [], 'records': [first, second]}, self.db)
        timeline = self.search.timeline('A')
        self.assertEqual([x['id'] for x in timeline['known_dates']], ['e1'])
        self.assertEqual([x['id'] for x in timeline['unresolved_dates']], ['e2'])
        self.assertEqual(timeline['unresolved_dates'][0]['source_refs'][0]['evidence_page'], 3)
        self.assertEqual(timeline['model_requests'], 0)

    def test_competing_artifacts_cannot_silently_overwrite_record_ids(self):
        row = copy.deepcopy(self.corpus['records'][0]); row['source_artifact'] = 'first/raw.jsonl'
        r.merge({'images': [], 'records': [row]}, self.db)
        row['source_artifact'] = 'second/raw.jsonl'
        with self.assertRaisesRegex(ValueError, 'Conflicting record ID'):
            r.merge({'images': [], 'records': [row]}, self.db)
        self.assertEqual(self.search.record('m1')['source_artifact'], 'first/raw.jsonl')

    def test_exports_keep_multiple_pages_and_locations(self):
        row = copy.deepcopy(self.corpus['records'][0]); row['source_refs'].append({'image_id': 'b', 'evidence_page': 4, 'bbox': [1, 2, 3, 4], 'quote': '另一处'})
        exported = r.export_rows([row])[0]
        self.assertEqual(exported['evidence_pages'], ['3', '4'])
        self.assertEqual(len(exported['source_refs']), 2)

    def test_extraction_rejects_bad_bbox_and_keeps_uncertainty(self):
        good = {'text': '收到', 'speaker_side': 'left', 'speaker_name': 'unknown', 'timestamp_raw': '12:10',
                'bbox': [1, 2, 90, 40], 'event_type': 'unknown', 'main_intent': 'unknown', 'uncertainty': '身份不明'}
        bad = dict(good, bbox=[1, 2, 200, 400])
        rows, issues = e.records_for(self.image, {'messages': [good, bad]}, {'run_id': 'test'}, 'artifact.jsonl')
        self.assertEqual(len(rows), 1); self.assertEqual(len(issues), 1)
        self.assertIsNone(rows[0]['timestamp_normalized']); self.assertIsNone(rows[0]['speaker_party_id'])
        self.assertEqual(rows[0]['review_status'], 'unreviewed')


class InferenceTests(unittest.TestCase):
    def test_declared_normalized_boxes_are_converted_once_and_raw_retained(self):
        image = {'image_id': 'a', 'case_id': 'A', 'conversation_id': 'a', 'size': [828, 1104], 'evidence_page': 1}
        message = {'text': '收到', 'speaker_side': 'left', 'speaker_name': 'unknown', 'timestamp_raw': 'unknown',
                   'bbox': [250, 100, 500, 200], 'event_type': 'unknown', 'main_intent': 'unknown', 'uncertainty': ''}
        rows, errors = e.records_for(image, {'messages': [message]}, {'run_id': 'test'}, 'raw.jsonl', 'normalized_1000')
        self.assertEqual(errors, [])
        ref = rows[0]['source_refs'][0]
        self.assertEqual(ref['bbox'], [207, 110.4, 414, 220.8])
        self.assertEqual(ref['raw_bbox'], [250, 100, 500, 200])
        message['bbox'] = [250, 100, 500, 1100]
        rows, errors = e.records_for(image, {'messages': [message]}, {'run_id': 'test'}, 'raw.jsonl', 'normalized_1000')
        self.assertEqual(rows, []); self.assertEqual(len(errors), 1)

    def test_image_progress_does_not_complete_job_before_index_commit(self):
        from legalhub.app import update_progress
        job = {'status': 'running', 'completed': 0}
        update_progress(job, {'status': 'ok', 'completed': 1, 'image_id': 'a'})
        self.assertEqual(job['status'], 'running')
        self.assertEqual(job['last_image_status'], 'ok')
        self.assertEqual(job['completed'], 1)

    def test_retry_records_every_attempt_and_does_not_retry_auth(self):
        result = {'raw': '{"answer":"yes"}', 'http_status': 200, 'latency_seconds': .1, 'usage': {'prompt_tokens': 2}}
        with patch.object(b, 'infer_detailed', side_effect=[b.ProviderHTTPError(500, {'code': 'failure'}), result]) as call:
            row = request({}, 'secret', 'prompt', [], sleeper=lambda _: None)
        self.assertEqual(call.call_count, 2); self.assertFalse(row['first_attempt_success']); self.assertEqual(len(row['attempts']), 2)
        with patch.object(b, 'infer_detailed', side_effect=b.ProviderHTTPError(401)) as call:
            row = request({}, 'secret', 'prompt', [], sleeper=lambda _: None)
        self.assertEqual(call.call_count, 1); self.assertEqual(row['status'], 'error')

    def test_valid_json_with_invalid_enum_is_not_a_valid_answer(self):
        task = {'track': 'screening_bundle', 'answer_spaces': {'evidence': ['is_evidence', 'not_evidence', 'unknown']}}
        self.assertFalse(validate_answer({'evidence': 'looks good'}, task))
        self.assertFalse(validate_answer({'evidence': 'unknown', 'extra': 'x'}, task))
        self.assertTrue(validate_answer({'evidence': 'unknown'}, task))


if __name__ == '__main__': unittest.main()
