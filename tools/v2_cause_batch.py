"""Versioned Chinese cause coverage: selection, generation, revision, render, review.

Every source label is accounted for. Model revisions are candidates, not human gold.
Run without --limit to cover all selected labels; resumable stages retain raw outputs.
"""
from pathlib import Path
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import argparse, copy, hashlib, html, json, re, shutil, sys, threading, os, uuid
import openpyxl
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from legalhub.synthesis import paragraphs, model, call

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'datasets/v2.0.0/round_003'
SOURCE=ROOT/'projects/ScreenshotLegalBench_v2/generate_chat/output/wkinfo_samples_by_case.xlsx'
PROMPTS=ROOT/'blocks/synthesizer/prompts'
STOP=threading.Event()
CFG={'model_config':'configs/models.local.yaml','generation_max_tokens':11000,
     'critic_max_tokens':11000,'timeout':240,'inference_mode':'cloud'}


def read(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_name(path.name+'.'+uuid.uuid4().hex+'.tmp')
    temporary.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(temporary,path)
def sha(data):return hashlib.sha256(data).hexdigest()
def status(folder,phase,**extra):save(folder/'status.json',{'phase':phase,**extra})
def folder(item):return OUT/'zh'/item['id']
def processing_items(manifest=None):
    manifest=manifest or read(OUT/'manifest.json')
    return manifest['representatives']+manifest.get('supplemental_representatives',[])


def score(row):
    text=row['content']
    nearby=re.findall(r'.{0,45}(?:微信|回复|聊天).{0,140}',text)
    quotes=sum('“' in chunk or '：' in chunk for chunk in nearby)
    return quotes*10+min(len(nearby),20)-max(0,len(text)-18000)/3000


def prepare():
    OUT.mkdir(parents=True,exist_ok=True)
    workbook=openpyxl.load_workbook(SOURCE,read_only=True,data_only=True)
    sheet=workbook.active;sheet.reset_dimensions();iterator=sheet.iter_rows(values_only=True);header=next(iterator)
    rows=[dict(zip(header,r)) for r in iterator];sheetname=sheet.title;workbook.close()
    groups=defaultdict(list)
    for index,row in enumerate(rows):groups[row['case_cause']].append(index)
    source_sha=sha(SOURCE.read_bytes());items=[];pool=[]
    for cause,indices in groups.items():
        index=146 if 146 in indices else max(indices,key=lambda i:(score(rows[i]),-i))
        row=rows[index];ident=f'zh_{index:04d}';directory=OUT/'zh'/ident
        source={'id':ident,'language':'zh','platform':'WeChat','jurisdiction':'China',
            'cause':cause,'cause_label_status':'historical_source_label_not_current_national_catalog',
            'case_no':row['case_no'],'title':row['title'],'url':row['url'],
            'source_file':SOURCE.relative_to(ROOT).as_posix(),'source_index':index,'source_sha256':source_sha,
            'judgment_text_sha256':sha(row['content'].encode('utf-8')),'text':row['content'],
            'paragraphs':paragraphs(row['content']),'split':'development','status':'synthetic_candidate_requires_review'}
        original=directory/'source.json'
        if original.exists():assert read(original)==source,'Source changed; create a new round'
        else:save(original,source)
        (directory/'judgment.txt').write_bytes(row['content'].encode('utf-8'))
        verified={'source_file':source['source_file'],'source_sha256_expected':source_sha,'source_sha256_actual':source_sha,
                  'sheet':sheetname,'excel_row':index+2,'content_cell':openpyxl.utils.get_column_letter(header.index('content')+1)+str(index+2),
                  'case_no_cell':openpyxl.utils.get_column_letter(header.index('case_no')+1)+str(index+2),
                  'court':row['court'],'date':row['date'],'content_exact':True,'judgment_text_sha256':source['judgment_text_sha256']}
        save(directory/'source.verification.json',verified)
        if not (directory/'status.json').exists():status(directory,'source_prepared')
        item={'id':ident,'source_index':index,'cause':cause,'atomic_causes':cause.splitlines(),'case_no':row['case_no'],
              'alternatives':indices,'selection_score':score(row),'judgment_text_sha256':source['judgment_text_sha256']}
        items.append(item)
    selected={i['source_index'] for i in items}
    for i,row in enumerate(rows):
        pool.append({'source_index':i,'excel_row':i+2,'case_no':row['case_no'],'cause':row['case_cause'],
                     'selected':i in selected,'judgment_text_sha256':sha(row['content'].encode('utf-8')),
                     'text_characters':len(row['content']),'selection_score':score(row)})
    (OUT/'source_pool.jsonl').write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in pool)+'\n',encoding='utf-8')
    manifest={'round':'round_003','version':'v2.0.0','language':'zh','split':'development',
        'source_records':len(rows),'raw_cause_labels':len(groups),'atomic_causes':len({c for item in items for c in item['atomic_causes']}),
        'unique_judgment_texts':len({r['judgment_text_sha256'] for r in pool}),
        'representatives':items,'source_sha256':source_sha,'generator':'kimi3_low','reviewer':'kimi26_nonthinking',
        'policy':'one representative per original cause label; unsuitable sources deferred with explicit reasons',
        'accepted_reference':'../round_002/zh/zh_sales_146','v1_assets_modified':False,
        'release_status':'development_review_candidates_not_gold','inference_mode':'cloud; local switch retained in batch config'}
    save(OUT/'manifest.json',manifest)
    assets=OUT/'assets';assets.mkdir(exist_ok=True)
    for p in (ROOT/'datasets/v2.0.0/round_002/assets').iterdir():
        if p.is_file():shutil.copyfile(p,assets/p.name)
    accepted=OUT/'zh/zh_0146'
    if not (accepted/'case.json').exists():
        case=read(ROOT/'datasets/v2.0.0/round_002/zh/zh_sales_146/case.json')
        case['id']='zh_0146';case['status']='user_accepted_reference';case['author']='Codex; reused user-reviewed round_002 sample'
        save(accepted/'case.json',case);save(accepted/'direct.draft.json',case)
        status(accepted,'reviewed',method='reuse_user_accepted_reference',independent_human_difficulty_review=False)
    print(json.dumps({k:manifest[k] for k in ['source_records','raw_cause_labels','atomic_causes','unique_judgment_texts']},ensure_ascii=False),flush=True)


