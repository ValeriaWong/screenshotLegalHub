"""Owner-scoped process/result projections. Formal releases and development probes remain distinct."""
import json
from pathlib import Path
from urllib.parse import urlencode
from .contracts import now, digest, uid
from . import audit

KINDS=('benchmark.pipeline.task','benchmark.pipeline.report','benchmark.pipeline','benchmark.pipeline.node','benchmark.prediction','benchmark.match','benchmark.input','benchmark.scoreset','benchmark.dataset','benchmark.history','benchmark.annotation','benchmark.review','benchmark.quality','benchmark.comment','benchmark.release','benchmark.run','benchmark.attempt','benchmark.score','evaluation.task_prompt','research.flow','review.sample','review.revision','review.manifest','review.comment','review.comment.event','review.quality','review.gold','review.release','review.prompt','studio.prompt','studio.batch','studio.package','evaluation.request','evaluation.run','evaluation.attempt','evaluation.probe','evaluation.metrics')
SECRET_FIELDS={'encrypted_api_key','ciphertext','api_key','authorization','cookie','password','lease_token','access_token','refresh_token','session_token'}
def public(value):
    if isinstance(value,dict): return {k:public(v) for k,v in value.items() if k.lower() not in SECRET_FIELDS}
    if isinstance(value,list): return [public(v) for v in value]
    return value

def operation_url(kind,id):
    return '/evaluation.html?'+urlencode(dict(operations=1,kind=kind,record=id))

