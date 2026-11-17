# e05_self_refine

候选编号：E05；状态：implemented；复现程度：author_controller_adaptation。

执行作者 responsegen 迭代控制器与三原生任务类调用；适配冻结来源案件输出、截图KIE及全图VQA；原benchmark未复现。

原论文 benchmark 复现：未完成。implemented 仅指本项目工作流有代码；原任务、输入输出、创新点与适配阻塞请先读 METHOD.md。

[原任务与适配说明](METHOD.md) · [独立实现文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e05_self_refine.py) · [按名称保存的工程测试](e05_self_refine.tests.json) · [机器可读索引](e05_self_refine.index.json)

## 论文出处

- Madaan et al. (2023), *Self-Refine: Iterative Refinement with Self-Feedback*. [来源](https://arxiv.org/abs/2303.17651)

## 已保存的实验

以下批次可能采用不同代码、配置及输入，不能合并计算方法优势。原始执行版本以每份 record/provenance 和所在批次 implementation/ 为准；当前源码链接仅用于导航。

| 批次 | 类型 | 状态 | 记录 |
|---|---|---|---|
| 2026-10-28-final | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-final/methods/e05_self_refine/e05_self_refine.REPORT.md) |
| 2026-10-28-mechanism-smoke | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-mechanism-smoke/methods/e05_self_refine/e05_self_refine.REPORT.md) |
| 2026-10-28-method-reproductions | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-method-reproductions/methods/e05_self_refine/e05_self_refine.REPORT.md) |
| 2026-10-28-named-methods | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-named-methods/methods/e05_self_refine/e05_self_refine.REPORT.md) |
| 2026-10-28-named-methods-final | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-named-methods-final/methods/e05_self_refine/e05_self_refine.REPORT.md) |
| 2026-10-28-reproducible-smoke | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-reproducible-smoke/methods/e05_self_refine/e05_self_refine.REPORT.md) |
| 2026-10-28-verified-smoke | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-verified-smoke/methods/e05_self_refine/e05_self_refine.REPORT.md) |

[作者控制器适配与当前原任务状态](../../author_reproductions/self_refine/README.md) · [KIE/全图VQA当前冻结计划](../../author_reproductions/results/2026-10-28-kie-global-vqa/current_plan.json)

每项运行目录包含以 e05_self_refine 开头的 prompts、model_responses、output、tools、sources、test_results、record 和 provenance 文件。
完整性/字符范围通过不等于法律质量通过；未实现方法的登记/拒绝执行测试通过也不表示方法已实现。
