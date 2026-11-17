# 方法实现与作者系统的差异

核对日期：2026-10-28。这里的“已实现”仅指本项目可执行方法，不表示作者代码、训练权重、原任务或论文分数已被完整复现。案件流程采用统一输出、冻结来源、工具权限和计量；KIE/全图VQA另用其任务协议。本页区分作者控制器任务适配和项目机制原型，不能混为作者整套系统复现。

| ID | 已实现的可观察机制 | 复现边界 / 必要前提 |
|---|---|---|
| E00 | 单次回答 | 基线，不带领域模板 |
| E01 | 案件run仍为受控工具原型；KIE/全图VQA的run_task已接作者Notebook webthink控制器 | 图像变体将Wikipedia工具替换为冻结原图目录和像素局部读取；原HotpotQA真实模型样例待新额度 |
| E02 | 识别→证据映射→整合，保持阶段输出 | 不提供 Matterpack，保留 RQ2 对照 |
| E03 | E02 + 显式领域模板 | 当前借贷模板尚未专家复核，仅允许显式开发诊断 |
| E05 | 案件run及KIE/全图VQA的run_task执行作者responsegen迭代控制器和原三任务类调用 | 任务模板/图像/模型/解析已适配；两轮生成含四次调用；工程夹具验证通过，新增原任务/真实图片试跑待额度，自评分不作评测成绩 |
| E06 | 新上下文的核查者审查草稿与原文，再修订 | LegalReasoner 的核查机制改写，未训练其过程验证器 |
| E07 | 双方独立初始意见→读取上一轮意见→原起草者整合 | 使用项目主张方/相对方角色 |
| E08 | E07 后增加独立中立汇总者 | 增加调用成本，不能仅按成功率挑选结果 |
| E09 | 0–3 轮同步信息交换；同轮双方均只读取上一轮意见 | L-MAD 风格；原论文 persona、投票/共识基准未照搬 |
| E10 | 根据要件生成查询→冻结资料检索和原文读取→阶段分析 | 当前为词项检索，不宣称向量/重排收益 |
| E11 | Lawyer 决定检索来源与停止→冻结工具返回资料→Judge 读取完整轨迹 | Legal-R1 的推理流程改写，未执行其 masked SFT、GRPO、MMR/PSI 或作者检查点 |
| E12 | correct/incorrect/ambiguous 三分支；过滤、改写查询、补充检索 | CRAG 的闭域变体；无训练专用 evaluator、Web 扩展或细粒度知识条重组 |
| E14 | 全部来源按顺序分块；worker 传递有引用的记忆；manager 汇总 | Chain of Agents 的通信结构；字符分块替代论文 token 窗口，材料过长时显式预算失败 |
| E18 | 实体/事件/争点结构→初稿→manager 动态检索或核查→修订 | JurisMA 的结构与路由改写；未做原文 DPO 训练或原系统完整测评 |
| E19 | 先从独立 Issue–Factor 层级选择因素，再提取关联的法律指南片段 | SCALE 需要独立指南原文及 factor→guide 映射。现有包缺失，正式运行会在入队前阻止；不能用测试 Gold 生成 |
| E20 | clerk 结构提取→assistant 法源检索→case judge 草稿→合议指令/退回修订→presiding judge | VERDICT 的角色与修订流程改写；无对齐专家模型，也没有 HJM 的标准/微指令记忆演化；不能称完整 VERDICT |

E04 形式验证、E13 GraphReader、E15 RAPTOR、E16 LightRAG、E17 人工反馈评测仍为 planned，接口会拒绝代跑。它们需要额外规则、图/层次索引或经控制的人工反馈协议，不用空适配器冒充完成。

首批作者控制器、原任务入口、逐篇状态与冻结真实试跑计划见[作者复现目录](../author_reproductions/README.md)。专家法律评测已延期；本轮先KIE/全局VQA，不以专家CaseGold阻塞代码接入。

方法源码现为“一候选一文件”，位于独立 method_reproductions 包；文件头注明本文对应来源与复现程度。按名称查看代码、原始回复及测试结果：[统一目录](../method_reproductions/README.md)。

## 先前案件机制的真实诊断（历史45次，非新作者控制器验证）

