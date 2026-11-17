import json
import os
import tempfile
import unittest
from pathlib import Path

from tools import v2_worker_retry as retry
from tools import v2_library_authoring as author
from tools.v2_library_expansion import ROOT, read, save, sha


class WorkerRetryTests(unittest.TestCase):
    def fixture(self, message='stream disconnected: EOF (502: retry)'):
        base = ROOT / '.runtime'
        base.mkdir(exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base, prefix='retry-test-')
        self.addCleanup(temp.cleanup)
        campaign = Path(temp.name)
        job = campaign / 'jobs' / 'writer'
        save(job / 'assignment.json', {'records': [{'document_id': 'zh_a'}]})
        save(job / 'runtime.json', {'pid': 12345})
        (job / 'prompt.txt').write_text('Preserve this task', encoding='utf-8')
        (job / 'last_message.txt').write_text('', encoding='utf-8')
        events = job / 'events.jsonl'
        events.write_text(json.dumps({'type': 'turn.failed', 'error': {'message': message}}) + '\n', encoding='utf-8')
        os.utime(events, (100, 100))
        save(campaign / 'automation.json', {'phase': 'needs_attention', 'error': 'dead', 'author_jobs_ingested': ['old']})
        return campaign, job

    def recover(self, campaign, active=(), now=1000):
        return retry.recover_dead_authors([campaign], active, author.job_finished, now)

    def test_retry_preserves_logs_inputs_and_ingestion_checkpoint(self):
        campaign, job = self.fixture()
        original = {p.name: sha(p) for p in job.iterdir() if p.is_file()}
        result = self.recover(campaign)
        self.assertEqual(len(result['queued']), 1)
        archive = job / 'attempts/transport_retry_001'
        for name, digest in original.items():
            self.assertEqual(sha(archive / name), digest)
        self.assertEqual(sha(job / 'assignment.json'), original['assignment.json'])
        self.assertEqual(sha(job / 'prompt.txt'), original['prompt.txt'])
        self.assertFalse((job / 'runtime.json').exists())
        self.assertFalse((job / 'events.jsonl').exists())
        self.assertEqual(read(campaign / 'automation.json')['author_jobs_ingested'], ['old'])
        self.assertEqual(read(campaign / 'automation.json')['phase'], 'transport_retry_queued')
        self.assertFalse(self.recover(campaign)['queued'])

    def test_backoff_and_retry_limit_survive_restart(self):
        campaign, job = self.fixture()
        self.assertTrue(self.recover(campaign, now=110)['waiting'])
        self.assertTrue((job / 'runtime.json').exists())
        save(job / 'retry.state.json', {'attempts': 3})
        self.assertEqual(self.recover(campaign)['refused'][0]['reason'], 'retry_limit_reached')
        self.assertTrue((job / 'runtime.json').exists())

    def test_partial_outputs_are_never_replayed(self):
        campaign, job = self.fixture()
        save(campaign / 'authoring/writer/zh_a/direct.draft.json', {'partial': True})
        self.assertEqual(self.recover(campaign)['refused'][0]['reason'], 'partial_author_outputs_require_reconciliation')
        self.assertTrue((job / 'runtime.json').exists())

    def test_live_and_completed_workers_are_untouched(self):
        campaign, job = self.fixture()
        self.assertFalse(self.recover(campaign, active=[job])['queued'])
        (job / 'last_message.txt').write_text('Done', encoding='utf-8')
        self.assertFalse(self.recover(campaign)['queued'])

    def test_invalid_request_and_unknown_failures_require_inspection(self):
        for message in ('Codex: Bad Request invalid_request_error 400', 'validation failed', 'unauthorized 502'):
            with self.subTest(message=message):
                campaign, job = self.fixture(message)
                self.assertFalse(self.recover(campaign)['queued'])
                self.assertTrue((job / 'runtime.json').exists())

    def test_peer_jobs_are_never_retried(self):
        campaign, job = self.fixture()
        peer = campaign / 'peer_jobs/reviewer'
        peer.parent.mkdir()
        job.rename(peer)
        self.assertFalse(self.recover(campaign)['queued'])
        self.assertTrue((peer / 'runtime.json').exists())


if __name__ == '__main__':
    unittest.main()
