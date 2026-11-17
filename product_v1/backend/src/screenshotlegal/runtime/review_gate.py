from screenshotlegal.domain.common.models import now
from screenshotlegal.runtime.events import emit

def create_gate(repo, run, gate_id, auto=False):
    gate=dict(id=run['id']+':'+gate_id,gate_id=gate_id,run_id=run['id'],status='APPROVED' if auto else 'WAITING_REVIEW',created_at=now())
    repo.put('review_gates',gate['id'],gate,run['case_id'],run['id'])
    if not auto:
        emit(repo,run['id'],'review-required',gate)
    return gate

def resolve_gate(repo,run_id,gate_id,action):
    gate=repo.get('review_gates',run_id+':'+gate_id)
    if gate['status']!='WAITING_REVIEW':
        raise ValueError('Gate already resolved')
    gate.update(status='APPROVED' if action=='approve' else 'REJECTED',resolved_at=now())
    repo.put('review_gates',gate['id'],gate,run_id=run_id)
    emit(repo,run_id,'review-resolved',gate)
    return gate
