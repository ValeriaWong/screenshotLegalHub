# e18_jurisma

候选编号：E18；状态：implemented；复现程度：project_mechanism。

复现法律要素结构、动态任务路由及修订；未执行 DPO 训练或作者原系统的完整测评。

原论文 benchmark 复现：未完成。implemented 仅指本项目工作流有代码；原任务、输入输出、创新点与适配阻塞请先读 METHOD.md。

[原任务与适配说明](METHOD.md) · [独立实现文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e18_jurisma.py) · [按名称保存的工程测试](e18_jurisma.tests.json) · [机器可读索引](e18_jurisma.index.json)

## 论文出处

- Lu et al. (2026), *From Query to Counsel: Structured Reasoning with a Multi-Agent Framework and Dataset for Legal Consultation* (JurisMA). [来源](https://arxiv.org/abs/2604.10470)

## 已保存的实验

以下批次可能采用不同代码、配置及输入，不能合并计算方法优势。原始执行版本以每份 record/provenance 和所在批次 implementation/ 为准；当前源码链接仅用于导航。

| 批次 | 类型 | 状态 | 记录 |
|---|---|---|---|
| 2026-10-28-deepseek-pilot | real_model | {'failed': 2} | [按名称查看](../../experiments/results/2026-10-28-deepseek-pilot/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-deepseek-pilot/without-thinking-simple | real_model | {'failed': 1} | [按名称查看](../../experiments/results/2026-10-28-deepseek-pilot/without-thinking-simple/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-final | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-final/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-mechanism-smoke | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-mechanism-smoke/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-method-reproductions | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-method-reproductions/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-named-methods | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-named-methods/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-named-methods-final | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-named-methods-final/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-reproducible-smoke | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-reproducible-smoke/methods/e18_jurisma/e18_jurisma.REPORT.md) |
| 2026-10-28-verified-smoke | demo | {'completed': 3} | [按名称查看](../../experiments/results/2026-10-28-verified-smoke/methods/e18_jurisma/e18_jurisma.REPORT.md) |

每项运行目录包含以 e18_jurisma 开头的 prompts、model_responses、output、tools、sources、test_results、record 和 provenance 文件。
完整性/字符范围通过不等于法律质量通过；未实现方法的登记/拒绝执行测试通过也不表示方法已实现。
