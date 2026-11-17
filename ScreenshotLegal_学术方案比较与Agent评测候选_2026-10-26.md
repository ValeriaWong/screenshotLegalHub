# ScreenshotLegal：前沿学术方案比较、Agent 评测候选与批判性研究设计

> **Research review / Benchmark candidate registry · v1.0 · 2026-10-26**  
> 研究对象：已完成论文 `ScreenshotLegalBench + 结构感知微信证据抽取 + ComplexEvidenceSociety`，以及后续拟建设的 `ScreenshotLegal Product v1.1`（Evidence Core + Matter Pack + Legal Skills + Stage Runtime + ProofGraph + HITL）。  
> **文档性质：文献研究与实验设计，不是现有系统已达到的性能认证；引用论文的性能数字不得直接与本项目比较。**

## 摘要 / 核心判断

**可比较的研究问题不是“谁的 Agent 更多”，而是：在固定输入证据、底座模型、外部法律知识、token/时间预算之后，结构化法律要件、受控检索、验证/对抗及证据溯源是否真正改善了可审计法律分析。**

检索至 2026-10-26，近期最接近方案的论文是 **JurisMA（2026）**、**SCALE（2026）**、**Legal-R1（2026-10）**、**LegalReasoner（2025）**、**On Verifiable Legal Reasoning（2025）**、**VERDICT（2026）**、**AgentsCourt（2024）** 和 **L-MAD（2026）**。它们已经覆盖多 Agent、法律要素图、结构化先例、动态检索、规则推理或验证纠错等主题。因此，“使用多 Agent”以及“把法律知识组织成图”本身**不能**构成当前方案的新颖性主张。[L01][L04][L05][L07][L08][L09][L10][L11]

ScreenshotLegal 值得检验的组合差异是：**从截图原始像素/消息气泡到可定位 SourceRef，再映射案件事实、请求权要件、待证事实、举证责任、支持/反证、抗辩和审查记录**。这比仅从既有案情文本出发预测法条/裁判，或回答法律咨询，更强调**原始证据来源、双向关联、可修订性以及不确定性**。但“组合差异”不等于已经证明性能或学术原创性；需要专门消融与律师盲评。

最危险的研究设计错误包括：**将专家预先填写的要件/举证责任同时提供给模型又计入模型识别成绩；用更大 token 预算对比单 Agent；在同一模型生成的标注上用同一模型打分；把存在 citation 当作 citation 正确；把模型自信度当作司法证明力；把后续发表的论文写成原论文（2025）之前的先行工作。**

---

## 1. 证据基础、检索范围与可证性边界

### 1.1 三种来源必须分开

| 类型 | 依据 | 本文允许得出的结论 |
|---|---|---|
| **A：用户原始论文** | 用户上传《基于多模态信息融合的微信证据收集和处理方法研究》（2025 年毕业稿） | 曾设计约 5000 图文样本、4600+ KIE、1100+ VQA；结构感知抽取；ComplexEvidenceSociety 多模块流程；论文明确说策略与对抗等模块缺少系统性量化评估，多图排序不是重点。**以上是论文自述，不代表独立复现验证。** |
| **B：后续产品设计讨论** | 会话中已确定的 Product v1.1 目标规范 | `product_v1/` 非破坏式新实现、Matter/Skill 两个 Registry、CasePlan/ProofGraph、HITL、SSE、Source Viewer、Reviewer；**这是计划/规格，不是已经提交代码且验收通过。** |
| **C：外部论文** | 本文参考文献 [L]/[A]/[R]/[D]/[B]，优先 arXiv/ACL/NeurIPS/官方仓库 | 论文作者声称的方法/实验发现；与 ScreenshotLegal 的适配性是本文**推断**，必须单独测试。 |

**时间说明：**论文已在 2025 年完成；2025 年毕业之后或 2026 年发表的工作可作为**后续竞争研究和产品基线**，不能反向否认原论文在完成时的时间优先性。相反，当前产品也不能忽视 2026 年已公开的相近方法。

**范围说明：**“全部候选”限定为本次检索的可验证代表性候选清单，覆盖中文法律智能体/检索、证据溯源、多模态文档、长文档、通用编排和评测；不是全球论文穷尽清单。库/软件项目（Holmes、Docling、RAGFlow）与同行评议/预印本论文分栏处理。代码是否开源、模型权重是否可得、能否在本地运行，是三个不同问题；未实际复现的条目不能标为“已复现”。

### 1.2 研究任务细分

**T0 原始材料感知：** OCR、微信发言人、消息边界、时间归属、转账金额、bbox 与跨截图去重。  
**T1 证据归并：** 文档页/块、对话/事件、身份映射、检索、长文档局部读取及精确引用。  
**T2 事实与规范：** 请求权候选、Legal Element、Fact Proposition、举证责任及抗辩。  
**T3 证据论证：** 证据对待证事实的 supports / contradicts / context、证据缺口、争议点与来源支持。  
**T4 工作流：** 选择 Skill、阶段编排、动态工具、验证、反方对抗、必要人工确认。  
**T5 质量评估：** 严格溯源、逻辑一致性、专家认可度、成本/时延、稳定性、隐私。

---

## 2. 先合并共性：五个方法学家族，而不是三十套彼此独立的 Agent

| 家族 | 共同方法 | 代表文献 | 在当前方案里的自然接口 | 方法学陷阱 |
|---|---|---|---|---|
| **F1 法律结构先行** | Issues / Factors / Elements / Norms → 事实实例化 → 法律推理 | JurisMA、SCALE、形式化法律规则、事实到法律 KG、KG-IRAC | `MatterPack`、`CaseCompiler`、`FactProposition`、`ProofGraph` | 模板与 Gold 标签重合；手工规则覆盖测试集；跨法域移植造成伪类比 |
| **F2 检索驱动 + 证据约束** | 检索候选 → 查询改写/重排 → 证据充分性判断 → 引用答案 | Legal-R1、Self-RAG、CRAG、Legal-DC、LegalBench-RAG | `RetrievalPort`、`AuthorityPort`、`SourceRef`、`EvidenceLink` | 检索到相关段落不等于支持具体结论；法条时间有效性/权威性不一致 |
| **F3 验证/纠错/辩论** | 首稿 → 自评/过程验证/反方审查 → 修正 | LegalReasoner、VERDICT、AgentsCourt、L-MAD、Self-Refine、Reflexion | `strategy.verify`、`adversarial.analyze`、`ReviewGate` | 同源模型互相迎合、过度辩论、更多 token 才带来提升 |
| **F4 长文档分层阅读** | 按页/块寻址；层级摘要；局部工具阅读；跨段整合 | MinerU、RAPTOR、GraphReader、Chain-of-Agents、LongAgent、Hi-VT5 | `EvidenceDocument`、`SourceRef`、`ContextProjection`、`read(locator)` | 信息遗漏/摘要失真；跨块前后文消失；只用召回分数掩盖漏掉关键证据 |
| **F5 文档/视觉源数据理解** | OCR、布局、表格/块树、统一中间表示、可定位元素 | MinerU、PaddleOCR-VL、DocOwl2、olmOCR、dots.ocr | `PerceptionAdapter`、`EvidenceDocument`、`Conversation/Message` | 普通 document block 不代表微信消息、speaker 或截图重叠关系 |

