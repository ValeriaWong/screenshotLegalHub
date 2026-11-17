"""Render method-named complete JurisMA development I/O; no inference or rescoring."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
RUNS=HERE.parent/'results/2026-10-29-per-paper/methods/e18_jurisma/runs'
NAME='e18_jurisma'
FENCE=chr(96)*3

def load(path,default=None):return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default

def block(value,kind='json'):
    text=json.dumps(value,ensure_ascii=False,indent=2) if kind=='json' else value
    return FENCE+kind+'\n'+text+'\n'+FENCE

def main():
    rows=[]
    for folder in sorted(RUNS.iterdir()):
        record=load(folder/(NAME+'.record.json'))
        if not record or record.get('source_kind')!='paper_algorithm_inference_reimplementation_training_deferred':continue
        inputs=load(folder/(NAME+'.input.json'),{});plan=load(folder/(NAME+'.provenance.json'),{})
        responses=load(folder/(NAME+'.model_responses.json'),[])
        output=load(folder/(NAME+'.output.json'));tests=load(folder/(NAME+'.test_results.json'),{})
        artifacts=load(folder/(NAME+'.author_artifacts.json'),[]);tools=load(folder/(NAME+'.tools.json'),[])
        verified=0
        for name,sha in plan.get('source_manifest',{}).items():
            path=folder/'source_snapshot'/name
            if hashlib.sha256(path.read_bytes()).hexdigest()!=sha:raise ValueError('Run source snapshot changed: '+str(path))
            verified+=1
        paid=[r for r in responses if r.get('supplier_request_new',True)]
        row=dict(directory=folder.relative_to(ROOT).as_posix(),plan_id=record['plan_id'],track=record['track'],status=record['status'],new_supplier_requests=record.get('new_supplier_requests',len(paid)),reused_exact_responses=sum(r.get('supplier_request_new') is False for r in responses),source_snapshots_verified=verified,tests=tests)
        if record['track']=='vqa_predicted_text' and output:row.update(prediction=output['prediction'],score=output['score'])
        if record['track']=='case_product' and output:row['final_fact_count']=len(output['facts'])
        rows.append(row)
        lines=['# e18_jurisma · '+record['track']+' · '+record['status'],'',
            '复现程度：论文推理算法重实现；不是作者代码、原DPO检查点或完整benchmark。原问题与评价信息分别保存；evaluation_only未作为模型参考答案输入。模型实际身份/参数/用量见每步原响应。','',
            '## 实际执行与来源','',block(record),'',block(dict(plan=plan,source_snapshots_verified=verified)),
            '','## 原始输入（完整）','',block(inputs),
            '','## 每步请求与实际模型回复（含缓存来源，未省略）','']
        for i,response in enumerate(responses):
            lines += ['### '+str(i+1)+'. '+response['stage'],'',block({k:v for k,v in response.items() if k!='response'}),'',block(response.get('response')), '']
        lines+=['## 工具观察','',block(tools),'',
            '案件入口的完整实际目录读取及每轮statutes同时保存在author_artifacts的iterations/retrieved_statutes；空的外层tools数组不能解释为未发生LawSearch。','',
            '## 最终输出（失败时保留null，原回复仍在上文）','',block(output),'',
            '## 独立算法中间产物（要素图/初稿/每轮动作与草稿/实际检索全文）','',block(artifacts),'',
            '## 测试与局限','',block(tests),'',
            '结构/逐字原文校验不等于法律正确性；专家CaseGold、原DPO训练和完整论文benchmark均未验证。失败记录不删除，缓存回复不冒充新供应商请求。','']
        (folder/(NAME+'.INPUT_OUTPUT.md')).write_text('\n'.join(lines),encoding='utf-8')
    summary=dict(method=NAME,paper_id='L07',source_kind='paper_algorithm_inference_reimplementation_training_deferred',whole_paper_completed=False,author_code_executed=False,training_reproduced=False,local_model_inference=False,original_complete_benchmark=False,runs=rows,new_supplier_requests=sum(r['new_supplier_requests'] for r in rows))
    (HERE/'validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(runs=len(rows),new_supplier_requests=summary['new_supplier_requests'],whole_paper_completed=False)))
if __name__=='__main__':main()
