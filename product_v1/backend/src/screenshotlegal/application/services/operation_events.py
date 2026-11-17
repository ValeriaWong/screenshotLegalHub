"""Public durable operation events in the owning case/config transaction."""
from uuid import uuid4
from datetime import datetime,timezone
from screenshotlegal.domain.common.audit import operation_context

def operation(owner,product,action,object_type,object_id,changes,reason=''):
    ctx=operation_context.get();id='operation.'+uuid4().hex
    return dict(id=id,contract='operation.audit.v1',owner=owner,actor_id=ctx.get('actor_id') or owner,actor_type=ctx.get('actor_type','user'),product=product,
                action=action,object_type=object_type,object_id=object_id,changes=changes,reason=reason,
                occurred_at=datetime.now(timezone.utc).isoformat(),request_id=ctx.get('request_id'),correlation_id=ctx.get('correlation_id'))

def record(event):
    return ('run_events',event['id'],event,'','operation-audit:'+event['owner'],True)

def pending(repo,owner):
    return [e for e in repo.list('run_events',run_id='operation-audit:'+owner) if e.get('contract')=='operation.audit.v1' and e.get('owner')==owner]