**关键相交关系：** JurisMA、SCALE、Legal-R1 不是相互排斥的竞争产品：可以把它们拆成 `结构化要素层`、`检索策略`、`推理执行策略` 分别消融。把三者完整堆叠然后与单次回答比较，无法确定因果来源。

---

## 3. 与本系统最直接相关的法律方法论文（完整首选清单）

下表 `对标方式`：**直接**=可抽象为同任务配置；**改写**=需在我们的 case-schema、工具和证据集上重实现思想；**参考**=仅方法论参考。**未运行作者仓库，所有运行成本/复现状态待验证。**

| ID | 年 | 方案与正式来源 | 共性家族 | 与 ScreenshotLegal 的实质差别 | 对标方式 / 优先级 |
|---|---:|---|---|---|---|
| L01 | 2024 | **AgentsCourt** — 庭审辩论+法律检索+判决精炼；SimuCourt 中国裁判文书 [L01] | F3 | 输入主要为既成裁判/案情，终点是司法决策；我们的任务起于**未整理电子证据**，终点为**律师可审查举证矩阵** | **改写，P0**：法条检索+原被告辩论+校核 |
| L02 | 2024 | **LawLuo** — 接待/律师/秘书/评价者多轮咨询 [L02] | F3 | 咨询交互/报告，不是证据与待证事实绑定 | 参考，P2 |
| L03 | 2025 | **LawFlow** — 人类律师端到端可迭代工作流数据 [L03] | F1/F3 | 更关注流程行为、未聚焦微信原图；提醒固定 DAG 可能遗漏律师的往复修订 | **评测设计，P0**：迭代/回退场景 |
| L04 | 2025 | **LegalReasoner** — 争点分解、逐步验证与错误归因 [L04] | F1/F3 | 裁判预测/判决推理，并非原证据抽取 | **改写，P0**：独立 verifier 与反事实纠错 |
| L05 | 2025 | **On Verifiable Legal Reasoning** — 先形式化规范，再映射事实并符号执行 [L05] | F1 | 侧重法规/税法可执行规则；ProofGraph 尚不是完整规则演绎器 | **改写，P1**：规则引擎做可验证基线 |
| L06 | 2025 | **Capturing Legal Reasoning Paths from Facts to Law...** — 从日本判例抽取事实—规范推理图 [L06] | F1 | 主要从**已有判决文本**抽取推理图，我们从**原证据**自底向上构造 | **改写，P1**：图边准确性/规范溯源 |
| L07 | 2026 | **JurisMA / From Query to Counsel** — 法律要素图、动态多 Agent 路由、法条 grounding [L07] | F1/F2/F3 | 与 Matter+Skills 最接近；其主要输入是法律咨询问题、目标是咨询答复而非证明链 | **改写，P0**：element-graph planner |
| L08 | 2026 | **VERDICT** — 协同法庭 panel，draft–verify–revise、混合先例记忆 [L08] | F3 | 预测裁判/法条/量刑，且用历史纠错更新 memory；我们的事实与人工审查必须隔离于 benchmark | **改写，P1**：draft–verify–revise（禁用在线学习） |
| L09 | 2026 | **SCALE** — Issue–Factor Hierarchy 和 Case-Law Guide 定位先例 [L09] | F1/F2 | 针对先例分析，法律争点—factor 结构与请求权构成要件有交集但**不等价** | **改写，P0**：factor-aware retrieval |
| L10 | 2026 | **L-MAD** — 系统比较多 Agent 辩论拓扑/聚合 [L10] | F3 | 单任务法律文本蕴含；可控制辩论轮数测试过度争辩 | **直接思想消融，P0**：0/1/2/3 轮辩论 |
| L11 | 2026-10 | **Legal-R1** — 律师 Agent 主动选择法源/检索时机/停止，助理检索、裁决 Agent 回答 [L11] | F2/F3 | 侧重规范/判例来源，未解决聊天证据感知及举证映射；作者训练检索策略，不能用简单 prompt 冒充原方法 | **改写，P0**：动态检索政策；原训练版 P2 |
| L12 | 2026 | **Chatlaw (RA-MoE 版本)** — 法律助理/研究者/高级律师的角色对齐专家 [L12] | F3 | 角色路由+专门训练权重，并非可插拔 Manifest；版本/模型资产核实复杂 | 参考，P2 |
| L13 | 2026 | **KG-Assisted LLM Post-Training for Legal Reasoning** — IRAC 图辅助 SFT/DPO [L13] | F1 | 用结构化法律知识训练权重；我们的知识主要外置版本化 YAML，避免训练开销 | 参考，P2；检验外置/内化区别 |
| L14 | 2026 | **Legal-DC / LegRAG** — 中文法条按条款分段、双路径反思检索 [L14] | F2 | 偏法规/合同管理类问答，对真实诉讼原证据无专门约束 | **改写，P1**：条款级 authority retrieval |
| L15 | 2025/26 | **Legal RAG Bench** — 司法 RAG 检索与推理误差分解 [B06] | F2 | 是评测框架/数据集，不是 Agent 框架；可借因子实验设计 | **评测协议，P0** |
| L16 | 2026 | **COLIEE 2025 多阶段系统族** — BM25→embedding/reranking→蕴含判断 [B09] | F2 | 以判例和法条蕴含为目标，较少处理屏幕图像及 proof burden | **改写，P1**：最强非 Agent RAG 基线 |

**特别提醒：** L07、L09、L11 是当前方案最需要正面讨论的三篇：其分别挑战 `Matter schema 新颖性`、`基于法律因素检索的新颖性` 和 `Agentic retrieval 新颖性`。其中没有一篇根据摘要已验证“截图→发言人/消息→待证事实→举证责任→人工审查”的完整链路；这是尚待实验支撑的差异，而不是已证明的胜出点。

---

## 4. 通用 Agent、记忆、检索、长文本论文（分家族候选清单）

### 4.1 工作流/Agent 控制变量候选

| ID | 方案 | 可以复现的机制 | 与当前方案差异 | 分类 |
|---|---|---|---|---|
| A01 | **ReAct** [A01] | 按观察选择 search/read/verify 工具；可记动作日志 | 无固定法律要素模板，动态但结果不一定更有法律效力 | **单 Agent 强基线，P0** |
| A02 | **Self-Refine** [A02] | 同模型生成→反馈→改写；限制轮数 | 不要求多个 Agent；检验复杂协作是否必要 | **强基线，P0** |
| A03 | **Reflexion** [A03] | 失败反馈进入短期反思记忆，重试 | 多轮案例记忆易产生跨集污染 | P1，仅运行内局部 memory |
| A04 | **MetaGPT** [A04] | SOP、角色规范、阶段交付物 | 最初面向软件工程；不等同法律完整推理 | P1，SOP baseline |
| A05 | **LongAgent** [A05] | leader 切文档给多个 reader、交叉消解 | 适合长文书，不适合仅十几条消息的轻案 | P1（长案） |
| A06 | **Chain-of-Agents** [A06] | 分块 worker 顺序读+manager 汇总 | 顺序摘要可能漏掉反证 | **P0（长案）** |
| A07 | **GraphReader** [A07] | 分层 graph index + tool read 邻居 | 图结构用于检索，不等于 ProofGraph 法律证明关系 | **P1（长案）** |
| A08 | **Towards a Science of Scaling Agent Systems** [A08] | 固定模型/工具/预算比较 Single、Independent、Centralized、Decentralized、Hybrid | 它是多任务编排比较而非法律产品 | **必读评测设计，P0** |
| A09 | **On Scalable Oversight with Weak LLMs Judging Strong LLMs** [A09] | debate vs consultancy vs direct QA、信息对称控制 | 反方辩论可能只是说服 judge，而不是更准确 | **批判性基线，P1** |

