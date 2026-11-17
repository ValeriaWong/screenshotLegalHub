# 独立方法复现实现

每个候选一个 Python 文件。文件头列出论文原登记引用、来源 URL、复现程度、已实现和未实现部分。16 个已有机制可执行；其余 5 个明确为 planned，分发入口会拒绝执行。

产品入口：experiments/engine.py → 本包 run_method → catalog.py 映射 → 各方法文件 run(context)。experiments/methods.py 仅保留旧导入路径兼容。context.py 只共享模型/工具调用、三阶段处理及检索读取，不集中保存不同论文的控制流。

论文入口与按名称查看记录的索引：[paper/method_reproductions](../../../../../paper/method_reproductions/README.md)。

| ID | 独立文件 | 复现程度 | 可执行状态 |
|---|---|---|---|
| E00 | [e00_single_shot.py](e00_single_shot.py) | generic_baseline | implemented |
| E01 | [e01_react.py](e01_react.py) | project_mechanism | implemented |
| E02 | [e02_staged_without_matterpack.py](e02_staged_without_matterpack.py) | project_baseline | implemented |
| E03 | [e03_staged_with_matterpack.py](e03_staged_with_matterpack.py) | project_baseline | implemented |
| E04 | [e04_symbolic_verifier.py](e04_symbolic_verifier.py) | not_implemented | planned |
| E05 | [e05_self_refine.py](e05_self_refine.py) | project_mechanism | implemented |
| E06 | [e06_legalreasoner_verifier.py](e06_legalreasoner_verifier.py) | project_mechanism | implemented |
| E07 | [e07_agentscourt_adversarial.py](e07_agentscourt_adversarial.py) | project_mechanism | implemented |
| E08 | [e08_agentscourt_judge.py](e08_agentscourt_judge.py) | project_mechanism | implemented |
| E09 | [e09_l_mad.py](e09_l_mad.py) | project_mechanism | implemented |
| E10 | [e10_factor_guided_retrieval.py](e10_factor_guided_retrieval.py) | project_mechanism | implemented |
| E11 | [e11_legal_r1.py](e11_legal_r1.py) | project_mechanism | implemented |
| E12 | [e12_crag.py](e12_crag.py) | project_mechanism | implemented |
| E13 | [e13_graphreader.py](e13_graphreader.py) | not_implemented | planned |
| E14 | [e14_chain_of_agents.py](e14_chain_of_agents.py) | project_mechanism | implemented |
| E15 | [e15_raptor.py](e15_raptor.py) | not_implemented | planned |
| E16 | [e16_lightrag.py](e16_lightrag.py) | not_implemented | planned |
| E17 | [e17_lawflow_review.py](e17_lawflow_review.py) | not_implemented | planned |
| E18 | [e18_jurisma.py](e18_jurisma.py) | project_mechanism | implemented |
| E19 | [e19_scale.py](e19_scale.py) | project_mechanism | implemented |
| E20 | [e20_verdict.py](e20_verdict.py) | project_mechanism | implemented |

稳定复现名称同时用于 API 返回、网页导出文件名、论文实验目录及测试记录；E 编号继续用作协议标识。
未新增作者训练、检查点或法律质量结论。具体限制以各文件头和 METHOD_REPRODUCTION.md 为准。
