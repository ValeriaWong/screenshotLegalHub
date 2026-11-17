# v1.1 验收映射

> 此57项PASS为初版规格映射，不是V3的S0–S7验收。2026-10-22复跑后端43项、前端9项及类型/lint/架构检查通过；[当前评估及原始日志](../../docs/ai_docs_center/PROGRESS.md)。本次未重跑浏览器和线上模型。

验收按原规格 AC01–AC57 映射。PASS 表示本地代码/测试/审查覆盖，不代表规则经过律师审查，也不代表真实模型供应商兼容性已线上认证。

| AC | 状态 | 证据 |
|---|---|---|
| 01 | PASS | 所有新实现位于 product_v1；旧 README 的已有变动未覆盖 |
| 02 | PASS | 新包无 legalhub import；独立锁文件、资源、数据库、启动脚本 |
| 03 | PASS | 新建 .venv 与第二个 .venv-clean，锁定依赖安装和测试成功 |
| 04 | PASS | 合成 seed 与三个无 Key Chromium E2E |
| 05 | PASS | MatterRegistry 发现民间借贷1.0.0 |
| 06 | PASS | MatterManifest 与 Claim/Element/Fact/Authority 校验测试 |
| 07 | PASS | Plan/Run 固化 Pack version/digest |
| 08 | PASS | 13个 manifest 注册并实际执行 |
| 09 | PASS | resolver priority/override/ambiguity 测试 |
| 10 | PASS | external_untrusted 与未 allowlist trusted 拒绝测试 |
| 11 | PASS | 两次编译相同 plan_digest，compiled_at 不参与摘要 |
| 12 | PASS | 每节点重读数据库 snapshots，Stage DAG 集成测试 |
| 13 | PASS | selector projection 深复制，不暴露 conversation/raw response |
| 14 | PASS | integrated fail-once retry 产生14次审计但只有13份成功节点快照 |
| 15 | PASS | compile-review/critical-finding 暂停与恢复测试；浏览器批准关卡 |
| 16 | PASS | 新 Run 不改变旧 Run/snapshots；历史 graph 查询 |
| 17 | PASS | attempt/digests/latency/permissions/trust/warnings/error 审计；无效输出也记录失败 |
| 18 | PASS | ProofGraph 从固化输入和结果快照重建，所有关系边可解析 |
| 19 | PASS | Matrix API 与 Claims 视图体现 Claim→Element→Fact |
| 20 | PASS | burden.assign 从 Matter 规则实例化，Matrix 呈现 |
| 21 | PASS | Demo 同时出现 supports 与 contradicts 关系 |
| 22 | PASS | 数据包预期证据驱动补证项 |
| 23 | PASS | 同一 Fact 相反陈述形成 contradiction |
| 24 | PASS | strategy 仅消费 ProofGraph projection，verification 检查目标 IDs |
| 25 | PASS | Entity 默认 unreviewed，集成测试检查全部初始输出 |
| 26 | PASS | ReviewDecision/LawyerAssessment append-only；两次审核历史保留 |
| 27 | PASS | 修改证据后新 Run → Fact review stale，后端和浏览器双覆盖 |
| 28 | PASS | SQLite FTS5/BM25 检索；测试无 egress audit |
| 29 | PASS | 上传 SHA256、读图与启动分析重验、篡改拒绝 |
| 30 | PASS | 浏览器显示原始图片；无来源/错误状态可见 |
| 31 | PASS | 点击引用打开真实 pixel bbox；组件精确测试百分比布局 |
| 32 | PASS | Timeline/Claims/Matrix/Findings/Review 共享 Citations 和 Source Navigation |
| 33 | PASS | AppShell 案件头/导航/工作区/共享右栏 |
| 34 | PASS | DetailRail 组件覆盖切换、开关、折叠、resize/localStorage |
| 35 | PASS | Timeline API/页面、人物/类型/审核/日期筛选；移动截图 |
| 36 | PASS | Claims 页面分组显示要件、事实、burden、证据计数 |
| 37 | PASS | Matrix 独立一级页面，只渲染 Matrix API |
| 38 | PASS | Review queue/当前决定/来源/四操作/历史；E2E 保存 |
| 39 | PASS | Advanced 按 Stage 显示节点、依赖箭头、状态文本、审计 |
| 40 | PASS | 持久化 SSE run/stage/node/review events，浏览器接收 |
| 41 | PASS | Reload 后 state-snapshot 还原已完成运行 |
| 42 | PASS | Feedback loading/error/empty/not-run；Review stale；操作 disabled |
| 43 | PASS | zh-CN/en 字典键匹配测试与浏览器英文切换 |
| 44 | PASS | reduced-motion hook/tokens/CSS 与浏览器 smoke |
| 45 | PASS | UI primitives/icons/motion 适配层；架构 guard 禁止 Feature vendor UI import |
| 46 | PASS | Feature 禁止 HEX/rgb，架构 guard 检查 |
| 47 | PASS | FastAPI OpenAPI 导出，openapi-typescript 生成客户端契约 |
| 48 | PASS | pytest，详细数量见 LOCAL_RUN_VERIFICATION |
| 49 | PASS | typecheck/lint/4个组件测试 |
| 50 | PASS | Vite production build |
| 51 | PASS | 三条 Playwright 流程 |
| 52 | PASS | axe WCAG2 A/AA smoke 无 serious/critical；实际问题修复记录 |
| 53 | PASS | 规定的16篇 docs + README + third-party notices |
| 54 | PASS | TROUBLESHOOTING 仅记录实际失败、原因、修复和最终配置 |
| 55 | PASS | 本机版本、实际命令、Demo ID、页面、测试结果和限制有记录 |
| 56 | PASS | 没有读取旧密钥；.env/data 忽略；测试只有显式无效 placeholder |
| 57 | PASS | HOLMES_REFERENCE 明确仅参考规格概念，未复制源码 |

上述AC01–AC57记录P0初版的本地单用户、内置确定性工作流与合成Demo范围。后续账户、会话、案件协作权限、批量导入与模型设置已于2026-10-13扩展并单独验收，见[扩展报告](../reports/multi-upload-auth-2026-10-13/REPORT.md)。真实证据实质法律质量、专家规则评审、付费模型线上调用和生产部署仍未完成认证。
