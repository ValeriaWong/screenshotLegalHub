# ScreenshotLegalHub 当前架构

核验日期：2026-11-17。以下当前结构来自源码静态核验；未在本轮启动服务、重跑应用测试或调用模型。后半部分保留历史架构记录。

## 当前系统与部署边界

```mermaid
flowchart TB
    Browser[浏览器：工作台 / 控制台 / 生成 / 审核 / 评测]
    Browser --> Frontend[product_v1/frontend：React + Vite，18431]
    Frontend --> API[FastAPI：/v1，18430]
    API --> Workspace[账户权限 / 案件证据 / 分析与审核]
    API --> Research[研究 API 与 worker]
    API --> Documents[文档 API 与 worker]
    Workspace --> ProductDB[产品库 / 原件 / 加密凭据]
    Workspace --> Runtime[Compiler → CasePlan DAG → Runtime / Skills]
    Runtime --> Proof[ProofGraph / 证明矩阵 / 人工 Review]
    Research --> ResearchDB[独立研究库 / 批次 / 发布版本 / 评测]
    Documents --> DocumentDB[独立文档库 / 解析资产]
    Documents --> Parser[独立解析解释器与 worker]
    Host[外部宿主 / CLI] --> Agentic[agentic：独立文本分析包，示例 HTTP 18440]
    Agentic --> AgentState[SQLite checkpoint / events / HTML 报告]
    LegacyUI[旧 blocks/retriever/web] --> Legacy[legalhub：ThreadingHTTPServer，18420]
    Legacy --> LegacyAssets[旧索引 / blocks artifacts / 研究资产]
    Offline[离线 tools / paper 研究脚本：显式执行与数据适配]
```

图中的 `agentic`、`legalhub` 与产品不是已集成的统一执行引擎。三个源码包未发现相互运行时导入；离线迁移工具仍可能依赖旧包和仓库资产。四类产品入口是同一应用的业务边界，五个 HTML 入口并不代表五个独立服务。

## 目录、入口与数据归属

| 位置 | 当前职责与关键文件 |
| --- | --- |
| `product_v1/backend/src/screenshotlegal/api/main.py` | `create_app` 组合服务、注册 API，并在 lifespan 管理研究和文档 worker |
| `domain`、`application/ports`、`application/services` | 领域契约、能力接口与业务用例；`workspace.py` 仍直接组合基础设施和 Runtime |
| `runtime`、`plugins`、`infrastructure` | DAG 执行、能力注册、持久化、模型网络及原件存储；`stage_executor.py` 仍依赖应用层 proof 和具体 Skill 工厂 |
| `research`、`experiments`、`method_reproductions` | 研究批次、合成、审核发布、评测及方法适配，与案件业务共享应用入口和账户体系 |
| `documents` | 文档注册、任务和解析适配；`adapter.py` 通过独立解释器执行解析 worker |
| `product_v1/frontend` | `vite.config.ts` 注册五个 HTML 构建入口；`src/main.tsx`、`console.tsx`、`research.tsx` 启动对应界面 |
| `agentic` | `core.py` 管理运行、DAG、预算；`builtin/workflow.py` 定义五阶段；`state.py` 管 checkpoint；`adapters` 提供平台接入；`report.py` 渲染报告 |
| `legalhub`、`blocks/retriever/web` | 旧 Python HTTP 服务、检索/问答/时间轴/批注与原生前端 |
| `blocks`、根 `tools/tests`、`paper`、`configs/v3` | 研究与数据流水线；不会随产品启动自动全部运行，复现依赖各自资产和环境 |

产品数据根由 `screenshotlegal/settings.py:Settings.data_dir` 指定，默认是 `product_v1/data`。主库为 `screenshotlegal.sqlite3`，研究库为 `research/research.sqlite3`，文档库为 `documents/documents.sqlite3`；凭据主密钥为数据目录内 `.credentials/model-master.key`。整个数据目录、备份和原件均排除提交。旧索引默认位于 `blocks/retriever/artifacts/index.sqlite3`。独立 Harness 的持久化由宿主指定；示例 CLI/HTTP 使用临时库，不能当作长期保存服务。

## 执行链与已知限制

