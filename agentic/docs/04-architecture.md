# 架构与取舍

Request → Context → 固定阶段 DAG → Skill → Tool / Stage Model → Deterministic Review → 下一阶段 → ReportData → report.html。

Core 管理任务/阶段状态、依赖、预算、超时、取消、人工 Gate 和恢复。builtin 管理证据业务，adapters 管理外部协议，report 管理表现层。任何宿主可组合自己的 registries/workflows，Core 无法律业务分支。

| 模块 | 职责 |
| --- | --- |
| contracts.py / primitives.py | 公共 Run/Task/Review/Principal 契约；独立 JSON 工具 |
| core.py / planning.py / context.py | 生命周期、DAG 校验、显式状态机、依赖投影、预算 |
| skills.py / tools.py / review.py | 注册、输入输出校验、受限原子调用、Review/Repair |
| state.py / observability.py | SQLite Checkpoint、CAS、单 worker 锁、幂等与事件 |
| builtin/contracts.py / tools.py / workflow.py | 文本证据 Schema、五个原子操作、五个阶段 Skills |
| model.py / prompts | Responses 阶段推理、输出结构、Prompt 版本和指纹 |
| adapters | Generic SDK、Responses function callback、Dify OpenAPI、HTTP/SSE |
| report.py / templates | 经复核 Run 的单文件报告；不执行模型生成 HTML |

规划采用两层：Core 的安全 DAG 在创建 Run 时确定；planning Skill 的语义计划确定后续检查重点。模型可以在枚举范围内增加重点和问题，后续 assess_evidence 消费该计划；不能删除 identity/source_quality/chronology 必要项或重写 DAG。取舍是保留可预测的恢复/权限边界，不做开放式无限规划。

每个阶段先调用确定性 Tool，再在配置启用时调用模型。阶段模型输入是当前材料、必要上游结果、阶段结果和有限修复意见；每次使用完整独立 Prompt，不继承不受控的聊天状态。模型结果为结构化候选判断/问题/缺口建议，带逐字引用与不确定性，不能修改事实账本。synthesis 的模型摘要在报告单列，最终 determination 仍受代码边界约束。

Review 顺序：输出 Schema → 引用合法性/逐字匹配 → 账本原文、时间和摘要不变 → 必要规划/阶段完整性 → 缺证和人工项保持未闭合。失败进入 repair handler，附 Review findings，再评审；默认最多 2 次。无上限循环不存在。软件 Review 不验证复杂法律推理的实质正确性。

状态：PENDING → RUNNING → COMPLETED/FAILED/CANCELLED/WAITING_REVIEW/INTERRUPTED。恢复仅接受 WAITING_REVIEW 或 INTERRUPTED，核对 owner、权限、版本/Prompt 指纹与 Gate 摘要。已完成 Tool 的结果可重放；未知外部调用不视为成功。模型中断可能已计费，额度保守保留。

小规模部署用 SQLite 单 worker 和顺序阶段执行，不引入 Redis/Celery/Agent Framework。持久化同时写入 Run 与 Event，并使用 revision CAS。Core 已支持副作用 Tool 的参数绑定审批和幂等协议；本包内建能力仅分析调用方数据，不包含危险操作。