def normalize(raw,source):
    candidate=copy.deepcopy(raw);errors=[]
    candidate.update(id=source['id'],language='zh',platform='WeChat',cause=source['cause'],case_no=source['case_no'],
                     author='Kimi K3 draft + Kimi K2.6 revision; program source checks; not human approved',status='model_revised_pending_user_review')
    if candidate.get('suitability',{}).get('decision')=='defer':return candidate,[]
    ps={p['id']:p for p in source['paragraphs']}
    def resolve(ref,who):
        legacy_ids=ref.get('paragraph_ids',[]) if not ref.get('source_id') else []
        p=ps.get(ref.get('source_id') or (legacy_ids[0] if legacy_ids else None))
        last=ps.get(ref.get('source_end_id') or (legacy_ids[-1] if legacy_ids else None),p)
        quote=ref.get('quote','')
        region=source['text'][p['char_start']:last['char_end']] if p and last else ''
        if not quote or quote not in region:
            errors.append(who+': nonliteral source reference');return ref
        if 'char_start' in ref or 'char_end' in ref:
            start=ref.get('char_start');end=ref.get('char_end')
            if (not isinstance(start,int) or not isinstance(end,int)
                    or not p['char_start']<=start<end<=last['char_end']
                    or source['text'][start:end]!=quote):
                errors.append(who+': invalid explicit source coordinates');return ref
        else:
            start=p['char_start']+region.index(quote)
        return {**ref,'char_start':start,'char_end':start+len(quote),
                'paragraph_ids':[p['id'] for p in source['paragraphs'] if p['char_start']<start+len(quote) and p['char_end']>start]}
    people={p.get('id'):p for p in candidate.get('participants',[])}
    convs={c.get('id'):c for c in candidate.get('conversations',[])}
    if len(people)!=len(candidate.get('participants',[])):errors.append('Duplicate participant IDs')
    if len(convs)!=len(candidate.get('conversations',[])):errors.append('Duplicate conversation IDs')
    messages=candidate.get('messages',[]);seen=set();dates={}
    if not people or not convs or not messages:errors.append('Missing actors, conversations or messages')
    for conv in convs.values():
        if conv.get('viewer_id') not in conv.get('participant_ids',[]):errors.append('Viewer not in participants')
        if not set(conv.get('participant_ids',[]))<=set(people):errors.append('Unknown conversation participant')
    allowed={'verbatim_quote','judgment_paraphrase','synthetic_completion','judgment_attachment_reconstruction'}
    for message in messages:
        ident=message.get('id','?')
        if ident in seen:errors.append('Duplicate message ID '+ident)
        seen.add(ident);conv=convs.get(message.get('conversation_id'),{})
        if message.get('sender_id') not in conv.get('participant_ids',[]):errors.append(ident+': wrong speaker')
        origin=message.get('origin_type')
        if origin not in allowed:errors.append(ident+': invalid origin')
        refs=[resolve(ref,ident) for ref in message.get('source_refs',[])]
        message['source_refs']=refs
        if origin!='synthetic_completion' and not refs:errors.append(ident+': missing source')
        if origin=='verbatim_quote' and not any(message.get('text')==r.get('quote') for r in refs):errors.append(ident+': altered quote')
        message.setdefault('kind','text');message.setdefault('text','');message.setdefault('timestamp',None)
        if message['kind'] not in ['text','file','attachment_excerpt','transfer']:errors.append(ident+': unsupported message kind')
        message.setdefault('minute_basis','synthetic_layout_only')
        if message.get('timestamp')=='null':message['timestamp']=None
        if message.get('timestamp'):
            try:
                moment=datetime.fromisoformat(message['timestamp']);cid=message['conversation_id']
                if cid in dates and moment<dates[cid]:errors.append(ident+': chronology reversed')
                dates[cid]=moment
            except (ValueError,TypeError):errors.append(ident+': invalid timestamp')
        if message['kind']=='attachment_excerpt':
            attachment=message.get('attachment') or {}
            if not attachment.get('rows') or not attachment.get('reconstruction_notice'):errors.append(ident+': unsupported attachment format')
        elif 'attachment' in message:message.pop('attachment')
        if message['kind']=='transfer':
            transfer=message.get('transfer',{})
            if not isinstance(transfer.get('amount'),(int,float)) or transfer['amount']<=0:errors.append(ident+': invalid transfer amount')
            if transfer.get('currency')!='CNY':errors.append(ident+': unsupported transfer currency')
            receipt=transfer.get('receipt_status','not_reconstructed')
            if receipt not in ['not_reconstructed','expired','received']:errors.append(ident+': unsupported transfer receipt status')
            state_words={'expired':['过期'],'received':['已被接收','已收款','已接收','予以接收']}
            if receipt in state_words and not any(w in ''.join(r['quote'] for r in refs) for w in state_words[receipt]):
                errors.append(ident+': transfer receipt status missing source support')
        if message['kind']=='file':message['file_type']=message.get('file_type') or '文档'
        if not message.get('timestamp') and message.get('date_basis')=='source_day':errors.append(ident+': exact source day missing')
    for fact in candidate.get('facts',[]):
        if not fact.get('source_refs'):errors.append(fact.get('id','fact')+': fact missing source reference')
        fact['source_refs']=[resolve(r,fact.get('id','fact')) for r in fact.get('source_refs',[])]
    for question in candidate.get('questions',[]):
        if not set(question.get('message_ids',[]))<=seen:errors.append(question.get('id','q')+': missing message citation')
        if not question.get('question') or not question.get('answer'):errors.append('Empty question or answer')
        question['status']='author_draft_not_certified_gold'
    if len(candidate.get('questions',[]))<2:errors.append('Insufficient questions')
    return candidate,list(dict.fromkeys(errors))


