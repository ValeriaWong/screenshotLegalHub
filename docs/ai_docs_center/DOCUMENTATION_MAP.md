# 文档地图与维护规则

对账日期：2026-10-24（Asia/Singapore）。完整清点见[DOCUMENTS_INDEX.md](DOCUMENTS_INDEX.md)与[documents_inventory.json](documents_inventory.json)，包含路径、标题、分类、SHA256和字节数。

## 按用途阅读

| 用途 | 当前入口 | 历史/证据 |
|---|---|---|
| 综合进度 | [完成度](PROGRESS.md)、[Feature](FEATURES.md)、[Issues](ISSUES.md)、[Gap](GAPS.md) | [2026-10-22归档](archive/2026-10-22/README.md) |
| 研究产品当前开发 | [可靠性/审计完善计划与现有进度](RESEARCH_PRODUCTS_PLAN.md)、[四产品边界](../products/PRODUCT_BOUNDARIES.md) | [MVP](../../product_v1/reports/research-products-mvp-2026-10-24/REPORT.md)、[图片审核](../../product_v1/reports/review-canvas-2026-10-24/REPORT.md)、[9项缺陷评审](../../product_v1/reports/critical-review-2026-10-24/REPORT.md) |
| 启动当前独立产品 | [product_v1 README](../../product_v1/README.md)、[账户/导入/模型](../../product_v1/docs/INGESTION_ACCOUNTS_MODELS.md) | [10月13日验收](../../product_v1/reports/multi-upload-auth-2026-10-13/REPORT.md) |
| 旧软件与七项目启动 | [历史指南](LEGACY_GUIDE.md)、[报告索引](../../reports/README.md) | 原projects、v1.0/v1.1/v1.2报告原位保留 |
| 当前人工交接 | [S4两份盲审包与填写说明](../v3.0.0/CALIBRATION_HANDOFF.md) | [本次连续推进归档](archive/2026-10-23/CONTINUATION.md) |
| 当前执行计划 | [KISS任务顺序](NEXT_STEPS.md)、[来源补齐用法](../v3.0.0/SOURCE_CLOSURE.md) | [774文件第二批验证](../../reports/v3.0.0/source_closure_20261023_001/README.md)、[G01完成归档](archive/2026-10-23/COMPLETED.md) |
| V3研究与交接 | [计划](../../V3.0.0_PLAN.md)、[清单](../v3.0.0/READINESS.md)、[工作包](../v3.0.0/work_packages.json) | 旧依赖预研保持v2/development路径 |
| 坐标与检索/回溯指标 | [技术与评测协议](../coordinate-retrieval-evaluation.md) | [运行库恢复审计](../../reports/coordinate_audit_20261024/README.md)，参考框与模型预测分开 |
| 截图样式与排版 | [渲染模板修改指南](../screenshot-rendering.md) | V2 共用模板、第五/六轮适配及 V3 冻结渲染器 |
| 架构/契约 | [综合架构](../architecture.md)、[旧数据契约](../data-contracts.md)、[新产品Schema](../../product_v1/docs/SCHEMA.md) | [早期重启架构](../RESTART_ARCHITECTURE.md) |
| 候选数据 | [第四轮](../../datasets/v2.0.0/round_004/REPORT.md)、[第三轮](../../datasets/v2.0.0/round_003/REPORT.md) | 第一/二轮、撤回稿、来源和失败记录原位保留 |
| 论文 | [工作稿说明](../../paper/README.md)、[评审矩阵](../../reports/research/REVIEW_AND_REBUTTAL.md) | 不将计划或旧摘要写成新实验结果 |

## 冲突与过时内容的处置

- 根README原来混排多个历史“当前”状态，现改为双软件线与研究入口；原全文保存为LEGACY_GUIDE阅读副本及字节快照。
- docs/architecture增加独立产品和最新V2/V3边界；原图明确归为2026-10-04基线。RESTART_ARCHITECTURE的早期“暂无软件”保留为历史事实，添加历史标识。
- product_v1 REQUIREMENTS/ACCEPTANCE区分P0初版和10月13日多用户/批量导入扩展；57项PASS是原规格验收，不能折算成V3完成。
- evidence_workbench_v1是迁移准备记录；后续独立实现入口是product_v1，避免把早期阻塞当作当前不存在产品。
- 旧报告中的模型默认值、病例数、测试数、环境和“无remote”按当次日期解释；本次origin已配置，但没有推送或核验远端同步。
- 根config.yaml仍是旧block流程配置，product_v1具有独立设置；本次不为更新文档而修改运行时配置。

## 清点与归档范围

清点根Markdown以及docs/reports/blocks/skills/paper/datasets、product_v1、迁移准备目录的第一方Markdown；projects仅收子项目顶层README。环境、依赖、vendor、临时目录、本文档中心自身以及V3 snapshot/重复字节副本不计入文档数量；副本由其source manifest单独清点。JSON/源码/图片按引用证据另校验，不等于逐文件完整资产审计。

原报告、项目、截图、数据库、论文和运行记录不移动、不删除、不重命名；归档采用副本/哈希与分类索引，保护已有引用。整理前文档使用`.txt`保存原始字节（含原相对链接）；这些是审计快照，阅读历史请走LEGACY_GUIDE。

## 后续同步

1. 人工核对新增代码、原始结果和验收条件；更新status.json中的稳定ID、范围、状态及证据。
2. 同步PROGRESS、NEXT_STEPS、根README、中心README、V3工作包和READINESS中的摘要；不得把待复核标成已认证。
3. 运行下列工具重新生成Feature/Issues/Gap和文档清单，再检查计数、证据路径与本地链接：

```powershell
.\.venv\Scripts\python.exe tools/sync_ai_docs_center.py
.\.venv\Scripts\python.exe tools/sync_ai_docs_center.py --check
```

工具不会推断完成度或执行专业认证，也不会更新历史归档；人工摘要需随台账更新。新增归档使用新日期或同日独立批次目录，旧快照不覆盖。

## admin全量案件同步

[运行库清单与使用说明](ADMIN_CASES.md)、[实际写入及审计](../../reports/admin_case_inventory_20261024/README.md)、[同步/备份命令](../../product_v1/docs/MIGRATION.md)。目录中的数据集文件需要显式导入运行库，文件清点不等同于账户中已可见。

## 研究三台进度与审计计划同步

2026-10-24已将MVP、图片审核、SQLite持久化基础及9项未修复问题纳入F29–F34/I17–I25/G20–G25；RP01–RP08现已在本轮实现并验收，审计表/API/前端已可用。当前历史测试和缺陷复现分别记账，V3独立认证仍0。[同步归档](archive/2026-10-24/research_products_plan/README.md)。

[本轮可靠性/操作审计交付](../../product_v1/reports/reliability-audit-2026-10-24/REPORT.md)、[用户操作与存储说明](../products/RELIABILITY_AUDIT.md)、[实现文档归档](archive/2026-10-24/research_products_implementation/README.md)。此前规划归档保持原样。
