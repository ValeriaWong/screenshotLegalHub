# B01 LegalAgentBench：作者三控制器、受限原任务回放与产品文本适配

**当前为部分完成，不新增整篇完成数。** 已建立独立环境，实际执行作者 ReAct、Plan-and-Solve、Plan-and-Execute 原类、原提示/示例/表格模式和解析函数。原法律工具服务拒绝连接，所以原任务验证使用作者公开日志的精确工具响应回放；不能称17个在线语料库已复现。产品已注册为E23，可在网页和研究API选择三种控制器，选项随计划冻结；案件读取计入工具预算。尚未做独立浏览器验收。当前18430服务只读探测仍是旧接口，未加载E23；没有重启其他窗口服务，需由该服务更新进程后才会在当前实例显示。

## 原方法、benchmark 与输入输出

- [ACL2025论文](https://aclanthology.org/2025.acl-long.116/) · [作者仓库](https://github.com/CSHaitao/LegalAgentBench/tree/ec14d8ab1fc439bfd99cbefba08d8e27dafca534)。本地 paper/upstream_sources/legalagentbench 固定 ec14d8ab1fc439bfd99cbefba08d8e27dafca534，16个原文件的SHA在上级sources.lock.json。
- 论文贡献是中文法律Agent benchmark：17个语料库、37个工具、300个1至5跳及写作任务，另报告关键词成功率和中间过程进度率。三条baseline控制器是作者的对照实现，不冒称新法律推理算法。
- 原输入：question、工具描述、相关表格schema；外部工具返回企业/裁判/法律等数据。answer、key、key_middle留在评分端。
- 原输出：Final Answer、scratchpad、过滤后的答案和过程摘要；key_answer/key_middle是原代码的字面子串包含率，不能当作语义法律准确率。可选BERTScore远程服务未执行。
- 原入口 src/react.py当前也只取datas[0:1]。本轮沿用这个首任务，不按模型结果挑题：查询金宏气体股份有限公司的代码、法人代表、董秘。作者原日志的一条观察作为工具回放数据，**不把作者原回答/思考作为新模型输入**。

## 实际复现位置

|文件|作用|
|---|---|
|[product_adapter.py](product_adapter.py)|文件头含论文出处、benchmark、原I/O、复现程度、适配说明；从锁定作者AST执行ReactAgent/PSAgent/PEAgent及原函数体，非本项目新写的三段prompt原型|
|[original_score.py](original_score.py)|从原eval.py选出key_answer/key_middle原分支体执行，保留子串匹配和原显示格式；非简化另写一个评分公式|
|[run_validation.py](run_validation.py)|同一B01持久预算、原任务回放/产品轨道、逐次messages/raw/usage落盘、源码快照与失败留存|
|[应用层桥接](../../../product_v1/backend/src/screenshotlegal/method_reproductions/legalagentbench_bridge.py)|冻结KIE文本→list_evidence/read_evidence→answer/evidence；另提供案件CaseAnalysisOutput映射函数。E23案件/基准分发共用此桥接，读取结果会检查/记录并计入预算|
|[author_log_first_task.json](native_inputs/author_log_first_task.json)|只从作者日志抽取原问题及工具观察，不包含原最终回答或key标签|

独立环境 paper/.author_envs/legalagentbench：Python3.12.15、Pydantic1.10.19、typing_extensions4.15.0，无模型权重/FAISS/嵌入安装。[依赖锁](requirements.lock.txt) · [环境校验](environment_state.json)。完整上游requirements仍保存在原仓库；未把未使用的FAISS等包安装成功当成复现条件。

## 已做的适配与问题修复

1. DeepSeek-V4.1-Flash-1017/AIPING替换作者提供商；温度0、2000输出token上限。保留原控制器的调用次数、plan/replan和动作解析，不将一次总prompt伪装成多步控制流。输出cap是显式有界设置，不声称所有原provider分支都使用相同cap。
2. 原LangChain只用PromptTemplate.format接口，采用str.format兼容层；原模板内容和类方法体未改写。Schema仍使用作者的Pydantic1.10模式。
3. 原agents.py的post_request调用format_input时少传name。本适配传输改用原format_input(name,input)，并严格匹配已保存观察；未知工具/identifier/columns组合返回不可用，**不从Gold答案补齐**。
4. 原解析器包含eval模型文本的备用路径；原任务只允许带json围栏的动作进入原函数；产品额外允许对完整、合法action/action_input JSON对象无损加围栏，原始回复及包装SHA均保留，备用eval路径仍不可达。Python或非JSON不会被执行。
5. 原表筛选器最多3次尝试仍保留，全部计入同一预算；没有网络自动重试和预算重置。
6. 产品工具明确替换为冻结文本list/read，不宣称调用原法律数据库。原few-shot示例涉及外部企业工具，产品分支明确去掉这些示例。原任务分支保留原示例。
7. 实际产品试跑发现PS/PE分步提示丢失原问题中的JSON要求。现在每步system消息保留同一输出契约，原任务提示不加产品契约。先前两条自然语言Final Answer失败保留，不能按语义看起来合理就记为接口成功。
8. 首次ReAct七个模型步骤及工具响应均执行完毕，但本适配最终事件多包了一层result，父进程取字段失败。修正事件后对每一条stage/messages/parameters做严格一致匹配，复用原7条响应完成评分，**新增调用0**。失败记录仍保留，回放响应不重复计费。

## 真实执行和记录

三原控制器均完成同一个作者首任务的**工具观察回放**。作者key_answer/key_middle评分均1.0；只有一个1跳任务，其key_middle为空，不能据此宣称多跳/写作/进度能力通过。

[run_summary.json](run_summary.json)按variant列出每次结果、实际新增调用、失败、复用次数与可读记录路径。每条运行保存 b01_legalagentbench.input/output/prompts/model_responses/tools/test_results/provenance.json、b01_legalagentbench.INPUT_OUTPUT.md 和当时source_snapshot。全部分开保存，不用“最新成功”覆盖失败。

本轮产品全局VQA只读冻结的真实KIE预测。ReAct已真实执行、读取了来源并弃答，旧开发参考得分0；Plan-and-Solve/Plan-and-Execute修正输出契约后分别用4次/10次调用完成执行，均弃答0。当前累计77/100次供应商请求，含全部失败；两次严格恢复共复用14条响应，不重复计费。产品参考未经过专家审核。原任务关键词标签没有进入产品提示。

|记录|新增请求|实际结果|可读完整I/O|
|---|---:|---|---|
|native_replay / react|0（复用7条）|原关键词评分1.0；受限工具回放|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/03fa1fd436220a50__native_replay__react/b01_legalagentbench.INPUT_OUTPUT.md)|
|native_replay / react|0（复用7条）|原关键词评分1.0；受限工具回放|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/3846ffb81d019b7a__native_replay__react/b01_legalagentbench.INPUT_OUTPUT.md)|
|case_product / react|20|失败（保留原错误）|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/823983f5bb72487c__case_product__react/b01_legalagentbench.INPUT_OUTPUT.md)|
|native_replay / plan_and_execute|7|原关键词评分1.0；受限工具回放|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/858d833f0f17f666__native_replay__plan_and_execute/b01_legalagentbench.INPUT_OUTPUT.md)|
|native_replay / react|7|失败（保留原错误）|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/9108c48b30ad2537__native_replay__react/b01_legalagentbench.INPUT_OUTPUT.md)|
|vqa_predicted_text / plan_and_solve|4|弃答，旧开发参考0|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/94f747736265e7b0__vqa_predicted_text__plan_and_solve/b01_legalagentbench.INPUT_OUTPUT.md)|
|case_product / react|6|3项陈述事实，逐字引用校验通过|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/bb43d4761e669d15__case_product__react/b01_legalagentbench.INPUT_OUTPUT.md)|
|vqa_predicted_text / plan_and_solve|5|失败（保留原错误）|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/c6f2ee6e48a82a8b__vqa_predicted_text__plan_and_solve/b01_legalagentbench.INPUT_OUTPUT.md)|
|vqa_predicted_text / plan_and_execute|10|弃答，旧开发参考0|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/d3fb2852adeb0893__vqa_predicted_text__plan_and_execute/b01_legalagentbench.INPUT_OUTPUT.md)|
|vqa_predicted_text / plan_and_execute|6|失败（保留原错误）|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/d781844d1dbec58c__vqa_predicted_text__plan_and_execute/b01_legalagentbench.INPUT_OUTPUT.md)|
|native_replay / plan_and_solve|6|原关键词评分1.0；受限工具回放|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/e499a8dfecdfe74f__native_replay__plan_and_solve/b01_legalagentbench.INPUT_OUTPUT.md)|
|vqa_predicted_text / react|6|弃答，旧开发参考0|[完整I/O](../results/2026-10-29-per-paper/methods/b01_legalagentbench/runs/e887785b123add5b__vqa_predicted_text__react/b01_legalagentbench.INPUT_OUTPUT.md)|

