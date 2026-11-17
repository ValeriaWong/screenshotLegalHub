"""Separate research database. Mutations and render outbox share FULL/WAL transactions."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from .contracts import dumps, now, uid, digest
from . import audit

class Conflict(ValueError):
    pass

class Store:
    def __init__(self, data_dir):
        self._anchor=None
        self.root = Path(data_dir) / 'research'
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'research.sqlite3'
        with self.tx() as db:
            for sql in [
                'CREATE TABLE IF NOT EXISTS records (kind TEXT NOT NULL,id TEXT NOT NULL,owner TEXT NOT NULL,body TEXT NOT NULL,PRIMARY KEY(kind,id,owner))',
                'CREATE INDEX IF NOT EXISTS records_owner ON records(kind,owner)',
                "CREATE INDEX IF NOT EXISTS records_owner_recent ON records(owner,coalesce(nullif(json_extract(body,'$.created_at'),''),json_extract(body,'$.occurred_at'),''),id,kind)",
                "CREATE INDEX IF NOT EXISTS records_pipeline ON records(kind,owner,json_extract(body,'$.pipeline_id'),json_extract(body,'$.image_key'))",
                "CREATE INDEX IF NOT EXISTS records_pipeline_issue ON records(kind,owner,json_extract(body,'$.pipeline_id'),json_extract(body,'$.has_issue'))",
                "CREATE INDEX IF NOT EXISTS records_pipeline_state ON records(kind,owner,json_extract(body,'$.pipeline_id'),json_extract(body,'$.status'))",
                'CREATE TABLE IF NOT EXISTS jobs (id TEXT PRIMARY KEY,owner TEXT NOT NULL,kind TEXT NOT NULL,status TEXT NOT NULL,lease_until REAL NOT NULL DEFAULT 0,lease_token TEXT,body TEXT NOT NULL)',
                'CREATE INDEX IF NOT EXISTS jobs_claim ON jobs(status,lease_until)',
                "CREATE INDEX IF NOT EXISTS jobs_owner_recent ON jobs(owner,coalesce(nullif(json_extract(body,'$.created_at'),''),json_extract(body,'$.occurred_at'),''),id)",
                "CREATE INDEX IF NOT EXISTS jobs_queued_order ON jobs(json_extract(body,'$.created_at')) WHERE status='queued'",
                'CREATE TABLE IF NOT EXISTS idempotency (owner TEXT,scope TEXT,key TEXT,fingerprint TEXT,result TEXT,PRIMARY KEY(owner,scope,key))'
            ]:
                db.execute(sql)
            for sql in audit.DDL: db.execute(sql)
            if not db.execute('SELECT 1 FROM schema_migrations WHERE version=1').fetchone():
                token=audit.context.set(dict(actor_id='unknown',actor_type='system'))
                try:
                    for r in db.execute("SELECT kind,id,owner FROM records WHERE kind IN ('review.sample','review.release','studio.batch','evaluation.run')").fetchall():
                        audit.emit(db,r['owner'],'migration_snapshot',r['kind'],r['id'],event_key='migration:1:'+r['kind']+':'+r['id'],details={'historical':True,'binding':'legacy_unbound'},reason='迁移前已有记录；原操作人和操作时间未知')
                finally: audit.context.reset(token)
                db.execute('INSERT INTO schema_migrations VALUES (?,?)',(1,now()))

        # Keep WAL open between short transactions; FULL commits still fsync.
        # Otherwise SQLite checkpoints on every last-connection close.
        self._anchor=sqlite3.connect(self.path,timeout=30,isolation_level=None,check_same_thread=False)
        self._anchor.execute('PRAGMA journal_mode=WAL').fetchone()
        self._anchor.execute('SELECT count(*) FROM sqlite_schema').fetchone()

    def close(self):
        if self._anchor is not None:self._anchor.close();self._anchor=None

    def __del__(self):
        self.close()

    @contextmanager
    def read(self):
        db=sqlite3.connect(self.path,timeout=30,isolation_level=None);db.row_factory=sqlite3.Row
        try: yield db
        finally: db.close()

    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('PRAGMA busy_timeout=30000')
        db.execute('BEGIN IMMEDIATE')
        meta={}; context_token=audit.transaction.set(meta)
        try:
            yield db
            db.commit()
        except BaseException as error:
            db.rollback()
            if meta.get("owner"):
                try:
                    db.execute("BEGIN IMMEDIATE")
                    ctx=audit.context.get()
                    audit.emit(db,meta["owner"],meta.get("action","operation")+".rejected","operation",meta.get("object_id",""),outcome="rejected",event_key="rejected:"+(ctx.get("request_id") or uid("request")),details={"error_type":type(error).__name__},reason="操作被拒绝，业务变更已回滚")
                    db.commit()
                except Exception:
                    db.rollback();audit.log.exception("Failed to persist rejected operation")
            raise
        finally:
            audit.transaction.reset(context_token)
            db.close()

    def get(self, kind, id, owner, db=None):
        if db is None:
            with self.read() as conn:
                return self.get(kind, id, owner, conn)
        row = db.execute('SELECT body FROM records WHERE kind=? AND id=? AND owner=?', (kind,id,owner)).fetchone()
        if row is None:
            raise KeyError('Research resource not found')
        return json.loads(row['body'])

    def optional(self, kind, id, owner, db=None):
        try:
            return self.get(kind,id,owner,db)
        except KeyError:
            return None

    def list(self, kind, owner, db=None, *, field=None, value=None):
        if db is None:
            with self.read() as conn:
                return self.list(kind,owner,conn,field=field,value=value)
        query='SELECT body FROM records WHERE kind=? AND owner=?'
        args=[kind,owner]
        if field is not None:
            if field not in ['sample_id','run_id','task_id','batch_id','pipeline_id','node_id','score_set_id']:
                raise ValueError('Unsupported record filter')
            query+=" AND json_extract(body,'$."+field+"')=?"
            args.append(value)
        return [json.loads(r['body']) for r in db.execute(query+' ORDER BY rowid DESC',args)]

    def put(self, kind, body, owner, db, immutable=False):
        if immutable:
            old = self.optional(kind,body['id'],owner,db)
            if old is not None:
                if old != body:
                    raise Conflict('Immutable record already exists')
                return
        old = self.optional(kind,body['id'],owner,db)
        db.execute('INSERT INTO records VALUES (?,?,?,?) ON CONFLICT(kind,id,owner) DO UPDATE SET body=excluded.body WHERE records.owner=excluded.owner',
                   (kind,body['id'],owner,dumps(body)))
        audit.record(db,kind,body,owner,old)

    def idem(self, db, owner, scope, key, payload, action):
        meta=audit.transaction.get()
        if meta is not None: meta.update(owner=owner,action=scope,object_id=scope.split(":",1)[-1])
        fingerprint = digest(payload)
        old = db.execute('SELECT fingerprint,result FROM idempotency WHERE owner=? AND scope=? AND key=?',(owner,scope,key)).fetchone()
        if old:
            if old['fingerprint'] != fingerprint:
                raise Conflict('Idempotency key reused with different content')
            return json.loads(old['result'])
        result = action()
        db.execute('INSERT INTO idempotency VALUES (?,?,?,?,?)',(owner,scope,key,fingerprint,dumps(result)))
        return result

    def cached(self, owner, scope, key, payload):
        with self.tx() as db:
            row=db.execute('SELECT fingerprint,result FROM idempotency WHERE owner=? AND scope=? AND key=?',(owner,scope,key)).fetchone()
            if row is None:
                return None
            if row['fingerprint']!=digest(payload):
                raise Conflict('Idempotency key reused with different content')
            return json.loads(row['result'])

    def enqueue(self, db, owner, kind, payload, id=None):
        job = dict(id=id or uid('job'), kind=kind, owner=owner, status='queued',
                   phase='queued', created_at=now(), updated_at=now(), payload=payload,
                   checkpoints={}, attempts=[], error=None, cancel_requested=False)
        db.execute('INSERT INTO jobs(id,owner,kind,status,body) VALUES (?,?,?,?,?)',
                   (job['id'],owner,kind,'queued',dumps(job)))
        event=audit.emit(db,owner,'job.queued','job',job['id'],details={k:payload.get(k) for k in ['sample_id','sample_ids','batch_id','run_id','pipeline_id','node_id']},result_ref='job:'+job['id'])
        job['operation_request_id']=audit.context.get().get('request_id')
        job['audit_event_id']=event['id'];job['correlation_id']=audit.context.get().get('correlation_id') or job['id']
        db.execute('UPDATE jobs SET body=? WHERE id=?',(dumps(job),job['id']))
        return job

    def job(self, id, owner=None, db=None):
        if db is None:
            with self.read() as conn:
                return self.job(id,owner,conn)
        row = db.execute('SELECT * FROM jobs WHERE id=?'+(' AND owner=?' if owner else ''), (id,owner) if owner else (id,)).fetchone()
        if row is None:
            raise KeyError('Job not found')
        return dict(json.loads(row['body']), lease_token=row['lease_token'])

    def jobs(self, owner, sample_id=None):
        with self.tx() as db:
            query='SELECT id,owner,kind,status,'+','.join('json_extract(body,\'$.%s\') AS %s'%(field,field) for field in ['phase','created_at','updated_at','error','cancel_requested','parent_job_id'])
            query+=",json_extract(body,'$.payload.sample_id') AS sample_id,json_extract(body,'$.payload.batch_id') AS batch_id,json_extract(body,'$.payload.run_id') AS run_id,json_extract(body,'$.payload.pipeline_id') AS pipeline_id,json_extract(body,'$.payload.node_id') AS node_id,(SELECT count(*) FROM json_each(jobs.body,'$.checkpoints')) AS checkpoint_count FROM jobs WHERE owner=?"
            args=[owner]
            if sample_id:
                query+=" AND json_extract(body,'$.payload.sample_id')=?"
                args.append(sample_id)
            result=[]
            for r in db.execute(query+' ORDER BY rowid DESC',args):
                row=dict(r)
                row['error']=json.loads(row['error']) if row['error'] else None
                row['payload']={field:row.pop(field) for field in ['sample_id','batch_id','run_id','pipeline_id','node_id']}
                row['checkpoints']={str(i):'stored' for i in range(row.pop('checkpoint_count'))}
                result.append(row)
            return result

    def save_job(self, db, job, token=None):
        job['updated_at'] = now()
        previous=self.job(job['id'],job['owner'],db)
        body = {k:v for k,v in job.items() if k != 'lease_token'}
        sql = 'UPDATE jobs SET status=?,body=? WHERE id=?'
        args = [job['status'],dumps(body),job['id']]
        if token is not None:
            sql += ' AND lease_token=?'
            args.append(token)
        if db.execute(sql,args).rowcount != 1:
            raise Conflict('Worker lease no longer valid')
        if previous.get('cancel_requested')!=job.get('cancel_requested'):
            audit.emit(db,job['owner'],'job.cancel_requested','job',job['id'],details={**{k:job['payload'].get(k) for k in ['sample_id','sample_ids','batch_id','run_id']},'job_id':job['id']})
        if previous.get('parent_job_id')!=job.get('parent_job_id'):
            audit.emit(db,job['owner'],'job.retry_linked','job',job['id'],details={'job_id':job['id'],'parent_job_id':job.get('parent_job_id')})
        if (previous['status'],previous['phase'])!=(job['status'],job['phase']):
            audit.emit(db,job['owner'],'job.'+job['status']+'.'+job['phase'],'job',job['id'],outcome=job['status'] if job['status'] in ['failed','unknown'] else 'success',details={**{k:job['payload'].get(k) for k in ['sample_id','sample_ids','batch_id','run_id']},'job_id':job['id'],'kind':job['kind'],'parent_job_id':job.get('parent_job_id')},changes={'status':{'before':previous['status'],'after':job['status']},'phase':{'before':previous['phase'],'after':job['phase']}},reason=(job.get('error') or {}).get('message',''),result_ref='job:'+job['id'])

    def claim(self, lease_seconds=30):
        import time
        with self.tx() as db:
            current_time=time.time()
            row=db.execute("SELECT * FROM jobs WHERE status='running' AND lease_until<? ORDER BY lease_until,rowid LIMIT 1",(current_time,)).fetchone()
            if row is None:
                row=db.execute("SELECT * FROM jobs INDEXED BY jobs_queued_order WHERE status='queued' AND lease_until<=? ORDER BY json_extract(body,'$.created_at'),rowid LIMIT 1",(current_time,)).fetchone()
            if row is None:
                return None
            token = uid('lease')
            job = json.loads(row['body'])
            if row['status']=='running' and job['phase']=='calling_model' and job['kind']!='benchmark_pipeline':
                job.update(status='unknown',error={'category':'unknown_outcome','message':'调用中断，费用与结果未知；显式重试会创建新任务。','retryable':True})
                self.save_job(db,job)
                return dict(job,lease_token=None)
            job.update(status='running', updated_at=now())
            db.execute('UPDATE jobs SET status=?,lease_until=?,lease_token=?,body=? WHERE id=?',
                       ('running',time.time()+lease_seconds,token,dumps(job),job['id']))
            job['lease_token'] = token
            return job

    def heartbeat(self, id, token, seconds=30):
        import time
        with self.tx() as db:
            return db.execute("UPDATE jobs SET lease_until=? WHERE id=? AND lease_token=? AND status='running'",
                              (time.time()+seconds,id,token)).rowcount == 1
