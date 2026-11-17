"""B01 method-named readable evidence; no requests, hidden Gold or new scores."""
import ast,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
NAME='b01_legalagentbench';RUNS=HERE.parent/'results/2026-10-29-per-paper/methods'/NAME/'runs'
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def block(value):return '\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```\n'
def main():
    rows=[];request_ids=set();unique_responses={}
    for d in sorted(RUNS.iterdir()):
        path=d/(NAME+'.record.json')
        if not path.exists():continue
        record=load(path)
        if record['status']=='running':continue
        original=load(d/(NAME+'.input.json'));responses=load(d/(NAME+'.model_responses.json'))
        output=load(d/(NAME+'.output.json'));checks=load(d/(NAME+'.test_results.json'))
        tools=load(d/(NAME+'.tools.json'))
        lines=['# '+NAME+' '+record['variant']+' 实际输入/回复/输出','',
            '来源等级：作者原控制器实际执行，原工具服务未恢复。原任务仅回放作者日志的精确工具响应；产品使用冻结KIE文本工具。不是完整benchmark，不报告专家法律准确率。',
            '## 状态',block(record),'## 输入与仅评分端参考',block(original),'## 最终输出',block(output),'## 工具响应',block(tools),'## 检查结果',block(checks),'## 全部实际请求和原始模型回复']
        for i,item in enumerate(responses):
            request_ids.add(item['request_id'])
            if item.get('response'):unique_responses[item['request_id']]=item['response']
            lines += [f"### {i+1}. {item['stage']}",block(item)]
        lines+=['## 出处与原文件快照','',
            '['+NAME+'.provenance.json]('+NAME+'.provenance.json)；source_snapshot目录保留当时执行代码。若record显示replayed_responses，仅复用已保存的相同请求，不能重复计为新调用。','']
        readable=d/(NAME+'.INPUT_OUTPUT.md');readable.write_text('\n'.join(lines),encoding='utf-8')
        rows.append(dict(directory=d.name,track=record['track'],variant=record['variant'],status=record['status'],
            trace_entries=len(responses),new_supplier_requests=record.get('new_supplier_requests',len(responses)),replayed_responses=record.get('replayed_responses',0),
            paper_used_after_run=record['per_paper_requests_including_history'],error=record.get('error_message'),
            final_fact_count=len(output['prediction']['facts']) if isinstance(output,dict) and isinstance(output.get('prediction'),dict) and 'facts' in output['prediction'] else None,
            prediction=output.get('prediction') if isinstance(output,dict) else None,score=output.get('score') if isinstance(output,dict) else None,
            readable=readable.relative_to(ROOT).as_posix()))
    catalog=ast.parse((ROOT/'product_v1/backend/src/screenshotlegal/method_reproductions/catalog.py').read_text(encoding='utf-8'))
    methods=next(ast.literal_eval(n.value) for n in catalog.body if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='METHOD_MODULES' for t in n.targets))
    result=dict(paper_id='B01',author_commit='ec14d8ab1fc439bfd99cbefba08d8e27dafca534',source_kind='author_source_controlled_tool_replay',
        local_model_inference=False,original_live_tool_service_available=False,original_complete_benchmark=False,
        three_stage_development_completed=False,product_catalog_registered=methods.get('E23')==NAME,expert_legal_accuracy=None,
        durable_requests_used=max((r['paper_used_after_run'] for r in rows),default=0),distinct_supplier_request_ids=len(request_ids),total_tokens_unique=sum((r.get('usage') or {}).get('total_tokens',0) for r in unique_responses.values()),
        estimated_cost_CNY_unique=round(sum(r.get('cost_estimate') or 0 for r in unique_responses.values()),6),limit=100,runs=rows)
    (HERE/'run_summary.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='runs'},ensure_ascii=False))
if __name__=='__main__':main()
