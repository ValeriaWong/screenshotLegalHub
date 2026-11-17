"""L07 JurisMA — Lu/Zhang/Wu/Feng, arXiv:2604.10470v1, §§3.2–3.4/Algorithm 1.
Paper: https://arxiv.org/html/2604.10470v1 (fixed local HTML and SHA-256).
Degree: inference-algorithm reimplementation ONLY; author repository unverified.
Original: Element Agent builds JSON G=(V,E) from a legal consultation q; Draft
Agent consumes [P_G;q]; Manager selects FormatCheck and/or LawSearch, in that
order, for at most T=5 iterations; Pass/empty stops; ContentCheck always runs.
Innovation: explicit legal semantic graph + selective multi-agent refinement +
statutory grounding + dual-section response. Full paper also uses JurisCQAD DPO.
Original benchmarks: revised LawBench 500 consultations (340 corrections),
LegalBench RuleQA/KoBLEX transfer; JurisCQAD >43K preference-training queries.
Original input example: Appendix C 2011 drunk-driving/child aviation-school query.
Original output: Response + Legal Basis with full article contents; graph is an
intermediate artifact. No image pixels, boxes, FrozenCaseInput or product JSON.
Adaptation: remote DeepSeek replaces trained backbone; NO DPO/checkpoint claim.
Prompts are ours because exact author templates/controller were not verified.
Law database backend is unspecified by paper: our adapter selects IDs through
API from a supplied frozen catalog and reads its literal texts, no embeddings.
Empty/missing catalog is an explicit gap, never fake statutory retrieval.
Final two sections are JSON-serialized. ContentCheck additionally receives a
frozen retrieved-statute appendix: our literal-grounding adaptation, because
intermediate Draft Agents may shorten statutory quotations. A SEPARATE product projection maps to
CaseAnalysisOutput/global text VQA, carrying frozen source anchors; product graph
output cap is 4096 (native 2048), and final facts-schema constraints apply only
to the product projection, avoiding conflicts with intermediate graph JSON. Pixel KIE is
unsupported. Training/local weights are deferred by user, full paper INCOMPLETE.
Raw inputs, graph, drafts, manager decisions, real retrieval and replies are
saved under methods/e18_jurisma. No benchmark or legal-accuracy claim is made.
"""
import hashlib
import json
from pathlib import Path
HERE=Path(__file__).parent
MAX_ITERATIONS=5
MAX_INFERENCE_CALLS=28

def resources():
    specification=json.loads((HERE/'specification.lock.json').read_text(encoding='utf-8'))
    for name,sha in specification['files'].items():
        if hashlib.sha256((HERE/name).read_bytes()).hexdigest()!=sha:
            raise ValueError('JurisMA specification changed: '+name)
    return specification,json.loads((HERE/'prompts.json').read_text(encoding='utf-8'))['templates']

def parse_json(raw):
    text=raw.strip()
    if text.startswith(chr(96)*3):text='\n'.join(text.splitlines()[1:-1])
    return json.loads(text)

