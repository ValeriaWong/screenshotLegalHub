"""Independent Studio/Evaluation use cases depend on Review Desk's release/projection APIs."""
import random
from .contracts import *
from .store import Conflict
from .gateway import evaluation_input, ModelFailure, error_view

class DataStudio:
    def __init__(self, store, review, gateway):
        self.store,self.review,self.gateway=store,review,gateway

    def create_batch(self, owner, payload):
        # Freeze models outside transaction (credential vault writes independently).
        data=payload.model_dump()
        with self.store.tx() as db:
            old=db.execute('SELECT result,fingerprint FROM idempotency WHERE owner=? AND scope=? AND key=?',(owner,'batch',payload.idempotency_key)).fetchone()
            if old:
                import json
                if old['fingerprint']!=digest(data):
                    raise Conflict('Idempotency key reused with different content')
                return json.loads(old['result'])
        model=self.gateway.freeze(owner,payload.model_id)
        source=self.review.revision(owner,payload.source_sample_id,payload.source_revision)
        prompt=self.review.prompt(owner,'studio',payload.prompt_id)
        with self.store.tx() as db:
            def action():
                available=self.feedback(owner,payload.source_sample_id) if payload.use_review_feedback else []
                selected_ids=set(payload.feedback_ids) if payload.feedback_ids is not None else {c['id'] for c in available}
                if selected_ids-{c['id'] for c in available}:
                    raise ValueError('所选评论不属于当前来源的可用审核反馈')
                feedback=[c for c in available if c['id'] in selected_ids] if payload.use_review_feedback else []
                row=dict(id=uid('batch'),**data,model=model,source=source,prompt=prompt,review_feedback=feedback,feedback_hash=digest(feedback),
                         created_at=now(),status='queued',sample_ids=[],stages=['generate','validate','render','package'],
                         reproducibility='固定配置和版本；模型输出不保证确定性')
                row.pop('idempotency_key')
                job=self.store.enqueue(db,owner,'generate',dict(batch_id=row['id'],batch=row))
                row['job_id']=job['id']
                self.store.put('studio.batch',row,owner,db)
                return row
            return self.store.idem(db,owner,'batch',payload.idempotency_key,data,action)

    def batches(self, owner):
        return self.store.list('studio.batch',owner)

    def feedback(self, owner, source_sample_id):
        self.review.sample(owner,source_sample_id)
        batches=self.batches(owner)
        parents={sid:b['source']['sample_id'] for b in batches for sid in b['sample_ids']}
        def origin(sid):
            seen=set()
            while sid in parents and sid not in seen:
                seen.add(sid);sid=parents[sid]
            return sid
        root=origin(source_sample_id)
        source=self.review.revision(owner,source_sample_id,self.review.sample(owner,source_sample_id)['revision'])['content']
        def source_key(c):
            if c['source_text'].strip(): return digest(c['source_text'])
            provenance=c.get('metadata',{}).get('source_manifest','')
            if provenance.startswith('datasets/v3.0.0/') and '/cases/' in provenance:
                prefix,case=provenance.split('/cases/',1)
                return digest([prefix,case.split('/')[0]])
            return None
        source_hash=source_key(source)
        ids=[]
        for s in self.review.list_samples(owner):
            c=self.review.revision(owner,s['id'],s['revision'])['content']
            if origin(s['id'])==root or (source_hash and source_hash==source_key(c)): ids.append(s['id'])
        return self.review.feedback(owner,ids)

