"""Resume the frozen 200-source V2 queue without changing any earlier round."""
import argparse, copy, hashlib, html, json, sys
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_cause_batch import normalize
from PIL import Image
OUT=ROOT/'datasets/v2.0.0/round_005'
def read(p):return json.loads(p.read_text(encoding='utf-8'))
def save(p,v):p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def copy_file(src,dst):
    dst.parent.mkdir(parents=True,exist_ok=True)
    if dst.exists():
        if sha(src)!=sha(dst):raise ValueError('Refusing to overwrite '+str(dst))
    else:dst.write_bytes(src.read_bytes())
def replay():
    state=read(OUT/'execution_state.json')
    for r in state['records']:
        if not r['prior_sample'] or r['new_sample_status']!='pending':continue
        prior=ROOT/r['prior_sample'];d=OUT/'zh'/f'q5_{r["source_index"]:04d}';d.mkdir(parents=True,exist_ok=True)
        source=read(prior/'source.json');assert source['judgment_text_sha256']==r['judgment_text_sha256']
        assert hashlib.sha256(source['text'].encode()).hexdigest()==r['judgment_text_sha256']
        case=read(prior/'case.json');rendering=read(prior/'render.json')
        save(d/'source.json',source);save(d/'case.json',case);copy_file(prior/'judgment.txt',d/'judgment.txt')
        save(d/'render.json',rendering)
        inherited=[]
        for name in ['source.reading.json','direct.draft.json','direct.revised.json','codex.review.json','root.review.json','claims.review.json']:
            if (prior/name).exists():copy_file(prior/name,d/'inherited_authoring'/name);inherited.append(name)
        for image in rendering['images']:copy_file(prior/image['path'],d/image['path'])
        save(d/'provenance.json',dict(kind='replayed_prior_chat_candidate',prior_directory=r['prior_sample'],
            prior_case_sha256=sha(prior/'case.json'),prior_render_sha256=sha(prior/'render.json'),
            source_queue_index=r['source_index'],new_judgment=False,new_dialogue=False,new_full_read_claimed=False,
            inherited_authoring=inherited,professional_review=False))
        tasks=[]
        for q in case['questions']:
            mids=set(q.get('message_ids',[]))
            shots=[p for p in rendering['images'] if q.get('whole_case_required') or mids&set(p['message_ids'])]
            tasks.append(dict(task_id=f'q5_{r["source_index"]:04d}.'+q['id'],question=q['question'],
                instruction='仅按提供的合成研究截图及明确给定背景回答；区分陈述与实际发生，不能由文件名推定身份。',
                images=[dict(file=p['path'],sha256=sha(d/p['path'])) for p in shots],
                scope='inherited_candidate_question_pending_new_semantic_review'))
        save(d/'tasks.json',tasks);save(d/'answers.reviewer_only.json',case['questions'])
        page='<!doctype html><meta charset="utf-8"><style>body{max-width:1200px;margin:30px auto;font:16px sans-serif}img{width:320px;vertical-align:top}</style><h1>'+html.escape(source['case_no'])+'</h1><p>既有聊天复用候选；来源与作者记录继承，未声称本轮新写或人工认证。</p><a href="judgment.txt">全文</a>'
        page+=''.join('<section><h2>'+html.escape(t['question'])+'</h2>'+''.join('<img src="'+im['file']+'">' for im in t['images'])+'</section>' for t in tasks)
        (d/'index.html').write_text(page,encoding='utf-8')
        r.update(new_sample_status='assembled',artifact_directory=d.relative_to(ROOT).as_posix(),generation_kind='replayed_prior_chat',new_dialogue=False)
        save(OUT/'execution_state.json',state)
        print(f'assembled {r["source_index"]}',flush=True)
    report()
