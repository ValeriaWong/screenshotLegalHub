# 报告入口

> 2026-11-17 提交边界：运行报告及原始响应保留本地，不随此次源码更新发布；下列链接可能需要完整本地工作区。已跟踪的历史报告继续保留，本次未重跑其验收。

- [2026-10-24 admin全仓库案件同步](admin_case_inventory_20261024/README.md)：运行库2687条案件/版本，覆盖、幂等及原有数据审计。

各报告保留其版本、样本和日期；当前综合判断见[完成度评估](../docs/ai_docs_center/PROGRESS.md)。旧测试数、默认模型或“无remote”不作为当前状态。

| 范围 | 入口与限制 |
|---|---|
| 当前校准交接 | [4场景/80图/352子集](v3.0.0/calibration_20261023_001/README.md)，作者/机械检查通过，独立意见待完成 |
| 环境复现 | [字体/浏览器/重复渲染/冻结软件烟测](v3.0.0/runtime_reproduction_20261023_002/README.md)，本机已装环境 |
| 导入修复 | [事务回归与2案真实语料隔离迁移](v3.0.0/import_atomicity_20261023_001/README.md)，I11关闭 |
| T02来源补齐 | [774文件/原始评分/P3图片/四案来源](v3.0.0/source_closure_20261023_001/README.md)，当时28项工具测试通过；其后G02见上行 |
| S0首批冻结 | [401文件与14项工具测试](v3.0.0/s0_baseline_20261022_001/README.md)，首批历史记录，当时完整S0未验收 |
| 旧软件最新批注验收 | [v1.2.0](v1.2.0_legal_review_workspace.md)，原HTTP/浏览器证据保留 |
| 旧软件多案与问答 | [多案](v1.1.0_multi_case_workspace.md)、[3案12题开发评估](v1.1.0_case_qa_evaluation.md) |
| v1模型复测 | [P3分析](v1.0.0_iteration_analysis.md)，未完成八轨全量专业评估 |
| 独立产品 | [10月13日账户/批量导入验收](../product_v1/reports/multi-upload-auth-2026-10-13/REPORT.md)，模型为mock/回环测试 |
| 依赖预研 | [原开发试验](research/legal_answer_review/20261004_dependency_pilot_v1/RESULTS.md)、[范围澄清](research/legal_answer_review/20261004_dependency_scope_probe_v2/RESULTS.md)、[空白认证包](research/legal_answer_review/20261004_dependency_certification_v1/CERTIFICATION_PLAN.md) |
| V2候选数据 | [第四轮](../datasets/v2.0.0/round_004/REPORT.md)、[第三轮](../datasets/v2.0.0/round_003/REPORT.md)，均非专业金标 |
| 论文/历史资产 | [重启核查](research/RESTART_FINDINGS.md)、[评审矩阵](research/REVIEW_AND_REBUTTAL.md) |
| 本次整理 | [测试与文档快照归档](../docs/ai_docs_center/archive/2026-10-22/README.md) |

不移动或改写原报告和原始响应；新评估通过文档中心引用。