### 4.2 检索/图/引用候选

| ID | 方案 | 可直接抽象的改变 | 适合的实验 | 分类 |
|---|---|---|---|---|
| R01 | **Self-RAG** [R01] | 检索/引用/自我评价 token 控制 | **真实 Self-RAG** 依赖训练；prompt-only 只能称 inspired | P1（训练条件） |
| R02 | **CRAG** [R02] | 检索结果质量门控/修正 | 在错误法规、低相关片段下的鲁棒性 | **P0（轻量改写）** |
| R03 | **RAPTOR** [R03] | 层级聚类摘要树 | 多文书长卷宗全局/局部问题 | **P1** |
| R04 | **GraphRAG** [R04] | 实体社区图+社区摘要用于全局语义 | 全案争议主题、多人物关系；附加成本高 | P2 |
| R05 | **LightRAG** [R05] | 低/高层图检索+增量更新 | 增量证据、关系查询，证据必须回源 | **P1** |
| R06 | **Legal-R1** [L11] | 法源类型与检索停止策略 | 动态 vs 固定 top-k 法律检索 | **P0 思想改写** |
| R07 | **Legal-DC / LegRAG** [L14] | 按法条边界 chunk、反思检索 | 中国法规的跨版本/条款粒度 | P1 |

**对比关键：** 一张 `ProofGraph` 可以用于生成证据矩阵，一张 `GraphRAG` 图用于检索文档；二者不能因为都叫 Graph 就直接互换。前者边应表达 `support / contradict / burden / derived_from` 的可审计语义，后者通常是实体共现或摘要社区关系。

---

## 5. 多模态文档、OCR 与长文档论文：作为感知层/长文档子评测，不全部参与 Agent 排名

| ID | 论文/系统 | 核心思想 | 适合材料 | 对截图法律证据的限制 | 建议 |
|---|---|---|---|---|---|
| D01 | **MinerU** [D01] | 版面/OCR/公式/表格+确定性后处理；当前 4.x 代码另含 doclib 缓存、locator、progressive reading | PDF、扫描卷宗、合同、论文 | 普通 block 不知道微信 speaker、聊天重叠、转账 UI | **文档 Adapter + 代码设计参考，P0** |
| D02 | **PaddleOCR-VL** [D02] | 小型 VLM 多语种文档解析 | 中文 OCR/合同/复杂表格 | 非微信对话专用 | **解析候选，P0** |
| D03 | **mPLUG-DocOwl2** [D03] | 压缩高分辨率多页视觉 token | 多页裁判、跨页材料 | 无法律规则/出处证明力 | P1 |
| D04 | **olmOCR** [D04] | VLM PDF → 按阅读顺序的结构化文本 | 大量 PDF | 可能损失 UI 交互结构 | P1 |
| D05 | **dots.ocr** [D05] | 统一 VLM 完成布局/文本/关系解析 | 多语言扫描件 | 不处理法律角色绑定 | P1 |
| D06 | **Hi-VT5 / MP-DocVQA** [D06] | 多页层级页摘要 + page answer provenance | 多页 VQA | 无案件要件链 | **长文档 baseline，P1** |
| D07 | **Self-Attention Scoring MP-DocVQA** [D07] | 先从海量页中筛相关页再问答 | 300–800 页查证 | page 级而不是消息/字符级来源 | P1 |
| D08 | **PureDocBench** [D08] | 可回溯合成源的 clean/degraded/real-degraded 解析评测 | 低质扫描、噪声/模糊 | 不是法律模型 | **评测方法 P0** |
| D09 | **OmniDocBench** [D09] | 多格式解析质量与布局/元素指标 | 解析赛道外部对齐 | 已有公开集可能污染；不能代表微信 | **评测基准，P1** |
| D10 | **MMLongBench-Doc** [B10] | 跨页、多种证据载体、不可回答样本 | 长文档多模态 QA | 非中国法律证明责任 | **长案评测设计，P0** |
| D11 | **MMLongBench-Doc-V2** [B11] | 校正问题答案与语义评估，重审旧分数 | 衡量评测标签噪声 | v1/v2 结果不能混比 | **评测反例，P0** |

**软件工程参考而非论文 Agent 候选：** `Docling`（typed `DoclingDocument`/provenance）；`MinerU 4.x doclib`（SHA256、page/block/char locator、段续读）；`PaddleOCR/PP-StructureV3`（工程流水线）；`RAGFlow/DeepDoc`（parser adapter/chunk/index）；`Holmes`（staged backend、HITL、SSE、DetailRail/Citation 导航）。它们应进入 `perception_adapters` 或 UI/系统 architecture comparison，**不应参加同一个“Agent 决策准确率”排行榜**。

---

## 6. 数据集、评测框架与质量指标论文（不是 Agent 结构）

| ID | 名称 | 主要覆盖 | 可借鉴的评测维度 | 迁移局限 |
|---|---|---|---|---|
| B01 | **LegalAgentBench** [B01] | 中国法律工具使用 Agent，17 法律语料与 37 工具 | 工具使用成功率、过程进度、错误动作 | 无微信截图定位/请求权矩阵 GT |
| B02 | **LawBench** [B02] | 中国法律 20 项知识/理解/应用任务 | 法律知识与应用能力分层 | 文本题≠诉讼证据工作流 |
| B03 | **LexEval** [B03] | 中文 23 类法律任务、伦理 | 法律能力/伦理/生成分项 | 不直接检验 source-grounded proof |
| B04 | **LegalBench** [B04] | 英语法律推理多任务 | 推理能力分类、专家题设计 | 法域/语言不同 |
| B05 | **LegalBench-RAG** [B05] | 法律检索需要的最小精确片段 | snippet Recall/Precision、超长 chunk 惩罚 | 英语/法规合同等，不含聊天证据 |
| B06 | **Legal RAG Bench** [B06] | 检索×生成因子设计、错误分解 | 判断“错误来自检索还是推理” | 英澳法域数据，不可直接当中国法答案 |
| B07 | **Reasoning-Focused Legal Retrieval** [B07] | 真实法律研究检索与答案 | 具有推理难度的检索 Gold | 法域/任务不同 |
| B08 | **Legal-DC** [L14] | 中文法条级 RAG 数据与方法 | clause-level authority correctness | 不等于待证事实举证责任 |
| B09 | **COLIEE 2025** [B09] | 判例检索、蕴含、法条检索/蕴含、侵权预测 | legal entailment、case retrieval、诉辩论据 | 加/日等法域/任务限制 |
| B10 | **MMLongBench-Doc** [B10] | 多页多模态和不可回答 QA | cross-page、abstention | 非法律专用 |
| B11 | **MMLongBench-Doc-V2** [B11] | 修正标注/评价方式 | ground truth 版本和 annotation audit | 自身也是新预印本成果，需复查 |
| B12 | **OmniDocBench** [D09] | OCR/layout/table 检验 | 文档 perception 子赛道 | 不检查 speaker/message |
| B13 | **PureDocBench** [D08] | 真实退化/可溯源合成 | 对噪声、压缩、模糊的鲁棒性 | 合成退化难覆盖微信全部异常 |
| B14 | **ALCE** [B14] | 带引用生成 | citation precision/recall、答案正确性 | 引文正确不代表举证责任正确 |
| B15 | **RAGChecker** [B15] | RAG 的 retrieval/generation 细粒度诊断 | hallucination / retrieval 分开估计 | 评估模型也会错误 |
| B16 | **FActScore** [B16] | 将长输出拆成 atomic facts | 无支持结论率、支持核验 | 法律规范推论非单纯事实陈述 |
| B17 | **LAR-ECHR** [B17] | 法庭论证链的下一步推断 | legal argument continuation | 欧洲人权法院情境不同 |
| B18 | **LawFlow** [L03] | 人类律师可迭代任务工作流 | 人工介入点/回退路径/非线性流程 | 企业设立不是民间借贷纠纷 |