def verify():
    state=read(OUT/'execution_state.json');counts=Counter();failures=[]
    for r in state['records']:
        if r['new_sample_status'] not in ['assembled','verified']:continue
        try:
            d=ROOT/r['artifact_directory'];source=read(d/'source.json');case=read(d/'case.json');rendering=read(d/'render.json')
            assert hashlib.sha256(source['text'].encode()).hexdigest()==r['judgment_text_sha256']
            assert (d/'judgment.txt').read_text(encoding='utf-8')==source['text']
            _,errors=normalize(case,source);assert not errors,errors
            covered=set()
            for shot in rendering['images']:
                with Image.open(d/shot['path']) as image:assert image.size==(860,1864)
                for box in shot['boxes']:
                    x,y,w,h=box['bbox_pixels'];assert 0<=x<x+w<=860 and 0<=y<y+h<=1864
                covered.update(shot['message_ids']);counts['images']+=1
            assert covered=={m['id'] for m in case['messages']}
            for task in read(d/'tasks.json'):
                assert not set(task)&{'answer','label','source_refs','reasoning','missing_evidence'}
                for im in task['images']:assert sha(d/im['file'])==im['sha256']
                counts['questions']+=1
            counts['messages']+=len(case['messages']);counts['cases']+=1
            r['new_sample_status']='verified'
        except Exception as error:
            r['new_sample_status']='verification_failed';failures.append(dict(source_index=r['source_index'],error=str(error)))
    save(OUT/'execution_state.json',state);save(OUT/'verification.json',dict(counts=counts,failures=failures,rendered_case_ids=[Path(r['artifact_directory']).name for r in state['records'] if r['new_sample_status']=='verified'],
        every_queued_source_generated=counts['cases']==len(state['records']),professional_gold=False))
    report();print(json.dumps(dict(counts=counts,failures=failures),ensure_ascii=False))
    return 1 if failures else 0
def report():
    state=read(OUT/'execution_state.json');phases=Counter(r['new_sample_status'] for r in state['records'])
    summary=dict(total_queue=len(state['records']),phases=phases,new_api_calls=0,
        complete=phases['verified']==len(state['records']),all_samples_generated=phases['verified']==len(state['records']),
        all_records_accounted_for=phases['verified']+phases['source_gap']==len(state['records']),
        source_gaps=phases['source_gap'],newly_authored_chats=sum(r.get('generation_kind')=='new_chat' and r['new_sample_status']=='verified' for r in state['records']),
        replayed_prior_chats=sum(r.get('generation_kind')=='replayed_prior_chat' and r['new_sample_status']=='verified' for r in state['records']),professional_gold=False)
    save(OUT/'summary.json',summary)
    page='<!doctype html><meta charset="utf-8"><style>body{max-width:1100px;margin:30px auto;font:16px/1.8 sans-serif}td{border-bottom:1px solid #ddd;padding:8px}</style><h1>V2第五轮：200项执行清单</h1><p>'+html.escape(json.dumps(summary,ensure_ascii=False))+'</p><table><tr><th>来源序号</th><th>历史标签</th><th>状态</th><th>样本</th></tr>'
    for r in state['records']:
        link='<a href="'+Path(r['artifact_directory']).relative_to(OUT.relative_to(ROOT)).as_posix()+'/index.html">查看</a>' if r.get('artifact_directory') else ('来源缺口' if r['new_sample_status']=='source_gap' else '待生成')
        page+='<tr><td>'+str(r['source_index'])+'</td><td>'+html.escape(r['cause'].split('>')[-1])+'</td><td>'+r['new_sample_status']+'</td><td>'+link+'</td></tr>'
    (OUT/'index.html').write_text(page+'</table>',encoding='utf-8')

def render_authored_case(browser,directory):
    """Use a visibly neutral transcript for sources that do not identify WeChat."""
    import tools.render_v2_round2 as renderer
    case=read(directory/'case.json');medium=case.get('source_medium')
    original=renderer.CSS
    if medium:
        label=medium+' · 通信摘录重建（非原界面）'
        renderer.CSS+='''
.phone{background:#f3f5f8}.header{background:#e8edf4}.bubble,.out .bubble{background:#fff;border:1px solid #cdd6e2}.bubble:before{display:none}.input>*{display:none}.input:before{content:"公开通信片段 · 合成研究样本";font-size:13px;color:#667085}.footnote{font-size:0}.footnote:after{content:'''+json.dumps(label,ensure_ascii=False)+''';font-size:10px;color:#555}.chevron,.dots{visibility:hidden}'''
    try:return renderer.render_case(browser,directory)
    finally:renderer.CSS=original

