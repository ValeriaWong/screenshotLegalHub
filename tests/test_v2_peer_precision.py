"""Independent boundary checks; all build mutations stay in TemporaryDirectory."""
import ast
import copy
import hashlib
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from tools import v2_peer_round as p
from tools import render_v2_round2 as renderer

REPO = Path(__file__).resolve().parents[1]


def source_fixture():
    text = '甲：请还款。'
    return dict(id='fixture', case_no='测试案号', cause='测试', text=text,
                paragraphs=[dict(id='p1', char_start=0, char_end=len(text))])


def candidate_fixture(stamps=(None,), platform='WeChat'):
    ref = dict(source_id='p1', source_end_id='p1', char_start=2,
               char_end=6, quote='请还款。')
    messages = [dict(id='m'+str(i+1), conversation_id='c1', sender_id='a',
                     kind='text', text='请还款。', timestamp=stamp,
                     origin_type='verbatim_quote', source_refs=[copy.deepcopy(ref)])
                for i, stamp in enumerate(stamps)]
    return dict(platform=platform, participants=[dict(id='a', name='甲'),dict(id='b', name='乙')],
                conversations=[dict(id='c1', participant_ids=['a','b'], viewer_id='b', title='通信')],
                messages=messages, facts=[], questions=[
                    dict(id='q1',question='有何请求？',answer='请还款。',message_ids=['m1']),
                    dict(id='q2',question='能否推定履行？',answer='不能。',message_ids=['m1'])])


class PrecisionTests(unittest.TestCase):
    def check(self, stamps, basis=None):
        raw=candidate_fixture(stamps)
        if basis:
            for message,value in zip(raw['messages'],basis):
                if value is not None:message['minute_basis']=value
        for message in raw['messages']:
            if message.get('timestamp') and len(message['timestamp'])>10 and 'minute_basis' not in message:
                message['minute_basis']='source_minute'
        return p.normalize_peer(raw,source_fixture())

    def test_same_day_coarse_between_exact_minutes_is_feasible(self):
        _, errors=self.check(['2024-08-06T10:00','2024-08-06','2024-08-06T11:00'])
        self.assertEqual(errors,[])

    def test_exact_reversal_rejected(self):
        _, errors=self.check(['2024-08-06T11:00','2024-08-06T10:00'])
        self.assertTrue(any('chronology inconsistent' in e for e in errors),errors)

    def test_coarse_message_does_not_reset_exact_lower_bound(self):
        _, errors=self.check(['2024-08-06T11:00','2024-08-06','2024-08-06T10:00'])
        self.assertTrue(any('m3: chronology inconsistent' in e for e in errors),errors)

    def test_cross_day_coarse_reversal_rejected(self):
        _, errors=self.check(['2024-08-07','2024-08-06'])
        self.assertTrue(any('chronology inconsistent' in e for e in errors),errors)

    def test_independent_conversations_do_not_share_cursor(self):
        raw=candidate_fixture(['2024-08-07','2024-08-06'])
        raw['conversations'].append(dict(id='c2',participant_ids=['a','b'],viewer_id='b'))
        raw['messages'][1]['conversation_id']='c2'
        self.assertEqual(p.normalize_peer(raw,source_fixture())[1],[])

    def test_unknown_minute_aliases_and_day_only_are_canonical_and_nonmutating(self):
        for basis in [None,'not_stated','unknown','source_day_only']:
            with self.subTest(basis=basis):
                raw=candidate_fixture(['2024-08-06'])
                if basis:raw['messages'][0]['minute_basis']=basis
                before=copy.deepcopy(raw)
                case,errors=p.normalize_peer(raw,source_fixture())
                self.assertEqual(errors,[])
                self.assertEqual(case['messages'][0]['minute_basis'],'not_visible')
                self.assertEqual(raw,before)
                fragment=renderer.message_html(case['messages'][0],case['conversations'][0],
                    {x['id']:x for x in case['participants']},None,'wechat')
                # The inline bubble clock is hidden by existing WeChat CSS; the visible stamp must omit midnight.
                stamp=fragment.split('<div class="stamp">',1)[1].split('</div>',1)[0]
                self.assertNotIn('00:00',stamp)
                self.assertIn('.bubble .time{display:none}',renderer.CSS)

    def test_non_wechat_platform_is_preserved_as_neutral_medium(self):
        for platform,medium in [('DingTalk','钉钉聊天转述'),('SMS','短信'),('unknown_chat','通信（平台未载明）'),('WhatsApp','WhatsApp')]:
            with self.subTest(platform=platform):
                case,errors=p.normalize_peer(candidate_fixture(platform=platform),source_fixture())
                self.assertEqual(errors,[])
                self.assertEqual(case['platform'],'communication_excerpt')
                self.assertEqual(case['source_medium'],medium)

    def test_mixed_timezone_and_local_precision_rejected_without_exception(self):
        _,errors=self.check(['2024-08-06T10:00+08:00','2024-08-06'])
        self.assertTrue(any('mixed timezone-aware and local' in e for e in errors),errors)

    def test_timezone_aware_day_interval_and_exact_reversal(self):
        _,errors=self.check(['2024-08-06T10:00+08:00','2024-08-06T00:00+08:00','2024-08-06T11:00+08:00'],
                            ['source_minute','not_visible','source_minute'])
        self.assertEqual(errors,[])
        _,errors=self.check(['2024-08-06T11:00+08:00','2024-08-06T10:00+08:00'])
        self.assertTrue(any('chronology inconsistent' in e for e in errors),errors)

    def test_unproven_minute_is_never_treated_as_source_minute(self):
        for basis in [None,'synthetic_layout_only']:
            raw=candidate_fixture(['2024-08-06T10:19'])
            if basis:raw['messages'][0]['minute_basis']=basis
            case,errors=p.normalize_peer(raw,source_fixture())
            self.assertEqual(errors,[]);self.assertEqual(case['messages'][0]['minute_basis'],'not_visible')
            fragment=renderer.message_html(case['messages'][0],case['conversations'][0],
                {x['id']:x for x in case['participants']},None,'wechat')
            stamp=fragment.split('<div class="stamp">',1)[1].split('</div>',1)[0]
            self.assertNotIn('10:19',stamp)

    def test_invalid_timestamp_is_still_rejected(self):
        _,errors=self.check(['2024-99-45'])
        self.assertTrue(any('invalid timestamp' in e for e in errors),errors)


class RenderingBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.directory=Path(self.temp.name)
    def tearDown(self):self.temp.cleanup()
    def test_unknown_medium_cannot_silently_use_wechat(self):
        p.save(self.directory/'case.json',candidate_fixture(platform='unknown_chat'))
        with patch.object(p,'render_authored_case') as render:
            with self.assertRaisesRegex(ValueError,'neutral transcript'):
                p.render_current_case(None,self.directory)
            render.assert_not_called()
    def test_neutral_css_is_present_during_render_and_restored(self):
        raw=candidate_fixture(platform='SMS');case,errors=p.normalize_peer(raw,source_fixture())
        self.assertEqual(errors,[]);p.save(self.directory/'case.json',case)
        original_css=renderer.CSS
        def capture(browser,directory):
            self.assertIn('短信 · 通信摘录重建（非原界面）',renderer.CSS)
            self.assertIn('.chevron,.dots{visibility:hidden}',renderer.CSS)
            return 'rendered'
        with patch.object(renderer,'render_case',side_effect=capture):
            self.assertEqual(p.render_current_case(None,self.directory),'rendered')
        self.assertEqual(renderer.CSS,original_css)
    def test_voice_paraphrase_and_partial_day_are_visible_without_synthetic_minute(self):
        case,_=p.normalize_peer(candidate_fixture(),source_fixture())
        m=case['messages'][0];m.update(origin_type='judgment_paraphrase',
            original_medium='voice_transcription_in_judgment',date_basis='source_part_of_day',
            time_label='2024年8月6日上午',minute_basis='not_visible')
        p.save(self.directory/'case.json',case);original=renderer.message_html
        def capture(browser,directory):
            return renderer.message_html(m,case['conversations'][0],{x['id']:x for x in case['participants']},None,'wechat')
        with patch.object(p,'render_authored_case',side_effect=capture):fragment=p.render_current_case(None,self.directory)
        self.assertIn('语音内容转述',fragment);self.assertNotIn('语音转文字',fragment)
        self.assertIn('2024年8月6日上午',fragment);self.assertNotIn('00:00',fragment)
        self.assertIs(renderer.message_html,original)
    def test_non_wechat_transfer_footer_has_no_invented_wechat_brand(self):
        raw=candidate_fixture(platform='SMS');raw['messages'][0].update(kind='transfer',
            transfer=dict(amount=100,currency='CNY',receipt_status='not_reconstructed'))
        case,errors=p.normalize_peer(raw,source_fixture());self.assertEqual(errors,[])
        p.save(self.directory/'case.json',case)
        def capture(browser,directory):
            return renderer.message_html(case['messages'][0],case['conversations'][0],
                {x['id']:x for x in case['participants']},None,'wechat')
        with patch.object(p,'render_authored_case',side_effect=capture):fragment=p.render_current_case(None,self.directory)
        self.assertNotIn('微信转账',fragment);self.assertIn('转账记录',fragment)

    def test_neutral_footer_adapter_preserves_actual_message_words(self):
        raw=candidate_fixture(platform='SMS');raw['messages'][0]['text']='请勿使用微信转账'
        case,_=p.normalize_peer(raw,source_fixture());p.save(self.directory/'case.json',case)
        def capture(browser,directory):
            return renderer.message_html(case['messages'][0],case['conversations'][0],
                {x['id']:x for x in case['participants']},None,'wechat')
        with patch.object(p,'render_authored_case',side_effect=capture):fragment=p.render_current_case(None,self.directory)
        self.assertIn('请勿使用微信转账',fragment)
        self.assertNotIn('请勿使用转账记录',fragment)

    def test_renderer_wrapper_restored_on_exception(self):
        p.save(self.directory/'case.json',candidate_fixture());original=renderer.message_html
        with patch.object(p,'render_authored_case',side_effect=RuntimeError('render failure')):
            with self.assertRaises(RuntimeError):p.render_current_case(None,self.directory)
        self.assertIs(renderer.message_html,original)


