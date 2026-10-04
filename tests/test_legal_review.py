"""Review persistence tests use synthetic data only; no evidence/model reads."""
import copy
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sqlite3
import tempfile
import threading
import unittest
from unittest.mock import patch

from legalhub.legal_review import ReviewConflict, ReviewNotFound, ReviewStore, ReviewValidation


def item(case_id='alpha', item_id='term-1', fingerprint='source-v1'):
    return {'id': item_id, 'case_id': case_id, 'case_name': 'Synthetic case',
        'kind': 'contract_term', 'title': {'zh': 'Test', 'en': 'Test'},
        'original_text': 'Synthetic original', 'proposed_text': 'Synthetic proposal',
        'rationale': 'Fixture only', 'priority': 'high',
        'source_refs': [{'image_id': case_id + '-image', 'message_id': 'message',
                         'quote': 'Synthetic original', 'bbox': [0, 0, 10, 10]}],
        'sources': [{'image_id': case_id + '-image', 'sha256': fingerprint,
                     'size': [10, 10], 'page': 1}], 'source_fingerprint': fingerprint,
        'source_coverage': 'fixture', 'content_origin': 'synthetic'}


class Registry:
    def __init__(self):
        self.cases = [{'case_id': 'alpha', 'name': 'Alpha', 'status': 'analyzed'},
                      {'case_id': 'beta', 'name': 'Beta', 'status': 'originals'}]
        self.content = {'alpha': [item()], 'beta': [item('beta', 'other-item')]}
        self.loaded = []

    def list(self):
        return copy.deepcopy(self.cases)

    def get(self, case_id):
        self.loaded.append(case_id)
        return case_id

    def build(self, workspace, chat_rows=None):
        return copy.deepcopy(self.content[workspace])


class ReviewStoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'reviews.sqlite3'
        self.registry = Registry()
        self.store = self.new_store()

    def new_store(self):
        return ReviewStore(self.registry, db_path=self.path, item_builder=self.registry.build)

    def test_persistence_preserves_originals_and_separate_amendment(self):
        original = copy.deepcopy(self.registry.content)
        saved = self.store.save('alpha', 'term-1', 'amended', edited_text='Human amendment',
                                note='Checked', expected_revision=0)
        loaded = self.new_store().get_item('alpha', 'term-1')
        self.assertEqual(loaded, saved)
        self.assertEqual(loaded['review']['status'], 'amended')
        self.assertEqual(loaded['review']['revision'], 1)
        self.assertEqual(loaded['original_text'], 'Synthetic original')
        self.assertEqual(loaded['proposed_text'], 'Synthetic proposal')
        self.assertEqual(self.registry.content, original)
        self.assertEqual([event['event'] for event in loaded['history']], ['registered', 'amended'])

    def test_changed_source_marks_stale_and_retains_approval_history(self):
        self.store.save('alpha', 'term-1', 'confirmed', expected_revision=0)
        self.registry.content['alpha'][0]['source_fingerprint'] = 'source-v2'
        self.registry.content['alpha'][0]['sources'][0]['sha256'] = 'source-v2'
        stale = self.store.get_item('alpha', 'term-1')
        self.assertEqual(stale['review']['status'], 'stale')
        self.assertEqual(stale['review']['revision'], 2)
        changed = stale['history'][-1]
        self.assertEqual(changed['event'], 'source_changed')
        self.assertEqual(changed['before']['review']['status'], 'confirmed')
        self.assertEqual(changed['before']['source_fingerprint'], 'source-v1')
        self.assertIsNone(self.store.export_review('alpha')['items'][0]['reviewed_text'])
        confirmed = self.store.save('alpha', 'term-1', 'confirmed', expected_revision=2)
        self.assertEqual(confirmed['review']['status'], 'confirmed')

    def test_content_change_without_source_change_invalidates_review(self):
        self.store.save('alpha', 'term-1', 'confirmed', expected_revision=0)
        self.registry.content['alpha'][0]['proposed_text'] = 'Changed synthetic proposal'
        stale = self.store.get_item('alpha', 'term-1')
        self.assertEqual(stale['review']['status'], 'stale')
        self.assertEqual(stale['history'][-1]['before']['proposed_text'], 'Synthetic proposal')

    def test_concurrency_checks_persisted_revision_across_store_instances(self):
        other = self.new_store()
        self.store.get_item('alpha', 'term-1')
        other.save('alpha', 'term-1', 'confirmed', expected_revision=0)
        with self.assertRaises(ReviewConflict):
            self.store.save('alpha', 'term-1', 'rejected', expected_revision=0)
        self.assertEqual(self.store.get_item('alpha', 'term-1')['review']['status'], 'confirmed')

    def test_simultaneous_writers_allow_exactly_one_revision_update(self):
        other = self.new_store()
        self.store.get_item('alpha', 'term-1')
        ready = threading.Barrier(2)

        def save(store, decision):
            ready.wait(timeout=5)
            try:
                return store.save('alpha', 'term-1', decision, expected_revision=0)['review']['status']
            except ReviewConflict:
                return 'conflict'

        with ThreadPoolExecutor(max_workers=2) as workers:
            first = workers.submit(save, self.store, 'confirmed')
            second = workers.submit(save, other, 'rejected')
            results = [first.result(timeout=10), second.result(timeout=10)]
        self.assertEqual(results.count('conflict'), 1)
        loaded = self.store.get_item('alpha', 'term-1')
        self.assertEqual(loaded['review']['revision'], 1)
        self.assertEqual(len(loaded['history']), 2)

    def test_save_detects_source_change_before_accepting_revision(self):
        self.store.save('alpha', 'term-1', 'amended', edited_text='Prior human edit', expected_revision=0)
        self.registry.content['alpha'][0]['source_fingerprint'] = 'source-v2'
        with self.assertRaises(ReviewConflict):
            self.store.save('alpha', 'term-1', 'confirmed', expected_revision=1)
        stale = self.store.get_item('alpha', 'term-1')
        self.assertEqual(stale['review']['status'], 'stale')
        self.assertEqual(stale['review']['revision'], 2)
        self.assertEqual(stale['review']['edited_text'], 'Prior human edit')
        self.assertEqual(stale['history'][-1]['before']['review']['status'], 'amended')
        self.assertIsNone(self.store.export_review('alpha')['items'][0]['reviewed_text'])

    def test_cross_case_and_unknown_items_are_rejected(self):
        self.store.get_item('alpha', 'term-1')
        with self.assertRaises(ReviewNotFound):
            self.store.save('beta', 'term-1', 'confirmed', expected_revision=0)
        with self.assertRaises(ReviewNotFound):
            self.store.get_item('missing-case', 'term-1')
        with self.assertRaises(ReviewNotFound):
            self.store.get_item('alpha', 'missing-item')
        self.assertEqual(self.store.get_item('alpha', 'term-1')['review']['revision'], 0)

    def test_amendment_and_revision_validation(self):
        for text in ('', '  ', None):
            with self.subTest(text=text), self.assertRaises(ReviewValidation):
                self.store.save('alpha', 'term-1', 'amended', edited_text=text, expected_revision=0)
        for revision in (None, -1, '0', True):
            with self.subTest(revision=revision), self.assertRaises(ReviewValidation):
                self.store.save('alpha', 'term-1', 'confirmed', expected_revision=revision)
        self.assertEqual(self.store.get_item('alpha', 'term-1')['review']['revision'], 0)

    def test_default_scope_filter_counts_and_pagination(self):
        self.registry.content['alpha'].append(item(item_id='term-2'))
        queue = self.store.queue(limit=1)
        self.assertEqual(queue['total'], 2)
        self.assertEqual(len(queue['items']), 1)
        self.assertEqual(self.registry.loaded, ['alpha'])
        self.assertEqual(queue['counts']['pending'], 2)
        self.store.save('alpha', 'term-1', 'deferred', expected_revision=0)
        queue = self.store.queue(status='all', offset=1, limit=1)
        self.assertEqual(queue['items'][0]['id'], 'term-2')
        self.assertEqual(queue['counts']['deferred'], 1)
        self.assertEqual(self.store.queue(case_id='beta')['items'][0]['id'], 'other-item')
        self.assertEqual(self.store.queue(kind='fact')['total'], 0)

    def test_filtered_registry_provider_avoids_full_case_list(self):
        requested = []

        def review_cases(case_id=None):
            requested.append(case_id)
            return copy.deepcopy([case for case in self.registry.cases
                if case['case_id'] == case_id] if case_id is not None else
                [case for case in self.registry.cases if case['status'] == 'analyzed'])

        self.registry.review_cases = review_cases
        with patch.object(self.registry, 'list', side_effect=AssertionError('Full registry list used')):
            queue = self.store.queue()
            self.assertEqual([case['case_id'] for case in queue['cases']], ['alpha'])
            self.assertEqual(self.store.get_item('beta', 'other-item')['case_id'], 'beta')
            saved = self.store.save('beta', 'other-item', 'confirmed', expected_revision=0)
            self.assertEqual(saved['review']['status'], 'confirmed')
            with self.assertRaises(ReviewNotFound):
                self.store.get_item('unknown', 'term-1')
        self.assertEqual(requested, [None, 'beta', 'beta', 'unknown'])

    def test_export_distinguishes_confirmed_rejected_and_human_amendment(self):
        self.registry.content['alpha'].extend([item(item_id='term-2'), item(item_id='term-3')])
        self.store.save('alpha', 'term-1', 'confirmed', expected_revision=0)
        self.store.save('alpha', 'term-2', 'rejected', expected_revision=0)
        self.store.save('alpha', 'term-3', 'amended', edited_text='User-only text', expected_revision=0)
        exported = self.store.export_review('alpha')['items']
        self.assertEqual([row['reviewed_text'] for row in exported],
                         ['Synthetic proposal', None, 'User-only text'])
        self.assertEqual(exported[2]['reviewed_text_origin'], 'user_amendment')
        self.assertTrue(all(row['source_refs'] and row['history'] for row in exported))

    def test_removed_item_stays_auditable_and_cannot_be_approved(self):
        self.store.save('alpha', 'term-1', 'confirmed', expected_revision=0)
        self.registry.content['alpha'] = []
        removed = self.store.get_item('alpha', 'term-1')
        self.assertEqual(removed['review']['status'], 'stale')
        self.assertFalse(removed['review']['available'])
        with self.assertRaises(ReviewConflict):
            self.store.save('alpha', 'term-1', 'confirmed', expected_revision=2)
        self.registry.content['alpha'] = [item()]
        returned = self.store.get_item('alpha', 'term-1')
        self.assertTrue(returned['review']['available'])
        self.assertEqual(returned['review']['status'], 'stale')
        self.assertEqual(returned['review']['revision'], 3)

    def test_noop_is_idempotent_and_reopen_clears_effective_replacement(self):
        saved = self.store.save('alpha', 'term-1', 'amended', edited_text='Edited', expected_revision=0)
        repeated = self.store.save('alpha', 'term-1', 'amended', edited_text='Edited', expected_revision=1)
        self.assertEqual(saved, repeated)
        reopened = self.store.save('alpha', 'term-1', 'reopen', expected_revision=1)
        self.assertEqual(reopened['review']['status'], 'pending')
        self.assertEqual(reopened['review']['edited_text'], '')
        self.assertEqual(reopened['history'][-1]['before']['review']['edited_text'], 'Edited')

    def test_audit_and_current_state_update_atomically(self):
        self.store.get_item('alpha', 'term-1')
        with patch.object(self.store, '_event', side_effect=RuntimeError('synthetic write error')):
            with self.assertRaises(RuntimeError):
                self.store.save('alpha', 'term-1', 'confirmed', expected_revision=0)
        loaded = self.store.get_item('alpha', 'term-1')
        self.assertEqual(loaded['review']['revision'], 0)
        self.assertEqual(len(loaded['history']), 1)
        with sqlite3.connect(self.path) as db:
            with self.assertRaises(sqlite3.IntegrityError):
                db.execute('DELETE FROM review_events')
            payload = json.loads(db.execute('SELECT payload FROM review_events').fetchone()[0])
            self.assertEqual(payload['after']['review']['status'], 'pending')


if __name__ == '__main__':
    unittest.main()