**评测文献的负面教训：** 文档基准本身会有标签错误与版本漂移；评估模型与人工之间可能低一致；同一论文不同版本样本规模/分数可能变化。必须版本锁定数据集、评分器与标注规范，报告 IAA/仲裁结果，而不是只画模型排名图。[B11][L09][D08]

---

## 7. ScreenshotLegal 与前沿方案的实质差异（逐维度、不夸大）

| 核心维度 | 当前目标设计 | 最接近研究 | 真正不同之处 | 是否已证明优势 |
|---|---|---|---|---|
| 输入来源 | 微信截图、连续多图、PDF/表格扩展 | MinerU/DocOwl2/Paddle；AgentsCourt 使用案情 | **聊天 UI 发言人/消息/时间/转账语义** 与法律证据一起建模 | **否**：需对照通用 parser |
| 法律知识 | 人工版本化 Matter Pack | JurisMA element graph、SCALE factor hierarchy、形式化法条 KG | 对请求权、要件、待证事项、举证责任、抗辩进行分别建模 | **否**：本体质量/覆盖率待审 |
| 执行 | Skill registry + staged DAG + HITL | AgentsCourt、VERDICT、JurisMA | Agent 可替换，知识在 Matter 而非 Agent prompt | **否**：稳定性/灵活性需测 |
| 检索 | 来源引用与法律 authority 双重检索 | Legal-R1、LegalBench-RAG、SCALE | 双轨区分“案内事实证据”和“案外规范来源” | **否**：需计入检索错误 |
| 事实与证明 | Fact→Element→Claim、support/contradict/gap | 事实—法律 KG、IRAC-KG、SCALE | 将证据链接到待证命题，明确反证与举证责任 | **否**：精度未测 |
| 验证 | strategy.verify/adversarial/ReviewGate | LegalReasoner、L-MAD、VERDICT | 验证可绑定具体证据和原件坐标；中途可人工确认 | **否**：对抗是否有益待测 |
| UI | Proof Matrix + Source Viewer bbox + Review 审计 | Holmes UI（工程项目） | 围绕法律证明责任组织工作台，而非调查情报中心 | 工程特性；**不能作为论文推理 SOTA** |
| 评测 | ScreenshotLegalBench + 预拟分层基准 | LegalAgentBench、LawBench、MMLongBench、ALCE | 可测试从像素到诉讼主张全链路传播误差 | **仍缺**案例级规范 Gold |

**谨慎表述“贡献”：** 推荐声称“提出并评测一种面向微信截图的、可溯源与人工审查的法律证据工作流框架”，而非“首个多模态法律 Agent”或“首个 Legal Proof Graph”。要通过检索更新后再确认任何“首个”。

---

## 8. 可执行 Agent 评测候选：用‘基线族’而非‘每篇论文都重新实现’

**所有方法统一运行在同一 `EvaluationHarness`**：固定 test cases、`Evidence Core` 版本、可用 Matter Pack、已验证 Authority corpus、底座模型与 decoding、时间/token/$预算；输出共同的 `FactProposition / EvidenceLink / Burden / Claim / StrategyItem / SourceRef / Audit`。必须记录某候选是 `faithful_reproduction`、`paper_inspired_reimplementation` 还是 `ours_implementation`。

| 候选ID | 配置 | 参照论文 | 核心变量 | 优先 |
|---|---|---|---|---|
| **E00** | Single-shot direct legal answer | 基础强基线 | 不用结构模板、不拆 Skill，单模型一次作答 | **P0** |
| **E01** | Single agent + 相同 retrieval tools | ReAct | 动态工具，但没有多角色 | **P0** |
| **E02** | Fixed staged workflow, no Matter Pack | SOP/MetaGPT 线索 | 固定阶段而非即兴角色 | **P0** |
| **E03** | E02 + Matter Pack schema | JurisMA/SCALE/本项目 | 测“外显请求权/要件知识”的净贡献 | **P0** |
| **E04** | E03 + deterministic rules verifier | 形式化法律推理 | 规则约束/时间生效校验 | **P1** |
| **E05** | E03 + Self-Refine verifier | Self-Refine | 同 Agent 自校核，非多 Agent | **P0** |
| **E06** | E03 + independent verifier | LegalReasoner / VERDICT | 独立检查 factual/legal grounding | **P0** |
| **E07** | E03 + plaintiff/defendant adversarial | AgentsCourt / L-MAD | 1轮对抗、相同总预算 | **P0** |
| **E08** | E07 + judge aggregation | AgentsCourt / L-MAD | 是否真的需要中立第三角色 | **P0** |
| **E09** | E07 改 0/1/2/3 rounds | L-MAD | 观察过度辩论与 token 成本 | **P0** |
| **E10** | E03 + rule-/factor-aware retrieval | SCALE / Legal-DC | 法律要件驱动检索 | **P0** |
| **E11** | E03 + agentic legal search/stop | Legal-R1 | 动态 source routing + sufficiency | **P0 改写版** |
| **E12** | E03 + CRAG gating | CRAG | 检索错误时自我修正 | **P1** |
| **E13** | E03 + GraphReader | GraphReader | 长证据阅读规划（固定图抽取） | **P1** |
| **E14** | E03 + Chain-of-Agents | CoA | 长卷宗分块连续汇总 | **P1** |
| **E15** | E03 + RAPTOR | RAPTOR | 分层摘要/树检索 | **P1** |
| **E16** | E03 + LightRAG | LightRAG | 增量 graph-based retrieval | **P1** |
| **E17** | E03 + human-review gates | LawFlow / HITL | 人工干预能否降低严重错误、代价是多少 | **P1** |
| **E18** | JurisMA-like dynamic task routing | JurisMA | 固定技能下 planner 自由规划 | **P1** |
| **E19** | SCALE-like Issue–Factor planner | SCALE | 因素层级 vs 请求权要件层级 | **P1** |
| **E20** | VERDICT-like draft–verify–revise | VERDICT | 草稿/规则审查/再写 | **P1** |

