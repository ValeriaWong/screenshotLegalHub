# 案件方法复现与评测入口

当前作者代码接入：E05案件主链已改用作者Self-Refine控制器，E01/E05的KIE/全图VQA通过同名方法文件的run_task接入作者控制器。独立环境、原任务入口和当前状态见[作者复现目录](../author_reproductions/README.md)。新增真实模型试跑仍待本轮额度答复；下述45次历史诊断不能作为新控制器的验证记录。专家法律金标按用户要求后补，不阻塞本轮环境与适配。

本目录把候选方法接入论文项目，直接调用产品中的同一个方法执行器。当前实现是 **16 项可调用配置（其中 E19 有指南前提）**，包括全部 11 项 P0。方法改写与作者原系统复现的差异见 [METHOD_REPRODUCTION.md](METHOD_REPRODUCTION.md)。没有把作者报告的提升幅度写成本项目成绩。

已运行记录：[2026-10-28 离线机制演练](results/2026-10-28-final/REPORT.md)。3 个独立合成开发夹具 × 16 项方法，共 48 项计划任务；45 项完成、3 项因缺少 SCALE 独立法律指南而阻止。演练不调用供应商模型，不计算法律准确率。

已完成[DeepSeek 真实开发试跑](results/2026-10-28-deepseek-pilot/REAL_PILOT_REPORT.md)：总共 45 / 46 次授权调用，估算 ¥0.874104。首轮与关闭思考阶段的失败完整保留；补强引用坐标与规划协议后，E03 简单夹具、Legal-R1 反证夹具各有一项真实任务完成。JurisMA / VERDICT 尚未通过最终协议下的真实端到端复核；此轮没有专家 Gold，不能形成法律准确率或方法优劣结论。

## 方法文件与产物入口

方法实现已迁至 product_v1/backend/src/screenshotlegal/method_reproductions/：每个候选独立文件，文件头注明论文出处、复现程度和缺失机制。论文侧统一索引见 [paper/method_reproductions](../method_reproductions/README.md)。

新实验按 methods/<复现名称>/ 保存。以 E11 为例：

~~~text
methods/e11_legal_r1/
  e11_legal_r1.planned_tasks.json
  e11_legal_r1.test_results.json
  e11_legal_r1.REPORT.md
  runs/<案件组>__<任务ID>/
    e11_legal_r1.record.json
    e11_legal_r1.prompts.json
    e11_legal_r1.model_responses.json
    e11_legal_r1.output.json
    e11_legal_r1.tools.json
    e11_legal_r1.sources.json
    e11_legal_r1.test_results.json
    e11_legal_r1.provenance.json
~~~

同一方法的多个案件/重复保留各自运行目录，不能互相覆盖。METHODS.md 和 methods/index.json 提供按名称入口。旧 attempts/<哈希>.json 仍可读取；原始历史记录、失败和代码快照保留，新增命名副本记录其原文件 SHA256。

只整理既有结果（不会调用模型）：

~~~powershell
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/experiments/organize_results.py --out paper/experiments/results/2026-10-28-deepseek-pilot/protocol-counter
~~~

网页和 API 仍通过原有实验入口运行，返回 reproduction_name；下载 JSON 使用 <复现名称>.<运行ID>.json。

## 执行方式

从仓库根目录执行，使用项目已有 Python 环境，无需新增依赖。

~~~powershell
# 独立临时数据库；不读取或改写现有案件，输出目录应为新的目录。
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/experiments/run.py demo --out paper/experiments/results/my-smoke

# 复制并修改 manifest.example.json 中的案件、文档、模型、预算与案件组。
# 登录凭据仅通过 SCREENSHOTLEGAL_USER / SCREENSHOTLEGAL_PASSWORD 环境变量提供。
# plan 只核对前提与冻结输入；execute 才入队运行，真实模型可能计费。
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/experiments/run.py plan --manifest paper/experiments/my-manifest.json --out paper/experiments/results/my-study
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/experiments/run.py execute --manifest paper/experiments/my-manifest.json --out paper/experiments/results/my-study

# 读取已经保存的输出重新计分，不再次调用模型。
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/experiments/report.py --out paper/experiments/results/my-study --gold-dir paper/experiments/gold
~~~

