"""Summarize completed P3, keeping task metrics and software acceptance separate."""
from pathlib import Path
from collections import Counter
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from legalhub import benchmark as b
from legalhub.retrieval import Retriever


def main():
    base = ROOT/'blocks/evaluator/artifacts/iterations/20261004-p3-form'
    result = b.read(base/'holdout-structured-results.json')
    runs = result['runs']
    if len(runs) != 3 or any(r['attempted'] != r['planned'] for r in runs):
        raise ValueError('P3 not complete; do not publish final selection')
    tasks = [json.loads(s) for s in (base/'tasks.jsonl').read_text(encoding='utf-8').splitlines()]
    dev = {t['case_id'] for t in tasks if t['split']=='development'}
    hold = {t['case_id'] for t in tasks if t['split']=='holdout'}
    if dev & hold: raise ValueError('Development/holdout group overlap')
    hashes = {split:{digest for t in tasks if t['split']==split for digest in t['image_hashes']} for split in ('development','holdout')}
    if hashes['development'] & hashes['holdout']: raise ValueError('Image content overlap')
    nonchat = [t for t in tasks if t['split']=='holdout' and t['track']=='screening_bundle'
               and t['answer']['classification'].startswith('not_dialog')]
    b.write(base/'gold_cross_field_review_queue.json', {'tasks':nonchat,
            'reason':'Historical gold classifies these as non-dialog but labels chat_type private_chat; current prompt abstains as unknown for non-dialog. Requires source audit, not automatic relabeling.'})
    audit = []
    case_diagnostics = {}
    for run in runs:
        path = base/'runs/holdout-structured'/run['alias']/'predictions.jsonl'
        predictions = {r['id']:r for r in map(json.loads, path.read_text(encoding='utf-8').splitlines())}
        tp = fp = fn = 0
        for task in tasks:
            if task['split']!='holdout': continue
            row = predictions[task['id']]
            if task['track']=='screening_bundle':
                for field, gold in task['answer'].items():
                    predicted = row.get('answer', {}).get(field) if row['status']=='ok' else None
                    if predicted != gold:
                        audit.append({'alias':run['alias'],'task_id':task['id'],'case_id':task['case_id'],
                                      'field':field,'gold':gold,'predicted':predicted,'status':row['status'],
                                      'images':task['images'],'prediction_source':path.relative_to(ROOT).as_posix(),
                                      'review_status':'unreviewed_disagreement_not_necessarily_model_error'})
            else:
                gold = set(b.normalize(task['answer']))
                answer = row.get('answer') if row['status']=='ok' else []
                predicted = set(b.normalize(answer)) if isinstance(answer,list) else set()
                tp += len(gold & predicted); fp += len(predicted - gold); fn += len(gold - predicted)
                if row['status']!='ok' or gold != predicted:
                    audit.append({'alias':run['alias'],'task_id':task['id'],'case_id':task['case_id'],
                                  'field':'case_choice','gold':task['answer'],'predicted':answer,'status':row['status'],
                                  'images':task['images'],'prediction_source':path.relative_to(ROOT).as_posix(),
                                  'review_status':'unreviewed_disagreement_not_necessarily_model_error'})
        case_diagnostics[run['alias']] = {'tp':tp,'fp':fp,'fn':fn,'micro_precision':tp/(tp+fp) if tp+fp else 0,
                                        'micro_recall':tp/(tp+fn) if tp+fn else 0}
    b.write(base/'case_label_set_diagnostics.json', case_diagnostics)
    b.write(base/'disagreement_review_queue.json', {'rows':audit,'notes':'Historical labels unchanged. Queue is for audit, never silent gold correction.'})
    lines = ['# v1 本轮结果分析与实施', '',
        '**本轮复测和软件闭环已完成。三模型证据形式判断均低于多数类基线，暂不适合自动判定证据形式；Kimi K3 仅作为转录与事件候选抽取的工程默认，结论保持待复核。**', '',
        '本轮完成三个实际模型配置各 230 项：200 张截图的三字段合并请求，另 30 项多图案由选择。后者复用输入、金标及配置完全一致的已记录请求，每项保留来源 SHA256。600 次新的留出截图请求与 90 条沿用案由结果分别计数；重试另计。开发集为各 14 项。',
        f'开发/留出文件前缀组分别为 {len(dev)}/{len(hold)}，组和图片内容摘要的交集均为零；尚未核验前缀等于司法案件，亦不能保证它等于真实独立来源。', '',
        '## 分项结果', '',
        '| 配置 | 有效回答 | 分类准确率 / 宏F1 | 证据形式准确率 / 宏F1 | 群聊私聊准确率 / 宏F1 | 多图案由选择 | p50 / p95 秒 |',
        '|---|---:|---:|---:|---:|---:|---:|']
    for r in runs:
        m = r['metrics']
        fields = [f"{m[k]['accuracy']:.1%} / {m[k]['macro_f1']:.3f}" for k in ('classification','evidence','chat_type')]
        lines.append(f"| {r['alias']} | {r['statuses'].get('ok',0)}/{r['planned']} | " + ' | '.join(fields) + f" | {m['case_choice']['correct']}/{m['case_choice']['planned']} | {r['success_latency_p50']:.2f} / {r['success_latency_p95']:.2f} |")
    lines += ['', '失败、格式错误和未知回答保留在任务指标分母。延迟仅统计 HTTP 200，包含格式不合格响应；含重试总耗时与每次尝试见原始结果。三字段来自同一张图，不相加成独立样本数。各配置推理模式和预算不同，本报告比较实际配置，不证明某种思考模式的因果优势。', '',
        '## 不能被总体准确率掩盖的问题', '',
        '留出集群聊仅 16/200，全部输出 private_chat 就有 92% 准确率；必须同时看宏F1及群聊召回。证据形式全部输出 not_evidence 就有 61.5% 准确率，三配置实际为 50.5%/46.0%/43.0%，均未超过该基线：主要问题是大量历史负例被判为规范截图。需要独立复核规范形式的具体标准和负例，当前不能自动筛选/排除证据。分类多数类 non_legal_dialog 为 104/200。类别按配额取样，不能外推自然分布。',
        f'另有 {len(nonchat)} 张历史金标 classification 为非聊天，但 chat_type 仍为 private_chat；当前输入要求非聊天回答 unknown，存在跨字段协议与金标冲突。上表保留全部原始分数，不能把该部分差异直接认定为模型能力不足。已单列 `gold_cross_field_review_queue.json`，下一版须查看原图后明确该字段适用范围，不能按模型答案自动改金标。', '',
        '| 配置 | 群聊召回 / 16 | 规范证据形式召回 / 77 | 不规范证据形式召回 / 123 | 分类最弱类别（召回） |', '|---|---:|---:|---:|---|']
    for r in runs:
        m=r['metrics']; chat={x['label']:x for x in m['chat_type']['per_class']}; ev={x['label']:x for x in m['evidence']['per_class']}
        weakest=min(m['classification']['per_class'],key=lambda x:x['recall'])
        lines.append(f"| {r['alias']} | {chat['group_chat']['recall']:.1%} | {ev['is_evidence']['recall']:.1%} | {ev['not_evidence']['recall']:.1%} | {weakest['label']}（{weakest['recall']:.1%}） |")
    lines += ['', 'evidence 已改回原题“规范的聊天截图证据形式”；不再以有无法律意义代替形式判断。P2 错误协议的原始记录保留且标注停止，不纳入选型。本轮历史金标未做完整独立专业审核；尤其消息题的头像编号、attitude 语义及隐含身份仍有问题。',
        f'本轮生成 {len(audit)} 条字段/案由不一致的复核队列，路径 `blocks/evaluator/artifacts/iterations/20261004-p3-form/disagreement_review_queue.json`。它不是已确认错误清单；未利用这些留出答案修改本轮提示或金标。',
        '多图案由的 8/30、10/30、9/30 是完整标签集合一致率，Qwen3.8 比 K3 多两题，尚不足以证明稳定优势。额外记录标签集合的命中、额外选择和遗漏数（`case_label_set_diagnostics.json`），方便分开审核少选与过度选择，不用文字相似度代替法律正确性。', '',
        '## 当前软件模型决定', '',
        '**默认 Kimi K3 low，用于跑通可追溯抽取。** 这项决定结合接口稳定性和实际软件抽取检查，不等同于宣布它在所有任务或法律理解上最好。标签筛选分数不能代替消息转录和引用定位能力。两个开发截图中，K3 五处已检查原文均有匹配且对应框覆盖检查点；锚点曾借助首个输出检查，不能用作独立定位能力排名。',
        'Qwen3.8 原像素模式读出了同样五处原文，但仅两处框覆盖检查点；显式归一化模式开发复测仅 1/2 图返回有效 JSON，五处锚点仅一处定位覆盖，未提升且未推广到生产。Qwen3-VL Thinking 的两张完整抽取请求在每次 120 秒、最多三次尝试后均超时，说明当前服务/预算组合不适合作为完整抽取默认值，不证明模型没有该能力。', '',
        '## 已实施的改进与下一轮', '',
        '1. 已修正题目语义、按组隔离、保存配置/图片/任务摘要，增加有限重试和逐次日志。逐模型设置视觉与推理参数；native Thinking 不强行加 enable_thinking，也不发送已被接口拒绝的 response_format。',
        '2. retrieve 已实现为 SQLite FTS5/BM25、中文 bigram、原文优先和显式同义词查询；消息/事件理解单独调用视觉模型。查询、筛选、来源定位与导出不依赖模型。',
        '3. 事件保留支持消息和原图区域；时钟或相对日期不补年份，跨图身份不自动合并。上下文限同图且同抽取版本。已跑通真实上传→API 抽取→增量索引→代码查询→原图引用→导出。',
        '4. 下一轮先独立审核开发集中的完整转录、框及事件支持关系，建立召回/遗漏/无依据推断指标；在新封存测试集验收。扩大已有 418 张历史预测之外的截图内容覆盖，补全跨图身份与页码核对，再实现双方证据对齐和当事方视图。',
        '5. GPT-6.1 Sol 仍缺有效 API 凭据；现有实际请求为 401，不能计入模型排名。17,672 项原八轨全量、开放题专业评分及完整法官/律师工作流尚未完成，因此不宣布 v1.0.0 全部验收。', '',
        '详细指标：[P3 留出报告](./v1.0.0_iteration_p3_holdout_structured.md)。抽取检查：[开发集报告](./v1.0.0_extractor_development_check.md)。软件：[实施与验收](./v1.0.0_software_iteration.md)。']
    (ROOT/'reports/v1.0.0_iteration_analysis.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps({'models':len(runs),'planned_per_model':230,'audit_rows':len(audit),'group_overlap':0}))


if __name__=='__main__':main()
