"""Owner-scoped, read-only leaderboards over frozen evaluation records.

A cohort fixes source/reference/input/prompt/method/scorer settings. Repeated runs
use the newest terminal run per model configuration; retries are not full trials.
No gateway, model credentials, mutable review heads or live inputs are consulted.
"""
from collections import Counter, defaultdict
import math
from .contracts import digest, dumps, now
from .leaderboard_taxonomy import CATEGORIES,CATEGORY_IDS,entry_metadata,comparison_definition

TERMINAL={'completed','completed_with_issues','failed','unknown','cancelled','aborted'}
FAMILIES={'qa','benchmark','pipeline','agent'}
REASONS={
 'active':'运行尚未结束','demo':'离线 Demo 不计能力分','retry':'部分重试分支不替代完整运行',
 'legacy':'旧回放或未绑定版本不参与排名','missing_snapshot':'缺少可比较的冻结快照',
 'access':'案件访问权限已失效','unclassified':'缺少可验证的方法分类信息','probe':'连通性测试与试跑不计分',
}

def number(value):
    return isinstance(value,(int,float)) and not isinstance(value,bool) and math.isfinite(value)

def public_model(model):
    return dict(config_id=model.get('config_id') or model.get('id'),name=model.get('name') or model.get('model') or '未命名模型',
                model=model.get('model',''),parameters=model.get('parameters',{}),
                identity=digest({k:model.get(k) for k in ['config_id','endpoint','model','parameters','timeout_policy']}))

def score_value(score):
    value=(score or {}).get('result',{}).get('score')
    return float(value) if number(value) and 0<=value<=1 else None

def unit(task,attempt,score=None,*,qa=False):
    attempt=attempt or {};response=attempt.get('response') or {};error=attempt.get('error') or {}
    evidence=response or error.get('evidence') or {}
    kind=task.get('answer_kind')
    target=task.get('gold_answer') if qa else (score.get('target_snapshot',score.get('target',task.get('target'))) if score else task.get('target'))
    eligible=target is not None and (qa or kind not in ['open_text','identity'])
    if not qa and ('reference_valid' in task or score and 'reference_valid' in score):
        eligible=eligible and (score or {}).get('reference_valid',task.get('reference_valid',False))
    value=attempt.get('score') if qa else score_value(score)
    if not number(value) or not 0<=value<=1 or response.get('demo') or attempt.get('status') not in ['completed','response_received']:value=None
    status=attempt.get('status') or task.get('status') or 'not_attempted'
    # A returned answer awaiting local scoring is not silently treated as wrong.
    pending=eligible and status in ['completed','response_received'] and value is None and not response.get('demo')
    return dict(eligible=eligible,score=float(value) if eligible and value is not None else None,
                pending=pending,status=status,latency_ms=attempt.get('latency_ms',evidence.get('latency_ms')),
                cost=attempt.get('cost',evidence.get('cost_estimate')),
                currency=attempt.get('cost_currency',evidence.get('cost_currency')),
                failure=error.get('category') or (status if status in ['service_failed','blocked_upstream','blocked_no_match','invalid_input'] else None),
                reference_status=(score or {}).get('reference_status',task.get('reference_status')),
                target_hash=digest(target))

def definition(family,run,model,scope,tasks,track,metric,prompt,method,scorer):
    return dict(family=family,scope=scope,dataset_id=run.get('dataset_id') or run.get('release_id'),
                release_hash=run.get('release_hash'),track=track,metric=metric,
                tasks=sorted(tasks,key=dumps),prompt=prompt,method=method,scorer=scorer,
                parameters=model.get('parameters',{}),timeout_policy=model.get('timeout_policy'),
                budget=dict(max_calls=run.get('max_calls'),method_max_output_tokens=run.get('method_max_output_tokens')))

