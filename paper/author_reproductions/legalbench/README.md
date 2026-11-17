# LegalBench — B04 / b04_legalbench

[论文：Guha et al. (2023)](https://arxiv.org/abs/2308.11462) / [作者代码](https://github.com/HazyResearch/legalbench/tree/b46bf4ffae90524b2b72aaa30e7745fe9db64481) / [固定作者原数据](https://huggingface.co/datasets/nguha/legalbench/tree/daec8237410aa23e3faf4bc41ad8b3a7e1696826)。固定180个作者代码/提示/说明文件（含162个基础提示）与23个原数据文件；独立Python3.12.15、16锁定依赖，不加载本地模型权重。

**复现程度：作者提示生成与评分代码直接执行，原任务代表和指定产品开发轨道已验证；完整162任务测试集及原论文成绩未复现。** 它是任务基准/评分器，不是生成Agent。作者UsingLegalBench.ipynb演示随机预测，没有LLM控制器；本项目增加的API传输不伪称作者控制器。

## 原方法、创新及原输入输出

创新是法律专业参与构建的162项多样任务、推理分类、定制few-shot提示与差异化评分协议。原输入为法律原文/问题及演示示例；原输出为类别、定义术语、引文、数值或开放答案；evaluation.py按任务执行平衡准确率、术语抽取、引文匹配、数值容差或集合F1，Rule QA要求人工评阅。

[原方法实现及完整头注](product_adapter.py)导入并执行作者完整utils.generate_prompts、tasks.py、evaluation.py，没有重写其算法。数据加载适配：从固定原TSV读入pandas，替代Notebook的datasets.load_dataset(...).to_pandas()；原数据字节逐项核对Git blob。[下载与哈希记录](source_downloads_verified.json)保留Git部分抓取失败后的固定版本HTTP恢复过程；未改SOLAR使用的旧数据。原文件、模型实际参数和全部源码快照均保存。

## 实际原任务验证

12组、11个不同任务、29个原测试样本：覆盖作者五个任务元数据分组，加abercrombie原application_prompt变体；同时覆盖特殊评分家族和人工任务状态。分类组按测试文件顺序取每个原标签首条，其余自动任务取首2条，人工任务取首1条。目标只用于评分/选择，不填入当前问题；原提示没有answer占位符。源提示中的既有few-shot答案按作者设计保留。162项基础提示与评测声明另做完整可用性核查，不等于162项测试集都已跑。

首次29次DeepSeek API，3条在当前512输出预算下截断。单独提高这3条上限到4096再调用3次，26条精确原回复复用；最终全部回复finish_reason=stop。没有清洗模型长解释、替换错误答案、自动抽取末尾标签或改原评分函数。原application_prompt要求解释，原精确匹配仍将整段原回复评分；0分如实保留。

|原组/任务|样本|原分数|
|---|---:|---:|
|issue_spotting / learned_hands_consumer|2|0.5|
|rule_recall / citation_prediction_classification|2|1|
|rule_conclusion / abercrombie|5|0.4|
|rule_application / abercrombie|5|0|
|interpretation / contract_nli_confidentiality_of_agreement|2|0.5|
|rhetoric / definition_classification|2|0.5|
|open_citation / citation_prediction_open|2|0.5|
|extraction / definition_extraction|2|1|
|numeric / sara_numeric|2|0|
|set_f1 / ssla_company_defendants|2|0.35294117647058826|
|shadowed_set_dispatch / successor_liability|2|0|
|original_manual / rule_qa|1|原人工任务，未评分|

这些是少量开发原例的不同指标，不合并成原论文准确率；Rule QA没有自动裁判或人工通过标记。

[首次29次完整输入/输出/回复/截断](../results/2026-10-29-per-paper/methods/b04_legalbench/runs/c241cad33d4f3073__native/b04_legalbench.INPUT_OUTPUT.md) · [最终3次恢复/26回复重用/原评分](../results/2026-10-29-per-paper/methods/b04_legalbench/runs/54416211eb315650__native/b04_legalbench.INPUT_OUTPUT.md)。每次请求均计B04共享上限。

## 原作者评分缺陷：保留并显式验证

[独立零付费探针](source_metric_probe.json) / [探针入口](probe_original_metrics.py)：

- SARA numeric把小数点删除：$100.00对$100得到0；这只是表示差异的算术反例，不能把本轮所有税额0分都归因为此缺陷。
- SSLA在每个参考项内部累计剩余FP：完全一致的Alpha,Beta集合得到0.8，独立集合F1应为1。
- successor_liability先落入EXACT_MATCH_BALANCED_ACC_TASKS，专用F1分支被遮蔽；单项命中两项参考的原dispatch=0、原专用F1=2/3。

原文件未改，原始分数与直接专用诊断分别保存。产品补充评分只使用已独立验证的原normalized exact-match balanced-accuracy函数，不使用上述有问题分支，不声称复现原论文数值成绩。

## 产品适配与真实输入输出

[逐方法调用文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/b04_legalbench.py) → [产品映射](../../../product_v1/backend/src/screenshotlegal/research/legalbench_scoring.py) → Benchmark.legalbench_score → 独立作者进程。原任务法律标签改为项目冻结的全局VQA分类标签；调用原函数直接比较，无A-D映射或语义裁判。KIE若有转录参考，则只在项目现有IoU匹配的消息文字字段上作补充精确匹配，位置/漏检等保留原评分，不能用该数值代替OCR或身份准确率。

真实整图VQA复用既有已完成生产者回答和原参考版本：原函数返回1，但仅有1个样本/1个实际参考类，预期标签有4类；不能据此估计四类平衡准确率或法律能力。参考仍legacy_unverified。原生成回复/原主评分均不变，新增供应商请求0。

[全局VQA完整原输入/回复/新原评分](../results/2026-10-29-per-paper/methods/b04_legalbench/runs/e5a6cb8737cf540d__product_scoring_vqa_image_full/b04_legalbench.INPUT_OUTPUT.md) · [KIE真实缺参考/未评分/0调用](../results/2026-10-29-per-paper/methods/b04_legalbench/runs/afbcb8620f654434__product_scoring_kie_image/b04_legalbench.INPUT_OUTPUT.md)。没有拿另一模型转录当Gold。

实际调用与导出已改：

- POST /v1/evaluation/benchmark-attempts/{id}/legalbench-score，body为idempotency_key；离线原评分器，无新增模型调用。
- benchmark.legalbench_score按owner、原回答、当前参考或流水线评分集绑定并独立保存benchmark.legalbench_score；同key缓存复用，原主评分不覆盖。
- 单任务结果/导出包含LawBench、LegalBench、RAGChecker各自命名的补充记录；流水线节点/导出包含已适配的两个离线评分器。
- 本轮通过隔离TestClient验收201、owner隔离、幂等及导出，并测试现有流水线；没有重启其他窗口在用的18430服务，没有声称该旧实例已加载新路由。

CLI：[run_native.py](run_native.py) --execute；三条恢复：[run_native_recovery.py](run_native_recovery.py) --execute；真实产品零付费重评分：[run_product_scoring.py](run_product_scoring.py)；再生MD：[write_validation_summary.py](write_validation_summary.py)（0调用）。同一B04持久账本累计32/100，原生、恢复、失败/未知均计数，后续不清零。实际模型为已配置DeepSeek-V4.1-Flash-1017。

## 记录与工程检查

[逐运行汇总/源码快照校验](validation_summary.json) · [环境](environment_state.json) · [锁定依赖](requirements.lock.txt) · [全部真实运行索引](../results/2026-10-29-per-paper/README.md)。4次执行记录、32个新增供应商请求，所有原源快照逐项SHA校验。

相关共享回归95项通过：原提示和公式、HTTP归属/缓存、流水线、旧LawBench、RAGChecker导出、预算与源码指纹。日志reports/author_expansion_20261029/test-legalbench-shared-scoring-api-regressions.log。首次KIE工程夹具缺task_id的1失败保留并已修正；工程夹具/探针均零供应商调用，不是模型质量或完整后端/浏览器全套验收。
