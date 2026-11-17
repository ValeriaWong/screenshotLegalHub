# AI 文档中心

## 评测交互重整（2026-10-25）

按用户对启动和结果交互的反馈，将新建、结果和单阶段调试分开；新建先选样本、再设置/预览，打开结果直接看结论。统计/恢复不再默认铺满页面。原图与回答在详情弹窗并排查看，关闭/Esc恢复位置和焦点。

纠正低IoU候选框也显示绿色“实际选入”的提示错误：仅合格匹配才标已采用，未发题明确没有输入/回答。增加首屏可见、未采用候选、弹窗返回与移动端验收。后端236、前端单元29、浏览器33通过，类型/lint/架构/构建通过；不将自动化通过当真人理解认证。

[本轮报告](../../reports/kie_vqa_interaction_redesign_20261025/REPORT.md) · [操作说明](../products/KIE_VQA_PIPELINE.md) · [查看刚才真实结果](http://127.0.0.1:18431/evaluation.html?benchmark=1&pipeline=pipeline.350e7b46e8f8458cae8969c2fa0222a4)。没有新增在线调用；G3/G4及B待完成状态保持。

## 单样本真实在线试跑（2026-10-25）

已按用户要求触发一次：6个计划单元，实际5次请求（1 KIE＋4全图VQA）全部返回。新IoU为0.0969＜0.6，区域VQA未发送并保留在分母；费用估计¥0.07285，用量完整。没有调低阈值或追加重试。开放题/旧参考待审核；G3的匹配消息VQA正向成功路径仍未验证，不能宣称在线完整成功。

[本轮结果](../../reports/kie_vqa_online_smoke_20261025_173000/REPORT.md) · [查看实际流程](http://127.0.0.1:18431/evaluation.html?benchmark=1&pipeline=pipeline.350e7b46e8f8458cae8969c2fa0222a4)。软件交付与研究质量分开，V3认证/发布状态保持。

## 默认按样本完整评测（2026-10-25）

评测台首页现在按图片选择样本，一轮自动展开该图KIE、IoU关联和全部VQA题。无需逐题拼接；同字节不同来源仍是独立逻辑样本。独立任务/单阶段调试保留在高级折叠区，样本结果可按图片追查，阶段筛选不改变整轮评分分母。样本选择支持搜索、分页和刷新恢复；整轮历史在默认页继续展示。

验收为236后端、29前端单元、32浏览器（含三图一次运行、默认页/旧页切换）；3张夹具图共12执行单元，不能将样本数当调用数。万题D盘快照新增查询p95：目录0.156秒、样本结果0.355秒，各20次。没有重新执行第二轮12172次，也没有新增真实在线调用。

[操作说明](../products/KIE_VQA_PIPELINE.md) · [本轮报告](../../reports/kie_vqa_sample_workflow_20261025/REPORT.md) · [操作台验证](http://127.0.0.1:18431/evaluation.html?operations=1&kind=research.flow&record=kie-vqa-sample-workflow-20261025)。G3/G4及B后续范围保持待完成，V3阶段4/8、独立认证0、未发布保持。

## KIE/VQA自动链路A阶段交付（RP14，2026-10-25）

已完成P0–P5的软件实现：按图冻结依赖、KIE新预测→IoU关联→绑定消息VQA、独立全图题、固定分母/ScoreSet，以及停止、本地恢复、迟到响应核对、最小范围重试和审计导出。SQLite保留原始返回、实际输入、修改原因与分支，评分失败不会自动重新调用模型。

验证：后端228项、前端单元29项、浏览器30项通过；1170图/12172任务通过本地模拟HTTP全量演练，6333条旧IoU逐项一致。全量库D盘分页结果p95约1.82秒、操作台列表约0.032秒。模拟结果只证明软件链路，不代表真实模型质量。

RP14整体仍为部分完成：P6/G3在线小批未执行，G4人工参考/独立审核未就绪；B0的问题资格字段已有基础，人工题目/证据/划分准备尚待完成，B1预测侧证据选择和B2补救/partial/模型裁判尚未实现。区域链路明确为“参考区域引导VQA”，低IoU、无匹配和失败保留计划分母。真实模型调用新增0；V3阶段4/8、独立认证0、未发布保持。

[使用说明](../products/KIE_VQA_PIPELINE.md) · [阶段计划](KIE_VQA_PIPELINE_PLAN.md) · [验收与边界](../products/KIE_VQA_PIPELINE_ACCEPTANCE.md) · [实现报告](../../reports/kie_vqa_pipeline_implementation_20261024/REPORT.md) · [操作台验证记录](http://127.0.0.1:18431/evaluation.html?operations=1&kind=research.flow&record=kie-vqa-pipeline-20261025)

## KIE/VQA本地迁移交付（RP13，2026-10-24）

已实际迁入admin操作台：1170逻辑图（含82身份待核对候选），11002 VQA＋1170 KIE任务及29旧意见，9份KIE历史汇总/1124原始尝试和450旧证据问答；6333旧IoU逐条一致。审核台可核对原图/区域/预测框、修订/评论/量表及发布，评测台可冻结答题Prompt、分轨运行、回放与离线重评；开发集评论同步生成台，过程与结果可在操作台/审计检索。

193后端全量、最终32相关后端（含新增未知/重试测试）、29前端单元、26浏览器全量及后续4/2个相关浏览器通过；当前195后端用例未再次全套执行。原590研究行、2687案件、111已绑定附件和1132源文件保持；重复迁入不新增。真实模型调用、实际人工认证/发布新增均0。M1–M5软件桥接完成，82候选身份、人工KIE目标/字典、开放题专业量表及M6真实小批试跑仍待完成；人工转录辅助和新任务自动模型裁判未启用，不宣称旧论文VQA成绩等价复现。

下一步先在审核台确认小批图片和目标，固定案件组/用途后发布，再明确实际任务、模型与调用预算。V3阶段4/8、独立认证0和未发布状态保持；原功能/问题台账计数不因RP13软件扩展自动上调。

[迁移计划](KIE_VQA_MIGRATION_PLAN.md) · [使用说明](../products/KIE_VQA_MIGRATION.md) · [交付与完整性](../../product_v1/reports/kie-vqa-migration-2026-10-24/REPORT.md) · [实际操作台](http://127.0.0.1:18431/evaluation.html?operations=1&kind=research.flow&record=kie-vqa-migration-20261024)


更新：2026-10-24（Asia/Singapore）；基准：[V3计划](../../V3.0.0_PLAN.md)。

**当前四场景S0–S3作者/机械交接完成（4/8阶段），独立认证0题，尚未发布。** Feature 34项：完成26、部分4、计划4；issues 32项：处置27、开放5；gap 25项：完成12、开放12、扩展1。计数限各项声明范围，不合并为主观项目完成率。

- [KIE/VQA迁移准备](KIE_VQA_MIGRATION_PLAN.md)：指定源目录清单、19标签字段映射和评分协议已产出，RP13软件迁移已交付，自动链路A见本页最新记录；[完整性审计](../../reports/kie_vqa_migration_20261024/REPORT.md)。
- [评测运行历史](../products/EVALUATION_HISTORY.md)：I32已修复，两轮真实试跑及连通性测试现在可直接查看；正式运行仍0，试跑未计分。[修复证据](../../product_v1/reports/evaluation-history-2026-10-24/REPORT.md)。
- [开放问题软件修复](../products/OPEN_ISSUES_FIXES.md)：RP11修复I29/I30/I31，I10等待配置子项交付但继续开放；171后端/29前端/24浏览器通过，无新增真实模型调用。[报告](../../product_v1/reports/open-issues-fixes-2026-10-24/REPORT.md)。
- [修复前8项问题评估与后续边界](OPEN_ISSUES_ASSESSMENT.md)：当前5项仍开放，历史质量意见、模型语义复测及人工认证分别推进。
- [13样本全量实际测试](../../product_v1/reports/full-actual-test-2026-10-24/REPORT.md)：软件160/29/21项通过；真实131调用130返回1未知，14新候选、90/90未计分问答；I29–I31在该轮发现，后续RP11完成软件修复。
- [新协作人员的控制台说明](../products/CONSOLE_CLARITY.md)：RP10已实现任务引导、状态解释和高级参数展开；真人理解测试待执行。[交付记录](../../product_v1/reports/console-clarity-2026-10-24/REPORT.md)。
- [模型配置与流程审计](../products/OPERATIONS_OBSERVABILITY.md)：RP09及I26–I28软件修复完成；模型单价/可选上限、历史流程、审计业务跳转及关键词日期聚合可用。
- [DeepSeek六样本真实试跑](DEEPSEEK_FLOW_RUN.md)：7候选、26/26双模态未计分问答、反馈Prompt迭代；人工审核与发布待完成，I26已由RP09修复，历史用量仍未知。
- [研究产品完善计划与现有进度](RESEARCH_PRODUCTS_PLAN.md)：RP01–RP08已交付，I17–I25关闭；输入保护、原图/审核/金标/发布绑定、SQLite操作审计及前端、视觉质量和评论闭环通过验证。[152后端/26前端/11浏览器及迁移证据](../../product_v1/reports/reliability-audit-2026-10-24/REPORT.md)。
- [坐标、代码检索与回溯评测](../coordinate-retrieval-evaluation.md)：已恢复6389区域、2549/2579图有框；剩30图及评分器/认证由G19跟踪，不能把区域覆盖当作检测召回。
- [admin全量案件与版本](ADMIN_CASES.md)：已实际新增2682条，admin可见2687条；覆盖差集0，重跑新增0，原有案件和人工工作保留。
- [V2第六轮全文复核](../../datasets/v2.0.0/round_006/REPORT.md)：200条由代理逐案阅读全文复核，恢复11、修订85、撤回11；当前138通信候选+2项辅助，62条仍待材料。
- [V2第五轮历史机械归档](../../datasets/v2.0.0/round_005/REPORT.md)：200条逐项处置；138候选（新增38、复用100），62条缺实际通信材料；[完整缺口](../../datasets/v2.0.0/round_005/SOURCE_GAPS.md)。
- [人工交接与两份盲审ZIP](../v3.0.0/CALIBRATION_HANDOFF.md)：当前需要两名独立复核者；4场景、80图、352子集。
- [完成度与证据](PROGRESS.md)、[当前计划](NEXT_STEPS.md)、[Feature](FEATURES.md)、[Issues](ISSUES.md)、[Gap](GAPS.md)。
- [文档地图](DOCUMENTATION_MAP.md)、[完整索引](DOCUMENTS_INDEX.md)、[机器台账](status.json)、[文档哈希清单](documents_inventory.json)。
- [环境复现](../../reports/v3.0.0/runtime_reproduction_20261023_002/README.md)、[导入回归](../../reports/v3.0.0/import_atomicity_20261023_001/README.md)、[校准检查](../../reports/v3.0.0/calibration_20261023_001/README.md)。
- [10月22日初次审计](archive/2026-10-22/README.md)、[G01完成档](archive/2026-10-23/COMPLETED.md)、[本次连续推进归档](archive/2026-10-23/CONTINUATION.md)。
- [旧项目启动指南](LEGACY_GUIDE.md)、[S0冻结工具](../v3.0.0/S0_BASELINE.md)、[来源核对](../v3.0.0/SOURCE_CLOSURE.md)。

历史材料按原日期/版本解释。本轮DeepSeek已发生61次实际请求；此前API调用0仅指各历史批次；2026-10-24已备份并写入本机产品运行库；没有仓库推送。当前是作者材料和程序验收，不是两份真实独立意见。研究三台交付轮137后端/26前端/6浏览器测试通过，后续9项问题已由本轮152后端/26前端/11浏览器覆盖修复；旧测试数按原交付轮保留，不相加。
