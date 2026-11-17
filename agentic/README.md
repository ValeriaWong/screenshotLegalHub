# Agentic Harness 0.2

独立、可嵌入的 Python 程序包，Skills、Tools、Planning、五阶段 Prompt、Responses 模型调用与 HTML 输出均在本包。运行时不导入 screenshotlegal 或 legalhub，不读取旧业务库、旧配置或旧模板。

本地生成的 `report.html` 包含分析概览、原文账本与来源弹窗、补证/推理缺口、阶段 Prompt、Review、Trace。报告属于运行产物，不随源码提交；可用下方命令重建。演示数据为合成材料，默认代码模式的模型调用为 0。该包尚未接入 `product_v1`，见[当前总架构](../docs/architecture.md)。

## 安装与运行

使用 Python 3.12+。依赖沿用项目技术栈：Pydantic、httpx、FastAPI、Uvicorn；无需安装原业务程序。

~~~powershell
python -m pip install ./agentic
python -m agentic.examples.report --output agentic/report.html
# 已安装 wheel 后也可在任意目录运行
agentic-report --output report.html
# 输入自己的文本证据包（Schema 见 examples/case.json）
agentic-report --input case.json --output report.html
~~~

同目录同时输出 report.json，保存实际 Run 结果及事件。CLI 使用临时 SQLite 并在退出时清理；需要跨进程恢复时通过 SDK 给 SQLiteStore 指定持久化路径。

## 包内执行链

| 阶段 | Skill | 原子 Tool | 确定性输出 | 模型可补充 |
| --- | --- | --- | --- | --- |
| Planning | evidence_planning | plan_case | 任务目标、白名单重点、验收条件 | 问题分解、额外分析重点 |
| Facts | evidence_facts | extract_records | 原文账本、金额提及、时间精度、来源哈希 | 语义、否定与条件解释 |
| Assessment | evidence_assessment | assess_evidence | 规划范围内的证据检查 | 竞争性解释、未知前提 |
| Gaps | evidence_gaps | map_gaps | 代码/模型/Prompt/证据/人工缺口 | 带引用的候选缺口与行动 |
| Synthesis | evidence_synthesis | compose_report | 复核后报告数据 | 有条件的报告判断摘要 |

每阶段具有独立 Prompt、输入/输出 Schema、依赖和 Review。启用模型后，每阶段调用 stage_reasoning Tool；未配置时执行真实代码能力，不生成模拟模型响应。模型规划只能在白名单内增加重点，不能跳过阶段、Review 或权限。来源引用必须存在且逐字匹配；语义推断保持候选，不能关闭补证和人工复核项。

默认最多 24 次任务迭代、每任务 2 次 Review 修复、32 次 Tool 调用；代码模式禁止模型调用。配置模型时示例服务上限为 10 次模型调用、2,000,000 保守预算 Token、USD 5、900 秒，可由部署方调整。最终服务账单仍以供应商为准；中断/异常无 usage 时保留预留额，并计入 unsettled_model_calls。

## 模型接入（本次按用户选择未做远程联调）

显式配置 HARNESS_RESPONSES_URL（完整 /responses 地址）、HARNESS_MODEL、HARNESS_MODEL_API_KEY、HARNESS_INPUT_PRICE_PER_MILLION、HARNESS_OUTPUT_PRICE_PER_MILLION，并设置 HARNESS_ALLOW_MODEL_EGRESS=1，再运行：

~~~powershell
python -m agentic.examples.report --model --input case.json --output report.html
~~~

密钥只从进程配置读取，不写入 Prompt、Run、日志或报告。费率由调用方提供，不内置价格或模型名；价格为每百万 Token 的 USD。仅支持 HTTPS，环回测试服务例外。默认 HARNESS_MODEL_FORMAT=json_schema；仅支持 JSON mode 的平台可显式设置为 json_object，仍经本地 Schema/引用校验。不会自动降级到代码模式掩盖模型失败。

[模型配置模板](examples/model.env.example)只描述变量，不自动加载 .env，更不会读取旧线密钥。

## SDK 与平台接入

~~~python
from agentic.builtin.workflow import components, runtime_limits
from agentic.core import Runtime
from agentic.state import SQLiteStore
from agentic.contracts import Principal
from agentic.report import render_report

# 在自己的 async 主程序中执行：
runtime = Runtime(*components(), SQLiteStore("harness.sqlite3"))
principal = Principal(subject="operator", permissions=frozenset({
    "run:create", "run:read", "run:cancel", "run:resume", "run:review", "evidence:analyze"
}))
created = runtime.create_run({"workflow": "evidence_analysis", "input": case_input,
                              "idempotency_key": "case-001-v1"}, principal)
result = await runtime.wait(created["run_id"], principal)
html = render_report(result)
await runtime.close()
~~~

- Responses 外层平台：导入 [function tools](examples/responses-tools.json)，由宿主将 function_call 交给 ResponsesAdapter，再把 function_call_output 回送模型。[可运行示例](examples/responses_bridge.py)。不是向任意平台填一个 base_url 就自动安装本地函数。
- Dify：导入 [OpenAPI](examples/dify-openapi.json)，配置 Bearer 服务令牌与 Idempotency-Key；调用 harness_run_evidence_analysis，随后可获取 /runs/{run_id}/report.html。
- HTTP：设置 HARNESS_SERVICE_TOKEN（随机且至少 24 字符），运行 python -m agentic.examples.serve；默认仅监听 127.0.0.1:18440。鉴权回调可由宿主替换。
- Skills/Tools 扩展：[examples/extensions.py](examples/extensions.py)，可直接运行 python -m agentic.examples.extensions。
- [完整导入清单](examples/harness-manifest.json)包含 Skills、Tools、Prompt 与 workflow 元数据；函数执行必须由宿主绑定本包。

## 验收与边界

~~~powershell
python -m pytest agentic/tests -q
python -m agentic.examples.responses_bridge
python -m agentic.examples.http_smoke
python -m agentic.examples.export_contracts
~~~

[测试报告](docs/09-test-report.md)记录实际结果及限制；[阶段 Gate](docs/08-stage-reviews.md)记录各阶段输出、修改、复用、风险和下一阶段条件。HTML 的 DOM 交互已测试；当前浏览器工具无可用浏览器，未完成实际截图检查。

本包当前接收调用方已转写的文本，不包含 OCR、PDF 解析、原件验证、在线法律检索或完整实体消歧。代码金额规则仅识别明确阿拉伯数字及元/千元/万元，排除不支持的负数和畸形格式。聊天声明不等于真实履行；软件 Review PASS 不代表材料真实、推断正确或 V3 专业认证通过。SQLite 为单进程 worker，持久化和导出包含原文，应由宿主控制文件访问。

## 文档

[能力现状](docs/01-current-capabilities.md) · [复用映射](docs/02-reuse-mapping.md) · [缺口](docs/03-gap-analysis.md) · [架构](docs/04-architecture.md) · [契约](docs/05-public-contracts.md) · [平台](docs/06-platform-integration.md) · [安全与可靠性](docs/07-security-reliability.md) · [独立化决策](docs/10-standalone-reasoning.md)