**复现真实性判定：** E07 ≠ 复现 AgentsCourt（只借了辩论机制）；E11 ≠ 原始 Legal-R1（原论文训练了检索策略）；E19 ≠ 完整 SCALE（除非具有相应先例指南/因子库）。在论文中必须写 `...-inspired baseline`，禁止“重现 SOTA 方法”式命名误导。

### 8.1 不同轴必须独立测（避免全笛卡尔积）

- **感知轴 P：** `raw-image`、`generic OCR`、`MinerU`、`PaddleOCR-VL`、`WeChat-structured`、`gold-perception`。只用于 T0–T3；其他变量固定。
- **检索轴 R：** `BM25`、`BM25+reranker`、`legal-element query expansion`、`Legal-R1-inspired dynamic`、`RAPTOR / GraphReader`。固定 perception gold 和 reasoning。
- **编排轴 E：** E00–E12（第一阶段只做 E00/E01/E03/E05/E06/E07/E08/E09/E10/E11）；固定感知/检索。
- **结构轴 S：** `no schema`、`retrieved rule text`、`Matter Pack`、`Matter Pack + BurdenRule`、`Matter Pack + Human Review`。

**禁止**把 P×R×E×S 全部组合（几十到数千实验），先做有明确研究假设的 block-controlled 对比。

---

## 9. Ground Truth 应如何标注：纠正当前设计的主要科学风险

现有 ScreenshotLegalBench 主要是截图与结构化/KIE/VQA；论文自身指出策略生成、对抗模块缺少系统化量化，多图时序重构也不是评估重点。所以不可以直接把历史 1100+ VQA 当作全部 Agent 评测 Gold。需要新增**案例级注释**。

### 9.1 CaseGold 最小可用模式

```yaml
case_id: gold_case_001
case_group_id: same_underlying_dispute_01
jurisdiction: CN
law_effective_date: '2024-01-01'
evidence_refs:
  - evidence_id: img_01
    sha256: '<file hash>'
    source_type: wechat_screenshot
    gt_messages:
      - message_id: m01
        speaker: party_A
        bbox_px: [100, 140, 450, 220]
        quote: '下月底还你五万'
claims:
  - claim_id: c01
    claim_template_id: repayment_principal
    applicability: plausible
    element_gold:
      - element_template_id: agreement
        fact_ids: [f01]
        expected_burden_role: claimant
facts:
  - id: f01
    proposition: '双方就五万元形成借贷合意'
    support: [m01]
    contradict: []
    verdict: supported_with_reservations
    ambiguity_note: '仅有承诺字样，不足以单独确认交付'
authorities:
  - authority_ref: '<expert-verified id>'
review:
  annotation_status: adjudicated
  annotator_roles: ['legal_expert_A', 'legal_expert_B']
  agreement_measure: '<IAA metric>'
```

`bbox` 原图像素、parser 原始坐标及转换参数均需存；`claim_template_id` 是 Matter schema 里的模板标识，**不等于案件中实际成立**。Proof matrix 不能只统计“字段填满率”。

### 9.2 双盲与泄漏控制

1. **训练/测试以 underlying case group 分组**：同一聊天多截图、同一判决不同页、轻微改写、同一典型案例不得跨 split；检测图像近重复与文本近重复。
2. **专家 Gold 不得从同一个模型生成后立即拿同模型评审**；至少双人标注，分歧仲裁，报告一致性和“无法判断”比例。
3. Matter Pack 只能从**独立规则来源**制作；不得读取 test-case 的 Gold `fact_ids`/`burden` 后写到 Pack。
4. 比较“是否有 schema”时，区分**系统提供的法律知识**与**模型自主发现的能力**：已提供的 burden_rule 不可再计入 model burden inference 的 accuracy。
5. 所有法律法源按 `law_effective_date` 和审理时间语义明确筛选，历史条文不能被 2026 新版本静默替代。
6. 法律判例/“典型案例”区分 `normative_authority`、`persuasive_precedent`、`case_pattern`，权重不同，不能都标 authoritative。
7. 如引用真实个人微信，必须有合法授权、脱敏、访问日志和不可反推的分组标识；评测集优先合成并专家复核。

### 9.3 需要专门添加的失败类样本

`negated_promise`（“我没说借你钱”）；`quote_misattributed`（引用内容属于另一发言人）；`screenshot_overlap`；`missing_timestamp`；`ambiguous_account_identity`；`transfer_not_loan`（投资/赠与/货款）；`partial_repayment`；`cash_repayment_defense`；`fabricated_message_claim`；`outdated_statute`；`irrelevant_precedent`；`insufficient_evidence`；`unanswerable`；`conflicting_amounts`；`different_original_files_same_name`；`bbox_misalignment`；`noisy_scanned_attachment`。

---

## 10. 统一评测协议（Codex 可以照此实现）

### 10.1 评测单位

| Track | 输入固定 | 主要输出 | 主指标 | 必要细分 |
|---|---|---|---|---|
| **V-Perception** | 图片+专家框 | speaker、msg、时间、bbox、实体 | speaker F1、message alignment F1、timestamp accuracy、bbox IoU、OCR CER | 转账、表情、相似头像、截图重叠 |
| **D-Document** | PDF/合同/流水 | page/block/text/table/source anchor | block/page F1、reading order、table cell F1、anchor hit rate | native vs scan、长页、旋转、模糊 |
| **E-Evidence Retrieval** | Gold事实问题+冻结证据库 | source passages/msgs | Recall@k、nDCG、minimal snippet precision、no-evidence abstention | 相关 vs 真正支持、跨页/跨图 |
| **L-Legal Structure** | Gold事实+锁定规范库 | Claim、Element、Fact、Burden、Defense | macro-F1、element coverage、burden accuracy | 多请求权、抗辩/例外、不确定性 |
| **G-Proof Grounding** | 冻结 Fact+Evidence | links/gaps/contradictions | evidence-link P/R/F1、support correctness、quote exact match、unsupported claim rate | 正反证双向、citation non-entailment |
| **A-Agent Workflow** | Frozen inputs, tools, model | strategy、trace、Review | 专家成对偏好、severe error rate、progress/step validity | 预算/中止/重试/对抗反效果 |
| **S-System** | 模拟上传、断线、二次分析 | 审计/回放/文件链接 | source open hit rate、replay consistency、p95 latency、$/case | 隐私/哈希/权限/人工修订 stale |

### 10.2 法律特有失败等级

- **Critical**：捏造法律依据；错认当事人身份/证据来源；把反证当支持；把明显不确定命题当成立；泄漏机密证据。
- **Major**：遗漏关键抗辩；错配请求权要件或举证责任；引用真实但不蕴含结论；忽略已发生部分还款。
- **Minor**：次要术语不规范、可修复的排序/表达问题。

报告必须同时列 `critical/major/minor errors per case`、`abstention quality` 和 `human correction time`。ROUGE/语义相似度只可做辅助。Proof strength 建议使用经过定义的 `weak/medium/strong/unknown` 人类评审标签，**不使用 0.82 作为法律上的胜诉或证明力概率**。

### 10.3 严格的对照运行

