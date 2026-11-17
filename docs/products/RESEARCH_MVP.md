# 评测台、合成生成台、数据审核台 MVP

日期：2026-10-24（Asia/Singapore）。产品边界见 [PRODUCT_BOUNDARIES.md](PRODUCT_BOUNDARIES.md)。

本轮审核交互已升级为[图片坐标框编辑、判决书原文侧栏与审核评论](REVIEW_CANVAS.md)。评论可单独保存，并由生成台固定读取用于下一轮迭代。

三个产品使用独立 HTML 入口、前端用例和后端命名空间；共用账户、模型配置、版本化数据契约、资产存储和任务运行库。研究记录存入独立 research.sqlite3，不修改用户工作台的案件记录。物理部署仍为模块化单体。

| 产品 | 本机入口 | 职责 |
| --- | --- | --- |
| 数据审核台 | http://127.0.0.1:18431/review.html | 全类别样本、来源、原图、文本/题目纠正、标签、草稿、渲染、质量记录、质量 Prompt、数据发布 |
| 合成生成台 | http://127.0.0.1:18431/studio.html | 生成 Prompt Markdown 版本、批次、生成与结构校验、候选、产物打包、读取质量对比 |
| 评测台 | http://127.0.0.1:18431/evaluation.html | 配置/勾选模型、文本/图片测试、固定发布版本、输入模式、范围、运行、错误、重试、指标与导出 |

## 从来源到评测

1. 在审核台“导入与发布”选择已有 V2/V3 批次，或导入标准 Content JSON、真实 PNG/JPEG/WebP 原图，也可新建候选。目录包含来源原文但没有 case.json 的 V2 条目会作为 source_only 原始文档接入。历史记录保留候选身份，不自动认证金标。
2. 在生成台保存生成 Prompt，填写本轮修改原因，可关联质量记录 ID。每次保存追加版本，可下载完整 Markdown 迭代历史。
3. 选择来源样本及其 revision、Prompt 版本、模型、数量、语言、平台、任务类型、约束、seed、模板和渲染参数。生成原始响应、结构校验、候选与渲染任务持久化。候选自动出现在审核台。
4. 在审核台纠正消息、题目、标签并填写纠正说明。显式保存产生新 revision 和真实 PNG 渲染任务；纠错同时追加一条 pending 质量记录。消息变动会取消旧答案的 gold 标记。
5. 在审核台“质量 Prompt 迭代”管理模型质量评估 Prompt；模型任务固定该 Prompt、样本 revision 和模型快照。人工审核、模型评估与纠错记录共同保存发现、结果、修改意见、过程、来源和修订关系。
6. 在生成台“质量结果对比”读取上述记录。按批次 × 生成 Prompt 聚合，人工和模型分开统计，每个当前样本版本/方法只取最新有效记录。未评分显示空值；旧版本评分不会进入新版本均分。
7. 当前版本人工审核通过且图片完整时，在审核台发布不可变 DatasetRelease。人工明确勾选的有效答案才可进入评分；历史候选答案仍为未确认。
8. 在评测台选择固定 release、模型和范围，运行后查看逐题答案、受控原始响应、请求/任务/运行 ID、错误类别、精确匹配指标、延迟、成本和失败分布。失败/未知/取消项可导出或创建关联重试运行。

离线 Demo 复制来源形成候选，并验证任务/质量/评测流程，不提供真实模型质量评分。真实模型使用用户已有的 OpenAI Chat Completions 兼容配置，需在模型设置启用请求。默认运行不调用收费模型。

## Prompt 与质量记录的所有权

- studio.prompt：生成 Prompt，不可变 Markdown 版本，包含父版本、SHA256、修改意见、关联质量记录和编辑者。
- review.prompt：质量评估 Prompt，版本规则相同，只在审核台编辑。
- review.quality：人工/模型/纠错记录。编辑会追加 supersedes 记录，保留旧内容；将模型结果人工修订时明确成为人工记录，不伪造模型原始输出。模型输出不能自行覆盖或取代人工记录。
- studio/comparison：审核台提供的只读投影；生成台没有质量记录写接口。

## 保存与恢复协议

SQLite 使用 WAL、synchronous=FULL 和 BEGIN IMMEDIATE。SampleRevision、差异、纠错记录、RenderJob 和幂等结果在同一事务中提交。所有研究数据按登录用户隔离；管理员不会自动读取其他用户的研究记录。

