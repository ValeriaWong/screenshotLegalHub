# ScreenshotLegal Product v1.1 Implementation Specification

**状态：Implementation Contract**  
**用途：直接交付 Codex 实现**  
**替代文档：此前 Product v1.0.0 实施规格**  
**目标目录：`screenshotLegalHub/product_v1/`**

---

# 1. 本文档的约束级别

本文档是本轮产品实现规范，不是讨论稿。

Codex 必须：

1. 实际创建代码；
2. 实际建立数据库；
3. 实际启动前后端；
4. 实际运行测试；
5. 实际跑通 Demo；
6. 实际记录环境、踩坑和验证结果。

禁止只创建：

- 空目录；
- TODO；
- 伪代码；
- 无实现接口；
- 没跑过的 README 命令；
- 声称“理论上可以”的验收报告。

---

# 2. 非破坏式开发原则

当前仓库保存历史 Benchmark、旧工作台、数据飞轮和论文实验。

新实现必须位于：

```text
screenshotLegalHub/
├── existing files...
└── product_v1/
```

默认不得：

- 删除旧目录；
- 移动旧目录；
- 改写历史实验；
- 让新产品运行时依赖旧 `legalhub`；
- 覆盖旧报告；
- 把历史 Benchmark 混入新产品。

允许：

```text
阅读旧代码
↓
提炼逻辑
↓
在 product_v1 中重新实现
```

`product_v1/` 最终应能够单独拆成：

```text
ScreenshotLegal
```

独立仓库。

---

# 3. 产品定位

ScreenshotLegal 是：

> Evidence-centric Legal Workflow Runtime

中文定义：

> 以电子证据为核心，通过版本化法律 Matter Pack、可插拔 Legal Skills、可审计运行时和 Proof Graph 完成案件事实—请求权—待证事实—证据—举证责任—策略分析。

第一阶段重点：

```text
微信聊天截图
```

架构不得绑定：

```text
微信-only
```

未来必须允许：

```text
PDF
合同
银行流水
邮件
聊天导出
音视频转写
图片
其他电子证据
```

进入同一 Evidence Core。

---

# 4. 六个核心概念

必须严格区分：

```text
Evidence
    证据客观出现了什么

Matter Pack
    某法律领域要求分析、证明什么

Skill
    某项分析能力如何执行

CasePlan
    当前案件将执行什么

ProofGraph
    当前案件已经形成了什么分析结构

Runtime
    以什么顺序、什么上下文执行 Skills
```

另外：

```text
Review
```

表示：

> 人类最终接受、编辑或拒绝了什么。

任何一个模块如果同时承担 3 个以上上述职责，应优先拆分。

---

# 5. 总体系统架构

```text
                       ScreenshotLegal

┌──────────────── Evidence Plane ────────────────┐
│ EvidenceItem                                   │
│ EvidenceImage                                  │
│ Message                                        │
│ Event                                          │
│ SourceRef                                      │
└──────────────────────┬─────────────────────────┘
                       │
                       ▼
┌──────────────── Legal Knowledge Plane ─────────┐
│ Matter Registry                                │
│ Claim Templates                                │
│ Legal Element Templates                        │
│ Fact Question Templates                        │
│ Burden Rules                                   │
│ Defenses                                       │
│ Authorities                                    │
│ Typical Patterns                               │
└──────────────────────┬─────────────────────────┘
                       │
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   Matter Registry                Skill Registry
                                      │
                                      ▼
                                Skill Resolver
        └──────────────┬──────────────┘
                       ▼
                  Case Compiler
                       ▼
                    CasePlan
                       ▼
┌──────────────── Runtime Plane ─────────────────┐
│ Stage Executor                                 │
│ Context Projection                             │
│ Retry / Idempotency                            │
│ Review Gates                                   │
│ SSE Event Stream                               │
│ State Snapshot                                 │
└──────────────────────┬─────────────────────────┘
                       ▼
                  ProofGraph
                       │
            ┌──────────┼────────────┐
            ▼          ▼            ▼
        Timeline   Proof Matrix   Strategy
                       │
                       ▼
                    Review
                       │
                       ▼
                 Frontend UI
```

---

# 6. 借鉴 Holmes 的范围

本项目可以借鉴 Holmes 的：

```text
stage-isolated execution
database-backed inter-stage state
config-driven workers
parallel stages
HITL
SSE progress
state snapshot/reconnect
app-wide detail sidebar
source navigation
citation interaction
timeline
evidence gaps
contradictions
knowledge/proof graph interaction
analysis DAG visualization
loading/error/empty states
design-token based theming
```

但不得把 Holmes 的：

```text
investigation workflow
agent角色设计
品牌
视觉语言
Logo
调查术语
```

直接变成本产品核心。

本项目对应关系：

```text
Holmes Hypothesis
→ Claim / Fact Proposition

Holmes Evidence Gap
→ Evidence Gap

Holmes Verdict
→ Overview + Strategy

Holmes Knowledge Graph
→ Legal Proof Graph

Holmes Source Viewer
→ ScreenshotLegal Source Viewer

Holmes Agent Flow
→ Advanced Analysis Run DAG
```

---

# 7. Holmes 源码使用边界

第一版默认：

> 只参考架构、信息架构和交互模式，不复制 Holmes 前端源文件。

必须增加：

```text
docs/HOLMES_REFERENCE.md
```

记录：

```text
参考了哪些概念
哪些内容是独立实现
是否复制任何代码
是否产生 Apache-2.0 attribution requirement
```

