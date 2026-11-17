# 实现报告

本轮完成独立 product_v1 的可运行第一版：版本化 Matter Pack 和通用 Skill 分离，CasePlan 编译与八阶段执行，可追溯 Evidence/SourceRef，ProofGraph/Matrix，追加式 Review 与失效，SQLite/FTS5/OpenAPI/SSE，统一轻量工作台。第一版覆盖民间借贷，无模型 Key 可完成整个 Demo。

后端组织为 domain/application/plugins/runtime/infrastructure/api/cli。主要表均经 Alembic 创建；JSON document + case/run 索引支持版本化持久化。原图按 SHA256 独立保存，禁止任意路径读写，下载和运行前验证完整性。来源对照与律师审核有独立数据模型和持久化入口。

运行时不共享无限增长对话。节点仅取 selectors；typed result 和派生结果事务写入；有限重试与 idempotency key 防止重复输出。审核关卡可以暂停/继续/拒绝。新 Run 不覆盖旧 snapshot，成功后更新 active run。审计记录摘要、attempt、latency、warnings/errors、trust/permissions，不暴露隐藏推理或 Key。

前端提供十个一级页面，浅色、简约、文档导向。共享 DetailRail 负责引用/实体/审计详情；Source Navigation 统一定位原始来源与 bbox。UI 库、图标、motion 均有边界，颜色集中 tokens，URL/Query/UI 状态分工明确。固定文案双语；业务页面显示可读分析内容，技术审计集中 Advanced。

测试和实际本地证据见 LOCAL_RUN_VERIFICATION、ACCEPTANCE。完整验收包括后端、前端、生产构建、三条真实 Chromium E2E 和 axe。实际踩坑单独记录，不把未试过的命令或真实模型效果写成已验证。

旧代码处理：仅阅读提炼来源校验、检索分离、历史保留等设计；未删除/移动/改写历史数据、Benchmark、论文、旧代码或报告。新运行时没有旧 legalhub 依赖。Holmes 仅参考规格所述架构与交互概念，无源码复制。

交付定位：第一版可运行功能架构与确定性流程。法律规则保持 draft/unreviewed，Authority保持unverified；更强的生产法律分析、专业评审、线上模型供应商验收与P1能力没有被表述为已完成。
