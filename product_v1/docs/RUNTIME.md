# Runtime

`CaseCompiler` 解析 capabilities 及依赖，拒绝缺失能力、同级歧义、依赖环和逆向 Stage。Plan 固化 Matter/Profile/Skill SHA256、节点、边、selectors、targets、review gates 和 retry policy；compiled_at 不进入 plan_digest，因此相同输入产生相同计划摘要。

运行输入在 `AnalysisRun.input_snapshot` 固化。每个节点从数据库加载此前已提交 snapshots，`context_projection.project` 仅复制 Manifest 声明字段。strategy/adversarial/verification 读取 ProofGraph projection，不把全部聊天作为新的独立事实来源。

节点幂等键为 SHA256(run + node + input_digest + skill_digest + matter_digest)。输出快照和派生领域行同事务提交；失败不留下部分成功输出。重试有限次且按错误类型 allowlist 执行；权限/Schema 错误不重试。SkillRun 记录每次 attempt、摘要、耗时、warnings/error、trust/permissions；无模型调用时 token_usage 为 {}。

Matter selection 由 PUT 显式确认。运行先 WAITING_REVIEW，批准 compile-review 后执行；可选择 critical-finding 关卡，在第6阶段后暂停。测试可设置 AUTO_APPROVE_GATES。关卡拒绝使运行失败，不改变旧的 active run。

运行成功后才切换 Case.active_analysis_run_id。历史结果逻辑不可变；重新运行创建新 run、快照和领域行。Review 绑定语义输出摘要；Fact 的摘要还包含当前证据关系依据，因此证据或状态变化会失效，重复相同运行可保留审核显示。编辑文本属于 Review，原模型结果仍保留。

SSE 先发送数据库重建的 state-snapshot，再发送后续持久化 run/stage/node/review 事件。node_states 从计划、审计与事件重建，覆盖七种状态。重连不依赖浏览器旧事件。进程中断的运行标记 INTERRUPTED；v1 采用新建 Run 重试，不自动恢复外部模型调用。WAITING_REVIEW 可在重启后继续批准。