如果 Codex 实际复制任何 Holmes 源代码：

必须：

```text
保留 Apache-2.0
记录具体文件
记录原始路径
标注修改
更新 THIRD_PARTY_NOTICES.md
```

---

# 8. 第一版 Matter

v1 只要求完整走通：

```text
cn.civil.private_lending
```

即：

```text
中国
└── 民事
    └── 民间借贷
```

新增第二个 Matter 时必须主要增加数据文件。

如果新增：

```text
sale_contract
```

需要复制大量 Python Skill：

> 架构视为不合格。

---

# 9. 双维 Schema

系统存在两个正交 Registry：

```text
Matter Registry
+
Skill Registry
```

禁止建立：

```text
案由 × Skill
```

的大型二维实现表。

---

# 10. Matter Pack 职责

Matter Pack 只描述：

```text
Matter
Claim
Legal Element
Fact Question
Burden Rule
Expected Evidence
Defense
Authority
Typical Pattern
```

Matter Pack：

- 不调用模型；
- 不访问数据库；
- 不直接运行 Skill；
- 不保存 Python class；
- 不保存 UI 组件；
- 不直接指定 executor。

---

# 11. Matter Pack 目录

固定：

```text
product_v1/matterpacks/

├── _template/
│
└── cn/
    └── civil/
        └── private_lending/
            └── 1.0.0/
                ├── manifest.yaml
                ├── claims.yaml
                ├── patterns.yaml
                ├── authorities.yaml
                └── tests.yaml
```

---

# 12. Matter Manifest

至少：

```yaml
id: cn.civil.private_lending

name_zh: 民间借贷
name_en: Private Lending

jurisdiction: CN
practice_area: civil

version: 1.0.0
schema_version: 1

status: draft

valid_from: null
valid_to: null

expert_review:
  status: unreviewed
  reviewed_by: null
  reviewed_at: null

required_capabilities:
  - claim.identify
  - fact.instantiate
  - burden.assign
  - evidence.map
  - evidence.strength
  - evidence.gap
  - contradiction.detect
  - strategy.generate
  - strategy.verify
  - adversarial.analyze
```

必须计算：

```text
MatterPack SHA256 digest
```

---

# 13. Matter Pack 法律状态

所有 Pack 必须显示：

```text
draft
reviewed
deprecated
```

UI 中：

```text
draft / unreviewed
```

必须有明显状态提示。

不能让用户把：

```text
AI草稿规则
```

误认为：

```text
已经律师审核的正式规则。
```

---

# 14. Authority 状态

Authority 至少：

```text
id
type
title
article
jurisdiction
valid_from
valid_to
source_url
source_digest
verification_status
```

verification：

```text
verified
unverified
expired
unknown
```

LLM 生成的 authority：

```text
不得自动进入 verified
```

---

# 15. Typical Pattern

Patterns 是：

```text
实务经验模式
```

而非：

```text
法律规则
```

必须在 Schema 和 UI 中区别。

例如：

```yaml
id: transfer_plus_acknowledgment

signals:
  - bank_transfer
  - repayment_acknowledgment

usually_supports:
  - agreement
  - delivery

risks:
  - investment_defense
```

Pattern 只能辅助：

```text
routing
evidence search
risk reminder
```

不能直接决定法律结论。

---

# 16. Template 与 Case Instance

必须区分：

```text
FactQuestionTemplate
```

例如：

```text
双方是否形成借贷合意？
```

与：

```text
FactProposition
```

例如：

```text
张三与李四是否于2024年1月就5万元形成借贷合意？
```

Matter Pack 只包含 Template。

Case 才包含 Proposition。

---

# 17. Skill Schema

Skill 代表：

```text
能力
```

而不是：

```text
Agent角色。
```

v1 capability：

```text
matter.route
claim.identify
fact.instantiate
burden.assign
evidence.map
evidence.strength
evidence.gap
contradiction.detect
timeline.build
strategy.generate
strategy.verify
adversarial.analyze
```

---

# 18. Skill Manifest

必须统一：

```yaml
id: evidence.map.generic.v1

capability: evidence.map

version: 1.0.0
schema_version: 1

executor_type: python

applies_to:
  jurisdictions:
    - "*"

  matters:
    - "*"

input_schema:
  - fact_propositions
  - evidence
  - events
  - messages

output_schema:
  - evidence_links

grounding:
  require_source_refs: true

dependencies:
  - fact.instantiate

side_effects: false

trust:
  level: builtin

permissions:
  network: false
  filesystem_write: false
  model: true
  retrieval: true
```

---

# 19. Skill Trust Model

这是 v1.1 新增的强制要求。

Skill trust：

```text
builtin
trusted
external_untrusted
```

默认：

```text
external_untrusted
```

不得执行。

第三方 Skill 只有进入 allowlist 后才能执行。

v1 不要求实现真正 OS sandbox。

因此：

> 不可信第三方 Python Skill 默认禁止加载。

---

# 20. Skill Permissions

Manifest 必须声明：

```text
network
filesystem_read
filesystem_write
model
retrieval
authority_search
```

Runtime 在运行前校验。

不要假设 Manifest 本身能实现真正安全隔离。

其目标是：

```text
policy enforcement + audit
```

---

# 21. Skill Interface

统一：

```python
class LegalSkill:

    manifest: SkillManifest

    async def run(
        self,
        context: SkillContext,
        input: SkillInput,
    ) -> SkillResult:
        ...
```

