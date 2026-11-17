# L02 LawLuo：资源暂缓与源码核查

论文：[LawLuo v3](https://arxiv.org/html/2407.16252v3)。作者源码：[NEFUJing/LawLuo](https://github.com/NEFUJing/LawLuo/tree/d3fe4c75af15db4933a89962eaacff3b1b414c41)。

v3原方法由接待、律师、秘书、老板四角色与案例图RAG组成，包含SFT、奖励模型与PPO。仓库内ToLC示例不等于v3完整案例图算法，版本对应关系尚未补齐。原输入是非正式法律咨询及用户澄清选择，原输出为澄清路径、咨询答复；不是截图KIE或图像VQA。创新点为面向模糊咨询的案例图RAG与法律角色协作。原benchmark包括咨询双盲/模型成对偏好、多轮指令场景，以及LEVEN、CJRC、CAIL2018、LeCaRD的常规任务；MURLED/LCRG用于训练。尚未执行任何原benchmark。v3实验使用A100 40GB；按本轮资源范围暂缓。

当前复现程度：**未复现**。按用户2026-10-30指令暂缓本地微调权重、奖励模型/训练和嵌入组件。公开ToLC示例也无法作为可运行API替代分支：原文件含全角右括号语法错误；Retriever、ChatGPT_API、User和Lawyerd仅有注释和未定义返回变量。未修补作者源文件，未用自创prompt填空后宣称作者复现。

[source_identity.json](source_identity.json)固定提交、原始含尾部空格路径与Windows规范化路径、SHA-256及Git blob；[source_probe.json](source_probe.json)保存实际AST检查错误及未实现返回值；[probe_source.py](probe_source.py)可用普通Python重跑，0次模型调用，不执行作者程序。[resource_boundary.json](resource_boundary.json)提供机器可读暂缓原因。

适配判断：澄清咨询可作为案件缺失要素收集流程；不能直接输出像素KIE/全局VQA。完整适配须先取得真实可运行的角色/检索组件、明确事实与陈述，再单独映射案件输出和引用。原输入/输出与产品不同，当前没有真实原任务或产品输出；本目录不计完成。

[paper_source.json](paper_source.json)固定v3原文快照。论文v3描述的案例图RAG和仓库保留的ToLC草稿分别记录，不将跨版本部件混作已运行的完整系统。
