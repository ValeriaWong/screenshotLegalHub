# L07 JurisMA：论文推理算法与产品适配（整篇仍未完成）

论文：[Lu et al., From Query to Counsel](https://arxiv.org/html/2604.10470v1)，§§3.2–3.4、Algorithm 1、附录C。原文HTML及SHA-256见[paper_source.json](paper_source.json)，论文流程/角色提示固定于[specification.lock.json](specification.lock.json)。本轮未核实对应作者仓库；没有使用同名第三方项目。

## 原方法、创新、原任务及本轮程度

原输入为自然语言法律咨询q。Element Agent生成实体、事件、用户主张、关键事实、法律问题与语义关系组成的JSON图G=(V,E)，初稿读取[serialize(G);q]。Manager根据草稿选择FormatCheck、LawSearch或Pass；同轮两项均选时先执行格式建议及Draft.applySuggestions，再让LawSearch接收修订后的草稿、实际读取法条，最后Draft.integrateStatutes。T固定5，Pass/空动作停止，循环结束后ContentCheck始终执行，输出Response与含完整条文的Legal Basis。

创新为法律语义图、选择性协作、法条grounding及内容修订。完整论文还包含JurisCQAD偏好数据与DPO训练；原基准为修订LawBench的500咨询问题（340项修订），另有RuleQA/KoBLEX等迁移。本轮只使用附录C逐字咨询示例，未取得修订测试集或训练检查点。

**复现程度：推理算法重实现；非作者源码执行，非原DPO训练系统。** 训练与本地检查点按用户指令暂缓；即使以下执行成功，整个L07也不增加三阶段完成数，完整benchmark与法律准确率均未验证。

## 实现与适配调试

- [algorithm.py](algorithm.py)：真实状态机，固定T=5、双动作执行顺序与独立ContentCheck；不再使用旧E18通用角色路由。
- [prompts.json](prompts.json)：本项目按论文角色契约编写；没有把它们标成作者原提示。模型用用户已启用AIPING DeepSeek-V4.1-Flash-1017替代原训练模型。
- [environment_state.json](environment_state.json)：独立Python3.12.15、0个额外依赖；无本地权重、GPU、训练或嵌入。
- 法条后端是项目适配：API在冻结目录中选ID，程序读取对应原文；拒绝目录外ID。原论文未指定的数据库后端没有冒称作者实现。原咨询目录含3份历史条款，出处/快照/边界见[native_inputs/statutes.json](native_inputs/statutes.json)，航空院校审查依据缺失，保持未知。
- 首次原任务最终条文被模型缩略，全文校验失败。补充已实际检索法源附录给ContentCheck是显式适配；21个精确相同前序请求/回复复用，新增1次最终调用后通过全文校验。原失败与原始回复保留。
- 案件首步受中间图与最终facts约束混淆影响，返回非JSON并达到2048输出上限。分离阶段契约、图上限显式改4096后重新执行；最终投影仍应用原完整产品Schema与引用约束。首次1次失败计入预算。
- 产品结果另经[product_adapter.py](product_adapter.py)的product_projection映射；原咨询输出与产品JSON分别保留。E18案件run与全局文本VQA run_task均已改接该算法；HTTP白名单、网页选项、API类型、动态预算29次已同步。无像素KIE入口。

## 真实运行与完整输入输出

全部记录按e18_jurisma命名，包含真实输入、每步消息/回复、模型身份/参数/用量、每轮草稿与实际检索全文、最终输出、失败和测试、执行时源码快照。

|轨道|执行状态|新增供应商请求|精确复用回复|可读记录|
|---|---|---:|---:|---|
|case_product|completed|19|0|[完整输入/逐步回复/输出/测试](../results/2026-10-29-per-paper/methods/e18_jurisma/runs/710a1dd93bc80825__case_product/e18_jurisma.INPUT_OUTPUT.md)|
|native|completed|1|21|[完整输入/逐步回复/输出/测试](../results/2026-10-29-per-paper/methods/e18_jurisma/runs/72bfa373de5519ef__native/e18_jurisma.INPUT_OUTPUT.md)|
|case_product|failed|1|0|[完整输入/逐步回复/输出/测试](../results/2026-10-29-per-paper/methods/e18_jurisma/runs/895318ad8451837d__case_product/e18_jurisma.INPUT_OUTPUT.md)|
|native|failed|22|0|[完整输入/逐步回复/输出/测试](../results/2026-10-29-per-paper/methods/e18_jurisma/runs/a3b46e386dda3dc2__native/e18_jurisma.INPUT_OUTPUT.md)|
|vqa_predicted_text|completed|19|0|[完整输入/逐步回复/输出/测试](../results/2026-10-29-per-paper/methods/e18_jurisma/runs/fd6f6d0f533fc661__vqa_predicted_text/e18_jurisma.INPUT_OUTPUT.md)|

本轮新增62次，L07累计79/100（含此前17次）；原任务与产品共用上限，失败及在途也计数。原任务恢复没有清零，也没有把缓存原回复成本当成新增请求。模型快照比较保留供应商/配置/模型/参数等，排除每次新建的内部id、时间和credential_ref分配值；缓存还逐阶段严格匹配完整消息和实际参数。

实际结果：原咨询五轮后完成，3份实际检索全文逐字校验；文本全局VQA执行19次，answer=null、开发参考分0（旧参考未专家确认）；案件成功执行19次，返回4条结构化条目/5处逐字引用，通过Schema与offset校验。案件冻结法源目录为空，实际法条读取结果为空，未冒造规则。

内容限制：案件首条“存在一笔款项”仍含从双方陈述抽象出来的存在性表述，observed不等于法院事实认定，须人工复核；4条结果不是专家认可的4个事实。VQA弃答并不表示内容能力达标；原论文训练收益与法律结论均未复现。

## 验证与运行

后端受影响共享回归64项通过；网页方法与预算测试8项、TypeScript检查通过。针对后续案件阶段契约/图上限的最终检查另见[报告](../../../reports/author_expansion_20261029/REPORT_JURISMA_RESOURCE_BOUNDARY_2026-10-30.md)。HTTP验收使用隔离TestClient；没有重启另一个窗口使用的18430服务，不能将源码变更说成该进程已经更新。

用项目Python执行setup_environment.py jurisma或--check；run_validation.py --track native|vqa_predicted_text|case_product默认只计划，加--execute才真实调用。每篇预算由原持久账本约束。当前L07只余21次，不再启动要求预留29次的全新产品单元。write_io.py仅渲染既有记录，0次调用。
