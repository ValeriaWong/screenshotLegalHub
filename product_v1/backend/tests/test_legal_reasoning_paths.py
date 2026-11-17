"""L06 graph-pipeline fidelity/transport tests; never calls a supplier."""
import importlib.util,json,sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[3]
def algorithm():
    name='lkg_algorithm_test'
    spec=importlib.util.spec_from_file_location(name,ROOT/'paper/author_reproductions/legal_reasoning_paths/algorithm.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module
def labels(facts=(),norms=(),applications=(),provisions=()):
    return {'司法事実':list(facts),'法律・省令・政令・規則・契約書の引用や参照':list(provisions),'法規範':list(norms),'法解釈':[],'法適用':list(applications),'裁判の結論':[]}
def test_history_scope_canonical_identity_all_edge_families_and_exact_prompts():
    m=algorithm();requests=[];observations=[];m.tool=lambda a,r:observations.append((a,r))
    fixtures=[
        labels(['先の事実。'],['規範A。'],provisions=['Mars Act 2']),{'norm':['Mars Act 2']},{'Mars Act 2':'規範A。'},
        labels(['現在の事実。'],applications=['適用B。']),{'適用1':'規範1'},{'適用1':['事実1','事実2']},
        labels(['将来の事実。'],['将来規範。'],provisions=['Mars Act 2']),{'norm':['Mars Act 2']},{'Mars Act 2':'将来規範。'}]
    def call(stage,messages,parameters):
        requests.append(dict(stage=stage,messages=messages));return json.dumps(fixtures[len(requests)-1],ensure_ascii=False)
    request={'documents':[{'id':'native-judge','source_status':'published_judgment','overview':'overview','blocks':[{'id':'b0','text':'先の事実。Mars Act 2。規範A。'},{'id':'b1','text':'現在の事実。適用B。'},{'id':'b2','text':'将来の事実。Mars Act 2。将来規範。'}]}]}
    result=m.run(request,call)
    assert len(requests)==9
    assert len([n for n in result['nodes'] if n['kind']=='Provision'])==1
    provision=next(n for n in result['nodes'] if n['kind']=='Provision')
    assert len(provision['source_occurrences'])==2
    assert {e['predicate'] for e in result['edges']}=={'provisionToNorm','appliedInApplication','toApplication'}
    assert len(result['existing_graph_paths'])==2
    assert result['embedding_retrieval_executed'] is False
    assert result['author_python_executed'] is False and not result['neural_modules_loaded']
    for item in requests:
        if '.app1.' in item['stage']:assert '将来' not in item['messages'][0]['content']
    raw=(ROOT/'paper/upstream_sources/legal_reasoning_paths/prompts/prompt_step1_ja.txt').read_text(encoding='utf-8')
    assert requests[0]['messages'][0]['content']==raw%('overview',request['documents'][0]['blocks'][0]['text'])
    assert result['ontology']['@context']['lkg'].endswith('lightweight_LKG_ontology.jsonld#')
    assert result['checks']['typed_endpoints_valid']
def test_unknown_edges_missing_labels_and_unlocated_offsets_are_not_invented():
    m=algorithm()
    with pytest.raises(ValueError,match='omitted labels'):m.node_lists({'司法事実':['x']})
    with pytest.raises(ValueError,match='Unknown/ambiguous'):m.edges_from({'fake':'real'},[{'id':'id1','label':'known','text':'known'}],[{'id':'id2','label':'real','text':'real'}],'provisionToNorm')
    assert m.spans('evidence','paraphrased')==[]
    assert m.eligible([dict(block_index=0,anchors=[])],dict(block_index=0,anchors=[{'start':1}]))==[]
    assert m.eligible([dict(block_index=0,anchors=[])],dict(block_index=1,anchors=[]))
def test_nonlegal_input_keeps_empty_graph_relations_without_fake_law_calls():
    m=algorithm();m.tool=lambda *_:None;calls=[]
    def call(stage,messages,parameters):
        calls.append(stage);return json.dumps(labels(['甲说没有借款。']),ensure_ascii=False)
    result=m.run({'documents':[{'id':'chat','blocks':[{'id':'b0','text':'甲说没有借款。'}]}]},call)
    assert calls==['doc0.block0.extract_nodes']
    assert result['edges']==[] and result['existing_graph_paths']==[]
    assert result['nodes'][0]['source_status']=='unverified_party_statement'
    assert result['ontology']['@graph'][0]['@type']=='lkg:LegalDocument'
    assert result['checks']['literal_nodes']==1

def test_isolated_product_transport_runs_real_pipeline_and_returns_top_level_artifacts():
    import asyncio
    from screenshotlegal.method_reproductions.paper_bridge import execute
    trace=[];tools=[]
    async def call(stage,messages,parameters):
        trace.append(stage)
        return {'raw':json.dumps(labels(['原文。']),ensure_ascii=False)}
    async def tool(action,result):tools.append((action,result))
    result=asyncio.run(execute('legal_reasoning_paths',{'documents':[{'id':'frozen','blocks':[{'id':'b0','text':'原文。'}]}]},call,tool))
    assert result['output']['@graph']
    assert result['source_kind']=='paper_pipeline_reimplementation_with_author_prompts_ontology'
    assert result['author_python_executed'] is False
    assert trace==['doc0.block0.extract_nodes'] and tools

def test_observed_original_norm_application_json_variant_is_strictly_resolved():
    m=algorithm()
    result=m.edges_from({'法適用':'(適用2)','根拠規範':['規範1']},[{'id':'norm','label':'規範1','text':'norm'}],[{'id':'application','label':'適用2','text':'application'}],'appliedInApplication','right')
    assert result==[{'source':'norm','target':'application','predicate':'appliedInApplication'}]
    with pytest.raises(ValueError,match='Unknown/ambiguous'):
        m.edges_from({'法適用':'(適用99)','根拠規範':['規範1']},[{'id':'norm','label':'規範1','text':'norm'}],[{'id':'application','label':'適用2','text':'application'}],'appliedInApplication','right')

def test_multiple_applications_have_distinct_ascii_request_stages():
    m=algorithm();m.tool=lambda *_:None;stages=[]
    def call(stage,messages,parameters):
        stages.append(stage)
        if stage.endswith('.extract_nodes'):return json.dumps(labels(['事実。'],['規範。'],['適用A。','適用B。']),ensure_ascii=False)
        app='適用1' if '.app1.' in stage else '適用2'
        return json.dumps({app:'規範1' if stage.endswith('.link_norm_application') else ['事実1']},ensure_ascii=False)
    result=m.run({'documents':[{'id':'case','blocks':[{'id':'both','text':'事実。規範。適用A。適用B。'}]}]},call)
    assert len(stages)==len(set(stages))==5 and all(s.isascii() for s in stages)
    assert len(result['edges'])==4
