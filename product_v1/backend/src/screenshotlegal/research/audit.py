"""Append-only, owner-scoped operation events. Shared by use cases and workers."""
import contextvars
import json
import logging
from .contracts import uid, now, dumps, digest

from screenshotlegal.domain.common.audit import operation_context as context
transaction = contextvars.ContextVar('research_audit_transaction', default=None)
log = logging.getLogger(__name__)

DDL = [
    'CREATE TABLE IF NOT EXISTS schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL)',
    '''CREATE TABLE IF NOT EXISTS audit_events (
        seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT NOT NULL UNIQUE, schema_version INTEGER NOT NULL,
        owner TEXT NOT NULL, actor_id TEXT NOT NULL, actor_type TEXT NOT NULL, product TEXT NOT NULL,
        action TEXT NOT NULL, object_type TEXT NOT NULL, object_id TEXT NOT NULL, outcome TEXT NOT NULL,
        occurred_at TEXT NOT NULL, request_id TEXT, correlation_id TEXT, parent_event_id TEXT,
        event_key TEXT NOT NULL, context_json TEXT NOT NULL, changes_json TEXT NOT NULL, reason TEXT NOT NULL,
        result_ref TEXT, UNIQUE(owner,event_key))''',
    'CREATE INDEX IF NOT EXISTS audit_owner_correlation ON audit_events(owner,correlation_id,occurred_at)',
    'CREATE INDEX IF NOT EXISTS audit_owner_request ON audit_events(owner,request_id)',
    "CREATE INDEX IF NOT EXISTS audit_owner_model_call ON audit_events(owner,json_extract(context_json,'$.model_call_id'))",
    "CREATE INDEX IF NOT EXISTS audit_owner_provider_call ON audit_events(owner,json_extract(context_json,'$.provider_request_id'))",
    'CREATE INDEX IF NOT EXISTS audit_owner_time ON audit_events(owner,occurred_at,seq)',
    'CREATE INDEX IF NOT EXISTS audit_owner_object ON audit_events(owner,object_type,object_id,seq)',
    'CREATE INDEX IF NOT EXISTS audit_owner_product ON audit_events(owner,product,action,seq)',
    "CREATE TRIGGER IF NOT EXISTS audit_no_update BEFORE UPDATE ON audit_events BEGIN SELECT RAISE(ABORT,'Audit events are append-only'); END",
    "CREATE TRIGGER IF NOT EXISTS audit_no_delete BEFORE DELETE ON audit_events BEGIN SELECT RAISE(ABORT,'Audit events are append-only'); END",
]

SENSITIVE = {'api_key','encrypted_api_key','ciphertext','authorization','cookie','password','secret','lease_token','access_token','refresh_token','session_token'}
def safe(value, depth=0):
    if depth > 6: return '[nested value]'
    if isinstance(value,dict):
        return {str(k): '[redacted]' if str(k).lower()=='token' or any(word in str(k).lower() for word in SENSITIVE) else safe(v,depth+1) for k,v in value.items() if k not in ['raw','response','source_text','metadata']}
    if isinstance(value,list): return [safe(v,depth+1) for v in value[:100]]
    if isinstance(value,str): return value[:2000]+('…' if len(value)>2000 else '')
    return value

def emit(db,owner,action,object_type,object_id,*,outcome='success',event_key=None,details=None,changes=None,reason='',result_ref=None,occurred_at=None):
    ctx=context.get()
    details={**{k:ctx[k] for k in ['model_call_id','job_id','sample_id'] if ctx.get(k)},**(details or {})}
    row=dict(id=uid('audit'),schema_version=1,owner=owner,actor_id=ctx.get('actor_id') or owner,
             actor_type=ctx.get('actor_type','user'),product=ctx.get('product') or ('studio' if action.startswith('studio') else 'evaluation' if action.startswith('evaluation') else 'review'),
             action=action,object_type=object_type,object_id=object_id,outcome=outcome,occurred_at=occurred_at or now(),
             request_id=ctx.get('request_id'),correlation_id=ctx.get('correlation_id'),parent_event_id=ctx.get('parent_event_id'),
             event_key=event_key or uid('event'),context_json=dumps(safe(details or {})),changes_json=dumps(safe(changes or {})),reason=reason[:2000],result_ref=result_ref)
    db.execute('INSERT OR IGNORE INTO audit_events ('+','.join(row)+') VALUES ('+','.join('?' for _ in row)+')',list(row.values()))
    return row

