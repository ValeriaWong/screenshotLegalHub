# 项目能力现状（0.2 更新）

依据 docs/ai_docs_center/{README,FEATURES,GAPS,ISSUES,DOCUMENTATION_MAP}.md 和当前源码扫描。最初 0.1 方案复用 product_v1；用户随后明确要求“Skills/Tools 都在当前程序包，不依赖旧线”。本版以独立运行替代原 Product Adapter。

| 层 | 已有项目证据 | 原能力与约束 | 0.2 决策 |
| --- | --- | --- | --- |
| 技术栈 | product_v1/backend/pyproject.toml | Python 3.12、Pydantic 2、httpx、FastAPI、Uvicorn、SQLite/SQLAlchemy | 保持语言和已有库，不引入 Agent Framework |
| 执行器 | product_v1/backend/src/screenshotlegal/runtime | DAG、重试、上下文投影；执行器绑定案件与 stage6 Gate | 不导入业务执行器，沿用 agentic 已有通用 Core |
| Skills | product_v1/backend/src/screenshotlegal/plugins/skills/deterministic.py | 已有路由、时间线、proof graph 等固定业务能力 | 不宣称迁移全套能力；本包实现最小文本证据链 |
| 工具与检索 | product_v1/backend/src/screenshotlegal/infrastructure/retrieval/fts.py、legalhub/retrieval.py | 原库内 FTS、来源读取与 case scope | 本版不依赖原库，不保留其检索 Adapter |
| 模型 | product_v1/backend/src/screenshotlegal/infrastructure/model/providers.py、legalhub/providers.py | 原业务 provider、Chat Completions 和开关 | 新建小型 Responses 调用模块，显式配置与预算 |
| 认证/服务 | product_v1/backend/src/screenshotlegal/application/services/{auth,workspace}.py 与 API | 原用户/案件认证、服务和数据库 | Host 注入 Principal/Auth，内核不继承原业务身份 |
| 结果交互 | legalhub/case_presentation.py、blocks/retriever/web/case.html、case.js | 时间轴、来源互跳、引用侧栏、条件显示 | 参考交互逻辑；模板/CSS/JS 在包内独立实现 |
| 研究认证 | docs/ai_docs_center/GAPS.md | V3 多项证据/校准/专业复核缺口未完成 | 实现改进不改变其认证状态 |

0.1 实际已完成通用 Runtime、Tool/Skill Registry、确定性 Review、人工 Gate、SQLite Checkpoint、Responses/Dify/Generic 桥接。该部分在本次保留并做回归。0.1 的检索演示只贯通检索与来源校验，未包含阶段 Prompt、模型推理和 HTML，是本次实质补齐的部分。

不进入 Core：法律结论、案件数据库结构、旧认证 Cookie、特定平台协议、UI 模板和业务词面规则。包内 builtin 是可替换插件，Core 仍可运行其他 Workflow。

分析 Gate：PASS。冲突已明确：原“尽量直接导入已有代码”要求在本次按用户最新“独立包”指令调整。未重构或修改旧业务源码和生产配置。
