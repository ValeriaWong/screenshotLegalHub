"""Apply archived peer decisions without modifying the frozen parent cohort."""
import argparse,copy,hashlib,html,json,os,sys,re
from datetime import datetime,time
from collections import Counter
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from tools.v2_full_queue import read,save,sha,copy_file,normalize,render_authored_case
from PIL import Image
OUT=ROOT/'datasets/v2.0.0/round_006';PARENT=ROOT/'datasets/v2.0.0/round_005'

def normalize_peer(raw,source):
    """A disclosed day is a time interval, not a fabricated midnight event."""
    candidate=copy.deepcopy(raw)
    original_platform=candidate.get('platform')
    if original_platform not in [None,'WeChat','wechat'] and not candidate.get('source_medium'):
        candidate['source_medium']={'DingTalk':'钉钉聊天转述','unknown_chat':'通信（平台未载明）','SMS':'短信'}.get(original_platform,str(original_platform))
    for message in candidate.get('messages',[]):
        if message.get('minute_basis') in [None,'synthetic_layout_only','not_stated','unknown','source_day_only'] or len(str(message.get('timestamp') or ''))==10:
            message['minute_basis']='not_visible'
    normalized,errors=normalize(candidate,source)
    if candidate.get('source_medium'):normalized.update(platform='communication_excerpt',source_medium=candidate['source_medium'])
    cursor={};precision_errors=[];awareness={}
    for message in candidate.get('messages',[]):
        stamp=message.get('timestamp')
        if not stamp:continue
        try:moment=datetime.fromisoformat(stamp)
        except (ValueError,TypeError):continue # the legacy validator already reports invalid dates
        if message.get('minute_basis')=='not_visible' or len(stamp)==10:
            lower=datetime.combine(moment.date(),time.min,tzinfo=moment.tzinfo);upper=datetime.combine(moment.date(),time.max,tzinfo=moment.tzinfo)
        else:lower=upper=moment
        cid=message['conversation_id']
        aware=moment.tzinfo is not None
        if cid in awareness and awareness[cid]!=aware:
            precision_errors.append(message['id']+': mixed timezone-aware and local timestamps require explicit normalization');continue
        awareness[cid]=aware;earliest=max(lower,cursor.get(cid,lower))
        if earliest>upper:precision_errors.append(message['id']+': chronology inconsistent at disclosed precision')
        cursor[cid]=earliest
    errors=[e for e in errors if not e.endswith(': chronology reversed')]+precision_errors
    return normalized,errors

def validate_review(review,source):
    assert review['full_judgment_read'] is True,'Full source review required'
    assert review['source_chars']==len(source['text']),'Source character count mismatch'
    assert review['source_paragraphs']==len(source['paragraphs']),'Source paragraph count mismatch'
    digest=review.get('source_hash') or review.get('judgment_text_sha256') or review.get('source_text_sha256')
    assert digest==hashlib.sha256(source['text'].encode()).hexdigest(),'Reviewed source hash mismatch'

def visible_payload(case):
    return {key:case.get(key) for key in ['language','platform','source_medium','participants','conversations','messages']}

def verify_case(directory,expected):
    source=read(directory/'source.json');case=read(directory/'case.json');render=read(directory/'render.json')
    assert hashlib.sha256(source['text'].encode()).hexdigest()==expected,'Source changed'
    assert (directory/'judgment.txt').read_text(encoding='utf8')==source['text']
    _,errors=normalize_peer(case,source);assert not errors,errors
    covered=set()
    for shot in render['images']:
        with Image.open(directory/shot['path']) as picture:assert picture.size==(860,1864)
        for box in shot['boxes']:
            x,y,w,h=box['bbox_pixels'];assert 0<=x<x+w<=860 and 0<=y<y+h<=1864
        covered.update(shot['message_ids'])
    assert covered=={m['id'] for m in case['messages']},'Message coverage mismatch'
    for task in read(directory/'tasks.json'):
        assert not set(task)&{'answer','label','source_refs','reasoning','missing_evidence'},'Answer leakage'
        for image in task['images']:assert sha(directory/image['file'])==image['sha256'],'Image changed'
    return dict(cases=1,images=len(render['images']),messages=len(case['messages']),questions=len(case['questions']))