LocalDraft 存入 IndexedDB，键包含用户/数据集/样本；记录 draft ID、base_revision、内容、渲染参数和修改意见。输入后立即排队串行写入 IndexedDB，另防抖向服务器保存带 CAS 版本的 ServerDraft。缓存失败会明确显示；服务器不可达不会清除本地内容。刷新恢复时比较当前 revision，冲突保留双方，必须显式对照合并；不会自动覆盖服务器新版本。

Worker 领取 30 秒租约并每 5 秒续约。每页 PNG 先写临时文件、flush/fsync、原子替换，再保存 SHA256 检查点。恢复只跳过通过哈希检查的页；损坏文件重新生成。全部完成后写入 manifest（text hash、revision、分页、尺寸、坐标空间、message ID/bbox、参数、renderer、Pillow 与字体哈希），只有仍对应当前 revision 的任务可以更新预览指针。旧任务晚完成不会覆盖新图。图片 URL 包含不可变 manifest hash；旧图明确显示版本落后。

模型调用开始状态在外发前落盘，响应在结构解析前落盘。调用中退出、超时或请求传输中断后标记 unknown，费用与结果未知；不会自动重放。显式重试产生新任务/运行并保留父关系。评测重试沿用原始模型、凭据引用、数据 release 和输入快照。

原件以内容寻址保存并校验，转录纠正形成派生视图，禁止覆盖原件、来源原文或原始引用。按需批次 ZIP 包含生成配置/响应、Prompt 历史、审核历史、任务过程、文本 revision、PNG 与 bbox manifest。

## 存储与启动

沿用 [product_v1 启动方式](../../product_v1/README.md)。新库按需初始化，不需要迁移或删除现有案件库。

- product_v1/data/research/research.sqlite3：三个产品的分区记录、幂等键、任务、租约、检查点；凭据仅以加密记录存放于 gateway 分区。
- product_v1/data/research/originals、assets、manifests、packages：原件、派生图、清单和导出包。
- 备份需包含整个 research 目录及原有 data/.credentials/model-master.key；冻结的模型凭据引用依赖该主密钥。

API 默认启动一个 worker；需要独立/额外 worker 时，从 product_v1 使用产品 Python 执行：

~~~powershell
.\.conda\screenshotlegal-v1\python.exe -m screenshotlegal.research
~~~

主要接口前缀：/v1/review、/v1/studio、/v1/evaluation；共享任务为 /v1/research/jobs。完整参数见 http://127.0.0.1:18430/docs 。

标准 JSON 最小导入示例：

~~~json
{
  "title": "候选样本",
  "category": "chat",
  "source_text": "可追溯来源原文",
  "messages": [{"id": "m1", "speaker": "A", "text": "收到300元。"}],
  "questions": [{"id": "q1", "question": "消息中的金额？", "answer": "300元", "gold": false, "message_ids": ["m1"]}]
}
~~~

## 当前 MVP 限制

渲染器为真实 Pillow 通用聊天/转录派生视图，支持分页和 bbox，尚未实现各平台像素级模板。模型协议目前支持 OpenAI 兼容 Chat Completions。评测内置评分为人工确认金标的精确答案匹配；法律实质质量通过审核台另行记录，不把流程通过当作法律正确。

调用预算以模型×题目次数为硬限制；成本仅在服务返回 token 用量且用户填写单价时估算。原图上传为单请求、有大小限制；未实现分片上传。真实断电、跨机器共享文件系统与浏览器配额耗尽还需要部署环境验收；本轮有真实子进程强制退出、半写/损坏产物、断网、缓存和并发冲突测试。

验证证据见 [本轮报告](../../product_v1/reports/research-products-mvp-2026-10-24/REPORT.md)。

## 2026-10-24 可靠性与操作审计完善

输入保护、审核/图片/金标/发布绑定、原图坐标升级、视觉质量、分协议比较及评论处理已完善；新增SQLite审计表与三台审计页面。使用方式见[可靠性与操作审计](RELIABILITY_AUDIT.md)，[本轮验证](../../product_v1/reports/reliability-audit-2026-10-24/REPORT.md)。本文较早的测试数按当轮范围保留，旧通过记录不会自动获得新绑定。