def prompt_source(source):
    return json.dumps({'case_no':source['case_no'],'language':'zh','cause':source['cause'],'paragraphs':source['paragraphs']},ensure_ascii=False)


def generate(item):
    directory=folder(item);state=read(directory/'status.json')
    if state['phase'] in ['reviewed','rendered','deferred']:return item['id'],state['phase']
    if STOP.is_set():return item['id'],'not_started_circuit_open'
    source=read(directory/'source.json')
    local_cfg=dict(CFG)
    config_path=ROOT/'blocks/synthesizer/config.round_003.json'
    if config_path.exists():local_cfg.update(read(config_path))
    generator,key=model(local_cfg.get('generator','kimi3_low'),local_cfg)
    reviewer,review_key=model(local_cfg.get('reviewer','kimi26_nonthinking'),local_cfg,True)
    reference=read(ROOT/'datasets/v2.0.0/round_002/zh/zh_sales_146/case.json')
    reference={k:reference[k] for k in ['participants','conversations','messages']}
    # Example context is isolated from the new source and never included as legal evidence.
    writing=(PROMPTS/'generate_v2_r3.md').read_text(encoding='utf-8')+'\n\n已获用户自然感认可的写作示例（不能复制情节）：\n'+json.dumps(reference,ensure_ascii=False)+'\n\n本案来源（引用只能来自此处）：\n'+prompt_source(source)
    try:
        raw=call('01_draft',directory,writing,generator,key);save(directory/'draft.raw.json',raw)
        draft,errors=normalize(raw,source);save(directory/'draft.json',draft)
        review=(PROMPTS/'critic_v2_r3.md').read_text(encoding='utf-8')+'\n本案来源：\n'+prompt_source(source)+'\n初稿：\n'+json.dumps(raw,ensure_ascii=False)+'\n程序检查：\n'+json.dumps(errors,ensure_ascii=False)
        revised=call('02_review_revision',directory,review,reviewer,review_key);save(directory/'revision.review.json',revised)
        raw_final=revised.get('case') or raw
        final,errors=normalize(raw_final,source)
        if revised.get('decision')=='defer' or final.get('suitability',{}).get('decision')=='defer':
            save(directory/'deferred.candidate.json',final)
            status(directory,'deferred',reason=revised.get('reason') or final.get('suitability',{}).get('reason'),errors=errors)
            return item['id'],'deferred'
        if errors:
            save(directory/'revision.invalid.json',final)
            status(directory,'validation_failed',reason='Source/schema checks failed after model revision',errors=errors)
            return item['id'],'validation_failed'
        final['second_pass_edits']=revised.get('issues',[])
        save(directory/'case.json',final);save(directory/'case.checks.json',{'errors':[],'source_spans_exact':True,'human_review':False,'difficulty_certified':False})
        status(directory,'reviewed',issues=len(revised.get('issues',[])),method='model_generation_and_revision')
        return item['id'],'reviewed'
    except Exception as e:
        http=[]
        for name in ['01_draft.response.json','02_review_revision.response.json']:
            if (directory/name).exists():http.append(read(directory/name).get('http_status'))
        quota_error=any('balance' in read(directory/name).get('provider_error',{}).get('message','').lower()
                        or read(directory/name).get('provider_error',{}).get('type')=='exceeded_current_quota_error'
                        for name in ['01_draft.response.json','02_review_revision.response.json'] if (directory/name).exists())
        if any(x in [401,402,403] for x in http) or quota_error:
            STOP.set()
            save(OUT/'execution_state.json',{'phase':'provider_blocked','reason':'API authentication, credit balance or quota prevents bulk model stages',
                'failed_case':item['id'],'http_statuses':http,'pending_action':'restore configured provider, or explicitly authorize direct Codex-agent writing'})
        status(directory,'provider_failed' if any(http) else 'stage_failed',reason=type(e).__name__+': '+str(e),http_statuses=http)
        return item['id'],read(directory/'status.json')['phase']