Skill：

- 不操作 FastAPI；
- 不直接修改 UI；
- 不直接修改 Matter Pack；
- 默认不直接 commit DB；
- 返回 typed output。

数据库更新由 Application Services 完成。

---

# 22. Skill Resolver

优先级固定：

```text
1 explicit run override
2 matter-specific
3 jurisdiction / practice-area
4 generic
```

同一级多个候选：

```text
CompileError
```

禁止：

```text
随机选择
最后注册覆盖
```

---

# 23. Analysis Profile

例如：

```yaml
id: cn_civil_default

capabilities:

  claim.identify:
    skill: claim.identify.generic.v1

  fact.instantiate:
    skill: fact.instantiate.generic.v1

  burden.assign:
    skill: burden.assign.matter_rules.v1

  evidence.map:
    skill: evidence.map.generic.v1

  evidence.strength:
    skill: evidence.strength.generic.v1

  evidence.gap:
    skill: evidence.gap.generic.v1

  contradiction.detect:
    skill: contradiction.generic.v1

  strategy.generate:
    skill: strategy.cn_civil.v1

  strategy.verify:
    skill: strategy.verify.generic.v1

  adversarial.analyze:
    skill: adversarial.cn_civil.v1
```

---

# 24. CasePlan

CasePlan 至少：

```text
case_id
matter_pack_id
matter_pack_version
matter_pack_digest

analysis_profile
analysis_profile_digest

nodes
edges

compiled_at
plan_digest
```

每个 node：

```text
node_id
stage
capability
resolved_skill_id
resolved_skill_version
skill_digest

depends_on

input_selectors
output_targets

required
review_gate

retry_policy
```

---

# 25. Stage 概念

v1.1 必须增加显式 Stage。

推荐：

```text
Stage 1  perception

Stage 2  timeline

Stage 3  matter_and_claim

Stage 4  facts_and_burden

Stage 5  evidence_analysis

Stage 6  contradiction_and_gap

Stage 7  strategy

Stage 8  verification
```

同 Stage 内无依赖节点可以并发。

---

# 26. Stage-isolated Execution

这是从 Holmes 借鉴的重要设计。

原则：

> 每个 Skill 只获得执行它所需要的 Context Projection。

禁止：

```text
第1个模型的完整prompt
+
第2个完整conversation
+
第3个完整conversation
……
持续累积
```

---

# 27. Context Projection

实现：

```text
runtime/context_projection.py
```

每个 Skill Manifest 或 executor 定义：

```text
needs
```

例如：

```text
evidence.map
```

可以获取：

```text
FactPropositions
Evidence
Messages
Events
Matter Element
```

但不应该默认得到：

```text
其他 Skill 的所有 raw model response
完整隐藏历史 prompt
```

---

# 28. Inter-stage Handoff

Stage 之间通过：

```text
Database
+
ProofGraph state
```

传递结果。

不通过：

```text
共享无限增长 LLM conversation
```

这项要求必须有测试。

---

# 29. Runtime Node 状态

统一：

```text
PENDING
RUNNING
WAITING_REVIEW
COMPLETED
FAILED
SKIPPED
INTERRUPTED
```

不要只用：

```text
running / done
```

---

# 30. Node Idempotency

每个 node 保存：

```text
input_digest
skill_digest
matter_digest
```

计算：

```text
idempotency_key
```

同一 AnalysisRun 中：

```text
same node
+
same input_digest
+
same skill_digest
```

不得重复创建语义相同输出。

---

# 31. Retry Policy

Node：

```text
max_attempts
retryable_errors
backoff
```

模型 JSON parse failure 可以有限重试。

以下默认不得无限重试：

```text
schema incompatibility
permission denied
missing authority
invalid Matter Pack
```

---

# 32. Analysis Run

保存：

```text
analysis_run_id
case_id

matter_pack_id
matter_pack_version
matter_pack_digest

analysis_profile
analysis_profile_digest

case_plan_digest

model_config_snapshot

started_at
completed_at

status
```

新运行：

```text
新 AnalysisRun
```

禁止覆盖历史运行。

---

# 33. SkillRun

保存：

```text
skill_run_id
analysis_run_id
node_id

stage
attempt

skill_id
skill_version
skill_digest

input_digest
output_digest

status

latency
token_usage

warnings
error
```

---

# 34. ReviewGate

v1.1 新增正式 HITL Gate。

至少支持：

```text
matter-selection gate
compile-review gate
optional critical-finding gate
```

默认产品流程：

```text
Matter candidate
↓
用户选择

Compile
↓
用户可以查看计划
↓
Run
```

测试模式可以：

```text
AUTO_APPROVE_GATES=true
```

---

# 35. Low-confidence 处理

禁止把：

```text
confidence < x
```

直接视为错误法律结论。

Skill 可以产生：

```text
requires_review: true
```

或：

```text
warnings
```

关键结论可以进入：

```text
WAITING_REVIEW
```

---

# 36. ProofGraph

ProofGraph 仍然是产品中心。

```text
Evidence
    ↓
Message
    ↓
Event
    ↓
Fact Proposition
    ↓
Legal Element
    ↓
Claim
    ↓
Remedy
```

关系：

```text
Burden
Defense
EvidenceLink
Authority
EvidenceGap
Contradiction
StrategyItem
```

---

# 37. 高层结论必须消费 ProofGraph

Strategy / Summary / Adversarial：

