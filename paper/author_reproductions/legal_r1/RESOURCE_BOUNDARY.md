# L11 Legal-R1：本地资源边界

原论文/原任务来源：https://arxiv.org/html/2610.18611v1。

原方法：法律问题上的主动法源选择、检索充分性判断和证据轨迹回答。

原输入：作者 infer_pipeline.py 默认读训练/RL JSON；实际取 row['Open-ended Verifiable Question']。同一行还含 Ground-True Answer、Complex_CoT，仅可保留作评测/参考，不能混入用户问题。规范库/类案库另行加载。

原输出：原 rollout 保存 original_question、turns、final_answer 及参考标签字段；最终回答从轨迹生成。它不是原图解析或带字符坐标的 ProofGraph。

原benchmark：LawBench、LexEval；法条检索另有 provision-oriented 查询。原规范库与 LeCaRDv2 类案库须版本匹配。

创新点：训练 Lawyer 检索策略（masked SFT、轨迹强化学习），结合 authority/diversity-aware Assistant 和 Judge。

当前完整方法未复现。按用户要求，依赖本地权重、训练和重计算的分支暂缓；不是缺专家CaseGold导致停止。具体原源码、提交、行号及SHA-256见[resource_boundary.json](resource_boundary.json)，此次仅做源码检查，0次新增模型调用。

此前E11的14次项目机制原型请求保留并计入预算；通用DeepSeek角色prompt不等于作者经训练的actor策略，原vLLM/GPU/torch rollout未运行。
