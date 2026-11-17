"""Agent experiment rows retain engineering measurements; no fabricated CaseGold."""
from collections import Counter,defaultdict
from .contracts import digest
from .leaderboard_taxonomy import entry_metadata,comparison_definition
from .leaderboard import public_model,number

def collect_agents(data,case_access,comparison,versions,include_active=False):
    rows=[];excluded=Counter();steps=defaultdict(list);allowed={}
    for step in data['agent.step']:steps[step['run_id']].append(step)
    for run in data['agent.run']:
        cid=run.get('case_id')
        if cid not in allowed:
            try:
                if case_access is None:raise PermissionError()
                case_access(cid);allowed[cid]=True
            except (KeyError,PermissionError):allowed[cid]=False
        if not allowed[cid]:excluded['access']+=1;continue
        if run.get('status') not in ({'completed','failed','unknown','cancelled','aborted','queued','running'} if include_active else {'completed','failed','unknown','cancelled','aborted'}):excluded['active']+=1;continue
        model=run.get('model') or {}
        if model.get('config_id')=='demo':excluded['demo']+=1;continue
        required=['input_digest','protocol_digest','budget','split']
        if not all(run.get(k) for k in required) or not model.get('config_id') or not model.get('model') or not run.get('method',{}).get('id'):
            excluded['missing_snapshot']+=1;continue
        pm=public_model(model);metadata=entry_metadata(run,'agent','case_analysis',pm);usage=run.get('usage') or {}
        defn=dict(family='agent',scope='development',dataset_id=run.get('case_id'),release_hash=None,track='case_analysis',metric='awaiting_expert_gold',
            tasks=[dict(input_digest=run['input_digest'],perception_digest=run.get('perception_digest'),
                        matterpack_digest=run.get('matterpack_digest'),legal_corpus_digest=run.get('legal_corpus_digest'))],
            prompt=run['protocol_digest'],method=run['method'],parameters=model.get('parameters',{}),timeout_policy=model.get('timeout_policy'),
            budget=run['budget'],case_group_id=run.get('case_group_id'),split=run['split'],method_options=run.get('method_options'),
            model_revision_declared=run.get('model_revision_declared'),response_models=run.get('response_models'),
            scorer='no-expert-case-gold.v1')
        defn=comparison_definition(defn,pm,comparison)
        ll=sorted(value for step in steps[run['id']] for value in [(step.get('response') or {}).get('latency_ms')] if number(value) and value>=0)
        cost=usage.get('cost');currency=(model.get('billing') or {}).get('currency')
        stale=bool(versions and (run['method'].get('implementation_digest')!=versions.get('implementation_digest') or run['method'].get('registry_digest')!=versions.get('registry_digest')))
        row=dict(cohort_id=digest(defn),definition=defn,model=pm,run_id=run['id'],run_name=run.get('name',''),created_at=run['created_at'],
            status=run['status'],href='/evaluation.html?view=agents&agent_run='+run['id']+'&case='+str(cid),
            score_set_id=None,dataset_name=run.get('case_title') or cid,planned=1,eligible=0,scored=0,
            score=None,conditional_score=None,score_coverage=None,response_coverage=1.0 if run.get('output') else 0.0,
            failed=int(run['status'] in ['failed','aborted']),unknown=int(run['status']=='unknown'),cancelled=int(run['status']=='cancelled'),
            pending_scoring=0,unreviewed=0,latency_p50_ms=ll[len(ll)//2] if ll else None,
            latency_p95_ms=ll[min(len(ll)-1,int(len(ll)*.95))] if ll else None,
            cost=cost if number(cost) and cost>=0 and currency else None,currencies=[currency] if currency else [],
            cost_complete=bool(number(cost) and currency and usage.get('model_calls',0)>0 and usage.get('cost_recorded')==usage.get('model_calls') and not usage.get('missing_usage_calls')),
            failures={run['error']['category']:1} if (run.get('error') or {}).get('category') else {},
            unranked_reason='待专家金标，暂不生成质量名次',engineering=dict(quote_spans_validated=(run.get('engineering_metrics') or {}).get('quote_spans_validated')),
            stale_code=stale,scoring_status=run.get('scoring_status','awaiting_expert_gold'),**metadata)
        if run['status'] in ['queued','running']:
            row.update(active=True,entry_id=digest([row['entry_id'],run['id']]),unranked_reason='运行中，质量待评')
        rows.append(row)
    return rows,excluded
