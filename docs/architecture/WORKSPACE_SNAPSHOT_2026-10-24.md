> 历史快照：保留 2026-10-24 的工作区记录，当前结构见[当前架构](../architecture.md)。

# screenshotLegalHub

电子证据工作台、截图候选数据与研究评测工作区。当前有旧 `legalhub` 与独立 `product_v1` 两条软件线，运行环境和模型设置分别维护。

**2026-10-24 进度：当前四场景校准的S0–S3作者/机械交接完成（4/8阶段），独立认证0题，尚未发布。** Feature 28项：完成20、部分4、待交付4；issues 16项：处置11、未关闭5；gap 19项：当前范围完成6、未关闭12、后续扩展1。阶段比例不代表全项目或法律质量完成率。

[架构盘点与模块化重构方案](../../docs/architecture/REFACTOR_PROPOSAL.md) · [AI 文档中心](../../docs/ai_docs_center/README.md) · [完成度与证据](../../docs/ai_docs_center/PROGRESS.md) · [Feature](../../docs/ai_docs_center/FEATURES.md) · [Issues](../../docs/ai_docs_center/ISSUES.md) · [Gap](../../docs/ai_docs_center/GAPS.md) · [文档地图](../../docs/ai_docs_center/DOCUMENTATION_MAP.md)

已完成774文件基线、环境重渲染、旧案导入原子性修复，以及4场景/80图/352子集和两份盲审ZIP。当前需要两位真实独立复核者。[人工交接与复核包](../../docs/v3.0.0/CALIBRATION_HANDOFF.md) · [当前计划](../../docs/ai_docs_center/NEXT_STEPS.md) · [本次归档](../../docs/ai_docs_center/archive/2026-10-23/CONTINUATION.md)

**admin 全量案件已实际导入运行库：现可见2,687条案件/版本记录（原有5+新增2,682）。** 覆盖旧库、V2/V3、全部round、作者修订、原文缺口和历史渲染，重复同步新增0条。刷新产品页面后可按案号、版本、来源和状态搜索。计数含版本及原文档案，不是不同真实案件数。[全量清单与审计](../../reports/admin_case_inventory_20261024/README.md) · [admin使用说明](../../docs/ai_docs_center/ADMIN_CASES.md)

坐标接入已补齐6389个几何引用，2549/2579张图有区域，剩30张旧图待补标；FTS5/BM25检索不调用模型。[坐标、检索与回溯评测说明](../../docs/coordinate-retrieval-evaluation.md) · [实际修复报告](../../reports/coordinate_audit_20261024/README.md)。

## 软件入口

当前产品方向已调整为[四个独立产品](../../docs/products/PRODUCT_BOUNDARIES.md)：评测、合成生成、数据审核、用户工作台。四个 MVP 现均有独立入口：评测 /evaluation.html、合成 /studio.html、审核 /review.html、用户工作台 /。生成与质量 Prompt 分属生成台/审核台，Markdown 历史和质量对比已接入。[研究产品使用说明](../../docs/products/RESEARCH_MVP.md)。旧完整控制台保留在 http://127.0.0.1:18431/console.html 。

| 软件 | 范围与入口 | 启动说明 |
|---|---|---|
| 独立产品 `product_v1` | FastAPI/React；Matter Pack、DAG、证明矩阵、审核、账户协作、批量导入、用户模型配置。UI `http://127.0.0.1:18431`，API `http://127.0.0.1:18430/docs` | [产品 README](../../product_v1/README.md) |
| 旧 `legalhub` | 案件库、截图转录、案件问答、时间轴、合同内容与法律批注；`http://127.0.0.1:18420`，批注 `/review` | 下方命令及[历史指南](../../docs/ai_docs_center/LEGACY_GUIDE.md) |
| `evidence_workbench_v1` | 2026-10-07 迁移准备快照，后续独立产品位于 `product_v1` | [历史范围](../../evidence_workbench_v1/README.md) |

旧工作台从仓库根目录启动：

```powershell
.\.venv\Scripts\python.exe -m legalhub.app serve --port 18420
```