不得绕过 ProofGraph 直接：

```text
重新读取所有聊天
→ 自由生成完全不同事实
```

它们的结构化输入必须来自：

```text
ProofGraph projection
```

如果需要访问原始证据：

必须通过：

```text
SourceRef
```

---

# 38. EvidenceLink

至少：

```text
id
fact_id
evidence_id

relation
strength

rationale

source_refs

analysis_run_id
skill_run_id

review_status
```

relation：

```text
supports
contradicts
context
identity
timeline
```

strength：

```text
strong
medium
weak
unknown
```

不把模型概率包装成法律概率。

---

# 39. Review 状态

业务状态：

```text
proposed
supported
contradicted
mixed
unknown
not_applicable
```

Review 状态：

```text
unreviewed
verified
edited
rejected
deferred
stale
```

二者完全分离。

---

# 40. Review Staleness

这是 v1.1 新增强制能力。

每个 Review 保存：

```text
reviewed_output_digest
```

如果重新运行后：

```text
current_output_digest
!=
reviewed_output_digest
```

则旧 Review：

```text
自动显示 stale
```

禁止让：

```text
上一版AI输出的人审确认
```

静默继承给：

```text
新AI输出。
```

---

# 41. Evidence Core

至少：

```text
Case
Party
EvidenceItem
EvidenceImage
Message
Event
SourceRef
Reconciliation
LawyerAssessment
```

继续采用：

```text
source-grounded
```

设计。

---

# 42. SourceRef

核心：

```text
image_id
evidence_page
message_id
bbox
quote
```

bbox：

```text
原图 pixel coordinate
```

额外：

```text
raw_bbox
raw_coordinate_space
```

禁止猜测坐标协议。

---

# 43. Evidence Storage

上传时：

```text
计算 SHA256
验证 MIME
验证文件大小
标准化安全扩展名
不信任用户 filename 作为路径
```

保存：

```text
data/uploads/<case_id>/<sha256>.<ext>
```

原文件默认不可修改。

---

# 44. 文件安全限制

配置：

```text
MAX_UPLOAD_BYTES
ALLOWED_MIME_TYPES
```

必须阻止：

```text
../ path traversal
绝对路径写入
任意服务器文件读取
```

---

# 45. Local-first Security

v1 默认：

```text
127.0.0.1
```

绑定。

默认：

```text
无认证
仅本地单用户
```

如果用户设置：

```text
HOST=0.0.0.0
```

启动时明确警告：

```text
当前 v1 未配置生产认证机制。
```

---

# 46. External Model Policy

默认：

```text
ENABLE_REAL_MODEL=false
ALLOW_EXTERNAL_EGRESS=false
```

必须显式开启。

每个外部模型调用记录：

```text
run_id
provider
model
timestamp
evidence_ids
```

不得保存 Key。

---

# 47. Perception Adapter

接口：

```text
EvidenceItem
↓
NormalizedPerceptionResult
```

v1：

```text
MockPerceptionAdapter
ManualFixtureAdapter
OpenAICompatibleVisionAdapter
```

可预留：

```text
OCRStructuredAdapter
```

---

# 48. 无 Key Demo

必须做到：

```text
没有网络
没有模型 Key
```

也可完成：

```text
完整 Demo。
```

依靠：

```text
Mock perception
Deterministic test skills
Fake model provider
```

---

# 49. Retrieval

案件检索继续代码实现：

```text
SQLite FTS5
BM25
```

负责：

```text
人物
关键词
事件
消息
时间
```

输出：

```text
result + SourceRef
```

Retriever：

```text
不生成法律答案。
```

---

# 50. AppShell

这是 v1.1 新增强制 UI 架构。

页面统一运行在：

```text
AppShell
```

结构：

```text
┌───────────────────────────────────────────────────────────┐
│ Case Header                                               │
├─────────────┬───────────────────────────┬─────────────────┤
│             │                           │                 │
│ Navigation  │      Main Workspace       │   DetailRail    │
│             │                           │                 │
│             │                           │                 │
└─────────────┴───────────────────────────┴─────────────────┘
```

DetailRail 是整个应用共享组件。

---

# 51. DetailRail

借鉴 Holmes 的成熟模式，但独立实现。

统一：

```ts
type DetailContentDescriptor =
  | SourceDetail
  | EvidenceDetail
  | MessageDetail
  | EventDetail
  | ClaimDetail
  | FactDetail
  | GapDetail
  | ContradictionDetail
  | StrategyDetail
  | SkillRunDetail;
```

任何 Feature：

```text
不得自己创建永久性的右侧详情栏。
```

统一：

```text
detailRail.open(descriptor)
```

---

# 52. DetailRail 功能

必须支持：

```text
open
close
collapse
resize
```

宽度保存在：

```text
local UI preference
```

页面切换时：

允许保持或合理清空。

---

# 53. CitationDescriptor

统一前端 citation：

```ts
interface CitationDescriptor {
  sourceRefId: string;
  evidenceId: string;

  imageId?: string;
  messageId?: string;

  page?: number;
  bbox?: [number, number, number, number];

  quote?: string;
}
```

所有页面：

```text
Timeline
Proof Matrix
Claims
Strategy
Contradictions
Review
```

统一消费 Citation。

---

# 54. Source Navigation

建立：

```text
frontend/src/features/source-navigation/
```

职责：

```text
CitationDescriptor
↓
resolve evidence
↓
get file URL
↓
construct ViewerContent
↓
open DetailRail / Viewer
```

