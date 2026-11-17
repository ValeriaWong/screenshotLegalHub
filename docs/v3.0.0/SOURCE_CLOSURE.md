# S0 来源补齐与核对（T02）

2026-10-23。T02 已完成本准备轮的输入补齐：[来源审计](../../datasets/v3.0.0/source_audit_20261023_002/audit_summary.json)、[第二批快照](../../datasets/v3.0.0/baseline_20261023_001/baseline_snapshot.json)、[验证报告](../../reports/v3.0.0/source_closure_20261023_001/README.md)。

## 结果与统计口径

| 项目 | 结果 | 边界 |
|---|---|---|
| 原始评分工作簿 | 3 份；从归档提取后字节哈希与旧记录一致 | 原 ZIP 留在原位；工作簿完整字节已纳入快照 |
| 旧评分抽取记录 | 512 条，对应 510 个不同 Excel 行 | 511 条非空、1 条空行；有 2 次重复行引用，不相加为独立评分 |
| 单元格内容/表头 | 5,599 次非空单元格核对通过 | 包含重复引用；只读取 Excel 缓存值，不重新计算公式 |
| P3 图片链 | 244 任务、306 次图片引用、286 张不同图片 | 每次引用均与任务保存的预期哈希一致；只覆盖 P3，非 v1 全量 |
| 校准候选来源池 | 4 个不同案件，2 中 + 2 英 | 上游文件哈希、原始行、全文哈希和段落偏移通过；仍为 development |
| 第二批快照 | 774 文件、15 组、247,208,463 字节（235.76 MiB） | 包含首批输入；两个批次不相加为唯一资产数 |

空行来自“人工迭代实验记录_钱书豪.xlsx / 假设 / 第12行”，保留来源记录，usable_for_mapping=false。非空记录通过字节/行定位检查也不意味着其评分正确或符合 V3 量表。

## 校准来源选择

| 案件 | 当前候选 | 原始定位 | 准备范围 |
|---|---|---|---|
| zh_sales_146 | V2 round_002 | 中文来源工作簿 samples!第148行 | 款项往来、对账与意思表示的截图可见内容 |
| zh_employment_130 | V2 round_001 | 中文来源工作簿 samples!第132行 | 通知、回复与事件先后；单方陈述与实际发生分开 |
| en_probate_283 | V2 round_002 | 英文来源 JSONL 第284行 | 不同账号的陈述与证据边界，未知身份保留 |
| en_charter_177 | V2 round_001 | 英文来源 JSONL 第178行 | 条件、接受与后续沟通的中间判断 |

原始索引为零起算：中文 Excel 行=source_index+2；英文 JSONL 行=source_index+1。两份上游容器的完整字节也纳入第二批快照。四案候选总计112条历史消息，不能称为已完成四个V3校准场景。候选池的详细范围和状态见[calibration_source_pool.json](../../datasets/v3.0.0/source_audit_20261023_002/calibration_source_pool.json)。

S1 仍需逐条形成事实账本、case scope、旧量表到新维度的语义映射及抽样方案。判决原文只供来源核对/作者与审核者使用，不能自动进入未来截图任务的模型输入；已经看过的开发来源不能转成独立测试集。

## 使用方式

工具：[audit_v3_inputs.py](../../tools/audit_v3_inputs.py)，配置：[source_audit.json](../../configs/v3/source_audit.json)。复用根 requirements.txt 中已有的 openpyxl；没有新增依赖或服务。freeze/check 继续使用[原冻结工具](S0_BASELINE.md)。

~~~powershell
# 检查第二批副本和当前已选输入
.\.venv\Scripts\python.exe -B tools\prepare_v3_baseline.py check --output datasets/v3.0.0/baseline_20261023_001 --check-sources

# 重新核对原位来源；必须使用尚不存在的目录
.\.venv\Scripts\python.exe -B -X utf8 tools\audit_v3_inputs.py --output datasets/v3.0.0/source_audit_20261023_003

# 两套工具共28项测试
.\.venv\Scripts\python.exe -B -X utf8 -m unittest discover -s tests -p test_v3_*.py -v
~~~

重新运行来源审计需要原位 ZIP、原始上游文件和任务图片；核对已存字节副本则只需冻结工具。审计错误返回非零，输出保留具体错位/缺失记录。全部内容一致的空行单独标记并排除映射用途；不会修改旧提取文件或自动补分。

新一轮先修改 source_audit.json，审计通过后将 baseline_inputs.json 的对应组、图片列表与来源容器更新到新产物，再用新目录执行 freeze。冻结工具不会自动替代来源质量审核。所有 datasets/ 产物沿用现有 Git 忽略规则，仅在本地保存。

## 交接

G01 按“当前准备轮纳入输入”的既定契约关闭：每个文件具备哈希、来源、版本、审核/作者状态、内部允许用途；未纳入其余 V2 候选和 v1 全量评测的范围已明示，后者仍由 G16 跟踪。后续扩充必须新建批次并重新核对。

G02 的环境/浏览器/字体复现尚未完成，因此 S0 及 V3 整体阶段验收仍为0/8。下一步执行 T03；本轮无模型调用或专业认证。
