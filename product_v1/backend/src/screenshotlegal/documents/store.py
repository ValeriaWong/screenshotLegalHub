"""Durable case-scoped document state; parsed blocks are immutable."""
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

class DocumentStore:
    def __init__(self, root):
        self.root = Path(root) / 'documents'
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'documents.sqlite3'
        with self.tx() as db:
            # execute each DDL statement inside tx; executescript would implicitly commit.
            for statement in """
                CREATE TABLE IF NOT EXISTS documents(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,sha TEXT NOT NULL,body TEXT NOT NULL,UNIQUE(case_id,sha));
                CREATE TABLE IF NOT EXISTS blocks(doc_id TEXT NOT NULL,ordinal INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(doc_id,ordinal));
                CREATE TABLE IF NOT EXISTS notes(doc_id TEXT NOT NULL,scope TEXT NOT NULL,revision INTEGER NOT NULL,body TEXT NOT NULL,PRIMARY KEY(doc_id,scope));
                CREATE TABLE IF NOT EXISTS publications(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS parse_jobs(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,doc_id TEXT NOT NULL,status TEXT NOT NULL,lease_until REAL NOT NULL,lease_token TEXT,body TEXT NOT NULL);
                CREATE UNIQUE INDEX IF NOT EXISTS active_parse_job ON parse_jobs(case_id,doc_id) WHERE status IN ('queued','running');
                CREATE VIRTUAL TABLE IF NOT EXISTS block_search USING fts5(doc_id UNINDEXED,block_id UNINDEXED,terms,tokenize='unicode61');
                CREATE TABLE IF NOT EXISTS parse_snapshots(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,doc_id TEXT NOT NULL,body TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS analyses(id TEXT PRIMARY KEY,doc_id TEXT NOT NULL,body TEXT NOT NULL);
            """.split(';'):
                if statement.strip():db.execute(statement)
            if 'profile' not in {r['name'] for r in db.execute('PRAGMA table_info(documents)')}:
                db.execute('ALTER TABLE documents RENAME TO documents_legacy_v1')
                db.execute('CREATE TABLE documents(id TEXT PRIMARY KEY,case_id TEXT NOT NULL,sha TEXT NOT NULL,profile TEXT NOT NULL,body TEXT NOT NULL,UNIQUE(case_id,sha,profile))')
                db.execute("INSERT INTO documents SELECT id,case_id,sha,'legacy',body FROM documents_legacy_v1")
                db.execute('DROP TABLE documents_legacy_v1')
    @contextmanager
    def tx(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute('PRAGMA journal_mode=WAL')
        db.execute('PRAGMA synchronous=FULL')
        db.execute('BEGIN IMMEDIATE')
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()
    def get(self, case_id, doc_id, db=None):
        if db is None:
            with self.tx() as conn: return self.get(case_id, doc_id, conn)
        row = db.execute('SELECT body FROM documents WHERE id=? AND case_id=?',(doc_id,case_id)).fetchone()
        if row is None: raise KeyError('Document not found')
        return json.loads(row['body'])
    def put(self, row, db):
        db.execute('INSERT INTO documents VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                   (row['id'],row['case_id'],row['sha256'],row.get('profile_digest','legacy'),json.dumps(row,ensure_ascii=False)))
    def list(self, case_id):
        with self.tx() as db:
            return [json.loads(r['body']) for r in db.execute('SELECT body FROM documents WHERE case_id=? ORDER BY rowid DESC',(case_id,))]
    def blocks(self, doc_id, offset=0, limit=None, q=""):
        if q:
            from screenshotlegal.infrastructure.retrieval.fts import tokenize
            terms=tokenize(q)[:50]
            if not terms:return []
            self.ensure_index(doc_id)
            match=" OR ".join('"'+t.replace('"','""')+'"' for t in terms)
            with self.tx() as db:
                sql="SELECT b.body FROM block_search s JOIN blocks b ON b.doc_id=s.doc_id AND json_extract(b.body,'$.id')=s.block_id WHERE block_search MATCH ? AND s.doc_id=? ORDER BY bm25(block_search),b.ordinal"
                args=[match,doc_id]
                if limit is not None:sql+=" LIMIT ? OFFSET ?";args.extend([limit,offset])
                found=[json.loads(r["body"]) for r in db.execute(sql,args)]
                if found or db.execute("SELECT count(*) FROM block_search WHERE block_search MATCH ? AND doc_id=?",(match,doc_id)).fetchone()[0]:return found
        with self.tx() as db:
            sql="SELECT body FROM blocks WHERE doc_id=?";args=[doc_id]
            if q: sql+=" AND instr(lower(json_extract(body,'$.text')),lower(?))>0";args.append(q)
            sql+=" ORDER BY ordinal"
            if limit is not None: sql+=" LIMIT ? OFFSET ?";args.extend([limit,offset])
            return [json.loads(r["body"]) for r in db.execute(sql,args)]
    def block_count(self, doc_id, q=""):
        if q:return len(self.blocks(doc_id,q=q))
        with self.tx() as db:
            sql="SELECT count(*) FROM blocks WHERE doc_id=?";args=[doc_id]
            if q: sql+=" AND instr(lower(json_extract(body,'$.text')),lower(?))>0";args.append(q)
            return db.execute(sql,args).fetchone()[0]
    def note(self, doc_id, scope):
        with self.tx() as db:
            row=db.execute('SELECT body FROM notes WHERE doc_id=? AND scope=?',(doc_id,scope)).fetchone()
            return json.loads(row['body']) if row else dict(revision=0,text='',cursor=0)
    def save_note(self, doc_id, scope, expected, text, cursor, actor):
        with self.tx() as db:
            old=db.execute('SELECT revision FROM notes WHERE doc_id=? AND scope=?',(doc_id,scope)).fetchone()
            if (old['revision'] if old else 0)!=expected: raise ValueError('批注已有新版本，请保留草稿后重新载入比对')
            row=dict(revision=expected+1,text=text,cursor=cursor,editor=actor)
            db.execute('INSERT INTO notes VALUES (?,?,?,?) ON CONFLICT(doc_id,scope) DO UPDATE SET revision=excluded.revision,body=excluded.body',
                       (doc_id,scope,row['revision'],json.dumps(row,ensure_ascii=False)))
            return row
    def analysis(self, doc_id, row):
        with self.tx() as db:
            db.execute('INSERT INTO analyses VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                       (row['id'],doc_id,json.dumps(row,ensure_ascii=False)))
    def analyses(self, doc_id):
        with self.tx() as db:
            return [json.loads(r['body']) for r in db.execute('SELECT body FROM analyses WHERE doc_id=? ORDER BY rowid DESC',(doc_id,))]

    def freeze(self, case_id, doc_id):
        from screenshotlegal.domain.common.models import digest,now
        with self.tx() as db:
            row=self.get(case_id,doc_id,db)
            if row["status"]!="complete": raise ValueError("选中文档尚未解析完成，不能冻结为完整案件输入")
            blocks=[json.loads(r["body"]) for r in db.execute("SELECT body FROM blocks WHERE doc_id=? ORDER BY ordinal",(doc_id,))]
            blocks=[{k:b.get(k) for k in ["id","ordinal","page","type","text","bbox","coordinate_space","table_rows","table_cells","vendor_source_ref","parent_id","children"]} for b in blocks]
            for block in blocks:block["children"]=block.get("children") or []
            payload=dict(case_id=case_id,document_id=doc_id,evidence_id=row.get("evidence_id") or "document."+doc_id,source_sha256=row["sha256"],parser=row["parser"],producer=row.get("producer"),document_version=row["version"],pages=row["total_pages"],blocks=blocks,profile=row.get("parse_profile"),profile_digest=row.get("profile_digest","legacy"),parse_run_id=row.get("parse_run_id",doc_id),artifacts=row.get('artifacts',[]))
            id=digest(payload)
            old=db.execute("SELECT body FROM parse_snapshots WHERE id=? AND case_id=?",(id,case_id)).fetchone()
            if old:return json.loads(old["body"])
            result=dict(payload,id=id,created_at=now(),schema_version="document-snapshot.v1")
            db.execute("INSERT INTO parse_snapshots VALUES (?,?,?,?)",(id,case_id,doc_id,json.dumps(result,ensure_ascii=False)))
            return result
    def snapshot(self, case_id, snapshot_id):
        with self.tx() as db:
            row=db.execute("SELECT body FROM parse_snapshots WHERE id=? AND case_id=?",(snapshot_id,case_id)).fetchone()
            if row is None:raise KeyError("解析快照不存在")
            return json.loads(row["body"])

    def submit_job(self,case_id,doc_id,pages,all_pages,actor):
        import time,uuid
        with self.tx() as db:
            row=self.get(case_id,doc_id,db)
            old=db.execute("SELECT body FROM parse_jobs WHERE case_id=? AND doc_id=? AND status IN ('queued','running')",(case_id,doc_id)).fetchone()
            if old:return json.loads(old['body'])
            job=dict(id=uuid.uuid4().hex,case_id=case_id,document_id=doc_id,status='succeeded' if row['status']=='complete' else 'queued',
                     pages=pages,all_pages=all_pages,actor_id=actor,created_at=time.time(),updated_at=time.time(),
                     parsed_pages=row['parsed_pages'],total_pages=row['total_pages'],cancel_requested=False,error=None)
            db.execute('INSERT INTO parse_jobs VALUES (?,?,?,?,?,?,?)',(job['id'],case_id,doc_id,job['status'],0,None,json.dumps(job)))
            return job
    def jobs(self,case_id,doc_id=None):
        with self.tx() as db:
            sql='SELECT body FROM parse_jobs WHERE case_id=?';args=[case_id]
            if doc_id:sql+=' AND doc_id=?';args.append(doc_id)
            return [json.loads(r['body']) for r in db.execute(sql+' ORDER BY rowid DESC',args)]
    def job(self,case_id,job_id):
        with self.tx() as db:
            row=db.execute('SELECT body FROM parse_jobs WHERE case_id=? AND id=?',(case_id,job_id)).fetchone()
            if row is None:raise KeyError('解析任务不存在')
            return json.loads(row['body'])
    def claim_job(self):
        import time,uuid
        with self.tx() as db:
            row=db.execute("SELECT * FROM parse_jobs WHERE status='queued' OR (status='running' AND lease_until<?) ORDER BY rowid LIMIT 1",(time.time(),)).fetchone()
            if row is None:return None
            body=json.loads(row['body']);token=uuid.uuid4().hex
            body.update(status='running',updated_at=time.time())
            db.execute('UPDATE parse_jobs SET status=?,lease_until=?,lease_token=?,body=? WHERE id=?',
                       ('running',time.time()+300,token,json.dumps(body),body['id']))
            return body|dict(lease_token=token)
    def settle_job(self,job,status,document,error=None):
        import time
        with self.tx() as db:
            old=db.execute('SELECT body,lease_token FROM parse_jobs WHERE id=?',(job['id'],)).fetchone()
            if old is None or old['lease_token']!=job['lease_token']:return False
            body=json.loads(old['body'])
            body.update(status='cancelled' if body['cancel_requested'] else status,parsed_pages=document['parsed_pages'],
                        total_pages=document['total_pages'],updated_at=time.time(),error=error)
            db.execute('UPDATE parse_jobs SET status=?,lease_until=0,lease_token=NULL,body=? WHERE id=?',(body['status'],json.dumps(body),body['id']))
            return True
    def cancel_job(self,case_id,job_id):
        import time
        with self.tx() as db:
            row=db.execute('SELECT body FROM parse_jobs WHERE case_id=? AND id=?',(case_id,job_id)).fetchone()
            if row is None:raise KeyError('解析任务不存在')
            body=json.loads(row['body'])
            if body['status'] in {'queued','running'}:
                body['cancel_requested']=True;body['updated_at']=time.time()
                if body['status']=='queued':body['status']='cancelled'
                db.execute('UPDATE parse_jobs SET status=?,body=? WHERE id=?',(body['status'],json.dumps(body),job_id))
            return body
    def continue_job(self,job,document):
        import time
        with self.tx() as db:
            row=db.execute('SELECT body,lease_token FROM parse_jobs WHERE id=?',(job['id'],)).fetchone()
            if row is None or row['lease_token']!=job['lease_token']:return False
            body=json.loads(row['body'])
            body.update(status='cancelled' if body['cancel_requested'] else 'queued',parsed_pages=document['parsed_pages'],
                        total_pages=document['total_pages'],updated_at=time.time())
            db.execute('UPDATE parse_jobs SET status=?,lease_until=0,lease_token=NULL,body=? WHERE id=?',(body['status'],json.dumps(body),body['id']))
            return True

    def ensure_index(self,doc_id):
        from screenshotlegal.infrastructure.retrieval.fts import tokenize
        with self.tx() as db:
            indexed=db.execute("SELECT count(*) FROM block_search WHERE doc_id=?",(doc_id,)).fetchone()[0]
            count=db.execute("SELECT count(*) FROM blocks WHERE doc_id=?",(doc_id,)).fetchone()[0]
            if indexed==count:return
            db.execute("DELETE FROM block_search WHERE doc_id=?",(doc_id,))
            for row in db.execute("SELECT body FROM blocks WHERE doc_id=? ORDER BY ordinal",(doc_id,)).fetchall():
                block=json.loads(row["body"])
                db.execute("INSERT INTO block_search(doc_id,block_id,terms) VALUES (?,?,?)",(doc_id,block["id"]," ".join(tokenize(block["text"]))))

    def queue_publication(self,case_id,doc_id,snapshot,sources,actor):
        from screenshotlegal.domain.common.models import now
        with self.tx() as db:
            row=db.execute('SELECT body FROM publications WHERE id=? AND case_id=?',(snapshot['id'],case_id)).fetchone()
            if row:
                value=json.loads(row['body'])
                if value['status']=='published':return value
            value=dict(id=snapshot['id'],case_id=case_id,document_id=doc_id,parse_run_id=snapshot['parse_run_id'],
                       status='pending',actor_id=actor,created_at=now(),sources=sources,error=None)
            db.execute('INSERT INTO publications VALUES (?,?,?) ON CONFLICT(id) DO UPDATE SET body=excluded.body',
                       (value['id'],case_id,json.dumps(value,ensure_ascii=False)))
            return value
    def publications(self,case_id=None,pending=False):
        with self.tx() as db:
            sql='SELECT body FROM publications WHERE 1=1';args=[]
            if case_id:sql+=' AND case_id=?';args.append(case_id)
            if pending:sql+=" AND json_extract(body,'$.status')='pending'"
            return [json.loads(r['body']) for r in db.execute(sql,args)]
    def publication_state(self,value,status,error=None):
        from screenshotlegal.domain.common.models import now
        value=dict(value,status=status,error=error,updated_at=now())
        with self.tx() as db:db.execute('UPDATE publications SET body=? WHERE id=? AND case_id=?',(json.dumps(value,ensure_ascii=False),value['id'],value['case_id']))
        return value
