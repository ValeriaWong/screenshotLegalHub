"""L06 — Capturing Legal Reasoning Paths from Facts to Law in Court Judgments.
论文出处：Kondo et al. (2025), arXiv:2508.17340v1 §§2.1–2.3.
Author resources rkondo3/CapturingLegalReasoningPaths @
918996f82037b7a9d6541ccbdc9553f0308a164d. No Python pipeline was released.
复现程度：paper-pipeline reimplementation using exact author Japanese prompts,
released ontology and original workbook sections. NOT author Python execution.
Original: sectioned Japanese judgments + case overview -> six node labels ->
canonical provisions -> local Provision/Norm and history-aware Norm/Application,
Fact/Application edges -> RDF -> embedded fact-masked provision retrieval.
Innovation: explicit inferential paths, per-application preceding-node history,
canonical legal references; not a generic graph prompt or chat debate wrapper.
Benchmark: 648 Japanese administrative judgments, expert node/edge annotations,
fact-masked provision retrieval; full dataset scores are NOT reproduced here.
Original I/O: judgment sections + overview -> extracted spans, normalized titles,
three typed edge families and RDF; query facts -> statutory provisions.
Our adaptation: supplied/frozen text blocks replace original unavailable HTML
preprocessor; missing native overview is disclosed. DeepSeek replaces GPT-4o.
JSON/code-fence parsing, candidate-ID transport and strict edge validation are our
code; unknown endpoints are rejected, no paid retry/JSON-repair call. The released
ontology's inverse properties are derived mechanically, not additional LLM edges.
Unmatched extracted spans are retained and marked, never given fake offsets.
Chat statements are explicitly unverified assertions, not judicial findings.
Product projection is one EXTRA call, reads graph plus frozen citation anchors.
Local model inference/training is absent. Embedding/Annoy Fact-Masked search is
NOT implemented: authorized AIPING chat config is not an embedding model. Raw
paths below only enumerate existing graph paths, not semantic provision search.
"""
import hashlib,json,re,sys
from pathlib import Path
HERE=Path(__file__).parent;sys.path.insert(0,str(HERE.parent))
from author_runtime import source,tool
SOURCE_KIND='paper_pipeline_reimplementation_with_author_prompts_ontology'
JA_LABELS={'Fact':['司法事実','Judicial Facts'],'Provision':['法律・省令・政令・規則・契約書の引用や参照','法律・省令・政令・規則・契約書','法律','Citation or Reference to Laws, Ministerial Ordinances, Cabinet Orders, Regulations, or Contracts'],'LegalNorm':['法規範','Legal Norm'],'Interpretation':['法解釈','Statutory Interpretation'],'LegalApplication':['法適用','Legal Application'],'Conclusion':['裁判の結論','Judgment Conclusion']}
PREFIX={'Fact':'事実','LegalNorm':'規範','LegalApplication':'適用','Provision':'法律'}
PROJECT='urn:screenshotlegal:legal-reasoning-paths:'
PARAMETERS=dict(model='gpt-4o',temperature=0,max_tokens=4096,parameter_origin='project bounded trial; author generation settings not released')

def parse_json(raw):
    text=raw.strip()
    if text.startswith(chr(96)*3):
        lines=text.splitlines()
        if lines[-1].strip()!=chr(96)*3:raise ValueError('Incomplete fenced JSON')
        text='\n'.join(lines[1:-1]).strip()
    value=json.loads(text)
    if not isinstance(value,(dict,list)):raise ValueError('Expected JSON object/list')
    return value

def identity(kind,value):return 'urn:sl-lkg:'+kind+':'+hashlib.sha256(value.encode('utf-8')).hexdigest()[:24]

def spans(text,quote):
    if not quote:return []
    return [dict(start=m.start(),end=m.end(),quote=quote) for m in re.finditer(re.escape(quote),text)]

def node_lists(value):
    if not isinstance(value,dict):raise ValueError('Node extraction must return label -> list')
    lookup={alias:kind for kind,aliases in JA_LABELS.items() for alias in aliases}
    unknown=[k for k,v in value.items() if k not in lookup and v not in ([],None,'該当無し','該当なし')]
    if unknown:raise ValueError('Unknown nonempty extraction labels: '+str(unknown))
    result={k:[] for k in JA_LABELS}
    for label,items in value.items():
        if label not in lookup:continue
        if items in (None,'該当無し','該当なし','なし'):items=[]
        if not isinstance(items,list):raise ValueError('Extraction label must contain a list: '+label)
        for item in items:
            if item in ('該当無し','該当なし','なし'):continue
            if not isinstance(item,str) or not item.strip():raise ValueError('Invalid extracted span')
            if item not in result[lookup[label]]:result[lookup[label]].append(item)
    missing=[k for k,aliases in JA_LABELS.items() if not any(a in value for a in aliases)]
    if missing:raise ValueError('Extraction omitted labels: '+str(missing))
    return result

