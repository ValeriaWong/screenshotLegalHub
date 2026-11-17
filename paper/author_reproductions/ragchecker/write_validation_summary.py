"""Regenerate readable RAGChecker artifacts from persisted real runs, zero API calls."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
RUNS=HERE.parent/'results/2026-10-29-per-paper/methods/b15_ragchecker/runs'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    rows=[];new=[]
    for directory in RUNS.iterdir():
        record=load(directory/'b15_ragchecker.record.json');plan=load(directory/'b15_ragchecker.provenance.json');tests=load(directory/'b15_ragchecker.test_results.json');out=load(directory/'b15_ragchecker.output.json');trace=load(directory/'b15_ragchecker.model_responses.json')
        for r in trace:
            if r.get('supplier_request_new',True):new.append(r)
        for name,expected in plan['source_manifest'].items():
            if hashlib.sha256((directory/'source_snapshot'/name).read_bytes()).hexdigest()!=expected:raise ValueError('Snapshot differs: '+name)
        lines=['# b15_ragchecker — '+record['track'],'',
            '作者源码、原输入输出、创新、benchmark、模型与产品差异见 [方法说明](../../../../../../ragchecker/README.md)。',
            'status=completed表示控制流返回；请同时检查标签解析、评分范围与缺参考状态。原论文完整benchmark未复现；没有专家法律准确率。',
            '', '本次新增供应商请求：'+str(record['new_supplier_requests'])+'；结束时B15累计：'+str(record['per_paper_requests_including_history'])+'/100。缓存/重放回复不冒充新模型调用。',
            '', '## 完整实际输入','','@@FENCE@@json',json.dumps(load(directory/'b15_ragchecker.input.json'),ensure_ascii=False,indent=2),'@@FENCE@@',
            '', '## 完整实际输出','','@@FENCE@@json',json.dumps(out,ensure_ascii=False,indent=2),'@@FENCE@@',
            '', '## 实际检查','','@@FENCE@@json',json.dumps(tests,ensure_ascii=False,indent=2),'@@FENCE@@','', '## 每次实际提示、原始模型回复与重放来源']
        for r in trace:
            lines+=['','### '+r['stage'],'',
                '新增请求：'+str(r.get('supplier_request_new',True))+'；复用来源：'+str(r.get('reused_from_original_request_id'))+'；finish_reason：'+str(r.get('response',{}).get('finish_reason')),
                '', '@@FENCE@@json',json.dumps({k:v for k,v in r.items() if k!='response'},ensure_ascii=False,indent=2),'@@FENCE@@',
                '', '@@FENCE@@text',r.get('response',{}).get('raw',''),'@@FENCE@@',
                '', '@@FENCE@@json',json.dumps({k:v for k,v in r.get('response',{}).items() if k!='raw'},ensure_ascii=False,indent=2),'@@FENCE@@']
        lines+=['','[原JSON请求/回复](b15_ragchecker.model_responses.json) · [原工具结果](b15_ragchecker.tools.json) · [来源与模型配置](b15_ragchecker.provenance.json) · [所有源码快照](source_snapshot/)','']
        (directory/'b15_ragchecker.INPUT_OUTPUT.md').write_text('\n'.join(lines).replace('@@FENCE@@',chr(96)*3),encoding='utf-8')
        rows.append(dict(**record,created_at=plan['created_at'],checks=tests['checks'],path=directory.relative_to(ROOT).as_posix(),source_snapshots_verified=True))
    rows.sort(key=lambda r:r['created_at'])
    unique={r['request_id']:r for r in new};assert len(unique)==sum(r['new_supplier_requests'] for r in rows)
    summary=dict(paper_id='B15',method='b15_ragchecker',runs=rows,new_supplier_requests=len(unique),
        response_models=sorted({r.get('response',{}).get('response_model','unknown') for r in unique.values()}),
        cost_estimate_cny=sum(r.get('response',{}).get('cost_estimate') or 0 for r in unique.values()),
        local_model_inference=False,original_complete_benchmark=False,expert_legal_accuracy=None)
    (HERE/'validation_summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(runs=len(rows),new_supplier_requests=len(unique),all_source_snapshots_verified=True,response_models=summary['response_models']),ensure_ascii=False))
if __name__=='__main__':main()
