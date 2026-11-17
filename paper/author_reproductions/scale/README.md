# SCALE — L09 / e19_scale

论文：[Structured Case-law-guided Anticipatory Legal Reasoning](https://aclanthology.org/2026.emnlp-main.36/)。[作者源码](https://github.com/khatrimann/SCALE/tree/1700924ca8c448af56c854e5e4c9ae693e86beb3)固定提交1700924ca8c448af56c854e5e4c9ae693e86beb3。

原方法以ECHR案例、公约条文和Case-law Guides为输入，从指南构建Issue–Factor层级，匹配问题/因素，沿¶编号取段落并逐批更新LAW分析。原任务benchmark为ECHR法律推理的专家评估；本次没有运行完整benchmark。

[原任务入口](product_adapter.py)已验证作者公开案例001-231088的1_PROTOCOL_1与6_CIVIL，使用作者发布的预建层级；原Stage I/II未在该原生样本中重建。[原生输入/输出/逐次回复](../results/2026-10-29-per-paper/methods/e19_scale/runs/871c73bab1bb87ef__native/)单列。

[产品方法实现](case_adapter.py)由[产品E19](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e19_scale.py)经[传输桥](../../../product_v1/backend/src/screenshotlegal/method_reproductions/scale_bridge.py)调用。实际加载作者StageProcessing(3/4)、ReasoningStage与filter_issues/extract_paras/extract_selected_paragraphs/batch_paras，函数体不变。Stage I/II使用作者公开提示词并在适配器装配；仅输入独立法源，不输入案件、问题或Gold。

领域适配将ECHR指南换为独立冻结的中国法规集合；中文研究分析提示替代裁判提示；末尾增加CaseAnalysisOutput投影。原/新提示及hash完整保存。这验证结构迁移，不能验证原论文的判例指南/先例覆盖收益，不声称法律准确率。未复核法源保持unverified，派生层级标为not_expert_reviewed；案件单方陈述不升级为裁判事实。不能直接执行像素KIE。

[本次真实产品输入](../results/2026-10-29-per-paper/methods/e19_scale/runs/699386efcd2665c0__case_product/e19_scale.input.json) · [输出](../results/2026-10-29-per-paper/methods/e19_scale/runs/699386efcd2665c0__case_product/e19_scale.output.json) · [逐次模型回复](../results/2026-10-29-per-paper/methods/e19_scale/runs/699386efcd2665c0__case_product/e19_scale.model_responses.json) · [层级/段落/迭代产物](../results/2026-10-29-per-paper/methods/e19_scale/runs/699386efcd2665c0__case_product/e19_scale.author_artifacts.json) · [测试](../results/2026-10-29-per-paper/methods/e19_scale/runs/699386efcd2665c0__case_product/e19_scale.test_results.json)。

真实API新增6次，累计66/100（原生、产品、失败与历史共享）。三项来源跨度逐字校验通过；没有专家语义/法律评分。本分支不加载本地模型权重。首次产品尝试因旧模板缺少法条原文在发送前失败，保留0777d8d324759cd0记录，新增调用0。

[法源提取脚本](prepare_legal_sources.py)、[官方原文快照和提取出处](native_inputs/legal_sources.json)可审查；只补原文与SHA256，没有自动批准专家审核。原快照时间在成功计划快照中曾用静态时间，当前出处文件改为读取文件实际保存时间；法律文本和原网页hash不变。

工程验证：test_scale_author_product.py实际执行作者组件，覆盖独立法源与案件隔离、提供层级分支、越界¶拒绝、HTTP分发与导出。最终相关后端91项通过；前端类型检查通过。Demo/确定传输测试不是真实模型结果。

运行：独立环境见requirements.lock.txt；运行器为[run_case_product.py](run_case_product.py)，默认仅计划，--execute执行，始终共用原有100次持久账本。已有真实成功结果无需重复付费运行；当前源版本变化会形成新计划，不能当无成本重放。
