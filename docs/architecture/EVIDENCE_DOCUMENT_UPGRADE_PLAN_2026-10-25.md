# ScreenshotLegal 证据文档层优化更新方案

日期：2026-10-25（Asia/Singapore）  
状态：待实施方案。本次只做架构审计、官方源码核实和方案文档；没有更换运行解析器、安装候选引擎或修改业务代码。  
输入：[new_plan.md](../../new_plan.md)。依据版本与代码指纹见 [来源清单](EVIDENCE_UPGRADE_SOURCES_2026-10-25.json)。

## 1. 推荐决策

保留四产品边界和现有 FastAPI / React / Pydantic / SQLite / DAG 架构。先把当前文档 MVP 升级为“可以被案件分析可靠消费的证据文档层”，再以相同材料评测解析器。

具体分工：

- 本项目拥有 EvidenceAsset、EvidenceDocument、ParseRun、SourceRef、来源解析与发布契约。
- Docling-Core：借鉴类型化文档、层级与 provenance 的结构设计；Docling 解析器作为第一批对照候选。
- MinerU：继续作为已验证的当前默认通用文档引擎；借鉴 Doclib 的范围、续读与定位协议。
- PP-StructureV3：作为中文扫描、表格、印章等场景的专项候选，在隔离进程中接入。
- Docling Graph：借鉴来源账本和来源精度分级，服务于现有 ProofGraph。
- Marker：作为 PDF 对照基线和选择性 OCR 策略参考。
- RAGFlow/DeepDoc：借鉴解析器分发与结果适配，整套平台本阶段不引入。
- 微信结构化继续独立发展；目前代码只有人工、Mock 和通用视觉感知适配器，不能把规划中的 WeChatStructure 当作已完成能力。

对 new_plan.md 的主要调整：**借鉴 Docling Schema 不等于立即让 Docling 成为默认解析器。** 当前没有同批材料对比数据，立即切换会新增部署与迁移成本，却不能证明法律分析或引用质量改善。

## 2. 现有架构审计：优先解决什么

以下是代码事实，不是对候选项目能力的推测。

| 当前代码 | 已有能力 | 优化缺口 |
| --- | --- | --- |
| domain/evidence/models.py: SourceRef、Message | 微信消息及图片像素 bbox、原始坐标信息、quote | 缺少解析运行/版本、块、字符范围、页面坐标框架、来源精度 |
| documents/service.py: normalized、parse_next | 文档块、归一化 bbox、分段提交、原页预览 | 字典契约；读取仍以全局块序号定位；缺少独立 ParseRun |
| documents/store.py | 原件哈希、块、批注版本、解析进度 | 文档按 case+sha 去重，块按 doc+ordinal 唯一，无法自然并存多解析器/多版本产物 |
| application/services/workspace.py: start_run | 冻结案件、Matter、证据、消息和 SourceRef | 仍要求 messages 非空；没有文档块与解析版本输入快照 |
| application/services/proof.py: graph | 法律实体、证据关联、来源边、审核过期判断 | 尚无文档来源投影；无法从新资料块完整贯通到已有法律图谱 |
| infrastructure/retrieval/fts.py | 消息 FTS5、中文分词预处理、BM25 | documents/store.py 使用 instr(lower(...)) 查询；两条检索链没有统一来源结果 |
| api/documents.py | 用户触发 parse-next 和逐段分析 | 本地解析通过 asyncio.to_thread 等待完成；尚非统一持久化案件任务协议 |
| research/worker.py、research/store.py | 研究任务租约、心跳、checkpoint、显式重试 | 可复用机制，但研究库 owner 语义不能直接替代案件 ACL |
| SourceViewer / DocumentWorkbench / RegionCanvas | 图片、PDF 页图、标注、批注 | 有多套坐标/定位实现，需要共同的只读来源视图与坐标转换库 |

结论：**首要工作是把文档链路接入证据与法律运行快照。** 再增加解析器，不能自动补上这个缺口。

文档查看器显示一份 PDF，并不代表当前 start_run 已能分析这份 PDF。修改该入口时应支持文档输入，不应把每个 PDF 段落伪造成聊天 Message 来绕过检查。