def record(db,kind,body,owner,old=None):
    if kind in ['gateway.credential','review.draft','benchmark.draft'] or old==body: return
    tracked=('benchmark.','review.','studio.','evaluation.','research.flow')
    if not kind.startswith(tracked): return
    context_keys=['sample_id','revision','content_hash','manifest_id','published_manifest','layout_hash','prompt_id','batch_id','run_id','job_id','release_id','supersedes','coverage','protocol_id','question_id','flow_id','mode','scope','dataset_id','task_id','image_name','annotation_id','pipeline_id','node_id','prediction_id','match_id','score_set_id','asset_sha256','source_task_hash','response_hash','scorer_version','version']
    details={k:body[k] for k in context_keys if k in body}
    response=body.get('response') or (body.get('error') or {}).get('evidence') or {}
    if kind=='benchmark.attempt' and body.get('request_id'): details['model_call_id']=body['request_id']
    if kind=='evaluation.request':details['model_call_id']=body['id']
    elif response.get('request_id'):details['model_call_id']=response['request_id']
    if response.get('provider_request_id'):details['provider_request_id']=response['provider_request_id']
    object_id=body.get('sample_id') if kind=='review.revision' else body['id']
    changes=body.get('diff') if kind=='review.revision' else {k:dict(before=(old or {}).get(k),after=v) for k,v in body.items() if k not in ['raw','response','content','source','model','metadata','revision','entries','tasks','checkpoints','images','image_files','source_files'] and (old or {}).get(k)!=v}
    if kind=='review.revision': details.update(revision=body['number'],layout_diff=body.get('layout_diff'),invalidated_gold=body.get('invalidated_gold',[]))
    if kind=='review.release': details.update(release_id=body['id'],sample_ids=[e['sample_id'] for e in body['entries']])
    if kind=='evaluation.run': details.update(run_id=body['id'],release_id=body['release_id'],sample_ids=body['frozen_sample_ids'])
    if kind=='studio.batch': details.update(batch_id=body['id'],sample_id=body['source']['sample_id'],sample_ids=body['sample_ids'])
    emit(db,owner,kind+('.updated' if old else '.created'),kind,object_id,outcome=body['status'] if kind=='evaluation.request' and body.get('status') in ['failed','unknown'] else 'success',details=details,changes=changes,reason=body.get('reason') or body.get('note') or body.get('suggestions') or '',result_ref=kind+':'+body['id'])

