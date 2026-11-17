"""Execute author's complete no-embedding index/global workflow with zero-call fixtures.
This verifies control/data flow, not model ability or original paper scores.
"""
import asyncio,json,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
sys.path.insert(0,str(ROOT/'product_v1/backend/src'))
from screenshotlegal.method_reproductions.paper_bridge import execute
async def main():
    seen=[];observations=[]
    async def transport(stage,messages,parameters):
        seen.append(dict(stage=stage,messages=messages,parameters=parameters))
        if stage.startswith('query.map.'):
            return dict(raw=json.dumps(dict(points=[dict(description='Only competing statements are visible. [Data: Reports (0)]',score=90)])))
        if stage.startswith('query.reduce.'):return dict(raw='Only competing statements are visible. [Data: Reports (0)]')
        if parameters.get('response_format') or ('\"rating\"' in messages[-1]['content'] and '\"findings\"' in messages[-1]['content']):
            return dict(raw=json.dumps(dict(title='甲乙陈述',summary='材料只有借款与赠与的相对陈述。',rating=3.0,rating_explanation='开发传输夹具',findings=[dict(summary='定性有争议',explanation='甲称借款，乙称赠与。[Data: Entities (0,1); Relationships (0)]')]),ensure_ascii=False))
        if 'MANY entities were missed' in messages[-1]['content'] or 'already extracted' in messages[-1]['content']:
            return dict(raw='<|COMPLETE|>')
        return dict(raw='("entity"<|>"甲"<|>"person"<|>"甲称借款")##("entity"<|>"乙"<|>"person"<|>"乙称赠与")##("relationship"<|>"甲"<|>"乙"<|>"双方对款项性质的陈述不同"<|>1)<|COMPLETE|>')
    async def observer(action,result):
        observations.append(dict(action=action,result=result))
        (HERE/'index_transport_observations.json').write_text(json.dumps(observations,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    request=dict(mode='product',documents=[dict(id='s1',text='甲：这是借款。乙：这是赠与。')],question='可见陈述有什么分歧？')
    try:
        result=await execute('graphrag',request,transport,observer)
        workflows={r['workflow'] for r in result['indexing']['workflows']}
        assert set(result['indexing']['required_workflows'])<=workflows
        assert result['indexing']['selected_reports']>0 and result['indexing']['selected_entities']==2
        assert result['query']['positive_map_points']>0
        assert not result['text_embeddings_computed'] and not result['neural_modules_loaded']
        report=dict(status='passed',supplier_requests=0,calls=len(seen),stages=[r['stage'] for r in seen],workflows=sorted(workflows),selected_reports=result['indexing']['selected_reports'],selected_entities=result['indexing']['selected_entities'],no_local_neural_modules=True,original_complete_benchmark=False)
        (HERE/'index_transport_output.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    except Exception as error:
        report=dict(status='failed',supplier_requests=0,calls=len(seen),error_type=type(error).__name__,error_message=str(error));raise
    finally:
        (HERE/'index_transport_test.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        (HERE/'index_transport_requests.json').write_text(json.dumps(seen,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report,ensure_ascii=False))
asyncio.run(main())