## 3. 对 new_plan.md 中几个关键判断的校正

1. **渐进读取与渐进语义分析分开。** 读取可确定范围和续读位置；法律推理还需固定模型、任务、上下文与人工验收。
2. **三种窗口分别配置。** MinerU 内部内存处理窗口、本项目解析任务的提交窗口、模型阅读/分析预算，分别解决内存、恢复和上下文问题。不能把内部默认 64 页直接变成本项目的提交粒度。
3. **来源定位具有精度等级。** Docling Graph 有 verbatim、observed、document scope 和 unresolved，不能将“确定性记账”理解为“所有节点都有精确原文”。
4. **坐标不能混用。** 当前 SourceRef.bbox 是图片像素，文档块 bbox 为 0–1000；new_plan.md 示例还有 0–1 坐标。Docling 支持不同坐标原点，必须显式转换。
5. **供应商节点 ID 不承诺跨重解析稳定。** 同一个文件换版本/策略可能产生不同块。旧引用应绑定旧 ParseRun，而不是自动指向新结果的第 17 块。
6. **不要要求所有证据先变成 Event。** 时间性行为可产生事件；身份信息、合同条款、表格数据也可直接支持待证事实。
7. **new_plan.md 中的星级是场景假设。** 它们不是本项目真实材料上的准确率或上线依据。
8. **原文匹配和语义支持分别验证。** 引文在结构文本中出现，不等于 OCR 完全正确，也不等于这句话足以支持法律结论。

## 4. 来源、采用部分及不采用替代方案的理由

下列链接固定在已核实的源码提交。这里的取舍是针对本项目当前阶段，不表示竞争项目缺少所有类似能力。

### A. 文档契约：借鉴 Docling-Core，自有 EvidenceDocument

来源：

