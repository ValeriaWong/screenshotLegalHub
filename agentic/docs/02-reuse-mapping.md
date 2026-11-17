# 复用与独立性映射

复用范围以用户最新要求为准：保留已在 agentic 内实现的通用能力，参考原项目设计，不依赖原业务运行线。

| 能力 | 复用/参考来源 | 本包落点 | 必要性与理由 |
| --- | --- | --- | --- |
| 生命周期、DAG、有限重试、取消 | agentic 0.1 core.py/planning.py | 原模块延续 | 已有实现与测试，无需重新造调度器 |
| Tool/Skill Registry | agentic 0.1 tools.py/skills.py | 原模块延续，注册真实内建能力 | 区分原子操作与阶段任务 |
| Review/Checkpoint/事件 | agentic 0.1 review.py/state.py/observability.py | 原模块延续 | 保留事务状态、Gate、恢复与权限边界 |
| 严格 JSON、摘要、投影、重试 | 原项目通用约定 | primitives.py 最小独立实现 | 移除原 screenshotlegal 运行时导入，保持 backoff 等公共字段；未搬运业务引擎 |
| 事实/推断与来源分离 | 原契约及 case_presentation.py | builtin/contracts.py、workflow.py | 不变原文、精确引用、待核时间和推断状态 |
| 时间轴/来源弹窗/分层展开 | blocks/retriever/web/case.html / case.js | templates/report.*、report.py | 独立、自包含产物；不引用原脚本、CSS 或 API |
| 平台桥接 | agentic 0.1 adapters | Responses、Dify、Generic、HTTP | 保持 Core 与平台解耦，新增鉴权 HTML 读取 |
| 五阶段推理 | 0.1 缺失 | builtin/*.py、prompts/*.md、model.py | 本次新建实际任务能力，非空接口 |

已移除 adapters/product.py 和 examples/retrieval.py；旧 evidence_lookup 示例替换为 evidence_analysis。0.1 是本次建设过程中的初版，未修改现有项目公共业务接口。包名 screenshotlegal-agentic 是分发名称，不是运行时应用依赖。

验证：静态 AST 导入检查；隔离 Python 子进程阻止 screenshotlegal/legalhub 导入仍可完成真实 E2E；wheel 在隔离目录安装并运行。DOM 测试可使用仓库已有 jsdom 开发依赖，报告运行和 Python 安装均不需要旧前端。
