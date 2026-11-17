"""Coverage first; no fabricated legal scores and no dropping failed planned tasks."""
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import random
import statistics
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'product_v1/backend/src'))
from screenshotlegal.experiments.gold import CaseGold,score_result
from method_artifacts import read_record,publish_methods
from screenshotlegal.method_reproductions.catalog import METHOD_MODULES

def paired_bootstrap(rows,left,right,metric,seed=42,samples=2000):
    # Pair within cases first, then average each case group before resampling groups.
    by_case={}
    for row in rows:
        result=row.get('result');value=row.get('scoring',{}).get('metrics',{}).get(metric)
        if not result or value is None or result['run'].get('demo') or result.get('staleness',{}).get('stale'):continue
        run=result['run'];key=(row['case_group_id'],row['case_id'],row['repeat'])
        if run.get('response_models')!=[run.get('model_revision_declared')]:continue
        by_case.setdefault(key,{})[row['method_id']]=(value,run)
    groups={}
    for (group,_,_),methods in by_case.items():
        if left not in methods or right not in methods:continue
        lv,lr=methods[left];rv,rr=methods[right]
        keys=['input_digest','model_digest','model_revision_declared','budget','split','protocol_digest','method_options']
        if any(lr.get(k)!=rr.get(k) for k in keys):continue
        groups.setdefault(group,[]).append(rv-lv)
    deltas=[statistics.mean(v) for v in groups.values()]
    if not deltas:return dict(paired_case_groups=0,mean_difference=None,ci95=None)
    if len(deltas)==1:return dict(paired_case_groups=1,mean_difference=deltas[0],ci95=None,note='单个案件组不足以估计组间不确定性')
    rng=random.Random(seed);draws=sorted(statistics.mean(rng.choices(deltas,k=len(deltas))) for _ in range(samples))
    return dict(paired_case_groups=len(deltas),mean_difference=statistics.mean(deltas),ci95=[draws[int(samples*.025)],draws[min(samples-1,int(samples*.975))]],seed=seed,bootstrap_samples=samples)

def summarize(out,gold_dir=None):
    out=Path(out);tasks=json.loads((out/'planned_tasks.json').read_text(encoding='utf-8'));rows=[]
    for task in tasks:
        row=read_record(out,task) or dict(task,status='not_started')
        result=row.get('result')
        if result:
            gold_path=Path(gold_dir)/(result['run']['input_digest']+'.json') if gold_dir else None
            gold=CaseGold.model_validate_json(gold_path.read_text(encoding='utf-8')) if gold_path and gold_path.exists() else None
            row['scoring']=score_result(result,gold)
        rows.append(row)
    groups=[]
    for method in dict.fromkeys(t['method_id'] for t in tasks):
        selected=[r for r in rows if r['method_id']==method];counts=Counter(r['status'] for r in selected)
        completed=[r for r in selected if r['status']=='completed'];real=[r for r in completed if not r['result']['run'].get('demo')]
        quality={k:None for k in ['claim_label_set_f1','burden_accuracy','citation_support_accuracy']}
        scored={}
        for metric in quality:
            values=[r.get('scoring',{}).get('metrics',{}).get(metric) for r in selected]
            values=[v for v in values if v is not None];scored[metric]=len(values)
            if values:quality[metric]=statistics.mean(values)
        usages=[r.get('result',{}).get('run',{}).get('usage') or {} for r in selected]
        real_runs=[r['result']['run'] for r in selected if r.get('result') and not r['result']['run'].get('demo')]
        costs={};cost_calls=0;real_calls=0
        for run in real_runs:
            usage=run.get('usage') or {};real_calls+=usage.get('model_calls',0);cost_calls+=usage.get('cost_recorded',0)
            currency=run['model'].get('billing',{}).get('currency') or 'unspecified'
            if usage.get('cost') is not None:costs[currency]=costs.get(currency,0)+usage['cost']
        elapsed=[r['result']['run']['usage']['elapsed_ms'] for r in completed if r['result']['run'].get('usage')]
        groups.append(dict(method=method,reproduction_name=METHOD_MODULES[method],planned=len(selected),completed=len(completed),statuses=dict(counts),completion_rate=len(completed)/len(selected),demo_completed=len(completed)-len(real),model_calls=sum(u.get('model_calls',0) for u in usages),tool_calls=sum(u.get('tool_calls',0) for u in usages),known_cost_by_currency=costs or None,cost_recorded_calls=cost_calls,real_model_calls=real_calls,cost_is_partial=cost_calls<real_calls,completed_elapsed_median_ms=statistics.median(elapsed) if elapsed else None,quality_means=quality,scored_counts=scored))
    report=dict(schema_version='paper-experiment-report.v1',metric_protocol='case-gold-exact.v1',scorer_sha256={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__),REPO/'product_v1/backend/src/screenshotlegal/experiments/gold.py']},planned=len(tasks),statuses=dict(Counter(r['status'] for r in rows)),methods=groups,
                paired_vs_E03={m['method']:{k:paired_bootstrap(rows,'E03',m['method'],k) for k in m['quality_means']} for m in groups if m['method']!='E03'},
                note='Demo只验证执行机制，不计准确率；失败、前提缺失、未启动均保留在计划分母。标签F1采用已审别名精确匹配；引文支持度需要绑定具体输出的人工判断。')
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    with (out/'coverage.csv').open('w',encoding='utf-8-sig',newline='') as file:
        writer=csv.DictWriter(file,fieldnames=['method','planned','completed','demo_completed','model_calls','tool_calls','statuses']);writer.writeheader()
        writer.writerows({k:(json.dumps(m[k],ensure_ascii=False) if k=='statuses' else m[k]) for k in writer.fieldnames} for m in groups)
    lines=['# 案件方法实验报告','',report['note'],'',f"计划任务：{len(tasks)}；状态：{dict(Counter(r['status'] for r in rows))}",'','| 方法 | 完成 / 计划 | Demo完成 | 模型调用 | 工具调用 | 状态 |','|---|---:|---:|---:|---:|---|']
    lines += [f"| {m['method']} | {m['completed']} / {m['planned']} | {m['demo_completed']} | {m['model_calls']} | {m['tool_calls']} | {m['statuses']} |" for m in groups]
    lines += ['', '法律质量均值、已评分分母及按案件组配对的bootstrap区间见 report.json。原始提示、响应、工具观察和来源快照保存在 attempts/。']
    (out/'REPORT.md').write_text(chr(10).join(lines)+chr(10),encoding='utf-8')
    publish_methods(out,tasks,rows,groups)
    return report

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--out',type=Path,required=True);p.add_argument('--gold-dir',type=Path);a=p.parse_args()
    print(json.dumps(summarize(a.out,a.gold_dir),ensure_ascii=False,indent=2))
