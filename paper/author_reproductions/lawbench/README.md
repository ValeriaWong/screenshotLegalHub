# B02 LawBench：官方数据、评分代码与产品补充指标

论文：[LawBench: Benchmarking Legal Knowledge of Large Language Models（EMNLP 2024）](https://aclanthology.org/2024.emnlp-main.452/)；[作者仓库](https://github.com/open-compass/LawBench/tree/e30981bb3ff54c41571f222e0b23e92d27375388)。提交固定为 e30981bb3ff54c41571f222e0b23e92d27375388，79个源码/数据文件校验见 ../sources.lock.json。

## 原方法、任务与复现范围

这是一套20类中文法律能力任务及官方评分协议，覆盖知识记忆、理解、应用；创新点是组合多种法律能力任务、不同任务指标及zero-shot/one-shot设置。它不是新训练模型，也不是可替代案件控制器的Agent。

原数据每任务、每提示模式有500条。本轮按固定顺序选每个可执行任务的第0条；不根据参考答案或模型结果挑样本。实际执行19类×zero/one-shot共38次AIPING调用，使用现有DeepSeek-V4.1-Flash-1017替换原论文参评模型。原作者评分函数和main.py CLI均实际执行，原源码未改。完整benchmark没有复现。

2-1文书校对的ChERRANT tokenizer需要LTP/Torch本地模型，按用户“先略过本地计算资源”的指令暂缓。没有用简化编辑距离顶替官方评分。其余评分仅用普通Python文本依赖，不装Torch、不下载模型权重，不运行嵌入或训练。

原输入是 instruction、question、answer；只把前两项拼为模型可见用户消息。当前题answer留在评分器；one-shot作者给的示范例题保留。原输出是纯文本prediction，官方评分输入为 origin_prompt / prediction / refr，输出是原始评分字典和CSV。

## 实现与实际调用

- [独立逐篇实现与完整出处/I/O注释](adapter.py)：核验原文件哈希；执行原main.py中的任务映射、原评分函数及原CLI。保留原2-6的anstention_rate拼写与CSV默认行为。
- [原任务运行器](run_native.py)：38个真实请求、同一B02持久账本、每篇100次上限、不隐式重试、不重置历史；当前38/100。
- [产品评分桥](../../../product_v1/backend/src/screenshotlegal/research/lawbench_scoring.py)：KIE匹配后文本字符F1、全局文本VQA字符F1、分类标签到原选择题A-D的显式映射。
- [真实历史产品输出重评分](run_product_scoring.py)：复用已保存的真实截图模型回复，新增供应商请求0。
- [独立环境17个依赖锁](requirements.lock.txt)与[环境检查](environment_state.json)。

PowerShell环境检查（不调用模型）：

```powershell
product_v1/.conda/screenshotlegal-v1/python.exe -X utf8 -B paper/author_reproductions/setup_environment.py lawbench --check
```

原任务运行器默认只生成计划；--execute使用既有每篇100次授权。已有成功计划不重跑；改变实现生成新计划也不会清零共享计数。

## 真实输入、回复、输出与测试

[38个原任务完整可读输入输出](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/d0ad3fba76db4517__native/b02_lawbench.INPUT_OUTPUT.md) · [原始输入及仅评测参考](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/d0ad3fba76db4517__native/b02_lawbench.input.json) · [逐次真实请求/回复/用量](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/d0ad3fba76db4517__native/b02_lawbench.model_responses.json) · [原输出与官方分数](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/d0ad3fba76db4517__native/b02_lawbench.output.json) · [测试记录](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/d0ad3fba76db4517__native/b02_lawbench.test_results.json) · [原始来源快照/模型/选择规则](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/d0ad3fba76db4517__native/b02_lawbench.provenance.json)。同目录保留两种提示模式的官方CSV和CLI输出。

原任务阅读理解2-5的zero/one-shot字符F1分别0.7273/0.4127；实体抽取2-6分别0/0.8889。zero-shot回复使用Markdown加粗实体名，原解析器未识别，原样记0；one-shot还存在“手机”和参考“查获手机”的边界差异。没有修饰回复或重试来抬高分数。每种任务仅1条，不能合并成可靠模型能力排名或宣称优于论文。

[真实KIE产品评分输入](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/063353722e8b1dfc__product_scoring_kie_image/b02_lawbench.input.json) · [输出](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/063353722e8b1dfc__product_scoring_kie_image/b02_lawbench.output.json)：没有消息级参考转录，返回unscored_missing_reference、score=null，不编造金标。

[真实全局VQA产品评分输入](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/ef8b05ec1a228cf4__product_scoring_vqa_image_full/b02_lawbench.input.json) · [输出与映射](../results/2026-10-29-per-paper/methods/b02_lawbench/runs/ef8b05ec1a228cf4__product_scoring_vqa_image_full/b02_lawbench.output.json)：冻结四标签映射A-D，原选择题评分得1；参考是legacy_unverified开发参考，不能视为人工或专家准确率。

## 产品适配与边界

产品可对已保存的benchmark或pipeline attempt调用 POST /v1/evaluation/benchmark-attempts/{id}/lawbench-score，JSON只需idempotency_key，不接收客户端上传答案。参考绑定既有主评分版本；结果独立保存在benchmark.lawbench_score，并进入原任务运行导出、流水线节点详情和流水线总导出。现有主评分不覆盖，整个操作不调用模型。接口已作归属隔离、幂等、导出与流水线版本绑定测试。

- 全局分类：按冻结allowed_values顺序映射到A-D，原1-2函数算准确率/弃答率。未知标签按弃答，不能直接把模型返回的字母当有效产品标签。任务内容由法律知识选择题变为截图分类，这是显式领域适配。
- 全局文本/文件名：原2-5字符F1只衡量文本重合，不替代文件名精确匹配、身份、金额币种或法律分析评分。
- KIE：先用现有IoU匹配消息，再对有参考的字段调用原2-5字符F1。缺失/多余消息继续体现在原检测分；匹配字段文本很像不等于整体检测正确。现有真实样本缺转录，质量分保持空。
- 原2-6是十种刑事实体抽取，不能直接改名为speaker/timestamp等消息字段；未假称截图KIE复现原NER。

本条目仍为部分完成：官方19/20任务开发样本验证＋产品评分接口完成，2-1暂缓、KIE参考缺失、完整benchmark未运行。没有增加“整篇三阶段完成”计数。专家法律Gold后补不阻止接口和可执行分支继续完善。

[本轮报告](../../../reports/author_expansion_20261029/REPORT_LAWBENCH_API_2026-10-30.md) · [全部真实记录索引](../results/2026-10-29-per-paper/README.md)
