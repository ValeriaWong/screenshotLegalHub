# ReAct：作者Notebook控制器与截图任务适配

当前状态：独立环境已配置，原WikiEnv/HotPotQAWrapper已实际加载7405道HotpotQA开发题；原Notebook webthink控制器已接入产品KIE/全图VQA。原任务和截图任务的新增真实模型运行仍待调用额度答复，完整benchmark未复现。案件分析run(context)仍是旧项目原型，只有run_task切换至作者控制器。

## 原方法、benchmark与输入输出

论文：[Yao et al., ReAct](https://arxiv.org/abs/2210.03629)。作者仓库：[ysymyth/ReAct](https://github.com/ysymyth/ReAct)，提交6bdb3a1fd38b8188fc7ba4102969fe483df8fdc9。

原创新是让推理/行动与环境观察交替进行。论文实验包括HotpotQA、FEVER、ALFWorld、WebShop。这里接的是HotpotQA入口：英文问题→Wikipedia Search/Lookup观察→Finish[文本答案]，由原包装器在输出侧计算EM/F1；答案不进入模型输入。

## 实际复用与适配

- 作者入口：paper/upstream_sources/react/hotpotqa.ipynb 的 webthink函数；函数体按原样加载，包括七轮上限、格式补问及Finish处理。
- [原任务/截图任务适配器](product_adapter.py)：native_task=true时调用原WikiEnv和HotPotQAWrapper、原六个示例、固定dev索引0；截图模式将环境替换为冻结图像工具。
- [产品方法文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e01_react.py)的run_task调用[react_bridge.py](../../../product_v1/backend/src/screenshotlegal/method_reproductions/react_bridge.py)。

截图任务将Search映射为冻结原图目录，Lookup映射为原图像素局部读取，Finish内容改成KIE或VQA的JSON。局部图附在原图之后，保存原图/裁剪哈希及坐标；越界会停止，不猜测修正坐标。此工具变化是任务适配，不能称原Wikipedia条件复现。

原Completion模型替换成受预算约束的chat模型，原100token上限也有明确参数适配。Thought仅要求一句公开行动标签，不记录供应商隐藏思考字段。原控制器最多七轮、格式补问最多另七次，因此启动前按十四次上限检查，实际次数逐步记录。

## 环境与状态

- [依赖锁](requirements.lock.txt)：gym0.26.2、numpy1.26.4、requests2.32.3、beautifulsoup4及其固定依赖，独立于产品和Self-Refine环境。
- [环境与原任务加载记录](environment_preflight.json)
- [源码及依赖检查](environment_state.json)

~~~powershell
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/author_reproductions/setup_environment.py react
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/author_reproductions/setup_environment.py react --check
~~~

## 记录与未完成项

[本轮冻结计划](../results/2026-10-28-kie-global-vqa/current_plan.json)包含原HotpotQA样例、KIE和全局VQA；记录按methods/e01_react/runs/<计划ID>__<任务>/保存。当前[工程验证](../../../reports/author_product_adaptation_20261028/REPORT.md)通过实际作者控制器与确定模型返回，验证像素裁剪、输入隔离和预算，不能冒充真实模型结果。

原HotpotQA真实模型样例、真实截图试跑尚未执行；其余三个原benchmark也尚未配置。原任务使用在线Wikipedia，未来样例保留原观察轨迹，但不声称网页版本固定。法律专家评测按用户要求延期。
