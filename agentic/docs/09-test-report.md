# 实际测试报告：0.2

验收日期：2026-10-23（Asia/Singapore）。本次是独立包与本地报告交付，真实远程模型联调按用户选择留待配置。

| 验证 | 实际结果 | 证据 |
| --- | --- | --- |
| Python 全套 | **125 passed**，9.23 秒，0 失败 | reports/tests.log、tests.xml |
| 五阶段真实代码 E2E | COMPLETED；5 阶段 PASS；5 次 Tool；0 次模型 | report.html、report.json、reports/report-example.log |
| Responses callback 示例 | function_call_output，5 阶段 COMPLETED | reports/responses-example.log |
| Skill/Tool 扩展示例 | 实际 SHA-256 Tool 输出并通过 Review | reports/extensions-example.log |
| 真实本地 HTTP/SSE | COMPLETED，5 阶段，6 个公开操作定义 | reports/http-smoke.log |
| 模型 HTTP 协议 | 五阶段各发一次实际环回 HTTP 请求；usage 结算与结构校验 | tests/test_model.py 中 actual_loopback_http_responses_transport |
| 独立性 | AST 无旧应用导入；禁止 screenshotlegal/legalhub 导入仍完成 E2E | tests/test_standalone.py |
| wheel 构建/隔离安装 | PASS；包内源码/Prompt/模板/Schema 与来源字节一致；安装后独立 E2E | reports/package-build.log、package-install.log、wheel-verification.log |
| HTML DOM 交互 | PASS：页签、键盘、来源弹窗、检索、缺口过滤、打印/下载 handler、CSP 哈希、无外部资产/脚本错误 | reports/dom-check.log、tests/report-dom.cjs |
| 真实浏览器视觉检查 | **BLOCKED**：工具无可用浏览器 | reports/browser-check.json |

pytest 涵盖 Core、Task/DAG/状态、Skills、Tools、Review/Repair、SQLite 恢复/版本、身份权限、参数校验、泄密防护、副作用审批、预算/限流/幂等、适配器、内建业务闭环。模型测试覆盖 structured JSON/json_object、Prompt 分阶段传递、规划影响后续检查、假引用修复和耗尽、语义标注、拒绝/incomplete/缺失 usage/非法 usage/401/429/超大响应/超时/取消；不把本地协议响应器当作真实模型效果。

端到端使用包内合成材料及真实代码计算，并验证输入变化会改变账本、规划和缺口；没有以固定成功 Mock 替代最终代码闭环。模型模式测试中的协议服务仅用于契约/故障，不产生本次交付 report.html 的内容。本次 HTML 明示模型未调用、合成材料与尚缺证据。

DOM 测试使用现有开发环境的 jsdom；其 dialog/print/download 原生 UI 使用测试替身，仅验证应用 handler。未执行真实浏览器布局、原生弹窗焦点、移动布局或打印视觉验收，不宣称这些项已通过。

## 复现

~~~powershell
python -m pytest agentic/tests -q --junitxml=agentic/reports/tests.xml
python -m agentic.examples.report --output agentic/report.html
python -m agentic.examples.responses_bridge
python -m agentic.examples.extensions
python -m agentic.examples.http_smoke
python -m agentic.examples.export_contracts
# DOM 测试使用任意已安装 jsdom 的开发环境 package.json 作为解析起点
node agentic/tests/report-dom.cjs product_v1/frontend/package.json agentic/report.html
python -m pip wheel --no-index --no-deps --no-build-isolation --wheel-dir agentic/reports/dist ./agentic
# verify_wheel.py 接收安装目标目录、wheel 文件和源码根目录
~~~

未执行新的原业务测试套件：本轮没有修改原业务代码或接口，不将 0.1 历史的 107+43 个原业务通过结果计入当前 125。历史日志已明确隔离到 reports/history-0.1。后续应优先完成真实模型服务能力探测与人工语义评估、可用浏览器视觉验收，再扩展原始证据接入与更丰富业务规则。