def run(request,generate,observe=lambda action,result:None):
    specification,prompts=resources()
    query=request['question'];catalog=request.get('statutes',[])
    if not isinstance(query,str) or not query.strip():raise ValueError('JurisMA requires a consultation query')
    if not isinstance(catalog,list):raise ValueError('Statute catalog must be a list')
    by_id={}
    for source in catalog:
        if not isinstance(source,dict) or not isinstance(source.get('id'),str) or not isinstance(source.get('text'),str) or not source['text']:
            raise ValueError('Invalid literal statutory source')
        if source['id'] in by_id:raise ValueError('Duplicate statutory source ID')
        by_id[source['id']]=source
    requests=[];iterations=[];retrieved={}
    policy=request.get('policy','')
    def ask(stage,role,payload):
        if len(requests)>=min(request.get('max_calls',MAX_INFERENCE_CALLS),MAX_INFERENCE_CALLS):
            raise ValueError('Explicit inference unit call budget exhausted; no retry or reduced T')
        messages=[dict(role='system',content=prompts[role]+('\n'+policy if policy else '')),
                  dict(role='user',content=json.dumps(payload,ensure_ascii=False))]
        raw=generate(stage,messages,dict(temperature=0,max_tokens=request.get('graph_max_tokens',2048) if stage=='element_graph' else 2048))
        if not isinstance(raw,str) or not raw.strip():raise ValueError('Empty agent response: '+stage)
        requests.append(dict(stage=stage,role=role,raw=raw))
        return raw
    graph=parse_json(ask('element_graph','element',dict(query=query)))
    fields=['entities','events','user_claims','key_facts','legal_questions','relationships']
    if not isinstance(graph,dict) or any(not isinstance(graph.get(k),list) for k in fields):
        raise ValueError('Element Agent graph does not meet §3.2 JSON serialization contract')
    observe('jurisma.element_graph',graph)
    draft=ask('initial_draft','draft',dict(serialized_element_graph=json.dumps(graph,ensure_ascii=False),query=query))
    initial_draft=draft;stop='iteration_limit'
    for t in range(MAX_ITERATIONS):
        decision=parse_json(ask('manager.'+str(t),'manager',dict(draft=draft)))
        actions=decision.get('actions') if isinstance(decision,dict) else None
        if actions=='Pass' or actions==[]:
            iterations.append(dict(iteration=t,actions=actions,draft_before=draft,draft_after=draft))
            observe('jurisma.iteration',iterations[-1]);stop='Pass' if actions=='Pass' else 'empty';break
        if not isinstance(actions,list) or not actions or len(set(actions))!=len(actions) or any(a not in ['FormatCheck','LawSearch'] for a in actions):
            raise ValueError('Manager must select FormatCheck/LawSearch, empty or Pass')
        record=dict(iteration=t,actions=actions,draft_before=draft)
        # Independent if clauses, fixed paper order, not an exclusive-action router.
        if 'FormatCheck' in actions:
            suggestions=ask('format_suggestions.'+str(t),'format',dict(draft=draft))
            draft=ask('apply_suggestions.'+str(t),'apply',dict(draft=draft,suggestions=suggestions))
            record.update(suggestions=suggestions,after_format=draft)
        if 'LawSearch' in actions:
            directory=[{k:s[k] for k in ('id','title','source_url','version_scope') if k in s} for s in catalog]
            selection=parse_json(ask('law_search.'+str(t),'search',dict(query=query,draft=draft,catalog=directory)))
            ids=selection.get('source_ids') if isinstance(selection,dict) else None
            if not isinstance(ids,list) or len(ids)>5 or any(not isinstance(s,str) or s not in by_id for s in ids) or len(set(ids))!=len(ids):
                raise ValueError('LawSearch selected an invalid/missing frozen source ID')
            statutes=[by_id[s] for s in ids]
            retrieved.update({s['id']:s for s in statutes})
            observe('jurisma.statute_read',dict(iteration=t,source_ids=ids,statutes=statutes,query=query,draft_received=draft))
            draft=ask('integrate_statutes.'+str(t),'integrate',dict(draft=draft,statutes=statutes))
            record.update(statute_ids=ids,statutes=statutes,after_statutes=draft)
        record['draft_after']=draft;iterations.append(record);observe('jurisma.iteration',record)
    native=parse_json(ask('content_check','content',dict(query=query,revised_draft=draft,retrieved_statutory_appendix=list(retrieved.values()))))
    if not isinstance(native,dict) or not isinstance(native.get('response'),str) or not isinstance(native.get('legal_basis'),list) or not isinstance(native.get('uncertainties'),list):
        raise ValueError('ContentCheck dual-section JSON contract invalid')
    for basis in native['legal_basis']:
        if not isinstance(basis,dict) or basis.get('source_id') not in retrieved or basis.get('article_text')!=retrieved[basis['source_id']]['text']:
            raise ValueError('ContentCheck statute is not an exact actually retrieved full article')
    return dict(method='jurisma',source_kind=specification['source_kind'],author_code_executed=False,
        original_paper_reproduced=False,original_complete_benchmark=False,original_benchmark_reproduced=False,training_reproduced=False,local_model_inference=False,
        output=native,element_graph=graph,initial_draft=initial_draft,revised_draft=draft,
        iterations=iterations,stop_reason=stop,max_iterations=MAX_ITERATIONS,
        retrieved_statutes=list(retrieved.values()),requests=requests,calls=len(requests),
        statutory_texts_literal_verified=True,legal_accuracy_verified=False)