禁止：

```text
Timeline自己写SourceViewer
Proof Matrix再写一套
Strategy再写第三套
```

---

# 55. Source Viewer

v1 重点图片。

架构必须支持：

```text
image
pdf
audio
video
```

ViewerContent：

```text
type
url
filename
page
timestamp
bbox
highlightText
```

图片：

```text
显示 bbox 高亮。
```

无 bbox：

```text
正常显示整图。
```

---

# 56. Frontend Information Architecture

一级：

```text
Overview
Evidence
Timeline
Claims
Proof Matrix
Contradictions
Evidence Gaps
Strategy
Review
Advanced
```

Proof Matrix 是一等页面。

Graph 为 P1。

---

# 57. Overview

显示：

```text
Matter
Matter review status
Matter version

Claims
Facts

supported
contradicted
unknown
gaps

pending review

latest run

next actions
```

---

# 58. Timeline

P0 可以使用：

```text
vertical timeline
```

但数据/API 不能绑定布局。

必须支持：

```text
filter by event type
filter by party
filter by review status
date range
```

未来可以替换：

```text
horizontal timeline
zoom timeline
```

而不改变 Timeline domain types。

---

# 59. Claims

层级：

```text
Claim
└── Legal Element
    └── Fact Proposition
```

显示：

```text
status
burden
support count
contradiction count
gap count
review
```

---

# 60. Proof Matrix

核心产品页面。

列：

```text
Claim
Legal Element
Fact Proposition
Burden

Supporting Evidence
Contradicting Evidence

Evidence Gap
Strength
Review Status
```

数据：

```text
只能来自 ProofMatrix API。
```

禁止让前端自己推导法律关系。

---

# 61. Contradictions

显示：

```text
Fact A
Fact B
Evidence A
Evidence B

Conflict Type
Severity

Review
```

点击任何来源：

```text
统一 Source Navigation。
```

---

# 62. Evidence Gaps

显示：

```text
Claim
Element
Fact

Missing Item
Why Needed
Suggested Evidence Type
Priority

Source / rule basis
```

---

# 63. Strategy

结构化：

```text
StrategyItem
title
description

supporting_fact_ids
risk_fact_ids
gap_ids
counterargument_ids

source_refs

review_status
```

---

# 64. Review Workspace

Review 不是普通表格。

布局建议：

```text
左：
review queue

中：
AI decision + related context

右：
DetailRail / Source evidence
```

Actions：

```text
verify
edit
reject
defer
```

---

# 65. Advanced

借鉴 Holmes Command Center 的成熟信息结构。

展示：

```text
AnalysisRun
CasePlan
Stage groups
Node status
Skill
attempt
latency
tokens
warnings
error
input/output digest
```

不展示：

```text
hidden chain-of-thought。
```

---

# 66. Run DAG

节点视觉：

```text
pending
running
waiting_review
completed
failed
skipped
interrupted
```

必须：

```text
状态不仅用颜色表达
```

同时显示 icon/text。

---

# 67. SSE

事件：

```text
run-started

stage-started
node-started
node-progress
node-completed
node-failed

review-required
review-resolved

stage-completed
run-completed
run-failed

state-snapshot
```

---

# 68. SSE Reconnect

这是 v1.1 新增强制要求。

Client 重连：

```text
GET events
```

服务端首先返回：

```text
state-snapshot
```

snapshot 从：

```text
AnalysisRun
SkillRuns
```

重建。

不能依赖：

```text
浏览器曾经收到哪些旧 event。
```

---

# 69. Loading / Error / Empty / Disabled

所有主要页面必须显式实现：

```text
loading
empty
error
ready
stale
disabled/not-run
```

不得：

```text
空白页面
```

作为状态处理。

---

# 70. Design System Boundary

这是保证未来换 UI 的核心。

前端四层：

```text
design tokens
↓
UI primitives
↓
application components
↓
features
```

---

# 71. Design Tokens

至少：

```text
foundation tokens

semantic tokens

component tokens

motion tokens
```

Foundation：

```text
font
spacing
radius
shadow
z-index
```

Semantic：

```text
background
surface
text
muted
border
primary

success
warning
danger
info
ai
```

---

# 72. Feature 禁止硬编码视觉值

`features/**` 默认禁止：

```text
#1A2B3C
rgb(...)
具体品牌色
```

业务状态应使用：

```text
status-supported
status-contradicted
status-warning
```

语义 token。

---

# 73. UI Library Adapter Boundary

未来用户可能更换 UI 库。

因此：

```text
features/
```

禁止大量直接 import 第三方 UI library。

例如：

```text
features
↓
components/ui/Button
```

而不是：

```text
features
↓
直接 import SomeUILibrary.Button
```

第三方 UI 库只应该集中在：

```text
components/ui/
```

---

# 74. Icon Boundary

统一：

```text
components/icons/
```

业务页面不应该遍地绑定某特定 icon 库。

---

# 75. Motion Boundary

未来可能加入：

```text
parallax
scroll reveal
page transition
```

必须集中：

```text
visual-effects/
```

或：

```text
components/motion/
```

业务数据逻辑：

```text
不得依赖动画是否开启。
```

---

# 76. Reduced Motion

所有未来动画必须遵循：

```text
prefers-reduced-motion
```

提供：

```text
motion.enabled
motion.reduced
```

设计 token / hook。

---

# 77. UI 风格 v1

默认：

