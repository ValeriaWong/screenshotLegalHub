"""Generate LegalBench readable I/O and source verification from real records, zero calls."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
RUNS=HERE.parent/'results/2026-10-29-per-paper/methods/b04_legalbench/runs'
def load(p):return json.loads(p.read_text(encoding='utf-8'))
def main():
    rows=[];new=[]
    for directory in RUNS.iterdir():
        record=load(directory/'b04_legalbench.record.json');plan=load(directory/'b04_legalbench.provenance.json');tests=load(directory/'b04_legalbench.test_results.json');out=load(directory/'b04_legalbench.output.json');trace=load(directory/'b04_legalbench.model_responses.json')
        for name,expected in plan['source_manifest'].items():
            if hashlib.sha256((directory/'source_snapshot'/name).read_bytes()).hexdigest()!=expected:raise ValueError('Source snapshot differs: '+name)
        lines=['# b04_legalbench — '+record['track'],'',
            '[原方法、输入输出、适配和完整限制](../../../../../../legalbench/README.md)。原控制器并未提供：作者原提示/评分代码执行，远程API由本项目增加。',
            '这是开发原任务/产品样本记录；不声称完整162任务benchmark或专家法律准确率。completed仅指执行返回，低分、截断/恢复和原人工未评分状态分别记录。','',
            '本次新增请求：'+str(record['new_supplier_requests'])+'；结束时整篇累计：'+str(record['per_paper_requests_including_history'])+'/100。','',
            '## 完整实际输入','','@@FENCE@@json',json.dumps(load(directory/'b04_legalbench.input.json'),ensure_ascii=False,indent=2),'@@FENCE@@','',
            '## 完整实际输出','','@@FENCE@@json',json.dumps(out,ensure_ascii=False,indent=2),'@@FENCE@@','',
            '## 实际检查','','@@FENCE@@json',json.dumps(tests,ensure_ascii=False,indent=2),'@@FENCE@@','']
        if isinstance(trace,list):
            lines+=['## 逐步实际提示、原回复和恢复来源']
            for r in trace:
                if r.get('supplier_request_new',True):new.append(r)
                lines+=['','### '+r['stage'],'','新增请求：'+str(r.get('supplier_request_new',True))+'；重放源：'+str(r.get('reused_from_original_request_id'))+'；finish_reason：'+str(r.get('response',{}).get('finish_reason')),'','@@FENCE@@json',json.dumps({k:v for k,v in r.items() if k!='response'},ensure_ascii=False,indent=2),'@@FENCE@@','','@@FENCE@@text',r.get('response',{}).get('raw',''),'@@FENCE@@','','@@FENCE@@json',json.dumps({k:v for k,v in r.get('response',{}).items() if k!='raw'},ensure_ascii=False,indent=2),'@@FENCE@@']
        else:
            lines+=['## 复用的原产品回复（新增模型调用0）','','@@FENCE@@json',json.dumps(trace,ensure_ascii=False,indent=2),'@@FENCE@@']
        lines+=['','[原模型请求/回复JSON](b04_legalbench.model_responses.json) · [原工具结果/评分器](b04_legalbench.tools.json) · [来源和模型配置](b04_legalbench.provenance.json) · [源码快照](source_snapshot/)','']
        (directory/'b04_legalbench.INPUT_OUTPUT.md').write_text('\n'.join(lines).replace('@@FENCE@@',chr(96)*3),encoding='utf-8')
        rows.append(dict(**record,created_at=plan['created_at'],checks=tests['checks'],source_snapshots_verified=True,path=directory.relative_to(ROOT).as_posix()))
    unique={r['request_id']:r for r in new};assert len(unique)==sum(r['new_supplier_requests'] for r in rows)
    rows.sort(key=lambda r:r['created_at'])
    out=dict(paper_id='B04',method='b04_legalbench',runs=rows,new_supplier_requests=len(unique),response_models=sorted({r['response']['response_model'] for r in unique.values()}),cost_estimate_cny=sum(r['response'].get('cost_estimate') or 0 for r in unique.values()),original_complete_benchmark=False,expert_legal_accuracy=None,local_model_inference=False)
    (HERE/'validation_summary.json').write_text(json.dumps(out,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(runs=len(rows),new_supplier_requests=len(unique),all_source_snapshots_verified=True),ensure_ascii=False))
if __name__=='__main__':main()