class SchemaMappingTests(unittest.TestCase):
    def test_mapping_is_structure_only_and_records_exact_quote_span(self):
        # Extract definitions without executing collector loops or mutating real decisions.
        tree=ast.parse((REPO/'datasets/v2.0.0/round_006/prepare_decisions.py').read_text(encoding='utf8'))
        definitions=ast.Module(body=[node for node in tree.body if isinstance(node,ast.FunctionDef)],type_ignores=[])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'round006';source=source_fixture()
            p.save(root/'source.json',source);p.save(root/'review.json',dict(reason='test'))
            raw=candidate_fixture(platform='DingTalk');raw['messages'][0].update(kind='voice',origin_type='judgment_voice_transcript')
            raw['messages'][0]['source_refs']=[dict(source_id='p1',source_end_id='p1',char_start=0,char_end=6,quote=source['text'])]
            p.save(root/'candidate.json',raw)
            ns=dict(copy=copy,ROOT=root,OUT=out,parent={87:dict(source_path='source.json')},
                    read=p.read,save=p.save,normalize=p.normalize_peer,decisions={})
            exec(compile(definitions,'prepare_definitions','exec'),ns)
            ns['accept'](87,root/'review.json',root/'candidate.json','revise')
            body=p.read(out/'root_accept/q6_0087/candidate.json');m=body['messages'][0]
            self.assertEqual(m['text'],raw['messages'][0]['text'])
            self.assertEqual(m['sender_id'],'a');self.assertIsNone(m['timestamp'])
            self.assertEqual(m['kind'],'text');self.assertEqual(m['origin_type'],'judgment_paraphrase')
            self.assertEqual(m['original_medium'],'voice_transcription_in_judgment')
            self.assertEqual(body['source_medium'],'钉钉聊天转述')
            self.assertEqual(p.read(root/'candidate.json'),raw)
            self.assertEqual(ns['decisions'][87]['action'],'revise')
    def test_verbatim_nested_unique_anchor_gets_exact_span(self):
        tree=ast.parse((REPO/'datasets/v2.0.0/round_006/prepare_decisions.py').read_text(encoding='utf8'))
        definitions=ast.Module(body=[n for n in tree.body if isinstance(n,ast.FunctionDef)],type_ignores=[])
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);source=source_fixture();p.save(root/'source.json',source);p.save(root/'review.json',dict(reason='test'))
            raw=candidate_fixture();raw['messages'][0]['source_refs']=[dict(source_id='p1',source_end_id='p1',char_start=0,char_end=6,quote=source['text'])]
            p.save(root/'candidate.json',raw)
            ns=dict(copy=copy,ROOT=root,OUT=root/'out',parent={1:dict(source_path='source.json')},read=p.read,save=p.save,normalize=p.normalize_peer,decisions={})
            exec(compile(definitions,'prepare_definitions','exec'),ns);ns['accept'](1,root/'review.json',root/'candidate.json','revise')
            refs=p.read(root/'out/root_accept/q6_0001/candidate.json')['messages'][0]['source_refs']
            self.assertEqual(refs[-1]['quote'],'请还款。');self.assertEqual((refs[-1]['char_start'],refs[-1]['char_end']),(2,6))