```text
light
simple
professional
document-oriented
```

避免：

```text
Holmes同款黑色调查界面
霓虹
赛博风
```

重点是：

```text
清楚
稳定
高密度法律信息
```

---

# 78. Accessibility

至少满足：

```text
keyboard navigation
visible focus
aria labels
semantic table
dialog focus management
contrast roughly WCAG AA
reduced motion
not color-only state
```

E2E 增加基本 accessibility smoke。

---

# 79. Internationalization

v1 必须：

```text
zh-CN
en
```

所有 UI 固定文案：

```text
不得散落硬编码。
```

放：

```text
frontend/src/i18n/
```

Matter 本身：

```text
name_zh
name_en
```

---

# 80. Frontend State Ownership

Server state：

```text
TanStack Query
```

URL state：

```text
selected tab
filters
search
date range
```

DetailRail 等 UI shell 状态：

```text
Context / local store
```

禁止：

```text
把全部后端 Case 数据复制进大型全局 frontend store。
```

---

# 81. Backend 架构

固定：

```text
domain
application
plugins
infrastructure
api
```

依赖方向：

```text
domain
↑
application
↑
plugins/infrastructure
↑
api
```

Domain 不能 import FastAPI、SQLAlchemy model、UI。

---

# 82. 后端目录

```text
product_v1/backend/

├── pyproject.toml
├── alembic.ini
├── alembic/
│
└── src/screenshotlegal/

    ├── settings.py
    ├── logging.py

    ├── domain/
    │   ├── common/
    │   ├── evidence/
    │   ├── legal/
    │   └── runtime/

    ├── application/
    │   ├── ports/
    │   └── services/

    ├── plugins/
    │   ├── matterpacks/
    │   ├── skills/
    │   └── perception/

    ├── runtime/
    │   ├── executor.py
    │   ├── stage_executor.py
    │   ├── context_projection.py
    │   ├── retry.py
    │   ├── idempotency.py
    │   ├── review_gate.py
    │   └── events.py

    ├── infrastructure/
    │   ├── db/
    │   ├── storage/
    │   ├── retrieval/
    │   ├── model/
    │   └── jobs/

    ├── api/
    │   ├── main.py
    │   ├── dependencies.py
    │   └── routers/

    ├── cli/

    └── prompts/
```

---

# 83. Database

默认：

```text
SQLite
SQLAlchemy 2
Alembic
```

主要表：

```text
cases
parties

evidence_items
messages
events
source_refs

matter_selections

analysis_runs
skill_runs

case_claims
case_elements
fact_propositions
burden_assignments

evidence_links
evidence_gaps
contradictions
strategy_items

review_decisions

analysis_snapshots
```

---

# 84. Immutable Run Results

AnalysisRun 结果逻辑上 immutable。

新 Run：

```text
产生新 rows / snapshot
```

当前 Case：

```text
active_analysis_run_id
```

指向当前视图。

禁止让第二次运行：

```text
破坏第一次实验结果。
```

---

# 85. API

前缀：

```text
/v1
```

至少：

```text
GET /health
GET /version

POST /cases
GET /cases
GET /cases/{id}

POST /cases/{id}/evidence
GET /cases/{id}/evidence

POST /cases/{id}/perception/runs

GET /cases/{id}/matter-candidates
PUT /cases/{id}/matter-selection

POST /cases/{id}/analysis/compile
GET /cases/{id}/case-plan

POST /cases/{id}/analysis/runs

GET /runs/{run_id}
GET /runs/{run_id}/events

POST /runs/{run_id}/review-gates/{gate_id}

GET /cases/{id}/proof-graph
GET /cases/{id}/proof-matrix

GET /cases/{id}/timeline
GET /cases/{id}/claims
GET /cases/{id}/contradictions
GET /cases/{id}/gaps
GET /cases/{id}/strategy

POST /cases/{id}/reviews

GET /matter-packs
GET /skills
```

---

# 86. OpenAPI

FastAPI 自动 OpenAPI。

Frontend TS 类型：

```text
由 OpenAPI 生成或单源同步。
```

禁止维护：

```text
backend interface A
frontend interface B
```

两个手写版本。

---

# 87. Demo

必须有：

```text
fixtures/demo_private_lending/
```

完全合成。

至少：

```text
2 images
4 messages
3 events

1 supporting link
1 contradiction
1 gap

4 fact propositions
1 strategy
```

并包含真实可点击 bbox。

---

# 88. Demo Flow

```text
create case
↓
load fixture
↓
perception
↓
select private_lending
↓
compile
↓
run
↓
ProofGraph
↓
ProofMatrix
↓
click citation
↓
open image bbox
↓
review
↓
new run
↓
old review becomes stale when output changes
```

---

# 89. Legacy Import

增加：

```text
tools/import_legacy_case.py
```

至少转换：

```text
Case
EvidenceImage
Message
Event
SourceRef
```

导入后运行：

```text
完全不依赖旧 legalhub。
```

---

# 90. Benchmark Boundary

产品：

```text
稳定 API
```

Benchmark：

```text
外部 Adapter
```

Benchmark 不知道内部：

```text
OCR
VLM
Skill
Agent
Workflow
```

只知道：

```text
配置
输入
输出。
```

---

# 91. Runtime Profiles

允许未来：

```text
raw_vlm
ocr
ocr_structured
structured

single_agent
workflow
multi_agent
adversarial
```

但 v1 默认：

```text
deterministic staged workflow
```

