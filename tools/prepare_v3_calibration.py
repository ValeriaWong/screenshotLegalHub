"""Build four author-stage V3 cases and isolated blind review packages. No API calls."""
import argparse, copy, hashlib, html, importlib.util, itertools, json, re, shutil, sys, zipfile
from collections import Counter
from pathlib import Path
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def dump(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
def jsonl(p, rows):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(''.join(json.dumps(r, ensure_ascii=False)+'\n' for r in rows), encoding='utf-8')
def read(p): return json.loads(p.read_text(encoding='utf-8'))
def module(p):
    spec=importlib.util.spec_from_file_location('v3_frozen_render',p)
    result=importlib.util.module_from_spec(spec);spec.loader.exec_module(result);return result

def locate(source, ref):
    quote=ref['quote']; start=ref.get('char_start'); end=ref.get('char_end')
    if start is not None and source['text'][start:end]==quote:
        method='original_exact_span'
    else:
        paragraphs=[p for p in source['paragraphs'] if p['id']==ref.get('source_id')]
        offset=paragraphs[0]['text'].find(quote) if paragraphs else -1
        if offset>=0:
            start=paragraphs[0]['char_start']+offset;end=start+len(quote);method='located_exactly_in_declared_paragraph'
        else:
            matches=[m.start() for m in re.finditer(re.escape(quote),source['text'])]
            if len(matches)!=1:
                return dict(original_ref=ref,status='unresolved',uncertainty='Quote missing or ambiguous; do not use as verified source.')
            start=matches[0];end=start+len(quote);method='unique_full_text_match_check_paragraph_scope'
    assert source['text'][start:end]==quote
    return dict(quote=quote,char_start=start,char_end=end,method=method,status='exact_text_located',original_ref=ref)

def legacy_field(label):
    if re.search(r'打分理由|扣分理由|修改要点|缺点|评分说明|^说明$',label):
        return 'qualitative_feedback',['provenance','naturalness','facts','time','uncertainty']
    if re.search(r'spearman|point_|系数|insight|是否差距|计数|平均分|显著异常|差距变小',label,re.I):
        return 'historical_aggregate_or_comparison',[]
    if re.search(r'打分|分值',label): return 'legacy_scalar_score',[]
    if re.search(r'修正.*剧本|inference|推理结果|查找引用',label,re.I): return 'candidate_or_reference_text',['provenance','naturalness']
    if re.search(r'prompt|变量|优化方向',label,re.I): return 'historical_prompt_or_hypothesis',['provenance']
    return 'source_or_run_metadata',[]

def prepare_s1(snapshot,out,config,spec):
    ledger=[]; scopes=[]; source_stats=[]
    for i, candidate in enumerate(spec['candidates']):
        directory=snapshot/candidate['directory']; source=read(directory/'source.json'); case=read(directory/candidate['candidate_file'])
        scenario=next(s for s in config['scenarios'] if s['source']==i)
        scopes.append(dict(case_id=scenario['id'],language=scenario['language'],platform='wechat' if scenario['language']=='zh' else 'whatsapp',
            source_case_id=source['id'],source_case_no=source['case_no'],source_jurisdiction=source['jurisdiction'],
            jurisdiction='not_assigned_for_synthetic_intermediate_task',relevant_event_period=scenario['period'],
            allowed_background=[],task_scope='screenshot_only_intermediate_judgments_no_legal_consequences',
            source_family_id=source['judgment_text_sha256'],template_family_id=scenario['template'],split='development',
            source_class='synthetic_adaptation_with_reviewer_only_theme_anchors',identity_boundary='displayed accounts only; real identities unknown',
            time_boundary='new scenario dates are explicitly synthetic; old invented layout minutes are not historical facts',
            review_roles=dict(author='assistant_author',reviewer_a=None,reviewer_b=None,adjudicator=None),source_path=(directory/'source.json').relative_to(ROOT).as_posix()))
        counts=Counter()
        for m in case['messages']:
            refs=[locate(source,r) for r in m.get('source_refs',[])]
            counts.update(r['status'] for r in refs)
            for ref in refs:
                ref['file']=(directory/'source.json').relative_to(ROOT).as_posix(); ref['file_sha256']=sha(directory/'source.json')
            # Preserve all historical timestamps, but never infer event times from generated layout.
            ledger.append(dict(fact_id=source['id']+'.'+m['id'],statement=m.get('text',''),attachment=m.get('attachment'),
                assertion_type='candidate_message_statement_not_verified_occurrence',speaker=m['sender_id'],account=m['sender_id'],party='unknown',
                time_raw=m.get('timestamp') or m.get('time_label'),normalized_time=m.get('timestamp') if m.get('time_basis')=='source' else None,
                time_precision='source_claimed' if m.get('time_basis')=='source' else 'unknown_historical_precision',
                origin_type=m.get('origin_type','unknown'),source_refs=refs,candidate_file=(directory/candidate['candidate_file']).relative_to(ROOT).as_posix(),
                candidate_json_pointer='/messages/'+str(case['messages'].index(m)),uncertainty=['Exact textual location is not semantic verification.',
                'Displayed names and generated minutes do not certify identity or historical timing.'],semantic_review='pending_independent_review'))
        source_stats.append(dict(case_id=source['id'],messages=len(case['messages']),**counts))
    dimensions=[('facts','只抽取可见陈述；不把陈述当真实发生'),('identity','账号/主体/事项关联须有可见桥梁'),('time','区分显示时间、提及时间、精度与未知'),
        ('conditions','前提、替代支持与反证分别列明'),('intent','收件、提议、同意、拒绝分开'),('conclusion','限定到问题允许的判断层级'),
        ('citations','页面/原句/坐标有效且实际支持主张'),('uncertainty','明确缺什么；未证明满足与证明不满足分开'),
        ('provenance','原文、转述、附件重建、合成补充、反事实分开'),('naturalness','称呼、回复目标、时间和会话语境连贯'),('legal','法律后果需规则来源及对应法域审核')]
    rubric=dict(version='v3-calibration-1',status='author_operational_protocol',dimensions=[dict(id=k,definition=v,
        scale={'0':'unsupported, contradicted or wrong','1':'partly supported; material omission','2':'fully supported within allowed scope'},
        allowed_special=['not_applicable','not_observable','ambiguous']) for k,v in dimensions],
        scoring_rules=['No aggregate-only accuracy: report each applicable dimension and its denominator.',
        'not_applicable is not full credit; not_observable requires a specific missing premise.',
        'ambiguous candidates go to revision; do not silently add them to a scored gold set.',
        'Legal dimension is not_applicable for these four intermediate tasks.',
        'Joint correctness requires all necessary nodes, scoped conclusion and valid supporting citations.',
        'Author node/subset ranges are proposals awaiting two independent semantic reviews.'])
    fields={}; row_mapping=[]; seen=set()
    audit=ROOT/'datasets/v3.0.0/source_audit_20261023_002'
    checks=[json.loads(line) for line in (audit/'legacy_score_checks.jsonl').read_text(encoding='utf-8').splitlines()]
    original={f:read(snapshot/f) for f in spec['reference_files']}
    for check in checks:
        row=original[check['reference_file']][check['record_index']]; ids=[]
        for cell in row['cells']:
            key='|'.join([row['workbook'],row['sheet'],cell['column'],str(cell['label'])])
            category, targets=legacy_field(str(cell['label']))
            value=fields.setdefault(key,dict(field_id=hashlib.sha256(key.encode()).hexdigest()[:16],workbook=row['workbook'],sheet=row['sheet'],
                column=cell['column'],label=cell['label'],category=category,v3_dimensions=targets,observed_nonempty_cells=0,
                numeric_conversion_allowed=False,semantic_equivalence=False,
                rule='Preserve historical value. Qualitative pointers require re-review; no old score certifies V3 sufficiency/minimality.'))
            value['observed_nonempty_cells']+=1;ids.append(value['field_id'])
        row_mapping.append(dict(row_id=check['row_id'],reference_file=check['reference_file'],record_index=check['record_index'],
            workbook_sha256=check['workbook_sha256'],sheet=check['sheet'],excel_row=check['excel_row'],cells_sha256=check['actual_cells_sha256'],
            usable_for_mapping=check['usable_for_mapping'],duplicate_reference=check['row_id'] in seen,field_ids=ids))
        seen.add(check['row_id'])
    dump(out/'case_scope.json',scopes); jsonl(out/'fact_ledger.jsonl',ledger);dump(out/'rubric.json',rubric)
    dump(out/'legacy_rubric_mapping.json',dict(fields=list(fields.values()),rows=row_mapping,
        conflict_resolution=['Legacy hypotheses permitting invented dialogue without deduction are not V3 source truth.',
        'V3 permits explicitly labelled synthetic tasks; hidden or mislabeled additions cannot supply visible premises.',
        'Old 0–5 scores and correlation metrics remain historical; no numeric conversion to node/independence certification.'],
        missing_dimensions=['exhaustive subset sufficiency','minimality witnesses','alternative support paths','independent reviewer agreement','legal rules by effective date'],
        empty_records_excluded=sum(not r['usable_for_mapping'] for r in row_mapping)))
    dump(out/'sampling_plan.json',dict(batch='calibration',base_scenarios=4,language_targets={'zh':2,'en':2},
        template_families=[s['template'] for s in config['scenarios']],split='development',heldout_count=0,
        future_target=20,extension_condition='Complete calibration independent review and repair returned cases first.',
        grouping=['source_judgment_hash','template_family','all_counterfactual_and_packaging_derivatives'],
        no_independent_sample_inflation=True,reviewers_required=2,reviewers_assigned=False,adjudicator_assigned=False))
    return ledger,source_stats


def author_range(scenario, visible_units, counterfactual=False):
    observed=set(visible_units); supported=set(); answers=[]; missing=[]
    for node in scenario['nodes']:
        ok=set(node.get('units',[]))<=observed and set(node.get('depends_on',[]))<=supported
        if ok:
            supported.add(node['id'])
            answers.append(dict(node_id=node['id'],claim=node.get('counterfactual_answer',node['answer']) if counterfactual else node['answer']))
        elif not node.get('optional'):
            missing.append(dict(node_id=node['id'],missing_units=sorted(set(node.get('units',[]))-observed),
                                missing_nodes=sorted(set(node.get('depends_on',[]))-supported)))
    return dict(status='author_proposed_not_certified',observable_claims=answers,missing_requirements=missing,
                answerability='full_scoped_answer_proposed' if not missing else 'partial_or_insufficient',
                universal_boundary='Do not infer real-world occurrence, identity, receipt or legal validity from unverified dialogue.',
                alternative_worlds=scenario['witnesses'])


def messages_for(scenario, variant):
    units=copy.deepcopy(scenario['units'])
    if variant=='counterfactual':
        cf=scenario['counterfactual']; row=units[cf['unit']-1][cf['message']]
        assert row[1].count(cf['before'])==1
        row[1]=row[1].replace(cf['before'],cf['after'])
    if variant=='distractor': units.append(scenario['distractor'])
    messages=[]
    for unit,rows in enumerate(units,1):
        date=scenario['dates'][min(unit-1,3)]
        for index,(sender,text) in enumerate(rows):
            messages.append(dict(id=f'{scenario["id"]}.u{unit}.m{index+1}',unit=unit,sender_id=sender,text=text,kind='text',
                conversation_id=scenario['id'],timestamp=date+'T00:00:00',minute_basis='source_day_only',
                origin_type='counterfactual' if variant=='counterfactual' and unit==scenario['counterfactual']['unit'] and index==scenario['counterfactual']['message'] else 'synthetic_adaptation',
                historical_time=None,date_basis='synthetic_scenario_date_only'))
    return messages


def render_variant(renderer,browser,scenario,variant,directory):
    directory.mkdir(parents=True)
    messages=messages_for(scenario,variant)
    people={chr(97+i):dict(id=chr(97+i),name=name) for i,name in enumerate(scenario['people'])}
    conv=dict(id=scenario['id'],title='项目对账' if scenario['id']=='zh_sales' else '工作通知' if scenario['language']=='zh' else 'Family updates' if scenario['id']=='en_probate' else 'Fixture updates',
              viewer_id='b',participant_ids=list(people),is_group=True)
    units=[[i] for i in range(1,6 if variant=='distractor' else 5)]
    if variant=='repagination': units=[[1,2],[3],[4]]
    if variant=='reverse_order': units.reverse()
    pages=[];refs=[];platform='wechat' if scenario['language']=='zh' else 'whatsapp'
    for number,page_units in enumerate(units,1):
        subset=[m for unit in page_units for m in messages if m['unit']==unit]
        rows=''.join(renderer.message_html(m,conv,people,subset[i-1] if i else None,platform) for i,m in enumerate(subset))
        css=renderer.CSS+'\n.wa .bubble .time{display:none}.content{background-image:none!important}.header{min-height:58px}'
        content='<!doctype html><html><meta charset="utf-8"><style>'+css+'</style><body><div class="phone '+('wa' if platform=='whatsapp' else '')+'"><div class="status">9:41</div><div class="header"><div class="title">'+html.escape(conv['title'])+'<div class="subtitle">'+('当前账号：' if scenario['language']=='zh' else 'Viewing as ')+html.escape(people[conv['viewer_id']]['name'])+'</div></div></div><div class="content">'+rows+'</div><div class="input"><div class="input-box"></div></div><div class="footnote">SYNTHETIC · RESEARCH SAMPLE</div></div></body></html>'
        if platform=='wechat' and hasattr(renderer,'phone_html'):
            # New snapshots use the same WeChat shell as V2. Frozen renderers
            # without this helper retain their exact legacy layout above.
            css=renderer.CSS+'\n.wa .bubble .time{display:none}.content{background-image:none!important}'
            content='<!doctype html><html><meta charset="utf-8"><style>'+css+'</style><body>'+renderer.phone_html(conv,people,platform,rows)+'</body></html>'
        file=directory/f'p{number:02d}.html';file.write_text(content,encoding='utf-8');browser.load(file)
        boxes=browser.evaluate('Array.from(document.querySelectorAll(".row"),x=>{let b=x.getBoundingClientRect(),c=document.querySelector(".content").getBoundingClientRect();return {message_id:x.dataset.id,bbox:[b.x,b.y,b.x+b.width,b.y+b.height],content_bottom:c.bottom,text:x.innerText}})')
        for box in boxes:
            x1,y1,x2,y2=box['bbox']
            if not (0<=x1<x2<=430 and 0<=y1<y2<=box['content_bottom']):
                raise ValueError(f'Clipped page {scenario["id"]}/{variant}/{number}')
        png=directory/f'p{number:02d}.png';browser.capture(png)
        with Image.open(png) as im: assert list(im.size)==[860,1864]
        page_id=f'{scenario["id"]}.{variant}.p{number:02d}'
        pages.append(dict(image_id=page_id,file=png.name,sha256=sha(png),width=860,height=1864,units=page_units,
                          input_page=number,evidence_page=None,message_ids=[m['id'] for m in subset]))
        for box in boxes:
            refs.append(dict(message_id=box['message_id'],image_id=page_id,image_sha256=sha(png),input_page=number,evidence_page=None,
                bbox=[round(v*2) for v in box['bbox']],bbox_scope='whole_message_row_including_displayed_date_and_sender',
                coordinate_format='xyxy_pixels',conversation_id=scenario['id'],rendered_text=box['text']))
    assert {r['message_id'] for r in refs}=={m['id'] for m in messages}
    jsonl(directory/'messages.jsonl',messages);dump(directory/'render_manifest.json',dict(pages=pages,viewport=[430,932],scale=2,
        style_version=getattr(renderer,'STYLE_VERSION','frozen-legacy'),effective_css_sha256=hashlib.sha256(css.encode()).hexdigest(),
        css_delta='hide synthetic minutes; omit background image; constant group header',font_policy='frozen renderer CSS / Windows installed fonts'))
    return messages,pages,refs


def build(root_output):
    config=read(ROOT/'configs/v3/calibration_scenarios.json');snapshot=ROOT/config['source_baseline']/'snapshot'
    spec=read(snapshot/'configs/v3/source_audit.json')
    out=ROOT/root_output
    if not out.resolve().is_relative_to(ROOT/'datasets/v3.0.0'): raise ValueError('Output outside V3 datasets')
    out.mkdir(parents=True,exist_ok=False);(out/'.incomplete').write_text('preparing',encoding='utf-8')
    dump(out/'author_config.snapshot.json',config)
    ledger,source_stats=prepare_s1(snapshot,out,config,spec)
    renderer=module(snapshot/'tools/render_v2_round2.py');renderer.ROOT=out/'work'
    all_refs=[];all_messages=[];questions=[];graphs=[];conditions=[];answers=[];subsets=[];author_checks=[]
    blind_tasks=[]
    with renderer.Browser('calibration') as browser:
        browser.call('Network.enable');browser.call('Network.setBlockedURLs',{'urls':['http://*','https://*']})
        browser_version=browser.call('Browser.getVersion')
        for scenario in config['scenarios']:
            qid=scenario['id']+'.q1'
            questions.append(dict(question_id=qid,question_version=1,question=scenario['question'],scope='synthetic_screenshot_only_intermediate',
                allowed_inputs=['question','scope','image_bytes'],required_operations=[n['operation'] for n in scenario['nodes']],
                answerability_type='scoped_multipart_with_explicit_unknowns',accepted_answer_range_ref='author_answers.reviewer_only.jsonl',status='author_candidate'))
            nodes=[]; dependencies={}
            for node in scenario['nodes']:
                support=set(node.get('units',[]))
                for parent in node.get('depends_on',[]):support.update(dependencies[parent])
                dependencies[node['id']]=support
                nodes.append(dict(node_id=node['id'],operation=node['operation'],depends_on=node.get('depends_on',[]),target_claim=node['answer'],
                    required_or_optional='optional' if node.get('optional') else 'required',
                    source_refs=[dict(message_id=f'{scenario["id"]}.u{u}.m{m}',image_id=f'{scenario["id"]}.base.p{u:02d}') for u in sorted(support) for m in [1,2]],
                    alternative_supports=[],counterevidence_refs=[],missing_evidence='See each subset author range; occurrence/real identity not certified.'))
            graphs.append(dict(question_id=qid,nodes=nodes,alternative_supports='Reviewer must inspect; author proposes none beyond the listed paths.',
                               counterevidence_refs='All four base units retained in full condition; optional nodes are not automatically necessary.',certification='pending'))
            for variant in ['base','counterfactual','reverse_order','repagination','distractor']:
                directory=out/'cases'/scenario['id']/variant
                messages,pages,refs=render_variant(renderer,browser,scenario,variant,directory)
                all_refs.extend(dict(variant=variant,**r) for r in refs)
                if variant=='base':
                    all_messages.extend(messages)
                    for m in messages:
                        ledger.append(dict(fact_id=m['id'],statement=m['text'],assertion_type='synthetic_message_statement',speaker=m['sender_id'],account=m['sender_id'],party='unknown',
                            time_raw=m['timestamp'][:10],normalized_time=m['timestamp'][:10],time_precision='day_in_synthetic_scenario_only',origin_type='synthetic_adaptation',
                            source_refs=[dict(file=(directory/'messages.jsonl').relative_to(ROOT).as_posix(),message_id=m['id'])],
                            theme_anchor_fact_ids=[spec['candidates'][scenario['source']]['directory'].split('/')[-1]+'.'+v for v in scenario['anchors']],
                            uncertainty=['New dialogue, names and premise bridges are invented; theme anchors do not attest these words or events.']))
                condition=dict(condition_id=scenario['id']+'.'+variant,parent_id=scenario['id']+'.base' if variant!='base' else None,
                    intervention_type=variant,changed_semantic_variable=scenario['counterfactual']['variable'] if variant=='counterfactual' else None,
                    expected_change=scenario['counterfactual']['expected'] if variant=='counterfactual' else 'Preserve base semantic facts' if variant!='distractor' else 'Ignore explicitly separate matter',
                    affected_messages=[scenario['id']+f'.u{scenario["counterfactual"]["unit"]}.m{scenario["counterfactual"]["message"]+1}'] if variant=='counterfactual' else [],
                    pages=pages,certification_status='not_reviewed')
                conditions.append(condition)
                for mask in range(2**len(pages)):
                    selected=[page for i,page in enumerate(pages) if mask&(1<<i)]
                    visible=sorted({u for p in selected for u in p['units']})
                    sid=condition['condition_id']+f'.subset{mask:02d}'
                    record=dict(subset_id=sid,question_id=qid,condition_id=condition['condition_id'],image_ids=[p['image_id'] for p in selected],visible_units=visible,
                                exhaustive_page_count=len(pages),is_full=len(selected)==len(pages),is_empty=not selected)
                    subsets.append(record);answers.append(dict(subset_id=sid,**author_range(scenario,visible,variant=='counterfactual')))
                    # Only white-listed question, scope and copied images enter each reviewer's package.
                    blind_tasks.append(dict(task_id=f't{len(blind_tasks)+1:04d}',question_id=qid,question=scenario['question'],
                        scope='All images depict invented research conversations. Evaluate only visible statements and cited support; no outside facts or legal validity.',
                        images=[dict(source=(directory/p['file']).relative_to(out).as_posix(),sha256=p['sha256']) for p in selected],
                        reviewer_identity=None,answer=None,citations=[],missing_evidence=[],sufficiency=None,minimality=None,
                        alternative_supports=[],counterevidence=[],ambiguity=None,reviewed_at=None))
                author_checks.append(dict(case_id=scenario['id'],variant=variant,checks=dict(no_question_contains_hidden_account_link=True,
                    dates_and_speakers_visible=True,no_minute_claim_from_layout=True,source_fiction_separated=True,
                    semantic_change_review='single amount / stance / endorsement / forwarding time; context kept explicit',
                    naturalness='author_self_review_only'),independent_review=False))
    # Prove packaging invariance and that the counterfactual modifies exactly the declared field.
    for scenario in config['scenarios']:
        base=messages_for(scenario,'base');cf=messages_for(scenario,'counterfactual')
        changed=[(a['id'],key) for a,b in zip(base,cf) for key in a if a[key]!=b[key]]
        assert len(changed)==2 and {key for _,key in changed}=={'text','origin_type'}
        for variant in ['reverse_order','repagination']:
            assert messages_for(scenario,variant)==base
        assert messages_for(scenario,'distractor')[:len(base)]==base
    jsonl(out/'messages.jsonl',all_messages);jsonl(out/'fact_ledger.jsonl',ledger);jsonl(out/'questions.jsonl',questions)
    jsonl(out/'dependency_graphs.jsonl',graphs);jsonl(out/'source_refs.jsonl',all_refs);jsonl(out/'subset_manifest.jsonl',subsets)
    jsonl(out/'interventions.jsonl',conditions);jsonl(out/'author_answers.reviewer_only.jsonl',answers)
    jsonl(out/'author_self_review.jsonl',author_checks)
    proposals=[]
    answer_by_id={a['subset_id']:a for a in answers}
    for condition in conditions:
        selected=[s for s in subsets if s['condition_id']==condition['condition_id']]
        sufficient=[s['image_ids'] for s in selected if answer_by_id[s['subset_id']]['answerability']=='full_scoped_answer_proposed']
        minimal=[items for items in sufficient if not any(set(other)<set(items) for other in sufficient)]
        proposals.append(dict(question_version=1,condition_id=condition['condition_id'],evidence_scope='supplied synthetic screenshots only',unit_type='page',
            sufficient_sets=sufficient,inclusion_minimal_sets=minimal,minimum_cardinality=min(map(len,sufficient)) if sufficient else None,
            subsets_checked=len(selected),search_exhaustive=True,reviewer_ids=[],status='author_proposed_not_certified',
            witnesses='alternative_interpretations.jsonl',defeaters_checked='author self-review only; reviewers must challenge these sets',
            semantic_review='pending',sufficiency_review='pending',minimality_review='pending',dependency_review='pending',legal_review='not_applicable_intermediate_task'))
    jsonl(out/'author_sufficiency_proposals.reviewer_only.jsonl',proposals)
    jsonl(out/'alternative_interpretations.jsonl',[dict(case_id=s['id'],witnesses=s['witnesses'],status='author_proposed') for s in config['scenarios']])
    # Packages are isolated folders/ZIPs; they never include graph, author answer or intervention labels.
    for reviewer in ['a','b']:
        folder=out/'blind_review'/('reviewer_'+reviewer);folder.mkdir(parents=True)
        package_tasks=copy.deepcopy(blind_tasks)
        image_names={}
        for task in package_tasks:
            for item in task['images']:
                source=item.pop('source');name=image_names.setdefault(source,f'images/{len(image_names)+1:04d}.png')
                dest=folder/name;dest.parent.mkdir(exist_ok=True)
                if not dest.exists():shutil.copyfile(out/source,dest)
                item['file']=name
        dump(folder/'tasks.json',package_tasks);dump(folder/'rubric.json',read(out/'rubric.json'))
        dump(folder/'reviewer.json',dict(reviewer_id=None,display_name=None,independent_of_author=None,worked_without_other_review=None,
            reviewed_at=None,scope='intermediate factual tasks; legal certification not requested'))
        groups=[]
        for index,condition in enumerate(conditions):
            task_ids=[task['task_id'] for task,subset in zip(package_tasks,subsets) if subset['condition_id']==condition['condition_id']]
            groups.append(dict(group_id=f'g{index+1:03d}',question_id=next(s['question_id'] for s in subsets if s['condition_id']==condition['condition_id']),
                task_ids=task_ids,unit_type='page',subsets_checked=None,sufficient_sets=None,inclusion_minimal_sets=None,minimum_cardinality=None,
                witnesses=None,defeaters_checked=None,semantic_review=None,dependency_review=None,ambiguity_resolution=None,
                legal_review='not_applicable_intermediate_task',status='unreviewed'))
        dump(folder/'case_reviews.json',groups)
        page='<!doctype html><meta charset="utf-8"><title>Independent review '+reviewer.upper()+'</title><style>body{font:16px sans-serif;max-width:1100px;margin:30px auto}img{width:300px;vertical-align:top}article{border-top:1px solid #ccc;padding:20px 0}</style><h1>Independent review '+reviewer.upper()+'</h1><p>Fill tasks.json independently. Null fields mean unreviewed. Do not access author answers or the other reviewer. Page subsets are separate tasks; zero images means no visual evidence. Original evidence-page numbers are unknown; cite displayed input positions.</p>'
        for task in package_tasks:
            page+='<article><h2>'+task['task_id']+'</h2><p>'+html.escape(task['question'])+'</p><p>'+html.escape(task['scope'])+'</p>'
            page+=''.join('<img alt="Input '+str(i+1)+'" src="'+item['file']+'">' for i,item in enumerate(task['images'])) or '<p>No images</p>'
            page+='</article>'
        (folder/'index.html').write_text(page,encoding='utf-8')
        with zipfile.ZipFile(out/'blind_review'/('reviewer_'+reviewer+'.zip'),'x',zipfile.ZIP_DEFLATED) as archive:
            for file in sorted(folder.rglob('*')):
                if file.is_file():archive.write(file,file.relative_to(folder).as_posix())
    dump(out/'evaluation_plan.json',dict(status='blocked_before_any_model_call',split='development_only',heldout_count=0,
        input_allowlist=['question','scope','image_bytes'],excluded_fields=['author_answers','dependency_graphs','review_notes','expected_change','source_judgments'],
        proposed_model_configurations=2,proposed_repeats=3,task_conditions=len(subsets),proposed_requests=len(subsets)*2*3,
        max_requests=None,max_cost=None,model_versions=[],retry_policy=None,
        blockers=['two independent completed reviews','necessary adjudication and accepted question list','explicit budget and selected model/service versions'],new_api_calls=0))
    dump(out/'review_task_mapping.reviewer_only.json',[dict(task_id=t['task_id'],subset_id=s['subset_id']) for t,s in zip(blind_tasks,subsets)])
    summary=dict(status='mechanical_pass_author_candidates_only',base_scenarios=4,languages={'zh':2,'en':2},base_messages=len(all_messages),
        conditions=len(conditions),screenshots=sum(len(c['pages']) for c in conditions),subset_tasks=len(subsets),reviewers_completed=0,
        source_stats=source_stats,source_fact_rows=len(ledger)-len(all_messages),fact_rows=len(ledger),browser=browser_version,
        renderer_sha256=sha(snapshot/'tools/render_v2_round2.py'),generator_sha256=sha(Path(__file__)),config_sha256=sha(ROOT/'configs/v3/calibration_scenarios.json'),
        checks=['all page dimensions and bbox bounds','all messages mapped','all subsets enumerated','single declared semantic variable',
                'order/pagination preserve messages','distractor preserves original messages','review packages exclude author fields'],
        limitations=['Author semantic ranges and naturalness are self-review, not independent certification.',
                     'Four scenarios are synthetic adaptations; source anchors do not make new dialogue historical.',
                     'Full source-case release rights remain unresolved; internal preparation only.'],new_api_calls=0)
    dump(out/'mechanical_checks.json',summary)
    manifest=[dict(path=p.relative_to(out).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(out.rglob('*')) if p.is_file() and 'work' not in p.relative_to(out).parts and p.name!='.incomplete']
    jsonl(out/'artifact_manifest.jsonl',manifest);(out/'.incomplete').unlink()
    print(json.dumps(summary,ensure_ascii=False))

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',required=True);build(parser.parse_args().output)
