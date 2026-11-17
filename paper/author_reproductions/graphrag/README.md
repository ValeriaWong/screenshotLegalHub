# R04 / E24 GraphRAG：作者全局 API 分支与产品原索引验证

论文：[Edge et al. (2024), From Local to Global](https://arxiv.org/html/2404.16130v1)。作者代码：[microsoft/graphrag v0.1.1](https://github.com/microsoft/graphrag/tree/a81efe58c7c21ff8b17aa9bf1cb78a0750f3065b)。399个源文件/原示例均固定SHA-256及Git blob，原文件未修改。原文快照见paper_source.json；逐文件校验见source_fetch_results.json。

## 原方法、原输入输出与本轮程度

原索引流程：文档分块→LLM实体/关系抽取→合并与元素摘要→Leiden层级社区→自底向上社区报告。原全局查询：报告分批map产生带分数的要点，再过滤0分、按分数排序并reduce成答案。创新在于可复用的层级社区报告支持整篇语料sensemaking，而非只做向量近邻检索。

原输入为文本语料及全局问题，查询读取社区报告与实体元数据；原输出为自然语言答案与报告ID引用，中间有图/社区/分数。原benchmark为Behind the Tech播客和MultiHop-RAG新闻的全局问题，评价覆盖度、多样性、赋能和直接性；本轮没有运行原百万token benchmark。

复现程度：**直接执行作者原索引/全局查询代码的无嵌入API分支**。独立[algorithm.py](algorithm.py)只调用原工作流/类与处理I/O，没有另写简化建图/聚类/map-reduce来冒称原算法。产品E24主链见后端method_reproductions/r04_graphrag.py，原方法、出处、benchmark、适配差异均在文件开头。

原任务采用完整官方Notebook的Operation Dulce问题和全部三张预计算索引表；原表434行节点（含层级）、217实体、6报告，作者level=2过滤后217实体/5报告。本次只重新执行原查询，**没有重建作者这套原索引**。产品冻结文本则单独重建图/社区/报告，再执行同一个原查询算法；两种验证分开保存。

## 可运行环境与兼容边界

- 独立Python3.11.0、101个依赖均按作者poetry.lock约束锁定；setup_environment.py graphrag或--check可复核。
- 没有Torch、Transformers、spaCy、ONNX等运行包/模型加载，没有本地神经权重、GPU推理、训练或嵌入。Leiden仅处理本次小图；native原表中的预计算向量未用于相似度检索/模型推理。
- 原包在全局查询时也急切导入未用LanceDB/Azure Search。Windows旧LanceDB轮子不可用；[loader.py](loader.py)隔离后端注册，base.py原类型及typing.py两个原工厂类保留（AST载入类，注解延后）；未实现或调用这些后端。九类原组件实际导入通过，见import_probe.json。
- Python3.12旧gensim轮子、全包LanceDB依赖、首次缺Azure导入的探针失败均保留。未用自创后端填空。输入/Token替换、历史跟踪、解析和算法继续执行原函数。
- DeepSeek-V4.1-Flash-1017替代原GPT-4；原参数和实际参数分别保存。请求由父进程转发，密钥不进入原作者子进程。
- 禁用SDK重试、付费JSON重格式化和额外格式重生成。非法返回保留并停止；有独立零费用测试确认非法社区JSON不增加修复调用。

## 产品适配及实际结果

产品输入是冻结的预测KIE文本或案件陈述，没有读截图像素，也没有读专家答案。产品使用1200-token块、100重叠、一次gleaning，实体类型增加platform/message；嵌入、布局与可选covariates关闭。数据、调用、图、报告、所有14个原索引工作流表、map/reduce结果及最终JSON分别保存。

原索引与查询完整结束后，额外一次product_projection映射为VQA JSON或CaseAnalysisOutput。它能读取冻结锚点以定位逐字引文，构成额外信息读取和模型调用，可能影响产品结果；其参考分不能当作未适配GraphRAG的原benchmark成绩。原生答案也单独保留，可独立检查。

|轨道|新增调用|真实执行与结果|完整原始输入/回复/输出/测试|
|---|---:|---|---|
|原Notebook全局查询|2|原map/reduce实际执行，3个正分要点；答案列出主角、冲突，并对未明确反派保留不确定性；未评分|[完整I/O](../results/2026-10-29-per-paper/methods/r04_graphrag/runs/61234347b55fca45__native/r04_graphrag.INPUT_OUTPUT.md)|
|冻结KIE文本全局VQA|6|14原索引工作流，3实体/3关系/1报告；answer=null、开发参考分0|[完整I/O](../results/2026-10-29-per-paper/methods/r04_graphrag/runs/301dfd4b24097759__vqa_predicted_text/r04_graphrag.INPUT_OUTPUT.md)|
|案件产品|7|14原索引工作流，7实体/11关系/2报告；3条陈述/3引文通过Schema及逐字offset检查|[完整I/O](../results/2026-10-29-per-paper/methods/r04_graphrag/runs/54b98ea6c350b827__case_product/r04_graphrag.INPUT_OUTPUT.md)|

累计15/100次，输入26998/output5718 tokens，按当前配置价估算CNY0.09974（非账单）。15条实际回复均完整stop，实际返回模型均为用户授权DeepSeek。机器可读汇总：[validation_summary.json](validation_summary.json)。每次运行源码快照逐一校验，当前文件后续变更不会改写执行时快照。

已观察的质量限制：VQA把未见显式classify字段当作不能确定的理由而弃答；案件摘要写“三方陈述”，与两名说话人、三条陈述不一致。原回复保留，没有事后改成正确答案。结构、引用有效不等于事实/法律质量达标；专家评测按用户要求后补。

## 验证、调用和入口

[验证报告](../../../reports/author_expansion_20261029/REPORT_GRAPHRAG_API_2026-10-30.md)包含测试命令、退出状态与失败记录。最终相关后端54项通过；网页9项、TypeScript检查通过。HTTP使用隔离TestClient，没有重启另一窗口的18430，也没有声称做了本轮独立浏览器端到端验收。

run_validation.py --track native|vqa_predicted_text|case_product默认只计划，加--execute才调用模型。原查询上限2；文本VQA研究单元上限40；本次案件研究单元预留40且实用7，正式案件HTTP仍受既有30次运行上限约束。每篇历史/失败/未知/在途共用100次持久预算。write_io.py仅渲染既有记录，0次模型调用。

E24是新增生成/检索方法，不是将评测器冒充新的Agent。全部51条保留；本条完成的是指定无嵌入API分支的有限开发执行验证，完整原论文benchmark仍未复现。