- 产品：Matter Pack → Compiler → CasePlan DAG → 分阶段 Skills → ProofGraph/证明矩阵 → 人工 Review；文档解析与研究任务分别有 worker。分层已存在，模块化单体重构建议尚未全部实施。
- 独立 Harness：Planning → Facts → Assessment → Gaps → Synthesis，每阶段先执行确定性 Tool，再按配置调用模型并做 Review/有限修复。它只接收已转写文本，不包含 OCR、PDF 解析或产品完整案件契约。
- 文档解析默认使用产品 `.tools/mineru-env`，可由 `DOCUMENT_PARSER_PYTHON` 覆盖；这不表示后端环境已安装完整 OCR 能力。
- 用户工作台的 `MockPresentationGenerator` 只返回模拟 PPT 预览。程序验证、规则 Review 与法律专业认证分别验收。
- 当前 Vite 开发配置和产品 `Settings.host` 默认为 `0.0.0.0`，实际监听仍由启动命令决定；旧线和 Harness 示例 HTTP 绑定回环。端口 18420/18430/18431/18440 是代码约定，本轮未做运行可达性验收。

源码与本地数据的提交边界见[仓库安全说明](REPOSITORY_SAFETY.md)。更细的产品和独立包说明分别见[产品架构](../product_v1/docs/ARCHITECTURE.md)、[Harness 架构](../agentic/docs/04-architecture.md)。

## 历史架构记录

> 2026-10-24：当前仓库职责、源码依赖与模块化改造建议见[架构盘点与重构方案](architecture/REFACTOR_PROPOSAL.md)。下文保留各时期架构记录；目标目录与端口方案尚未实施。

## 2026-10-22 架构补记

当前综合状态见[AI文档中心](ai_docs_center/README.md)和[V3阶段评估](ai_docs_center/PROGRESS.md)。下方原有图及Block表是2026-10-04旧软件/研究基线；不能据其第一轮描述判断后续工作未做。

| 软件/研究线 | 实际结构与边界 |
|---|---|
| `legalhub`（18420） | 原有Python工作台：检索/转录/问答/来源/法律批注；[v1.2.0验收](../reports/v1.2.0_legal_review_workspace.md) |
| `product_v1`（API18430/UI18431） | 独立FastAPI/React；domain/application/plugins/runtime/infrastructure/api；Matter Pack→CasePlan DAG→ProofGraph/Matrix→审核历史/SSE；账户/协作/导入/模型设置已扩展；[产品架构](../product_v1/docs/ARCHITECTURE.md) |
| V2 | 四轮候选已独立保存；[第三轮](../datasets/v2.0.0/round_003/REPORT.md)与[第四轮](../datasets/v2.0.0/round_004/REPORT.md)是当前候选进展；尚无专业认证 |
| V3 | S0–S7尚未阶段验收；认证依赖图、充分路径/结论一致性、完整双模式及专用Excel/PPT需另行接入和回归 |

新产品运行时不依赖旧legalhub、根模型配置或旧数据库；旧数据适配通过[显式迁移工具](../product_v1/docs/MIGRATION.md)，目前仅合成迁移验收。具备ProofGraph/缺证线索不等于V3证据充分性认证。

## 2026-10-04 旧架构基线


