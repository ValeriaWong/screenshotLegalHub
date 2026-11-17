# Self-Refine：原代码、原任务与产品适配

当前状态：独立环境可重建；上一轮已用真实 DeepSeek 完成作者缩写三模块的一次修订；本轮已把案件主链、KIE和全图VQA接入作者 responsegen 控制器。当前新增验证使用确定传输夹具，新增真实试跑仍待调用额度答复。原论文完整 benchmark 未复现。

## 原方法与原始输入输出

论文：[Madaan et al., Self-Refine (2023)](https://arxiv.org/abs/2303.17651)。作者仓库：[madaan/self-refine](https://github.com/madaan/self-refine)，提交9a206d41e5d2d0c241bb441f41eeadb945afaa55。

创新是同一模型生成、给出具体反馈并根据反馈继续修订，无需专门训练反馈模型。原论文包含Yelp情感反转、对话响应、PIE代码优化、CodeNet可读性、GSM8K、缩写生成、CommonGen七类任务。

作者没有统一KIE/VQA接口。缩写任务接收英文title/max_attempts，返回缩写与评分轨迹；responsegen接收对话context/max_attempts，返回每轮response/scores/n_attempts。它们都不直接接收截图或CaseAnalysisOutput。

## 实际复用的代码

- 原控制器：paper/upstream_sources/self_refine/src/responsegen/run.py 的 iterative_response。
- 原任务类：ResponseGenTaskInit、ResponseGenFeedback、ResponseGenTaskIterate 的三个 __call__。
- [任务适配器](product_adapter.py)：从固定作者源码原样编译控制器函数体；移除整轮付费重试装饰器，不执行作者批处理CLI及pandarallel的25进程初始化。
- 产品入口：[e05_self_refine.py](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e05_self_refine.py)。run(context)执行案件任务；run_task执行KIE/全图VQA；旧项目原型只保留在历史源码快照，不提供运行时回退。
- 产品调度：[author_bridge.py](../../../product_v1/backend/src/screenshotlegal/method_reproductions/author_bridge.py)。子进程不接收供应商密钥，每一步均由父进程的持久预算与Gateway执行。

## 适配与调试

保留原控制器的生成/反馈循环、历史响应与自评分记录；max_attempts=2对应Init→Feedback→Iterate→Feedback四次调用。案件参数refinement_rounds在E05映射作者max_attempts（包含初稿），KIE/VQA接口则明确使用method_attempts。任务模板改为KIE、VQA或案件输出；图像由父进程在每一步附加同一冻结原件。反馈只要求可公开的简短修改意见，分数是方法内自评，不进入外部评测成绩。

作者原解析器会删除#并截取Response:或第一行；适配器把生成JSON规范为单行，并转义这些解析敏感字符，解码后的原文字符不变。测试覆盖System:/User:/Response:/#及中文。SDK兼容、模型身份和实际token上限另行记录；不声称与原模型实验条件相同。

原GSM评分器包含代码执行及Unix清理流程，本轮没有直接运行它，也没有执行模型生成的程序。

## 环境

固定环境状态：[environment_state.json](environment_state.json)；[依赖锁](requirements.lock.txt)。本机Python3.12独立环境中46个固定包版本检查一致。

从仓库根目录执行：

~~~powershell
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/author_reproductions/setup_environment.py self_refine
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/author_reproductions/setup_environment.py self_refine --check
~~~

安装/检查不会调用模型；已有源码变化会报告并保留，不会reset覆盖。

## 记录与边界

- [上一轮真实缩写样例与失败说明](HISTORICAL_NATIVE_EXAMPLE.md)
- [上一轮实际请求/响应](runs/2026-10-28-native-acronym/format_adapted/native_trace.json)
- [上一轮实际输出](runs/2026-10-28-native-acronym/format_adapted/native_output.json)
- [本轮冻结KIE/全局VQA计划](../results/2026-10-28-kie-global-vqa/current_plan.json)
- [本轮工程检查](../../../reports/author_product_adaptation_20261028/REPORT.md)

新增原控制器真实完整任务、真实图片KIE/VQA尚未运行，不能用工程夹具验证代替。1170个现有KIE任务没有目标转录，先给结构/坐标有效性及旧区域关联IoU；闭集VQA对照未复核旧参考，开放题留待量表审核。专家法律金标后补，不阻塞环境与接口适配。
