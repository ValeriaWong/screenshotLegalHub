import contextlib,io,json,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
from PIL import Image
from tools import v2_full_queue as q

class FullQueueTests(unittest.TestCase):
    def setUp(self):
        runtime=q.ROOT/'.runtime';runtime.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=runtime,prefix='v2-full-queue-test-');self.out=Path(self.tmp.name)
        self.patcher=patch.object(q,'OUT',self.out);self.patcher.start();self.addCleanup(self.patcher.stop);self.addCleanup(self.tmp.cleanup)
    def fixture(self):
        text='甲发消息说：请还款。';start=text.index('请还款。');ref=dict(source_id='p1',quote='请还款。',char_start=start,char_end=len(text))
        source=dict(id='q5_0001',case_no='测试',cause='测试',text=text,paragraphs=[dict(id='p1',char_start=0,char_end=len(text),text=text)])
        case=dict(participants=[dict(id='a',name='甲'),dict(id='b',name='乙')],conversations=[dict(id='c1',viewer_id='a',participant_ids=['a','b'])],messages=[dict(id='m1',conversation_id='c1',sender_id='a',kind='text',text='请还款。',source_refs=[ref],origin_type='verbatim_quote')],questions=[dict(id='q1',question='说了什么？',answer='请还款。',message_ids=['m1']),dict(id='q2',question='还款了吗？',answer='未知',message_ids=['m1'])])
        d=self.out/'zh/q5_0001';q.save(d/'source.json',source);q.save(d/'case.json',case);(d/'judgment.txt').write_text(text,encoding='utf8')
        (d/'screenshots').mkdir();Image.new('RGB',(860,1864),'white').save(d/'screenshots/c1_01.png')
        q.save(d/'render.json',dict(images=[dict(path='screenshots/c1_01.png',message_ids=['m1'],boxes=[dict(bbox_pixels=[0,0,100,100])])]))
        q.save(d/'tasks.json',[dict(task_id='x',question='说了什么？',images=[dict(file='screenshots/c1_01.png',sha256=q.sha(d/'screenshots/c1_01.png'))])])
        row=dict(source_index=1,cause='测试',new_sample_status='assembled',artifact_directory=d.relative_to(q.ROOT).as_posix(),judgment_text_sha256=q.hashlib.sha256(text.encode()).hexdigest(),generation_kind='new_chat')
        q.save(self.out/'execution_state.json',dict(records=[row]));return d
    def verify(self):
        with contextlib.redirect_stdout(io.StringIO()):return q.verify()
    def test_valid_fixture_and_completion(self):
        self.fixture();self.assertEqual(self.verify(),0);self.assertTrue(q.read(self.out/'summary.json')['complete'])
    def test_corrupted_source_hash_rejected(self):
        d=self.fixture();s=q.read(d/'source.json');s['text']+='伪造';q.save(d/'source.json',s);self.assertEqual(self.verify(),1)
    def test_corrupted_quote_coordinates_rejected(self):
        d=self.fixture();c=q.read(d/'case.json');c['messages'][0]['source_refs'][0]['char_start']=0;q.save(d/'case.json',c);self.assertEqual(self.verify(),1)
    def test_answer_leak_rejected(self):
        d=self.fixture();tasks=q.read(d/'tasks.json');tasks[0]['answer']='泄漏';q.save(d/'tasks.json',tasks);self.assertEqual(self.verify(),1)
    def test_image_hash_tamper_rejected(self):
        d=self.fixture();Image.new('RGB',(860,1864),'black').save(d/'screenshots/c1_01.png');self.assertEqual(self.verify(),1)
    def test_existing_different_file_not_overwritten(self):
        a=self.out/'a';b=self.out/'b';a.write_text('a');b.write_text('b')
        with self.assertRaises(ValueError):q.copy_file(a,b)
        self.assertEqual(b.read_text(),'b')
    def test_gap_accounting_is_not_generated_completion(self):
        q.save(self.out/'execution_state.json',dict(records=[dict(source_index=1,cause='测试',new_sample_status='source_gap')]))
        q.report();s=q.read(self.out/'summary.json');self.assertTrue(s['all_records_accounted_for']);self.assertFalse(s['all_samples_generated']);self.assertFalse(s['complete'])
    def test_neutral_renderer_restores_global_css_on_failure(self):
        import tools.render_v2_round2 as renderer
        q.save(self.out/'case.json',dict(source_medium='短信'));old=renderer.CSS
        with patch.object(renderer,'render_case',side_effect=RuntimeError('failure')):
            with self.assertRaises(RuntimeError):q.render_authored_case(None,self.out)
        self.assertEqual(renderer.CSS,old)

if __name__=='__main__':unittest.main()
