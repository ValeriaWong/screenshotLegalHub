# S0 首批输入冻结

> 本页记录2026-10-22首批。最新第二批已扩至774文件并完成G01本准备轮输入核对，见[来源补齐](SOURCE_CLOSURE.md)；完整S0仍缺G02环境复现。

2026-10-22 已执行首批内部准备冻结：[baseline_20261022_001](../../datasets/v3.0.0/baseline_20261022_001/baseline_snapshot.json)。401 个文件，26,266,866 字节（25.05 MiB，不含控制文件）；10 个分组。**S0 完整验收仍未通过**，G01/G02 的剩余工作见[执行计划](../ai_docs_center/NEXT_STEPS.md)。

## 工具与输出

[prepare_v3_baseline.py](../../tools/prepare_v3_baseline.py)只使用 Python 标准库。输入为[baseline_inputs.json](../../configs/v3/baseline_inputs.json)，目录路径相对仓库根，统一使用正斜杠。

每组明确 source_id、version、origin_type、author_status、review_status 和 permitted_use。路径按实际工作区枚举，包含未跟踪源码；不依赖 Git HEAD 来代表当前实现。原来源的作者/审核声明按历史状态保留，未重新认证。

| 输出 | 作用 |
|---|---|
| source_manifest.jsonl | 每文件路径、SHA-256、来源、版本、审核/用途及冻结副本位置 |
| snapshot/ | 按原相对路径保存实际字节副本 |
| baseline_snapshot.json | 组计数、总字节、采集环境、软件基线选择及控制文件哈希 |
| readiness.json | 首批准备状态、剩余缺口；明确 s0_accepted=false、release_ready=false |
| inherited_gaps.md | 从冻结时台账继承的缺口、影响阶段和责任角色 |
| input_spec.snapshot.json / gap_ledger.snapshot.json | 实际采用的输入清单和执行前台账，便于追溯当时判断 |

内部准备快照不授予发布许可。source_id 指向组级来源；两案逐段来源仍在各自 source.json 中，旧评分细节在 references 中。author_status 为沿用资产、作者未重新核验。

## 命令

在仓库根目录运行，使用现有根 Python 环境；命令不调用模型：

~~~powershell
# 只核对已冻结副本与控制文件；源码后续变化不影响这项检查
.\.venv\Scripts\python.exe -B tools\prepare_v3_baseline.py check --output datasets/v3.0.0/baseline_20261022_001

# 额外核对当前工作区：检测已选文件的变化、缺失及目录内新增文件
.\.venv\Scripts\python.exe -B tools\prepare_v3_baseline.py check --output datasets/v3.0.0/baseline_20261022_001 --check-sources

# 扩展输入清单后创建下一批；示例目录必须尚不存在
.\.venv\Scripts\python.exe -B tools\prepare_v3_baseline.py freeze --output datasets/v3.0.0/baseline_20261022_002

# 重跑完整性测试
.\.venv\Scripts\python.exe -B -m unittest discover -s tests -p test_v3_baseline.py -v
~~~

freeze 完成后自动执行工作区与副本双重校验。JSON 结果为 passed 时退出码 0；失败返回非零。现存输出目录直接拒绝，无覆盖开关。输入校验失败不创建目录；复制中断保留 .incomplete 标记，不能算有效基线，应排查后使用新批次名。

check 的来源对比使用快照内的输入清单，后续编辑当前清单不会改写旧批次范围。快照校验验证保存字节的一致性，不自动证明来源真实性、法律正确性或环境可复现；哈希清单不是外部签名。

## 首批范围与剩余工作

- 已冻结 V2 第二轮两案及其图片/判决文本/修订记录、三个历史评分抽取文件、完整依赖预研材料和一次原始模型运行、v1 P3 任务/响应/队列。
- 已冻结 legalhub 源码/静态页面、product_v1 源码/测试/锁文件/示例 fixture，以及执行/渲染/评分抽取工具。后续优先在 product_v1 集成 V3 契约，真实兼容迁移完成后再验收 G18。
- 未纳入 v1 原始图片池、原始评分 xlsx、V2 其他轮的完整资产，尚未确定 2 中 + 2 英的独立校准来源池。保留 G01。
- 保存的是源码和依赖声明，尚未冻结或复现浏览器/字体/完整安装环境；未重渲染，保存当前 renderer 不代表它就是旧批次实际执行版本。保留 G02。
- 本地密钥配置、数据库、生产上传目录和虚拟环境不纳入；只复制显式选择的文件，历史运行配置仍按原 run.json 解释。

本批沿用仓库对 datasets/ 的 Git 忽略规则，是本地冻结副本；后续发布需按 S7 生成可分发归档。

[验证报告](../../reports/v3.0.0/s0_baseline_20261022_001/README.md)保存 14 项测试及两种检查结果。[状态台账](../ai_docs_center/status.json)负责现行进度，快照中的台账仅描述冻结时状态。文档索引排除 snapshot/ 下重复字节副本，这些文件由 source_manifest.jsonl 单独清点。