def summarize(candidate):
    units=candidate.pop('units');eligible=[u for u in units if u['eligible']]
    scored=[u['score'] for u in eligible if u['score'] is not None]
    latencies=sorted(u['latency_ms'] for u in units if number(u['latency_ms']) and u['latency_ms']>=0)
    costs=[u['cost'] for u in units if number(u['cost']) and u['cost']>=0]
    currencies=sorted({u['currency'] for u in units if u['currency']})
    requested=[u for u in units if u['status'] not in ['not_attempted','cancelled','blocked_upstream','blocked_no_match','invalid_input']]
    complete_cost=bool(requested) and len(costs)==len(requested) and len(currencies)==1
    pending=sum(u['pending'] for u in eligible)
    # Unreviewed development references have their own explicitly labelled board.
    reason='没有可自动计分的有效参考' if not eligible else '已有回答尚未完成计分' if pending else None
    candidate.update(planned=len(units),eligible=len(eligible),scored=len(scored),
        score=sum(scored)/len(eligible) if eligible and not pending else None,
        conditional_score=sum(scored)/len(scored) if scored else None,score_coverage=len(scored)/len(eligible) if eligible else None,
        response_coverage=sum(u['status'] in ['completed','response_received'] for u in units)/len(units) if units else None,
        failed=sum(u['status'] in ['failed','service_failed','invalid_input','blocked_upstream','blocked_no_match'] for u in units),
        unknown=sum(u['status']=='unknown' for u in units),cancelled=sum(u['status']=='cancelled' for u in units),
        pending_scoring=pending,unreviewed=sum(u['reference_status'] not in ['human_reviewed','human_confirmed'] for u in units),
        latency_p50_ms=latencies[len(latencies)//2] if latencies else None,
        latency_p95_ms=latencies[min(len(latencies)-1,int(len(latencies)*.95))] if latencies else None,
        cost=sum(costs) if costs and len(currencies)==1 and all(u['currency']==currencies[0] for u in units if number(u['cost'])) else None,cost_complete=complete_cost,currencies=currencies,
        failures=dict(Counter(u['failure'] for u in units if u['failure'])),unranked_reason=reason)
    return candidate

def leaderboard(store,owner,*,scope='official',family='all',cohort_id='',sort='score',offset=0,limit=20,q='',category='all',comparison='models',include_baseline=False,case_access=None,agent_versions=None,inventory=None,include_active=False,model_id='',method_id=''):
    if scope not in ['auto','official','development'] or family not in FAMILIES|{'all'} or sort not in ['score','coverage','latency','elapsed','calls'] or category not in CATEGORY_IDS|{'all'} or comparison not in ['models','methods']:
        raise ValueError('不支持的榜单筛选或排序')
    if offset<0 or not 1<=limit<=100 or len(q)>200:raise ValueError('无效榜单分页或搜索')
    kinds=['evaluation.run','evaluation.attempt','benchmark.run','benchmark.pipeline','benchmark.attempt','benchmark.score',
           'benchmark.pipeline.node','benchmark.pipeline.task','benchmark.scoreset','benchmark.dataset','review.release','benchmark.release','agent.run','agent.step']
    with store.read() as db:
        db.execute('BEGIN')
        data={kind:store.list(kind,owner,db) for kind in kinds}
        extra={kind:db.execute('SELECT count(*) FROM records WHERE kind=? AND owner=?',(kind,owner)).fetchone()[0] for kind in ['evaluation.probe']}
    excluded=Counter(probe=extra['evaluation.probe']);candidates=[];available=Counter()
    attempts=defaultdict(dict)
    for kind in ['evaluation.attempt','benchmark.attempt']:
        for a in data[kind]:
            attempts[a.get('run_id') or a.get('pipeline_id')].setdefault(a.get('task_id') if kind=='evaluation.attempt' else a['id'],a)
    all_attempts={a['id']:a for a in data['benchmark.attempt']}
    scores={s['id']:s for s in data['benchmark.score']}
    latest_scores={}
    for s in data['benchmark.score']:latest_scores.setdefault(s.get('attempt_id'),s)
    bundles={t['id']:t for t in data['benchmark.pipeline.task']}
    sets={s['id']:s for s in data['benchmark.scoreset']}
    nodes=defaultdict(list)
    for n in data['benchmark.pipeline.node']:nodes[n['pipeline_id']].append(n)
    names={r['id']:r.get('name',r['id']) for kind in ['benchmark.dataset','review.release','benchmark.release'] for r in data[kind]}
    def accept(run,fam):
        if run.get('parent_run_id') or run.get('parent_pipeline_id'):excluded['retry']+=1;return False
        if run.get('status') not in TERMINAL and not (include_active and run.get('status') in ['queued','running']):excluded['active']+=1;return False
        if run.get('mode')=='legacy_replay' or fam=='qa' and run.get('binding_contract')!='research.v2':
            excluded['legacy']+=1;return False
        return True
    def add(run,model,defn,units):
        if (model.get('config_id') or model.get('model'))=='demo':excluded['demo']+=1;return
        if not model.get('model') or not model.get('config_id'):excluded['missing_snapshot']+=1;return
        pm=public_model(model)
        metadata=entry_metadata(run,defn['family'],defn['track'],pm)
        defn=comparison_definition(defn,pm,comparison)
        cid=digest(defn)
        fam=defn['family'];track=defn['track']
        href='/evaluation.html?view=runs&run='+run['id'] if fam=='qa' else '/evaluation.html?view=benchmark&'+('pipeline=' if fam=='pipeline' else 'benchmark_run=')+run['id']
        row=summarize(dict(cohort_id=cid,definition=defn,model=pm,units=units,run_id=run['id'],
             run_name=run.get('name',''),created_at=run['created_at'],status=run['status'],href=href,
             score_set_id=run.get('score_set_id'),dataset_name=names.get(defn['dataset_id'],defn['dataset_id'] or '历史数据'),
             **metadata))
        if run.get('status') not in TERMINAL:
            row.update(score=None,conditional_score=None,unranked_reason='运行中，尚未生成成绩',
                       entry_id=digest([row['entry_id'],run['id']]),active=True)
        if fam=='pipeline' and 'kie_enhanced' in row['categories']:
            row['pipeline_models']=dict(extractor=pm,answer=pm)
        candidates.append(row)

    for run in data['evaluation.run']:
        if not accept(run,'qa'):continue
        if not run.get('release_hash'):excluded['missing_snapshot']+=1;continue
        groups=defaultdict(list)
        for task in run.get('tasks',[]):groups[task['model']['id']].append(task)
        for tasks in groups.values():
            model=tasks[0]['model'];aa=attempts[run['id']]
            us=[unit(t,aa.get(t['id']),qa=True) for t in tasks]
            signature=[dict(sample_id=t['sample_id'],revision=t.get('revision'),question_id=t['question_id'],
                            input_hash=t.get('input_hash'),target_hash=u['target_hash']) for t,u in zip(tasks,us)]
            defn=definition('qa',run,model,'official',signature,run.get('mode'), 'exact_match',
                            'evaluation-fixed-prompt.v1','direct','exact-stripped-answer.v1')
            add(run,model,defn,us)

    for run in data['benchmark.run']:
        if not accept(run,'benchmark'):continue
        if not run.get('scorer_version') or not run.get('tasks'):excluded['missing_snapshot']+=1;continue
        groups=defaultdict(list)
        for task in run['tasks']:groups[(task['task_family'],task['answer_kind'],task.get('label'))].append(task)
        for (task_family,kind,label),tasks in groups.items():
            aa=list(attempts[run['id']].values());us=[];signature=[]
            for task in tasks:
                a=next((a for a in aa if a['task_id']==task['task_id']),None);score=latest_scores.get(a['id']) if a else None
                u=unit(task,a,score);us.append(u)
                signature.append(dict(task_id=task['task_id'],input_hash=task.get('input_hash'),target_hash=u['target_hash'],
                    source_task_hash=task.get('source_task_hash'),reference_status=u['reference_status'],
                    scorer=(score or {}).get('scorer_version',run['scorer_version']),scorer_config=(score or {}).get('scorer_config',run.get('scorer_config'))))
            lane='official' if run['mode']=='official_reviewed' and run.get('release_hash') and all(u['reference_status']=='human_reviewed' for u in us) and all((latest_scores.get(a['id']) or {}).get('mode',run['mode'])=='official_reviewed' for a in aa) else 'development'
            metric='detection_f1' if task_family=='kie.extract' else 'exact_match'
            defn=definition('benchmark',run,run['model'],lane,signature,dict(track=run['track'],field=label,answer_kind=kind),metric,
                run.get('prompt',{}).get('sha256') or digest(run.get('prompt',{})),
                run.get('method',{'id':'E00'}),dict(version=run['scorer_version'],config=run.get('scorer_config')))
            add(run,run['model'],defn,us)

    for run in data['benchmark.pipeline']:
        if not accept(run,'pipeline'):continue
        ss=sets.get(run.get('score_set_id'))
        if not ss or not nodes[run['id']]:excluded['missing_snapshot']+=1;continue
        groups=defaultdict(list)
        for n in nodes[run['id']]:groups[(n['variant'],n['answer_kind'],n.get('label'))].append(n)
        for (variant,kind,label),group in groups.items():
            us=[];signature=[]
            for n in group:
                bundle=bundles.get(n.get('task_bundle_id'),{})
                task=next((t for t in bundle.get('tasks',[]) if t['task_id']==n['task_id']),None)
                if task is None:break
                task=dict(task,**ss.get('reference_overrides',{}).get(n['id'],{}),status=n['status'])
                score=scores.get(ss.get('overrides',{}).get(n['id'],n['id']+':'+ss['id']))
                a=all_attempts.get(n.get('attempt_id'));u=unit(task,a,score)
                # Upstream failures and local failures have distinct pipeline statuses.
                u['status']=n['status'];u['pending']=u['eligible'] and n['status']=='response_received' and u['score'] is None
                if n['status'] in ['service_failed','blocked_upstream','blocked_no_match','invalid_input']:u['failure']=u['failure'] or n['status']
                us.append(u);signature.append(dict(task_id=n['task_id'],source_task_hash=task.get('source_task_hash'),
                    asset_sha256=task.get('asset',{}).get('sha256'),question=task.get('question'),roi=task.get('roi'),
                    target_hash=u['target_hash'],reference_status=u['reference_status'],reference_valid=u['eligible'],
                    output_schema=task.get('output_schema'),scorer=(score or {}).get('scorer_version',ss['scorer_version'])))
            if len(us)!=len(group):excluded['missing_snapshot']+=1;continue
            lane='official' if run['mode']=='official_reviewed' and run.get('release_hash') and all(u['reference_status']=='human_reviewed' for u in us) and not any(n['id'] in ss.get('reference_overrides',{}) for n in group) else 'development'
            defn=definition('pipeline',run,run['model'],lane,signature,dict(variant=variant,field=label,answer_kind=kind),
                 'detection_f1' if variant=='kie_image' else 'exact_match',
                 {k:v.get('sha256') or digest(v) for k,v in run.get('prompts',{}).items()},'direct',
                 dict(version=ss['scorer_version'],protocol=run.get('protocol'),iou_threshold=.6,variants=sorted(run.get('variants',{}))))
            add(run,run['model'],defn,us)

    from .leaderboard_agents import collect_agents
    agent_rows,agent_excluded=collect_agents(data,case_access,comparison,agent_versions,include_active)
    candidates.extend(agent_rows);excluded.update(agent_excluded)
    # Baselines must match every frozen condition except the treatment variant.
    for c in candidates:
        c['baseline_delta']=None
        declared=next((m for m in (inventory or {}).get('methods',[]) if m['id']==c['method']['id']),None)
        if declared:c['method']['sources']=declared.get('sources',[])
        if 'kie_enhanced' in c['categories']:
            assets={t.get('asset_sha256') for t in c['definition']['tasks']} - {None}
            upstream=[r for r in candidates if r['run_id']==c['run_id'] and r['definition']['metric']=='detection_f1'
                      and assets and {t.get('asset_sha256') for t in r['definition']['tasks']} - {None}==assets]
            if len(upstream)==1:
                u=upstream[0]
                c['upstream_kie']=dict(score=u['score'],eligible=u['eligible'],scored=u['scored'])
        if 'kie_enhanced' in c['categories'] and c['score'] is not None:
            d=c['definition']
            key=dict(d,track={k:v for k,v in d['track'].items() if k!='variant'})
            matches=[r for r in candidates if r['run_id']==c['run_id'] and r['model']['identity']==c['model']['identity']
                     and r['definition']['family']=='pipeline' and r['score'] is not None
                     and r['definition']['track'].get('variant') in ['full_image_control','full_image']
                     and dict(r['definition'],track={k:v for k,v in r['definition']['track'].items() if k!='variant'})==key]
            if len(matches)==1:c['baseline_delta']=c['score']-matches[0]['score']
        if not c['categories']:excluded['unclassified']+=1
    latest={};repeat_counts=Counter()
    for c in sorted(candidates,key=lambda c:(c['created_at'],c['run_id']),reverse=True):
        k=(c['cohort_id'],c['entry_id']);repeat_counts[k]+=1;latest.setdefault(k,c)
    def matches_filters(c):
        return (family=='all' or c['definition']['family']==family) and (not model_id or comparison!='methods' or c['model']['config_id']==model_id) and (not method_id or comparison!='models' or c['method']['id']==method_id)
    category_members=[c for c in latest.values() if matches_filters(c) and (category=='all' or category in c['categories'])]
    if scope=='auto':
        scope='official' if any(c['definition']['scope']=='official' for c in category_members) else 'development'
    member_cohorts={c['cohort_id'] for c in latest.values() if category=='all' or category in c['categories']}
    cohorts=defaultdict(list);category_counts=Counter()
    for k,c in latest.items():
        c['repeated_runs']=repeat_counts[k]
        if matches_filters(c) and c['definition']['scope']==scope:category_counts.update(c['categories'])
        if matches_filters(c) and (category=='all' or category in c['categories'] or include_baseline and comparison=='methods' and category in ['agent','reproductions'] and c['baseline'] and c['cohort_id'] in member_cohorts):
            cohorts[c['cohort_id']].append(c)
    for rows in cohorts.values():
        if family=='all' or rows[0]['definition']['family']==family:available[rows[0]['definition']['scope']]+=1
    selected_cohorts=[]
    for cid,rows in cohorts.items():
        d=rows[0]['definition']
        if d['scope']!=scope or family!='all' and d['family']!=family:continue
        last=max(r['created_at'] for r in rows)
        selected_cohorts.append(dict(id=cid,family=d['family'],dataset_name=rows[0]['dataset_name'],track=d['track'],metric=d['metric'],
             scope=d['scope'],fixed_model_config_id=rows[0]['model']['config_id'] if comparison=='methods' else None,method_id=rows[0]['method']['id'],models=len({r['model']['identity'] for r in rows}),entries=len(rows),fixed_model_name=rows[0]['model']['name'] if comparison=='methods' else None,eligible=rows[0]['eligible'],planned=rows[0]['planned'],
             updated_at=last,definition=d))
    selected_cohorts.sort(key=lambda c:(c['eligible']>0,c['entries']>1,c['updated_at'],c['id']),reverse=True)
    if cohort_id and cohort_id not in {c['id'] for c in selected_cohorts}:raise KeyError('榜单不存在或无访问权限')
    selected=cohort_id or (selected_cohorts[0]['id'] if selected_cohorts else None)
    rows=sorted(cohorts.get(selected,[]),key=lambda r:(r['score'] is None,-(r['score'] or 0),r['model']['name'],r['method_name'],r['entry_id']))
    baseline_score=next((r['score'] for r in rows if r['baseline'] and r['score'] is not None),None)
    if comparison=='methods' and baseline_score is not None:
        for row in rows:row['baseline_delta']=row['score']-baseline_score if row['score'] is not None else None
    previous=None;rank=None
    for i,row in enumerate(rows,1):
        if row['score'] is None:row['rank']=None;continue
        if previous is None or not math.isclose(previous,row['score'],abs_tol=1e-12):rank=i
        previous=row['score'];row['rank']=rank
    from .leaderboard_inventory import inventory_rows
    registered=inventory_rows(inventory or {},rows,next((c for c in selected_cohorts if c['id']==selected),None),category,comparison,method_id,model_id,include_baseline)
    rows.extend(registered)
    if q:rows=[r for r in rows if q.casefold() in (r['model']['name']+' '+r['model']['model']+' '+r['method_name']).casefold()]
    if sort!='score':
        field={'coverage':'score_coverage','latency':'latency_p50_ms','elapsed':'elapsed_ms','calls':'model_calls'}[sort]
        rows.sort(key=lambda r:(r[field] is None,-(r[field] or 0) if sort=='coverage' else (r[field] or 0),r['entry_id']))
    # The response is an explicit allowlist: never raw input, target, prompt text or credentials.
    public_rows=[{k:v for k,v in r.items() if k not in ['definition','cohort_id','dataset_name']} for r in rows]
    return dict(scope=scope,inventory=inventory or dict(models=[],methods=[]),categories=[dict(c,entries=category_counts[c['id']]) for c in CATEGORIES],category=category,comparison=comparison,include_baseline=include_baseline,cohorts=selected_cohorts,selected_cohort_id=selected,items=public_rows[offset:offset+limit],total=len(rows),
        next_offset=offset+limit if offset+limit<len(rows) else None,generated_at=now(),
        summary=dict(available_scopes=dict(available),excluded=[dict(reason=k,label=REASONS[k],count=v) for k,v in excluded.items() if v]),
        policy='latest_terminal_per_model_method.v2',metric_note='得分交付率＝已获得分数之和 / 固定范围内有效参考题数；失败、未知和取消没有交付分数。已有回答等待计分时暂不排名。')