- [ProvenanceItem：page_no、bbox、charspan](https://github.com/docling-project/docling-core/blob/b501ec8011181db4a08a45b27a47fe7f66814cbe/docling_core/types/doc/common/reference.py#L205)。
- [NodeItem / DocItem：结构节点与来源](https://github.com/docling-project/docling-core/blob/b501ec8011181db4a08a45b27a47fe7f66814cbe/docling_core/types/doc/items/node.py)。
- [BoundingBox / CoordOrigin：坐标单位转换基础](https://github.com/docling-project/docling-core/blob/b501ec8011181db4a08a45b27a47fe7f66814cbe/docling_core/types/doc/base.py#L61)。
- [HybridChunker：结构和 token 预算结合](https://github.com/docling-project/docling-core/blob/b501ec8011181db4a08a45b27a47fe7f66814cbe/docling_core/transforms/chunker/hybrid_chunker.py#L56)。

采用：类型化页/块、父子关系、来源范围、独立坐标框架；读取段与原始块分离。

为什么优先借鉴它：这些结构与现有 Pydantic SourceRef 契约贴近，能把来源校验放在领域层。

为什么不直接采用完整 DoclingDocument：它不表达本项目案件权限、解析发布、人工修订与法律运行冻结。让业务对象直接依赖其 SDK，会使换引擎牵动法律、检索、审核和前端。

为什么不以 MinerU MiddleJson / Marker JSON 作为核心：它们是优秀的引擎产物，但仍属于特定引擎的解析协议。它们应作为原始 artifact 保留，再转换为本项目契约。

采用 Schema 设计不要求当前生产后端安装 Docling-Core；先实现最小自有契约，避免只为借字段就引入整套依赖。

### B. 续读、缓存与文档定位：借鉴 MinerU Doclib

来源：

- [DocContentResponse / ContentRequestScope / ContentNextRequest](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/doclib/types.py#L266)。
- [page / block / char 定位器](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/doclib/locators.py#L44)。
- [PDF 处理窗口](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/backend/analysis/pdf/window.py#L56)。

采用：范围请求、返回范围、截断状态、下一请求、按解析配置隔离的缓存；定位到块内字符。

为什么选择这部分：当前文档 MVP 已有 MinerU 隔离运行环境和页段 checkpoint，升级协议可沿现有实现演进。

为什么不只用 offset+limit 或 Markdown 截断：超长单块仍可能超过预算；块数不是 token 数；序列号不能表达旧解析版本与剩余字符。

为什么不直接挂接 MinerU Doclib 的数据库和全局文件扫描：案件权限、研究集隔离和发布快照应由本项目控制；避免产生第二份权威案件目录。当前只借协议与机制，SDK 仍经适配器调用。

**明确不照搬的部分：** 当前 [ParseService._maybe_update_fts](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/doclib/services/parse_svc.py#L1367) 会调用首尾截断函数。案件证据需要索引全部已发布块，不能仅索引长卷宗首尾。这里是根据源码作出的本项目完整性取舍。

### C. 图谱来源账本：借鉴 Docling Graph，保留现有法律图谱

来源：

- [ProvenanceLedger / SourceAnchor / NodeProvenance](https://github.com/docling-project/docling-graph/blob/bbcd0e4846fadfcadac2800784783e59cd2722a9/docling_graph/core/provenance/models.py#L198)。
- [bind_provenance](https://github.com/docling-project/docling-graph/blob/bbcd0e4846fadfcadac2800784783e59cd2722a9/docling_graph/core/provenance/binder.py#L172)。
- [来源精度及未定位状态说明](https://docling-project.github.io/docling-graph/fundamentals/graph-management/provenance/)。

采用：与推理并行保存的来源账本、实体合并后的来源保留、精确/近似/未定位分级。

为什么不直接用整个 Docling Graph 替换 ProofGraph：当前图谱已表达 claim、element、fact、burden、evidence_link、gap 与审核 digest；通用实体抽取图不直接等价于这些法律关系。

不能照搬的语义：某个实体标识或金额在一段中出现，仅说明它被定位到，不足以认定整条待证事实成立。引用范围校验与支持/反驳关系仍分别处理。

### D. 中文扫描专项：候选 PP-StructureV3

来源：

- [PPStructureV3.predict_iter 与配置入口](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/paddleocr/_pipelines/pp_structurev3.py#L31)。
- [输出结构与使用说明](https://github.com/PaddlePaddle/PaddleOCR/blob/dab3fe35379033fdcb2d0e9572fac0b36c9a9ebf/docs/version3.x/pipeline_usage/PP-StructureV3.en.md)。

采用候选范围：中文扫描页 OCR、版面、表格、印章文字；结果转换为 EvidenceDocument 与 SourceRef。

为什么进入专项对比：当前 MinerU 配置固定 Flash/txt/image_analysis=False，确实缺少已部署的扫描识别路径；Paddle 提供可单独配置的相关模块。

为什么不直接替代所有材料：Office 原生文字和表格不应无条件光栅化后 OCR；还没有本项目对照准确率。它也不应承担案件权限、来源版本或法律任务。

实施注意：该 Python 类是 PaddleXPipelineWrapper，实际部署需固定相容的 PaddleOCR、PaddleX、推理框架和模型。部分文档字段是可视化结果，适配器必须读取序列化结构，不能把可视化图片字典当作全部 JSON 契约。

### E. PDF 对照与选择性 OCR：Marker

来源：

- [PdfConverter](https://github.com/datalab-to/marker/blob/6d40b01930dd45f4fc3b014f2ede8fb0d8cb6b81/marker/converters/pdf.py#L59)。
- [OcrBuilder：按页面/问题块执行 OCR](https://github.com/datalab-to/marker/blob/6d40b01930dd45f4fc3b014f2ede8fb0d8cb6b81/marker/builders/ocr.py#L28)。
- [JSONBlockOutput：polygon、children、section_hierarchy](https://github.com/datalab-to/marker/blob/6d40b01930dd45f4fc3b014f2ede8fb0d8cb6b81/marker/renderers/json.py#L12)。

采用：基线候选、文本层质量检查后选择 OCR 的策略、块树到自有模型的映射参考。

为什么暂不做默认：本项目首先需要通用资料与法律来源链闭环，已有可运行 MinerU。新增一套 PDF 栈的收益必须通过相同材料、成本和引用指标证明。

这不是断言 Marker 无法做多格式或一定劣于其他引擎。若它在特定材料上胜出，可经同一 Port 成为该场景默认。

### F. 解析器分发和位置适配：RAGFlow / DeepDoc

来源：

- [dispatchParse：配置解析器并返回边界结果](https://github.com/infiniflow/ragflow/blob/176e91d7c26c479ffcb2fb305743bb64bdf43250/internal/ingestion/component/parser_dispatch.go#L77)。
- [Docling 适配实现](https://github.com/infiniflow/ragflow/blob/176e91d7c26c479ffcb2fb305743bb64bdf43250/internal/parser/parser/pdf_parser_docling.go#L41)。
- [Paddle OCR 结果适配](https://github.com/infiniflow/ragflow/blob/176e91d7c26c479ffcb2fb305743bb64bdf43250/internal/parser/parser/pdf_parser_paddleocr.go#L28)。
- [部署服务配置](https://github.com/infiniflow/ragflow/blob/176e91d7c26c479ffcb2fb305743bb64bdf43250/docker/docker-compose-base.yml)。

采用：配置驱动分发、各供应商输出在边界归一化、能力差异显式暴露。

为什么不整套接入：本项目已有账户、案件 ACL、研究发布、DAG、检索和审核。直接嵌入平台会新增数据、权限及任务状态的同步边界。其部署配置还包含多种服务/存储选择，不能当成一个轻量解析库使用。

为什么 DeepDoc 暂后于 Docling/Paddle：当前重点是增加一套类型化文档对照和一套中文扫描对照；再加第三套感知栈的额外收益未证实。先保留可扩展 Port，后续按评测结果决定。

源码路径按本次核实的当前提交记录；该提交使用 internal/... 的 Go 模块，不沿用旧资料中的 rag/app/naive.py 路径。选型思想可参考，实现代码不能假定可直接 import 到当前 Python 应用。

### G. 微信、审核、法律 Runtime：优先复用本项目

- 微信：在 plugins/perception 上逐步新增会话、说话人、消息实例、跨图重叠识别。通用 OCR 作为可选前置，不把段落直接当消息。
- 审核：继续使用现有审核 revision、草稿、LabelU 矩形交换与渲染发布。完整 LabelU 平台不作为本轮新增依赖，避免双份任务和审核状态。
- 法律分析：复用 CaseCompiler、Runtime、StageExecutor、SkillRegistry 和 ProofGraph；不同时安装另一套通用 Agent Runtime 来接管案件。

## 5. 目标架构

~~~mermaid
flowchart TB
    UI["用户工作台 / 审核台 / 生成台 / 评测台"] --> UC["各产品应用用例与权限"]
    UC --> R["EvidenceRouter：材料类型 + 用户用途 + 固定配置"]
    R --> C["ChatPerceptionPort"]
    R --> D["DocumentParserPort"]
    R --> M["RawMediaPort"]
    C --> CHAT["Conversation / Message / MessageOccurrence"]
    D --> AD["MinerU（当前） / Docling（对照） / Paddle（扫描候选）"]
    AD --> DOC["EvidenceDocument + ParseRun + 原始产物"]
    M --> ASSET["EvidenceAsset"]
    CHAT --> REF["SourceRef v2 / SourceResolver"]
    DOC --> REF
    ASSET --> REF
    REF --> Q["按权限、发布版本检索"]
    REF --> SNAP["冻结案件分析输入快照"]
    Q --> SNAP
    SNAP --> SK["现有 Skills / 法律 DAG"]
    SK --> G["现有 Fact / Element / Claim / ProofGraph"]
    G --> LEDGER["CitationBinding 来源账本 + 人工审核"]
~~~

四产品各有用例和私有数据；共享契约、坐标工具、解析 Port 和任务机制。上图不是把四产品数据库合并。研究 DatasetRelease 和用户 CasePublication 使用不同业务标识。

微信消息、文档段落、原始媒体在 SourceRef/来源访问层统一；它们的业务对象继续分别建模。

### 使用的设计模式

| 模式 | 应用位置 | 带来的具体结果 |
| --- | --- | --- |
| 端口与适配器 | DocumentParserPort、AssetStorePort、SourceResolverPort | 换 SDK 不修改法律 Skill 与 UI 契约 |
| 适配器隔离外部模型 | 各引擎 normalize 与原始 artifact | 供应商字段/版本变化限制在解析边界 |
| Strategy + Registry | 固定 ParseProfile 与 EvidenceRouter | 按用途选择引擎；避免服务内部不断增加 if parser 分支 |
| Command / Query 分离 | ParseDocument 与 ReadDocument/SearchSources | 阅读不触发重解析或付费请求 |
| Repository + Transactional Outbox | 解析发布与 SourceRef 投影 | 跨当前文档库/案件库可靠衔接，无需分布式事务 |
| 不可变运行快照 | ParseRun、Publication、AnalysisInput | 升级解析器后旧引用仍能定位，审核不会被悄悄继承 |

DocumentParserPort 需报告 capabilities：支持的格式、页范围、OCR 是否可用、输出坐标框架、表格结构能力和取消/恢复语义。parse(input_ref, profile, scope) 返回 ParseArtifactManifest，供应商原始数据由适配器 normalize；不支持页范围的 Office 引擎可以整文件解析后分段读取，UI 不显示伪造的逐页完成度。

本阶段不增加消息总线、图数据库或向量数据库。是否引入由吞吐和检索测试决定。

## 6. 自有数据契约

### 6.1 原件、解析运行和阅读块分层

~~~text
EvidenceAsset
  case_id, evidence_id, source_sha256, mime_type, size, original_ref

ParseProfile
  parser_name, package_versions, adapter_version
  model_artifact_hashes, options, output_schema_version, profile_digest

ParseRun（不可变身份，进度单独更新）
  parse_run_id, evidence_id, source_sha256, profile_digest
  requested_units, completed_units, status, diagnostics, artifact_manifest

EvidenceDocument（指定 ParseRun 的视图）
  pages / logical_units
  DocumentBlock[]：block_id, type, reading_order, parent_id, children
  raw_text, text_digest, table_cells?, vendor_source_ref, source_regions

ReadChunk（派生，不替换原始块）
  chunk_revision, block_ranges, rendered_text, tokenizer_profile, token_count
~~~

关键规则：

- 同一文件可有 MinerU-A、Docling-B 两个 ParseRun；分别保存，不覆盖块。
- 页码从 1 开始；明确 physical_page / slide / sheet / logical_unit，不把逻辑单元冒充物理打印页。
- block_id 在一个已冻结 ParseRun 内稳定；不承诺换 parser/profile 后相同。
- 标题、段落、表格、公式、列表分别保留类型；表格单元格保留行列与 rowspan/colspan，平铺文本仅用于搜索/阅读。
- 原始 JSON/MiddleJson 保留并校验哈希，用于升级适配器和复查转换损失。
- 缓存键至少含 source_sha256、profile_digest、页面/单元范围和输出契约版本；原件去重不代表解析产物去重。
- ParseRun 模型信息与请求记录只保存版本/凭据引用，不保存密钥。

### 6.2 SourceRef v2：明确文本和空间两类来源

~~~text
SourceRefV2
  id, schema_version, case_id, evidence_id, source_sha256
  parse_run_id?, block_id?, message_id?, occurrence_id?
  page_no?, page_kind?, source_locator
  text_revision, text_digest, char_start?, char_end?, quote
  char_unit = unicode_code_point
  source_regions[]: frame_id, units, origin, bbox, transform_ref
  text_match = exact | normalized | ambiguous | none
  spatial_resolution = region | page | logical_unit | none
  review_status = unreviewed | verified | rejected | stale
~~~

示例地址：

~~~text
sl://cases/{case_id}/evidence/{evidence_id}/parse/{parse_run_id}/block/{block_id}
~~~

定位地址提供寻址，不提供授权；Resolver 每次检查当前案件访问权限。

quote 的 exact 表示它与指定 text_revision 的提取文本精确匹配，不表示扫描图字形或法律事实已被认证。换行/空格归一化匹配、重复句子的多位置候选必须分别标记，不能取第一次匹配冒充唯一位置。

字符范围绑定具体块文本，使用左闭右开区间。浏览器 UTF-16 下标与 Python 字符下标需要统一转换测试，尤其是非 BMP 字符。

### 6.3 坐标框架及兼容

当前像素 SourceRef 不能直接接收 0–1 或 0–1000 bbox。

- 新框架记录页面/图像尺寸、原点、单位、旋转、CropBox 与显示变换。
- 可选统一显示坐标为左上角 0–1；必须绑定明确的预览 frame，并保留原始坐标及变换。
- Docling 的底部原点先按明确页高转换；PDF points 不直接当图片 pixels。
- 展示层从同一 frame 转换到像素；只转换一次。
- v1 API 和现有 SourceViewer 通过兼容投影继续接收原来的像素 bbox；新文档 UI 逐步消费 v2。
- 缺少可证明的变换时，降级页面/逻辑单元定位，而不是猜框。

### 6.4 图谱引用与法律支持分开

CitationBinding 保存：

~~~text
analysis_run_id, entity_id, entity_output_digest
source_ref_ids, parse_run_ids, publication_id
relation = supports | contradicts | context
text_match, spatial_resolution, review_decision_id?
~~~

SourceResolver 确定“引用在哪里”；法律 Skill 和人工审核决定“引用是否支持命题”。两者不会因为共享一个字段就合并成一次认证。

复用 proof.py 中的 output_digest / stale 思路：命题或证据基础变动时，原审核标记过期；新解析结果不会继承旧审核通过状态。

## 7. 任务、续读与检索

### 7.1 持久化任务

把当前 api/documents.py 的长耗时解析改为提交任务并返回 job_id；查询/事件接口返回实际阶段和覆盖范围。

复用 research worker 的租约、心跳、checkpoint 机制设计，提取中立 JobPort；用户任务保留 case_id 与案件 ACL，研究任务继续按 dataset/release 隔离。先共享机制，按需要逐步迁移，不一次重写所有 DAG。

状态区分：queued、running、partial、succeeded、failed、cancelled；外部模型调用另保留 unknown_outcome。本地解析按页段恢复；已发出的外部请求结果未知时不自动再次调用。

解析器完成并不等于内容识别完整。coverage 记录哪些页被处理；quality 记录文字、表格、版面及人工审核状态，两者独立显示。

### 7.2 两层续读协议

1. ParseDocument 决定待解析页段、模型档位与恢复单元。
2. ReadDocument 只读指定已提交快照，按字符/模型预算返回范围与下一请求。

ReadResponse 至少包括：

~~~text
parse_run_id, requested_ranges, returned_ranges, parsed_coverage
content, content_ranges, context_ranges
truncated, truncation_reason, next_request
~~~

next_request 允许从某块的字符位置继续；不能只返回下一块。页段有空洞、尚未解析或受权变化时明确返回，不能“找不到后续块”就称全文已读完。

字符预算控制接口体积；模型 token 预算在指令、来源元数据和输出预留计入后校验。30,000 字符不能直接作为所有模型的安全上下文上限。

### 7.3 统一来源检索

延续现有 SQLite FTS5/BM25，在项目自有索引中纳入全部已发布文档块、表格可读内容及聊天消息。

- 统一返回 SourceRef、parse_run、页/块及片段，现有中文 tokenize 逻辑提取为共享实现。
- 查询前约束 case/release、权限和可用解析版本；用户案件与研究集分开。
- 搜索、片段显示和精确引用使用不同文本视图；检索归一化不能改写原文 char span。
- 旧解析版本的结果可按明确开关检索，不能悄悄混入“当前资料”。
- 若经人工标注的召回测试证明词法检索不足，再引入语义索引并做增益评测；本阶段不以部署向量库代替来源治理。

## 8. 和现有存储、API、四产品的迁移方式

### 8.1 渐进兼容，保留旧引用

1. 新增契约与 ParseRun/ArtifactManifest 表；当前 documents 记录映射为 legacy ParseRun。
2. 保存旧 document:.../page:.../block:... 与新 SourceRef 的别名映射。
3. 既有聊天 SourceRef 保持 ID 和像素语义；v2 增加身份与版本信息。
4. 从已有证据添加文档时关联原 evidence_id；历史独立文档回填案件资产绑定，验证哈希后建立映射。
5. 新 API 使用显式版本或兼容字段；补 response_model 与 OpenAPI，生成前端类型，减少长期维护重复 TS interface。
6. 默认解析器切换只影响新任务或显式新建的 ParseRun，旧引用继续读旧快照。

### 8.2 当前多 SQLite 的可靠衔接

不先把所有库合并，也不要求跨库两阶段提交：

- 文档库同一事务提交 immutable manifest、块和投影 outbox 事件。
- 消费者按事件 ID 幂等写入案件 SourceRef 投影；完成后确认事件。
- 在“案件投影完成”之前，不把该解析发布标成 ready_for_analysis。
- 分析快照只冻结已经发布且投影完整的解析版本及覆盖范围。
- 重试不能重复创建不同的来源身份；旧任务晚完成不能改写最新发布指针。
- 索引和跨库投影可从 immutable manifest 重建。

### 8.3 四产品各自的变化

| 产品 | 新增/优化 | 保留的边界 |
| --- | --- | --- |
| 用户工作台 | 文档案件可进入分析；统一来源预览、进度、续读、批注 | 原件保留；证据时间线继续以图片为主，文档另有资料视图 |
| 数据审核台 | 审核页/块/单元格/quote；对照解析运行；发布可评分版本 | 真原件的纠正转录作为派生修订；合成文本修改才触发新渲染 |
| 合成生成台 | 消费授权开发集的审核反馈和固定版本资料 | 不读取留出集答案；不改用户案件的原件和私有审核 |
| 评测台 | 增加 parser、输入表示和来源完整性指标 | 固定发布版本、Prompt/模型/预算快照；不沿用用户案件作为公共评测集 |

## 9. 目录与代码调整位置

沿用现有分层，只在职责稳定后迁移文件。下面是目标落点，不是本轮创建空目录。

~~~text
domain/evidence/
  documents.py          # 自有文档、ParseRun、Page、Block 契约
  source_refs.py        # SourceRefV2、CoordinateFrame、来源精度
  citations.py          # CitationBinding

application/ports/
  parsing.py            # DocumentParserPort + capabilities
  assets.py
  source_resolution.py
  jobs.py

application/services/
  document_ingestion.py
  document_reading.py
  evidence_publication.py
  citation_grounding.py

plugins/document_parsers/
  mineru.py             # 从当前 documents/adapter.py 演进
  docling.py            # 到候选试验阶段再加入
  paddle.py             # 到扫描试验阶段再加入

infrastructure/
  documents/            # 当前 DocumentStore 的迁移目标
  retrieval/            # 文档+消息的来源检索
  jobs/                 # 中立机制；存储权限仍分产品

api/documents.py         # 保留入口，拆开命令与查询
frontend/features/source-navigation/
  SourceViewer          # 共同只读视图，不混入审核保存逻辑
~~~

当前 Documents 同时承担校验、调度、读取和模型分析，宜按用例拆分；不先抽象所有旧类。domain 不导入 MinerU/Docling/Paddle SDK，adapter 的业务无关转换应可独立测试。

## 10. 实施阶段与完成标准

先做阶段 0 的契约与接通，不以“多接几个引擎”为第一交付。

| 阶段 | 交付切片 | 验收 |
| --- | --- | --- |
| 0A：契约与版本 | 自有模型、SourceRef v2、ParseRun、多版本并存、v1 别名 | 同文件两个解析运行互不覆盖；旧像素引用与旧文档链接仍可用 |
| 0B：接通案件 | 解析发布 → SourceRef 投影 → start_run 输入 → ProofGraph 来源 | 只有 PDF、没有聊天消息的案件可形成受控分析输入；每条采纳引用能回指定快照 |
| 1：可恢复阅读 | 持久化案件任务、char 续读、统一 FTS、权限与错误分类 | 杀进程恢复不丢已提交页；正文中间可检索；超长单块可完整续读 |
| 2A：解析器比较 | Docling Adapter，与当前 MinerU 比较 | 固定同批材料、归一化契约和下游 Skill；产物与成本可审计 |
| 2B：扫描专项 | Paddle Adapter、扫描/表格/印章审核 | 对照扫描基线，验证旋转/反扭曲后的原图回定位 |
| 3：深入专项 | 微信跨图消息、来源账本、语义支持审核；按需 Marker/DeepDoc | 分开报告文本定位、消息身份和命题支持质量；再按场景发布默认路由 |

阶段 0 的第一条完整切片：**一份文档 → 一个不可变解析运行 → 一条可校验引文 → 一个待证事实 → 点击返回原页**。同时用旧聊天案件做回归，避免统一模型破坏原路线。

阶段 2A/2B 不预先安排“必须换默认”的结果。单场景显著获益后，可以只调整该场景路由；现有默认也可能继续保留。

## 11. 评测及更换默认的门槛

### 11.1 同批、同版本、同任务

建议先做一轮小型分层试点，样本量是计划值，不是已运行结果：

- 文档：约 60 份，覆盖电子判决/合同、中文扫描、流水表格和 Office。
- 微信：约 20 个会话组，至少 100 张包含重叠、同名、未知时间和转账的截图。
- 开发/留出按案件组及来源内容分割；同一原件、渲染版本和近重复不得跨组。
- 所有引擎输出保留原件、版本、配置、原始结果和统一模型；下游 Skills/Prompt/模型保持固定。
- 原图 VLM、OCR、结构化文档属于不同输入处理条件，分别报告总成本，不能只算最后一次模型费用。

具体数量应由实际材料可用性调整；小样本用于发现问题，不能作为所有工业材料的泛化准确率证明。

### 11.2 分层指标

| 层 | 指标 |
| --- | --- |
| 文本/版面 | CER、块召回、阅读顺序、空白页/漏页、表格单元格及合并结构 |
| 来源 | 页码正确率、bbox/polygon IoU、引用 exact/ambiguous/unresolved 比例、回跳成功率 |
| 微信 | 消息分割、speaker、时间归属、跨图重复识别及误合并率 |
| 法律下游 | 专家标注下的证据—待证事实映射、支持/反驳关系、引文支持度 |
| 运行 | 每页耗时、峰值内存/显存、成本、失败/重试、恢复与人工修订时间 |

没有专家金标的法律指标标为待评，不让模型裁判分数或源字符串命中代替法律正确性。

### 11.3 必过工程门槛

这些是发布门槛，不是声称 parser 能达到 100% 准确率：

- 被系统采纳的来源记录必须解析到授权的固定快照；不能有悬空、跨案件或错版本引用。
- 范围外/缺失/歧义定位必须拒绝或明确降级，不能伪造精确结果。
- 字符续读在相同范围内无静默遗漏；有意加入的上下文单独标明。
- 新旧 parser 并存后，旧报告来源、旧审核 digest 和原件字节保持可追踪。
- 90/180/270 度、裁切页、不同尺寸、原点变换、长单块和重复引文都有回归。
- 外部调用结果未知时不盲目重发；实际失败类别与请求身份可追查。

引擎更换默认还需在预先约定的成本预算内改善目标场景，并经留出集与人工样本复核。收益相当时，优先保留维护成本更低、当前已稳定的实现；多引擎不是目标本身。

## 12. 本轮结论与下一步

采纳 new_plan.md 的“可替换适配器、自有证据模型、可追溯来源”方向；调整其默认解析器选择和若干精度假设。

建议下一实施轮只完成 0A + 0B：**先统一契约、保留版本、接通文档到 SourceRef/ProofGraph。** 随后完善持久化阅读与检索，再接 Docling/Paddle 做有证据的路由决策。

本轮没有修改业务代码或服务配置，也未运行候选解析器准确率比较。上文中“采用”表示方案决策，“候选”表示待实现/待评测，不构成已交付功能声明。