核验日期：2026-10-04。图中标明当前可运行部分与待实现部分。参考 [LegoFlow 官方架构](https://github.com/LegoX/LegoFlow) 的 block 合约：各阶段拥有配置、脚本、skills、依赖索引和运行产物；不直接搬用其 SWE 数据采集、代码执行奖励或训练流程。

## v1.0.0：先实跑，再选型，再交付软件

```mermaid
flowchart TB
    ROOT[Root：版本 / 运行配置 / 进度]
    OLD[历史资产 projects / 归档.zip / 毕业文档 / GitHub]
    OLD --> C[Curator 已运行：图片索引 / 哈希 / 来源]
    C --> FREEZE[冻结八类任务 / dataset digest 已运行]
    FREEZE --> E[Evaluator：24题 pilot / P3 200图及30项多图复测]
    CLOUD[云端视觉模型] --> AD[模型 adapter]
    LOCAL[可选本地视觉模型服务] --> AD
    AD --> E
    E --> REPORT[MD / 原始响应 / 分任务指标 / 费用与延迟]
    REPORT --> PICK[分任务评估及原文定位检查 / K3 联调默认]
    PICK --> PROD[Evidence / 代码 Retrieve：本轮闭环已运行]
    C --> PROD
    ROOT --> C
    ROOT --> E
    ROOT --> PROD
    UP[案件多张截图 / 提交方 / 页码 / 会话信息] --> STORE[原件及完整处理记录]
    STORE --> MSG[已运行：消息及事件候选 / 原文 / 时间 / 图片区域]
    PROD --> MSG
    MSG --> ID[图内说话位置已保留 / 跨图身份关联待实现]
    ID --> MODE{模式}
    MODE -->|法官| J[待实现：双方对齐 / 重叠合并 / 缺口 / 冲突]
    MODE -->|律师| L[待实现：指定委托方有利 / 不利 / 中性标注]
    J --> EVENTS[事件与意思表示 / 来源链 / 时间区间]
    L --> EVENTS
    MSG --> R[已运行：代码案内检索 / FTS5及BM25 / 无模型调用]
    EVENTS --> R
    LAW[已导入归档类案及民法典 / 版本与来源] --> R
    R --> EX[已有：CSV / JSON 完整引用 / 页码 / 原图框]
    EX --> PPT[待实现：专用 Excel / 时间轴 PPT]
    EVENTS --> QA[人工复核及修订 / 失败案例]
```

Judge 仅重建双方材料共同支持的可观察聊天；未提交或截断的内容呈现为缺口。Lawyer 支持不利标注、律师选择工作视图及导出范围，保留原始材料和完整来源记录。两者均不得把推断时间写成可见时间。

## v2.0.0：开发数据飞轮与冻结评测分开

```mermaid
flowchart LR
    FAIL[v1 失败案例 / 分层分析] --> TARGET[确定能力缺口]
    TARGET --> JUDG[判决选择与引用定位]
    JUDG --> FACT[事实约束图 / 逐字引用 / 转述]
    FACT --> SYN[生成候选聊天 / 标记合成补充]
    SYN --> UI[微信中文 / WhatsApp 英文前端]
    UI --> SCREEN[固定视口截图 / message bbox / 截图真值]
    SCREEN --> Q[问题 / 最小证据集 / 推理依赖图]
    Q --> HUMAN[独立人工审核 / 多人评分校准]
    HUMAN --> DEV[开发集：迭代生成与评分 prompt]
    DEV --> TARGET
    HUMAN --> HOLD[判决级隔离：封存 test]
    HOLD --> RELEASE[版本化 benchmark 发布]
    RELEASE --> EVAL[同版本多模型评测 / 置信区间]
    EVAL --> PAPER[LaTeX 论文 / 图表 / 评审与证据矩阵]
    EVAL --> FAIL
```

Test 的答案和失败细节不用于逐题优化生成器或评分器；飞轮使用开发集与新候选池。下一轮发布新版本时，旧 test 保留为历史对照。困难样本需经证据移除、跨图必要性和文本捷径检查，不能只靠增加图片数或把语言写复杂。

## Block 对应与当前状态

| Block | 代码或资产 | 状态 |
|---|---|---|
| curator | tools/restart_inventory.py、tools/research_assets.py | 已运行 |
| evaluator | legalhub/benchmark.py、tools/iterate_v1_p3.py、旧 KIE runner | 已有真实 pilot；P3 复测；全量八轨及专业法律评分待完成 |
| evidence | legalhub/evidence.py、tools/extract_evidence.py | 已有真实抽取及完整上传闭环；事件及身份仍需复核 |
| retriever | legalhub/retrieval.py、legalhub/app.py、blocks/retriever/web | 代码查询、来源查看、类案/法条、大事记及导入已运行 |
| reporter | retriever export_rows、legal-exports skill | 已有完整引用 CSV/JSON；专用 Excel/PPT 待实现 |
| synthesizer / quality | blocks/synthesizer、legalhub/synthesis.py、历史评分及飞书导出 | v2 第一轮中英文 6 案已生成复核修订，待人工看效果；评分校准及难度验证仍待执行 |
| research | paper/、reports/research/、legal-paper skill | 资产核查及工作稿；实验待补 |

完整来源和缺口见 [重启核查报告](../reports/research/RESTART_FINDINGS.md)。

本轮 v2 的可运行阶段与模型替换见 [synthesizer 架构图](../blocks/synthesizer/README.md)，结果见 [第一轮报告](../datasets/v2.0.0/round_001/REPORT.md)。新目录与 v1 存储隔离；中文来源判决与历史生成池重叠，本轮定位为 development，不能当成新的独立 test。