```yaml
evaluation:
  benchmark_version: 1.0.0
  case_group_split: heldout_cases_v1
  gold_visibility: evaluation_only
  freeze:
    perception_snapshot: gold_or_fixed_parser_digest
    legal_corpus_digest: '<sha256>'
    matterpack_digest: '<sha256>'
    tools_available: [case_search, source_read, authority_search]
    base_model: '<same pinned model revision>'
    decoding: {temperature: 0, top_p: 1}
  budgets:
    total_llm_input_tokens: 50000
    total_llm_output_tokens: 10000
    max_tool_calls: 20
    max_wall_time_s: 180
  methods: [E00, E01, E03, E05, E06, E07, E08, E09, E10, E11]
  repeats: 3
  metrics: [claim_f1, element_coverage, burden_accuracy, evidence_link_f1,
            citation_support_accuracy, unsupported_claim_rate,
            critical_error_rate, human_review_time, latency, total_tokens]
```

**预算解释：**以上数字只是待预注册的示例阈值，必须按模型/硬件试验校准后冻结。`temperature=0` 并不能保证后端完全确定性；重复实验需要储存每次真实响应、模型返回标识和随机 seed（如可用）。

### 10.4 防止“多 Agent 靠更多算力赢”的两个报告视角

- **Equal budget**：所有候选的总模型调用 tokens/工具数/延迟预算相同；主结论采用这个视角。
- **Equal performance target**：达到同一 citation support / expert score 所需成本；考察性价比。

每一表报告 `quality ± bootstrap CI`、`tokens`、`wall time`、`cost`、`failure rate`。小样本/高方差时不得宣称统计显著优胜。推荐 case-level bootstrap 而不是 message-level bootstrap，以免同案多消息误作独立样本。

---

## 11. 最少需要跑的研究矩阵、假设与拒绝条件

| RQ | 主要假设 | 必跑对比 | 可能否定该假设的情况 |
|---|---|---|---|
| **RQ1 感知结构** | Speaker/message 对齐比通用 OCR 更能改善法律证据映射 | P:`genericOCR vs WeChatStructured vs gold`；固定 E03 | OCR 少错但人物归属无变化，法律 F1 不升 |
| **RQ2 Matter Pack** | 外置要件/举证规则减少遗漏 | E02 vs E03；同法源信息预算 | 模板泄漏、召回升但误判也升、仅命中预设案由 |
| **RQ3 Source-grounding** | 强制 source links 减少无证据陈述 | E03 without citation validation vs +grounding validator | 引用率升、citation support precision 不升 |
| **RQ4 多 Agent 的净增益** | verifier/adversary 减严重错误 | E03、E05、E06、E07、E08、E09 | token 增加后优势消失，过度辩论恶化 |
| **RQ5 动态检索** | source-type-aware retrieval 比固定 BM25 更充分且高效 | fixed BM25 vs E10/E11；固定 P/Pack | 检索调用增大，但关键 snippet recall 不升 |
| **RQ6 长卷宗** | 分层阅读保持证据覆盖而降低上下文成本 | full-context vs CoA vs GraphReader vs RAPTOR | 摘要丢失反证、引用错误、耗时更长 |
| **RQ7 人机协作** | 人工 Gate 降低 critical error | E03 vs E17；记录审核时间 | 专家只能覆盖不重要信息，成本过高 |

**最低优先执行集（资源有限）：** `E00 E01 E03 E05 E06 E07 E08 E09 E10 E11` + 2 个 perception 比较 + 1 个 long-document 比较。之后再决定是否值得运行模型训练型 Self-RAG/Legal-R1 原版，以及大规模 GraphRAG。

---

## 12. 面向当前 Product v1.1 的技术变更清单

### 12.1 不要引入第二个“万能法律大模型服务”

保留 `MatterRegistry + SkillRegistry + CaseCompiler + StageRuntime + ProofGraph`，增补三个小接口：

```python
class SourceReaderPort(Protocol):
    async def read(self, source_ref: str, *, context: int = 0,
                   max_chars: int = 30000) -> 'SourceChunk': ...

class AuthoritySearchPort(Protocol):
    async def search(self, query: str, *, effective_date: str,
                     source_types: list[str]) -> list['AuthorityHit']: ...

class EvaluationAgentAdapter(Protocol):
    async def run(self, case: 'FrozenCaseInput',
                  budget: 'EvaluationBudget') -> 'CaseAnalysisOutput': ...
```

**关键补充：** `SourceRef` 分清 `primary_case_evidence` 与 `legal_authority`；`source_sha256`、`parser_revision`、`page_no`、`block_id`、`message_id`、`bbox_coordinate_space`、`quote_start/end`、`review_status` 必须能核验。MinerU 的 `doc:{hash}/tier:{tier}/page:{n}/block:{n}` 可存为 `external_locator`，但**不能把 tier-dependent block 序号当作独立于 parser 的永久稳定主键**。应以本产品 EvidenceID + parse_run_id + local anchor 映射。

### 12.2 增设可机读 Candidate Registry

建议文件：

```text
product_v1/benchmark/
  candidates.yaml
  paper_registry.yaml
  adapters/
    baseline_single.py
    baseline_react.py
    baseline_workflow.py
    verifier_selfrefine.py
    verifier_independent.py
    debate_agent.py
    retrieval_factor.py
    retrieval_dynamic.py
  eval/
    evaluation_protocol.py
    citation_support.py
    legal_elements.py
    budget_tracker.py
    report.py
```

**注意：**这是产品试验期间的本地轻量 harness 结构示意。正式 `ScreenshotLegalBench` 仓库仍负责数据、评测器与 leaderboard；当前新产品只暴露调用 API/插拔运行策略，不允许把正式 benchmark hardcode 进产品服务层。

### 12.3 新增 reviewer gates

- `matter_pack_expert_review`: 未审核 Matter Pack 必须显示草稿；不得作为权威法律咨询默认输出。
- `evidence_link_validation`: EvidenceLink 必须通过 `source exists`、quote 匹配、有效 bbox/schema 检查；再由 NLI/专家检验“是否蕴含”。
- `burden_rule_exception_review`: 抗辩、举证责任倒置/法定例外等特殊情况单独建模。
- `run_staleness`: parser/Matter/authority/skill digest 任一更改，应对受影响的派生结论标 `stale` 而非静默复用 review。

---

## 13. 批判性综合：当前设计最大价值、弱点、风险与行动优先级

### 13.1 价值（有待证伪的研究假说）

1. **证据到法律要件的“可追责中间层”**：相较法律咨询 Agent，能指出每条结论来自哪个截图气泡、什么位置、支持或反对哪个命题。
2. **外置、可审查、可版本化的法律知识**：比将要件与举证规则散落各 Agent prompt 更易审核、更可测试、更适合变更。
3. **可控运行时与研究设计天然相容**：能力 manifest、案例快照与 Run digest 让消融较易实现。
4. **适合做人机协作，而非替代裁判**：人工可修改法律知识级和案件事实级两类对象。

### 13.2 四个根本弱点

**(a) 证据层还有实质错误传播风险。** 微信截图的发言人归属错误，可能让后续要件、风险、策略全错；仅在最终答案加 citation 无法纠正前段错认。应做逐层 oracle substitution（把前段换成 Gold）计算误差传播。

