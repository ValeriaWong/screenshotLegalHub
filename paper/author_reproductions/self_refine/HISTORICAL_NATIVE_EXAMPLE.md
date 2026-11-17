# 上一轮 Self-Refine 原生缩写样例记录

本文件保存新增4次调用时的历史说明；其中“产品尚未替换”为当时状态。当前调用链和适配状态见 README.md。

这份记录运行作者原生模块，不是调用产品 E05 的机制改写函数。作者源码保持原样；当前只完成一个原任务样例的一次生成—反馈—修订，模型与格式提示有适配。原论文完整 benchmark 尚未复现，产品 E05 尚未替换为作者原生接口。

## 原方法、任务与 benchmark

论文：[Self-Refine](https://arxiv.org/abs/2303.17651)。作者代码：[madaan/self-refine](https://github.com/madaan/self-refine)，固定提交 9a206d41e5d2d0c241bb441f41eeadb945afaa55。依赖 prompt-lib 的提交见 [sources.lock.json](../sources.lock.json)。

核心是同模型生成、提出反馈、根据反馈修订；原论文覆盖 Yelp、对话、PIE、CodeNet、GSM8K、缩写生成、CommonGen 等任务。本次选择作者 README 的缩写样例，不是整套数据集。

## 实际调用的作者函数

- src.acronym.task_init.AcronymGenTaskInit.__call__
- src.acronym.feedback.AcronymGenFeedback.__call__
- src.acronym.task_iterate.AcronymGenTaskIterate.__call__

入口：[driver.py](driver.py)；受限模型 broker：[run.py](run.py)。这三个类的提示构建、反馈组织和解析来自固定作者源码。首次还尝试了原 iterative_acronym 控制器；其失败未覆盖。

## 真实运行结果

原输入标题：Using language models of code for few-shot commonsense。

原生 Init 得到 LMCODE；作者 Feedback 模块得到模型自评 16/25；原生 Iterate 返回新标题 "Few-Shot Commonsense Code Models" 和缩写 FSCM。修订后未再次反馈评分，没有证明质量提升。

新增授权最多 4 次已全部使用：首次失败 1 次，修复后 3 次。估算费用 ¥0.015272。与之前 45 次试跑合计 49 次。数据源是作者公开提示/标题，不含真实案件资料。

- [运行总表](runs/2026-10-28-native-acronym/run_summary.json)
- [原生最终输出](runs/2026-10-28-native-acronym/format_adapted/native_output.json)
- [原始模型请求、实际适配请求及真实返回](runs/2026-10-28-native-acronym/format_adapted/native_trace.json)
- [失败记录](runs/2026-10-28-native-acronym/native_stderr.log)
- [实际执行时的适配代码快照](runs/2026-10-28-native-acronym/format_adapted/adapter_source/driver.py)

## 适配调试及保留差异

1. 在独立 Python 3.12 环境中固定依赖，没有改产品依赖。prompt-lib 的旧 Anthropic 构造调用与 SDK 不兼容，添加仅作用于客户端构造的 keyword shim，并固定 httpx 0.27.2。
2. 原代码用返回 model 字段决定 Chat/Completion 解析器。供应商实际返回 DeepSeek 型号造成 KeyError:text。broker 对原 SDK 保留请求 engine alias，同时在研究轨迹中保留真实 DeepSeek 身份。
3. DeepSeek 首次复述了 few-shot 示例。修复阶段保留作者完整 few-shot 文本，追加短格式指令；这属于模型接口适配，不是完全相同的原实验条件。
4. 禁用作者整轮解析失败自动重试；所有请求经过有持久 4 次上限的产品 Gateway。重复执行同一已完成目录只返回保存结果。
5. 首次失败后剩余 3 次，只执行原 Init/Feedback/Iterate 的一次修订，不再追加第二次反馈。因此不声称原控制器两轮完整成功。

## 迁移到截图证据任务

原接口处理缩写/程序/评论等任务，与 FrozenCaseInput → CaseAnalysisOutput 不同。迁移须替换任务提示和输出解析，定义证据支持/反证/未知的反馈标准，并保留原任务与新任务两条评测线。当前产品 E05 仍是项目原型，不能拿这个缩写样例宣称法律任务适配成功。

本次所有原始数据均保留。native_plan.amended.json 解释了初始计划中“两轮”与实际“三模块一次修订”的差异。
