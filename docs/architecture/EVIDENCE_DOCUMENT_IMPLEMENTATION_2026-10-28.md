# 证据文档层实施说明

日期：2026-10-28。依据：[已批准方案](EVIDENCE_DOCUMENT_UPGRADE_PLAN_2026-10-25.md)。

本轮落实方案最后一节指定的 **0A + 0B**，同时加入可恢复阅读和 Docling Native 对照。没有把整条研究路线声明为完成。

## 交付范围

| 内容 | 状态 |
| --- | --- |
| 自有 EvidenceDocument、ParseRun、SourceRef v2、坐标工具 | 已接入；历史 documents 行映射为解析运行，旧文档定位器和像素来源继续兼容 |
| 文档发布 → 来源投影 → 主流程冻结 → ProofGraph | 已打通；只有文档、没有聊天的案件也可整理事实，不伪造 Message |
| 多配置、不可变快照、原始产物哈希 | 已接入；新版本独立保存，旧引用继续绑定旧快照 |
| 案件后台解析任务 | 已接入；入队、查询、页段 checkpoint、租约恢复、停止后续页 |
| Unicode 跨块续读、FTS、引文歧义 | 已接入；完整正文索引，字符预算不冒充 token 预算 |
| Docling Native | 隔离安装并验证 DOCX / XLSX / PPTX / CSV；保留 MinerU 默认 |
| Paddle PP-StructureV3 | 隔离候选适配器已编写；本地模型和原图坐标未验收，入口禁用 |
| Marker / DeepDoc、微信跨图消息身份 | 本轮未实施，沿用方案的后续评测顺序 |
| 扫描准确率、专家法律支持评测 | 待评；合成 smoke 不能代替这些指标 |

## 真实流程

~~~mermaid
flowchart LR
    A[原件与哈希] --> P[固定配置的独立解析运行]
    P --> W[后台页段任务与检查点]
    W --> D[自有文档块与原始产物清单]
    D --> S[不可变解析快照]
    S --> O[待投影发布记录]
    O --> R[案件 SourceRef 幂等投影]
    R --> I[冻结分析输入]
    I --> G[既有法律 DAG 与 ProofGraph]
    G --> L[来源账本与审核摘要]
    L --> V[授权 Resolver 回到固定原文]
~~~

上传、阅读、检索、发布不触发付费模型。逐段模型分析仍由用户选择配置后显式触发；主流程沿用既有模板和审核门。文档发布不依赖无关聊天转录的重新校验。

## 职责及修改位置

以下路径相对 product_v1。

| 职责 | 代码 |
| --- | --- |
| 自有文档、运行、任务、坐标契约 | backend/src/screenshotlegal/domain/evidence/documents.py |
| 冻结来源、原件与解析身份 | backend/src/screenshotlegal/domain/evidence/sources.py |
| 解析端口 | backend/src/screenshotlegal/application/ports/parsing.py |
| 固定引擎配置和能力注册 | backend/src/screenshotlegal/documents/parsers.py |
| 原始格式分发和供应商字段 | scripts/document_worker.py、scripts/document_candidate_worker.py |
| 边界归一化、解析、发布用例 | backend/src/screenshotlegal/documents/service.py |
| 缓存与原始产物 SHA 校验 | backend/src/screenshotlegal/documents/adapter.py |
| 窗口、快照、任务、发布记录 | backend/src/screenshotlegal/documents/store.py |
| 不可变字符续读 | backend/src/screenshotlegal/documents/reading.py |
| 引文范围、歧义和原件检查 | backend/src/screenshotlegal/application/services/source_resolution.py |
| 文档进入案件运行 | backend/src/screenshotlegal/application/services/workspace.py: start_run |
| 来源账本、output_digest、审核 | backend/src/screenshotlegal/application/services/proof.py |
| HTTP 命令与查询 | backend/src/screenshotlegal/api/documents.py |
| 任务、对照版本、发布与表格展示 | frontend/src/features/workbench/DocumentControls.tsx、DocumentWorkbench.tsx |
| 服务端校验后回跳 | frontend/src/features/source-navigation/index.tsx |

领域层不导入解析 SDK。原始 JSON 保留在隔离产物中，经 normalized 转为自有块；供应商 parent/children 引用转换为本地块 ID。无法可靠映射的根/分组仍保留在原始产物中，不生成悬空块引用。

OpenAPI 已重新导出到 artifacts/openapi.json，前端 schema.d.ts 已重新生成。新任务控件消费生成的 ParseJobView / ParserCapabilities 类型。

## 为什么可以混合资料、渐进阅读并定位原文

这由三个机制共同完成：