**(b) Matter Pack 初版可能成为封闭世界。** 已知民间借贷四要件并不意味着总能涵盖关联的其他请求权、抗辩、多个诉讼请求、诉讼时效、部分还款、无权代理等；先保证“多候选/不适用/专家补充”，而不是把所有输入强塞到 `private_lending` 模板。

**(c) 多 Agent 的“逼真感”可能掩盖独立验证缺失。** 同底模扮演原告/被告/法官容易产生相关性错误；L-MAD 等已有过度协作警示。[L10][A08] 应优先引入真正独立的 source-checker、法条版本检查和规则约束，再考虑增加角色数。

**(d) 缺少能支持论文强结论的案例级 Gold。** 历史截图标注充分不等于完成“请求权/举证责任/反证/严重失误”的专业评审；需要法学专家双盲和仲裁预算。该点比增加 10 个 Skill 更优先。

### 13.3 最大风险表

| 风险 | 触发情形 | 可观察预警 | 缓解 | 余留风险 |
|---|---|---|---|---|
| **R1 法律规则过时** | Matter Pack 法条随司法解释变动 | 引文过期/生效日错配 | Authority manifest 有 effective dates + 审核签名 | 地域/程序规则仍复杂 |
| **R2 错配举证责任** | 抗辩与构成要件未分清 | burden accuracy 掉、重大误导 | 主张/抗辩分开建模；专家审查 | 模糊争点无法单一 Gold |
| **R3 假引用** | 引用真实段落但不支持结论 | quote match 高但 entailment 低 | citation evidence NLI + expert sample | NLI 也可能错 |
| **R4 洗入虚构事实** | 多 Agent 摘要把推断说成事实 | unsupported claim rate 升 | raw fact/source 双轨、summary 可回溯 | 语言含混 |
| **R5 反方辩论污染** | 对抗双方共享错误前提 | 对抗轮数越多得分越低 | 固定轮数+独立证据复查 | 同底模相关偏差 |
| **R6 训练/评测泄漏** | 多截图同案跨 split | 重复样本上成绩过高 | case-group split、perceptual hash | 隐性外部训练污染 |
| **R7 不公平成本** | 多 Agent token 翻几倍 | 准确率升、效率大降 | equal-budget 主结果、Pareto | 不同 API 计费偏差 |
| **R8 人工知识主导成绩** | Gold 要件已放入 Matter | 要件 F1 假满分 | knowledge-provided vs model-inferred 分轨计分 | 专家制作 Pack 成本高 |
| **R9 索引/源定位失效** | 重新解析 PDF 改了 block ID | 点击引用错页/错框 | source_sha + parse_run + anchor map | 图像渲染差异 |
| **R10 模型外送隐私** | 法律截图未经授权被发送 | 出站请求/日志敏感数据 | 本地默认/显式授权/出口日志/脱敏 | 第三方留存政策 |

### 13.4 研究实施建议（先后次序）

**第 1 阶段：不是写新 Agent，而是审计 Gold 与 schema。** 选约 50–100 个相互独立的案件组，按请求权/抗辩/证据链制作高质量人工 Gold；加入无充分证据的负例和可拒答任务。统计专家分歧。

**第 2 阶段：先跑最强简单模型。** `single-shot + evidence`、`single-agent ReAct`、`fixed staged workflow`、`Matter+workflow` 与 `Self-Refine`，优先检验结构而非规模。

**第 3 阶段：只有在基础流程可靠时，比较 verifier/adversarial。** 尤其报告 E07/E08/E09 在 severe error 与预算上的双向变化；如果无净增益，就不要在生产默认开启多角色辩论。

**第 4 阶段：增加动态检索与长案。** 对比 `fixed BM25`、`factor-aware`、`agentic search`、`read(locator)`、`Chain-of-Agents`；检验漏读反证、断点续读与回源精度。

**第 5 阶段：审查用户受益。** 与人工对照记录每案所需时间、审核量、危险遗漏、引用检查时间；证明“辅助律师整理证据”而不是只证明模型会写漂亮诉讼文本。

### 13.5 最终结论（保留可反驳性）

ScreenshotLegal 的潜在优势不是“一个最强通用法律 Agent”，而是一个可被拆开测量的**源证据驱动、法律知识显式化、过程可审查的民事证据工作台**。它可吸收 JurisMA 的要素分解、SCALE 的 factor 检索、Legal-R1 的动态信息搜集、LegalReasoner 的过程纠错、MinerU 的 locator 渐进阅读，但不能把这些机制全部堆叠后便声称创新或性能提升。最终应基于**有约束的同预算消融、可定位证据的真支持率、专家严重错误评分和人机工作效率**决定哪些能力留下。

**如果 E03（Matter + 固定流程）在同预算下不优于 E01（ReAct 单 Agent），则复杂框架的合理性首先受到挑战；如果 E07/E08（对抗/裁决）不降低严重错误，就应把它们留在可选的 Advanced；如果通用 OCR 与微信结构化感知在下游结果无显著差异，需重新审视专用截图模型的产品边际价值。** 这样的反证条款应提前写入实验方案，避免结果导向选择。

---

## 14. 已核实来源清单（每个条目均带论文入口；链接为 2026-10-26 本次检索确认）

### 14.1 法律任务/结构化推理论文

- **[L01]** He et al. (2024), *AgentsCourt: Building Judicial Decision-Making Agents with Court Debate Simulation and Legal Knowledge Augmentation*. EMNLP Findings. https://arxiv.org/abs/2403.02959
- **[L02]** Sun et al. (2024), *LawLuo: A Multi-Agent Collaborative Framework for Multi-Round Chinese Legal Consultation*. https://arxiv.org/abs/2407.16252
- **[L03]** Das et al. (2025), *LawFlow: Collecting and Simulating Lawyers’ Thought Processes*. Microsoft Research: https://www.microsoft.com/en-us/research/publication/lawflow-collecting-and-simulating-lawyers-thought-processes/
- **[L04]** Shi et al. (2025), *LegalReasoner: Step-wised Verification-Correction for Legal Judgment Reasoning*. https://arxiv.org/abs/2506.07443
- **[L05]** Sadowski & Chudziak (2025), *On Verifiable Legal Reasoning: A Multi-Agent Framework with Formalized Knowledge Representations*. https://arxiv.org/abs/2509.00710
- **[L06]** Kondo et al. (2025), *Capturing Legal Reasoning Paths from Facts to Law in Court Judgments using Knowledge Graphs*. https://arxiv.org/abs/2508.17340
- **[L07]** Lu et al. (2026), *From Query to Counsel: Structured Reasoning with a Multi-Agent Framework and Dataset for Legal Consultation* (JurisMA). https://arxiv.org/abs/2604.10470
- **[L08]** Liao et al. (2026), *VERDICT: Verifiable Evolving Reasoning with Directive-Informed Collegial Teams for Legal Judgment Prediction*. https://arxiv.org/abs/2603.19306
- **[L09]** Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026: https://aclanthology.org/2026.emnlp-main.36/
- **[L10]** Nguyen et al. (2026), *L-MAD: A Systematic Evaluation of Multi-Agent Debate Structures in Legal Reasoning*. https://arxiv.org/abs/2607.09099
- **[L11]** Pang et al. (2026-10), *Legal-R1: Agentic Retrieval for Evidence-Based Legal Reasoning*. https://arxiv.org/abs/2610.18611
- **[L12]** Cui et al. (2026), *Chatlaw: A Multi-Agent Legal Assistant based on a Role-Aligned Mixture-of-Experts Architecture*. https://doi.org/10.1016/j.fmre.2026.03.026 （注意与更早 ChatLaw 项目/同名版本核对）
- **[L13]** Song et al. (2026), *Knowledge Graph-Assisted LLM Post-Training for Enhanced Legal Reasoning*. https://arxiv.org/abs/2601.13806
- **[L14]** Li et al. (2026), *Legal-DC: Benchmarking Retrieval-Augmented Generation for Legal Documents* (LegRAG). https://arxiv.org/abs/2603.11772

