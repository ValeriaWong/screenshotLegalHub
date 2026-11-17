# L10 L-MAD：论文协议＋所引原组件的 API 适配

复现等级：**paper_specification_with_cited_upstream_components**。本目录有可运行的独立环境、两种原任务协议、真实 API 请求及产品调用；没有核实 L-MAD 作者仓库，不能称为作者原工程复现。全部原论文 benchmark 尚未复现。

## 来源与原方法

- [论文 v1](https://arxiv.org/html/2607.09099v1)；本地 [PDF](paper_v1.pdf)、[TeX](example_paper.tex)、[协议/证据校验值](specification.lock.json)、[原附录提示](paper_prompts.json)。HTML 丢失的日文提示由原 TeX 核对。
- 论文引用的框架 [MALLM](https://github.com/Multi-Agent-LLMs/mallm/tree/eeec9f5c28961a7349cbb4306a5aa860bdaef6dd)，固定提交 eeec9f5c28961a7349cbb4306a5aa860bdaef6dd。11 个执行依赖源码文件的哈希在上级 sources.lock.json；不把 MALLM 当作 L-MAD 作者仓库。
- 原任务：相关日本民法条文 premise ＋法律命题 hypothesis → Y/N 蕴含判断及简要解释。原 benchmark 为 COLIEE Task 4 R05/R06/R07（109/73/82 样本），原实验使用 Qwen3/Llama 本地模型。创新比较三角色中立讨论、不同共识阈值与固定轮数后的排序投票，并限制近期讨论上下文。
- 本次原任务输入是论文第 2.1 节英文 Article 9 示例：成年被监护人的日常必需品交易能否由监护人取消，参考 N。**不是下载并验证了上述年度 COLIEE 数据集**。[实际输入](native_inputs/paper_illustration.json)。参考仅评分端使用，不进入模型消息。

## 真正执行在哪里

|入口|实际职责|
|---|---|
|[algorithm.py](algorithm.py)|论文调度：3 角色、初始独立回答、近期两轮上下文、hybrid 共识、ranked 投票与平票补充轮；开头列明来源、原 I/O、benchmark 和复现差异|
|[mallm_components.py](mallm_components.py)|从锁定源码 AST 加载原数据类、SimpleResponseGenerator 模板、agreement/投票提示、ThresholdConsensus 和 RankedVoting 原方法体；不重写这些方法体|
|[product_adapter.py](product_adapter.py)|独立子环境 JSON 传输，不持有供应商密钥|
|[E09 方法文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e09_l_mad.py)|run 接案件链；run_task 接文本全局 VQA，替换旧通用 debate 原型|
|[产品映射](../../../product_v1/backend/src/screenshotlegal/method_reproductions/lmad_bridge.py)|逐候选二值蕴含；案件事实提出→核验→代码固定事实集合→五字段修订补丁→图/引用校验|
|[run_validation.py](run_validation.py)|原任务/产品实际执行，持久 L10 共享预算，源文件快照和逐次回复落盘|

独立环境 paper/.author_envs/l_mad：Python 3.12.15、0 个额外依赖，无 Torch/本地权重/嵌入。[依赖锁](requirements.lock.txt) · [环境检查](environment_state.json)。父进程使用已有 AIPING 配置；DeepSeek-V4.1-Flash-1017 替换论文原模型。子进程仅收到消息，不接收 API key。

## 与原论文/框架的差异

1. 精确 L-MAD 讨论提示、调度源码未公开核实；采用所引 MALLM 原 SimpleResponseGenerator 模板并按论文描述调度。原组件执行不代表原整套 Coordinator 被执行。
2. 附录 A.1 三个人设固定复用，未重新自动生成。产品另用中立证据审查、支持审查、反例审查角色，不伪装成日本诉讼角色。
3. 本实现把“近期两轮”明确为当前轮开始前的两个完整轮次，并冻结各角色可见历史；论文未给出精确源码。传输串行，记录可见消息 ID。
4. 论文 hybrid：先一致，末轮退回 >.66。原 MALLM HybridMajority 默认 .75/第5轮/3人总是一致，与论文不同；故实际执行原 ThresholdConsensus 并配置论文阈值。默认轮上限 3 是本项目有界设定。
5. ranked 固定 3 轮后完整排序、原 Borda 计分；平票追加一完整讨论轮和投票，仍平票返回 unknown。论文未明确的耗尽策略被显式限制；不以首个角色打破平票。
6. 论文要求完整排序，本实现拒绝不完整 ballot；不调用 MALLM 10 次解析重试路径。正文 Answer:Y/N 与附录 判断:Y/N 冲突保留为独立解析模式，不悄悄转写。
7. 温度 .1 与论文一致；1024 输出 token 上限是本项目设置，不冒称论文参数。DeepSeek 模型替换、固定人设等使结果不能等同原论文成绩。
8. A08 只是 E09 的既有设计引用，**本目录不构成 A08 方法复现**。

## 真实结果与直接查看输入/输出

|轨道/协议|实际调用|结果|可读记录|
|---|---:|---|---|
|原任务 hybrid|5|N，命中论文示例 N|[完整 I/O](../results/2026-10-29-per-paper/methods/e09_l_mad/runs/a2386156d6841124__native__hybrid/e09_l_mad.INPUT_OUTPUT.md)|
|原任务 ranked|12|N，命中同一示例 N|[完整 I/O](../results/2026-10-29-per-paper/methods/e09_l_mad/runs/b21b140da9086225__native__ranked/e09_l_mad.INPUT_OUTPUT.md)|
|全局文本 VQA hybrid|17|弃答，旧开发参考得分 0；两个标签都没有唯一正向支持|[完整 I/O](../results/2026-10-29-per-paper/methods/e09_l_mad/runs/1814043722ca8211__vqa_predicted_text__hybrid/e09_l_mad.INPUT_OUTPUT.md)|
|全局文本 VQA ranked|30|弃答，得分 0；真实触发平票补充轮，仍平票时保持未知|[完整 I/O](../results/2026-10-29-per-paper/methods/e09_l_mad/runs/d60074513de5d1a1__vqa_predicted_text__ranked/e09_l_mad.INPUT_OUTPUT.md)|
|案件首试 hybrid|1|失败：要件引用未生成的事实 ID，结构入口即拒绝|[失败 I/O](../results/2026-10-29-per-paper/methods/e09_l_mad/runs/df63d7f9b390e5d5__case_product__hybrid/e09_l_mad.INPUT_OUTPUT.md)|
|案件第二试 hybrid|16|失败：核验未接受事实，但模型修订恢复了原事实，被拒绝|[失败 I/O](../results/2026-10-29-per-paper/methods/e09_l_mad/runs/1a6a5128c2ffd31d__case_product__hybrid/e09_l_mad.INPUT_OUTPUT.md)|
|案件修正后单事实 hybrid|11|结构/图引用校验通过；候选未获确认，最终 facts=[]，不代表事实提取有效|[完整 I/O](../results/2026-10-29-per-paper/methods/e09_l_mad/runs/b075523bcd722ec1__case_product__hybrid/e09_l_mad.INPUT_OUTPUT.md)|

累计 **92/100** 次真实供应商调用，含失败和所有协议，不重置。两种原任务都只覆盖同一个论文示例，不能报告法律准确率。文本 VQA 只读取冻结的真实 KIE 预测，旧参考未经过专家审核；N 不等于相反标签成立，故逐一验证两个标签，只有唯一 Y 才选择答案。

案件仅是我们增加的产品映射，非论文原输出：第一、二试的失败保留。最终改用五字段修订补丁，代码组装不可变 facts，再校验引用。当前真实样本没有已接受事实，summary 仍复述原文且存在把陈述写成事实的质量风险；只证明执行/输出结构闭环，**不称有效证据提取或法律推断**。ranked 案件未另试；像素 KIE、开放问答、四分类不适配该二值入口，执行前明确拒绝。

每条可读记录包括完整输入、评分端参考、每次实际 messages、原始 raw 回复、参数/usage/成本估计、最终输出、失败原因和工具/投票数据链接。机器可读 [run_summary.json](run_summary.json)；运行目录带源文件快照，后续修订不覆盖历史执行代码。

## 可复查命令

```powershell
product_v1/.conda/screenshotlegal-v1/python.exe paper/author_reproductions/setup_environment.py l_mad --check
product_v1/.conda/screenshotlegal-v1/python.exe paper/author_reproductions/l_mad/run_validation.py --track native --protocol hybrid
product_v1/.conda/screenshotlegal-v1/python.exe paper/author_reproductions/l_mad/summarize_validation.py
product_v1/.conda/screenshotlegal-v1/python.exe -m pytest product_v1/backend/tests/test_lmad_protocol.py product_v1/backend/tests/test_lmad_product.py -q
```

不带 --execute 只生成计划。再次真实试跑仍受同一 L10 预算，不建议消耗最后 8 次来重复已有轨道。专家法律金标后补，不阻止当前原任务/产品执行，但不得将共识、结构合法或字面引用校验当作专家正确率。
