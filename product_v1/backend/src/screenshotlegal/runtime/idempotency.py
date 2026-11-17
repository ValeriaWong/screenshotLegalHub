from screenshotlegal.domain.common.models import digest

def idempotency_key(run_id, node_id, input_digest, skill_digest, matter_digest):
    return digest([run_id,node_id,input_digest,skill_digest,matter_digest])
