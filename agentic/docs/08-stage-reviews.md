# 阶段任务与 Review Gate（0.2）

日期：2026-10-23（用户时区 Asia/Singapore）。本轮按用户最新约束独立化，不导入旧线；真实模型联调由用户选择留待配置。本表是建设阶段 Review，报告里的 planning/facts/assessment/gaps/synthesis 是运行阶段 Review，两者分开记录。

| 建设阶段 / 目标 | 完成事项 | 实际修改文件 | 复用模块 | 新增及原因 | 实际验证结果 | 风险 / Gate | 下一阶段前置条件 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 分析 / 确定独立性与缺口 | 扫描原项目、旧输出交互、0.1 依赖和 docs center；确定模型/Prompt/代码/外部材料边界 | docs/01、02、03、10 | 既有能力分析证据 | 独立化决策文档，说明需求变更取舍 | 扫描发现并定位 screenshotlegal 导入；无实现前大规模业务重构 | PASS；研究认证缺口仍保留 | 依赖和模块边界明确 |
| 2 Core / 独立安装基础 | 去除通用模块的应用导入，保留 backoff 与原公共契约；更新依赖 | primitives.py、contracts.py、context.py、tools.py、pyproject.toml、__init__.py | core/planning/review/state/registry | 最小 JSON、重试与投影基础，消除应用依赖 | 原有 79 项 Core/权限/适配/恢复测试通过 | PASS；SQLite 单 worker | 原公共行为回归通过 |
| 3 Tools → Skills → Planning | 五个真实原子能力与五阶段 Skill；显式安全 DAG、分析重点传递、阶段 Prompt | builtin/*、prompts/*、model.py、examples/case.json | Registry、TaskContext、预算和 Tool 审计 | 阶段能力及 Responses 调用；此前不存在 | 输入变化、时间精度、金额格式、模型重点驱动后续检查通过 | PASS；代码模式仅有限文本线索 | 有完整可执行链与模型边界 |
| 4 Review → State / 可恢复推理 | 逐字引用、账本不变、必要阶段和补证保护；反馈驱动有限修复；未结算费用标记 | builtin/workflow.py、contracts.py、context.py、tests/test_model.py、test_integration.py | Review/Repair、审批、CAS、Checkpoint 缓存 | model receipt 与未结算计数，防止未知费用当 0 | 非法引用修复成功；持续非法引用有限失败；原恢复/取消/版本冲突测试通过 | PASS；实质推断正确性需复核 | 错误和恢复可观测 |
| 5 Platform Adapters / 可导入 | Responses/Dify/Generic 使用独立 workflow；鉴权 HTML 路由；导出 manifest/Schema | adapters/*、examples/serve.py、responses_bridge.py、http_smoke.py、export_contracts.py；删除 product.py/retrieval.py | 0.1 平台桥接 | HTML 路由与完整导入清单，供宿主绑定 | SDK/Responses/Dify 本地结果一致；真实 HTTP/SSE、内部 Responses HTTP 合约通过 | PASS（本地协议）；未做远程平台部署 | 身份与协议边界经测试 |
| 6 安全 / 报告可靠性 | 不可信文本隔离、费用预算、错误脱敏、HTML 转义、CSP、无外部资产、来源查看与筛选 | model.py、report.py、templates/*、tests/report-dom.cjs、docs/07 | 权限、审计、幂等及副作用 Gate | 自包含报告渲染，旧线仅作交互参考 | 注入、畸形输入、模型拒绝/超时/限流/取消/费用、DOM 交互检查通过 | PASS（代码与 DOM）；实际视觉检查 BLOCKED | 完整测试与安装验证通过 |
| 7 E2E / 交付 | CLI 生成 report.html/report.json；wheel 隔离安装；禁止导入旧应用仍运行 | report.html、report.json、reports/*、docs/09、README.md | 五阶段实现和统一 Runtime | 当前版本交付证据与历史隔离 | 125 pytest 全过；5 阶段/5 Tool/0 Model；安装后 E2E 和包内资源一致性通过 | PASS（本地可运行交付）；限制见下 | 已满足本次本地包与报告范围 |

## REWORK 与复审记录

- 首次新增模型测试收集失败：测试 lambda 多一个右括号；修正后全套通过，未在失败时宣布完成。
- 代码审查发现不支持的负数/畸形逗号金额可能被截取为正数：收紧数字边界，添加 4 个反例，全部通过。
- 审查发现模型调用异常时预算预留与已结算值需要区分：新增 unsettled_model_calls 和报告注记；预算、取消及费用测试通过。
- 规划推断需要影响后续任务：保留白名单重点并由 assess_evidence 消费，新增模型增加分析重点的契约测试通过。

## 例外与未完成项

| 项 | 状态 | 依据 / 后续 |
| --- | --- | --- |
| 本次真实远程模型联调 | WAIVED | 用户明确选择“先交付独立包和本地报告，保留模型接入配置”；调用入口和本地协议故障测试已实现 |
| 实际浏览器截图与视觉检查 | BLOCKED | UI 工具返回没有可用浏览器和 App；Chrome unavailable。DOM 交互通过不替代截图；浏览器可用后检查桌面/窄屏与打印 |
| Dify 云端/任意第三方导入 UI | 未部署范围 | 已交付 OpenAPI/Responses 回调示例及本地协议测试；实际部署需平台可达地址和宿主回调绑定 |
| V3 研究、专业与证据充分性认证 | 未关闭 | 本包代码测试不替代 docs/ai_docs_center 的独立验收 |

本轮实际源码修改限于 agentic。旧线与 product_v1 业务源码、生产数据库、生产配置未改动；工作区原有的其他变更保持原状。旧 0.1 日志和 wheel 在 reports/history-0.1，不计入本次通过数量。
