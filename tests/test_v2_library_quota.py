import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools import v2_library_expansion as library


class LibraryQuotaTests(unittest.TestCase):
    def test_missing_causes_precede_repeated_causes(self):
        catalog = {key: {'causes': [cause]} for key, cause in
                   [('a0', 'A'), ('a1', 'A'), ('a2', 'A'), ('b1', 'B'), ('c1', 'C')]}
        rows = [{'document_id': key} for key in ['a1', 'a2', 'b1', 'c1']]
        selected = library.select_balanced(rows, 2, catalog, {'a0'}, target=3)
        self.assertEqual({row['document_id'] for row in selected}, {'b1', 'c1'})

    def test_quota_is_a_priority_and_does_not_truncate_library(self):
        catalog = {key: {'causes': ['A']} for key in ['a0', 'a1', 'a2', 'a3', 'a4']}
        rows = [{'document_id': key} for key in ['a3', 'a4']]
        self.assertEqual(library.select_balanced(rows, 10, catalog, {'a0', 'a1', 'a2'}, target=3), rows)

    def test_one_multilabel_judgment_covers_each_cause_once(self):
        catalog = {'old': {'causes': ['A', 'A', 'B']},
                   'a': {'causes': ['A']}, 'b': {'causes': ['B']}, 'c': {'causes': ['C']}}
        rows = [{'id': key} for key in ['a', 'b', 'c']]
        selected = library.select_balanced(rows, 1, catalog, ['old', 'old'], target=3)
        self.assertEqual(selected[0]['id'], 'c')

    def test_rulings_do_not_fill_judgment_quota(self):
        catalog = {'r': {'causes': ['A'], 'document_type': 'ruling_or_other'},
                   'a': {'causes': ['A'], 'document_type': 'judgment'},
                   'b': {'causes': ['B'], 'document_type': 'judgment'}}
        rows = [{'document_id': key} for key in ['r', 'a', 'b']]
        selected = library.select_balanced(rows, 3, catalog, {'r'}, target=3)
        self.assertEqual(selected[-1]['document_id'], 'r')
        self.assertEqual({r['document_id'] for r in selected[:2]}, {'a', 'b'})

    def test_cross_track_sources_are_deduplicated_and_pending_is_excluded(self):
        runtime = library.ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime, prefix='quota-test-') as temporary:
            root = Path(temporary)
            source = root / 'source'
            fact = root / 'datasets/v2.0.0/fact_constrained_20261106'
            library.save(source / 'current_artifacts.json', {'records': [{'document_id': 'same'}]})
            library.save(source / 'verification.json', {'checked': [
                {'id': 'same', 'group': 'communication'}, {'id': 'aux', 'group': 'auxiliary'}]})
            library.save(source / 'cases/same/peer.acceptance.json', {})
            library.save(source / 'cases/same/case.json', {'id': 'same'})
            library.save(fact / 'verification.json', {'checked': [{'id': 'fc_same'}, {'id': 'fc_pending'}]})
            library.save(fact / 'cases/fc_same/peer.acceptance.json', {})
            library.save(fact / 'cases/fc_same/case.json', {'source_judgment_id': 'same'})
            with patch.object(library, 'ROOT', root), patch.object(library, 'OUT', source):
                self.assertEqual(library.covered_source_ids(), {'same'})

    def test_invalid_quota_is_rejected(self):
        runtime = library.ROOT / '.runtime'
        runtime.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime, prefix='quota-config-test-') as temporary:
            out = Path(temporary)
            library.save(out / 'campaign.config.json', {'minimum_distinct_judgments_per_cause': 0})
            with patch.object(library, 'OUT', out), self.assertRaises(AssertionError):
                library.quota_target()


if __name__ == '__main__':
    unittest.main()