def authored():
    from tools.render_v2_round2 import Browser,render_case
    import tools.render_v2_round2 as rendering_module
    rendering_module.ROOT=OUT/'work'
    state=read(OUT/'execution_state.json')
    pending=[r for r in state['records'] if r['new_sample_status']=='pending' and (OUT/'authoring/root'/f'q5_{r["source_index"]:04d}'/'direct.revised.json').exists()]
    if not pending:return
    with Browser('round005-authoring') as browser:
        browser.call('Network.enable');browser.call('Network.setBlockedURLs',{'urls':['http://*','https://*']})
        for r in pending:
            source=read(ROOT/r['source_path']);folder=OUT/'authoring/root'/f'q5_{r["source_index"]:04d}'
            reading=read(folder/'source.reading.json');assert reading['full_judgment_read'] and reading['source_chars']==len(source['text'])
            case,errors=normalize(read(folder/'direct.revised.json'),source);assert not errors,errors
            case.update(id=f'q5_{r["source_index"]:04d}',author='root assistant direct source reading and writing; exact model build not exposed',status='author_candidate_pending_independent_review')
            raw=read(folder/'direct.revised.json')
            if raw.get('source_medium'):case.update(platform='communication_excerpt',source_medium=raw['source_medium'])
            d=OUT/'zh'/f'q5_{r["source_index"]:04d}';d.mkdir(parents=True,exist_ok=True)
            save(d/'case.json',case);save(d/'source.json',source);(d/'judgment.txt').write_text(source['text'],encoding='utf-8')
            for file in folder.iterdir():
                if file.is_file():copy_file(file,d/'authoring'/file.name)
            render_authored_case(browser,d);rendering=read(d/'render.json');tasks=[]
            for q in case['questions']:
                mids=set(q['message_ids']);shots=[p for p in rendering['images'] if q.get('whole_case_required') or mids&set(p['message_ids'])]
                tasks.append(dict(task_id=f'q5_{r["source_index"]:04d}.'+q['id'],question=q['question'],instruction='仅按合成研究截图回答，界面不等于原始载体，陈述和实际发生分开。',images=[dict(file=p['path'],sha256=sha(d/p['path'])) for p in shots]))
            save(d/'tasks.json',tasks);save(d/'answers.reviewer_only.json',case['questions'])
            save(d/'provenance.json',dict(kind='new_source_grounded_chat_candidate',source_path=r['source_path'],source_text_sha256=r['judgment_text_sha256'],new_dialogue=True,new_external_judgment=False,professional_review=False,author='root_assistant',independent_reviewer=False))
            page='<!doctype html><meta charset="utf-8"><style>body{max-width:1100px;margin:30px auto;font:16px/1.8 sans-serif}img{width:340px}</style><h1>'+html.escape(source['case_no'])+'</h1><p>合成界面重建，来源原文与作者复核见JSON，不是专业金标。</p><a href="judgment.txt">判决全文</a>'
            page+=''.join('<h2>'+html.escape(t['question'])+'</h2>'+''.join('<img src="'+im['file']+'">' for im in t['images']) for t in tasks)
            (d/'index.html').write_text(page,encoding='utf-8')
            r.update(new_sample_status='assembled',artifact_directory=d.relative_to(ROOT).as_posix(),generation_kind='new_chat',new_dialogue=True,source_reading=reading)
            save(OUT/'execution_state.json',state);print(f'new chat {r["source_index"]}',flush=True)
    report()

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['replay','verify','report','authored']);args=parser.parse_args()
    if args.command=='authored':authored()
    elif args.command=='replay':replay()
    elif args.command=='verify':sys.exit(verify())
    else:report()
