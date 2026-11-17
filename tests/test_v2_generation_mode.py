import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock
from types import SimpleNamespace

from tools import v2_library_expansion as library
from tools import v2_library_authoring as author
from tools import v2_library_runner as runner
from tools import v2_fact_constrained as facts


class GenerationOnlyTests(unittest.TestCase):
    def temporary(self):
        base=library.ROOT/'.runtime';base.mkdir(exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=base,prefix='generation-mode-test-')
        self.addCleanup(temp.cleanup)
        return Path(temp.name)

    def test_empty_output_file_keeps_live_worker_active_and_blocks_extra_launch(self):
        root=self.temporary();job=root/'jobs/live'
        library.save(job/'runtime.json',{'pid':12345})
        library.save(root/'jobs/waiting/assignment.json',{'records':[]})
        (job/'last_message.txt').write_text('')
        with patch.object(author,'OUT',root),patch.object(author.subprocess,'run',return_value=SimpleNamespace(stdout='"codex.exe","12345"')):
            self.assertEqual(author.active_jobs(),[job])
            self.assertFalse(author.job_finished(job))
            self.assertFalse(facts.job_finished(job))
        with patch.object(author,'OUT',root),patch.object(author,'active_jobs',return_value=[job]*2),patch.object(author.shutil,'which',return_value='codex'),patch.object(author.subprocess,'Popen',side_effect=AssertionError('Worker budget is full')):
            author.launch_group('jobs')
        (job/'last_message.txt').write_text('Complete')
        self.assertTrue(author.job_finished(job))

    def test_two_author_limit_is_shared_across_tracks(self):
        root=self.temporary()
        for name in ['a','b']:
            library.save(root/'jobs'/name/'assignment.json',{'records':[]})
            (root/'jobs'/name/'prompt.txt').write_text('fixture',encoding='utf-8')
        process=MagicMock();process.pid=12345
        with patch.object(author,'OUT',root),patch.object(author,'active_jobs',return_value=[facts.OUT/'jobs/live_fact_author']),patch.object(author.shutil,'which',return_value='codex'),patch.object(author.subprocess,'Popen',return_value=process) as launch:
            author.launch_group('jobs')
            launch.assert_called_once()
        self.assertTrue((root/'jobs/a/runtime.json').exists())
        self.assertFalse((root/'jobs/b/runtime.json').exists())

    def test_config_cannot_raise_author_limit_above_two(self):
        root=self.temporary()
        with patch.object(author,'OUT',root):
            self.assertEqual(author.worker_limit(),2)
            library.save(root/'campaign.config.json',{'max_concurrent_authors':3})
            with self.assertRaisesRegex(AssertionError,'concurrency'):
                author.worker_limit()

    def test_dead_worker_with_empty_output_cannot_be_ingested_as_finished(self):
        root=self.temporary();job=root/'jobs/dead'
        library.save(job/'assignment.json',{'records':[]})
        library.save(job/'runtime.json',{'pid':12345})
        (job/'last_message.txt').write_text('')
        with patch.object(runner,'jobs',return_value=[job/'assignment.json']):
            with self.assertRaisesRegex(RuntimeError,'without completion marker'):
                runner.check_dead_jobs([],include_reviews=False)

    def test_fact_worker_with_empty_output_stays_running_without_collection(self):
        root=self.temporary();job=root/'jobs/live'
        library.save(job/'assignment.json',{'records':[]})
        library.save(job/'runtime.json',{'pid':12345})
        (job/'last_message.txt').write_text('')
        with patch.object(facts,'OUT',root),patch.object(author,'active_jobs',return_value=[job]),patch.object(facts,'collect',side_effect=AssertionError('Live author must finish first')):
            self.assertTrue(facts.advance_generation())
            self.assertEqual(library.read(root/'automation.json')['phase'],'generation_only_running')

    def test_legacy_review_default_and_explicit_disable(self):
        root=self.temporary()
        with patch.object(library,'OUT',root):
            self.assertTrue(library.review_enabled())
            library.save(root/'campaign.config.json',{'independent_review_enabled':False})
            self.assertFalse(library.review_enabled())

    def test_review_launch_is_blocked_for_both_tracks(self):
        with patch.object(author,'review_enabled',return_value=False),patch.object(author.shutil,'which',side_effect=AssertionError('No CLI discovery for reviews')):
            author.launch_group('peer_jobs')
            author.launch_group(str(facts.OUT/'peer_jobs'))

    def test_active_generation_never_launches_peer_workers(self):
        with patch.object(author,'active_jobs',return_value=[runner.OUT/'jobs/active_writer']),patch.object(runner,'jobs',return_value=[]),patch.object(runner,'check_dead_jobs') as dead,patch.object(author,'launch') as launch,patch.object(author,'peer_launch',side_effect=AssertionError('No peer launch')),patch.object(runner,'emit') as emit,patch.object(runner,'unassigned',return_value=12):
            self.assertTrue(runner.coordinate_generation(10,False))
            dead.assert_called_once_with([runner.OUT/'jobs/active_writer'],include_reviews=False)
            launch.assert_called_once()
            self.assertFalse(emit.call_args.kwargs['independent_review_enabled'])

    def test_new_source_batch_does_not_wait_for_review_backlog(self):
        root=self.temporary();job=root/'jobs/done'
        library.save(job/'assignment.json',{'records':[{'document_id':'zh_1'}]})
        library.save(job/'runtime.json',{'pid':1});(job/'last_message.txt').write_text('done')
        library.save(root/'authoring_status.json',{'records':[{'id':'zh_1'}],'errors':[]})
        library.save(root/'verification.json',{'passed':True})
        with patch.object(runner,'OUT',root),patch.object(runner,'jobs',return_value=[job/'assignment.json']),patch.object(author,'active_jobs',return_value=[]),patch.object(author,'collect'),patch.object(author,'render'),patch.object(author,'verify'),patch.object(author,'report'),patch.object(author,'bundle'),patch.object(author,'peer_launch',side_effect=AssertionError('Review disabled')),patch.object(author,'peer_assign',side_effect=AssertionError('Review disabled')),patch.object(author,'assign') as assign,patch.object(author,'launch') as launch,patch.object(runner,'emit'),patch.object(runner,'unassigned',return_value=100):
            self.assertTrue(runner.coordinate_generation(10,False))
            assign.assert_called_once_with(10);launch.assert_called_once()

    def test_paused_fact_review_is_not_treated_as_dead_author(self):
        root=self.temporary()
        library.save(root/'peer_jobs/paused/runtime.json',{'pid':-1})
        library.save(root/'peer_jobs/paused/assignment.json',{'records':[]})
        library.save(root/'automation.json',{'author_jobs_ingested':[],'peer_jobs_ingested':[]})
        with patch.object(facts,'OUT',root),patch.object(author,'active_jobs',return_value=[]),patch.object(facts,'assign',return_value=0),patch.object(facts,'peer_assign',side_effect=AssertionError('No review assignment')),patch.object(facts,'peer_apply',side_effect=AssertionError('No review apply')):
            self.assertFalse(facts.advance_generation())
            self.assertEqual(library.read(root/'automation.json')['phase'],'generation_only_waiting_for_sources')

    def test_fact_generation_can_use_author_only_gap_with_explicit_label(self):
        root=self.temporary();parent=root/'source';out=root/'fact'
        records=[];catalog=[]
        for ident,language in [('zh_a','zh'),('en_b','en')]:
            records.append({'id':ident,'decision':'defer','authoring_path':'authoring/writer/'+ident})
            catalog.append({'document_id':ident,'causes':['A'] if language=='zh' else [],'source_chars':100,'primary_cause':'A' if language=='zh' else None})
            library.save(parent/'sources'/ident/'source.json',{'id':ident,'cause':'A','text':'Fixture only'})
        library.save(parent/'authoring_status.json',{'records':records})
        library.save(parent/'source_catalog.json',{'records':catalog})
        library.save(out/'authorization.json',{'authorized':True})
        with patch.object(facts,'OUT',out),patch.object(facts,'PARENT',parent),patch.object(facts,'review_enabled',return_value=False),patch.object(facts,'covered_source_ids',return_value=set()):
            self.assertEqual(facts.assign(3),2)
        assigned=[r for p in (out/'jobs').glob('*/assignment.json') for r in library.read(p)['records']]
        self.assertTrue(all(r['source_screening_status']=='author_only_pending_independent_review' for r in assigned))
        self.assertTrue(all('source_gap_decision' not in r for r in assigned))


if __name__=='__main__':unittest.main()
