# 仓库架构盘点与重构建议

> 后续产品决策已更新：按用户最新需求拆成评测、合成生成、数据审核和用户工作台四个独立产品，见[当前产品边界与 MVP](../products/PRODUCT_BOUNDARIES.md)。本文模块化单体建议适用于单个产品内部；不再作为把四类业务合成一个产品的目标。

核验日期：2026-10-24。状态：已完成源码与功能盘点、目标设计和迁移方案；尚未执行运行代码或数据目录迁移。

建议采用：模块化单体、按业务组织代码、模块内部用端口与适配器隔离外部依赖。当前产品已有良好分层基础，应补全职责与依赖边界，而不是一次性重写。

## 1. 当前仓库分别在做什么

| 部分 | 实际职责与入口 | 建议归属 |
| --- | --- | --- |
| product_v1/backend 与 frontend | 当前 FastAPI/React 工作台；API 18430、UI 18431；账户、案件共享、原件上传、转录、案由与 DAG、证明矩阵、人工审核、模型配置与文本/图片连通性 | 主产品应用 |
| agentic | 独立可安装推理 Harness；规划、事实、评估、缺口、综合五阶段，含 Skills、Tools、Review、预算、Responses 接口和 HTML 报告；SDK、CLI、可选 HTTP 18440 | 独立软件包，保留自身公开契约 |
| legalhub 与 blocks/retriever/web | 旧工作台及旧浏览器界面；案件检索、问答、时间轴、内容及法律批注；旧服务 18420 | 维护兼容，存量用户入口 |
| blocks、根 tools、根 tests | 数据整理、合成、截图、质量检查、V2/V3 校准与研究评测；部分工具调用旧包 | 按研究任务分组的流水线 |
| datasets、paper、reports | 数据版本、论文、实验和交付证据；不等同产品业务模块 | 可追溯研究资产与文档 |
| evidence_workbench_v1、projects、归档.zip | 历史快照、参考项目与第三方资产，生命周期不一 | 历史/参考资产，不统一视为可删除缓存 |
| product_v1/tools | 旧案与仓库资产的导入导出、OpenAPI 导出和初始化 | 显式集成工具；不由产品请求直接依赖旧系统 |
| .runtime、.tools、.conda、.venv、tmp、product_v1/data | 本地进程日志、安装/测试副本、环境、数据库、原件与加密主密钥 | 运维状态与开发环境，不参与源码架构扫描 |

静态核查当前三个源码包没有互相导入：screenshotlegal 产品包、agentic、legalhub；这不表示历史安装副本或离线迁移工具没有依赖。product_v1/tools/export_legacy_repository_cases.py 明确引用 legalhub，应继续作为受控离线适配入口。

特别注意：agentic 当前输入为已转写文本，不提供产品的原图存储、OCR、完整 Matter Pack/ProofGraph 契约。它不是已经接入当前前端的引擎，也不能仅因名称相近就替换产品 Runtime。

## 2. 已核实的结构问题

以下结论来自源码依赖和职责，不将文件行数作为是否需要重构的唯一依据。

