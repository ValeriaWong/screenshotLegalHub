"""Publish measured dataset coverage and majority baselines, never fabricated model results."""
from collections import Counter, defaultdict
from pathlib import Path
import json
from legalhub.benchmark import dataset, categorical_metrics

ROOT=Path(__file__).resolve().parents[1]
m,tasks=dataset()
inventory=json.loads((ROOT/'reports/restart/inventory_summary.json').read_text(encoding='utf-8'))
summary={}
for track in ['classification','evidence','chat_type']:
    ts=[t for t in tasks if t['track']==track]
    counts=Counter(t['answer'] for t in ts)
    majority,n=counts.most_common(1)[0]
    summary[track]={'records':len(ts),'unique_images':len({t['images'][0] for t in ts}),'labels':dict(counts),
                    'majority_prediction':majority,'majority_accuracy':n/len(ts),
                    **categorical_metrics([(t,{'status':'ok','answer':majority}) for t in ts])}
out=ROOT/'reports/restart/majority_baselines.json'
out.write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
lines=['# v1.0.0 评测报告：数据接入与运行准备','',
       '日期：2026-10-04。状态：离线数据核验已完成，SOTA 在线推理尚未执行，尚无最佳模型。以下数值只来自资产盘点与多数类基线。',
       '',f'当前冻结数据 SHA256：`{m["dataset_sha256"]}`。','',
       '## 已接入评测数据','', '| Track | 可运行记录数 |','|---|---:|']
lines += [f'| {k} | {v} |' for k,v in m['tracks'].items()]
lines += ['',f'这些不是互相独立的 {len(tasks):,} 个新问题：多个 track 是相同截图/标注的不同任务或输入协议。不得相加后声称扩大了数据集。',
          '', '## 离线多数类基线','',
          '该基线不读取图片，只对全部样本输出最常见标签。宏指标对当前 track 中出现的金标类别计算，失败和缺失回答在模型运行报告中计入分母。',
          '', '| Track | 常量预测 | Accuracy | Macro P | Macro R | Macro F1 |','|---|---|---:|---:|---:|---:|']
lines += [f'| {k} | {s["majority_prediction"]} | {s["majority_accuracy"]:.4f} | {s["macro_precision"]:.4f} | {s["macro_recall"]:.4f} | {s["macro_f1"]:.4f} |' for k,s in summary.items()]
lines += ['','群聊/私聊的多数类 accuracy 高，说明这项任务单看 accuracy 容易误导。这个结果不能证明多图法律推理整体容易，也不能代替 SOTA 测试。',
          '', '## 覆盖率及历史版本问题','',
          f'- 主评估目录有 {inventory["primary_images"]:,} 张图片；通过 quiz-collector 图片补充 {inventory["supplemental_images"]} 张，当前合计 {inventory["images"]:,} 个不同图片文件名，全部已校验。源标注有 1,176 条记录，其中 6 条为相同图片的重复分类记录。当前版本保留历史记录权重，未来清理另发数据版本。',
          f'- 154 个案件级多图问题中，当前 {m["tracks"]["case_open"]} 个输入图片完整；缺图排除记录为 {len(m["excluded_missing_images"])}。最初的 82 个缺图已经从本库人工答题图片目录补齐，无需从 GitHub 另行下载。',
          '- 消息题共 6,333 条，历史 IoU 通过 1,475 条、未通过 4,858 条。两种消息输入协议均保留全部现有题，单独报告。',
          '- 论文 Classify 分布 457/21/664/34 与现存标注 410/19/711/36 不同，不是同一个标注版本。',
          '- 原 KIE runner 可复用，但论文所述 143 张/696 条消息的人工 KIE 测试快照尚未在本库定位；它与现存 450 条 image_structured_info 不能默认相等。',
          '', '## 新模型比较待执行','',
          '需要模型网关/供应商、准确模型 ID、希望比较的模型范围及费用上限。现存配置含旧模型及文本模型，不能直接当作当前视觉 SOTA 清单。',
          '', '| 模型 | 运行状态 | 得分 | 产品选型 |','|---|---|---|---|','| 尚未配置 | 未执行 | 无 | 未选择 |',
          '', '每个在线运行将产生 `blocks/evaluator/artifacts/runs/<run>/report.md`、metrics.json 和原始响应。开放法律问答需人工/校准评分，文本重合率仅用于诊断；模型选型还要核对引用正确性、消息/事件召回、时序、费用与延迟。',
          '', '## 软件阶段','',
          '模型比较完成后才按结果选择证据软件默认模型。目前已提供数据契约和 skills 拆分，尚未实现律师/法官软件、Excel/PPT 导出，也未做端到端软件验收。v1.0.0 尚未完成。']
destination=ROOT/'reports/v1.0.0_model_evaluation.md'
if destination.exists() and not destination.read_text(encoding='utf-8-sig').startswith('# v1.0.0 评测报告：数据接入与运行准备'):
    destination=ROOT/'reports/restart/evaluation_readiness.md'
destination.write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps(summary,ensure_ascii=False))
