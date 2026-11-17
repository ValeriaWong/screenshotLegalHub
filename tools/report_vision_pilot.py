"""Consolidate real requests, failures and per-task metrics without inventing scores."""
from collections import Counter
from pathlib import Path
import hashlib
import json
import statistics
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from legalhub import benchmark as b

RUN=b.ART/'runs'/'20261004-vision-pilot'
MODELS=['sf_qwen38_thinking','sf_qwen3vl_instruct','sf_qwen3vl_thinking_native','kimi3_low','kimi26_nonthinking']


def main():
    cohort=b.read(RUN/'cohort.json');manifest,tasks=b.dataset()
    lookup={x['id']:x for x in tasks}
    lines=['# v1.0.0 模型评测：首轮真实视觉 API 对照','',
           '日期：2026-10-04（Asia/Singapore）。本轮是真实图片请求，不是模拟推理。GPT-6.1 Sol 受凭据认证失败影响，尚无有效模型回答。', '',
           '## 样本与输入协议','',
           f'完整冻结数据 SHA256：`{manifest["dataset_sha256"]}`。本轮共同样本为 **{len(cohort["task_ids"])} 题**，不等于 17,672 条任务全量评测。',
           '分类标签均衡抽样；案件多图题限制为 2–6 张；消息题选三种不同属性，并保持 assisted/grounded 问题成对。样本固定、各有效配置使用同一批任务。', '',
           '| Track | 题数 |','|---|---:|']
    lines += [f'| {track} | {count} |' for track,count in cohort['tracks'].items()]
    lines += ['', '模型只收到图片和问题，未发送参考答案。原始图像以 base64 image_url 提交；硅基流动显式设置 detail=high，Kimi 采用提供商默认视觉预处理。未对原图裁切/压缩。', '',
              '## 模型及模式','',
              '| 配置 | 实际模型 ID | 模式与请求参数 |', '|---|---|---|']
    runs=[]
    for alias in MODELS:
        out=RUN/alias
        if not (out/'run.json').exists():continue
        spec=b.read(out/'run.json');model=spec['model']
        lines.append(f'| {alias} | `{model["model_name"]}` | `{json.dumps(model.get("request_parameters",{}),ensure_ascii=False)}`；{model.get("thinking_mode","")}；上限 {model.get("max_tokens")} |')
        predictions=[json.loads(x) for x in (out/'predictions.jsonl').read_text(encoding='utf-8').splitlines()] if (out/'predictions.jsonl').exists() else []
        latest={x['id']:x for x in predictions}
        usage=Counter()
        for row in predictions:
            for key in ['prompt_tokens','completion_tokens','total_tokens']:
                usage[key]+=row.get('usage',{}).get(key,0)
        b.report(out)
        metrics=b.read(out/'metrics.json')
        statuses=Counter(x['status'] for x in latest.values())
        statuses['missing']=len(spec['task_ids'])-len(latest)
        latencies=[x['latency_seconds'] for x in predictions if 'latency_seconds' in x]
        errors=Counter(str(x.get('http_status') or x.get('error_type')) for x in predictions if x['status']=='error')
        runs.append({'alias':alias,'model':model,'planned':len(spec['task_ids']),
                     'attempted':len(predictions),'statuses':dict(statuses),'metrics':metrics,
                     'usage':dict(usage),'median_latency_seconds':statistics.median(latencies) if latencies else None,
                     'errors':dict(errors),
                     'finished':(out/'status.json').exists(),
                     'reported_models':sorted({x['reported_model'] for x in predictions if x.get('reported_model')})})
    lines += ['', '## 请求完成与稳定性','',
              '| 模型配置 | 计划题 | 已请求 | 有效 JSON | 格式错误 | 接口错误 | 未完成 | 延迟中位数（秒） | 输入 tokens | 输出 tokens |',
              '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
    for row in runs:
        s=row['statuses'];latency=row['median_latency_seconds']
        lines.append(f'| {row["alias"]} | {row["planned"]} | {row["attempted"]} | {s.get("ok",0)} | {s.get("invalid_format",0)+s.get("truncated",0)} | {s.get("error",0)} | {s.get("missing",0)} | {latency:.2f} | {row["usage"].get("prompt_tokens",0)} | {row["usage"].get("completion_tokens",0)} |' if latency is not None else f'| {row["alias"]} | {row["planned"]} | {row["attempted"]} | 0 | 0 | 0 | {s.get("missing",0)} | 无 | 0 | 0 |')
    lines += ['', '用量按 API 返回值累加，未声称为账单实付费用。以上表仅计共同样本正式运行；目录查询、预检和密钥池探测另有原始记录。失败和无效回答不从指标分母删除。', '',
              '## 分项指标','',
              '| 模型配置 | Track | 分母 | 有效 JSON | Exact match | 宏 F1（分类任务） |', '|---|---|---:|---:|---:|---:|']
    for row in runs:
        for metric in row['metrics']:
            f1=f'{metric["macro_f1"]:.4f}' if 'macro_f1' in metric else '—'
            lines.append(f'| {row["alias"]} | {metric["track"]} | {metric["planned"]} | {metric["ok"]} | {metric["exact_match"]:.4f} | {f1} |')
    lines += ['', '开放案由题的 Exact match 只显示与旧参考文本完全一致的情况，**不能代替法律正确性**。自由文本重合率保存在各运行 metrics.json，仅作诊断。各 track 不合并成一个“模型总分”。', '',
              '## 消息题的可评分性限制','',
              '- `message_grounded-bf0f152d866a-02823`：nickname 的金标是内部编号 avator_0，题目未给出头像编号规则。不可把 unknown 或真实昵称与该内部编号的不匹配直接解释为昵称识别失败。',
              '- `message_grounded-bf0f152d866a-03859`：attitude 的金标是 non_legal，但题目只写 attitude 属性，没有解释它是法律属性标签；模型可能按日常情绪理解。',
              '- `message_grounded-bf0f152d866a-03021`：人工框内可见“12点10”；旧参考答案涉及商家/消费者及口头承诺，单张截图没有明确给出该身份关系。这题需核对额外案情上下文，不能以字符串匹配推出法律理解正确率。',
              '这些问题保留在原冻结样本与诊断指标中，未在看到结果后删题或改金标。下一版须明确字段含义、头像 ID 映射和 case-context-required 标签，另冻新的输入协议。', '',
              '## 调用问题与修正','',
              '- 原 OpenAI `.env` 与 YAML 两份密钥均在目录查询返回 401；gpt-6.1-sol 实际截图预检也返回 401。未用其他 GPT 型号替代。',
              '- 硅基流动初选密钥与池中另一份密钥返回 402，错误码 30001：账户余额不足；池内第三个不同密钥成功调用 Qwen3.8，其后正式运行使用这份已验证密钥。',
              '- Qwen3-VL-32B-Thinking 加 enable_thinking 时返回 400 / 20015：该模型不支持此参数。失败配置保留；修正配置去掉 enable_thinking 和 thinking_budget，使用固定 Thinking 型号，单独命名为 sf_qwen3vl_thinking_native。',
              '- Kimi K3 始终思考，使用 reasoning_effort=low 和 max_completion_tokens；K2.6 使用 thinking.type=disabled 和 max_tokens，没有套用 K3 的参数。',
              '- 部分回答在 JSON 前输出解释文字，即使末尾有 JSON，也按既定严格协议记为格式错误；保留原文供判断是接口适配问题还是答案问题。', '',
              '接口错误分布：']
    lines += [f'- `{x["alias"]}`：`{json.dumps(x["errors"],ensure_ascii=False)}`。' for x in runs if x['errors']]
    lines += ['', '## 可得结论与下一步','',
              '已验证现有 Kimi 和硅基流动密钥能执行截图理解；视觉输入和模式参数已接入，原始回答、提供商返回模型名、usage、finish_reason、延迟及失败都已归档。',
              '24 题仅用于首轮对照和适配检查，当前不能宣布全量 SOTA 或据此冻结产品最佳模型。需要扩大冻结样本，并对案件开放问答、消息/事件来源引用人工复核后选型。GPT-6.1 Sol 需有效 OpenAI Key 补跑同一 cohort。', '',
              '## 可复现产物','',
              '- `blocks/evaluator/artifacts/runs/20261004-vision-pilot/cohort.json`：共同题 ID 和抽样口径。',
              '- 同目录每个模型子目录：run.json、predictions.jsonl、metrics.json、report.md、status.json。',
              '- `siliconflow-key-pool.json` 与 `*-smoke`：预检及失败修复记录，均不包含密钥。',
              '- `reports/v1.0.0_provider_probe.json`：实际供应商模型目录及认证状态。',
              '- `configs/models.local.yaml`：仅引用原有凭据位置，不复制密钥；列精确模型 ID 和模式参数。', '',
              '## 参数核验来源','',
              '- [OpenAI GPT-6.1 Sol](https://developers.openai.com/api/docs/models/gpt-6.1-sol)。',
              '- [硅基流动模型中心](https://www.siliconflow.cn/models)、[视觉输入](https://docs.siliconflow.cn/docs/userguide/capabilities/vision)、[Chat API](https://docs.siliconflow.cn/docs/api/chat-completions-post)。',
              '- [Kimi 当前模型](https://platform.kimi.com/docs/models)、[K3](https://platform.kimi.com/docs/guide/kimi-k3-quickstart)、[K2.6](https://platform.kimi.com/docs/guide/kimi-k2-6-quickstart)。']
    b.write(ROOT/'reports/v1.0.0_vision_pilot.json',{'cohort':cohort,'runs':runs})
    (ROOT/'reports/v1.0.0_model_evaluation.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    print(json.dumps([{'model':x['alias'],'attempted':x['attempted'],'status':x['statuses']} for x in runs],ensure_ascii=True))


if __name__=='__main__':main()