---

# 92. Frontend 目录

```text
frontend/src/

├── app/

├── components/
│   ├── ui/
│   ├── icons/
│   ├── shell/
│   ├── motion/
│   └── feedback/

├── features/
│   ├── cases/
│   ├── evidence/
│   ├── timeline/
│   ├── claims/
│   ├── proof-matrix/
│   ├── contradictions/
│   ├── gaps/
│   ├── strategy/
│   ├── review/
│   ├── runs/
│   └── source-navigation/

├── api/
├── hooks/
├── i18n/
├── design-system/
└── styles/
```

---

# 93. Frontend Error Boundaries

Feature-level：

```text
Evidence
Timeline
Proof Matrix
Review
Advanced
```

不得因为一个 API error：

```text
整站白屏。
```

---

# 94. README 环境

统一：

```text
Python 3.12
venv

Node 22 LTS
npm
```

不用 Conda。

后端：

```text
backend/.venv
```

---

# 95. 启动端口

```text
backend 18430
frontend 18431
```

默认 host：

```text
127.0.0.1
```

---

# 96. Scripts

必须：

```text
scripts/bootstrap.ps1
scripts/dev-backend.ps1
scripts/dev-frontend.ps1
scripts/seed-demo.ps1
scripts/test.ps1
scripts/verify.ps1
```

任一步失败：

```text
non-zero exit。
```

---

# 97. Tests

默认：

```text
offline
no API key
no paid calls
```

---

# 98. Backend 必测

至少：

```text
Matter validation
Matter digest

Skill validation
Skill resolver priority
Skill trust restriction

CaseCompiler

Plan determinism

Stage isolation

Context Projection

Node idempotency

Retry policy

ReviewGate

SSE snapshot reconstruction

Evidence hashing

SourceRef bbox validation

ProofGraph projection

Review stale detection

Retrieval

AnalysisRun immutability
```

---

# 99. Frontend 必测

至少：

```text
typecheck
lint
unit/component
production build
```

另外：

```text
DetailRail content switching
Citation navigation
Source Viewer bbox
loading/error/empty state
i18n smoke
reduced motion smoke
```

---

# 100. UI Architecture Guard Tests

为了保证未来可换样式，增加静态检查。

至少检查：

```text
features/** 不允许直接 import 指定第三方 UI package
```

以及：

```text
features/** 不允许新增硬编码 HEX brand colors
```

允许集中在：

```text
design-system/
components/ui/
```

---

# 101. E2E

Playwright：

```text
open demo
↓
open Proof Matrix
↓
click citation
↓
DetailRail opens
↓
bbox visible
↓
review one item
↓
run analysis
↓
Advanced receives SSE state
↓
browser reload
↓
state-snapshot restores run status
```

---

# 102. Accessibility Smoke

建议：

```text
@axe-core/playwright
```

至少检查主要工作台无严重 accessibility violation。

---

# 103. Documentation

必须：

```text
docs/

REQUIREMENTS.md
ARCHITECTURE.md
RUNTIME.md
SCHEMA.md

MATTER_PACK_AUTHORING.md
SKILLS.md
PLUGIN_TRUST.md

API.md

DESIGN_SYSTEM.md
HOLMES_REFERENCE.md

SECURITY.md

MIGRATION.md

ACCEPTANCE.md
TROUBLESHOOTING.md

LOCAL_RUN_VERIFICATION.md
IMPLEMENTATION_REPORT.md
```

---

# 104. DESIGN_SYSTEM.md

必须说明：

```text
token layers
UI adapter boundary
icon boundary
motion boundary
DetailRail
responsive behavior
i18n
accessibility
future visual replacement
```

明确告诉后续开发者：

> 更换 UI library 不允许改变 Feature API / Domain Schema。

---

# 105. TROUBLESHOOTING

必须只写：

```text
实际遇到的问题。
```

格式：

```text
Symptom
Root cause
Fix
Final configuration
```

---

# 106. Local Verification

实际记录：

```text
OS
Python
Node
npm

backend install
migration
seed
start

frontend install
start

tests
build
E2E

Demo ID

实际访问页面
实际结果
known limitations
```

---

# 107. P0

必须：

```text
Evidence Core

Matter Pack

Skill Registry
Skill Resolver
Skill trust

CaseCompiler
CasePlan

Stage Runtime
Context Projection
Idempotency
Retry
ReviewGate

ProofGraph

Review
Review staleness

Retrieval

API
SSE
state snapshot

AppShell
DetailRail
Source Navigation
Source Viewer

Overview
Evidence
Timeline
Claims
Proof Matrix
Contradictions
Gaps
Strategy
Review
Advanced

Design System Boundary

Mock E2E

OpenAI Compatible Adapter

Tests
Documentation
Local verification
```

---

# 108. P1

后续：

```text
Legal Proof Graph visualization

Horizontal / zoomable timeline

Matter Pack visual editor

Chat

Judge-specific workspace

PostgreSQL

More Matter Packs

External trusted plugin marketplace

Excel / PPT

advanced parallax / motion design

Auth / multi-user
```

---

# 109. 关键风险及代码级解决方案

## Risk A — Skill 爆炸

风险：

```text
Matter × Task
```

产生大量 Agent。

解决：

```text
capability registry
+
generic Skill
+
matter overrides
```

---

## Risk B — Context Explosion

风险：

每一步把之前所有 prompt/result 塞给下一步。

解决：

```text
stage isolation
+
Context Projection
+
DB state handoff
```

