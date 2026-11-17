# 独立阶段推理包（0.2）

本文件取代 0.1 对 product_v1 运行时的依赖方案。依据用户最新要求：Skills、Tools、Planning、阶段 Prompt、模型调用与报告渲染均在 agentic 内；旧线只作交互和契约设计参考。模型联调本次不执行，用户已选择本地报告与可配置模型入口。

## 分析与设计 Gate：PASS（实现前）

当前 0.1 已有可保留的生命周期、DAG 校验、权限、有限重试/修复、Review、SQLite Checkpoint、Responses function-call / Dify OpenAPI 桥接。缺失：业务能力在外部 Product Adapter；没有阶段 Prompt、模型调用实现和独立报告。现有 screenshotlegal 导入与最新独立性要求冲突，必须解除。仅泛型 JSON 哈希、严格模型、重试、上下文投影需要包内最小实现；不搬运旧业务引擎/数据库/渲染器。

## 最小链路与边界

输入 CaseInput（文本证据、来源 ID、时间精度、问题）→ Planning → Facts → Assessment → Gaps → Synthesis → report.html。

- Core 继续管理固定、安全的阶段 DAG、预算、超时、取消、Review/Repair 和恢复。
- builtin 内每个阶段有真实 Skill、原子 Tool、输入/输出 Schema。代码处理确定性提取、引用校验、金额精度、时间不确定性与报告结构。
- 五个版本化 Prompt 驱动对应阶段的 Responses 推理调用；公共 Prompt 约束证据与指令隔离，输出简洁判断依据而非内部思维链。
- Planning 允许模型在白名单内增加分析重点和问题；不得删除必要阶段、Review 或决定权限。后续分析消费规划重点。
- 模型返回结构化推断/候选缺口；来源 ID 与逐字引用必须通过本地校验。模型不改写原文、确定性账本或权限。失败显式终止；仅 Review 可进入有上限的修复。
- 不配置模型时运行真实代码规则，不伪造模型响应。该模式支持文本线索梳理，不能替代开放领域语义推理。
- HTML 是同一 Run 输出的静态自包含视图，使用时间轴、证据引用弹窗、筛选、阶段展开；不导入旧线前端、模板运行时或资产。

## 缺口补全策略

| 缺口 | 代码负责 | Prompt / 模型可补全 | 必须保留 |
| --- | --- | --- | --- |
| 事实/推断混淆 | 精确来源、原文、声明与事实分栏 | 语义归类、简洁依据、替代解释 | 现实真实性、身份与完整性待核 |
| 金额/日期与未知前提 | Decimal、明确时间精度、禁止缺值当已知 | 识别条件语句、待核时间关系 | 未给出的日期/支付凭证不能推断成事实 |
| 争点与结论一致性 | 缺证阻断结论升级、白名单阶段、引用门禁 | 反向解释、问题分解、建议补证 | 专业裁判、适用法律与证据充分性认证 |
| 来源/产物可追溯 | 原文哈希、Run/Task/Trace、Prompt 哈希、事件/Checkpoint | 有依据的推断可追溯展示 | 文本哈希不是原始文件真实性证明 |
| 模型与预算就绪 | 真实 Responses HTTP、超时、限次、费用预留、配置校验 | 分阶段结构化输出 | 服务实测、能力/价格配置、独立评测 |
| V3 G01–G18 研究认证 | 记录实现与验证证据 | 辅助材料整理 | 不能因软件测试通过而宣告认证关闭 |

## 新增模块必要性

primitives.py 解耦通用基础；builtin/contracts.py 是本地文本证据契约；builtin/tools.py 是实际原子能力；builtin/workflow.py 是阶段组合和规则 Review；model.py 是可替换 Responses 调用；prompts 是版本化执行策略；report.py/templates 是独立输出。沿用当前 Python 3.12/Pydantic/httpx/FastAPI，不引入新 Agent Framework。

## 后续验收条件

1. 包内无 screenshotlegal/legalhub 导入，也不读取旧数据库、fixture、模板或配置。
2. 独立数据包执行五阶段并输出可交互 report.html；改变输入会改变账本、缺口和结论边界。
3. 原有 Runtime 测试继续通过；补充模型 HTTP 契约、超时/拒绝/非法引用、Prompt 注入、HTML 转义、独立安装测试。
4. 模型线上验收明确记为未执行，不使用模拟服务代表真实模型效果；本地端到端使用实际代码能力。
5. 报告和文档记录可自动补全与必须待补证/复核的区别。