def filters(owner, *, product='', action='', outcome='', object_id='', actor_id='', since='', until='', cursor=None, q='', correlation_id='', request_id=''):
    sql=['owner=?'];args=[owner]
    for key,value in [('product',product),('action',action),('outcome',outcome),('actor_id',actor_id),('correlation_id',correlation_id)]:
        if value: sql.append(key+'=?');args.append(value)
    if request_id:
        sql.append("(request_id=? OR json_extract(context_json,'$.model_call_id')=? OR json_extract(context_json,'$.provider_request_id')=? OR (object_type='evaluation.request' AND object_id=?))");args.extend([request_id]*4)
    if object_id:
        keys=['sample_id','batch_id','run_id','job_id','release_id','prompt_id','manifest_id','published_manifest','question_id','pipeline_id','node_id']
        sql.append('(object_id=? OR '+ ' OR '.join("json_extract(context_json,'$.%s')=?"%k for k in keys)+" OR EXISTS(SELECT 1 FROM json_each(context_json,'$.sample_ids') WHERE value=?))");args.extend([object_id]*(len(keys)+2))
    if len(q)>500: raise ValueError('关键词最多500字符')
    searchable="lower(coalesce(action,'')||' '||coalesce(object_id,'')||' '||coalesce(reason,'')||' '||context_json||' '||changes_json||' '||actor_id||' '||coalesce(request_id,'')||' '||coalesce(correlation_id,''))"
    for word in q.split():
        sql.append('instr('+searchable+',lower(?))>0');args.append(word)
    from datetime import datetime, timezone
    for key,value,op in [('since',since,'>='),('until',until,'<=')]:
        if value:
            try:
                moment=datetime.fromisoformat(value.replace('Z','+00:00'))
                if len(value)==10 and key=='until': moment=moment.replace(hour=23,minute=59,second=59,microsecond=999999)
                value=(moment.replace(tzinfo=timezone.utc) if moment.tzinfo is None else moment.astimezone(timezone.utc)).isoformat()
            except ValueError: raise ValueError('时间筛选须为ISO格式') from None
            sql.append('occurred_at'+op+'?');args.append(value)
    if cursor is not None: sql.append('(occurred_at,seq)<(SELECT occurred_at,seq FROM audit_events WHERE owner=? AND seq=?)');args.extend([owner,cursor])
    return ' AND '.join(sql),args

def unpack(row):
    value=dict(row)
    value['context']=json.loads(value.pop('context_json'));value['changes']=json.loads(value.pop('changes_json'))
    level={'failed':'ERROR','unknown':'WARN','rejected':'WARN'}.get(value['outcome'],'INFO')
    value['level']=level
    value['formatted_log']=' | '.join([value['occurred_at'],level,value['product'],value['actor_id']+'('+value['actor_type']+')',value['action'],value['object_id'],value['reason'].replace('\n',' '),"operation_request_id="+(value['request_id'] or '—'),"model_call_id="+str(value['context'].get('model_call_id') or (value['object_id'] if value['object_type']=='evaluation.request' else '—')),"provider_request_id="+str(value['context'].get('provider_request_id') or '—')])
    return value

def query(store,owner,limit=50,**kwargs):
    if not 1<=limit<=200: raise ValueError('审计分页大小须在1到200之间')
    where,args=filters(owner,**kwargs)
    with store.read() as db:
        rows=list(db.execute('SELECT * FROM audit_events WHERE '+where+' ORDER BY occurred_at DESC,seq DESC LIMIT ?',args+[limit+1]))
    return dict(items=[unpack(r) for r in rows[:limit]],next_cursor=rows[limit-1]['seq'] if len(rows)>limit else None)

def summary(store,owner,group_by='day',**kwargs):
    kwargs.pop('cursor',None);where,args=filters(owner,**kwargs)
    with store.read() as db:
        outcomes=dict(db.execute('SELECT outcome,count(*) FROM audit_events WHERE '+where+' GROUP BY outcome',args))
        actions=dict(db.execute('SELECT action,count(*) FROM audit_events WHERE '+where+' GROUP BY action',args))
        day="strftime('%Y-%m-%d',occurred_at,'+8 hours')"
        days=dict(db.execute('SELECT '+day+',count(*) FROM audit_events WHERE '+where+' GROUP BY '+day,args))
        field={'day':day,'product':'product','action':'action','actor':'actor_id','outcome':'outcome'}.get(group_by)
        if not field: raise ValueError('不支持的聚合维度')
        groups=dict(db.execute('SELECT '+field+',count(*) FROM audit_events WHERE '+where+' GROUP BY '+field+' ORDER BY count(*) DESC',args))
    return dict(total=sum(outcomes.values()),outcomes=outcomes,actions=actions,days=days,groups=groups,group_by=group_by,timezone='Asia/Singapore')