class EvaluationLab:
    def __init__(self, store, review, gateway):
        self.store,self.review,self.gateway=store,review,gateway

    def create_run(self, owner, payload):
        cached=self.store.cached(owner,'evaluation',payload.idempotency_key,payload.model_dump())
        if cached is not None:
            return cached
        release=self.review.release(owner,payload.release_id)
        if release.get('contract')!='research.v2': raise Conflict('历史发布缺少审核/图片/金标绑定；请保留历史并重新复核发布后创建新评测')
        entries=release['entries']
        requested=set(payload.sample_ids)
        if requested-set(e['sample_id'] for e in entries):
            raise ValueError('范围包含发布版本以外的样本')
        entries=[e for e in entries if (not requested or e['sample_id'] in requested)
                 and (not payload.category or e['revision']['content']['category']==payload.category)
                 and (not payload.batch_id or e.get('batch_id')==payload.batch_id)
                 and set(payload.tags)<=set(e['revision']['content']['tags'])]
        if payload.sample_size and len(entries)>payload.sample_size:
            entries=random.Random(payload.seed).sample(sorted(entries,key=lambda e:e['sample_id']),payload.sample_size)
        if not entries:
            raise ValueError('所选范围没有样本')
        models=[self.gateway.freeze(owner,id,vision=payload.mode!='text') for id in dict.fromkeys(payload.model_ids)]
        tasks=[]
        for model in models:
            for entry in entries:
                for q in entry['revision']['content']['questions']:
                    if payload.task_type and q['task_type']!=payload.task_type:
                        continue
                    error=None
                    try:
                        input=evaluation_input(entry,q,payload.mode)
                    except ModelFailure as e:
                        input=dict(question=q['question'],task_type=q['task_type'],mode=payload.mode)
                        error=error_view(e)
                    tasks.append(dict(id=uid('task'),sample_id=entry['sample_id'],revision=entry['revision']['number'],
                                      question_id=q['id'],category=entry['revision']['content']['category'],
                                      task_type=q['task_type'],model=model,input=input,input_hash=digest(input),
                                      gold_answer=q['answer'] if q['gold'] else None,
                                      status='queued',preflight_error=error))
        if not tasks:
            raise ValueError('范围中没有题目')
        if len(tasks)>payload.max_calls:
            raise ValueError('模型×题目数量超过调用预算；请缩小范围或增加 max_calls')
        with self.store.tx() as db:
            def action():
                row=dict(id=uid('eval'),**payload.model_dump(),created_at=now(),status='queued',
                         binding_contract='research.v2',release_hash=release['sha256'],model_snapshots=models,tasks=tasks,
                         frozen_sample_ids=[e['sample_id'] for e in entries],parent_run_id=None)
                row.pop('idempotency_key')
                job=self.store.enqueue(db,owner,'evaluation',dict(run_id=row['id'],sample_ids=row['frozen_sample_ids']))
                row['job_id']=job['id']
                self.store.put('evaluation.run',row,owner,db)
                return row
            return self.store.idem(db,owner,'evaluation',payload.idempotency_key,payload.model_dump(),action)

    def runs(self, owner):
        return self.store.list('evaluation.run',owner)

    def results(self, owner, id):
        run=self.store.get('evaluation.run',id,owner)
        attempts=self.store.list('evaluation.attempt',owner,field='run_id',value=id)
        latest={a['task_id']:a for a in reversed(attempts)}
        groups={}
        confusion={}
        for task in run['tasks']:
            a=latest.get(task['id'])
            key=task['model']['id']
            g=groups.setdefault(key,dict(model=task['model'],total=0,completed=0,failed=0,unknown=0,cancelled=0,
                                         scored=0,correct=0,latencies=[],costs=[],by_category={},by_task={},failures={}))
            g['total']+=1
            if not a:
                continue
            status=a['status']
            if status in ['completed','failed','unknown','cancelled']:
                g[status]+=1
            if a.get('latency_ms') is not None:
                g['latencies'].append(a['latency_ms'])
            if a.get('cost') is not None:
                g['costs'].append(a['cost'])
            if a.get('score') is not None:
                g['scored']+=1
                g['correct']+=a['score']
                for field,dest in [('category','by_category'),('task_type','by_task')]:
                    agg=g[dest].setdefault(task[field],dict(scored=0,correct=0))
                    agg['scored']+=1; agg['correct']+=a['score']
                gold=task['gold_answer']
                prediction=a.get('answer','')
                if gold in ['support','refute','insufficient','支持','反驳','证据不足'] and prediction in ['support','refute','insufficient','支持','反驳','证据不足']:
                    ckey=gold+' → '+prediction
                    confusion[ckey]=confusion.get(ckey,0)+1
            if a.get('error'):
                category=a['error']['category']
                g['failures'][category]=g['failures'].get(category,0)+1
        for g in groups.values():
            ls=sorted(g.pop('latencies'))
            costs=g.pop('costs')
            g['latency_distribution']={label:sum(low <= value < high for value in ls) for label,low,high in
                                      [('0–1s',0,1000),('1–5s',1000,5000),('5–15s',5000,15000),('15–60s',15000,60000),('60s+',60000,float('inf'))]}
            g['cost_min']=min(costs) if costs else None
            g['cost_max']=max(costs) if costs else None
            g.update(accuracy=g['correct']/g['scored'] if g['scored'] else None,
                     latency_p50_ms=ls[len(ls)//2] if ls else None,
                     latency_p95_ms=ls[min(len(ls)-1,int(len(ls)*.95))] if ls else None,
                     cost=sum(costs) if costs else None,cost_recorded=len(costs),cost_is_partial=len(costs)<g['completed']+g['failed']+g['unknown'],
                     unscored=g['completed']-g['scored'])
        report=dict(id=id,models=list(groups.values()),confusion=confusion,legacy_unbound=run.get('binding_contract')!='research.v2',
                    scoring='仅对人工确认的有效金标做精确答案匹配；法律实质质量须另行人工/模型评估')
        return dict(run=run,attempts=attempts,report=report)

    def retry(self, owner, id, task_ids, key):
        old=self.store.get('evaluation.run',id,owner)
        latest={a['task_id']:a for a in reversed(self.results(owner,id)['attempts'])}
        eligible=[t for t in old['tasks'] if latest.get(t['id'],{}).get('status') in ['failed','unknown','cancelled']
                  or (t['id'] not in latest and old['status'] in ['failed','unknown','cancelled'])]
        if task_ids:
            if set(task_ids)-{t['id'] for t in eligible}:
                raise ValueError('只能重试失败、取消或结果未知的题目')
            eligible=[t for t in eligible if t['id'] in task_ids]
        if not eligible:
            raise ValueError('没有可重试的题目')
        with self.store.tx() as db:
            def action():
                row=dict(old,id=uid('eval'),parent_run_id=id,created_at=now(),status='queued',
                         tasks=[dict(t,id=uid('task'),parent_task_id=t['id'],retry_count=t.get('retry_count',0)+1,status='queued') for t in eligible])
                # Keep original model credentials, dataset release and exact input snapshots.
                job=self.store.enqueue(db,owner,'evaluation',dict(run_id=row['id'],sample_ids=row['frozen_sample_ids']))
                row['job_id']=job['id']
                self.store.put('evaluation.run',row,owner,db)
                return row
            return self.store.idem(db,owner,'evaluation.retry:'+id,key,task_ids,action)
