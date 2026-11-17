# Skill 拆分

> 2026-10-22补记：本页为仓库研究/旧工作台的任务Skill分工。独立product_v1有自己的[运行时Skill注册体系](../product_v1/docs/SKILLS.md)，与本页SKILL.md流程不是同一层。V3新增能力仍待[阶段验收](ai_docs_center/PROGRESS.md)。

仓库 skills 位于 `skills/`。它们是工作流程说明，不是已完成的软件功能。当前 curator、evaluator、evidence 和代码 retriever 有可执行入口，后续专业工作流仍待实现。未安装到全局 Codex，不修改用户配置。

| Skill | 阶段 | 实际执行对象 |
|---|---|---|
| legal-assets | v1 已有 | 本地/归档/GitHub 清单、哈希、图片完整性与缺口 |
| legal-benchmark | v1 已有 | 冻结题目、选取模型、推理、断点恢复、分 track 报告 |
| legal-evidence | v1 本轮闭环已运行 | 图片 → 消息/事件候选 → 来源校验 → 代码 retrieve；专业复核仍待完成 |
| legal-reconcile | v1 待实现 | 法官模式双边证据对齐、重叠去重、缺口及冲突 |
| legal-lawyer-review | v1 待实现 | 指定委托方的有利/不利标注和工作视图 |
| legal-exports | v1 部分已有 | 已有带完整来源的 CSV/JSON、事件大事记；专用 Excel/PPT 待实现 |
| legal-synthesis | v2 | 中/英文判决约束生成、微信/WhatsApp 固定视口截图 |
| legal-quality-loop | v2 | 人工评分恢复、生成/评分 prompt 校准、难度分层与冻结 |
| legal-paper | v1/v2 同步 | LaTeX 工作稿、实验来源、内部评审及原 review/rebuttal 对照 |

每个 skill 使用共同的数据契约。入口按照 check → run → inspect 组织；已经获得的操作授权持续有效，不新增重复确认。