---

## Risk C — Retry 产生重复法律结论

解决：

```text
node idempotency_key
+
immutable SkillRun
```

---

## Risk D — AI 结果变化但 Review 沿用

解决：

```text
Review binds output_digest
```

变化：

```text
stale
```

---

## Risk E — 第三方 Skill 执行任意代码

解决：

```text
external untrusted disabled
+
explicit allowlist
+
declared permissions
```

---

## Risk F — 换 UI 需要重写业务代码

解决：

```text
tokens
+
UI adapters
+
feature separation
+
DetailRail abstraction
+
motion isolation
```

---

## Risk G — 各页面重复 Source Viewer

解决：

```text
CitationDescriptor
+
SourceNavigation
+
DetailRail
```

---

## Risk H — SSE 刷新丢状态

解决：

```text
DB-backed Run state
+
state-snapshot
```

---

## Risk I — 法律 Schema 尚未专家确认

解决：

```text
draft status
+
review badges
+
verified authority status
```

---

## Risk J — 外部模型泄露证据

解决：

```text
external egress off by default
+
explicit configuration
+
egress audit
```

---

# 110. Acceptance Criteria

只有全部 P0 AC 通过，才可宣布 v1 functional implementation complete。

核心：

```text
AC01
旧代码未破坏

AC02
product_v1 独立运行

AC03
fresh venv install passes

AC04
no-key demo works

AC05
Matter Pack discovered

AC06
Matter Pack validates

AC07
Matter version/digest persisted

AC08
Skill Registry works

AC09
Resolver priority works

AC10
untrusted Skill rejected

AC11
CasePlan deterministic

AC12
Stage isolation verified

AC13
Context Projection verified

AC14
Retry does not duplicate output

AC15
ReviewGate works

AC16
AnalysisRun immutable

AC17
SkillRun audit exists

AC18
ProofGraph reconstructs

AC19
Claim→Element→Fact works

AC20
Burden works

AC21
Evidence supports/contradicts works

AC22
Gap works

AC23
Contradiction works

AC24
Strategy grounded in ProofGraph

AC25
AI outputs unreviewed by default

AC26
Review revision history preserved

AC27
Review becomes stale after changed output

AC28
Retrieval does not call model

AC29
Evidence SHA verified

AC30
Source Viewer works

AC31
bbox highlight works

AC32
all features reuse Source Navigation

AC33
AppShell works

AC34
DetailRail open/collapse/resize works

AC35
Timeline renders

AC36
Claims renders

AC37
Proof Matrix renders

AC38
Review works

AC39
Advanced DAG renders

AC40
SSE works

AC41
browser reconnect restores snapshot

AC42
loading/error/empty states exist

AC43
zh/en basic UI works

AC44
reduced-motion works

AC45
feature components do not directly depend on chosen UI library

AC46
no hard-coded brand color violations in feature layer

AC47
OpenAPI generated

AC48
backend tests pass

AC49
frontend tests pass

AC50
production build passes

AC51
Playwright passes

AC52
accessibility smoke passes

AC53
documentation complete

AC54
troubleshooting contains actual issues

AC55
local verification is factual

AC56
no real API key committed

AC57
Holmes code provenance documented
```

---

# 111. 实施顺序

```text
1 project skeleton

2 domain schemas

3 database + migration

4 Evidence Core

5 Matter Pack

6 Skill Manifest / Registry / Resolver / Trust

7 Case Compiler

8 CasePlan

9 Stage Runtime

10 Context Projection

11 Retry / Idempotency

12 Review Gates

13 ProofGraph

14 deterministic Demo Skills

15 backend integration flow

16 Perception adapters

17 Model providers

18 API

19 SSE + state snapshot

20 AppShell

21 DetailRail

22 Citation / Source Navigation

23 Source Viewer

24 Timeline / Claims / Proof Matrix

25 Contradiction / Gap / Strategy

26 Review Workspace

27 Advanced Run DAG

28 i18n / accessibility / motion contract

29 Legacy importer

30 E2E

31 architecture guard tests

32 documentation

33 empty-machine bootstrap verification

34 final implementation report
```

---

# 112. Definition of Done

从干净环境实际完成：

```text
bootstrap

↓

migration

↓

seed demo

↓

backend

↓

frontend

↓

open case

↓

Evidence visible

↓

Timeline visible

↓

Claims visible

↓

Proof Matrix visible

↓

click citation

↓

DetailRail opens

↓

original screenshot visible

↓

bbox highlighted

↓

Review one item

↓

run analysis

↓

SSE progress visible

↓

refresh browser

↓

state restored

↓

changed rerun

↓

old review shows stale

↓

verify.ps1

↓

backend pass

↓

frontend pass

↓

E2E pass
```

才允许写：

```text
ScreenshotLegal Product v1.0.0
functional implementation complete
```

---

# 113. 最终不可违反的架构规则

```text
Evidence
回答证据中发生了什么。

Matter Pack
回答法律上需要判断什么。

Skill
回答某个任务怎么做。

CasePlan
回答本案将执行什么。

Runtime
回答这些任务如何可靠执行。

ProofGraph
回答本案目前形成了什么分析。

Review
回答人最终认可了什么。

UI
回答律师如何查看和修改结果。

Benchmark
独立回答这些方法是否真的有效。
```

不要把这些职责重新合并回一个巨大：

```text
LegalAgent
```

或：

```text
synthesis.py
```

文件。