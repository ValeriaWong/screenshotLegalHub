# 当前执行优先级

用户指令：先略过需要本地计算资源的复现，特别是依赖模型权重本地推理的。

当前优先：通过已有AIPING配置与DeepSeek远程调用运行的作者算法。普通Python调度、文本处理、令牌计数不属于模型权重推理。每篇原任务与产品轨道共用100次供应商请求上限，既有失败、未知与历史请求不清零。

暂缓：本地模型权重推理、训练、重型索引与嵌入分支；包括PaddleOCR-VL完整本地流水线、VERDICT当前本地嵌入方案、CRAG原T5 evaluator、LawFlow本地监控模型等。RAPTOR/LightRAG已存结果保留，不追加本地模型复现任务。作者若提供不依赖本地权重的正式分支，可核实后另行执行，不能以临时prompt替代必要组件而标完成。

SCALE：原任务双条文和API案件产品适配已完成开发执行。VERDICT：暂停本轮新建环境的安装进程PID2392及其子进程，下载与历史日志保留；这表示顺序调整，不表示作者方法不可复现。

全部51条目范围保留；资源暂缓不计失败或完成。专家法律Gold不作为本轮原任务与产品执行的门槛。

LawBench：19类任务评分只需轻量文本依赖，已执行作者zero/one-shot首样本共38次API调用；2-1文书校对的官方ChERRANT tokenizer导入LTP与Torch，按用户要求暂缓。原官方评分函数不以简化编辑距离替代。

CoA：论文Algorithm 1/原提示重实现（非作者源码执行），使用AIPING API与普通分词；原任务、冻结KIE文本VQA和案件轨道共9次调用。原QA答案未命中；原始回复和官方F1保留。无本地权重/嵌入/训练。

L-MAD：独立Python零额外依赖环境，论文协议＋所引MALLM原组件使用AIPING API。原示例两协议、冻结KIE文本VQA和单事实案件流程均有原始记录；两VQA均弃答、案件facts为空，不称内容质量达标。累计92/100次，暂不重复耗费剩余8次。详见[l_mad/README.md](l_mad/README.md)。

GraphReader：进一步追溯第3.2节所引InsTag后发现完整归一化含语义嵌入/聚类；本地权重分支暂缓，远程嵌入配置未建立。保留[原文与依赖核查](graphreader/README.md)，0次模型调用，不以简化图冒充完整方法。

LegalAgentBench：作者3个控制器与2依赖环境不需要本地模型；在线工具端点拒绝连接，原任务仅作者日志精确工具回放。3条冻结KIE文本VQA均执行并弃答0，累计77/100次；E23网页/API三变体已接入，真实案件3项陈述事实/3引用通过结构校验。当前保持部分完成。

MetaGPT：本轮只用远程DeepSeek与普通Python测试。原QA续跑新增19次、累计45/100；仍有失败和最终未执行的测试文件，不增加整篇完成数。详见[原始I/O与检查](metagpt/README.md)。

SOLAR：Stage I原图审核前流程已用4次API实际执行，累计6/100；原结构校验最终0问题，24类/71属性/21规则已生成具体审核包。已补齐作者锁版本pandas等普通数据处理依赖。保留作者human_review输入边界；人工审核具体TBox后才继续原解释器生成，不以缺专家CaseGold作为本轮其他工作的阻塞。

RAGChecker：作者默认triplet/no-segmentation API分支不需要本地模型；原RAGChecker/RefChecker实际执行，Python3.12.15与11依赖、无spaCy/Torch/Transformers加载。两个完整原例/原11指标与全局VQA证据文字faithfulness开发适配已验证，累计56/100。KIE缺人审转录仍未评分；原本地NLI/AlignScore/localizer等分支继续暂缓。详见[逐篇原I/O与差异](ragchecker/README.md)。

LegalBench：原提示渲染与评分不需要神经权重；独立Python3.12.15/16依赖，180个原代码/提示/说明文件及23个原数据文件均固定校验。原代表任务与产品标签补充评分已执行，累计32/100。Rule QA按原框架人工未评分；不用用户后补的CaseGold伪装原人工通过。无新增本地权重、训练或GPU任务。

LawLuo：作者ToLC示例已固定提交并实际AST检查，含语法错误和未实现函数；不作为可运行API分支。完整SFT/PPO/本地模型与嵌入暂缓，0次调用。见[源码核查](lawluo/README.md)。

JurisMA：当前仅推进论文§3.2–3.4/Algorithm 1的远程API推理重实现，作者仓库未核实，DPO/本地训练检查点暂缓；整个L07不计三阶段完成，即使推理样例与产品映射成功。

环境入口：setup_environment.py all默认排除models/model_lock分支；显式安装raptor/lightrag/paddleocr_vl也会按资源暂缓返回，不启动权重下载。--check仍允许核对既有资源；本轮不新增本地推理。

GraphRAG（R04/E24）：优先原无嵌入global分支；v0.1.1固定399文件，Python3.11/101作者锁依赖，无本地神经权重。原Notebook完整预计算索引查询2次，产品冻结KIE/案件14原工作流及查询各6/7次，累计15/100。不是原百万token benchmark；见[真实I/O](graphrag/README.md)。

AgentsCourt：源码retrieve_rerank.py明确调用本地BAAI/bge-large-zh-v1.5；完整重排暂缓，已运行的API庭辩组件及历史9次请求保留。Legal-R1：RL.sh与generation.py明确依赖本地vLLM/GPU及torch actor rollout，按用户指令暂缓；此前14次项目原型请求保留，不能称原训练策略已运行。两者机器可读原文件/行号/哈希见各自resource_boundary.json。
