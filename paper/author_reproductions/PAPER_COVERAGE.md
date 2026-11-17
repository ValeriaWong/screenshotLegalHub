# 全部51条目覆盖台账

登记 51 条文献；现有 25 个配置引用 22 个不同条目；另有3个作者评测器接入。配置/接口数不是复现完成数。

当前先略过本地模型权重推理/训练与重计算分支；范围仍保留全部51条目，详见RESOURCE_PRIORITY_2026-10-30.md。
保留所有未完成条目。主页面已下载表示来源可访问，不表示已阅读/实现方法。基准论文也保留待适配状态，不因不是生成方法而自行移出用户范围。
本轮三阶段完成只指独立环境、原任务真实执行、指定产品轨道的开发样本完成；完整原论文benchmark和专家准确率另列。

|ID|文献|配置|当前实际状态|方法/原任务资料|
|---|---|---|---|---|
|L01|He et al. (2024), *AgentsCourt: Building Judicial Decision-Making Agents with Court Debate Simulation and Legal Knowledge Augmentation*. EMNLP Findings.|E07,E08|作者庭辩组件已真实执行；完整Legal-KB重排需本地BGE权重，按用户要求暂缓；原完整检索/裁判与产品未完成|[作者源码](https://github.com/Zhitao-He/AgentsCourt/tree/7c14d6960abfdfdd7366250905da8dbcb416d6d6) / [ E07 ](../method_reproductions/e07_agentscourt_adversarial/METHOD.md) / [ E08 ](../method_reproductions/e08_agentscourt_judge/METHOD.md)|
|L02|Sun et al. (2024), *LawLuo: A Multi-Agent Collaborative Framework for Multi-Round Chinese Legal Consultation*.|尚未建配置|作者ToLC示例精确固定/AST检查失败；含未定义返回占位，原任务未运行，0次新增模型调用；完整训练/本地模型分支暂缓；当前本地资源分支按用户要求暂缓|[作者源码](https://github.com/NEFUJing/LawLuo/tree/d3fe4c75af15db4933a89962eaacff3b1b414c41) / [原源码/AST失败/资源暂缓](lawluo/README.md)|
|L03|Das et al. (2025), *LawFlow: Collecting and Simulating Lawyers’ Thought Processes*. Microsoft Research:|E17|作者源码已固定，后续步骤待完成；当前本地资源分支按用户要求暂缓|[作者源码](https://github.com/minnesotanlp/LawFlow/tree/0a3f0327c7d44f0c38d27b1f6d5e0362b72f1d64) / [ E17 ](../method_reproductions/e17_lawflow_review/METHOD.md)|
|L04|Shi et al. (2025), *LegalReasoner: Step-wised Verification-Correction for Legal Judgment Reasoning*.|E06|未完成作者方法/环境复现|[ E06 ](../method_reproductions/e06_legalreasoner_verifier/METHOD.md)|
|L05|Sadowski & Chudziak (2025), *On Verifiable Legal Reasoning: A Multi-Agent Framework with Formalized Knowledge Representations*.|E04|Stage II原数值精确未命中/10%容差命中；Stage I抽取/整合/校验已运行，24类/71属性/21规则待原人工审核；新解释器/训练反馈与中国规则域未完成，累计6/100|[作者源码](https://github.com/albsadowski/solar/tree/067f8f78b128dc7647c8a54b2560a612fae91a87) / [ E04 ](../method_reproductions/e04_symbolic_verifier/METHOD.md)|
|L06|Kondo et al. (2025), *Capturing Legal Reasoning Paths from Facts to Law in Court Judgments using Knowledge Graphs*.|尚未建配置|未完成作者方法/环境复现|待实施|
|L07|Lu et al. (2026), *From Query to Counsel: Structured Reasoning with a Multi-Agent Framework and Dataset for Legal Consultation* (JurisMA).|E03,E18|论文§3.2–3.4/Algorithm 1推理重实现，非作者代码；原任务/产品API分支状态见逐步记录，DPO与本地训练检查点暂缓，整篇未完成|[论文推理/差异/真实I/O](jurisma/README.md) / [ E03 ](../method_reproductions/e03_staged_with_matterpack/METHOD.md) / [ E18 ](../method_reproductions/e18_jurisma/METHOD.md)|
|L08|Liao et al. (2026), *VERDICT: Verifiable Evolving Reasoning with Directive-Informed Collegial Teams for Legal Judgment Prediction*.|E06,E20|作者源码已固定，后续步骤待完成；当前本地资源分支按用户要求暂缓|[作者源码](https://github.com/luckyhui235/VERDICT/tree/1b6c9d6ecfbe95900076cbfd2eedf94aecaaf952) / [ E06 ](../method_reproductions/e06_legalreasoner_verifier/METHOD.md) / [ E20 ](../method_reproductions/e20_verdict/METHOD.md)|
|L09|Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026:|E03,E10,E19|原ECHR样例＋案例产品轨道完成；中国法规替代判例指南的任务适配（非像素KIE）|[作者源码](https://github.com/khatrimann/SCALE/tree/1700924ca8c448af56c854e5e4c9ae693e86beb3) / [ E03 ](../method_reproductions/e03_staged_with_matterpack/METHOD.md) / [ E10 ](../method_reproductions/e10_factor_guided_retrieval/METHOD.md) / [ E19 ](../method_reproductions/e19_scale/METHOD.md)|
|L10|Nguyen et al. (2026), *L-MAD: A Systematic Evaluation of Multi-Agent Debate Structures in Legal Reasoning*.|E07,E08,E09|论文协议＋所引MALLM原组件：两原示例协议和产品轨道已执行；非L-MAD作者代码/原COLIEE年度benchmark|[论文协议/原组件/输入输出](l_mad/README.md) / [ E07 ](../method_reproductions/e07_agentscourt_adversarial/METHOD.md) / [ E08 ](../method_reproductions/e08_agentscourt_judge/METHOD.md) / [ E09 ](../method_reproductions/e09_l_mad/METHOD.md)|
|L11|Pang et al. (2026-10), *Legal-R1: Agentic Retrieval for Evidence-Based Legal Reasoning*.|E11|作者源码已固定，后续步骤待完成；当前本地资源分支按用户要求暂缓|[作者源码](https://github.com/killerqueen-wonder/Legal-R1/tree/a2bf5054841a108b5f1a3be10fe1cd8a336ed806) / [ E11 ](../method_reproductions/e11_legal_r1/METHOD.md)|
|L12|Cui et al. (2026), *Chatlaw: A Multi-Agent Legal Assistant based on a Role-Aligned Mixture-of-Experts Architecture*.  （注意与更早 ChatLaw 项目/同名版本核对）|尚未建配置|未完成作者方法/环境复现|待实施|
|L13|Song et al. (2026), *Knowledge Graph-Assisted LLM Post-Training for Enhanced Legal Reasoning*.|尚未建配置|未完成作者方法/环境复现|待实施|
|L14|Li et al. (2026), *Legal-DC: Benchmarking Retrieval-Augmented Generation for Legal Documents* (LegRAG).|E10|作者源码已固定，后续步骤待完成|[作者源码](https://github.com/legal-dc/Legal-DC/tree/1f4422e4a9de4ce7bb311ebf926f61c1b077d50a) / [ E10 ](../method_reproductions/e10_factor_guided_retrieval/METHOD.md)|
|A01|Yao et al. (2022/23), *ReAct: Synergizing Reasoning and Acting in Language Models*.|E01|原任务真实执行＋产品轨道完成（单样本）|[作者源码](https://github.com/ysymyth/ReAct/tree/6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9) / [ E01 ](../method_reproductions/e01_react/METHOD.md)|
|A02|Madaan et al. (2023), *Self-Refine: Iterative Refinement with Self-Feedback*.|E05|原任务真实执行＋产品轨道完成（单样本）|[作者源码](https://github.com/madaan/self-refine/tree/9a206d41e5d2d0c241bb441f41eeadb945afaa55) / [ E05 ](../method_reproductions/e05_self_refine/METHOD.md)|
|A03|Shinn et al. (2023), *Reflexion: Language Agents with Verbal Reinforcement Learning*.|E21|原任务真实执行＋产品轨道完成（单样本）|[作者源码](https://github.com/noahshinn/reflexion/tree/218cf0ef1df84b05ce379dd4a8e47f17766733a0) / [ E21 ](../method_reproductions/e21_reflexion/METHOD.md)|
|A04|Hong et al. (2023), *MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework*.|E02,E22|原软件SOP/案例产品已执行；原QA续跑19次，7个测试文件最后2个失败且最终main修订未执行；累计45/100，保持部分完成|[作者源码](https://github.com/FoundationAgents/MetaGPT/tree/820fee5df6697b4e85e90c787940de111c3ed05b) / [ E02 ](../method_reproductions/e02_staged_without_matterpack/METHOD.md) / [ E22 ](../method_reproductions/e22_metagpt/METHOD.md)|
|A05|Zhao et al. (2024), *LongAgent: Scaling Language Models to 128k Context through Multi-Agent Collaboration*.|尚未建配置|未完成作者方法/环境复现|待实施|
|A06|Zhang et al. (2024), *Chain of Agents: Large Language Models Collaborating on Long-Context Tasks*.|E14|论文Algorithm 1重实现；官方QA原任务完整执行但答案未命中；冻结KIE文本VQA和案件产品执行完成；非作者源码执行|[论文算法/输入输出](chain_of_agents/README.md) / [ E14 ](../method_reproductions/e14_chain_of_agents/METHOD.md)|
|A07|Li et al. (2024), *GraphReader: Building Graph-based Agent to Enhance Long-Context Abilities*.|E13|资源暂缓：原文与提示已固定；所引InsTag完整归一化的嵌入/聚类分支未运行，不能用简化图冒充原方法；当前本地资源分支按用户要求暂缓|[归一化依赖/暂缓依据](graphreader/README.md) / [ E13 ](../method_reproductions/e13_graphreader/METHOD.md)|
|A08|Kim et al. (2025), *Towards a Science of Scaling Agent Systems*.|E09|未完成作者方法/环境复现|[ E09 ](../method_reproductions/e09_l_mad/METHOD.md)|
|A09|*On Scalable Oversight with Weak LLMs Judging Strong LLMs* (2024),|尚未建配置|未完成作者方法/环境复现|待实施|
|R01|Asai et al. (2023/24), *Self-RAG*.|尚未建配置|未完成作者方法/环境复现|待实施|
|R02|Yan et al. (2024), *Corrective Retrieval Augmented Generation*.|E12|作者源码已固定，后续步骤待完成；当前本地资源分支按用户要求暂缓|[作者源码](https://github.com/HuskyInSalt/CRAG/tree/de7c2961ae624a1483a138c5798e1f6d0c4fb0e0) / [ E12 ](../method_reproductions/e12_crag/METHOD.md)|
|R03|Sarthi et al. (2024), *RAPTOR*.|E15|原任务真实执行＋产品轨道完成（单样本）|[作者源码](https://github.com/parthsarthi03/raptor/tree/7da1d48a7e1d7dec61a63c9d9aae84e2dfaa5767) / [ E15 ](../method_reproductions/e15_raptor/METHOD.md)|
|R04|Edge et al. (2024), *From Local to Global: A Graph RAG Approach to Query-Focused Summarization*.|E24|官方v0.1.1原全局查询2次；产品冻结KIE文本/案件各14个原索引工作流与map/reduce执行完成，累计15/100；VQA弃答0；原查询索引为作者预计算，完整原benchmark未复现|[作者源码](https://github.com/microsoft/graphrag/tree/a81efe58c7c21ff8b17aa9bf1cb78a0750f3065b) / [作者索引/查询/实际输入输出](graphrag/README.md) / [ E24 ](../method_reproductions/r04_graphrag/METHOD.md)|
|R05|Guo et al. (2024), *LightRAG*.|E16|原任务真实执行＋产品轨道完成（单样本）|[作者源码](https://github.com/HKUDS/LightRAG/tree/c31a2654f9fff95145d6edf372c1f5af5b6db891) / [ E16 ](../method_reproductions/e16_lightrag/METHOD.md)|
|D01|Wang et al. (2024), *MinerU: An Open-Source Solution for Precise Document Content Extraction*.  ；4.x 的具体 `doclib`/`MiddleJson`/`locator` 参考当前源码：|尚未建配置|未完成作者方法/环境复现|待实施|
|D02|Cui et al. (2025), *PaddleOCR-VL: Boosting Multilingual Document Parsing via a 0.9B Ultra-Compact Vision-Language Model*.|尚未建配置|原0.9B权重核心识别完成（达到输出上限）；完整布局流水线和产品适配未完成；当前本地资源分支按用户要求暂缓|[作者源码](https://huggingface.co/PaddlePaddle/PaddleOCR-VL/tree/7fa00a8c55b735ba51ba49a9058f3f9c57a99a11)|
|D03|Hu et al. (2024), *mPLUG-DocOwl2*.|尚未建配置|未完成作者方法/环境复现|待实施|
|D04|Poznanski et al. (2025), *olmOCR*.|尚未建配置|未完成作者方法/环境复现|待实施|
|D05|Li et al. (2025), *dots.ocr*.|尚未建配置|未完成作者方法/环境复现|待实施|
|D06|Tito et al. (2022), *Hierarchical multimodal transformers for Multi-Page DocVQA*.|尚未建配置|未完成作者方法/环境复现|待实施|
|D07|Kang et al. (2024), *Multi-Page Document Visual Question Answering using Self-Attention Scoring Mechanism*.|尚未建配置|未完成作者方法/环境复现|待实施|
|D08|Li et al. (2026), *PureDocBench*.|尚未建配置|未完成作者方法/环境复现|待实施|
|D09|Ouyang et al. (2024), *OmniDocBench*.|尚未建配置|未完成作者方法/环境复现|待实施|
|B01|Li et al. (2025), *LegalAgentBench: Evaluating LLM Agents in Legal Domain*. ACL 2025.|E23|作者三控制器原任务工具回放＋三协议冻结KIE文本VQA已执行（均弃答0）；E23网页/API与案件映射已接入；在线原工具服务拒绝连接，保持部分完成|[作者源码](https://github.com/CSHaitao/LegalAgentBench/tree/ec14d8ab1fc439bfd99cbefba08d8e27dafca534) / [作者控制器/回放/产品I/O](legalagentbench/README.md) / [ E23 ](../method_reproductions/b01_legalagentbench/METHOD.md)|
|B02|Fei et al. (2023/24), *LawBench*. EMNLP 2024.|b02_lawbench|官方19/20类任务×zero/one-shot首样本共38次真实调用；产品分类原评分器已接入，KIE缺参考未评分；2-1本地LTP暂缓|[作者源码](https://github.com/open-compass/LawBench/tree/e30981bb3ff54c41571f222e0b23e92d27375388) / [复现/输入输出](lawbench/README.md)|
|B03|Li et al. (2024), *LexEval*. NeurIPS 2024.|尚未建配置|未完成作者方法/环境复现|待实施|
|B04|Guha et al. (2023), *LegalBench*.|b04_legalbench|作者原提示/评分代码已执行；11任务/12组29个原测试样本，截断3条已单独恢复；原Rule QA人工未评分；真实全局VQA原平衡精确匹配补充评分已接HTTP/CLI/导出；KIE缺参考未评分；累计32/100|[作者源码](https://github.com/HazyResearch/legalbench/tree/b46bf4ffae90524b2b72aaa30e7745fe9db64481) / [原提示/原评分/任务/产品I/O](legalbench/README.md)|
|B05|Pipitone & Alami (2024), *LegalBench-RAG*.|尚未建配置|未完成作者方法/环境复现|待实施|
|B06|Butler & Butler (2026), *Legal RAG Bench: an end-to-end benchmark for legal RAG*.|尚未建配置|未完成作者方法/环境复现|待实施|
|B07|Zheng et al. (2025), *A Reasoning-Focused Legal Retrieval Benchmark*.|尚未建配置|未完成作者方法/环境复现|待实施|
|B09|COLIEE 2025 官方任务/论文： ；综述：|尚未建配置|未完成作者方法/环境复现|待实施|
|B10|Ma et al. (2024), *MMLongBench-Doc*. NeurIPS 2024.|尚未建配置|未完成作者方法/环境复现|待实施|
|B11|Zhang (2026), *MMLongBench-Doc-V2*.|尚未建配置|未完成作者方法/环境复现|待实施|
|B14|Gao et al. (2023), *Enabling Large Language Models to Generate Text with Citations* (ALCE).|尚未建配置|未完成作者方法/环境复现|待实施|
|B15|Ru et al. (2024), *RAGChecker*.|b15_ragchecker|作者默认API分支两完整原例/原11指标已验证；单条格式适配差异和45原回复复用均保存；文本全局VQA证据faithfulness产品开发轨道完成，KIE缺转录未评分；累计56/100|[作者源码](https://github.com/amazon-science/RAGChecker/tree/6091f08c00e676e87a970f2aeb4a23a484746348) / [作者方法/原任务/产品I/O](ragchecker/README.md)|
|B16|Min et al. (2023), *FActScore*.|尚未建配置|未完成作者方法/环境复现|待实施|
|B17|Chlapanis et al. (2024), *LAR-ECHR*.|尚未建配置|未完成作者方法/环境复现|待实施|

[逐次真实输入/输出/回复/测试](results/2026-10-29-per-paper/README.md) · [逐配置审查](ADAPTATION_REVIEW.md)