class AssemblyBoundaryTests(unittest.TestCase):
    def test_auxiliary_remains_gap_and_changed_input_keeps_old_artifacts(self):
        class Browser:
            def __init__(self,*args):pass
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def call(self,*args):pass
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);out=root/'round006';parent=root/'round005';source=source_fixture()
            p.save(root/'source.json',source);digest=hashlib.sha256(source['text'].encode()).hexdigest()
            p.save(root/'review.json',dict(full_judgment_read=True,source_chars=len(source['text']),source_paragraphs=1,source_hash=digest))
            p.save(root/'candidate.json',candidate_fixture(platform='SMS'))
            p.save(parent/'execution_state.json',dict(records=[dict(source_index=1,source_path='source.json',judgment_text_sha256=digest,new_sample_status='source_gap')]))
            p.save(out/'decisions.json',dict(records=[dict(source_index=1,review_path='review.json',candidate_path='candidate.json',action='auxiliary')]))
            old=out/'zh/q6_0001';p.save(old/'provenance.json',dict(authored_input_sha256='old-input'))
            (old/'old-image.png').write_bytes(b'keep exactly')
            old_hash={x.name:p.sha(x) for x in old.iterdir()}
            def render(browser,directory):
                case=p.read(directory/'case.json');self.assertEqual(case['platform'],'communication_excerpt');self.assertEqual(case['source_medium'],'短信')
                (directory/'shot.png').write_bytes(b'isolated fake screenshot')
                p.save(directory/'render.json',dict(images=[dict(path='shot.png',message_ids=['m1'],boxes=[])]))
            original_renderer_root=renderer.ROOT
            with patch.multiple(p,ROOT=root,OUT=out,PARENT=parent),patch.object(renderer,'Browser',Browser),patch.object(p,'render_current_case',side_effect=render):
                try:p.build()
                finally:renderer.ROOT=original_renderer_root
            row=p.read(out/'execution_state.json')['records'][0];summary=p.read(out/'summary.json')
            self.assertEqual(row['new_sample_status'],'source_gap');self.assertTrue(row['auxiliary_only'])
            self.assertFalse(summary['all_samples_generated']);self.assertTrue(summary['all_records_accounted_for'])
            self.assertTrue(Path(row['artifact_directory']).name.startswith('q6_0001_'))
            self.assertNotEqual(root/row['artifact_directory'],old)
            self.assertEqual(old_hash,{x.name:p.sha(x) for x in old.iterdir()})
            tasks=p.read(root/row['artifact_directory']/'tasks.json')
            for task in tasks:self.assertFalse(set(task)&{'answer','label','source_refs','reasoning','missing_evidence'})

if __name__=='__main__':unittest.main()
