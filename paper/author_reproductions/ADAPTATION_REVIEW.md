# 原论文方法与本项目适配审查

这里按当前全部实验配置披露原任务与适配；配置数不是论文复现完成数。原清单51个条目全部保留在PAPER_COVERAGE.md。

original_paper_reproduced 指完整原论文benchmark，当前均为false。真实原样例、产品轨道与工程测试分别见 results/2026-10-29-per-paper/README.md；每篇共享100次请求上限。专家法律金标按用户要求后补。

| 配置 | 逐项说明 | 原代码状态 | 原 benchmark |
|---|---|---|---|
| e00_single_shot | [METHOD.md](../method_reproductions/e00_single_shot/METHOD.md) | not_applicable_project_baseline | 本项目基线 |
| e01_react | [METHOD.md](../method_reproductions/e01_react/METHOD.md) | author_controller_native_and_product_real_validated | ReAct: HotpotQA、FEVER、ALFWorld、WebShop；原任务分别采用回答/核验或环境成功率指标。 |
| e02_staged_without_matterpack | [METHOD.md](../method_reproductions/e02_staged_without_matterpack/METHOD.md) | not_applicable_project_baseline | MetaGPT: HumanEval、MBPP、SoftwareDev。 |
| e03_staged_with_matterpack | [METHOD.md](../method_reproductions/e03_staged_with_matterpack/METHOD.md) | not_applicable_project_baseline | JurisMA: 修订版 LawBench；JurisCQAD 用于训练/DPO。另有 LegalBench-RuleQA 小样本迁移实验。；SCALE: ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。 |
| e04_symbolic_verifier | [METHOD.md](../method_reproductions/e04_symbolic_verifier/METHOD.md) | author_stage_ii_and_stage_i_pre_review_executed_pending_review_and_product | SOLAR / On Verifiable Legal Reasoning: LegalBench 的 SARA numeric，论文研究 96 个税务计算案例；不是民事证明责任数据。 |
| e05_self_refine | [METHOD.md](../method_reproductions/e05_self_refine/METHOD.md) | author_controller_native_and_product_real_validated | Self-Refine: 论文七类任务：Yelp 情感反转、对话响应、PIE 代码优化、CodeNet 可读性、GSM8K、缩写生成、CommonGen；本次原生示例不是整套 benchmark。 |
| e06_legalreasoner_verifier | [METHOD.md](../method_reproductions/e06_legalreasoner_verifier/METHOD.md) | original_benchmark_not_reproduced | LegalReasoner: LegalHK、CMDL，论文采用各自训练/验证/测试划分；不与我们的合成聊天夹具同分布。；VERDICT: CAIL2018（CAIL-Small）、未来时间划分 CJO2025；当前作者 CLI 仅暴露 cail2018。 |
| e07_agentscourt_adversarial | [METHOD.md](../method_reproductions/e07_agentscourt_adversarial/METHOD.md) | original_benchmark_not_reproduced | AgentsCourt: SimuCourt，420 份中文裁判文书，涉及民事、行政、刑事及审级设置；配套 Legal-KB。；L-MAD (Nguyen et al., 2026): COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。 |
| e08_agentscourt_judge | [METHOD.md](../method_reproductions/e08_agentscourt_judge/METHOD.md) | original_benchmark_not_reproduced | AgentsCourt: SimuCourt，420 份中文裁判文书，涉及民事、行政、刑事及审级设置；配套 Legal-KB。；L-MAD (Nguyen et al., 2026): COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。 |
| e09_l_mad | [METHOD.md](../method_reproductions/e09_l_mad/METHOD.md) | LMAD_author_code_unverified_cited_MALLM_components_executed | L-MAD (Nguyen et al., 2026): COLIEE Task4 R05/R06/R07分别109/73/82条，accuracy。原Qwen3/Llama模型、本地bfloat16和完整年度成绩未复现。；Towards a Science of Scaling Agent Systems: 当前核对版本包含 BrowseComp-Plus、Finance-Agent、PlanCraft、WorkBench，并报告 SWE-bench Verified、Terminal-Bench 小规模扩展。 |
| e10_factor_guided_retrieval | [METHOD.md](../method_reproductions/e10_factor_guided_retrieval/METHOD.md) | original_benchmark_not_reproduced | SCALE: ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。；Legal-DC / LegRAG: Legal-DC：480 份法律文档、2,475 个问答，条款级标注；不是聊天真实性或举证责任测试集。 |
| e11_legal_r1 | [METHOD.md](../method_reproductions/e11_legal_r1/METHOD.md) | original_benchmark_not_reproduced | Legal-R1: LawBench、LexEval；法条检索另有 provision-oriented 查询。原规范库与 LeCaRDv2 类案库须版本匹配。 |
| e12_crag | [METHOD.md](../method_reproductions/e12_crag/METHOD.md) | original_benchmark_not_reproduced | CRAG: PopQA、Biography、PubHealth、ARC-Challenge；分别使用任务准确率或 FactScore 等原指标。 |
| e13_graphreader | [METHOD.md](../method_reproductions/e13_graphreader/METHOD.md) | original_benchmark_not_reproduced | GraphReader: LongBench 的 HotpotQA、2WikiMultihopQA、MuSiQue、NarrativeQA；LV-Eval HotpotWikiQA-mixup。 |
| e14_chain_of_agents | [METHOD.md](../method_reproductions/e14_chain_of_agents/METHOD.md) | not_executed_no_verified_author_repository | Chain of Agents (Zhang et al., 2024): HotpotQA、MuSiQue、NarrativeQA、Qasper、QuALITY、QMSum、GovReport、BookSum、RepoBench-P。原QA F1、摘要ROUGE与代码相似度分轨记录；未跑完整benchmark。 |
| e15_raptor | [METHOD.md](../method_reproductions/e15_raptor/METHOD.md) | author_algorithm_product_adapter | RAPTOR: NarrativeQA、QASPER、QuALITY。 |
| e16_lightrag | [METHOD.md](../method_reproductions/e16_lightrag/METHOD.md) | author_algorithm_product_adapter | LightRAG: UltraDomain 中 Agriculture、CS、Legal、Mix 四域。 |
| e17_lawflow_review | [METHOD.md](../method_reproductions/e17_lawflow_review/METHOD.md) | original_benchmark_not_reproduced | LawFlow: LawFlow 工作流数据及人类与 LLM 工作流比较；不是现有截图案件的法律准确率 benchmark。 |
| e18_jurisma | [METHOD.md](../method_reproductions/e18_jurisma/METHOD.md) | not_executed_no_verified_author_repository | JurisMA: 修订版 LawBench；JurisCQAD 用于训练/DPO。另有 LegalBench-RuleQA 小样本迁移实验。 |
| e19_scale | [METHOD.md](../method_reproductions/e19_scale/METHOD.md) | author_native_and_case_product_real_validated | SCALE: ECHR 案例上的专家评测及 LLM-as-a-Judge 对照；不同法域，不能直接作为中国民事案件 Gold。 |
| e20_verdict | [METHOD.md](../method_reproductions/e20_verdict/METHOD.md) | original_benchmark_not_reproduced | VERDICT: CAIL2018（CAIL-Small）、未来时间划分 CJO2025；当前作者 CLI 仅暴露 cail2018。 |
| e21_reflexion | [METHOD.md](../method_reproductions/e21_reflexion/METHOD.md) | author_algorithm_product_adapter | Reflexion: HotpotQA、ALFWorld、HumanEval等；本适配选择作者CoT_context分支 |
| e22_metagpt | [METHOD.md](../method_reproductions/e22_metagpt/METHOD.md) | author_software_sop_and_case_product_validated_native_qa_executed_with_failures | MetaGPT: HumanEval、MBPP、SoftwareDev。 |
| b01_legalagentbench | [METHOD.md](../method_reproductions/b01_legalagentbench/METHOD.md) | author_controller_controlled_replay_live_service_unavailable | LegalAgentBench author baseline controllers: 300个原任务；success/progress substring匹配，另有远程BERTScore分支。不是截图KIE或专家案件金标。 |
| r04_graphrag | [METHOD.md](../method_reproductions/r04_graphrag/METHOD.md) | author_global_query_and_no_embedding_index_workflows | GraphRAG: Behind the Tech播客与MultiHop-RAG新闻的全局问题；LLM成对覆盖度、多样性、赋能和直接性。官方Notebook原例不是原百万token benchmark。 |

## 作者评测器（独立于生成配置）

[B02 LawBench](lawbench/README.md) · [B04 LegalBench](legalbench/README.md) · [B15 RAGChecker](ragchecker/README.md) · [评测器实现状态](EVALUATOR_IMPLEMENTATION_STATUS.json)

评测器有独立原任务/产品适配，不因不能输出CaseAnalysisOutput而移出51条范围；不伪装为新的生成Agent配置。