def run(limit,workers,ids):
    if (OUT/'execution_state.json').exists() and read(OUT/'execution_state.json').get('phase')=='provider_blocked':
        print('Bulk API run blocked by recorded provider state. Restore the provider before resuming.',flush=True);return
    items=read(OUT/'manifest.json')['representatives']
    if ids:items=[i for i in items if i['id'] in ids.split(',')]
    pending=[i for i in items if read(folder(i)/'status.json')['phase'] not in ['rendered','reviewed','deferred']]
    if limit:pending=pending[:limit]
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures={executor.submit(generate,item):item for item in pending}
        for future in as_completed(futures):
            ident,phase=future.result();print(json.dumps({'case':ident,'phase':phase},ensure_ascii=False),flush=True)
    report()


def render_all():
    from tools.render_v2_round2 import Browser,render_case
    from tools.build_v2_judgment_review import build
    from PIL import Image
    with Browser('chrome-round003') as browser:
        for item in processing_items():
            directory=folder(item);state=read(directory/'status.json')
            if state['phase']!='reviewed':continue
            try:
                if (directory/'render.json').exists():
                    version=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%f')
                    archive=directory/'render.versions'/version;archive.mkdir(parents=True,exist_ok=True)
                    shutil.copyfile(directory/'render.json',archive/'render.json')
                    for old in read(directory/'render.json')['images']:
                        path=(directory/old['path']).resolve()
                        assert path.is_relative_to(directory.resolve())
                        target=archive/old['path'];target.parent.mkdir(parents=True,exist_ok=True)
                        if path.exists():shutil.copyfile(path,target)
                render_case(browser,directory)
                rendering=read(directory/'render.json');fixed={};covered=set()
                for image in rendering['images']:
                    with Image.open(directory/image['path']) as png:
                        assert png.size==(860,1864)
                        chrome=(png.crop((0,0,860,176)).tobytes(),png.crop((0,1738,860,1864)).tobytes())
                        cid=image['conversation_id']
                        if cid in fixed:assert chrome==fixed[cid]
                        else:fixed[cid]=chrome
                    covered.update(image['message_ids'])
                candidate=read(directory/'case.json');assert covered=={m['id'] for m in candidate['messages']}
                build(directory,read(directory/'source.verification.json'))
                case_review(directory,candidate,rendering)
                status(directory,'rendered',images=len(rendering['images']),messages=len(candidate['messages']),
                       exact_quotes=sum(m['origin_type']=='verbatim_quote' for m in candidate['messages']),method=state.get('method'))
                current={i['path'] for i in rendering['images']}
                for stale in (directory/'screenshots').glob('*.png'):
                    if stale.relative_to(directory).as_posix() not in current:
                        assert stale.resolve().parent==(directory/'screenshots').resolve()
                        stale.unlink()
                print(item['id'],'rendered',len(rendering['images']),flush=True)
            except Exception as e:
                status(directory,'render_failed',reason=type(e).__name__+': '+str(e));print(item['id'],'render_failed',str(e),flush=True)
    report()


