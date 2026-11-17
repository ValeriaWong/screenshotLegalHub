# 系统架构

`domain/` 定义纯 Python/Pydantic 领域契约，不导入 FastAPI、SQLAlchemy 或 UI。`application/ports` 定义能力接口，`application/services` 负责用例、编译、证据/审核/结果投影。`plugins` 提供数据包发现、能力注册和内置执行器、感知适配器。`infrastructure` 实现数据库、存储、检索和模型网络端口。`api` 组合应用服务。

Evidence 只记录客观转录与来源；Matter Pack 只描述法律模板；Skill 完成一项能力；Compiler 生成 CasePlan；Runtime 执行 DAG；ProofGraph 表达当前分析结构；Review 独立保存人的决定。新增 Matter 主要添加 YAML，不复制一套案由专用 Python 类。

运行顺序为 perception → timeline → matter/claim → fact/burden → evidence map/strength → gap/contradiction → strategy/adversarial → verification。同 Stage 内依赖满足的节点通过 `asyncio.gather` 执行；Stage 间从数据库重读已提交的 typed snapshots。没有共享的 LLM 对话历史。

SQLite 每种主要聚合对应独立索引表。v1 使用 JSON document 保存版本化内容、case/run 索引定位，领域关联由服务验证；不是关系表每字段一列的最终 PostgreSQL Schema。Alembic 0001 创建全部表和 FTS5。

前端：tokens → UI primitives → shell/application components → feature。TanStack Query 管理服务端数据；URL 管理案件、页签、筛选、检索、日期、运行 ID；Context 只管理详情栏等本地壳状态。没有复制全部案件数据的大型全局 store。

旧模块参考：`legalhub/evidence.py` 的明确坐标协议/可见原文原则；`retrieval.py` 的哈希、来源校验和本地检索；`case_registry.py` 的历史保留；`providers.py` 的密钥不落入公共配置原则。新代码独立实现，不 import 旧包，也不读取旧配置密钥。
