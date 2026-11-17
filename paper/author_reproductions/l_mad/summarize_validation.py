"""Readable L10 method-named I/O from persisted evidence only; no model calls."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).parent
RUNS=HERE.parent/'results/2026-10-29-per-paper/methods/e09_l_mad/runs'
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def block(value):return '\n```json\n'+json.dumps(value,ensure_ascii=False,indent=2)+'\n```\n'
def main():
    rows=[]
    for directory in sorted(RUNS.iterdir()):
        prefix=directory/'e09_l_mad'
        if not prefix.with_suffix('.record.json').exists():continue
        record=load(prefix.with_suffix('.record.json'))
        if record['status']=='running':continue
        original=load(prefix.with_suffix('.input.json'));output=load(prefix.with_suffix('.output.json'))
        responses=load(prefix.with_suffix('.model_responses.json'))
        results=load(prefix.with_suffix('.test_results.json'))
        lines=['# e09_l_mad 实际输入、输出与逐次模型回复','',
            '复现等级：论文协议调度＋论文所引 MALLM 原组件；没有核实 L-MAD 作者代码。不使用本地模型权重。',
            '原任务仅论文示例，非 COLIEE 年度 benchmark；产品参考是旧开发参考，非专家金标。失败和弃答保留。','',
            '## 运行状态',block(record),'## 输入与仅评分端参考',
            'evaluation_only 不发给模型；逐次实际消息在下方。',block(original),
            '## 最终输出',block(output),'## 检查结果',block(results),
            '## 全部实际调用']
        tokens=0;cost=0.0
        for i,item in enumerate(responses):
            response=item.get('response') or {};tokens+=(response.get('usage') or {}).get('total_tokens',0);cost+=response.get('cost_estimate') or 0
            lines.extend([f"### {i+1}. {item['stage']}",block(item)])
        lines+=['## 其他证据','',
            '[原始请求](e09_l_mad.prompts.json) · [原始回复](e09_l_mad.model_responses.json) · [工具/协议结果](e09_l_mad.tools.json) · [来源快照](e09_l_mad.provenance.json)','']
        (directory/'e09_l_mad.INPUT_OUTPUT.md').write_text('\n'.join(lines),encoding='utf-8')
        rows.append(dict(directory=directory.name,track=record['track'],protocol=record.get('variant'),status=record['status'],requests=len(responses),
            total_tokens=tokens,estimated_cost_CNY=round(cost,6),error=record.get('error_message'),
            paper_used_after_run=record['per_paper_requests_including_history'],
            prediction=output.get('prediction') if isinstance(output,dict) else None,
            score=output.get('score') if isinstance(output,dict) else None,
            correct=output.get('correct') if isinstance(output,dict) else None,
            final_fact_count=len(output['facts']) if isinstance(output,dict) and 'facts' in output else None,
            readable=(directory/'e09_l_mad.INPUT_OUTPUT.md').relative_to(ROOT).as_posix()))
    summary=dict(paper='L10',source_kind='paper_specification_with_cited_upstream_components',author_LMAD_code_executed=False,
        original_complete_benchmark=False,expert_legal_accuracy=None,local_model_inference=False,
        requests_used_including_failures=max((r['paper_used_after_run'] for r in rows),default=0),limit=100,runs=rows)
    (HERE/'run_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,ensure_ascii=False))
if __name__=='__main__':main()
