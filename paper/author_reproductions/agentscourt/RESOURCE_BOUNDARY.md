# L01 AgentsCourt：本地资源边界

原论文/原任务来源：https://aclanthology.org/2024.findings-emnlp.549/。

原方法：从给定案情模拟法庭辩论、检索法律知识并生成裁判分析。

原输入：SimuCourt 中的案情与案件类型/审级等任务信息，通常是已整理的案件叙述。

原输出：案件分析、适用法条、裁判结果；刑事任务涉及罪名、刑期和罚金。

原benchmark：SimuCourt，420 份中文裁判文书，涉及民事、行政、刑事及审级设置；配套 Legal-KB。

创新点：法庭辩论模拟、法律资源增强与裁判迭代结合；不等于增加两个对立角色。

当前完整方法未复现。按用户要求，依赖本地权重、训练和重计算的分支暂缓；不是缺专家CaseGold导致停止。具体原源码、提交、行号及SHA-256见[resource_boundary.json](resource_boundary.json)，此次仅做源码检查，0次新增模型调用。

已有作者API庭辩组件记录保留；完整Legal-KB的BGE重排没有执行，不能将庭辩组件当完整AgentsCourt。