| 证据位置 | 观察 | 实际影响 |
| --- | --- | --- |
| product_v1/backend/src/screenshotlegal/api/accounts.py，image_sample 与 register_accounts | 账户、用户、模型、共享权限路由在同一注册函数；选图、文件完整性检查也进入路由层 | 添加一种测试输入需要改账户 API；CLI 和其他入口难复用同一规则 |
| application/services/preferences.py | 用户资料、模型 CRUD、密钥、默认选择、模型实例与连通性集中；直接导入具体网络和加密实现 | 更换模型协议会触及用户配置用例；测试依赖对 httpx 的 monkeypatch |
| application/services/workspace.py | 案件、原件、转录、案由、运行、审核与对账经同一门面调度，构造多个基础设施对象 | 跨业务职责聚集，组合根和业务用例不清晰 |
| application/services/auth.py | 登录/会话和案件共享授权集中，并直接使用 SQLAlchemy 与 MODELS | 修改业务授权时同时接触数据库结构和账户生命周期 |
| runtime/stage_executor.py | 直接导入应用层 proof，直接把 DeterministicSkill 设为工厂 | 执行机制与特定能力实现及结果落库规则耦合；在层级上出现 application 与 runtime 的双向依赖，不能据此认定存在 Python 模块导入环 |
| infrastructure/db/repository.py 与 db/models.py | 大部分持久化通过表名字符串和 JSON body 的通用 get/list/put/batch | 数据格式和表名穿透至用例；有些查询需要遍历并在应用内筛选 |
| frontend/src/features/settings/ModelSettings.tsx | 表单、查询、两种测试、状态和展示集中 | 当前体量可控，但后续新增图像选择、能力参数时应提取功能内 API、Hook 和组件 |
| frontend/tools/architecture-guard.mjs | 已检查功能色值和 UI/图标/动效供应商依赖 | 尚未约束 feature 间内部导入、后端模块边界与跨包依赖 |
| 多份架构/阶段文档，嵌套安装副本与研究工具 | 当前方案、历史方案与生成物并存 | 容易误读历史阶段或重复计算代码；发现问题时入口不明确 |

此次产品 application 对 infrastructure 有 9 个静态导入位置。目标是让这些变化点通过端口连接；创建具体实现的导入应集中到组合根。不能把所有层间 import 都判为错误。

## 3. 以业务划分模块

| 模块 | 拥有的数据与规则 | 对外提供的能力 |
| --- | --- | --- |
| identity | 用户、角色、密码散列、会话、启停用 | 认证、当前用户、账号管理 |
| cases | 案件、案件成员、案级访问规则、导入来源与版本标识 | 查询/创建案件、分享、检查读取或编辑权限 |
| evidence | 原件、哈希、存储位置、转录、页码/bbox、source refs | 上传、读取已授权原件、校验、转录、选取测试样本 |
| models | 用户模型配置、默认模型、加密凭据引用、能力与外发授权 | 配置管理、文本/图片连通性、模型调用端口 |
| analysis | Matter Pack、编译计划、运行、阶段、ProofGraph/矩阵投影 | 编译、执行、状态与事件、读取分析结果 |
| review | 对特定输出摘要作出的人工决定、编辑记录与审核失效规则 | 审核、查询审核状态、批准关卡 |

导入适配器负责外部格式转成内部请求；导入后的记录由上述模块拥有。未来导出成为独立业务能力时再形成 reporting 模块，不先建立空壳。

高内聚的判据：修改“连通性测试”主要进入 models 模块；新增证据格式主要进入 evidence 模块；人工审核规则的变化主要进入 review。低耦合的判据：跨模块只用公开契约或注入的端口，不读取对方私有表、存储路径或内部实现。

## 4. 推荐的架构与设计模式

这些模式承担不同层次的职责，不要求给每个文件套一组抽象。