原公开工具端点探测证据：[tool_service_probe.json](tool_service_probe.json)，结果ECONNREFUSED。未向该服务发送AIPING密钥，没有用伪造企业数据替代在线服务。

## 复查与剩余工作

```powershell
product_v1/.conda/screenshotlegal-v1/python.exe paper/author_reproductions/setup_environment.py legalagentbench --check
product_v1/.conda/screenshotlegal-v1/python.exe paper/author_reproductions/legalagentbench/run_validation.py --track native_replay --variant react
product_v1/.conda/screenshotlegal-v1/python.exe paper/author_reproductions/legalagentbench/run_validation.py --track vqa_predicted_text --variant plan_and_solve
product_v1/.conda/screenshotlegal-v1/python.exe paper/author_reproductions/legalagentbench/summarize_validation.py
product_v1/.conda/screenshotlegal-v1/python.exe -m pytest product_v1/backend/tests/test_legalagentbench_author.py -q
```

不带--execute只生成计划。全部原生/产品/失败/未知请求共享B01的100次上限，不因版本或回放恢复清零。方法/HTTP/预算测试覆盖三控制器、原评分、精确工具回放、未知请求、eval路径阻断、上限、真实子进程事件和产品契约传递；不等于原300题benchmark通过。

E23网页/研究API已接入并冻结variant；三种控制器的基准及案件HTTP离线集成均通过，前端相关10项和类型检查通过。真实案件ReAct用6次调用完成，返回3项陈述事实及3条逐字引用；另两种案件控制器仅做HTTP夹具验证，未额外真实调用。案件首试因裸JSON与原围栏协议冲突耗尽原10步（20次调用），失败保留；修订阶段协议并增加无损包装后重试完成，本次实际输出已有围栏，包装次数0。

下一步仍需：独立浏览器验收；恢复原法律工具服务或获得完整可校验原语料，才能完成在线原任务。完整benchmark与专家法律金标另列。当前不将本条目算作三阶段整篇完成。
