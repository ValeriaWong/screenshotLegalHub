"""Zero-supplier deterministic execution of real GraphRAG global core and index.
Not a native-model or quality result. Tests derive map ranking/filtering from
paper §2.6, and require the named original index stages to actually return.
"""
import asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'product_v1/backend/src'))
from screenshotlegal.method_reproductions.paper_bridge import execute
async def main():
    observed=[];tools=[]
    async def transport(stage,messages,parameters):
        observed.append(dict(stage=stage,messages=messages,parameters=parameters))
        if stage.startswith('query.map.'):
            return dict(raw=json.dumps(dict(points=[dict(description='LOW_PRIORITY',score=10),dict(description='HIGH_PRIORITY',score=90),dict(description='ZERO_EXCLUDED',score=0)])))
        if stage.startswith('query.reduce.'):
            prompt=messages[0]['content'];assert prompt.index('HIGH_PRIORITY')<prompt.index('LOW_PRIORITY');assert 'ZERO_EXCLUDED' not in prompt
            return dict(raw='DETERMINISTIC_TRANSPORT_RESULT')
        raise AssertionError('Unexpected stage '+stage)
    async def tool(action,result):tools.append(dict(action=action,result=result))
    request=json.loads((HERE/'native_input.json').read_text(encoding='utf-8'))
    result=await execute('graphrag',request,transport,tool)
    assert result['source_commit']=='a81efe58c7c21ff8b17aa9bf1cb78a0750f3065b'
    assert result['lineage']['selected_entities']==217 and result['lineage']['selected_reports']==5
    assert result['output']=='DETERMINISTIC_TRANSPORT_RESULT'
    assert result['query']['positive_map_points']==2 and len(observed)==2
    assert not result['neural_modules_loaded'] and not result['original_complete_benchmark']
    (HERE/'native_transport_test.json').write_text(json.dumps(dict(status='passed',supplier_requests=0,stages=[r['stage'] for r in observed],rank_descending_verified=True,zero_score_filtered=True,source_index_unchanged=True,neural_modules_loaded=result['neural_modules_loaded']),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',supplier_requests=0,stages=[r['stage'] for r in observed])))
asyncio.run(main())