独立产品按其 README 使用本目录 Conda 或 venv；不要混用根 `.venv`。产品默认无 Key Demo，模型按用户在界面设置；根 `configs/models.local.yaml` 用于旧软件和研究流程，不能直接控制新产品。

## 当前数据与研究状态

| 资产 | 实际规模 | 状态 |
|---|---|---|
| [V2 第六轮](../../datasets/v2.0.0/round_006/REPORT.md) / [当前预览](../../datasets/v2.0.0/round_006/index.html) | 200条全文复核；当前138通信候选、200图、528消息、408问答；另2项辅助摘录 | 恢复11、修订85、撤回11；62条缺口，非人类金标 |
| [V2 第五轮](../../datasets/v2.0.0/round_005/REPORT.md) / [全量清单与预览](../../datasets/v2.0.0/round_005/index.html) | 200条已处置：138候选（新增38、复用100），242图、815消息、439问答；62来源缺口 | 历史机械归档；当前采用第六轮复核版本，旧稿不可直接作为金标 |
| [V2 第四轮](../../datasets/v2.0.0/round_004/REPORT.md) / [截图预览](../../datasets/v2.0.0/round_004/index.html) | 28案、56图、176消息、118主张题；支持38/反驳21/证据不足59 | development；2份本轮联网判决进入截图组；200为扩充目标 |
| [V2 第三轮](../../datasets/v2.0.0/round_003/REPORT.md) / [预览](../../datasets/v2.0.0/round_003/index.html) | 177候选案、382图、1417消息；覆盖177/207历史来源标签 | 30种仍缺可用来源；非专业金标 |
| [V2 第二轮](../../datasets/v2.0.0/round_002/REPORT.md) / [第一轮](../../datasets/v2.0.0/round_001/REPORT.md) | 第二轮2案9图6题；第一轮6案49图24题 | 历史迭代与来源/修订记录保留 |
| [依赖预研](../../reports/research/legal_answer_review/20261004_dependency_pilot_v1/RESULTS.md) | 12变体、48图片位置/18种像素、192子集 | 一个抽象模板的开发材料；待独立认证 |
| [V3校准与交接](../../docs/v3.0.0/CALIBRATION_HANDOFF.md) | 4基础场景、80图、352子集 | S0–S3当前批交接通过；S4独立复核待人员，20场景目标未完成 |

各轮有同源复用，不能相加为独立案件总数。来源可定位、程序测试通过与法律判断正确分别验收。

## 本次验证与后续工作

本次离线回归及日志见[完成度报告](../../docs/ai_docs_center/PROGRESS.md)；历史浏览器、真实模型和性能记录仍按各版本报告解释。2026-10-24已备份并写入本机product_v1运行库，全部文件/引用及原有记录校验通过；服务健康和前端资源HTTP检查通过，未做本轮视觉E2E。没有调用项目模型API或推送仓库。

当前从S4独立复核继续；认证题及预算明确后再做正式评测。继承的全量专业评测、完整法官/律师双模式、专用Excel与时间轴PPT仍须单独验收。

当前已配置 origin（GitHub `ValeriaWong/screenshotLegalHub`）；本次仅整理本地工作区，未确认远端与本地同步。历史报告中的“无 remote”仅描述当时状态。

## 文档与历史

- [文档入口](../../docs/README.md)、[报告入口](../../reports/README.md)、[架构及版本边界](../../docs/architecture.md)、[数据契约](../../docs/data-contracts.md)。
- [产品账户/导入/模型说明](../../product_v1/docs/INGESTION_ACCOUNTS_MODELS.md)、[产品验收映射](../../product_v1/docs/ACCEPTANCE.md)、[论文工作稿](../../paper/README.md)。
- [历史根 README 与七项目启动指南](../../docs/ai_docs_center/LEGACY_GUIDE.md)、[完整文档索引](../../docs/ai_docs_center/DOCUMENTS_INDEX.md)、[2026-10-22 整理前快照](../../docs/ai_docs_center/archive/2026-10-22/README.md)。
- 原 `projects/`、数据、图片、模型响应和旧报告均原位保留。
