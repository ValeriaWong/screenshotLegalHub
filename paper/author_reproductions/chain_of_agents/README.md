# A06 Chain of Agents：论文算法重实现与产品适配

论文：[Zhang et al., Chain of Agents（NeurIPS 2024 / arXiv v1）](https://arxiv.org/html/2406.02818v1)；[作者Google Research介绍](https://research.google/blog/chain-of-agents-large-language-models-collaborating-on-long-context-tasks/)。本实现依据固定v1的Algorithm 1、3.1/3.2节、Appendix B Tables 9/10及Appendix D。

**复现等级：paper_algorithm_reimplementation。** 目前未核实到该论文作者发布的代码入口；这里执行的是按公开算法和提示重写的实现，不是作者CoA Python原代码，也没有把OPPO等同名项目当作作者代码。论文快照及SHA见[规范锁](specification.lock.json)，全部源码快照保留在各运行目录。

## 原方法、benchmark、输入输出

原方法将完整长文本顺序分块，CU0为空。每个worker只读取当前块、上一个worker的累计CU及问题，产生更新后的CU。独立manager只接收最后CU、任务要求及问题；不额外读回原文，也不把所有CU拼给manager。

创新点是交错阅读、顺序累计通信与职责分离，在短窗口内覆盖完整长资料；不能用独立分块摘要后拼接或一次全文问答替代。

原任务输入是长文本x、可选问题q与任务要求，输出是答案、摘要或代码续写及通信CU。原benchmark为HotpotQA、MuSiQue、NarrativeQA、Qasper、QuALITY、QMSum、GovReport、BookSum、RepoBench-P，按QA F1、摘要ROUGE、代码相似度分别评估。本轮没有复现全部benchmark。

## 真实实现与调用

- [algorithm.py](algorithm.py)：完整方法、原任务/输入输出/创新点/适配说明在文件开头；实现token窗口、Unicode无损完整覆盖、顺序CU及last-CU-only manager。不是空文件或统一多阶段prompt入口。
- [隔离运行入口](product_adapter.py)：仅借用共享JSON管道交换原始API响应，算法在本目录执行。
- [实际E14模块](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e14_chain_of_agents.py)与[产品桥](../../../product_v1/backend/src/screenshotlegal/method_reproductions/coa_bridge.py)：run()案件主链和run_task()冻结KIE文本VQA均调用上述同一算法。
- [原任务/两类产品运行器](run_validation.py)：原任务和产品共用A06持久100次上限；本轮累计9次，包括首次弃答，未清零。
- [独立环境](environment_state.json)：Python3.12.15、[7项依赖锁](requirements.lock.txt)，无本地模型权重、嵌入、训练或GPU推理。普通分词资源校验后使用。

原模型来自Vertex；本轮按用户授权替换为AIPING DeepSeek-V4.1-Flash-1017。窗口为8192，原任务生成上限1024、温度0。cl100k_base是明确标注的分词代理，不是DeepSeek/Vertex官方分词器；每次代理窗口计数与供应商实测token分开保留。产品生成上限2048，并增加JSON与原文引用契约，均为显式适配。

## 原任务实际验证：已执行，答案未命中

官方LongBench代码提交为2e00731f8d0bff23dc4325161044d0ed8af94c1e；数据集原THUDM入口现重定向到zai-org，固定revision 5e628be450b7e67fb7ae6e201bd6d8f7056f7672。下载来源、ZIP/成员哈希和固定第0条规则见[数据出处](native_inputs/dataset_provenance.json)。[原始完整首条样本](native_inputs/hotpotqa_first.json)和官方评分代码均保留；没有按模型表现选题。

输入上下文54062字符，完整分为[0,29608)、[29608,54062)两块，原文没有截断。2个worker＋独立manager共3次真实调用。

模型回答Gates v. Collier；数据集参考Miller v. California。原LongBench qa_f1_score为0.3333333，答案未命中。逐轮CU表明模型对调查、立案、一审与上诉时间的理解与参考不一致；没有改写参考、输入问题或重试来取得正确答案。本记录验证了完整执行和可核查的失败结果，不能称为QA正确率通过。

[完整可读输入/每步回复/输出/分数](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/b7e15d91616acd45__native/e14_chain_of_agents.INPUT_OUTPUT.md) · [原输入与仅评分参考](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/b7e15d91616acd45__native/e14_chain_of_agents.input.json) · [原始逐次请求/回复/用量](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/b7e15d91616acd45__native/e14_chain_of_agents.model_responses.json) · [最终输出及完整chunk/CU](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/b7e15d91616acd45__native/e14_chain_of_agents.output.json) · [检查](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/b7e15d91616acd45__native/e14_chain_of_agents.test_results.json)。

## 产品适配与调试

1. 冻结KIE预测文本→全局VQA。CoA不接图像像素，依靠上游已保存模型预测；原始图片、上游输出哈希和任务输入关联保持。首次2次调用返回answer=null，在旧开发参考下得0。检查发现原冻结分类输入没有传入公开选项表，CoA也只传问题文本；已补齐全部允许标签并传给worker/manager的问题部分，当前题参考仍不进入输入。
2. 修复后的同一开发样本再用2次调用，返回non_legal_dialog，在legacy_unverified参考下得1。该分数不是人工/专家成绩，也不是原长上下文benchmark指标；前次弃答仍保存。
3. 案件产品通过真实E14.run()调用，worker携带原文quote、source_ref_id与完整start/end，manager仅依据最后CU整理CaseAnalysisOutput。2次调用返回3项带引用事实，结构和逐字范围检查通过；陈述/否认/缺失信息仍须人工核查，没有专家法律准确率。
4. 普通评测现在先查找确实存在的KIE attempt，再解析旧历史指针，修复流水线KIE编号中冒号导致误判的问题。图像哈希、归属、KIE结构、完成状态仍按既有规则核验。
5. 前端方法选择新增CoA论文算法选项，要求已保存KIE预测文本；显示至少2次、实际按文本窗口动态执行、用户上限约束。API/OpenAPI/前端类型同步。旧字符分块案件计划不能用新算法静默运行。

产品记录：

- [修复前弃答完整I/O](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/c62faca80f2c97ad__vqa_predicted_text/e14_chain_of_agents.INPUT_OUTPUT.md)
- [修复后VQA完整I/O](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/5c8847569acd6456__vqa_predicted_text/e14_chain_of_agents.INPUT_OUTPUT.md) · [原始输出/分数](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/5c8847569acd6456__vqa_predicted_text/e14_chain_of_agents.output.json)
- [案件完整I/O](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/93cf97434ec04e87__case_product/e14_chain_of_agents.INPUT_OUTPUT.md) · [案件输出](../results/2026-10-29-per-paper/methods/e14_chain_of_agents/runs/93cf97434ec04e87__case_product/e14_chain_of_agents.output.json)
- [四次运行汇总](run_summary.json)：9次请求；17118输入token、2757输出token；按配置价格估算约0.056292元，非供应商结算金额。

## 工程验证及运行

[后端回归](../../../reports/author_expansion_20261029/test-coa-api-and-benchmark-regression-fixed.log)：57项通过，包含算法窗口/顺序/预算、Unicode、案件HTTP导出、文本VQA实际参数、流水线上游KIE、既有评测与LawBench回归。[前端方法选择](../../../reports/author_expansion_20261029/test-coa-frontend-method-picker.log)：5项通过；生成最新API类型后TypeScript检查通过。另对Table 10无查询摘要分支做了[单项验证](../../../reports/author_expansion_20261029/test-coa-query-free-summary.log)，1项通过。测试夹具使用确定传输，不能充当真实模型质量结果。

环境检查和计划（不发模型请求）：

```powershell
product_v1/.conda/screenshotlegal-v1/python.exe -X utf8 -B paper/author_reproductions/setup_environment.py chain_of_agents --check
product_v1/.conda/screenshotlegal-v1/python.exe -X utf8 -B paper/author_reproductions/chain_of_agents/run_validation.py --track native
```

真实执行由运行器--execute触发，轨道可选native、vqa_predicted_text、case_product。读取上述已存文件可直接重放核查，无需再次付费调用；实现/输入变化的新计划也共用既有100次账本。

本条目完成的是论文算法重实现的开发执行闭环，来源等级与作者源码6篇分开标注；原QA错误、产品旧参考、完整benchmark未运行和专家Gold待补均保留。全部51条目目标继续，其他本地权重分支依用户指令暂缓。
