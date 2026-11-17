"""Audit an authorized real pilot without making any model requests.

Only evaluation.request rows are read from the isolated SQLite ledger. Credentials,
raw provider reasoning, and production case records are never read or exported.
"""
import argparse
from collections import Counter
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'product_v1/backend/src'))
from method_artifacts import read_record

PHASES=['baseline','without-thinking-simple','protocol-simple','protocol-counter']
LABELS={
    'baseline':'供应商默认思考模式',
    'without-thinking-simple':'显式关闭思考，原提示协议',
    'protocol-simple':'关闭思考，修正协议：E03 简单夹具',
    'protocol-counter':'关闭思考，修正协议：Legal-R1 反证夹具',
}

def read(file):
    return json.loads(file.read_text(encoding='utf-8'))

def write(file,value):
    file.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

def analyze(out):
    authorization=read(out/'authorization.json')
    limit=authorization['max_calls']
    ledger_path=out/'.runtime/research/research.sqlite3'
    with closing(sqlite3.connect(ledger_path.resolve().as_uri()+'?mode=ro',uri=True)) as db:
        records=[json.loads(r[0]) for r in db.execute("SELECT body FROM records WHERE kind=? ORDER BY rowid",('evaluation.request',))]
    ledger=[]
    for record in records:
        response=record.get('response') or record.get('error',{}).get('evidence') or {}
        usage=response.get('usage') or {}
        ledger.append(dict(
            request_id=record['id'],status=record['status'],
            created_at=record.get('created_at'),finished_at=record.get('finished_at'),
            error_category=(record.get('error') or {}).get('category'),
            configured_model=record['model_snapshot']['model'],
            response_model=response.get('response_model'),
            provider=response.get('provider'),
            parameters=record['model_snapshot']['parameters'],
            input_tokens=usage.get('prompt_tokens'),output_tokens=usage.get('completion_tokens'),
            reasoning_tokens=(usage.get('completion_tokens_details') or {}).get('reasoning_tokens'),
            finish_reason=response.get('finish_reason'),
            cost_estimate=response.get('cost_estimate'),cost_currency=response.get('cost_currency'),
        ))
    phases=[];traced_ids=[];all_rows=[]
    for phase in PHASES:
        directory=out if phase=='baseline' else out/phase
        if not (directory/'planned_tasks.json').exists():continue
        tasks=read(directory/'planned_tasks.json');rows=[];phase_ids=set()
        for task in tasks:
            row=read_record(directory,task) or dict(task,status='not_started')
            result=row.get('result',{});run=result.get('run',{});usage=run.get('usage',{})
            steps=result.get('steps',[])
            traced_ids.extend(s['id'] for s in steps)
            phase_ids.update(s['id'] for s in steps)
            calls=[r for r in ledger if r['request_id'] in {s['id'] for s in steps}]
            rows.append(dict(
                task_id=task['task_id'],method=row['method_id'],case_group_id=row['case_group_id'],
                status=row['status'],run_id=row.get('run_id'),
                error=(run.get('error') or {}).get('category'),
                model_calls=usage.get('model_calls',0),tool_calls=usage.get('tool_calls',0),
                input_tokens=usage.get('input_tokens',0),output_tokens=usage.get('output_tokens',0),
                cost_estimate_CNY=usage.get('cost'),cost_recorded_calls=usage.get('cost_recorded',0),
                missing_usage_calls=usage.get('missing_usage_calls',0),
                quote_spans_validated=(run.get('engineering_metrics') or {}).get('quote_spans_validated'),
                model_parameters=run.get('model',{}).get('parameters'),
                protocol_digest=run.get('protocol_digest'),input_digest=run.get('input_digest'),
                response_models=run.get('response_models',[]),
                finish_reasons=dict(Counter(c['finish_reason'] for c in calls)),
            ))
        phase_calls=[r for r in ledger if r['request_id'] in phase_ids]
        phases.append(dict(
            phase=phase,label=LABELS[phase],planned=len(tasks),statuses=dict(Counter(r['status'] for r in rows)),
            model_calls=sum(r['model_calls'] for r in rows),
            input_tokens=sum(r['input_tokens'] for r in rows),output_tokens=sum(r['output_tokens'] for r in rows),
            cost_estimate_CNY=round(sum(r['cost_estimate_CNY'] or 0 for r in rows),6),
            finish_reasons=dict(Counter(c['finish_reason'] for c in phase_calls)),rows=rows,
        ))
        all_rows.extend(rows)
    ids=[r['request_id'] for r in ledger]
    matched=set(ids)==set(traced_ids) and len(ids)==len(traced_ids)==len(set(traced_ids))
    if not matched:raise ValueError('The exported traces and durable request ledger do not reconcile')
    if len(ids)>limit:raise ValueError('Authorized request cap exceeded')
    if any(r['status'] in {'calling_model','unknown'} for r in ledger):raise ValueError('Unresolved requests remain')
    if any(r['input_tokens'] is None or r['output_tokens'] is None or r['cost_estimate'] is None for r in ledger):
        raise ValueError('Incomplete measured usage/cost; do not present a complete estimate')
    ledger_cost=sum(r['cost_estimate'] for r in ledger)
    if abs(ledger_cost-sum(r['cost_estimate_CNY'] or 0 for r in all_rows))>1e-8:
        raise ValueError('Run and request costs do not reconcile')
    evidence=dict(
        schema_version='deepseek-pilot-audit.v1',date='2026-10-28',
        authorization_limit=limit,requests=len(ledger),remaining_authorized_calls=limit-len(ledger),
        ledger_reconciled=True,no_unresolved_requests=True,
        planned_tasks=len(all_rows),statuses=dict(Counter(r['status'] for r in all_rows)),
        input_tokens=sum(r['input_tokens'] for r in ledger),output_tokens=sum(r['output_tokens'] for r in ledger),
        cost_estimate_CNY=round(ledger_cost,6),
        cost_basis='Existing local model configuration: input CNY 2 / million tokens; output CNY 8 / million tokens. Not a supplier invoice; cache discounts are not applied.',
        reasoning_tokens_reported=sum(r['reasoning_tokens'] or 0 for r in ledger),
        reasoning_usage_reporting_calls=sum(r['reasoning_tokens'] is not None for r in ledger),
        missing_reasoning_usage_is_not_zero=True,
        observed_model_names=sorted({r['response_model'] for r in ledger if r['response_model']}),
        configured_model_names=sorted({r['configured_model'] for r in ledger}),
        provider_field_values=sorted({r['provider'] for r in ledger if r['provider']}),
        expert_gold_available=False,legal_quality_scores=None,
        method_superiority_conclusion=None,phases=phases,
        reporting_script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    )
    write(out/'request_ledger.json',ledger);write(out/'pilot_summary.json',evidence)
    lines=[
        '# DeepSeek 真实开发试跑报告',
        '',
        f"已使用启用的 DeepSeek-V4.1-Flash-1017 发出 **{len(ledger)} / {limit} 次**真实请求。任务共 {len(all_rows)} 项：{evidence['statuses']}。各阶段保留原始失败记录，不把调整后的任务替换进原始分母。",
        f"累计输入 {evidence['input_tokens']:,} token、输出 {evidence['output_tokens']:,} token；按原有本地单价估算 **¥{ledger_cost:.6f}**。全部请求的用量和估算费用均已对账；没有未决调用。此金额不是供应商账单，未扣除可能的缓存优惠。",
        '',
        '| 阶段 | 任务完成 / 计划 | 实际调用 | 输入 token | 输出 token | 估算费用 CNY |',
        '|---|---:|---:|---:|---:|---:|',
    ]
    for phase in phases:
        lines.append(f"| {phase['label']} | {phase['statuses'].get('completed',0)} / {phase['planned']} | {phase['model_calls']} | {phase['input_tokens']} | {phase['output_tokens']} | {phase['cost_estimate_CNY']:.6f} |")
    lines += [
        '',
        '## 发现与修复',
        '',
        '1. 首轮 8 项任务均失败，终止调用均返回 finish_reason=length：5 次无正文、3 次截断 JSON。首轮 19 次请求的 usage 共报告 45,516 个 reasoning token；只统计用量，不保存或展示隐含推理内容。',
        '2. 新增显式 enable_thinking 参数，并随模型快照、步骤参数和对照摘要冻结。页面可选供应商默认/关闭/开启，也可配置单次输出上限。仅对已核对的 AIPing 接口开放该开关；默认不改变旧配置。[AIPing 接口文档](https://aiping.cn/docs/API/text-models) 声明此参数由部分模型服务支持。本次关闭后 19 次请求均正常结束，但该阶段仍因输出协议失败；返回用量没有 reasoning_tokens 字段，不能据此宣称思考 token 精确为零。',
        '3. 严格校验发现模型误算中文引文位置，VERDICT 还生成无引用事实、给引文追加审核说明。新增由冻结原文机械生成的 citation_units，提供 Unicode 字符起止坐标；公开输入、搜索、续读和长文档分块沿用同一坐标。Schema 明确每项事实至少一条原文引用，缺失材料写入 uncertainties。校验没有放宽，没有自动改写模型引文或填造事实。',
        '4. Legal-R1 检索规划阶段曾返回完整分析对象，无法执行工具。现在把规划动作协议置于系统提示，明确 finish 只停止检索，最终分析由独立 judge 生成；错误动作单独标记 tool_protocol，不执行未知工具、不自动重发。',
        '5. 最后新建两项诊断任务：E03 简单夹具完成全部 3 阶段；Legal-R1 反证夹具完成检索循环和最终 judge，共 4 次请求。两项最终输出通过结构、原文引文和字符范围校验。JurisMA / VERDICT 的旧失败保留，尚未在最终协议下重新做真实端到端验证。',
        '',
        '## 如何解读',
        '',
        '这是适配故障诊断，不是论文方法效果排名。只使用两条合成开发材料，没有专家 CaseGold；各阶段改过配置/提示协议，最终两项的输入案件也不同，不能合并为等条件准确率对照、净增益或显著性结果。',
        '仅能确认实际模型请求、预算停止、用量记录、方法控制流和逐字引文约束。通过字符校验不代表事实命题受到语义支持，更不代表法律结论正确。',
        '方法仍为项目机制改写（project_mechanism）：没有复现 Legal-R1 训练检查点、JurisMA 的完整原系统或 VERDICT 的 HJM 记忆演化。现有领域模板/法源仍为开发草稿。',
        '返回的模型名称均与配置别名一致，但别名不能独立验证权重；provider 字段仅为 "-"，未获得可核实的底层服务商身份。每阶段模型和实现版本均保留在原始产物中。',
        '',
        '## 原始证据与复核',
        '',
        '- [逐请求账本](request_ledger.json)：45 条请求 ID、状态、配置参数、用量、结束原因和估算费用；不含凭据。',
        '- [机器可读总表](pilot_summary.json)：逐阶段、逐方法任务分母和校验结果。',
        '- [首轮报告](REPORT.md)、[关闭思考阶段](without-thinking-simple/REPORT.md)、[最终 E03 复核](protocol-simple/REPORT.md)、[最终 Legal-R1 复核](protocol-counter/REPORT.md)。',
        '- 每阶段 attempts/ 保存原始提示、最终正文、工具轨迹、冻结来源和失败；implementation/ 与 implementation.sha256.json 保存当时实际代码，不能用当前代码覆盖旧阶段来源。',
        '- 只读复核命令：python -B paper/experiments/analyze_real_pilot.py --out paper/experiments/results/2026-10-28-deepseek-pilot；不会请求模型。',
        '- 运行数据库在被 .gitignore 排除的 .runtime/；独立于原有案件。原有模型配置只读，没有改写全局思考模式、密钥或供应商设置。',
        '',
    ]
    (out/'REAL_PILOT_REPORT.md').write_text('\n'.join(lines),encoding='utf-8')
    return {k:evidence[k] for k in ['requests','authorization_limit','ledger_reconciled','statuses','input_tokens','output_tokens','cost_estimate_CNY']}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--out',type=Path,required=True)
    print(json.dumps(analyze(parser.parse_args().out.resolve()),ensure_ascii=False))