def render_current_case(browser,directory):
    import tools.render_v2_round2 as renderer
    original=renderer.message_html
    case=read(directory/'case.json')
    if case.get('platform') not in [None,'WeChat','wechat'] and not case.get('source_medium'):
        raise ValueError('Non-WeChat or unknown medium requires an explicit neutral transcript marker')
    def render_message(message,conversation,people,previous,platform):
        adapted=copy.deepcopy(message)
        if adapted.get('date_basis') in ['source_part_of_day','source_month_day'] and not adapted.get('timestamp'):
            adapted['date_basis']='source_month' # display-only adapter for the renderer's date-label branch
        output=original(adapted,conversation,people,previous,platform)
        if message.get('original_medium')=='voice_transcription_in_judgment' and message.get('origin_type')=='judgment_paraphrase':
            output=output.replace('>语音转文字</div>','>语音内容转述</div>')
        if message.get('minute_basis')=='source_approximate_minute':
            output=re.sub(r'(<div class="stamp">[^<]*?)([0-9]{2}:[0-9]{2})(</div>)',r'\1约\2\3',output)
        if case.get('source_medium') and '微信' not in case['source_medium']:
            output=output.replace('<div class="transfer-footer">微信转账</div>','<div class="transfer-footer">转账记录</div>')
        return output
    renderer.message_html=render_message
    try:return render_authored_case(browser,directory)
    finally:renderer.message_html=original

def build():
    from tools.render_v2_round2 import Browser
    import tools.render_v2_round2 as renderer
    renderer.ROOT=OUT/'work'
    parent=read(PARENT/'execution_state.json');decisions=read(OUT/'decisions.json')['records']
    assert len({d['source_index'] for d in decisions})==len(decisions),'Duplicate decisions'
    mapping={d['source_index']:d for d in decisions};records=[]
    with Browser('round006-peer-revisions') as browser:
        browser.call('Network.enable');browser.call('Network.setBlockedURLs',{'urls':['http://*','https://*']})
        for prior in parent['records']:
            row=copy.deepcopy(prior);row['parent_status']=prior['new_sample_status'];decision=mapping.get(row['source_index'])
            row['peer_round_action']='inherited_without_new_review'
            if decision:
                source=read(ROOT/row['source_path']);review=read(ROOT/decision['review_path']);validate_review(review,source)
                row.update(peer_review=decision['review_path'],peer_round_action=decision['action'])
                if decision['action']=='withdraw':
                    row.pop('artifact_directory',None);row['new_sample_status']='source_gap';row['withdrawal_reason']=decision['reason']
                elif decision['action']=='confirm_gap':row['new_sample_status']='source_gap'
                elif decision['action']=='pass':assert prior['new_sample_status']=='verified'
                elif decision['action'] in ['revise','recover','auxiliary']:
                    raw=read(ROOT/decision['candidate_path']);case,errors=normalize_peer(raw,source);assert not errors,errors
                    ident=f'q6_{row["source_index"]:04d}';directory=OUT/'zh'/ident;provenance=directory/'provenance.json'
                    input_hash=sha(ROOT/decision['candidate_path'])
                    visible_digest=hashlib.sha256(json.dumps(visible_payload(case),sort_keys=True,ensure_ascii=False).encode()).hexdigest()
                    if provenance.exists() and (read(provenance)['authored_input_sha256']!=input_hash or visible_payload(read(directory/'case.json'))!=visible_payload(case)):
                        revision_digest=hashlib.sha256((input_hash+visible_digest).encode()).hexdigest()[:8]
                        ident+='_'+revision_digest;directory=OUT/'zh'/ident;provenance=directory/'provenance.json'
                    if provenance.exists():
                        assert read(provenance)['authored_input_sha256']==input_hash,'Existing revision differs; use a new version'
                        verify_case(directory,row['judgment_text_sha256'])
                    else:
                        directory.mkdir(parents=True,exist_ok=True)
                        case.update(id=ident,status='agent_peer_reviewed_candidate_not_professional_gold',author=decision.get('author','root author; peer correction; exact model build not exposed'))
                        if raw.get('source_medium'):case.update(platform='communication_excerpt',source_medium=raw['source_medium'])
                        if decision.get('display_case_no'):case.update(source_case_no_stored=source['case_no'],case_no=decision['display_case_no'])
                        save(directory/'case.json',case);copy_file(ROOT/row['source_path'],directory/'source.json');(directory/'judgment.txt').write_text(source['text'],encoding='utf8')
                        copy_file(ROOT/decision['candidate_path'],directory/'authoring'/'accepted.candidate.json');copy_file(ROOT/decision['review_path'],directory/'authoring'/'peer.review.json')
                        parent_directory=ROOT/prior['artifact_directory'] if prior.get('artifact_directory') else None
                        if parent_directory and visible_payload(case)==visible_payload(read(parent_directory/'case.json')):
                            copy_file(parent_directory/'render.json',directory/'render.json')
                            for shot in read(parent_directory/'render.json')['images']:copy_file(parent_directory/shot['path'],directory/shot['path'])
                            # Retain reproducible HTML, without rewriting its message content.
                            for conv in case['conversations']:copy_file(parent_directory/(conv['id']+'.html'),directory/(conv['id']+'.html'))
                            render_mode='byte_reused_images_answer_revision_only'
                        else:render_current_case(browser,directory);render_mode='rerendered_archived_messages'
                        rendering=read(directory/'render.json');tasks=[]
                        for question in case['questions']:
                            mids=set(question['message_ids']);shots=[s for s in rendering['images'] if question.get('whole_case_required') or mids&set(s['message_ids'])]
                            tasks.append(dict(task_id=ident+'.'+question['id'],question=question['question'],instruction='仅按合成研究图中可见通信回答；标注原载体不等于原界面，陈述不等于实际履行。',images=[dict(file=s['path'],sha256=sha(directory/s['path'])) for s in shots]))
                        save(directory/'tasks.json',tasks);save(directory/'answers.reviewer_only.json',case['questions'])
                        save(provenance,dict(parent_round='round_005',parent_artifact=prior.get('artifact_directory'),action=decision['action'],authored_input=decision['candidate_path'],authored_input_sha256=input_hash,normalized_visible_sha256=visible_digest,peer_review=decision['review_path'],render_mode=render_mode,source_text_sha256=row['judgment_text_sha256'],professional_gold=False))
                        page='<!doctype html><meta charset="utf-8"><style>body{max-width:1100px;margin:30px auto;font:16px/1.8 sans-serif}img{width:340px}</style><h1>'+html.escape(case['case_no'])+'</h1><p>合成开发候选，经独立代理复查；非人类/法律认证。</p><a href="judgment.txt">判决全文</a>'
                        page+=''.join('<h2>'+html.escape(t['question'])+'</h2>'+''.join('<img src="'+im['file']+'">' for im in t['images']) for t in tasks)
                        (directory/'index.html').write_text(page,encoding='utf8')
                    row.update(new_sample_status='source_gap' if decision['action']=='auxiliary' else 'verified',artifact_directory=directory.relative_to(ROOT).as_posix(),auxiliary_only=decision['action']=='auxiliary')
                else:raise ValueError('Unsupported action')
            records.append(row)
    save(OUT/'execution_state.json',dict(records=records,parent_state='datasets/v2.0.0/round_005/execution_state.json'));report()

