# 平台接入：Responses / Dify / Generic

DSH 已按用户指令移出范围。需要区分两个方向：外部 Harness 通过 function tool 调用本包；本包内部通过 Responses HTTP 调用阶段模型。两个方向没有平台私有分支进入 Core。

## 导入支持 Responses 的 Harness

将 [responses-tools.json](../examples/responses-tools.json) 传入外层平台的 tools，使用服务器端 Principal 创建 ResponsesAdapter(runtime, principal, scope_id=会话ID)。完整 function_call 到达后交给 handle_call，返回 {type:function_call_output, call_id, output:JSON字符串}。宿主把结果放回模型后续 input。完整 output_item.done 可调用 handle_event；arguments delta 不触发执行，in_progress/incomplete 项拒绝执行。

公开函数包括 harness_run_evidence_analysis、get_run/cancel_run/events/list_skills/list_tools。人工审批保持在有权限的 Core/HTTP resume_run；不向模型暴露自动批准函数。调用 evidence_analysis 后可按返回 run_id 获取报告 HTML。

该接口遵循 [OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) 的扁平 function 定义、call_id 与 function_call_output；事件处理参照 [Responses Streaming](https://developers.openai.com/api/docs/guides/streaming-responses)。导出使用 strict:false 保留可选输入字段，执行端始终严格校验。

支持 Responses 形式不等于平台能自动安装 Python 函数。宿主必须能注册 function 定义并将回调绑定本包或 HTTP 服务；只允许填模型 base_url 的平台无法凭此导入本地 Tools。本包不是一个仿制 /v1/responses 模型服务。

运行 python -m agentic.examples.responses_bridge 验证真实本地五阶段回调；examples/harness-manifest.json 额外携带包内 Skills、Tools、Prompt 和 workflow 元数据供自定义导入器使用。

## 内部阶段模型

model.py 用当前技术栈 httpx 发送 POST /responses，字段包括 model、instructions、input、max_output_tokens、store:false、text.format。默认 json_schema 严格结构，可显式配置 json_object 并在本地验证；兼容服务需实际支持该格式。[结构化输出协议](https://developers.openai.com/api/docs/guides/structured-outputs?api-mode=responses)。

只读取 completed assistant message 的 output_text，忽略内部 reasoning 项，不存储思维链。拒绝、incomplete、非法结构、缺少 usage、非 message/function_call 等意外输出均规范化失败；不会把失败改成静默成功。模型来源仅从显式配置读取，不发现或复用旧线密钥。本次按用户选择未做真实模型联调。

## Dify

Dify 支持通过 OpenAPI 定义导入自定义工具，而非要求本包实现 Dify App 的聊天 API。依据 [Dify Tools](https://docs.dify.ai/en/cloud/use-dify/workspace/tools) 和 [HTTP Request 节点](https://docs.dify.ai/en/cloud/use-dify/nodes/http-request)。

1. 在宿主环境运行 create_app，提供身份回调和部署地址；本地演示仅绑定环回地址。
2. 导入 examples/dify-openapi.json；将 servers.url 换成该 Dify 实例可达的 HTTPS 地址。Dify 云端不能访问用户机器的 127.0.0.1。
3. 配置 Bearer 服务令牌；为创建运行提供稳定 Idempotency-Key；将 CaseInput 作为 harness_run_evidence_analysis 的参数。
4. 查看返回 status/error；完成后取 /runs/{run_id}/report.html。长任务可直接使用 POST /runs 与 SSE，避免平台单次 Tool 超时。

本次测试涵盖 OpenAPI 结构、实际本地 HTTP/鉴权、相同输入的 Responses/Dify/SDK 结果一致性。未部署到 Dify 云端，也未测试任意第三方平台的导入 UI。
