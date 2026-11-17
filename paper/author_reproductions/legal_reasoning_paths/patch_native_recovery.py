from pathlib import Path
p=Path('paper/author_reproductions/legal_reasoning_paths/algorithm.py');s=p.read_text(encoding='utf-8')
s=s.replace("stage=prefix+'.'+application['label']","stage=prefix+'.app'+str(counter['LegalApplication'])")
anchor="    result=[]\n    for key,targets in value.items():"
replacement="""    # Author norm/application prompt leaves the JSON object shape unspecified.
    # This observed variant uses explicit application + basis fields, not a map.
    if key_side=='right' and set(value)=={'法適用','根拠規範'}:
        application=value['法適用']
        if isinstance(application,str):application=application.strip().strip('()')
        value={application:value['根拠規範']}
    result=[]
    for key,targets in value.items():"""
if anchor not in s:raise ValueError('edges parser anchor missing')
s=s.replace(anchor,replacement);p.write_text(s,encoding='utf-8')
p=Path('product_v1/backend/tests/test_legal_reasoning_paths.py');s=p.read_text(encoding='utf-8').replace("'.適用1.'","'.app1.'")
s+="""
def test_observed_original_norm_application_json_variant_is_strictly_resolved():
    m=algorithm()
    result=m.edges_from({'法適用':'(適用2)','根拠規範':['規範1']},[{'id':'norm','label':'規範1','text':'norm'}],[{'id':'application','label':'適用2','text':'application'}],'appliedInApplication','right')
    assert result==[{'source':'norm','target':'application','predicate':'appliedInApplication'}]
    with pytest.raises(ValueError,match='Unknown/ambiguous'):
        m.edges_from({'法適用':'(適用99)','根拠規範':['規範1']},[{'id':'norm','label':'規範1','text':'norm'}],[{'id':'application','label':'適用2','text':'application'}],'appliedInApplication','right')
"""
p.write_text(s,encoding='utf-8')
p=Path('paper/author_reproductions/legal_reasoning_paths/run_validation.py');s=p.read_text(encoding='utf-8')
s=s.replace('async def main(track,do_execute=False):','async def main(track,do_execute=False,reuse_completed=None):')
s=s.replace("    trace=[];tools=[];artifacts=[];output=None;checks={}","""    cache={}
    if reuse_completed:
        if track!='native' or not all(c in '0123456789abcdef' for c in reuse_completed) or len(reuse_completed)!=16:raise ValueError('Only explicit same-paper native plan reuse is accepted')
        previous=run.OUT/'methods'/METHOD/'runs'/(reuse_completed+'__native')
        provenance=json.loads((previous/(METHOD+'.provenance.json')).read_text(encoding='utf-8'))
        if provenance['model']!=model:raise ValueError('Cached model snapshot differs')
        rows=json.loads((previous/(METHOD+'.model_responses.json')).read_text(encoding='utf-8'))
        cache={r['stage']:r for r in rows if r['status']=='completed' and r.get('response',{}).get('finish_reason')=='stop'}
    trace=[];tools=[];artifacts=[];output=None;checks={}""")
needle="""        sid=plan_id+'.L06.'+track+'.'+stage
        item=dict("""
replacement="""        sid=plan_id+'.L06.'+track+'.'+stage
        if not sid.isascii():raise ValueError('HTTP request IDs must be ASCII')
        cached=cache.get(stage)
        if cached:
            if cached['messages']!=messages or cached['effective_parameters']!=effective['parameters']:raise ValueError('Explicit cache input/parameters differ; no resend')
            item=dict(stage=stage,request_id=sid,messages=messages,original_parameters=parameters,effective_parameters=effective['parameters'],status='completed',supplier_request_new=False,reused_from_plan_id=reuse_completed,reused_from_request_id=cached['request_id'],response=cached['response'])
            trace.append(item);run.save(directory/(METHOD+'.model_responses.json'),trace);return cached['response']
        item=dict("""
if needle not in s:raise ValueError('cache hook missing')
s=s.replace(needle,replacement)
s=s.replace("p.add_argument('--execute',action='store_true')","p.add_argument('--execute',action='store_true');p.add_argument('--reuse-completed')")
s=s.replace('main(a.track,a.execute)','main(a.track,a.execute,a.reuse_completed)')
p.write_text(s,encoding='utf-8')
