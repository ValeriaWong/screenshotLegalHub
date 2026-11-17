"""Aggregate immutable per-method records, including failed attempts; no inference."""
import hashlib,json,sqlite3
from pathlib import Path
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'paper/author_reproductions/results/2026-10-29-per-paper'
def load(path):return json.loads(path.read_text(encoding='utf-8'))
def save(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def main():
    plans={p.parent.name:load(p) for p in (OUT/'plans').glob('*/per_paper_plan.json')}
    records=[]
    for path in (OUT/'methods').glob('*/runs/*/*.record.json'):
        row=load(path);folder=path.parent;name=row['method']
        files={p.name:p.relative_to(ROOT).as_posix() for p in folder.iterdir() if p.is_file()}
        hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.iterdir() if p.is_file()}
        checks=load(folder/(name+'.test_results.json')) if (folder/(name+'.test_results.json')).exists() else {}
        records.append(dict(paper_id=row['paper_id'],method=name,variant=row.get('variant'),track=row['track'],status=row['status'],plan_id=row['plan_id'],
          plan_created_at=plans.get(row['plan_id'],{}).get('created_at') or (load(folder/(name+'.provenance.json')).get('created_at','') if (folder/(name+'.provenance.json')).exists() else ''),files=files,sha256=hashes,tests=checks))
    records.sort(key=lambda r:(r['plan_created_at'],r['plan_id']))
    authorization=load(OUT/'authorization.json');used=dict(authorization['historical_counts'])
    ledger=OUT/'.runtime/research/research.sqlite3'
    with sqlite3.connect(ledger.resolve().as_uri()+'?mode=ro',uri=True) as db:
        reservations=[json.loads(r[0]) for r in db.execute("SELECT body FROM records WHERE kind='author.paper_request'")]
    for reservation in reservations:used[reservation['paper_id']]=used.get(reservation['paper_id'],0)+1
    budgets=dict(limit_per_paper=authorization['limit_per_paper'],historical=authorization['historical_counts'],used=used,updated_at=datetime.now(timezone.utc).isoformat(),counting='Durable reservations including failed/unknown/inflight; process exit cannot release a counted request')
    assert all(n<=100 for n in used.values());save(OUT/'paper_budgets.json',budgets)
    groups={}
    for r in records:groups.setdefault((r['method'],r.get('variant')),[]).append(r)
    lines=['# 逐论文真实执行记录','',
      '供应商：现有 AIPING 配置；模型：DeepSeek-V4.1-Flash-1017。每篇论文原任务与产品轨道共享 100 次上限，失败和未知请求也计数。',
      '以下是开发样本执行验证；原论文完整 benchmark 尚未完成，专家法律准确率未评测。结构合法不代表内容正确。',
      'completed仅表示控制流结束，必须另外查看测试、内容正确性和最终文件是否实际执行；不会自动升级为论文完成。所有失败尝试保留。每组列出最近一次尝试和最近完成执行记录；原始输入、实际请求、模型回复、输出、工具结果、测试与出处文件分别保存。','',
      '|论文|方法|轨道|最近状态|最近完成执行的实际输入 / 输出 / 回复 / 测试|','|---|---|---|---|---|']
    latest=[]
    for (name,variant),rows in groups.items():
        for track in sorted({r['track'] for r in rows}):
            rs=[r for r in rows if r['track']==track];last=rs[-1];good=next((r for r in reversed(rs) if r['status']=='completed'),None)
            chosen=good or last;folder=Path(chosen['files'][name+'.record.json']).parent
            def link(suffix,label):
                target=folder/(name+'.'+suffix+'.json')
                return '['+label+']('+target.relative_to(OUT.relative_to(ROOT)).as_posix()+')' if (ROOT/target).exists() else label+'（未生成）'
            links=' / '.join(link(s,l) for s,l in [('input','输入'),('output','输出'),('model_responses','逐次回复'),('test_results','测试')])
            readable=folder/(name+'.INPUT_OUTPUT.md')
            if (ROOT/readable).exists():links+=' / [可读完整I/O]('+readable.relative_to(OUT.relative_to(ROOT)).as_posix()+')'
            if name=='e05_self_refine' and track=='native':
                links+=' / [作者缩写修订输出]('+ (folder/'native_output.json').relative_to(OUT.relative_to(ROOT)).as_posix()+')'
            lines.append('|'+ '|'.join([last['paper_id'],name+(' ['+variant+']' if variant else ''),track,last['status'],links])+'|')
            latest.append(dict(paper_id=last['paper_id'],method=name,variant=variant,track=track,latest=last,latest_success=good))
    lines+=['','## 调用累计（含历史）','','|论文|累计请求|上限|','|---|---:|---:|']
    for paper,count in sorted(budgets['used'].items()):lines.append(f'|{paper}|{count}|100|')
    lines+=['','## 读取边界','',
      '- ReAct、Self-Refine、Reflexion：作者控制器改用 DeepSeek，产品反馈不含专家答案。',
      '- RAPTOR：作者摘要树／UMAP-GMM／检索，嵌入替换为锁定的 CPU 多语模型；产品输入为冻结 KIE 预测。',
      '- LightRAG：作者实体关系提取、图存储和混合检索；原法律文档完整输入，产品输入为冻结 KIE 预测。空图或调用耗尽保留失败。',
      '- SCALE：原ECHR案例双条文运行；case_product使用独立冻结中国法规构建未复核层级，执行原问题/因素/段落/迭代阶段并投影JSON；不支持像素KIE，也不等同原判例指南条件。',
      '- SOLAR：作者 Stage II 规则图及解释器；仅 SARA 税法域，未完成 Stage I 和中国聊天法律适配。原样例检查分别报告精确值与论文 10% 容差。',
      '- AgentsCourt：作者庭辩组件；完整 Legal-KB 检索与最终判决链尚未跑完，不能算全文复现完成。',
      '- 原生样例、产品截图轨道和离线工程测试分别记录。native 原任务成功不会自动变成产品适配成功。','']
    lines+=['','## D02 PaddleOCR-VL：原权重核心识别（完整流水线未完成）','',
      '原0.9B权重在CPU完成官方原始页面识别，输出1616字符，达到1024-token上限；未给出准确率，未执行完整布局流水线或消息KIE。供应商请求0次。',
      '[原任务代码](../../paddleocr_vl/original_task.py) · [原图](../../paddleocr_vl/native_inputs/paddleocr_vl_demo.png) · [实际输入](../../paddleocr_vl/runs/2026-10-30-native-sdpa-keyword-fixed/paddleocr_vl.input.json) · [模型回复](../../paddleocr_vl/runs/2026-10-30-native-sdpa-keyword-fixed/paddleocr_vl.model_responses.json) · [输出](../../paddleocr_vl/runs/2026-10-30-native-sdpa-keyword-fixed/paddleocr_vl.output.json) · [测试](../../paddleocr_vl/runs/2026-10-30-native-sdpa-keyword-fixed/paddleocr_vl.test_results.json) · [出处与兼容修复](../../paddleocr_vl/runs/2026-10-30-native-sdpa-keyword-fixed/paddleocr_vl.provenance.json)','']
    (OUT/'README.md').write_text('\n'.join(lines),encoding='utf-8')
    save(OUT/'validation_index.json',dict(generated_at=datetime.now(timezone.utc).isoformat(),records=records,latest=latest,budgets=budgets,complete_paper_benchmarks=0))
    print(json.dumps(dict(records=len(records),tracks=len(latest),completed=sum(r['latest']['status']=='completed' for r in latest),budgets=budgets['used'])))
if __name__=='__main__':main()
