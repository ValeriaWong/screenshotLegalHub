"""Provenance checks must fail on damaged locators, content or missing images."""
import io
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

import openpyxl
from tools.audit_v3_inputs import audit, candidate_audit, image_audit, score_audit, sha_bytes


class SourceAuditTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v3-input-audit-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '评分'
        ws.append(['title', 'score', 'comment'])
        ws.append(['case', 0, '原始意见'])
        raw = io.BytesIO()
        wb.save(raw)
        wb.close()
        self.workbook = raw.getvalue()
        with zipfile.ZipFile(self.root / 'feedback.zip', 'w') as z:
            z.writestr('旧评分.xlsx', self.workbook)
        self.ref = dict(archive='feedback.zip', workbook='旧评分.xlsx', workbook_sha256=sha_bytes(self.workbook),
            sheet='评分', excel_row=2, cells=[dict(column='A', label='title', value='case'),
            dict(column='B', label='score', value=0), dict(column='C', label='comment', value='原始意见')])
        self.put('references.json', [self.ref])
        self.put_bytes('images/a.png', b'image-fixture')
        self.task = dict(id='t1', split='development', images=['images/a.png'], image_hashes=[sha_bytes(b'image-fixture')])
        self.put_bytes('tasks.jsonl', (json.dumps(self.task)+'\n').encode('utf-8'))
        self.config = dict(reference_files=['references.json'], task_file='tasks.jsonl',
                           language_targets=dict(zh=2, en=2), candidates=[])
        # Both upstream formats use exactly the historical zero-based index.
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(['content', 'case_no'])
        for index in range(2):
            ws.append(['zh-text-'+str(index), 'zh-case-'+str(index)])
        wb.save(self.root / 'cn.xlsx')
        wb.close()
        en = [dict(judgment_text='en-text-'+str(i), neutral_citation='en-case-'+str(i)) for i in range(2)]
        self.put_bytes('en.jsonl', ''.join(json.dumps(r)+'\n' for r in en).encode('utf-8'))
        for language in ['zh', 'en']:
            upstream = 'cn.xlsx' if language == 'zh' else 'en.jsonl'
            for index in range(2):
                ident = language+str(index)
                text = language+'-text-'+str(index)
                source = dict(id=ident, case_no=language+'-case-'+str(index), language=language,
                    jurisdiction='test', source_file=upstream, source_index=index,
                    source_sha256=sha_bytes((self.root/upstream).read_bytes()), text=text,
                    judgment_text_sha256=sha_bytes(text.encode('utf-8')),
                    paragraphs=[dict(id='p1', char_start=0, char_end=len(text), text=text)])
                self.put(ident+'/source.json', source)
                self.put(ident+'/case.json', dict(messages=[dict(id='m1')]))
                self.config['candidates'].append(dict(directory=ident, candidate_file='case.json', scope_proposal='test'))
        self.put('spec.json', self.config)
        self.out = 'datasets/v3.0.0/audit_test'
        self.score_out = self.root/'score_output'
        self.score_out.mkdir()

    def put_bytes(self, file, content):
        target = self.root/file
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)

    def put(self, file, content):
        self.put_bytes(file, json.dumps(content, ensure_ascii=False).encode('utf-8'))

    def scores(self):
        self.put('references.json', [self.ref])
        return score_audit(self.root, ['references.json'], self.score_out)[1]

    def pool(self):
        return candidate_audit(self.root, self.config['candidates'], self.config['language_targets'])[0]

    def test_complete_audit_preserves_workbook_bytes_and_locators(self):
        result = audit(self.root, 'spec.json', self.out)
        self.assertEqual(result['status'], 'passed')
        self.assertEqual((result['score_records'], result['cells_checked'], result['unique_images']), (1, 3, 1))
        workbooks = list((self.root/self.out/'workbooks').glob('*.xlsx'))
        self.assertEqual(workbooks[0].read_bytes(), self.workbook)
        pool = self.pool()
        self.assertEqual(pool[1]['upstream_locator']['excel_row'], 3)
        self.assertEqual(pool[3]['upstream_locator']['jsonl_line'], 2)
        self.assertTrue(all(c['split']=='development' for c in pool))

    def test_existing_output_is_not_overwritten(self):
        audit(self.root, 'spec.json', self.out)
        with self.assertRaisesRegex(ValueError, 'already exists'):
            audit(self.root, 'spec.json', self.out)

    def test_score_content_and_header_mismatches_are_detected(self):
        self.ref['cells'][1]['value'] = 1
        self.assertEqual(self.scores()[0]['status'], 'failed')
        self.ref['cells'][1]['value'] = 0
        self.ref['cells'][1]['label'] = 'wrong header'
        self.assertEqual(self.scores()[0]['status'], 'failed')

    def test_omitted_nonempty_cell_is_detected(self):
        self.ref['cells'].pop()
        self.assertEqual(self.scores()[0]['status'], 'failed')

    def test_workbook_hash_and_invalid_locators_fail(self):
        self.ref['workbook_sha256'] = '0'*64
        self.assertIn('workbook_hash_mismatch', self.scores()[0]['errors'])
        self.ref['sheet'] = 'absent'
        self.assertIn('sheet_or_row_missing', self.scores()[0]['errors'])
        self.ref['excel_row'] = 0
        with self.assertRaisesRegex(ValueError, 'row locator'):
            self.scores()

    def test_missing_or_changed_image_fails(self):
        (self.root/'images/a.png').write_bytes(b'changed')
        self.assertEqual(image_audit(self.root, 'tasks.jsonl')[1][0]['status'], 'failed')
        (self.root/'images/a.png').unlink()
        self.assertEqual(image_audit(self.root, 'tasks.jsonl')[1][0]['status'], 'failed')

    def test_image_count_and_traversal_are_rejected(self):
        self.task['image_hashes'] = []
        self.put_bytes('tasks.jsonl', json.dumps(self.task).encode('utf-8'))
        with self.assertRaisesRegex(ValueError, 'cardinality'):
            image_audit(self.root, 'tasks.jsonl')
        self.task['image_hashes'] = ['0'*64]
        self.task['images'] = ['../outside']
        self.put_bytes('tasks.jsonl', json.dumps(self.task).encode('utf-8'))
        with self.assertRaises(ValueError):
            image_audit(self.root, 'tasks.jsonl')

    def test_ambiguous_archive_member_is_rejected(self):
        # Same decoded name cannot silently select one of two records.
        with zipfile.ZipFile(self.root/'feedback.zip', 'w') as z:
            z.writestr('unrelated.xlsx', self.workbook)
        with self.assertRaisesRegex(ValueError, 'Missing/ambiguous'):
            self.scores()

    def test_source_index_text_and_offsets_are_checked(self):
        source = json.loads((self.root/'zh0/source.json').read_text(encoding='utf-8'))
        source['source_index'] = 1
        self.put('zh0/source.json', source)
        self.assertIn('upstream_text_mismatch', self.pool()[0]['errors'])
        source['source_index'] = 0
        source['paragraphs'][0]['char_end'] -= 1
        self.put('zh0/source.json', source)
        self.assertIn('paragraph_offset_mismatch:p1', self.pool()[0]['errors'])

    def test_upstream_container_drift_is_detected(self):
        with (self.root/'en.jsonl').open('a', encoding='utf-8') as stream:
            stream.write('{"new":true}\n')
        self.assertIn('upstream_file_hash_mismatch', self.pool()[2]['errors'])

    def test_duplicate_source_and_language_imbalance_rejected(self):
        self.config['candidates'][1] = self.config['candidates'][0]
        with self.assertRaisesRegex(ValueError, 'Repeated'):
            self.pool()
        self.config['candidates'].pop()
        with self.assertRaisesRegex(ValueError, 'language'):
            self.pool()

    def test_empty_row_is_preserved_but_not_mapping_evidence(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = '评分'
        ws.append(['title', 'score', 'comment'])
        ws.append([None, None, None])
        ws.append(['after empty row', 1, None])
        raw = io.BytesIO()
        wb.save(raw)
        wb.close()
        with zipfile.ZipFile(self.root/'feedback.zip', 'w') as z:
            z.writestr('旧评分.xlsx', raw.getvalue())
        self.ref['workbook_sha256'] = sha_bytes(raw.getvalue())
        self.ref['cells'] = []
        row = self.scores()[0]
        self.assertEqual(row['status'], 'passed')
        self.assertEqual(row['content_status'], 'empty')
        self.assertFalse(row['usable_for_mapping'])

    def test_empty_extraction_does_not_hide_real_cells(self):
        self.ref['cells'] = []
        self.assertEqual(self.scores()[0]['status'], 'failed')

    def test_failed_checks_remain_failed_in_final_summary(self):
        self.ref['cells'][1]['value'] = 5
        self.put('references.json', [self.ref])
        result = audit(self.root, 'spec.json', self.out)
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(result['errors'][0]['kind'], 'score')


if __name__ == '__main__':
    unittest.main()