def resolve(value,candidates):
    if not isinstance(value,str):raise ValueError('Edge endpoint must be a known string')
    matches=[n for n in candidates if value in (n['id'],n['label'],n['text'])]
    if len(matches)!=1:raise ValueError('Unknown/ambiguous edge endpoint: '+value[:100])
    return matches[0]

def edges_from(value,left,right,predicate,key_side='left'):
    if value==[]:return []
    if not isinstance(value,dict):raise ValueError('Edge response must be an object or empty list')
    # Author norm/application prompt leaves the JSON object shape unspecified.
    # This observed variant uses explicit application + basis fields, not a map.
    if key_side=='right' and set(value)=={'法適用','根拠規範'}:
        application=value['法適用']
        if isinstance(application,str):application=application.strip().strip('()')
        value={application:value['根拠規範']}
    result=[]
    for key,targets in value.items():
        if targets in (None,[],{},'該当無し','該当なし'):continue
        if not isinstance(targets,list):targets=[targets]
        for target in targets:
            a,b=(resolve(key,left),resolve(target,right)) if key_side=='left' else (resolve(target,left),resolve(key,right))
            edge=dict(source=a['id'],target=b['id'],predicate=predicate)
            if edge not in result:result.append(edge)
    return result

def eligible(nodes,application):
    return [n for n in nodes if n['block_index']<application['block_index'] or
        n['block_index']==application['block_index'] and n['anchors'] and application['anchors'] and n['anchors'][0]['start']<=application['anchors'][0]['start']]

def numbered(nodes):return '\n'.join('('+n['label']+')'+n['text'] for n in nodes)

def materialize(nodes,edges,documents,ontology):
    graph=[]
    for d in documents:
        graph.append({'@id':identity('document',d['id']),'@type':'lkg:Judgment' if d.get('source_status')=='published_judgment' else 'lkg:LegalDocument','project:sourceRefId':d['id'],'project:sourceStatus':d.get('source_status','unverified_party_statements')})
    for node in nodes:
        if node['kind'] not in ('Fact','Provision','LegalNorm','LegalApplication'):continue
        record={'@id':node['id'],'@type':'lkg:'+node['kind'],'project:label':node['label'],'project:extractionStatus':'literal_span_verified' if node['anchors'] else 'unmatched_or_normalized_text','project:assertionStatus':node['source_status'],'lkg:sourceDocument':{'@id':identity('document',node['document_id'])}}
        if node['kind']=='Provision':
            record['project:canonicalTitle']=node['text']
            record['lkg:sourceDocument']=[{'@id':identity('document',d)} for d in sorted({o['document_id'] for o in node['source_occurrences']})]
        if node['anchors']:record['lkg:sourceText']=node['text']
        else:record['project:unmatchedExtractedText']=node['text']
        graph.append(record)
    by_id={n['@id']:n for n in graph};inverse={'provisionToNorm':'fromProvision','appliedInApplication':'appliesNorm','toApplication':'toFact'}
    for edge in edges:
        relation=edge['predicate'];by_id[edge['source']].setdefault('lkg:'+relation,[]).append({'@id':edge['target']})
        by_id[edge['target']].setdefault('lkg:'+inverse[relation],[]).append({'@id':edge['source']})
    return {'@context':dict(ontology['@context'],project=PROJECT),'@graph':graph}

def validate_graph(nodes,edges,ontology):
    ids={n['id']:n for n in nodes};expected={'provisionToNorm':('Provision','LegalNorm'),'appliedInApplication':('LegalNorm','LegalApplication'),'toApplication':('Fact','LegalApplication')}
    available={entry['@id'].split(':')[-1] for entry in ontology['@graph']}
    for edge in edges:
        if edge['predicate'] not in available:raise ValueError('Predicate absent from author ontology')
        a,b=ids[edge['source']],ids[edge['target']]
        if (a['kind'],b['kind'])!=expected[edge['predicate']]:raise ValueError('Typed edge violates author ontology')
        if edge['predicate']=='provisionToNorm':
            if not any(o['document_id']==b['document_id'] and o['block_index']==b['block_index'] for o in a['source_occurrences']):raise ValueError('Provision/Norm edge outside its local block')
        elif a['document_id']!=b['document_id']:raise ValueError('Cross-document reasoning edge not authorized')
        if edge['predicate']!='provisionToNorm' and a['block_index']>b['block_index']:raise ValueError('Future-section edge')
    return dict(typed_endpoints_valid=True,no_future_section_edges=True,node_count=len(nodes),edge_count=len(edges),literal_nodes=sum(bool(n['anchors']) for n in nodes),unmatched_nodes=sum(not n['anchors'] for n in nodes))

