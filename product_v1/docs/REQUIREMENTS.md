# 实现范围

> 本页区分P0初版和后续扩展。2026-10-13已增加账户/多用户案件权限、批量导入及用户隔离模型设置，见[扩展说明](INGESTION_ACCOUNTS_MODELS.md)和[验收](../reports/multi-upload-auth-2026-10-13/REPORT.md)；这些不再作为未实现P1。2026-10-22离线回归见[文档中心](../../docs/ai_docs_center/PROGRESS.md)。V3研究认证与产品P0完成分别统计。

以父目录 `docs/ScreenshotLegal_Implementation_Specification.md` v1.1 为本轮规格。目标是可独立启动的 `product_v1/`，保留旧项目、论文与 Benchmark。

P0：Evidence Core；版本化民间借贷 Matter Pack；正交 Skill Registry/Resolver；编译为确定性 DAG；阶段隔离、数据库交接、有限重试、幂等、人审关卡；可重建 ProofGraph/ProofMatrix；审核版本和失效；FTS5；API/OpenAPI/SSE；统一 AppShell/DetailRail/Source Navigation；十个一级页面；中英文、减少动效与可替换 UI；无 Key Demo、迁移工具、测试、真实环境记录。

P1 不纳入本轮：Proof Graph 图形编辑、横向缩放时间线、规则可视化编辑器、Chat、PostgreSQL、更多 Matter、市场、Excel/PPT、复杂视差。

Demo 数据全部合成；法律规则不宣称已专家审核。模型默认关闭且禁止外发；真实模型能力需要显式配置，不能作为离线验收依赖。
