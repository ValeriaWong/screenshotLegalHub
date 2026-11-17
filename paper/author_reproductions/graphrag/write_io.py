"""Render complete method-named R04 actual I/O and verify run source snapshots.
No model requests, changes to raw outputs, reruns or rescoring.
"""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
RUNS=HERE.parent/'results/2026-10-29-per-paper/methods/r04_graphrag/runs';NAME='r04_graphrag';FENCE=chr(96)*3

def read(path,default=None):return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def block(value):return FENCE+'json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n'+FENCE

def main():
    rows=[]
    for folder in sorted(RUNS.iterdir()):
        record=read(folder/(NAME+'.record.json'))
        if not record:continue
        inputs=read(folder/(NAME+'.input.json'),{});plan=read(folder/(NAME+'.provenance.json'),{})
        output=read(folder/(NAME+'.output.json'));responses=read(folder/(NAME+'.model_responses.json'),[])
        tests=read(folder/(NAME+'.test_results.json'),{});tools=read(folder/(NAME+'.tools.json'),[]);artifacts=read(folder/(NAME+'.author_artifacts.json'),[])
        checked=0
        for name,sha in plan['source_manifest'].items():
            if hashlib.sha256((folder/'source_snapshot'/name).read_bytes()).hexdigest()!=sha:raise ValueError('Snapshot changed: '+name)
            checked+=1
        row=dict(directory=folder.relative_to(ROOT).as_posix(),track=record['track'],status=record['status'],plan_id=record['plan_id'],new_supplier_requests=record['new_supplier_requests'],source_snapshots_verified=checked,tests=tests,
            prompt_tokens=sum(r.get('response',{}).get('usage',{}).get('prompt_tokens',0) for r in responses),completion_tokens=sum(r.get('response',{}).get('usage',{}).get('completion_tokens',0) for r in responses),
            cost_estimate_CNY=sum(r.get('response',{}).get('cost_estimate',0) for r in responses),all_replies_complete=all(r.get('response',{}).get('finish_reason')=='stop' for r in responses),response_models=sorted({r['response']['response_model'] for r in responses if r.get('response',{}).get('response_model')}))
        execution=(output or {}).get('execution') if record['track']!='case_product' else artifacts[0] if artifacts else None
        if record['track']=='vqa_predicted_text' and output:row.update(prediction=output['prediction'],score=output['score'])
        if record['track']=='case_product' and output:row['structured_entries']=len(output['facts']);row['literal_citations']=sum(len(f['citations']) for f in output['facts'])
        if execution and execution.get('indexing'):
            idx=execution['indexing'];row.update(selected_entities=idx['selected_entities'],selected_reports=idx['selected_reports'],indexing_workflows=[r['workflow'] for r in idx['workflows']])
        rows.append(row)
        lines=['# r04_graphrag · '+record['track']+' · '+record['status'],'',
            '来源等级：直接运行固定官方GraphRAG v0.1.1无嵌入索引/全局查询分支。原查询读完整作者预计算表，不冒称重建该索引；产品索引单独从冻结文本执行。完整原benchmark/专家法律准确率未验证。','',
            '## 执行、预算与来源','',block(record),'',block(row),'',
            '[完整来源/参数/哈希清单]('+NAME+'.provenance.json)，所有执行时源码快照均逐一校验。当前源码后续编辑不会覆盖本次快照。','',
            '## 实际输入（request；未省略）','',block(inputs.get('request')),'',
            '## 仅用于评分/审计的信息（未作为参考答案送入模型）','',block(inputs.get('evaluation_only')),'',
            '## 每次实际请求和模型回复','']
        for index,response in enumerate(responses):
            lines+=['### '+str(index+1)+'. '+response['stage'],'',block(response),'']
        lines+=['## 原工作流逐阶段输出/上下文观察（未省略）','',block(tools),'',
            '## 最终输出（未省略）','',block(output),'',
            '## 原控制器/图/社区报告/带分数map/reduce完整产物','',block(artifacts),'',
            '## 检查结果与边界','',block(tests),'',
            '结构与逐字引文有效不等于事实支持或法律正确。产品额外JSON投影可以读取冻结锚点用于引用定位，存在额外模型调用与信息读取；其分数不是未适配GraphRAG原输出的benchmark成绩。','']
        (folder/(NAME+'.INPUT_OUTPUT.md')).write_text('\n'.join(lines),encoding='utf-8')
    summary=dict(paper_id='R04',method=NAME,source_kind='author_global_api_index_and_query',original_complete_benchmark=False,local_neural_inference=False,runs=rows,new_supplier_requests=sum(r['new_supplier_requests'] for r in rows),
        prompt_tokens=sum(r['prompt_tokens'] for r in rows),completion_tokens=sum(r['completion_tokens'] for r in rows),cost_estimate_CNY=sum(r['cost_estimate_CNY'] for r in rows))
    (HERE/'validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in summary.items() if k!='runs'}))
if __name__=='__main__':main()
