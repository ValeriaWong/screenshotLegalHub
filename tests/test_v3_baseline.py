"""Integrity and boundary tests for local, append-only V3 snapshots."""
import copy
import json
from pathlib import Path
import tempfile
import unittest

from tools.prepare_v3_baseline import check, freeze


class BaselineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='v3-baseline-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.out = 'datasets/v3.0.0/test_batch'
        self.put('inputs/source.txt', 'old source\n')
        self.put('inputs/nested/candidate.json', '{"candidate": true}\n')
        self.put('ledger.json', json.dumps({'gaps': [dict(id='G01', stage='S0', status='open',
                    title='Full input pool', acceptance='Complete the input pool')]}))
        self.spec = dict(schema_version=1, scope='Test-only partial preparation',
            software_baseline={'reproduction_status': 'not_verified'},
            limitations=['Not certified'], gap_ledger='ledger.json', gap_owners={'G01': ['data_engineering']},
            groups=[dict(id='test', paths=['inputs'], source_id='local-test', version='test-v1',
                origin_type='test_fixture', author_status='test', review_status='not_reviewed',
                permitted_use='internal_preparation_only')])

    def put(self, relative, text):
        file = self.root / relative
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding='utf-8')

    def run_freeze(self):
        self.put('spec.json', json.dumps(self.spec))
        return freeze(self.root, 'spec.json', self.out)

    def test_freezes_actual_files_without_git_and_keeps_use_boundary(self):
        self.assertEqual(self.run_freeze()['status'], 'passed')
        out = self.root / self.out
        rows = [json.loads(line) for line in (out / 'source_manifest.jsonl').read_text(encoding='utf-8').splitlines()]
        self.assertEqual(len(rows), 2)
        for row in rows:
            self.assertEqual((out / row['snapshot_path']).read_bytes(), (self.root / row['path']).read_bytes())
        readiness = json.loads((out / 'readiness.json').read_text(encoding='utf-8'))
        self.assertFalse(readiness['s0_accepted'])
        self.assertFalse(readiness['can_run_formal_evaluation'])
        self.assertTrue(readiness['can_prepare_s1'])
        self.assertEqual(readiness['remaining_gaps'][0]['owners'], ['data_engineering'])
        self.assertEqual(check(self.root, self.out)['status'], 'passed')

    def test_existing_batch_cannot_be_overwritten(self):
        self.run_freeze()
        original = (self.root / self.out / 'baseline_snapshot.json').read_bytes()
        self.put('inputs/source.txt', 'changed')
        with self.assertRaisesRegex(ValueError, 'already exists'):
            self.run_freeze()
        self.assertEqual((self.root / self.out / 'baseline_snapshot.json').read_bytes(), original)

    def test_source_drift_does_not_invalidate_frozen_copy(self):
        self.run_freeze()
        self.put('inputs/source.txt', 'new version')
        self.assertEqual(check(self.root, self.out)['status'], 'passed')
        result = check(self.root, self.out, check_sources=True)
        self.assertEqual(result['status'], 'failed')
        self.assertTrue(any('input changed' in e for e in result['errors']))

    def test_source_addition_and_removal_are_detected(self):
        self.run_freeze()
        self.put('inputs/new.txt', 'new')
        self.assertEqual(check(self.root, self.out, True)['status'], 'failed')
        (self.root / 'inputs/source.txt').unlink()
        self.assertEqual(check(self.root, self.out, True)['status'], 'failed')
        self.assertEqual(check(self.root, self.out)['status'], 'passed')

    def test_corrupted_snapshot_and_extra_files_are_detected(self):
        self.run_freeze()
        self.put(self.out + '/snapshot/inputs/source.txt', 'corrupted')
        self.assertEqual(check(self.root, self.out)['status'], 'failed')
        self.put(self.out + '/snapshot/inputs/source.txt', 'old source\n')
        self.put(self.out + '/snapshot/unlisted.txt', 'extra')
        self.assertEqual(check(self.root, self.out)['status'], 'failed')

    def test_missing_or_changed_control_file_fails(self):
        self.run_freeze()
        file = self.root / self.out / 'source_manifest.jsonl'
        original = file.read_bytes()
        file.write_bytes(b'')
        self.assertEqual(check(self.root, self.out)['status'], 'failed')
        file.write_bytes(original)
        (self.root / self.out / 'readiness.json').unlink()
        self.assertEqual(check(self.root, self.out)['status'], 'failed')

    def test_missing_input_and_empty_directory_fail_before_output(self):
        for relative in ['missing.txt', 'empty']:
            with self.subTest(relative=relative):
                (self.root / 'empty').mkdir(exist_ok=True)
                self.spec['groups'][0]['paths'] = [relative]
                with self.assertRaises(ValueError):
                    self.run_freeze()
                self.assertFalse((self.root / self.out).exists())

    def test_traversal_and_outside_output_are_rejected(self):
        for relative in ['../outside', '/absolute', 'C:/outside', 'inputs/../ledger.json', 'inputs\\source.txt']:
            with self.subTest(relative=relative):
                self.spec['groups'][0]['paths'] = [relative]
                with self.assertRaises(ValueError):
                    self.run_freeze()
        self.spec['groups'][0]['paths'] = ['inputs']
        self.out = 'datasets/v2.0.0/would-overwrite-history'
        with self.assertRaises(ValueError):
            self.run_freeze()
        self.assertFalse((self.root / self.out).exists())

    def test_private_configs_and_databases_are_rejected(self):
        for relative in ['.env', 'models.local.yaml', 'user.sqlite3', 'secret.key', '.venv/file.txt']:
            with self.subTest(relative=relative):
                target = self.root / 'inputs' / relative
                self.put('inputs/' + relative, 'private fixture')
                with self.assertRaisesRegex(ValueError, 'excluded'):
                    self.run_freeze()
                target.unlink()
                if target.parent.name == '.venv':
                    target.parent.rmdir()
                self.assertFalse((self.root / self.out).exists())

    def test_cache_is_not_an_asset(self):
        self.put('inputs/__pycache__/cached.pyc', 'cache')
        self.assertEqual(self.run_freeze()['asset_count'], 2)

    def test_empty_metadata_unassigned_gap_and_duplicate_inputs_fail(self):
        original = copy.deepcopy(self.spec)
        variants = []
        for change in ['metadata', 'owner', 'duplicate', 'use']:
            variant = copy.deepcopy(original)
            if change == 'metadata':
                variant['groups'][0]['source_id'] = ''
            elif change == 'owner':
                variant['gap_owners'] = {}
            elif change == 'duplicate':
                variant['groups'][0]['paths'].append('inputs/source.txt')
            else:
                variant['groups'][0]['permitted_use'] = 'public_release'
            variants.append(variant)
        for variant in variants:
            self.spec = variant
            with self.assertRaises(ValueError):
                self.run_freeze()
            self.assertFalse((self.root / self.out).exists())

    def test_symlink_input_is_rejected(self):
        try:
            (self.root / 'inputs/link.txt').symlink_to(self.root / 'ledger.json')
        except OSError:
            self.skipTest('Creating symlinks requires Windows privilege')
        with self.assertRaisesRegex(ValueError, 'Links'):
            self.run_freeze()

    def test_frozen_check_does_not_follow_replaced_source_link(self):
        self.run_freeze()
        file = self.root / 'inputs/source.txt'
        file.unlink()
        try:
            file.symlink_to(self.root / 'ledger.json')
        except OSError:
            self.skipTest('Creating symlinks requires Windows privilege')
        self.assertEqual(check(self.root, self.out)['status'], 'passed')
        self.assertEqual(check(self.root, self.out, True)['status'], 'failed')

    def test_incomplete_batch_is_not_accepted(self):
        self.run_freeze()
        self.put(self.out + '/.incomplete', 'interrupted')
        self.assertEqual(check(self.root, self.out)['status'], 'failed')


if __name__ == '__main__':
    unittest.main()
