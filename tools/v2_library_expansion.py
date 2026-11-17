"""Inventory the original judgment library; schedule cause-balanced, immutable expansion."""
from __future__ import annotations
import argparse, collections, csv, hashlib, html, io, json, os, re, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub.synthesis import paragraphs
OUT=ROOT/'datasets/v2.0.0/library_expansion_20261106'
RAW=ROOT/'projects/ScreenshotLegalBench_v2/generate_chat/src'
EN=ROOT/'projects/Batch/england_court_dataset/results.enriched.jsonl'
DATE='2026-11-06'

def read(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def save(p,x):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def textsha(s):return hashlib.sha256(s.encode('utf-8')).hexdigest()
def rel(p):return Path(p).relative_to(ROOT).as_posix()

def quota_target():
    config=OUT/'campaign.config.json'
    value=read(config).get('minimum_distinct_judgments_per_cause',10) if config.exists() else 10
    assert isinstance(value,int) and not isinstance(value,bool) and value>0,'Invalid cause quota'
    return value

def review_enabled():
    config=OUT/'campaign.config.json'
    return read(config).get('independent_review_enabled',True) if config.exists() else True

def covered_source_ids(require_independent=True):
    """Deduplicate accepted screenshot sources across the two separately stored tracks."""
    covered={r['document_id'] for r in read(OUT/'current_artifacts.json')['records']}
    for campaign,kind in [(OUT,'source'),(ROOT/'datasets/v2.0.0/fact_constrained_20261106','fact')]:
        verification=campaign/'verification.json'
        if not verification.exists():continue
        for row in read(verification).get('checked',[]):
            if kind=='source' and row.get('group')!='communication':continue
            folder=campaign/'cases'/row['id']
            if require_independent and not (folder/'peer.acceptance.json').exists():continue
            ident=read(folder/'case.json').get('source_judgment_id',row['id'])
            covered.add(ident)
    return covered

def is_quota_judgment(doc):return doc.get('document_type','judgment')=='judgment'

def select_balanced(records,limit,catalog,covered,target=None):
    """Prioritize uncovered causes, then their quota, while retaining the entire library scope."""
    target=quota_target() if target is None else target
    assert target>0 and limit>=0
    def ident(row):return row.get('document_id') or row['id'].removeprefix('fc_')
    counts=collections.Counter(c for key in set(covered) if key in catalog and is_quota_judgment(catalog[key]) for c in set(catalog[key]['causes']))
    available=collections.Counter(c for doc in catalog.values() if is_quota_judgment(doc) for c in set(doc['causes']))
    pending=list(enumerate(records));selected=[]
    while pending and len(selected)<limit:
        def priority(item):
            index,row=item;causes=set(catalog[ident(row)]['causes'])
            eligible=is_quota_judgment(catalog[ident(row)])
            count=min((counts[c] for c in causes),default=target)
            return (not (eligible and count<target),count if eligible else target,min((available[c] for c in causes),default=len(catalog)),index)
        index,row=min(pending,key=priority)
        selected.append(row);pending.remove((index,row))
        if is_quota_judgment(catalog[ident(row)]):counts.update(set(catalog[ident(row)]['causes']))
    return selected
def clean_no(s):return re.sub(r'\s+','',str(s)).replace('（','(').replace('）',')')
def case_number(text, fallback='',lang='zh'):
    if lang=='zh':
        found=re.search(r'[（(]\s*(?:19|20)\d{2}\s*[）)]\s*[\u4e00-\u9fff][\u4e00-\u9fff\d\s第之—-]{2,40}?号',text[:1300])
        return clean_no(found[0]) if found else clean_no(fallback)
    return clean_no(fallback)
def identity(text, number,lang):
    basis=number if number and number not in ['None','nan','null'] else re.sub(r'\s+','',text)
    return lang+'_'+textsha(basis)[:20]
def split_causes(s):
    if not s or str(s).lower() in ['nan','none','null']:return []
    parts=re.split(r';|；|\n|\|',str(s))
    return sorted({x.strip().replace('＞','>') for x in parts if x.strip()})

def inventory():
    target=quota_target()
    OUT.mkdir(parents=True,exist_ok=True)
    docs={};containers=[];errors=[];prior_current={};auxiliary=[];round_rows=[]
    def add(text,number,lang,cause,origin,title='',url='',court='',metadata=None):
        if not isinstance(text,str) or len(text.strip())<200:
            errors.append({'origin':origin,'reason':'missing_or_short_body'});return None
        num=case_number(text,number,lang);key=identity(text,num,lang)
        causes=split_causes(cause) if lang=='zh' else []
        doc=docs.setdefault(key,dict(document_id=key,language=lang,case_no=num,title=title,court=court,
            text=text,text_sha256=textsha(text),causes=[],origins=[],urls=[],variants=[],metadata=metadata or {}))
        doc['origins'].append(origin)
        if url and url not in doc['urls']:doc['urls'].append(url)
        for c in causes:
            if c not in doc['causes']:doc['causes'].append(c)
        if doc['text_sha256']!=textsha(text):doc['variants'].append({'text_sha256':textsha(text),'origin':origin,'chars':len(text)})
        return key
    csv.field_size_limit(20000000)
    for p in sorted(RAW.glob('*.csv')):
        b=p.read_bytes();encoding=None
        for enc in ['utf-8-sig','gb18030']:
            try:raw=b.decode(enc);encoding=enc;break
            except UnicodeError:pass
        if not encoding:raise ValueError('Undecodable source '+str(p))
        count=0
        for i,row in enumerate(csv.DictReader(io.StringIO(raw)),2):
            count+=1;body=row.get('wk-row') or row.get('wk-col-12') or ''
            fields=[row.get('detail-meta-parameter-text'+s,'') for s in ['', ' (2)',' (3)']]
            num=next((v for v in fields if re.search(r'[（(]\d{4}[）)]',v)), '')
            court=next((v for v in fields if '法院' in v), '')
            add(body,num,'zh',row.get('legislation-meta-content'),{'path':rel(p),'row':i,'encoding':encoding},row.get('doc-title',''),row.get('wkb-doc-title-text href',''),court)
        containers.append({'path':rel(p),'sha256':sha(p),'rows':count,'encoding':encoding,'language':'zh','role':'original_csv'})
    with EN.open(encoding='utf-8-sig') as stream:
        count=0
        for i,line in enumerate(stream,1):
            if not line.strip():continue
            a=json.loads(line);count+=1
            add(a.get('judgment_text'),a.get('neutral_citation'),'en','',{'path':rel(EN),'line':i},a.get('title',''),a.get('html_link',''),a.get('court',''),{'court_group':a.get('court'),'cause_classification':'pending_semantic_review'})
    containers.append({'path':rel(EN),'sha256':sha(EN),'rows':count,'language':'en','role':'original_jsonl'})
    source_to_key={}
    v2=ROOT/'datasets/v2.0.0'
    for p in sorted(v2.glob('round_00[1-6]/*/*/source.json'))+sorted((v2/'round_003/zh').glob('*/alternatives/*/source.json')):
        a=read(p);lang=a.get('language') or ('en' if '/en/' in p.as_posix() else 'zh')
        key=add(a.get('text',''),a.get('case_no',''),lang,a.get('cause',''),{'path':rel(p),'role':'archived_source'},a.get('title',''),a.get('url',''))
        source_to_key[rel(p)]=key
    # Source.json may retain the original sample id. The containing directory identifies a rendered version.
    for rnd in range(1,7):
        base=v2/f'round_{rnd:03d}';arts=[]
        for render in sorted(base.glob('*/*/render.json')):
            d=render.parent
            case_path=next((d/n for n in ['case.json','curated.json','final.json'] if (d/n).exists()),None)
            if not (d/'source.json').exists() or case_path is None:continue
            key=source_to_key.get(rel(d/'source.json'));r=read(render)
            paths=[d/(s.get('path') or s['file']) for s in r.get('images',[])]
            if not key or not paths or any(not p.exists() for p in paths):continue
            case=read(case_path)
            art={'document_id':key,'artifact_path':rel(d),'round':base.name,'images':[{'path':rel(p),'sha256':sha(p)} for p in paths],
                 'messages':len(case.get('messages',[])),'questions':len(case.get('questions',[])),'platform':case.get('platform'),'source_medium':case.get('source_medium')}
            arts.append(art)
            if rnd<=4:prior_current[key]=art
        if rnd>=5 and (base/'execution_state.json').exists():
            bypath={a['artifact_path']:a for a in arts}
            for row in read(base/'execution_state.json').get('records',[]):
                source_path=row.get('source_path');src=read(ROOT/source_path) if source_path and (ROOT/source_path).exists() else None
                key=identity(src['text'],case_number(src['text'],src.get('case_no','')),'zh') if src else None
                if row.get('new_sample_status')=='verified':
                    artifact=row.get('artifact_directory');a=bypath.get(artifact)
                    if a is None and artifact:
                        d=ROOT/artifact;r=read(d/'render.json');case=read(d/'case.json')
                        a={'document_id':key,'artifact_path':artifact,'round':base.name,'images':[{'path':rel(d/s['path']),'sha256':sha(d/s['path'])} for s in r['images']], 'messages':len(case['messages']),'questions':len(case['questions']),'platform':case.get('platform'),'source_medium':case.get('source_medium')}
                    if a:prior_current[key]=a
                elif rnd==6 and key:
                    prior_current.pop(key,None)
                    if row.get('auxiliary_only'):auxiliary.append(row)
        round_rows.append({'round':base.name,'artifact_versions':len(arts),'image_references':sum(len(a['images']) for a in arts),'unique_image_hashes':len({i['sha256'] for a in arts for i in a['images']})})
    # Count historical files only within dataset output folders, excluding browser profiles and caches.
    files=[]
    for base,dirs,names in os.walk(v2):
        dirs[:]=[n for n in dirs if n not in ['work','node_modules','.cache','Cache','GPUCache',OUT.name]]
        for name in names:
            if not name.lower().endswith('.png'):continue
            p=Path(base)/name
            if 'assets' in p.parts:continue
            files.append({'path':rel(p),'sha256':sha(p),'is_archive':any('versions' in x for x in p.parts),'is_forwardtest':'round_skill_forwardtest' in p.parts,'is_dependency_variant':any(x.startswith('dependency_') for x in p.parts)})
    raw_images=read(ROOT/'reports/restart/images_manifest.json')
    legacy=[{'path':r['path'],'sha256':sha(ROOT/r['path'])} for r in raw_images if (ROOT/r['path']).exists()]
    for key,doc in docs.items():
        doc['causes']=sorted(doc['causes']);doc['source_chars']=len(doc['text'])
        doc['primary_cause']=doc['causes'][0] if doc['causes'] else None
        doc['existing_current_artifact']=prior_current.get(key)
        doc['communication_keyword_hits']=len(re.findall(r'微信|聊天|WhatsApp|text message',doc['text'],re.I))
        doc['has_quoted_communication_signal']=bool(re.search(r'(?:微信|聊天|发送|发来|回复|WhatsApp)[^\n]{0,120}[“「\"]',doc['text'],re.I))
        doc['document_type']='judgment' if re.search(r'判\s*决\s*书',doc['text'][:600]) or doc['language']=='en' else 'ruling_or_other'
        path=OUT/'sources'/key/'source.json'
        source={'id':key,'source_index':key,'language':doc['language'],'case_no':doc['case_no'],'cause':doc['primary_cause'] or 'UNCLASSIFIED',
            'title':doc['title'],'court':doc['court'],'text':doc['text'],'paragraphs':paragraphs(doc['text']),
            'judgment_text_sha256':doc['text_sha256'],'origins':doc['origins'],'urls':doc['urls'],'document_type':doc['document_type']}
        if path.exists():assert read(path)['text']==source['text'],'Never overwrite a frozen source'
        else:save(path,source)
        doc['source_path']=rel(path);doc.pop('text')
    causes=collections.defaultdict(list)
    for d in docs.values():
        if d['language']=='zh':
            for cause in d['causes']:causes[cause].append(d)
    quotas=[];selected=[]
    for cause,items in sorted(causes.items()):
        current=[x for x in items if x['existing_current_artifact']]
        pending=sorted([x for x in items if not x['existing_current_artifact']],key=lambda x:(not x['has_quoted_communication_signal'],-x['communication_keyword_hits'],x['source_chars'],x['document_id']))
        quotas.append({'cause':cause,'local_distinct_documents':len(items),'current_screenshot_cases':len(current),'minimum_target':target,
                       'local_source_shortfall':max(0,target-len(items)),'screenshot_shortfall':max(0,target-len(current)),
                       'priority_document_ids':[x['document_id'] for x in pending], 'source_count_is_feasible_chat_count':False})
    # Cover underrepresented causes in passes before adding a second source from the same cause.
    order=sorted(quotas,key=lambda q:(q['current_screenshot_cases'],q['local_distinct_documents'],q['cause']))
    queued=set()
    for depth in range(max([len(q['priority_document_ids']) for q in order]+[0])):
        for q in order:
            if depth<len(q['priority_document_ids']):
                key=q['priority_document_ids'][depth]
                if key not in queued:
                    queued.add(key);selected.append({'document_id':key,'source_path':docs[key]['source_path'],'cause':q['cause'],'pass':depth+1,'status':'pending_full_read'})
    en_pending=[{'document_id':d['document_id'],'source_path':d['source_path'],'cause':None,'status':'pending_cause_classification'} for d in docs.values() if d['language']=='en' and not d['existing_current_artifact']]
    summary={'as_of':DATE,'unique_documents':len(docs),'languages':dict(collections.Counter(d['language'] for d in docs.values())),
        'document_types':dict(collections.Counter(d['document_type'] for d in docs.values())),
        'chinese_cause_labels':len(causes),'chinese_unclassified':sum(d['language']=='zh' and not d['primary_cause'] for d in docs.values()),
        'minimum_distinct_judgments_per_cause':target,
        'source_available_target_causes':sum(q['local_distinct_documents']>=target for q in quotas),
        'source_shortfall_to_target_total':sum(q['local_source_shortfall'] for q in quotas),
        'current_distinct_rendered_documents':len(prior_current),'current_languages':dict(collections.Counter(docs[k]['language'] for k in prior_current)),
        'current_image_pages':sum(len(a['images']) for a in prior_current.values()),'current_unique_image_hashes':len({i['sha256'] for a in prior_current.values() for i in a['images']}),
        'v2_historical_png_files':len(files),'v2_historical_unique_png_hashes':len({x['sha256'] for x in files}),
        'legacy_benchmark_image_files':len(legacy),'legacy_unique_image_hashes':len({x['sha256'] for x in legacy}),
        'all_legacy_and_v2_unique_image_hashes':len({x['sha256'] for x in files+legacy}),
        'chinese_pending_source_count':len(selected),'english_pending_classification':len(en_pending),
        'auxiliary_sources_not_counted_as_chat':len(auxiliary),'counts_are_not_professional_gold':True}
    save(OUT/'summary.json',summary);save(OUT/'source_catalog.json',{'records':list(docs.values()),'containers':containers,'errors':errors})
    save(OUT/'cause_quotas.json',{'minimum_distinct_judgments_per_cause':target,'multi_label_overlap_allowed_per_cause':True,'global_cases_deduplicated':True,'records':quotas})
    save(OUT/'current_artifacts.json',{'records':list(prior_current.values()),'latest_review_overrides_old_versions':True,'auxiliary':auxiliary})
    save(OUT/'image_inventory.json',{'v2':files,'legacy':legacy,'round_counts':round_rows})
    save(OUT/'queue.json',{'chinese':selected,'english':en_pending,'policy':f'all_library_documents; low_coverage_causes_first; at_least_{target}_distinct_documents_per_cause; missing_sources_require_acquisition'})
    report();print(json.dumps(summary,ensure_ascii=False))

def configure(minimum):
    """Change quota metadata without rebuilding or overwriting the frozen source inventory."""
    import shutil
    from datetime import datetime,timezone
    assert isinstance(minimum,int) and minimum>0
    if (OUT/'runner.status.json').exists():
        assert read(OUT/'runner.status.json')['phase'] in ['stopped','needs_attention'],'Stop the coordinator before reconfiguration'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    backup=OUT/'configuration.versions'/stamp
    for name in ['campaign.config.json','campaign.json','summary.json','cause_quotas.json','cause_progress.json','queue.json','expansion_summary.json','INVENTORY.md','PROGRESS.md','index.html','runner.status.json','STOP']:
        src=OUT/name
        if src.exists():
            backup.mkdir(parents=True,exist_ok=True);shutil.copyfile(src,backup/name)
    catalog=read(OUT/'source_catalog.json')['records']
    quota=read(OUT/'cause_quotas.json');quota['minimum_distinct_judgments_per_cause']=minimum
    for row in quota['records']:
        row['minimum_target']=minimum
        row['local_distinct_judgments']=sum(row['cause'] in doc['causes'] and is_quota_judgment(doc) for doc in catalog)
        row['local_source_shortfall']=max(0,minimum-row['local_distinct_judgments'])
        row['screenshot_shortfall']=max(0,minimum-row['current_screenshot_cases'])
    save(OUT/'cause_quotas.json',quota)
    config=read(OUT/'campaign.config.json') if (OUT/'campaign.config.json').exists() else {}
    config.update({'minimum_distinct_judgments_per_cause':minimum,'scope':'all_local_library_sources',
            'quota_document_type':'judgment','priority':'different_causes_then_below_quota_then_rest_of_library',
            'counting_basis':'deduplicated accepted source IDs across separately stored dataset tracks',
            'user_instruction_date':'2026-11-12','updated_utc':datetime.now(timezone.utc).isoformat(),
            'previous_configuration_snapshot':rel(backup),'professional_gold':False})
    save(OUT/'campaign.config.json',config)
    campaign=read(OUT/'campaign.json');campaign.update(goal=f'all library judgments; >={minimum} distinct judgments per cause',minimum_distinct_judgments_per_cause=minimum,completed=False)
    save(OUT/'campaign.json',campaign)
    summary=read(OUT/'summary.json')
    for name in ['source_available_10_causes','source_shortfall_to_10_total']:summary.pop(name,None)
    summary.update(minimum_distinct_judgments_per_cause=minimum,
                   source_available_target_causes=sum(not row['local_source_shortfall'] for row in quota['records']),
                   source_shortfall_to_target_total=sum(row['local_source_shortfall'] for row in quota['records']))
    save(OUT/'summary.json',summary)
    queue=read(OUT/'queue.json');queue['policy']=f'all_library_documents; accepted_low_coverage_causes_first; at_least_{minimum}_distinct_judgments_per_cause; missing_sources_reported_separately'
    save(OUT/'queue.json',queue)
    report()
    print(json.dumps(config,ensure_ascii=False))

def report():
    target=quota_target()
    summary=read(OUT/'summary.json');quotas=read(OUT/'cause_quotas.json')['records']
    s='# 全库盘点与按案由扩充\n\n统计日期：'+DATE+'。中文以正文首部案号去重，英文以中立引证去重；正文变体和原文件位置另行保存。这里只统计库内已取得正文的裁判文书。\n\n'
    s+='```json\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n```\n\n'
    s+='当前截图取每份判决的最新可用版本，服从第六轮撤回与辅助材料决定；历史PNG包括旧版、回滚与复现副本。V1历史评测截图未逐张重新认定真实/合成来源，故单列。案由是来源的历史标签，不是已完成法律复核的现行分类。英文按法院分类的信息不能替代案由，需逐案补标。\n\n'
    s+='原始CSV按各文件实际编码读取；已发现旧 parsed.jsonl 把部分UTF-8劳动/IP/特殊程序材料误解码。本次从原CSV重建，原文件不改写。一份文书可以有多个原始案由标签，每个标签内去重计数；全库总量仍只计一份，表内数量不可直接求和。来源量不足10的类别保留缺口，候选量不等于可合成聊天量。\n\n'
    s+='|案由|库内不同文书|当前聊天案件|最低目标|需外部补来源至少|\n|---|---:|---:|---:|---:|\n'
    for q in sorted(quotas,key=lambda q:(q['current_screenshot_cases'],q['cause'])):
        s+=f'|{q["cause"]}|{q["local_distinct_documents"]}|{q["current_screenshot_cases"]}|{target}|{q["local_source_shortfall"]}|\n'
    (OUT/'INVENTORY.md').write_text(s,encoding='utf-8')
    rows=''.join('<tr><td>'+html.escape(q['cause'])+'</td><td>'+str(q['local_distinct_documents'])+'</td><td>'+str(q['current_screenshot_cases'])+'</td><td>'+str(q['local_source_shortfall'])+'</td></tr>' for q in sorted(quotas,key=lambda q:(q['current_screenshot_cases'],q['cause'])))
    (OUT/'index.html').write_text('<!doctype html><meta charset="utf-8"><title>全库案由扩充</title><style>body{font:16px/1.7 sans-serif;max-width:1250px;margin:30px auto;padding:20px}td,th{padding:9px;border-bottom:1px solid #ddd}input{padding:10px;width:80%}table{width:100%}</style><h1>全库盘点与案由扩充</h1><p>每个案由至少10份不同判决；优先低覆盖类别。</p><p><a href="INVENTORY.md">统计口径与完整报告</a> · <a href="queue.json">全量队列</a></p><input id="q" placeholder="筛选案由" oninput="for(const r of document.querySelectorAll(\'tbody tr\'))r.hidden=!r.textContent.includes(this.value)"><table><thead><tr><th>案由</th><th>库内文书</th><th>当前聊天案</th><th>来源缺口</th></tr></thead><tbody>'+rows+'</tbody></table>',encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('command',choices=['inventory','report','configure']);p.add_argument('--minimum',type=int,default=3);a=p.parse_args()
    if a.command=='configure':configure(a.minimum)
    else:globals()[a.command]()