| 模式 | 在本项目的落点 | 建议实施方式 |
| --- | --- | --- |
| 模块化单体 + 限界上下文 | 上述六个业务模块；产品仍保持当前部署规模 | 明确数据归属与公开接口，先保持单进程应用和现有存储。按业务职责分模块是本仓库的设计判断；[限界上下文说明](https://martinfowler.com/bliki/BoundedContext.html)解释了不同模型之间显式边界的价值 |
| Ports & Adapters + 构造器注入 | 模型服务、证据存储、持久化、运行引擎 | 用例依赖窄接口；bootstrap 注入具体客户端。这样 HTTP、CLI、自动测试可调用同一个用例。见[六边形架构原文](https://alistair.cockburn.us/hexagonal-architecture) |
| Strategy + 注册表 | 文本/图片测试策略，感知方式、模型协议和文件格式 | 在确有变化的算法处替换策略；注册能力到实现，业务代码按能力选择，不在案件服务里堆模型名称判断 |
| Application Service / Facade | CreateCase、UploadEvidence、TestConnectivity、StartAnalysis、ReviewOutput | 每个用例组织授权、数据读取、外部调用和提交；HTTP 层仅解析、调用、转换结果。Workspace 可临时保留为兼容门面，逐项转发给新用例 |
| Repository + Unit of Work | CaseRepository、EvidenceRepository、ModelConfigRepository、运行/审核提交 | 表达 get_owned_config、list_accessible_cases、commit_node_result 等有意义操作；由持久化适配器封装 SQL/JSON，并保留跨记录原子提交。见[Repository 模式](https://martinfowler.com/eaaCatalog/repository.html) |
| 显式状态机 + Pipeline/DAG | 已有 Run、Stage、Node、Gate、重试与审计 | 保留可恢复状态和幂等语义，把执行机制与 Skill 工厂、结果投影及存储隔开；扩展已有设计 |

领域事件可在后续用于非关键投影、通知和审计订阅。关键业务状态与节点输出仍显式调用并在事务中提交；只有确有可靠异步交付需求时再增加 outbox/worker。当前方案不需要把整套系统改成 Event Sourcing 或分布式服务。

## 5. 目标代码结构

先在现有 product_v1 路径内实现业务边界，保持运行与资源位置可用。小模块可先用数个文件，随着复杂度再扩为 domain/application 子目录。

~~~text
product_v1/backend/src/screenshotlegal/
  bootstrap.py                  # 唯一组合根：创建并注入具体实现
  api/app.py                    # FastAPI、中间件、路由挂载
  modules/
    identity/
    cases/
    evidence/
    models/
      public.py                 # 允许其他模块使用的契约/门面
      domain.py                 # 配置、能力和业务约束
      ports.py                  # 模型网关、凭据与仓储接口
      use_cases.py              # 配置管理与连通性用例
      http.py                   # 模型模块 HTTP 入站适配器
      adapters/                 # OpenAI 兼容客户端、加密与 SQL 实现
    analysis/
    review/
  integrations/
    agentic_adapter.py          # 未来可选，未实现；不预建空文件
  shared/                       # 少量稳定基础：ID、时钟、摘要
~~~

模块对外只暴露 public.py 或明确的 Protocol；其他模块不能通过 imports 访问其 adapters、私有 ORM 或内部服务。shared 不放 User、Case、ModelConfig，也不发展成通用业务容器。

前端沿用现有 features 模式，把模型功能收拢到 features/models：api.ts、useConnectivityTest.ts、ModelForm、ConnectivityPanel、TestImageSample。账户设置与案件共享各自归 identity/cases；UI primitives、设计 tokens 和通用反馈继续集中管理。服务端状态继续由 TanStack Query 持有，案件与页签选择继续使用 URL。

~~~mermaid
flowchart LR
  UI["React 功能页面 / HTTP / CLI"] --> UC["模块用例：案件、证据、模型、分析、审核"]
  UC --> DOMAIN["本模块领域规则"]
  UC --> PORTS["本模块端口与跨模块公开契约"]
  ADAPTERS["数据库 / 文件 / 模型服务 / 引擎适配器"] -. "实现" .-> PORTS
  BOOT["bootstrap 组合根"] --> UC
  BOOT --> ADAPTERS
~~~

图中是依赖方向；运行时由用例调用注入的适配器。领域规则不反向依赖数据库、FastAPI 或网络客户端。

仓库顶层的长期分类如下，仅作迁移后的目标；现有路径尚未调整：

~~~text
apps/workbench/                # 当前 product_v1
packages/agentic/              # 当前独立 agentic，保持包名与分发契约
research/pipelines/            # blocks、按任务分组的研究脚本与测试
datasets/                      # 版本化数据及来源资产
legacy/                        # legalhub 与历史工作台，保留兼容入口
references/                    # 经清点后归类 projects 中的参考/第三方项目
docs/                          # 当前入口、架构决策与历史索引
reports/                       # 有证据的验收和实验记录
configs/                       # 示例和配置结构；私密配置保持受控来源
var/                           # 将来配置化的运行数据与日志，不提交版本库
~~~

目录重命名是最后一步。Conda 前缀、SQLite/原件/主密钥、导入源路径、来源清单、相对链接及按 parents[n] 定位的代码都必须先完成兼容设计。环境应按锁文件重建，而不是假定移动 Conda 目录后仍可运行。

## 6. 第一块切入：把连通性测试做成独立用例

当前图片样本选择在 accounts.py，Preferences 创建具体 Provider 和 EvidenceStorage。刚增加的功能也应该纳入相同拆分标准。

建议把 TestConnectivityUseCase 作为首个完整切片，保留现有 HTTP 路径和返回结构：

1. 接收 Actor、ModelConfigId、mode 和可选样本标识。
2. 通过 ModelConfigRepository 获取该用户拥有的配置。
3. 检查模型能力和外发授权。
4. 图片模式通过 AuthorizedEvidenceReader 选取并读取有权限且完整的图片，返回明确来源标识。
5. TextProbe/ImageProbe 策略构造请求，通过 ModelGateway 执行。
6. 对响应进行本地校验，经 AuditWriter 保存脱敏审计，返回结果。

建议只抽取真正隔离变化的端口：ModelGateway、ModelConfigRepository、CredentialStore、AuthorizedEvidenceReader。现有两个分支仍可先用一个小策略函数实现，不必立即增加复杂工厂。

用例测试注入内存仓储与 FakeGateway，验证授权、选图、独立结果及不修改案件。HTTP 适配器测试检查序列化与认证；网络适配器测试使用 httpx.MockTransport，验证实际请求含图片。已有回归测试可沿用并逐步迁移。

Prompt 归模型模块，以版本化资源或常量管理；返回 prompt_version 并在审计记录摘要。是否从配置动态加载是独立的运维决策：当前 prompt 在后端代码里，需要重启；用户模型配置从数据库读取，保存后下次请求使用。

## 7. 两个 Runtime 的处理

目前产品 Runtime 面向 Matter Pack、CasePlan、SkillManifest、七阶段 DAG、ProofGraph、证据关系和审核摘要；agentic 包是独立的五阶段文本推理 Harness，带不同的 Principal、Run、Review、预算、恢复和报告契约。

产品继续拥有案件权限、原件、转录、ProofGraph 与人工审核。将来如需使用 agentic，由产品的 AnalysisEngine 端口通过适配器显式转换已授权、已转写的文本及来源 ID，调用它的公开 SDK；由产品负责把经过校验的输出转换成自己的视图。

启用另一种引擎前必须验证：阶段与输出映射不丢失、source refs 与原文保持、权限和外发授权一致、预算与超时有效、取消/恢复/Gate/审核语义可解释、历史 Run 仍可打开。五阶段和七阶段不能机械对号入座，也不能让两个 Runtime 同时修改同一条运行记录。

agentic 保持独立安装与测试，不导入产品的数据库、FastAPI 应用或仓储实现。模型协议可通过适配器共用低层通信能力，但用户凭据、预算和权限策略由各自宿主掌握。

## 8. 渐进迁移与验收

迁移采用逐项替换并保留兼容入口的方式，参考[Strangler Fig 渐进现代化](https://martinfowler.com/bliki/StranglerFigApplication.html)。以下是执行顺序，不是已完成的代码迁移。

| 顺序 | 具体工作 | 验收条件 |
| --- | --- | --- |
| 1：形成基线 | 固化目录职责、功能地图、公开入口和现有测试；建立独立恢复点，记录运行库数量与原件哈希 | 新旧产品、agentic 均能按各自说明启动；来源/版本计数有明确口径 |
| 2：模型连通性切片 | 提取 TestConnectivityUseCase、授权图片读取与 ModelGateway；将路由缩为适配层 | URL 和 JSON 契约兼容；文本/图片、反复测试、无密钥、无外发授权、越权与文件篡改回归通过 |
| 3：案件/证据与持久化 | 从 Workspace/Auth 拆出案件授权、上传与转录用例；增加有业务语义的 Repository/UoW | 原子导入、原件不变、来源/坐标保留、用户隔离、重复导入幂等；既有案件和运行可读取 |
| 4：运行与审核 | 提取纯摘要逻辑，注入 Skill 工厂、快照写入和投影端口，保留既有状态机 | 节点输出与审计同事务；SSE、失败重试、Gate、审核失效与重启行为保持 |
| 5：可选引擎接入 | 在明确需要时实现 agentic 适配器并完成逐项语义映射 | 独立包契约测试、来源追踪与预算/授权回归通过；无共享私有表 |
| 6：物理目录整理 | 有 manifest 地迁移 apps/packages/research 等路径；配置化运行目录；更新脚本与文档 | 逐个入口 smoke、资源哈希/数量一致、旧路径兼容和回滚可用 |

本次运行库只读核实共有 2,687 条案件/版本记录，均归 admin。它们含历史版本与来源档案，不能当作 2,687 个独立真实案件。迁移验收要按来源与版本比对，不能沿用早期 5 条 Demo 的规模假设。

数据迁移时一起验证 SQLite、原件文件与 data/.credentials/model-master.key 的一致性；密钥明文不进入审计输出。先保留数据布局，再切换配置化路径。

## 9. 把边界写成可执行检查

- domain 禁止导入 FastAPI、SQLAlchemy、httpx、文件存储和应用服务。
- 用例依赖端口；具体适配器由 bootstrap 注入。迁移期间现有例外记录在显式清单中，逐片收紧。
- 模块只能引用其他模块公开契约；禁止跨模块读写私有表或导入 adapters。
- runtime 核心不导入高层应用服务或内建 Skill 的具体类。
- 当前 agentic 源码保持独立性；架构扫描排除 .runtime、安装副本、生成物和历史版本。
- 前端 feature 只能通过公开 API 使用另一功能；组件不得直接依赖供应商 SDK。
- 数据库结构、API/OpenAPI、模型协议和导入格式分别做契约校验；关键权限在用例内再次验证。

这些是目标检查规则，尚未作为 CI 脚本实施。现有前端 architecture-guard 仅覆盖色值和 UI 厂商依赖，不能当作已满足全部边界。

## 10. 核查证据与参考

- [可复核静态清单](../../reports/architecture_audit_20261024/source_inventory.json)：产品运行源码 40 文件/2,206 行；agentic 29 文件/2,246 行；旧 legalhub 15 文件/3,167 行。排除隐藏目录、tests/reports/build/dist；前端另排生成 schema 和测试。行数仅说明审计范围。
- [审计脚本](../../reports/architecture_audit_20261024/audit_source.py)：从仓库根目录运行，仅读取 Python/前端源码，不读取本地模型 YAML、密钥或案件正文。
- [产品现有架构](../../product_v1/docs/ARCHITECTURE.md)、[运行语义](../../product_v1/docs/RUNTIME.md)。
- [agentic 独立化约束](../../agentic/docs/10-standalone-reasoning.md)、[当前架构](../../agentic/docs/04-architecture.md)。
- [当前资产入口](../ai_docs_center/ADMIN_CASES.md)与[已有导入说明](../../product_v1/docs/MIGRATION.md)。

本轮没有执行模块代码搬迁、数据迁移或服务重启；架构判断基于静态源码和现有行为记录，没有把此前测试结果作为本次新测试。最终方案优先缩小变化影响范围，再调整目录布局。