1. **混合格式**：worker 按 PDF、Word、表格、PPT 等格式分发，读取各原生解析后端的输出，再转成 DocumentBlock。无需把各类业务对象都变成聊天消息。
2. **渐进解析**：应用记录已提交范围，每次原子提交一个 PDF 窗口。任务重新领取后从已提交范围继续。Office Native 使用逻辑单元，不声称具有物理打印分页或逐页 OCR 进度。
3. **阅读与定位**：固定解析快照确定块文本，read_snapshot 返回实际字符范围、截断信息和 next_request；原件、页图、bbox 和字符引文分别提供不同精度的位置。

模型只消费确定范围的结构文本。它没有因成功定位而自动获得法律正确性认证。

## 来源项目的哪些部分被采用

固定源码链接与原有取舍见 [方案第 4 节](EVIDENCE_DOCUMENT_UPGRADE_PLAN_2026-10-25.md#4-来源采用部分及不采用替代方案的理由)。

| 来源 | 本项目的落地 | 没有选整套替代方案的原因 |
| --- | --- | --- |
| Docling-Core DocItem / ProvenanceItem / BoundingBox | 自有类型、层级、坐标、单元格结构 | DoclingDocument 不表达案件 ACL、审核和法律运行，不直接作为核心业务模型 |
| MinerU Doclib 范围、续读和定位协议 | 固定快照、范围响应、块内续读 | 不引入第二个资料数据库，不复制长文首尾截断索引 |
| Docling Graph provenance ledger | ProofGraph.citation_bindings 和 Resolver | 法律 ProofGraph 已有 claim / fact / burden / gap；通用实体图不等价 |
| RAGFlow / DeepDoc 分发与适配思想 | CONFIGS、隔离 SDK、统一输出 | 不重复引入账户、任务和存储系统 |
| Paddle PP-StructureV3 | 独立候选进程和结构化结果转换 | 未获得本项目扫描、印章和原图定位验收，不直接作为默认 |

实际对照安装的是 docling-slim 2.143.1 / docling-core 2.105.0，调用原生 Office 后端。完整 DocumentConverter 会提前加载 ASR / Torch，本轮未采用；本配置不声称包含 Docling PDF 模型管线。四种格式已在相同合成资料上验证已知金额、独立运行、快照和产物保存。这是工程 smoke，不是引擎准确率排名。

## 数据与恢复规则

- 缓存包含原件 SHA、解析器/适配器版本、输出协议、请求范围，并由独立解析运行的目录隔离配置；读取时校验原始产物 SHA。
- 页段、进度、块在文档库事务内提交。任务租约 300 秒，解析子进程超时 180 秒。过期任务从已提交窗口继续。
- 停止后续解析等待当前窗口完成，保留结果，不承诺强杀正在运行的 SDK。
- 发布保留待投影记录，案件来源写入后确认；确认前中断可幂等重放，明确失败可由用户重新发布。
- 主流程先确认发布再冻结输入。文档资产进入输入快照，来源不会指向不存在的图谱资产。
- 默认检索使用每个原件最近明确发布的解析；显式 document_id 可以查询指定运行并标明发布状态。未发布新版本不会悄悄进入默认搜索。
- quote 多处出现返回 ambiguous；不匹配返回 unresolved；越界或指定范围与引文冲突会拒绝。
- 统一字符单位为 Unicode code point，保持左闭右开；未将 30,000 字符等同于模型 token 限制。
- 文档显示框为左上角 0–1000；旧聊天来源维持图片像素。无可靠框时降级到页或逻辑单元，不猜坐标。
- 命题支持和文本匹配分开；账本绑定实体 output_digest，继续复用审核过期机制。
- 未读取 configs/models.local.yaml。运行验证使用应用中已保存的加密凭据，未输出密钥。

## 验证和复现

业务 Python 位于 product_v1/.conda/screenshotlegal-v1/python.exe。在 product_v1/backend 运行：

~~~powershell
python -m pytest -q
python -m pytest tests/test_evidence_document_layer.py -q
python ../scripts/verify_document_parser.py --output ../reports/document-parser-local
python ../scripts/compare_document_parsers.py
~~~

候选依赖通过 scripts/setup-document-candidates.ps1 安装在 .tools 对应隔离环境。Docling 实测依赖锁定见报告目录 docling-requirements.lock.txt。Paddle 尚未完成模型/坐标验收，未创建 verified.json，也未开放 UI 运行。

DeepSeek 合成验证脚本为 scripts/verify_document_model.py，调用前将请求预留到 SQLite 账本，最多 50 次，失败与未知结果也计数，无自动重试。本轮实际 1 次，通过逐字引文和字符范围校验。

验收结果、日志和服务状态见 product_v1/reports/evidence-upgrade-2026-10-28/RESULTS.md。

前端 Vite 开发服务支持热更新；本轮后端正常运行 uvicorn，未开启 reload，修改 Python 后需重启。队列和已保存批注不依赖浏览器持续打开。