### 14.2 通用 Agent 与 RAG 方法

- **[A01]** Yao et al. (2022/23), *ReAct: Synergizing Reasoning and Acting in Language Models*. https://arxiv.org/abs/2210.03629
- **[A02]** Madaan et al. (2023), *Self-Refine: Iterative Refinement with Self-Feedback*. https://arxiv.org/abs/2303.17651
- **[A03]** Shinn et al. (2023), *Reflexion: Language Agents with Verbal Reinforcement Learning*. https://arxiv.org/abs/2303.11366
- **[A04]** Hong et al. (2023), *MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework*. https://arxiv.org/abs/2308.00352
- **[A05]** Zhao et al. (2024), *LongAgent: Scaling Language Models to 128k Context through Multi-Agent Collaboration*. https://arxiv.org/abs/2402.11550
- **[A06]** Zhang et al. (2024), *Chain of Agents: Large Language Models Collaborating on Long-Context Tasks*. https://arxiv.org/abs/2406.02818
- **[A07]** Li et al. (2024), *GraphReader: Building Graph-based Agent to Enhance Long-Context Abilities*. https://arxiv.org/abs/2406.14550
- **[A08]** Kim et al. (2025), *Towards a Science of Scaling Agent Systems*. https://arxiv.org/abs/2512.08296
- **[A09]** *On Scalable Oversight with Weak LLMs Judging Strong LLMs* (2024), https://arxiv.org/abs/2407.04622
- **[R01]** Asai et al. (2023/24), *Self-RAG*. https://arxiv.org/abs/2310.11511
- **[R02]** Yan et al. (2024), *Corrective Retrieval Augmented Generation*. https://arxiv.org/abs/2401.15884
- **[R03]** Sarthi et al. (2024), *RAPTOR*. https://arxiv.org/abs/2401.18059
- **[R04]** Edge et al. (2024), *From Local to Global: A Graph RAG Approach to Query-Focused Summarization*. https://arxiv.org/abs/2404.16130
- **[R05]** Guo et al. (2024), *LightRAG*. https://arxiv.org/abs/2410.05779

### 14.3 多模态文档及定位

- **[D01]** Wang et al. (2024), *MinerU: An Open-Source Solution for Precise Document Content Extraction*. https://arxiv.org/abs/2409.18839 ；4.x 的具体 `doclib`/`MiddleJson`/`locator` 参考当前源码：https://github.com/opendatalab/MinerU
- **[D02]** Cui et al. (2025), *PaddleOCR-VL: Boosting Multilingual Document Parsing via a 0.9B Ultra-Compact Vision-Language Model*. https://arxiv.org/abs/2510.14528
- **[D03]** Hu et al. (2024), *mPLUG-DocOwl2*. https://arxiv.org/abs/2409.03420
- **[D04]** Poznanski et al. (2025), *olmOCR*. https://arxiv.org/abs/2502.18443
- **[D05]** Li et al. (2025), *dots.ocr*. https://arxiv.org/abs/2512.02498
- **[D06]** Tito et al. (2022), *Hierarchical multimodal transformers for Multi-Page DocVQA*. https://arxiv.org/abs/2212.05935
- **[D07]** Kang et al. (2024), *Multi-Page Document Visual Question Answering using Self-Attention Scoring Mechanism*. https://arxiv.org/abs/2404.19024
- **[D08]** Li et al. (2026), *PureDocBench*. https://arxiv.org/abs/2605.07492
- **[D09]** Ouyang et al. (2024), *OmniDocBench*. https://arxiv.org/abs/2412.07626

### 14.4 评测/基准/法律检索

- **[B01]** Li et al. (2025), *LegalAgentBench: Evaluating LLM Agents in Legal Domain*. ACL 2025. https://aclanthology.org/2025.acl-long.116/
- **[B02]** Fei et al. (2023/24), *LawBench*. EMNLP 2024. https://aclanthology.org/2024.emnlp-main.452/
- **[B03]** Li et al. (2024), *LexEval*. NeurIPS 2024. https://arxiv.org/abs/2409.20288
- **[B04]** Guha et al. (2023), *LegalBench*. https://arxiv.org/abs/2308.11462
- **[B05]** Pipitone & Alami (2024), *LegalBench-RAG*. https://arxiv.org/abs/2408.10343
- **[B06]** Butler & Butler (2026), *Legal RAG Bench: an end-to-end benchmark for legal RAG*. https://arxiv.org/abs/2603.01710
- **[B07]** Zheng et al. (2025), *A Reasoning-Focused Legal Retrieval Benchmark*. https://arxiv.org/abs/2505.03970
- **[B09]** COLIEE 2025 官方任务/论文：https://coliee.org/COLIEE2025/overview ；综述：https://doi.org/10.1007/s12626-026-00199-9
- **[B10]** Ma et al. (2024), *MMLongBench-Doc*. NeurIPS 2024. https://arxiv.org/abs/2407.01523
- **[B11]** Zhang (2026), *MMLongBench-Doc-V2*. https://arxiv.org/abs/2608.03397
- **[B14]** Gao et al. (2023), *Enabling Large Language Models to Generate Text with Citations* (ALCE). https://aclanthology.org/2023.emnlp-main.398/
- **[B15]** Ru et al. (2024), *RAGChecker*. https://arxiv.org/abs/2408.08067
- **[B16]** Min et al. (2023), *FActScore*. https://arxiv.org/abs/2305.14251
- **[B17]** Chlapanis et al. (2024), *LAR-ECHR*. https://aclanthology.org/2024.nllp-1.22/

---

## 15. 文档维护与代码实现交接

该文献清单应每季度重新检索，按 `paper_id / venue / first_release / version / source_url / code_url / code_verified / data_available / model_weights / license / faithful_or_inspired / applicable_track` 管理。对于 `2026-10` 新工作务必记录“预印本/同行评议/是否复现”。

**建议 Codex 第一项任务**：生成 `benchmark/candidates.yaml` 与上述 10 个 P0 配置的空白 adapter manifest，然后实现 **E00、E01、E03、E05、E06** 的规范化 I/O 和预算记录；完成基线可运行测试后才继续 E07–E11。不要一次性复制所有研究框架或把论文名字当作可调用 Python 包名。

**文档作者立场**：对于未在相同数据上运行的候选，“预期效果”是研究假设而不是事实；对于缺少可用代码/权重的论文，优先做明确标记的概念复现。任何研究对比都应允许现有系统输给简单基线，并报告这个结果。
