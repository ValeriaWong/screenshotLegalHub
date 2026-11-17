from screenshotlegal.domain.common.models import digest, Entity, ProofGraph, MatrixRow

OUTPUT_TABLES = dict(claim='case_claims',element='case_elements',fact='fact_propositions',burden='burden_assignments',
    evidence_link='evidence_links',gap='evidence_gaps',contradiction='contradictions',strategy='strategy_items',event='events')

def semantic_digest(entity):
    return digest({k:v for k,v in entity.items() if k not in ['analysis_run_id','skill_run_id','output_digest','review_status','case_id']})

def run_entities(repo,run_id):
    if not run_id:
        return []
    entities=[]
    for row in repo.list('analysis_snapshots',run_id=run_id):
        entities.extend(row['entities'])
    return entities

def decorate_reviews(repo,case_id,entities):
    reviews=repo.list('review_decisions',case_id=case_id)
    for entity in entities:
        relevant=sorted((r for r in reviews if r['target_id']==entity['id']),key=lambda r:r['created_at'])
        if relevant:
            latest=relevant[-1]
            entity['review_status']=latest['action'] if latest['reviewed_output_digest']==entity['output_digest'] else 'stale'
            if entity['review_status']=='edited':
                entity['details']['reviewed_text']=latest['text']
    return entities

def graph(repo,case_id,run_id=None):
    case=repo.get('cases',case_id)
    run_id=run_id or case.get('active_analysis_run_id')
    entities=run_entities(repo,run_id)
    if run_id:
        inputs=repo.get('analysis_runs',run_id)['input_snapshot']
        for kind,rows in [('evidence',inputs['evidence']),('message',inputs['messages']),('source_ref',inputs['source_refs']),('authority',inputs['matter']['authorities'])]:
            for row in rows:
                raw=Entity(id=row['id'],kind=kind,title=row.get('text') or row.get('quote') or row.get('title') or row.get('filename') or row['id'],case_id=case_id,analysis_run_id=run_id,source_refs=row.get('source_refs',[]),details=row).model_dump()
                raw['output_digest']=semantic_digest(raw)
                entities.append(raw)
        for claim in inputs['matter']['claims']:
            remedy=Entity(id='remedy.'+claim['id'],kind='remedy',title=claim['remedy'],details={'claim_id':'claim.'+claim['id']}).model_dump()
            remedy['output_digest']=semantic_digest(remedy);entities.append(remedy)
    # A human reviews the proposition together with its current evidence basis.
    for entity in entities:
        if entity['kind']=='fact':
            links=[e for e in entities if e['kind']=='evidence_link' and e['details']['fact_id']==entity['id']]
            strengths=[e for e in entities if e['kind']=='strength' and e['details']['fact_id']==entity['id']]
            entity['status']=strengths[0]['status'] if strengths else entity.get('status','unknown')
            entity['source_refs']=list(dict.fromkeys(r for link in links for r in link['source_refs'])) if links else entity['source_refs']
            source_digests={r['id']:digest(r) for r in inputs['source_refs']}
            entity['details']['evidence_basis']=[link['output_digest'] for link in links]+[source_digests[r] for r in entity['source_refs'] if r in source_digests]
            entity['output_digest']=semantic_digest(entity)
    entities=decorate_reviews(repo,case_id,entities)
    edges=[]
    for e in entities:
        for key in ['claim_id','element_id','fact_id','contradiction_id','evidence_id','message_id']:
            if e['details'].get(key):
                edges.append(dict(source=e['id'],target=e['details'][key],relation=key.removesuffix('_id')))
        for ref in e['source_refs']:
            edges.append(dict(source=ref,target=e['id'],relation='grounds'))
    bindings=[]
    if run_id:
        frozen_refs={r["id"]:r for r in inputs["source_refs"]}
        for e in entities:
            if e["kind"] in {"source_ref","message","evidence","authority"}:continue
            for rid in e["source_refs"]:
                ref=frozen_refs.get(rid)
                if ref is None:
                    bindings.append(dict(entity_id=e["id"],source_ref_id=rid,resolution="unresolved"))
                    continue
                bindings.append(dict(analysis_run_id=run_id,entity_id=e["id"],entity_output_digest=e["output_digest"],
                    source_ref_id=rid,parse_run_id=ref.get("parse_run_id"),snapshot_id=ref.get("parse_snapshot_id"),
                    source_locator=ref.get("source_locator"),publication_id=ref.get("parse_snapshot_id"),source_text_digest=ref.get("text_digest") or digest(ref.get("text",ref.get("quote",""))),
                    resolution=ref.get("spatial_resolution","region" if ref.get("bbox") else "none"),
                    relation=e["details"].get("relation","context"),review_status=e["review_status"]))
    return ProofGraph(analysis_run_id=run_id,entities=entities,edges=edges,citation_bindings=bindings)

def matrix(repo,case_id):
    entities=graph(repo,case_id).entities
    result=[]
    by_id={e.id:e for e in entities}
    for fact in entities:
        if fact.kind!='fact' or not fact.details.get('claim_id'):
            continue
        related=lambda kind:[e for e in entities if e.kind==kind and e.details.get('fact_id')==fact.id]
        links=related('evidence_link');strength=related('strength')
        fact=fact.model_copy(update={'status':strength[0].status if strength else 'unknown','source_refs':list(dict.fromkeys(r for l in links for r in l.source_refs))})
        burden=related('burden')
        result.append(MatrixRow(claim=by_id[fact.details['claim_id']],element=by_id[fact.details['element_id']],fact=fact,burden=burden[0] if burden else None,
            supporting=[l for l in links if l.details['relation']=='supports'],contradicting=[l for l in links if l.details['relation']=='contradicts'],gaps=related('gap'),strength=strength[0].details['strength'] if strength else 'unknown'))
    return result