def verify():
    state=read(OUT/'execution_state.json');counts=Counter();auxiliary_counts=Counter();errors=[]
    for row in state['records']:
        try:
            source=read(ROOT/row['source_path']);assert hashlib.sha256(source['text'].encode()).hexdigest()==row['judgment_text_sha256']
            if row.get('peer_review'):validate_review(read(ROOT/row['peer_review']),source)
            if row['new_sample_status']=='verified':counts.update(verify_case(ROOT/row['artifact_directory'],row['judgment_text_sha256']))
            elif row.get('auxiliary_only'):auxiliary_counts.update(verify_case(ROOT/row['artifact_directory'],row['judgment_text_sha256']))
        except Exception as error:errors.append(dict(source_index=row['source_index'],error=str(error)))
    parent_manifest=read(PARENT/'artifact_manifest.json')['sha256'];changed=[p for p,digest in parent_manifest.items() if not (ROOT/p).is_file() or sha(ROOT/p)!=digest]
    if changed:errors.append(dict(parent_frozen_files_changed=changed))
    save(OUT/'verification.json',dict(counts=counts,auxiliary_counts=auxiliary_counts,errors=errors,parent_manifest_files=len(parent_manifest),parent_frozen_files_changed=changed,professional_gold=False))
    print(json.dumps(dict(counts=counts,auxiliary_counts=auxiliary_counts,errors=errors),ensure_ascii=False));return bool(errors)

def report():
    state=read(OUT/'execution_state.json');rows=state['records'];actions=Counter(r['peer_round_action'] for r in rows);phases=Counter(r['new_sample_status'] for r in rows)
    summary=dict(queue_records=len(rows),phases=phases,peer_actions=actions,all_records_accounted_for=phases['verified']+phases['source_gap']==len(rows),all_samples_generated=phases['verified']==len(rows),professional_gold=False,new_api_calls=0)
    save(OUT/'summary.json',summary)
    page='<!doctype html><meta charset="utf-8"><style>body{max-width:1100px;margin:30px auto;font:16px/1.8 sans-serif}td{padding:7px;border-bottom:1px solid #ddd}</style><h1>V2第六轮：并行复核后的200条清单</h1><p>'+html.escape(json.dumps(summary,ensure_ascii=False))+'</p><table><tr><th>来源序号</th><th>状态</th><th>本轮处置</th><th>当前版本</th></tr>'
    for row in rows:
        href=os.path.relpath(ROOT/row['artifact_directory']/'index.html',OUT).replace(os.sep,'/') if row.get('artifact_directory') else None
        link='<a href="'+href+'">查看</a>' if href else '来源缺口'
        page+='<tr><td>'+str(row['source_index'])+'</td><td>'+row['new_sample_status']+'</td><td>'+row['peer_round_action']+'</td><td>'+link+'</td></tr>'
    (OUT/'index.html').write_text(page+'</table>',encoding='utf8')

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['build','verify','report']);args=parser.parse_args()
    if args.command=='build':build()
    elif args.command=='verify':sys.exit(verify())
    else:report()
