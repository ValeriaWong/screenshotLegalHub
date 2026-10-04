"""Reviewed presentation overlays: conversations, legal events and contract evidence.

Does not relabel original evidence or overwrite model responses. All references are
resolved against the current case; inference/checkpoint and observed facts differ.
"""
import json
from pathlib import Path
from legalhub import benchmark as b
from legalhub.case_timeline import build_timeline

LABELS={
 'invitation':('要约邀请','Invitation to offer'),'offer':('要约','Offer'),
 'withdrawal':('要约撤回','Withdrawal of offer'),'revocation':('要约撤销','Revocation of offer'),
 'acceptance':('承诺','Acceptance'),'counteroffer':('反要约 / 新要约','Counteroffer / new offer'),
 'authorization':('授权范围','Scope of authority'),'performance_notice':('付款履行线索','Payment performance evidence'),
 'receipt_confirmation':('受领确认','Receipt confirmation'),'variation':('合同变更 / 补款','Variation / additional payment'),
 'negotiation':('交易磋商','Negotiation'),'formation':('合同成立','Contract formation'),
 'termination':('解除','Termination'),'factual_statement':('履行事实陈述','Performance statement'),
 'demand':('履行请求 / 催告','Request for performance'),'other':('其他法律意义','Other legal significance'),'uncertain':('法律性质待核','Legal characterization unresolved')}

def localized(zh,en=None):return {'zh':zh,'en':en or zh}

def presentation(material,path):
    if not path or not Path(path).exists():return {}
    overlay=b.read(path)
    if overlay['case_id']!=material['metadata']['case_id']:raise ValueError('Presentation belongs to another case')
    expected={x['image_id']:x['sha256'] for x in material['images']}
    if overlay['source_hashes']!=expected:raise ValueError('Presentation original images changed')
    if overlay.get('source_corpus_sha256')!=material['metadata'].get('source_corpus_sha256'):raise ValueError('Presentation transcription changed')
    return overlay

def conversation_groups(material,overlay):
    image_ids={x['image_id'] for x in material['images']};assigned={};groups=[]
    for item in overlay.get('conversations',[]):
        if not item.get('id') or not item.get('name'):raise ValueError('Conversation needs an ID and name')
        for id in item['image_ids']:
            if id not in image_ids or id in assigned:raise ValueError('Invalid or duplicate conversation image')
            assigned[id]=item['id']
        groups.append(dict(item))
    for image in material['images']:
        if image['image_id'] in assigned:continue
        original=image.get('conversation_id','');confirmed=original and not original.startswith('unconfirmed:')
        id=original if confirmed else 'unverified:'+image['image_id']
        found=next((x for x in groups if x['id']==id),None)
        if found:found['image_ids'].append(image['image_id'])
        else:
            title=image.get('conversation_name') or image.get('chat_title')
            name=localized(title) if title else localized('会话未核实 · 截图 '+str(image['display_page']),'Unverified conversation · Image '+str(image['display_page']))
            groups.append({'id':id,'name':name,'image_ids':[image['image_id']],
                           'basis':'registered_conversation' if confirmed else 'unverified_separate_source','identity_status':'unverified'})
        assigned[image['image_id']]=id
    return groups,assigned

def build_presentation(material,analysis,path=None):
    overlay=presentation(material,path);conversations,assigned=conversation_groups(material,overlay)
    graph=build_timeline(material,analysis,assigned)
    messages={x['id']:x for x in material['records']};short={f'M{n:03d}':x for n,x in enumerate(material['records'],1)}
    position={x['id']:n for n,x in enumerate(material['records'])};rank={x['image_id']:x['display_page'] for x in material['images']}
    meanings=(analysis or {}).get('meanings',[])
    def resolve(keys):
        if not keys:raise ValueError('Observed legal item needs sources')
        rows=[]
        for key in keys:
            row=messages.get(key) or short.get(key)
            if not row or row['case_id']!=material['metadata']['case_id']:raise ValueError('Legal source outside case')
            rows.append(row)
        return rows
    def refs(rows):return [dict(ref,quote=row['text']) for row in rows for ref in row['source_refs']]
    laws={x['id']:x for x in b.read(b.ROOT/'blocks/retriever/artifacts/statutes/civil-code-2020.json')['records']}
    events=[]
    candidates=overlay.get('legal_events')
    if candidates is None:
        candidates=[{'id':r['id'],'type':r['interpretation'].get('declaration_type','uncertain'),
                     'status':'candidate','title':localized(r['title']),
                     'description':localized(r['interpretation'].get('expression_meaning','')),
                     'legal_test':localized(r['interpretation'].get('legal_significance','')),
                     'sources':r['supporting_message_ids'],'article_ids':r['interpretation'].get('law_ids',[]),'term_keys':[]} for r in meanings]
    seen=set()
    for item in candidates:
        if item['id'] in seen or item['type'] not in LABELS:raise ValueError('Invalid legal event')
        seen.add(item['id']);rows=resolve(item['sources']);mids=[x['id'] for x in rows]
        linked=[r for r in meanings if set(mids)&set(r['supporting_message_ids']) and
                (not item.get('meaning_types') or r['interpretation']['declaration_type'] in item['meaning_types'])]
        for id in item.get('article_ids',[]):
            if id not in laws:raise ValueError('Unknown legal provision')
        all_images={x['image_id'] for x in rows}|{ref['image_id'] for r in linked for ref in r['source_refs']}
        first=min(mids,key=position.__getitem__)
        events.append(dict(item,id='legal:'+item['id'],type_label=localized(*LABELS[item['type']]),
                           message_ids=mids,meaning_ids=[r['id'] for r in linked],source_refs=refs(rows),
                           image_ids=sorted({x['image_id'] for x in rows},key=rank.__getitem__),
                           source_image_ids=sorted(all_images,key=rank.__getitem__),time=graph['message_times'][first],
                           conversation_ids=list(dict.fromkeys(assigned[x['image_id']] for x in rows)),
                           law_refs=[laws[x] for x in item.get('article_ids',[])],
                           provenance='assistant_reviewed_source_annotation' if overlay.get('legal_events') is not None else 'model_interpretation_candidate'))
    events.sort(key=lambda x:min(position[m] for m in x['message_ids']))
    terms=[]
    for item in overlay.get('contract_terms',(analysis or {}).get('contract_terms',[])):
        rows=resolve(item['sources']) if item.get('sources') else []
        if not rows and item['status']!='missing':raise ValueError('Contract evidence needs sources')
        terms.append(dict(item,source_refs=refs(rows),message_ids=[x['id'] for x in rows],
                          event_ids=[x['id'] for x in events if item['key'] in x.get('term_keys',[])],
                          conversation_ids=list(dict.fromkeys(assigned[x['image_id']] for x in rows))))
    for page in graph['pages']:
        page['conversation_id']=assigned[page['image_id']]
        page['legal_event_ids']=[x['id'] for x in events if page['image_id'] in x['image_ids']]
    for mid,links in graph['message_links'].items():
        links['legal_event_ids']=[x['id'] for x in events if mid in x['message_ids'] or set(links['meaning_ids'])&set(x['meaning_ids'])]
    for id,links in graph['meaning_links'].items():links['legal_event_ids']=[x['id'] for x in events if id in x['meaning_ids']]
    graph.update(fact_nodes=graph['milestones'],milestones=events,legal_events=events,conversations=conversations,
                 image_conversations=assigned,contract_terms=terms,legal_checkpoints=overlay.get('legal_checkpoints',[]),
                 translations=overlay.get('translations',{}),presentation_origin=overlay.get('review_note',{}))
    return graph
