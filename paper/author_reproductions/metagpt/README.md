# MetaGPT — A04 / e22_metagpt

论文：[MetaGPT: Meta Programming for A Multi-Agent Collaborative Framework](https://arxiv.org/html/2308.00352v7)。作者[FoundationAgents/MetaGPT](https://github.com/FoundationAgents/MetaGPT)，本次固定v0.3.0 / 820fee5df6697b4e85e90c787940de111c3ed05b，166源文件和25依赖包已校验；Python3.11独立环境，无模型权重推理。

原方法将SOP角色分工、结构化通信、消息发布订阅和可执行反馈用于软件开发；原输入为一句需求/编程任务，输出需求、设计、任务、代码与测试。论文benchmark为HumanEval、MBPP、SoftwareDev。本次运行公开README的“Write a cli snake game”，没有跑完整benchmark或复现论文分数。

**当前完成范围：默认软件SOP、案件产品流程及原QaEngineer续跑均有真实记录；QA仍有失败/未执行的最终修订，整篇方法保持部分完成。** 不把原软件任务生成的法律无关代码当法律能力，也不把项目E02三段提示基线改称MetaGPT。

[原软件任务入口](product_adapter.py)调用作者startup.startup，保留ProductManager、Architect、ProjectManager、Engineer（开启code review）、Team/Environment/Role/Memory及原Action/解析器。首次18次请求完整生成3份文档、3份Mermaid文本与7份Python源码，后续收集遇到Windows默认编码与UTF8不一致，原失败记录保留；按原编码恢复产物新增请求0。

实际原任务：[输入](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native/e22_metagpt.input.json) · [首次软件输出](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native/e22_metagpt.output.json) · [18次原回复](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native/e22_metagpt.model_responses.json) · [首次功能失败](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native/e22_metagpt.native_functional_before_feedback.json)。

首次游戏缺少Snake.occupied()，4项功能检查中2项失败。由功能探针选择失败文件，额外调用作者原WriteCodeReview 1次后，移动/增长/反向、吃食物计分、碰撞/重启/退出、食物避开蛇身4项检查通过。**这次额外审查由测试脚本触发，不是原自主QA控制器成功。**

[额外作者审查的真实输入与输出](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/cf51096b1f9b1a17__native_feedback/) · [修订后功能检查](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native/e22_metagpt.native_functional_after_feedback.json) · [最终原任务项目及范围](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native/e22_metagpt.native_followup_output.json) · [可检查项目目录](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/46d2f9262b31af56__native/native_project_after_author_review/)。导出源码与已测试源码AST逐项核对；原输出保持不变。Windows终端依赖/交互界面未完整验收。

[产品方法文件](../../../product_v1/backend/src/screenshotlegal/method_reproductions/e22_metagpt.py) → [传输桥](../../../product_v1/backend/src/screenshotlegal/method_reproductions/metagpt_bridge.py) → [领域适配](case_adapter.py)。实际使用作者Team、Environment、Role观察/记忆/发布机制、原Action._aask_v1与ActionOutput解析。四角色为EvidenceCurator → ElementMapper → EvidenceReviewer → CounselWriter，各自仅订阅前一Action类型；动作任务、角色说明和输出Schema为本项目适配。父进程反馈只检查schema和逐字引用，无专家Gold。

真实产品：[输入](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/ccb8fd08646d1009__case_product/e22_metagpt.input.json) · [输出](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/ccb8fd08646d1009__case_product/e22_metagpt.output.json) · [逐次回复](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/ccb8fd08646d1009__case_product/e22_metagpt.model_responses.json) · [角色订阅/结构化消息/反馈](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/ccb8fd08646d1009__case_product/e22_metagpt.author_artifacts.json) · [测试](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/ccb8fd08646d1009__case_product/e22_metagpt.test_results.json)。最终4步成功、结构与逐字引文通过；法律质量未评测。首次产品3步后因中间Schema被最终Schema覆盖而失败，已修正并保留a55ffea0574845ce记录，未修补旧模型回复。

调用累计45/100：软件18＋额外作者审查1＋首次产品失败3＋最终产品4＋本次原QA续跑19。原生/产品/失败共用账本，没有重置。编码及CRLF收集/应用错误以0调用恢复，详见原失败日志。

兼容改动：[loader.py](loader.py)仅省略无关模块预加载、替换LLM传输、完全unwrap两层付费重试、独立输出路径与UTF8文本；原类/函数体保留。默认长期向量记忆关闭，可选本地资源若被调用则明确失败；Mermaid文本保留，图形渲染暂缓。

环境：[environment_state.json](environment_state.json) / [requirements.lock.txt](requirements.lock.txt)。工程测试执行原软件角色、案件角色订阅、机械反馈、失败单请求及HTTP产物导出；Demo不是模型质量结果。当前案例产品适配不等于像素KIE或全图VQA接口，自主开发代码修复、交互终端与后续产品轨道仍待完成。

## 原作者 QA 续跑（2026-10-30）

[原入口与复现边界](native_qa_adapter.py) / [父进程预算与原始产物入口](run_native_qa.py)。从此前真实生成并经单独记录的额外作者审查修订后的7个源码文件续跑，没有重新生成上游需求/设计/代码。保留原QaEngineer观察、写测试、RunCode分析、DebugError改测试及消息订阅机制；仅替换Windows子进程执行、UTF8和自建字典literal_eval。原v0.3.0 Engineer只订阅WriteTasks，不支持自主开发代码修复。

新增19次远程调用：WriteTest 7、RunCode分析9、DebugError 3；实际9次子进程，7个测试文件最后执行结果为5个通过、2个失败。game反馈缺少Send To冒号，原解析器未路由；main最后修订finish_reason=length，最终磁盘SHA不同且没有重跑。原Memory按消息内容去重，重复DebugError文件信息未被重新观察，是最后修订未重跑的源码依据。不能把脚本正常返回或模型声称PASS算成测试通过；也不能用之前版本的通过代替新版本。

[完整可读输入/逐次提示/回复/子进程结果](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/e963b57f3eca6d0a__native_qa/e22_metagpt.INPUT_OUTPUT.md) · [真实输出/测试代码](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/e963b57f3eca6d0a__native_qa/e22_metagpt.output.json) · [最终磁盘版本审计](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/e963b57f3eca6d0a__native_qa/e22_metagpt.qa_audit.json) · [独立4项功能复查](../results/2026-10-29-per-paper/methods/e22_metagpt/runs/e963b57f3eca6d0a__native_qa/e22_metagpt.native_qa_independent_functional.json)。4项功能通过，开发代码字节未改变；这不覆盖整套QA或交互终端。

工程检查：相关共享桥/原SOP/产品集成等40项通过；新增最终测试版本必须实际执行才能判通过的回归另列，全部零供应商调用。
