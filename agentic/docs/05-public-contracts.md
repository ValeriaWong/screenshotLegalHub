# 公共契约与 Schema

正式生成产物：[contracts.schema.json](contracts.schema.json)、[HTTP OpenAPI](http-openapi.json)、[导入清单](../examples/harness-manifest.json)。运行 python -m agentic.examples.export_contracts 更新，契约回归检查产物与实现一致。

## 三层 API

| 层 | 入口 | 语义 |
| --- | --- | --- |
| Core | Runtime.create_run(request, principal) | 校验授权/输入/预算，生成 DAG，返回 Run 视图并调度 |
| Core | get_run / wait / stream_events | 读取、等候、按 sequence 游标流式读取本人 Run |
| Core | cancel_run / resume_run | 取消；从人工 Gate 或中断状态恢复 |
| Core | list_skills / list_tools | 发现能力与当前身份可用原子工具 |
| Platform | GenericAdapter.invoke / ResponsesAdapter.handle_call | 平台 envelope 转换，调用 Core，不执行任意函数 |
| Tool | TaskContext.call_tool / ToolRegistry.execute | 仅注册、Skill 声明且身份获权的原子操作 |
| Output | render_report / GET /runs/{id}/report.html | 从已完成并通过 Review 的 evidence_analysis 生成 HTML |

RunRequest 含 workflow、input、idempotency_key、limits。TaskSpec 含 task_id、stage_id、dependencies、input、retry_policy、timeout_seconds、human_review；运行态额外包含 status、output、review_status、reviews、attempts、repairs 和 output_digest。ReviewResult 含 status、score、findings、suggested_actions、reviewer_type。

所有 Pydantic 契约拒绝额外字段；外部运行、Tool/Skill 输入输出做严格校验。时间支持 day/month/unknown，并检查真实日历日期；unknown 必须 time=null。Source ID 必须唯一；CaseInput 最多 64 条、每条最多 4000 字符。材料过大返回 CONTEXT_LIMIT，不静默丢弃来源。Responses function arguments 额外限制 65536 字符。

CaseInput 示例见 [case.json](../examples/case.json)：case_id/title/question/sources/synthetic；每条来源含 source_id/text/speaker/time/time_precision/kind/locator。speaker、日期和 kind 是调用方元数据，不代表现实验证。source_digest 对整条来源的规范 JSON 做 SHA-256。

最终 result.synthesis 是 ReportData：case、plan、ledger、assessment、gaps、stages、conclusion、determination。各阶段 meta 包含 stage、mode、prompt_digest、reasoning、model_receipt。模型 reasoning 含 focus/findings/questions/gap_proposals；每个判断/建议有准确来源引用。Gap.status 使用 completed/candidate/needs_evidence/needs_review，与任务 Review 状态分开。

ErrorInfo 统一为 code/message/retryable，公开 message 从错误码生成，禁止透传 provider 响应、异常文本或凭证。典型错误：INVALID_INPUT、PERMISSION_DENIED、BUDGET_EXHAUSTED、STAGE_TIMEOUT、REVIEW_FAILED、MODEL_TIMEOUT、MODEL_REFUSED、MODEL_INCOMPLETE、INVALID_MODEL_RESPONSE、VERSION_CONFLICT。

Usage 记录 iterations/tool_calls/model_calls/tokens/cost/unsettled_model_calls。tokens/cost 在调用前预留，收到可信 usage 后结算；异常未结算预留仍计入额度。model_calls 为尝试次数，外层平台自己的模型调用由平台计费统计。

## HTTP

所有路由需要 Bearer 身份。Principal 从服务端鉴权产生，客户端不能在正文提交自身权限。默认单身份 120 请求/分钟，正文限制按 Runtime 的 max_context_bytes。生产接入应由宿主提供自己的身份/资源授权和服务令牌管理。

| 方法/路径 | 返回 |
| --- | --- |
| POST /runs | 202，Run 视图 |
| GET /runs/{run_id} | Run 视图 |
| GET /runs/{run_id}/events | SSE；after 或 Last-Event-ID 续读 |
| POST /runs/{run_id}/cancel | 取消后的状态 |
| POST /runs/{run_id}/resume | 人工 approve/reject 与 gate_digest，或中断无决策恢复 |
| GET /runs/{run_id}/report.html | 自包含 HTML；仅所有阶段 PASS 的报告 |
| GET /skills / GET /tools | Schema/元数据 |
| GET /adapters/responses/tools | Responses function 定义 |
| POST /adapters/responses/calls | function_call_output；必需 X-Harness-Scope |
| GET /adapters/dify/openapi.json | Dify 导入定义 |
| POST /adapters/dify/{operation} | 操作结果；必需 Idempotency-Key |

HTTP 鉴权失败 401，权限失败 403，跨 owner Run 隐藏为 404，版本/幂等/Gate 冲突 409，限流 429，正文过大 413，其他结构化失败 422。Run 执行失败在 Run.status/error 中表达；请求被接受不等于任务成功。

幂等键在 owner 范围内绑定请求内容和身份；同键异参冲突。人工批准绑定实际工具、版本、参数、operation_key 与运行指纹；模型不得获得审批身份。详见安全文档。