def existing_paths(nodes,edges):
    index={n['id']:n for n in nodes};to_app={};norms={};provisions={}
    for e in edges:
        if e['predicate']=='toApplication':to_app.setdefault(e['source'],[]).append(e['target'])
        elif e['predicate']=='appliedInApplication':norms.setdefault(e['target'],[]).append(e['source'])
        elif e['predicate']=='provisionToNorm':provisions.setdefault(e['target'],[]).append(e['source'])
    return [dict(fact=f,application=a,norm=n,provision=p,text=[index[k]['text'] for k in (f,a,n,p)]) for f,apps in to_app.items() for a in apps for n in norms.get(a,[]) for p in provisions.get(n,[])]

def run(request,call):
    folder,source_lock=source('legal_reasoning_paths');ontology=json.loads((folder/'lightweight_LKG_ontology.jsonld').read_text(encoding='utf-8'))
    prompts={name:(folder/'prompts'/('prompt_'+name+'_ja.txt')).read_text(encoding='utf-8') for name in ('step1','step2','step3_law_norm','step3_norm_application','step3_fact_application')}
    if not request.get('documents'):raise ValueError('No frozen text documents')
    nodes=[];edges=[];events=[];exact=[];skipped=[];counter={k:0 for k in JA_LABELS}
    def ask(stage,prompt):
        raw=call(stage,[dict(role='user',content=prompt)],PARAMETERS)
        parsed=parse_json(raw);events.append(dict(stage=stage,prompt_sha256=hashlib.sha256(prompt.encode('utf-8')).hexdigest(),parsed=parsed));return parsed
    for task in request.get('exact_author_edge_tasks',[]):
        result=ask('author_fixture.'+task['stage'],task['prompt'])
        exact.append(dict(stage=task['stage'],prompt_sha256=hashlib.sha256(task['prompt'].encode('utf-8')).hexdigest(),output=result))
    for di,document in enumerate(request['documents']):
        history_norms=[];history_facts=[]
        for bi,block in enumerate(document['blocks']):
            prefix='doc'+str(di)+'.block'+str(bi);text=block['text']
            if not isinstance(text,str) or not text.strip():raise ValueError('Empty source block')
            extracted=node_lists(ask(prefix+'.extract_nodes',prompts['step1']%(document.get('overview',''),text)))
            block_nodes=[]
            for kind,values in extracted.items():
                if kind=='Provision':continue
                for value in values:
                    counter[kind]+=1
                    n=dict(id=identity(kind,document['id']+'|'+str(bi)+'|'+value),kind=kind,label=PREFIX.get(kind,kind)+str(counter[kind]),text=value,document_id=document['id'],block_index=bi,anchors=spans(text,value),source_status=document.get('source_status','unverified_party_statement'))
                    nodes.append(n);block_nodes.append(n)
            citations=extracted['Provision'];provisions=[]
            if citations:
                normalized=ask(prefix+'.normalize_provisions',prompts['step2']%(repr(citations),text))
                if not isinstance(normalized,dict) or set(normalized)!={'norm'} or not isinstance(normalized['norm'],list):raise ValueError('Original normalization contract must be norm:list')
                for value in dict.fromkeys(normalized['norm']):
                    if not isinstance(value,str) or not value.strip():raise ValueError('Empty normalized provision')
                    counter['Provision']+=1
                    n=dict(id=identity('Provision',document['id']+'|'+str(bi)+'|'+value),kind='Provision',label='法律'+str(counter['Provision']),text=value,document_id=document['id'],block_index=bi,anchors=spans(text,value),source_status=document.get('source_status','unverified_party_statement'),raw_citation_candidates=[dict(text=c,anchors=spans(text,c)) for c in citations],canonical_alignment='only exact full-title spans are verified; no guessed raw-to-canonical mapping')
                    occurrence=dict(document_id=document['id'],block_index=bi,anchors=n['anchors'],raw_citation_candidates=n['raw_citation_candidates'])
                    existing=next((p for p in nodes if p['kind']=='Provision' and p['text']==value),None)
                    if existing:
                        existing['source_occurrences'].append(occurrence)
                        existing['anchors'].extend(a for a in n['anchors'] if a not in existing['anchors'])
                        n=existing
                    else:
                        n['id']=identity('Provision',value);n['source_occurrences']=[occurrence];nodes.append(n)
                    provisions.append(n)
            else:skipped.append(dict(stage=prefix+'.normalize_provisions',reason='no extracted provision'))
            norms=[n for n in block_nodes if n['kind']=='LegalNorm'];facts=[n for n in block_nodes if n['kind']=='Fact'];applications=[n for n in block_nodes if n['kind']=='LegalApplication']
            if provisions and norms:
                value=ask(prefix+'.link_provision_norm',prompts['step3_law_norm']%(repr([n['text'] for n in provisions]),repr([n['text'] for n in norms]),text))
                edges.extend(edges_from(value,provisions,norms,'provisionToNorm'))
            else:skipped.append(dict(stage=prefix+'.link_provision_norm',reason='empty provision or norm candidates'))
            history_norms.extend(norms);history_facts.extend(facts)
            for application in applications:
                prior_norms=eligible(history_norms,application);prior_facts=eligible(history_facts,application)
                tool('legal_reasoning_paths.history_scope',dict(document_id=document['id'],application=application['id'],block_index=bi,norm_candidates=[n['id'] for n in prior_norms],fact_candidates=[n['id'] for n in prior_facts],same_section_order_policy='literal start <= application start; unmatched same-section order excluded'))
                stage=prefix+'.app'+application['label'].removeprefix('適用')
                if prior_norms:
                    value=ask(stage+'.link_norm_application',prompts['step3_norm_application']%(numbered(prior_norms),'('+application['label']+')'+application['text']))
                    edges.extend(edges_from(value,prior_norms,[application],'appliedInApplication','right'))
                else:skipped.append(dict(stage=stage+'.link_norm_application',reason='no preceding legal norm candidate'))
                if prior_facts:
                    value=ask(stage+'.link_fact_application',prompts['step3_fact_application']%(numbered(prior_facts),'('+application['label']+')'+application['text']))
                    edges.extend(edges_from(value,prior_facts,[application],'toApplication','right'))
                else:skipped.append(dict(stage=stage+'.link_fact_application',reason='no preceding fact candidate'))
            tool('legal_reasoning_paths.block_graph',dict(document_id=document['id'],block_id=block['id'],extracted=extracted,node_count=len(nodes),edge_count=len(edges),raw_citations=citations))
    edges=[dict(t) for t in {tuple(sorted(e.items())) for e in edges}]
    edges.sort(key=lambda e:(e['source'],e['predicate'],e['target']))
    checks=validate_graph(nodes,edges,ontology);paths=existing_paths(nodes,edges);graph=materialize(nodes,edges,request['documents'],ontology)
    result=dict(source_kind=SOURCE_KIND,source_commit=source_lock['commit'],author_python_executed=False,author_prompts_exact=True,ontology=graph,nodes=nodes,edges=edges,existing_graph_paths=paths,path_enumeration_not_semantic_retrieval=True,exact_author_fixture=exact,stages=events,skipped_stages=skipped,checks=checks,embedding_retrieval_executed=False,original_complete_benchmark=False,local_model_inference=False,neural_modules_loaded=[k for k in ('torch','transformers','sentence_transformers','onnxruntime','spacy') if k in sys.modules])
    if request.get('projection'):
        p=request['projection']
        system=p['instruction']+'\nUse graph nodes as analysis; anchors are only for literal citation alignment. Do not promote party statements to judicial findings. If the graph has no Fact nodes with literal spans, output no factual findings; retain unknowns. Return only the product JSON. This is an extra project projection, not the original paper output.'
        raw=call('product_projection',[dict(role='system',content=system),dict(role='user',content=json.dumps(dict(question=request['question'],graph=graph,extracted_nodes=nodes,reasoning_paths=paths,citation_anchors=p.get('anchors',[]),limitations=dict(embedding_retrieval_executed=False,source_status='unverified_party_statements')),ensure_ascii=False))],dict(model='project DeepSeek',temperature=0,max_tokens=4096))
        result['output']=parse_json(raw)
    else:result['output']=graph
    if result['neural_modules_loaded']:raise ValueError('Unexpected local neural model module')
    return result