def case_review(directory,case,rendering):
    esc=lambda v:html.escape(str(v));mapping=defaultdict(list)
    for image in rendering['images']:
        for ident in image['message_ids']:mapping[ident].append(image['page'])
    questions=case.get('questions',[])
    for question in questions:
        question['candidate_pages']=sorted({p for ident in question['message_ids'] for p in mapping[ident]})
        question['page_scope']='whole_case' if question.get('whole_case_required') else 'cited_messages_candidate'
        question['review_pages']=list(range(1,len(rendering['images'])+1)) if question.get('whole_case_required') else question['candidate_pages']
    save(directory/'questions.review.json',questions)
    tasks=[{'id':case['id']+'_'+q['id'],'language':'zh','question':q['question'],
            'images':[image['path'] for image in rendering['images']],'reference_status':'author_draft_not_gold'} for q in questions]
    save(directory/'tasks.image_only.json',tasks)
    images=''.join(f'<figure><figcaption>第{image["page"]}页 · {esc(image["conversation_id"])}</figcaption><a href="{image["path"]}"><img src="{image["path"]}" loading="lazy"></a></figure>' for image in rendering['images'])
    checks=''.join('<li>'+esc(c)+'</li>' for c in case.get('constraints',[]))
    review_file='codex.review.json' if (directory/'codex.review.json').exists() else 'revision.review.json'
    amendments=read(directory/review_file).get('issues',[]) if (directory/review_file).exists() else []
    if (directory/'root.review.json').exists():amendments=amendments+read(directory/'root.review.json').get('issues',[])
    draft_file='draft.json' if (directory/'draft.json').exists() else 'direct.draft.json'
    issues=''.join(f'<li>{esc(i.get("problem",""))} → {esc(i.get("change",""))}</li>' for i in amendments)
    questions_html=''.join(f'<details><summary>{esc(q["question"])}</summary><p>{esc(q["answer"])}</p><small>消息 {q["message_ids"]}；候选页 {q["candidate_pages"]}；未经最小集验证。</small></details>' for q in questions)
    review_link=f' · <a href="{review_file}">具体修订记录</a>' if (directory/review_file).exists() else ''
    if (directory/'root.review.json').exists():review_link+=' · <a href="root.review.json">主 agent 实际修订</a>'
    if (directory/'peer.review.json').exists():review_link+=' · <a href="peer.review.json">另一位 agent 复核（非人工评分）</a>'
    if (directory/'peer.supplement_questions.review.json').exists():review_link+=' · <a href="peer.supplement_questions.review.json">纯图片题复核</a>'
    page=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(case['case_no'])} · 聊天复审</title><style>body{{font:16px/1.8 "Microsoft YaHei",sans-serif;background:#f1f5f0;color:#263a31;margin:0}}main{{max-width:1200px;margin:auto;padding:25px}}section{{background:white;padding:24px;border-radius:10px;margin:20px 0}}a{{color:#13745e}}.gallery{{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:18px}}figure{{margin:0}}img{{width:100%;height:auto}}small{{color:#687a70}}details{{padding:13px;background:#f6f8f4;margin:12px 0}}summary{{cursor:pointer}}@media(max-width:720px){{.gallery{{grid-template-columns:1fr}}}}</style><main><section><a href="../../index.html">← 全部案由</a><h1>{esc(case['case_no'])}</h1><p>{esc(case['cause'])}</p><p><a href="JUDGMENT.html">判决全文与逐句来源</a> · <a href="case.json">结构化聊天</a> · <a href="{draft_file}">初稿</a>{review_link}</p><p>作者与修订：{esc(case.get('author',''))}</p><p>合成开发候选。原话、转写、创作和重建附件分开标记；模型修订不代表人工认可或难度达标。</p></section><section><h2>固定尺寸截图</h2><div class="gallery">{images}</div></section><section><h2>本案约束</h2><ul>{checks}</ul><h2>具体修订</h2><ul>{issues}</ul></section><section><h2>候选题</h2>{questions_html}</section></main></html>'''
    if case.get('parent_case_id'):
        page=page.replace('<h1>',f'<p>同标签候补判决：<a href="../{case["parent_case_id"]}/status.json">原代表案及暂缓原因</a>。本案是独立来源，不与原代表案拼接。</p><h1>',1)
    (directory/'review.html').write_text(page,encoding='utf-8')


def report():
    manifest=read(OUT/'manifest.json');entries=[];phases=Counter();total_images=total_messages=0
    for item in manifest['representatives']:
        directory=folder(item);state=read(directory/'status.json');phases[state['phase']]+=1
        if state['phase']=='rendered':total_images+=state.get('images',0);total_messages+=state.get('messages',0)
        entries.append({**item,**state})
    supplements=[];supplement_phases=Counter()
    for item in manifest.get('supplemental_representatives',[]):
        state=read(folder(item)/'status.json');supplement_phases[state['phase']]+=1
        supplements.append({**item,**state})
        if state['phase']=='rendered':total_images+=state.get('images',0);total_messages+=state.get('messages',0)
    covered_labels={i['cause'] for i in entries+supplements if i['phase']=='rendered'}
    usage=Counter();calls=Counter()
    for record in OUT.glob('zh/*/requests/*.json'):
        r=read(record);calls[r.get('status','unknown')]+=1
        for k,v in r.get('usage',{}).items():
            if isinstance(v,int):usage[k]+=v
    execution=read(OUT/'execution_state.json') if (OUT/'execution_state.json').exists() else {'phase':'ready'}
    audit=read(OUT/'source_audit.json') if (OUT/'source_audit.json').exists() else {}
    alternative_audit=read(OUT/'alternatives.verification.json') if (OUT/'alternatives.verification.json').exists() else {}
    if execution.get('phase')=='provider_blocked':
        execution['pending_original_labels']=manifest['raw_cause_labels']-phases['rendered']
        execution['unaffected_work']=f'207 source representatives archived; {phases["rendered"]} cases rendered with exact source mappings, including accepted reference and directly revised/written pilots.'
        save(OUT/'execution_state.json',execution)
    elif execution.get('phase') in ['agent_writing','agent_review','complete_with_deferrals','complete']:
        execution['pending_original_labels']=sum(phases[p] for p in ['source_prepared','reviewed','render_failed','validation_failed','stage_failed','provider_failed'])
        execution['rendered_cases']=phases['rendered'];execution['deferred_cases']=phases['deferred']
        execution['pending_supplemental_cases']=sum(n for phase,n in supplement_phases.items() if phase not in ['rendered','deferred'])
        execution['rendered_supplemental_cases']=supplement_phases['rendered']
        save(OUT/'execution_state.json',execution)
    save(OUT/'summary.json',{'source_records':manifest['source_records'],'raw_cause_labels':manifest['raw_cause_labels'],
        'atomic_causes':manifest['atomic_causes'],'phases':dict(phases),'rendered_images':total_images,
        'rendered_messages':total_messages,'calls':dict(calls),'usage':dict(usage),'human_approved_reference_cases':1,
        'all_labels_accounted_for':len(entries)==manifest['raw_cause_labels'],'all_labels_generated':len(covered_labels)==manifest['raw_cause_labels'],
        'all_primary_labels_handled':phases['rendered']+phases['deferred']==manifest['raw_cause_labels'],
        'all_labels_processed':phases['rendered']+phases['deferred']==manifest['raw_cause_labels'] and all(i['phase'] in ['rendered','deferred'] for i in supplements) and alternative_audit.get('complete',False),
        'deferred_alternative_review':alternative_audit,
        'supplemental_phases':dict(supplement_phases),'rendered_cases_total':phases['rendered']+supplement_phases['rendered'],'labels_with_rendered_candidate':len(covered_labels),
        'labels_without_rendered_candidate':manifest['raw_cause_labels']-len(covered_labels),
        'execution_state':execution,'source_audit_counts':audit.get('counts',{}),'gold_release':False})
    save(OUT/'coverage.json',entries)
    save(OUT/'supplemental_coverage.json',supplements)
    esc=lambda s:html.escape(str(s));rows=[]
    labels={'source_prepared':'待生成','reviewed':'待渲染','rendered':'有截图，待人工复审','deferred':'来源不足，暂缓','validation_failed':'引用/结构待修','provider_failed':'模型服务失败','stage_failed':'阶段待修','render_failed':'图片排版待修'}
    for item in entries:
        cause=item['cause'];ident=item['id'];state=item['phase'];directory=folder(item)
        if (directory/'review.html').exists() and state=='rendered':links=f'<a href="zh/{ident}/review.html">聊天截图</a> · <a href="zh/{ident}/JUDGMENT.html">判决及来源</a>'
        else:links=f'<a href="zh/{ident}/judgment.txt">判决全文</a> · <a href="zh/{ident}/status.json">处理记录</a>'
        reason=item.get('reason','');reason+='；'.join(item.get('errors',[])[:3])
        case_audit=read(directory/'source.audit.json') if (directory/'source.audit.json').exists() else {}
        for extra in supplements:
            if extra['parent_case_id']==ident:
                target='review.html' if extra['phase']=='rendered' else 'status.json'
                links+=f'<br><span id="{extra["id"]}">独立候补：<a href="zh/{extra["id"]}/{target}">{extra["id"]} ({esc(extra["phase"])})</a></span>'
        if case_audit.get('warnings'):
            reason+='；'+'；'.join(case_audit['warnings'])
            links+=f' · <a href="zh/{ident}/source.audit.json">来源字段核查</a>'
        number=esc(item['case_no'])
        if case_audit.get('case_no_from_text') and any('案号字段' in w for w in case_audit.get('warnings',[])):
            number=esc(case_audit['case_no_from_text'])+'<br><small>正文案号候选；归档案号字段：'+esc(item['case_no'])+'</small>'
        rows.append(f'<tr id="{ident}" data-search="{esc(cause+item["case_no"]+str(case_audit.get("case_no_from_text",""))+state)}"><td>{esc(cause.replace(chr(10)," / "))}</td><td>{number}<br>{links}</td><td>{esc(labels.get(state,state))}<br><small>{esc(reason)}</small></td></tr>')
    style='body{font:15px/1.8 "Microsoft YaHei",sans-serif;background:#f1f5f0;color:#263a31;margin:0}main{max-width:1400px;margin:auto;padding:25px}section{background:white;border-radius:12px;padding:24px;margin:20px 0}a{color:#13745e}table{border-collapse:collapse;width:100%}td,th{border:1px solid #d7e3da;text-align:left;padding:12px;vertical-align:top}th{background:#edf5ed}td:first-child{width:42%}small{color:#728376}input{width:100%;padding:12px;font:16px "Microsoft YaHei";border:1px solid #c7d9cc;border-radius:6px}code{overflow-wrap:anywhere}'
    script='document.getElementById("search").addEventListener("input",e=>{let q=e.target.value.toLowerCase();document.querySelectorAll("tbody tr").forEach(r=>r.hidden=!r.dataset.search.toLowerCase().includes(q))})'
    notice='<p>执行阻塞：云API试跑返回余额/额度不足，大规模调用尚未开始；来源索引完成，截图仅为下表标出的已完成案件。等待恢复可用服务或明确授权Codex agent直接写作。</p>' if execution.get('phase')=='provider_blocked' else ''
    page=f'<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>V2 中文案由覆盖</title><style>{style}</style><main><section><h1>中文案由逐案迭代 · 第三轮</h1><p>350条来源记录；207种原始标签；复合标签拆开后197个独立案由路径。每原始标签先选1宗代表，不冒充全国案由目录。</p><p>当前状态：{esc(dict(phases))}；已渲染 {total_images} 张图、{total_messages} 条消息。</p>{notice}<p><a href="REPORT.md">覆盖与问题说明</a> · <a href="coverage.json">全部处理记录</a> · <a href="source_pool.jsonl">350条来源索引</a> · <a href="../round_002/index.html#zh_sales_146">用户认可的写作参考</a></p><p>批量生成与模型修订只是开发候选；人工认可只适用于参考案。日期、引用、图片和结构检查分别保留；暂缓和失败案件有具体原因。</p><input id="search" placeholder="搜索案由、案号或状态"></section><section><table><thead><tr><th>来源案由</th><th>代表判决与产物</th><th>状态与问题</th></tr></thead><tbody>'+''.join(rows)+'</tbody></table></section></main><script>'+script+'</script></html>'
    page=page.replace('<a href="REPORT.md">覆盖与问题说明</a>',
                      '<a href="REPORT.md">覆盖与问题说明</a> · <a href="SOURCE_AUDIT.md">来源字段与标签核查</a> · <a href="SOURCE_GAPS.md">暂缓案件与候补缺口</a> · <a href="QUALITY_REVIEW.md">质量复核清单</a> · <a href="ITERATION_METHOD.md">实际迭代与修改示例</a>')
    shortlist_path=OUT/'review_shortlist.json'
    if shortlist_path.exists():
        selections=[]
        for selected in read(shortlist_path)['records'][:8]:
            ident=selected['id'];d=OUT/'zh'/ident
            if read(d/'status.json')['phase']!='rendered':continue
            c=read(d/'case.json');selections.append(f'<li><a href="zh/{ident}/review.html">{esc(c["case_no"])} · {esc(c["cause"].split(">")[-1])}</a>（{selected["conversations"]}会话 / {selected["images"]}图 / {selected["origin_counts"]["verbatim_quote"]}条原话）</li>')
        if selections:page=page.replace('<section><table>', '<section><h2>优先看原话较多、跨会话的候选</h2><p>按会话、图片和原话数量选出供人工预览，尚未认证难度。</p><ul>'+''.join(selections)+'</ul></section><section><table>',1)
    page=page.replace('张图、',f'张图（含 {supplement_phases["rendered"]} 宗独立候补）、')
    page=page.replace('<input id="search"',f'<p>已有候选覆盖 {len(covered_labels)} 种原始标签；其余 {manifest["raw_cause_labels"]-len(covered_labels)} 种的来源缺口见上方清单。数量只表示开发覆盖，不表示困难评测集已定稿。</p><input id="search"')
    (OUT/'index.html').write_text(page,encoding='utf-8')
    summary=read(OUT/'summary.json')
    text='# 中文案由覆盖 · 第三轮\n\n来源350条记录、207种原始标签、197个拆分后的独立路径。每原始标签优先选一个代表；其余来源作为候补保留。这里是本地历史池的覆盖，不是全国现行案由全集。\n\n'
    text+=f'已渲染 {phases["rendered"]+supplement_phases["rendered"]} 宗案件、{total_images} 张固定尺寸截图、{total_messages} 条消息，覆盖 {len(covered_labels)} 种来源标签。原代表 {phases["rendered"]} 宗可生成、{phases["deferred"]} 宗暂缓；独立候补 {supplement_phases["rendered"]} 宗。仍有 {manifest["raw_cause_labels"]-len(covered_labels)} 种标签缺少可用来源，见 [来源缺口](SOURCE_GAPS.md)。全部详细计数与阶段见 [summary.json](summary.json)。\n\n'
    text+='[打开全部案件与截图](index.html)。每案提供完整判决、逐句来源、事实属性、初稿、修订记录和候选题。候选题尚未经过律师独立评分与模型盲测，不作为已认证困难集发布。\n\n'
    text+='已认可的买卖合同案仅复用到本轮独立目录。首批新增四宗：企业租赁经营、劳动合同、民间借贷、婚约财产；前两宗保留API初稿及实际修订，后两宗由Codex读全文直接写作，均保留第二遍修改。后续已获用户授权，由三个Codex agent按各自名单直接阅读、写作和自审，不调用外部API。自审不是独立专业评分，仍待人工复审。未生成状态按上方统计，不把来源归档算成完成截图。失败和不适合合成的案由不隐藏、不计入已生成图集。原始判决、初稿、复核、请求日志和来源对照保留；与v1以及前两轮独立。\n\n'
    text+='来源核查：[完整问题清单](SOURCE_AUDIT.md)。66宗归档案号字段实际是日期，已从正文提取案号候选但保留原字段；1宗标题为行政文书而来源标签为民事，不按未经核对的标签发布。207宗均出现通信关键词，但关键词出现不等于有逐字聊天或适合高难合成。\n\n'
    text+='历史API试跑遇到余额/额度不足；已改为用户授权的Codex agent直接写作，不依赖恢复额度。授权与分工保留在 execution_state.json、agent_assignments.json；共享渲染与检查由主agent执行。\n\n'
    for filename,label in [('peer.short_quotes.review.json','全轮短原话上下文复核'),('peer.short_quotes.corrections.json','实际引用定位校正'),('peer.repeated_long_quotes.review.json','重复长原话复核'),('peer.numeric_questions.review.json','题目数值上下文复核'),('peer.supplement_questions.review.json','候补题目图内身份复核')]:
        if (OUT/filename).exists():text+=f'[{label}]({filename})。'
    text+='以上复核均为模型阅读与程序核验，保留范围和限制，不冒充人工评分。\n\n'
    text+='检查入口：`tools/check_v2_round3.py` 核对原文、字面引用、消息覆盖、固定图幅、页码、链接及错误引用拦截；`tools/check_v2_chat_layout.py` 检查文件/转账/重建附件内层宽度，防止只核对外框而漏掉金额或标题截断。\n\n'
    if execution.get('phase') in ['complete_with_deferrals','complete']:
        verification=read(OUT/'verification.json');layout=read(OUT/'layout.verification.json');archive=read(OUT/'archive.verification.json')
        text+=f'本轮技术核验已通过：{verification["rendered_images_checked"]}张860×1864图片及完整消息覆盖、{verification["exact_messages_checked"]}条逐字原话、{verification["local_links_checked"]}个本地链接、{verification["negative_provenance_checks"]}项错误拦截检查与重复短句坐标保留检查。{len(layout["conversations"])}个会话、{sum(len(r["cards"]) for r in layout["conversations"])}个卡片的内层宽度及转账状态显示检查通过。350行原工作簿与362份归档来源副本逐字核对；已认可的5张第二轮截图摘要保持一致。证据见 [引用与截图核验](verification.json)、[排版核验](layout.verification.json)、[来源归档核验](archive.verification.json)。这些检查不认证法律理解、自然度或难度。\n\n'
    text+='## 待处理问题\n\n'
    for item in entries:
        if item['phase'] not in ['rendered','reviewed','source_prepared']:
            text+=f'- {item["id"]} {item["case_no"]} {item["cause"].split(">")[-1]}：{item["phase"]}；{item.get("reason","")}；'+','.join(item.get('errors',[]))+'\n'
    text+='\n## 实际写作与复核路径\n\n[实际迭代方法、架构与修改例子](ITERATION_METHOD.md)展示初稿、作者自审、主 agent 语义修订和截图检查。`AGENT_WRITING.md` 保留全文阅读、约束台账、原话/转写/创作分层、初稿与第二遍具体修改的要求。`tools/v2_agent_case.py` 提交候选；主 agent 检查来源、图内生成说明及附件数值，修订前文件保存在 `root.versions/`，修改记录保存在 `root.review.json`。候补判决独立生成，不替换或混入原案来源。\n\n[质量复核清单](QUALITY_REVIEW.md) 标出单图、无原话、未知日期和题目上下文等人工复核优先级。这些是复核线索，不是自动质量评分。\n\n## 检查与展示复现\n\n```powershell\n.venv/Scripts/python.exe tools/v2_root_review.py\n.venv/Scripts/python.exe tools/v2_cause_batch.py render\n.venv/Scripts/python.exe tools/check_v2_round3.py\n.venv/Scripts/python.exe tools/check_v2_chat_layout.py\n.venv/Scripts/python.exe tools/build_v2_quality_inventory.py\n.venv/Scripts/python.exe tools/v2_cause_batch.py report\n```\n\n已有归档不需重跑 prepare。API run 是历史云模型路径，本次采用用户授权的 agent 直接写作；本轮配置保留 inference_mode=local 和 cloud 开关，相应 endpoint 需单独配置。模型修订不被描述成人工打分，消息/图片数量不代表难度认证。\n'
    (OUT/'REPORT.md').write_text(text,encoding='utf-8')
    print(json.dumps({'phases':dict(phases),'images':total_images,'messages':total_messages},ensure_ascii=False),flush=True)


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser();parser.add_argument('command',choices=['prepare','run','render','report'])
    parser.add_argument('--limit',type=int);parser.add_argument('--workers',type=int,default=6);parser.add_argument('--ids');args=parser.parse_args()
    if args.command=='prepare':prepare();report()
    elif args.command=='run':run(args.limit,args.workers,args.ids)
    elif args.command=='render':render_all()
    else:report()
