"""Registered candidates are visible before evaluation, with no invented scores."""
from .contracts import digest

def inventory_rows(inventory, rows, cohort, category, comparison, method_id, model_id, include_baseline):
    models=inventory.get('models',[])
    methods=[m for m in inventory.get('methods',[]) if category in m['categories'] or category=='all'
             or include_baseline and comparison=='methods' and m['id']=='E00']
    if category=='kie_enhanced':
        methods=[dict(id='E00',name='KIE → 问答',categories=['kie_enhanced'],available=True,profile='catalog-kie',paper=False,reproduction_level='',original_paper_reproduced=False)]
    if comparison=='models':
        chosen=method_id or (cohort or {}).get('method_id') or ('E00' if category in ['oneshot','kie_enhanced','all'] else methods[0]['id'] if methods else '')
        methods=[m for m in methods if m['id']==chosen]
    else:
        chosen=model_id or (cohort or {}).get('fixed_model_config_id') or (models[0]['config_id'] if models else '')
        models=[m for m in models if m['config_id']==chosen]
        if not models and rows:models=[rows[0]['model']]
        if not models:models=[dict(config_id='',name='待选择底座模型',model='')]
    represented={(r['model'].get('config_id'),r['method']['id']) for r in rows}
    result=[]
    for model in models:
        for method in methods:
            if (model['config_id'],method['id']) in represented:continue
            reason='尚未在当前评测范围运行' if cohort else '尚未评测'
            if not method['available']:reason='方法已登记，尚未实现'
            elif not model['config_id']:reason='请先添加并选择底座模型'
            elif category=='kie_enhanced' and not model.get('supports_vision',True):reason+='；当前按图流程需要模型声明图片能力'
            elif not model.get('enabled',True):reason+='；模型请求未启用'
            elif not model.get('configured',True):reason+='；模型密钥未配置'
            result.append(dict(entry_id='catalog:'+digest([category,model['config_id'],method['id']]),
                catalogue=True,categories=method['categories'],method=method,method_name=method['name'],
                baseline=method['id']=='E00' and category in ['agent','reproductions'],
                rank=None,model=dict(config_id=model['config_id'],name=model['name'],model=model['model'],identity='catalog:'+model['config_id']),
                run_id=None,run_name='',created_at=None,status='not_implemented' if not method['available'] else 'not_evaluated',
                href='/evaluation.html?view='+('agents' if category in ['agent','reproductions'] else 'benchmark'),
                planned=(cohort or {}).get('planned',0),eligible=0,scored=0,score=None,conditional_score=None,
                score_coverage=None,response_coverage=None,failed=0,unknown=0,cancelled=0,unreviewed=0,
                latency_p50_ms=None,latency_p95_ms=None,cost=None,cost_complete=False,currencies=[],failures={},
                unranked_reason=reason,repeated_runs=0,model_calls=None,tool_calls=None,input_tokens=None,
                output_tokens=None,elapsed_ms=None,baseline_delta=None))
    return result
