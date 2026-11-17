from screenshotlegal.domain.common.models import digest, now, SkillContext, SkillInput
from screenshotlegal.runtime.context_projection import project
from screenshotlegal.runtime.idempotency import idempotency_key
from screenshotlegal.runtime.retry import with_retry
from screenshotlegal.runtime.events import emit
from screenshotlegal.application.services.proof import run_entities, semantic_digest, OUTPUT_TABLES
from screenshotlegal.plugins.skills.deterministic import DeterministicSkill

class StageExecutor:
    def __init__(self,repo,skills):
        self.repo,self.skills=repo,skills
        self.factory=DeterministicSkill

    async def execute_node(self,run,node):
        repo=self.repo
        # Reload committed snapshots for every node; parallel peers do not share mutable state.
        entities=run_entities(repo,run['id'])
        base=run['input_snapshot']
        state=dict(base,proof_graph=entities)
        for selector,kind in [('claims','claim'),('elements','element'),('facts','fact'),('evidence_links','evidence_link')]:
            state[selector]=[e for e in entities if e['kind']==kind]
        values=project(node.input_selectors,state)
        input_digest=digest(values)
        key=idempotency_key(run['id'],node.node_id,input_digest,node.skill_digest,run['matter_pack_digest'])
        if repo.optional('analysis_snapshots',key):
            return
        manifest=self.skills.skills[node.resolved_skill_id]
        self.skills.authorize(manifest)
        if self.skills.digests[manifest.id]!=node.skill_digest:
            raise ValueError('Skill digest changed after compilation')
        emit(repo,run['id'],'node-started',dict(node_id=node.node_id,stage=node.stage))
        skill=self.factory(manifest)
        async def operation():
            result=await skill.run(SkillContext(case_id=run['case_id'],run_id=run['id'],projection=values),SkillInput(values=values))
            refs={r['id'] for r in base['source_refs']}
            for item in result.entities:
                if item.kind not in node.output_targets:
                    raise ValueError('Skill output violates declared output schema')
                if any(ref not in refs for ref in item.source_refs):
                    raise ValueError('Output contains foreign source reference')
                if manifest.grounding['require_source_refs'] and item.kind!='gap' and not item.source_refs:
                    raise ValueError('Grounded output requires source refs')
            return result
        async def attempt(number,result,error,latency):
            sid=key+':'+str(number)
            audit=dict(id=sid,analysis_run_id=run['id'],node_id=node.node_id,stage=node.stage,attempt=number,skill_id=manifest.id,skill_version=manifest.version,skill_digest=node.skill_digest,
                input_digest=input_digest,output_digest=digest(result.model_dump()) if result else None,idempotency_key=key,matter_digest=run['matter_pack_digest'],status='FAILED' if error else 'COMPLETED',latency=latency,token_usage={},warnings=result.warnings if result else [],error=type(error).__name__ if error else None,permissions=manifest.permissions,trust=manifest.trust)
            records=[('skill_runs',sid,audit,run['case_id'],run['id'],True)]
            if result:
                refs={r['id'] for r in base['source_refs']}
                output=[]
                for item in result.entities:
                    e=item.model_dump();e.update(case_id=run['case_id'],analysis_run_id=run['id'],skill_run_id=sid)
                    if e['kind'] not in node.output_targets:
                        raise ValueError('Skill output violates declared output schema')
                    if any(ref not in refs for ref in e['source_refs']):
                        raise ValueError('Output contains foreign source reference')
                    if manifest.grounding['require_source_refs'] and e['kind'] not in ['gap'] and not e['source_refs']:
                        raise ValueError('Grounded output requires source refs')
                    e['output_digest']=semantic_digest(e);output.append(e)
                    if e['kind'] in OUTPUT_TABLES:
                        records.append((OUTPUT_TABLES[e['kind']],run['id']+':'+e['id'],e,run['case_id'],run['id'],True))
                records.append(('analysis_snapshots',key,dict(id=key,node_id=node.node_id,entities=output,requires_review=result.requires_review),run['case_id'],run['id'],True))
            repo.batch(records)
            emit(repo,run['id'],'node-progress',dict(node_id=node.node_id,attempt=number,status=audit['status']))
        try:
            result=await with_retry(operation,node.retry_policy,attempt)
        except Exception as error:
            emit(repo,run['id'],'node-failed',dict(node_id=node.node_id,error=type(error).__name__))
            raise
        emit(repo,run['id'],'node-completed',dict(node_id=node.node_id,requires_review=result.requires_review))
