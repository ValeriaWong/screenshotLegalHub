# RAGChecker — B15 / b15_ragchecker

[论文：Ru et al., RAGChecker](https://arxiv.org/abs/2408.08067) / [作者源码](https://github.com/amazon-science/RAGChecker/tree/6091f08c00e676e87a970f2aeb4a23a484746348) / [作者所用RefChecker](https://github.com/amazon-science/RefChecker/tree/1df1b25cee792ba2b171302e31ca4f768bd67703)。两个仓库分别固定15/33文件；独立Python3.12.15、11依赖，无spaCy/Torch/Transformers或模型权重加载。

**复现程度：作者默认API分支的原任务与指定产品开发轨道已真实执行；不是完整4k题benchmark或人类相关性结果复现。** RAGChecker是评测器，不是生成案件分析的Agent，未把它伪装成新的E24生成配置。

## 原方法、创新与原输入输出

创新是将回答与参考分解成三元组声明，执行answer→response、response→answer、retrieved→answer、retrieved→response四类蕴含检查，计算原11项总体/检索/生成诊断指标。原输入为query、gt_answer、response、retrieved_context[{doc_id,text}]；原输出包括声明、四类检查矩阵和逐样本/宏平均指标。论文benchmark为4k题、10领域及人工meta-evaluation。

[方法实现头注与原控制器入口](product_adapter.py)直接执行原RAGChecker.evaluate、RAGResults、computation/METRIC_FUNC_MAP，以及原RefChecker LLMExtractor/LLMChecker、原提示、解析与合并。没有用自写分数替代作者公式。原默认triplet不调用RCText，RAGChecker固定max_reference_segment_length=0；仅跳过未使用的重模型/SDK预加载。其他分句/子句、NLI、AlignScore与localizer分支明确拒绝。模型返回的Python元组使用literal_eval代替eval；正则与去重规则不改。

## 完整原示例实际验证

作者examples/checking_inputs.json两条完整原示例均执行（尼罗河、刚果旗帜）；全部原数据原样输入，原默认joint-check每组5声明，原全部11指标完成。首次46次调用；一条无标签回复被原解析器补Neutral。单独重验1次仍被截断。之后仅对该一条增加明确“只输出标签”的system格式指令，再新增1次，45条精确原回复复用，原完整图与指标重算；最终所有标签数量匹配。旧两次未通过检查的执行记录保留。原模型改为用户授权DeepSeek，不能把新分数当原论文成绩。

最终原示例宏平均：precision52.8、recall52.5、F1 50.7、faithfulness65.0。这只描述这两题在当前裁判模型下的输出，未评价裁判正确率。

[首次完整输入/输出/46回复](../results/2026-10-29-per-paper/methods/b15_ragchecker/runs/4848902c9cdff847__native/b15_ragchecker.INPUT_OUTPUT.md) · [单条原提示重验/截断](../results/2026-10-29-per-paper/methods/b15_ragchecker/runs/11fba6c917dbcd05__native/b15_ragchecker.INPUT_OUTPUT.md) · [最终格式差异/原图重算/全部回复](../results/2026-10-29-per-paper/methods/b15_ragchecker/runs/71538dc3aaf14bf6__native/b15_ragchecker.INPUT_OUTPUT.md)。缓存不是新调用；原失败和重放来源逐次可查。

## 产品适配：实际输入不相同，指标也不能照搬

[逐方法调用文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/b15_ragchecker.py) → [产品映射](../../../product_v1/backend/src/screenshotlegal/research/ragchecker_scoring.py) → Benchmark.ragchecker_score。调用方提供已授权、持久化预算的raw_call；本模块没有密钥或隐式模型客户端。原回答、其实际冻结KIE输入、同图上游引用及参考版本绑定；独立保存benchmark.ragchecker_score，不覆盖原评分或原回答。目前提供后端/CLI入口，没有新增HTTP付费触发按钮或重启当前服务。

第一版将全局分类标签直接交原11指标，6次调用后发现“candidate answer is non_legal_dialog”只是标签描述，不是KIE原文中的事实。该[真实试跑](../results/2026-10-29-per-paper/methods/b15_ragchecker/runs/167ca328d5ee9c9e__product_scoring_vqa_predicted_text/b15_ragchecker.INPUT_OUTPUT.md)保留用于说明适配失败：标签F1=100但faithfulness=0，不能解读为分类能力或事实准确率。

最终对分类任务只比较原回答附带的证据文字与实际冻结KIE输入，调用原faithfulness指标；gt_answer为空且不请求任何依赖Gold的指标。原分类标签对错继续由已有评分处理。真实2次API：7段原证据文字经原三元组去重形成5个声明，5个Entailment，faithfulness=100。重复次数、消息身份/位置、OCR真实性以及法律判断均不由该分数验证。参考状态仍legacy_unverified；此次指标不使用该标签作Gold。

[最终产品全部输入/输出/2次真实回复](../results/2026-10-29-per-paper/methods/b15_ragchecker/runs/f262bb52ae43b062__product_scoring_vqa_predicted_text/b15_ragchecker.INPUT_OUTPUT.md) · [原补充评分及来源绑定](../results/2026-10-29-per-paper/methods/b15_ragchecker/runs/f262bb52ae43b062__product_scoring_vqa_predicted_text/b15_ragchecker.output.json)。原主评分和生产者回答不变的机械检查均通过。

KIE代码支持有冻结human_transcript时仅用原overall_metrics比较消息文字，排除坐标；本次真实KIE样本没有转录参考，[明确未评分/0调用](../results/2026-10-29-per-paper/methods/b15_ragchecker/runs/c83c7fd63077a64e__product_scoring_kie_image/b15_ragchecker.INPUT_OUTPUT.md)，没有拿另一模型输出冒充人工转录。也没有将图片直接伪造为RAG检索文字。

## 请求、源码与工程记录

B15整篇累计56/100：首次原例46＋无格式改动重验1＋格式适配重验1＋不合适分类指标试跑6＋最终证据忠实度2；两次真实KIE缺参考检查各0。所有历史/失败/未知/在途均计上限，后续不清零。实际模型均DeepSeek-V4.1-Flash-1017。

[逐运行汇总](validation_summary.json) / [完整记录索引](../results/2026-10-29-per-paper/README.md) / [独立环境校验](environment_state.json)。每次运行包含完整源码快照并逐项重新校验；重放只复用完全匹配的原提示/参数对应回复，改动的格式system和实际有效请求分别存储。

工程：原控制流/公式/失败不重试、产品冻结绑定、缺参考、跨图片拒绝、幂等缓存与主评分不覆盖均验证。相关共享回归87项通过；最终含分类证据适配专项13项通过（与87项有12项重叠）。最初工程夹具缺db事务失败记录保留并已修正；不涉及供应商调用。日志在reports/author_expansion_20261029/test-ragchecker-*.log。

复跑入口：原示例run_native.py --execute，目标调试run_native_recheck.py / run_native_format_recheck.py，产品run_product_scoring.py --execute；全部仍共用B15账本。write_validation_summary.py不调用模型，仅从已有记录再生可读MD。每次付费运行必须在现有剩余预算内，不因复跑重置上限。