用户授权 DeepSeek 总计最多 46 次请求，实际发出 45 次。全部成本和失败分母见[真实开发试跑报告](results/2026-10-28-deepseek-pilot/REAL_PILOT_REPORT.md)。这些是两条合成开发材料上的工程诊断，仍不构成法律质量评测。

| 方法 | 最后真实验证状态 | 已验证范围 |
|---|---|---|
| E03 | 简单夹具完成 | 3 阶段、2 条逐字引用与 Unicode 范围 |
| E11 Legal-R1 机制 | 反证夹具完成 | 3 次检索规划 + Judge；case_search / authority_search / source_read；3 条引用 |
| E18 JurisMA 机制 | 先前任务失败；最终协议尚未重跑 | 结构图、动态路由、修订的真实轨迹已保存，不能标为端到端通过 |
| E20 VERDICT 机制 | 先前任务失败；最终协议尚未重跑 | 角色链与合议修订的真实轨迹已保存，不能标为端到端通过 |

真实请求发现思考输出截断、中文字符位置误算、规划者动作协议混淆等问题。已增加显式思考模式、机械引用分段坐标、非空引用 Schema 和专用检索动作协议；严格引文验证保持启用。不同阶段的代码、输入、参数和失败均独立保存，不据此计算方法净增益。

## 主要一手来源

- [Legal-R1](https://arxiv.org/html/2610.18611v1)：核对检索规划、检索助理、轨迹裁判以及训练流程。另读取[作者 infer_pipeline.py](https://github.com/killerqueen-wonder/Legal-R1/blob/main/infer_pipeline.py)，文件 Git blob 与 SHA256 见 [legal_r1_upstream.json](legal_r1_upstream.json)。原入口依赖 Linux/bash、vLLM、检查点和多个 CUDA 设备、法条/刑事类案语料与检索服务。未在本 Windows 项目直接执行原训练/推理进程。
- [JurisMA](https://arxiv.org/html/2604.10470v1)：依据其法律要素结构、动态任务路由及内容修订设计项目变体；DPO 不在已完成范围。
- [L-MAD](https://arxiv.org/html/2607.09099v1)：采用独立初始意见与轮间信息交换；本项目角色、最终输出和汇总方式有变化。
- [LegalReasoner](https://arxiv.org/html/2506.07443v1)：参考验证器给出针对性纠错；本项目核查者是同一底座的新上下文，没有论文训练验证器。
- [CRAG](https://arxiv.org/html/2401.15884v3)：核对三种检索质量动作；闭域变体不引入网上新资料，检索评估器也由同一底座担当。
- [Chain of Agents 作者说明](https://research.google/blog/chain-of-agents-large-language-models-collaborating-on-long-context-tasks/)：顺序 worker→manager 的结构进入 E14。本条指 Zhang 等人的长上下文方法，不是同名的另一项 Agent Foundation Model 训练工作。
- [SCALE](https://aclanthology.org/2026.emnlp-main.36/)：保留独立法律指南与 Issue–Factor 层级的前提；当前只通过合成结构夹具测试分支。
- [VERDICT](https://arxiv.org/html/2603.19306v1)：核对司法角色链、退回修改和最终汇总。其训练与双层记忆是重要差异，不能把普通多轮 Self-Refine 叫作完整 VERDICT。

## 与先前架构方案的连接

[架构优化方案](../../docs/architecture/EVIDENCE_DOCUMENT_UPGRADE_PLAN_2026-10-25.md) 和 [17 个上游入口](../../docs/architecture/EVIDENCE_UPGRADE_SOURCES_2026-10-25.json) 均已读取。17 个固定提交文件的实际 SHA256 全部匹配，所列符号均存在；逐文件证据见 [upstream_verification.json](../../reports/research_implementation_20261028/upstream_verification.json)。它们提供来源/解析工程参考，不计入论文 Agent 方法成果。

已落地共享冻结来源、文档进入主运行、字符续读、原生文本分块配置多版本、坐标含义与原文件链接。当前仍沿用原有 MinerU 默认路线；没有声称 Docling/Paddle 已安装、取得性能提升，或已经完成全局 FTS 与解析持久任务迁移。详见实现报告。