class Operations:
    def __init__(self,store): self.store=store

    def rows(self,owner,kind='',q='',flow_id='',offset=0,limit=50):
        if kind and kind not in KINDS+('job',): raise ValueError('不支持的记录类型')
        if not 1<=limit<=200 or offset<0: raise ValueError('无效分页')
        if not q.strip() and not flow_id:
            kinds=(kind,) if kind and kind!='job' else KINDS if not kind else ()
            rows=[];total=0;take=offset+limit
            order="coalesce(nullif(json_extract(body,'$.created_at'),''),json_extract(body,'$.occurred_at'),'') DESC,id DESC"
            with self.store.read() as db:
                if kinds:
                    where='owner=? AND kind IN ('+','.join('?' for _ in kinds)+')';args=[owner,*kinds]
                    total+=db.execute('SELECT count(*) FROM records WHERE '+where,args).fetchone()[0]
                    rows += [(r['kind'],r['id'],json.loads(r['body'])) for r in db.execute('SELECT kind,id,body FROM records INDEXED BY records_owner_recent WHERE '+where+' ORDER BY '+order+' LIMIT ?',[*args,take])]
                if kind in ('','job'):
                    total+=db.execute('SELECT count(*) FROM jobs WHERE owner=?',(owner,)).fetchone()[0]
                    rows += [('job',r['id'],json.loads(r['body'])) for r in db.execute('SELECT id,body FROM jobs INDEXED BY jobs_owner_recent WHERE owner=? ORDER BY '+order+' LIMIT ?',(owner,take))]
            result=[]
            for k,i,r in rows:
                status=r.get('status') or r.get('verdict') or (('completed' if r['success'] else 'failed') if 'success' in r else 'recorded')
                result.append(dict(kind=k,id=i,title=r.get('title') or r.get('name') or r.get('scope') or r.get('phase') or k,status=status,
                    created_at=r.get('created_at') or r.get('occurred_at') or '',sample_id=r.get('sample_id'),flow_id=r.get('flow_id') or r.get('correlation_id'),
                    href=operation_url(k,i),mode=r.get('mode'),scope=r.get('scope'),method=r.get('method')))
            result.sort(key=lambda x:(x['created_at'],x['id']),reverse=True)
            return dict(items=result[offset:offset+limit],total=total,next_offset=offset+limit if offset+limit<total else None,kinds=list(KINDS)+['job'])
        with self.store.read() as db:
            kinds=(kind,) if kind and kind!='job' else KINDS if not kind else ()
            fields=['title','name','scope','phase','status','verdict','success','created_at','occurred_at','sample_id','flow_id','correlation_id','mode','method']
            projection=','.join("json_extract(body,'$."+f+"') AS "+f for f in fields)+",json_type(body,'$.success') AS success_present"
            records=list(db.execute('SELECT kind,id,'+projection+' FROM records WHERE owner=? AND kind IN ('+','.join('?' for _ in kinds)+')',[owner,*kinds])) if kinds else []
            jobs=list(db.execute("SELECT 'job' AS kind,id,"+projection+' FROM jobs WHERE owner=?',[owner])) if kind in ('','job') else []
        result=[]
        for record in records+jobs:
            r=dict(record);k,i=r['kind'],r['id']
            if r.pop('success_present') is None:r.pop('success',None)
            title=r.get('title') or r.get('name') or r.get('scope') or r.get('phase') or k
            status=r.get('status') or r.get('verdict') or (('completed' if r['success'] else 'failed') if 'success' in r else 'recorded')
            correlation=r.get('flow_id') or r.get('correlation_id')
            row=dict(kind=k,id=i,title=title,status=status,created_at=r.get('created_at') or r.get('occurred_at') or '',sample_id=r.get('sample_id'),flow_id=correlation,href=operation_url(k,i),mode=r.get('mode'),scope=r.get('scope'),method=r.get('method'))
            if flow_id and correlation!=flow_id: continue
            if any(word.casefold() not in json.dumps(row,ensure_ascii=False).casefold() for word in q.split()): continue
            result.append(row)
        result.sort(key=lambda x:(x['created_at'],x['id']),reverse=True)
        return dict(items=result[offset:offset+limit],total=len(result),next_offset=offset+limit if offset+limit<len(result) else None,kinds=list(KINDS)+['job'])

    def get(self,owner,kind,id):
        if kind=='job': row=self.store.job(id,owner)
        elif kind in KINDS: row=self.store.get(kind,id,owner)
        else: raise ValueError('不支持的记录类型')
        body=public(row)
        related=[]
        for key,target in [('pipeline_id','benchmark.pipeline'),('node_id','benchmark.pipeline.node'),('prediction_id','benchmark.prediction'),('match_id','benchmark.match'),('score_set_id','benchmark.scoreset'),('dataset_id','benchmark.dataset'),('annotation_id','benchmark.annotation'),('sample_id','review.sample'),('batch_id','studio.batch'),('run_id','evaluation.run'),('job_id','job'),('parent_job_id','job'),('prompt_id','review.prompt'),('release_id','review.release')]:
            ref=row.get(key) or (row.get('payload') or {}).get(key)
            if ref:
                try: related.append(dict(label=key,**self.resolve(owner,ref)))
                except KeyError: pass
        for sid in row.get('sample_ids',[]):
            try:related.append(dict(label='候选样本',**self.resolve(owner,sid)))
            except KeyError:pass
        if kind=='research.flow':
            samples=set(row.get('source_sample_ids',[])+row.get('sample_ids',[]));batches=set(row.get('batch_ids',[]));linked=[]
            with self.store.read() as db:
                records=list(db.execute('SELECT kind,id,body FROM records WHERE owner=? AND kind IN ('+','.join('?' for _ in KINDS)+')',[owner,*KINDS]))
                jobs=list(db.execute('SELECT id,body FROM jobs WHERE owner=?',[owner]))
            for k,i,raw in [(r['kind'],r['id'],r['body']) for r in records]+[('job',r['id'],r['body']) for r in jobs]:
                v=json.loads(raw)
                if i==id:continue
                if i in set(row.get('linked_record_ids',[])) or (row.get('summary',{}).get('dataset_id') and (v.get('dataset_id')==row['summary']['dataset_id'] or i==row['summary']['dataset_id'])) or i in samples|batches or v.get('sample_id') in samples or v.get('batch_id') in batches or v.get('flow_id')==id or v.get('correlation_id')==id or (k.endswith('.prompt') and v.get('name')==id):
                    linked.append(dict(kind=k,id=i,title=v.get('name') or v.get('title') or v.get('scope') or k,status=v.get('status') or v.get('verdict') or ('completed' if v.get('success') else 'recorded'),created_at=v.get('created_at',''),href=operation_url(k,i)))
            body['linked_records']=sorted(linked,key=lambda x:x['created_at'],reverse=True)
            related += [dict(label='原始样本',**self.resolve(owner,sid)) for sid in row.get('source_sample_ids',[])]
        if kind=='benchmark.pipeline':
            with self.store.read() as db:
                rows=db.execute("SELECT id,json_extract(body,'$.title') AS title,json_extract(body,'$.status') AS status,json_extract(body,'$.created_at') AS created_at FROM records WHERE kind='benchmark.pipeline.node' AND owner=? AND json_extract(body,'$.pipeline_id')=? ORDER BY rowid LIMIT 30",(owner,id)).fetchall()
            body['linked_records']=[dict(kind='benchmark.pipeline.node',id=r['id'],title=r['title'],status=r['status'],created_at=r['created_at'],href=operation_url('benchmark.pipeline.node',r['id'])) for r in rows]
            body['linked_records_total']=row['planned_units']
        return dict(kind=kind,id=id,body=body,related=related,href=self.resolve(owner,id)['href'])

    def resolve(self,owner,id):
        if id.startswith('job.'):
            self.store.job(id,owner);return dict(id=id,kind='job',href=operation_url('job',id))
        with self.store.read() as db:
            r=db.execute('SELECT kind FROM records WHERE owner=? AND id=? AND kind IN ('+','.join('?' for _ in KINDS)+')',[owner,id,*KINDS]).fetchone()
        if not r: raise KeyError('对象不存在或无访问权限')
        kind=r['kind'];href=operation_url(kind,id)
        if kind=='review.sample':href='/review.html?'+urlencode(dict(sample=id))
        if kind=='benchmark.pipeline':href='/evaluation.html?'+urlencode(dict(benchmark=1,pipeline=id))
        if kind=='benchmark.run':href='/evaluation.html?'+urlencode(dict(benchmark=1,benchmark_run=id))
        if kind=='benchmark.dataset':href='/review.html?'+urlencode(dict(section='benchmark',benchmark=id))
        if kind=='evaluation.run':href='/evaluation.html?'+urlencode(dict(run=id))
        if kind=='studio.batch':href='/studio.html?'+urlencode(dict(batch=id))+'#batch-'+id
        return dict(id=id,kind=kind,href=href)

    def import_trial(self,owner,directory):
        directory=Path(directory).resolve();reports=(self.store.root.parent.parent/'reports').resolve()
        if not directory.is_relative_to(reports) or not directory.is_dir():raise ValueError('仅可同步本产品reports下的实际流程记录')
        summary=json.loads((directory/'summary.json').read_text(encoding='utf-8'))
        execution=json.loads((directory/'execution.json').read_text(encoding='utf-8'))
        recovery=json.loads((directory/'recovery.json').read_text(encoding='utf-8'))
        fid=summary['flow_id'];artifacts=[]
        names=['REPORT.md','RESULTS.html','summary.json','request-ledger.json','quality-records.json','qa-results.json','comparison.json','audit-events.json','jobs.json','studio-prompt-history.md','review-prompt-history.md','integrity-checks.json','response-normalization.json','authorization.json']
        for file in [directory/name for name in names]+list(directory.glob('batch.*.zip')):
            if file.is_file() and file.resolve().is_relative_to(reports):artifacts.append(dict(name=file.name,path=file.relative_to(reports).as_posix(),sha256=digest(file.read_bytes()),bytes=file.stat().st_size))
        for sid in execution['sources']+recovery['candidate_ids']:self.store.get('review.sample',sid,owner)
        nsource=len(execution['sources']);ncandidate=len(recovery['candidate_ids']);it=summary.get('iteration',{})
        steps=[dict(stage='原图绑定',result=str(nsource)+'个来源；版本与完整性见样本记录'),dict(stage='生成及恢复',result=str(ncandidate)+'个候选；失败尝试保留'),dict(stage='质量评估',result='来源覆盖 '+str(summary.get('source_quality_coverage','未知'))+'；候选覆盖 '+str(summary.get('candidate_quality_coverage','未知'))),dict(stage='反馈迭代',result=str(it.get('before_score','未评'))+' → '+str(it.get('after_score','未评'))+'；模型观察，不是因果结论'),dict(stage='问答探测',result=str(summary.get('qa_success','未知'))+'/'+str(summary.get('qa_requests','未知'))+'返回，未计分'),dict(stage='发布检查',result=summary.get('status','未知'))]
        row=dict(id=fid,flow_id=fid,name=summary.get('model','模型')+' · '+str(nsource)+'个初始样本试跑',status=summary['status'],created_at=execution['started_at'],synced_at=now(),historical_sync=True,summary=summary,source_sample_ids=execution['sources'],sample_ids=recovery['candidate_ids'],batch_ids=recovery['batches'],steps=steps,artifacts=artifacts,source_summary_hash=digest((directory/'summary.json').read_bytes()),request_ledger=json.loads((directory/'request-ledger.json').read_text(encoding='utf-8')))
        with self.store.tx() as db:
            old=self.store.optional('research.flow',fid,owner,db)
            if old and old['source_summary_hash']==row['source_summary_hash']:return old
            self.store.put('research.flow',row,owner,db)
            audit.emit(db,owner,'research.flow.synced','research.flow',fid,reason='历史试跑记录同步；不补造当时的界面操作',details={'flow_id':fid,'source_sha256':row['source_summary_hash']})
        return row

    def artifact(self,owner,flow_id,name):
        flow=self.store.get('research.flow',flow_id,owner)
        entry=next((a for a in flow['artifacts'] if a['name']==name),None)
        if not entry:raise KeyError('流程产物不存在')
        reports=(self.store.root.parent.parent/'reports').resolve();file=(reports/entry['path']).resolve()
        if not file.is_relative_to(reports) or digest(file.read_bytes())!=entry['sha256']:raise ValueError('流程产物路径或哈希校验失败')
        return file
