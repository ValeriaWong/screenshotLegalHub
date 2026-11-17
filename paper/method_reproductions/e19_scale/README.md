# e19_scale

候选编号：E19；状态：implemented；复现程度：project_mechanism。

复现独立 Issue–Factor 层级选择关联指南；需要已冻结独立法律指南，现有领域包缺失时阻止执行。

原论文 benchmark 复现：未完成。implemented 仅指本项目工作流有代码；原任务、输入输出、创新点与适配阻塞请先读 METHOD.md。

[原任务与适配说明](METHOD.md) · [独立实现文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e19_scale.py) · [按名称保存的工程测试](e19_scale.tests.json) · [机器可读索引](e19_scale.index.json)

## 论文出处

- Khatri et al. (2026), *SCALE: Structured Case-law-guided Anticipatory Legal Reasoning*. EMNLP 2026: [来源](https://aclanthology.org/2026.emnlp-main.36/)

## 已保存的实验

以下批次可能采用不同代码、配置及输入，不能合并计算方法优势。原始执行版本以每份 record/provenance 和所在批次 implementation/ 为准；当前源码链接仅用于导航。

| 批次 | 类型 | 状态 | 记录 |
|---|---|---|---|
| 2026-10-28-final | demo | {'blocked_prerequisite': 3} | [按名称查看](../../experiments/results/2026-10-28-final/methods/e19_scale/e19_scale.REPORT.md) |
| 2026-10-28-mechanism-smoke | demo | {'blocked_prerequisite': 3} | [按名称查看](../../experiments/results/2026-10-28-mechanism-smoke/methods/e19_scale/e19_scale.REPORT.md) |
| 2026-10-28-method-reproductions | demo | {'blocked_prerequisite': 3} | [按名称查看](../../experiments/results/2026-10-28-method-reproductions/methods/e19_scale/e19_scale.REPORT.md) |
| 2026-10-28-named-methods | demo | {'blocked_prerequisite': 3} | [按名称查看](../../experiments/results/2026-10-28-named-methods/methods/e19_scale/e19_scale.REPORT.md) |
| 2026-10-28-named-methods-final | demo | {'blocked_prerequisite': 3} | [按名称查看](../../experiments/results/2026-10-28-named-methods-final/methods/e19_scale/e19_scale.REPORT.md) |
| 2026-10-28-reproducible-smoke | demo | {'blocked_prerequisite': 3} | [按名称查看](../../experiments/results/2026-10-28-reproducible-smoke/methods/e19_scale/e19_scale.REPORT.md) |
| 2026-10-28-verified-smoke | demo | {'blocked_prerequisite': 3} | [按名称查看](../../experiments/results/2026-10-28-verified-smoke/methods/e19_scale/e19_scale.REPORT.md) |

每项运行目录包含以 e19_scale 开头的 prompts、model_responses、output、tools、sources、test_results、record 和 provenance 文件。
完整性/字符范围通过不等于法律质量通过；未实现方法的登记/拒绝执行测试通过也不表示方法已实现。
