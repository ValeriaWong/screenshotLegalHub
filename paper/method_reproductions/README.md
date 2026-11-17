# 按方法名称查看复现代码与实验记录

从本目录进入每个方法，可以看到独立源码、文件头的论文出处与复现范围、原始回复、最终输出和测试记录。代码统一在 product_v1/backend/src/screenshotlegal/method_reproductions/，案件产品与论文批处理共用run(context)；KIE/全图VQA作者适配入口是同名文件的run_task。

原清单有 51 个文献条目，本页是其中 21 个实验配置，不是 21 篇已复现论文。现有可调用配置16个、未实现5个；E05案件主链及E01/E05的KIE/全图VQA已接作者控制器，真实新增试跑待授权。作者原benchmark完整复现仍为0；逐项状态见author_reproductions。

| 编号 | 复现名称 / 入口 | 状态 | 程度 |
|---|---|---|---|
| E00 | [e00_single_shot](e00_single_shot/README.md) | implemented | generic_baseline |
| E01 | [e01_react](e01_react/README.md) | implemented | project_mechanism |
| E02 | [e02_staged_without_matterpack](e02_staged_without_matterpack/README.md) | implemented | project_baseline |
| E03 | [e03_staged_with_matterpack](e03_staged_with_matterpack/README.md) | implemented | project_baseline |
| E04 | [e04_symbolic_verifier](e04_symbolic_verifier/README.md) | planned | not_implemented |
| E05 | [e05_self_refine](e05_self_refine/README.md) | implemented | author_controller_adaptation |
| E06 | [e06_legalreasoner_verifier](e06_legalreasoner_verifier/README.md) | implemented | project_mechanism |
| E07 | [e07_agentscourt_adversarial](e07_agentscourt_adversarial/README.md) | implemented | project_mechanism |
| E08 | [e08_agentscourt_judge](e08_agentscourt_judge/README.md) | implemented | project_mechanism |
| E09 | [e09_l_mad](e09_l_mad/README.md) | implemented | project_mechanism |
| E10 | [e10_factor_guided_retrieval](e10_factor_guided_retrieval/README.md) | implemented | project_mechanism |
| E11 | [e11_legal_r1](e11_legal_r1/README.md) | implemented | project_mechanism |
| E12 | [e12_crag](e12_crag/README.md) | implemented | project_mechanism |
| E13 | [e13_graphreader](e13_graphreader/README.md) | planned | not_implemented |
| E14 | [e14_chain_of_agents](e14_chain_of_agents/README.md) | implemented | project_mechanism |
| E15 | [e15_raptor](e15_raptor/README.md) | planned | not_implemented |
| E16 | [e16_lightrag](e16_lightrag/README.md) | planned | not_implemented |
| E17 | [e17_lawflow_review](e17_lawflow_review/README.md) | planned | not_implemented |
| E18 | [e18_jurisma](e18_jurisma/README.md) | implemented | project_mechanism |
| E19 | [e19_scale](e19_scale/README.md) | implemented | project_mechanism |
| E20 | [e20_verdict](e20_verdict/README.md) | implemented | project_mechanism |

## 文件组织

每批实验：paper/experiments/results/<批次>/methods/<复现名称>/。方法级 REPORT.md/test_results.json 汇总该批全部任务；runs/<案件组>__<任务ID>/ 中保存每次运行的命名文件，保留失败与重复，避免覆盖。

旧 attempts/<哈希>.json 仍可读取；命名副本的 provenance.json 记录原文件位置和 SHA256。网页下载为 <复现名称>.<运行ID>.json。

[原任务/适配逐项审查](../author_reproductions/ADAPTATION_REVIEW.md) · [51 条文献覆盖表](../author_reproductions/PAPER_COVERAGE.md) · [作者原代码运行](../author_reproductions/README.md) · [实验运行说明](../experiments/README.md)

刷新本导航：python -B paper/experiments/build_method_index.py。需要更新工程测试入口时，同时提供 --junit 和 --equivalence 对应的已执行记录。