默认服务器 http://127.0.0.1:18430，可用 --server 指定。真实模型必须在模型设置中已启用；model_revision 应记录供应商返回的精确型号，别名一致不能证明权重未变。网页入口：/evaluation.html?view=agents。

implementation/ 与 implementation.sha256.json 保存实际源码及每文件哈希；已有计划的代码变化要求新建实验目录。每项任务包含 input_digest、代码/注册表版本、模型配置、原始提示与响应、工具参数/观察、实际用量、失败状态和来源快照。相同输出目录绑定同一 manifest；重复 execute 用幂等键恢复同一任务，不自动重发失败或结果未知的调用。已有计划的输入变化会阻止运行。若读取结果时网络失败，服务任务可能仍在运行，先查看原 run_id；不要换幂等键盲目重发。

## 真实模型参数与诊断复核

options.inference_options.enable_thinking 可设为 false / true；省略则保持供应商默认。当前仅对已核对的 AIPing 主机开放，该参数进入冻结模型与比较摘要。不同思考模式或提示协议不能混为等条件对照。网页同时提供单次输出 token 上限；改变参数后必须重新预检。

执行器为原文提供机械分段 citation_units（quote/start/end），工具续读保留完整来源中的 Unicode 坐标。每项事实必须有原文引用；没有原文支持的缺失信息进入 uncertainties。引文仍逐字严格校验，不自动纠正错误位置或给模型补证。

本次专用 real_pilot.py 从隔离数据库的持久请求记录累计 46 次总上限；各阶段共享同一个根输出目录和 .runtime 账本。不要通过更换根目录重新启动该已授权试跑。报告可独立只读重建，不发出模型请求：

~~~powershell
./product_v1/.conda/screenshotlegal-v1/python.exe -B paper/experiments/analyze_real_pilot.py --out paper/experiments/results/2026-10-28-deepseek-pilot
~~~

## 评分与对照

- planned_tasks.json 在执行前写入，失败、前提缺失和未启动任务保留在分母。
- CaseGold 独立于输入，文件名为 input_digest.json；结构由后端 experiments/gold.py 的 CaseGold 定义，JSON Schema 见 case_gold.schema.json。
- Gold 必须绑定案件组、输入摘要、原文件哈希、开发/留出划分，并有审核记录。标签全集须显式标为 claims_complete。没有审核 Gold、Demo 或不完整输出，分数为 null。
- claim_label_set_f1 只采用人工认可别名的精确标签/适用性集合匹配，不冒充开放语义判断。它不是 claim macro-F1。
- citation_support_accuracy 由人工逐条审核当前 output_digest 的引文得出；字符匹配不产生语义支持分。报告同时给出人工审核覆盖数。
- 已提供模板的方法不计“自主举证责任推断”得分。模型自行推断的举证项须标为 model_inferred。
- 配对报告先匹配同一案件与重复次序，再按案件组合并；检查输入、预算、代码、模型版本等固定因素。对有效案件组做固定种子 bootstrap，单组不输出置信区间。Demo/过期记录不进入统计。

## 论文问题与运行范围

RQ2：E02/E03 比较模板增益；RQ4：E03/E05/E06/E07/E08/E09 比较核查、审查和辩论的净收益。E09 的 0–3 轮需分别冻结 manifest，不能只挑选最好轮次。E10/E11 对比检索策略；E12、E14、E18、E19、E20 为扩展机制。默认每方法使用相同上限，实际消耗和中途停止必须同时报告。

RQ1 的感知对照仍需同一原件的不同已冻结解析结果及感知金标；当前原生文本支持分块参数多版本，未跑 Docling/Paddle 的实际质量对照。RQ3 的关闭 grounding 验证消融尚未开放。E04/E13/E15/E16/E17 未实现，不会以其他方法代跑。

正式论文结果仍缺专家复核的领域模板/法源、CaseGold 与留出案件，以及相应真实模型运行。SCALE 另需独立法律指南及 Issue–Factor 层级，不能从测试答案倒推。作者训练方法的 GPU、检查点和语料缺口见复现矩阵。
