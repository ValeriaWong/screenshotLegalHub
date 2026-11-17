# 本地检索与证据工作台

retrieve 使用代码完成。查询通过 SQLite FTS5/BM25、中文 bigram、原文匹配及显式同义词词典执行，不调用模型。消息/事件抽取是独立模块，可替换视觉模型。

在仓库根目录启动：

```powershell
.\.venv\Scripts\python.exe -m legalhub.app serve --port 18420
```

打开 http://127.0.0.1:18420/ 。演示可选资料组 `5ad6f87311be1056f7197a9f`，查 `2000`，再查看原图；也可检索 `预付款`、类案 `股权转让纠纷` 和法条 `借款人应当按照约定的期限返还借款`。

## 模块与资产

| 模块 | 输入 | 输出 |
|---|---|---|
| curator | 两处原图目录 | 1,170 张原图索引及 SHA256 |
| evaluator | 冻结截图、旧题和修订协议 | 提供商原始回答、分项指标、失败、用量和耗时 |
| evidence | 提交清单和截图 | 消息、事件候选、原文、原图 bbox 和不确定项 |
| retriever | 经结构校验的记录与本地文书/法条 | 带完整来源的检索结果 |

既有原图的文件名前缀暂作资料组 ID，不声称为真实司法案号。原图证据页码尚未登记时显示“未登记”；新增上传按用户选择顺序登记页码。头像身份不跨图自动合并，日期未知不会被补成今天。

当前索引包含历史模型预测和新模型抽取，界面分别标识。81 条新消息与 16 条事件候选来自 9 张真实原图的新 API 请求，保存于 `blocks/evidence/artifacts/runs/p2-kimi3-development/`；仍需人工复核。结构和引文校验不代表视觉或法律结论已经正确。

类案来自本库归档判决，返回原文件、记录号、正文字符位置及来源 URL。法条初始范围为最高人民法院网站的《中华人民共和国民法典》2020 年公布文本，按 1,260 条分别索引，保留公布/施行日期；并非完整法条库，具体案件适用版本需核对。联网下载仅发生在法条导入阶段，查询在本地执行。

## 重建、抽取和查询

```powershell
.\.venv\Scripts\python.exe tools/import_civil_code.py
.\.venv\Scripts\python.exe tools/extract_evidence.py blocks/evidence/artifacts/demo_manifest.json --output blocks/evidence/artifacts/runs/p2-kimi3-development --execute
.\.venv\Scripts\python.exe tools/build_retrieval_index.py --corpus blocks/evidence/artifacts/runs/p2-kimi3-development/corpus.json --corpus blocks/retriever/artifacts/statutes/civil-code-2020.json
.\.venv\Scripts\python.exe -m legalhub.app query --case 5ad6f87311be1056f7197a9f --query 2000
```

完整重建大型归档索引需要一段时间；工作台导入使用增量更新。SQLite 使用 WAL，使已提交的查询结果在写入过程中仍可读取。历史预测中损坏 JSON、越界框等跳过记录单独列在 `artifacts/historical_import_issues.json`，不会当作无损全量抽取。

抽取不带 `--execute` 只核验清单；带该参数发送截图给配置的视觉模型。同一输出目录按原配置断点恢复，已有响应不自动重发。网页“同时理解截图内容”也会调用模型；关闭后只导入原图，不进行文字抽取。模型凭据仅在本地读取，浏览器不能获取配置文件。

CSV 和 JSON 导出保留全部 source_refs，CSV 采用 UTF-8 BOM 并防止原始消息成为表格公式。服务只绑定 127.0.0.1；不对外发布。

事件大事记将已知日期和日期待核对项分开；整份大事记导出保留全部事件候选，重复抽取版本不会被默认为不同真实事件。原图上下文只读取同一抽取版本。

抽取坐标可显式选择 `--coordinate-space normalized_1000`；该模式保留模型原始框并按原图尺寸转换一次。默认像素协议不变，不能用新模式静默解释旧结果。

## 验收

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe tools/verify_retrieval_app.py
```

HTTP 验收检查真实检索、案件隔离、来源图片、同图前后文、类案/法条、CSV 导出和无需模型的截图导入。六道开发样本来源查询的命中率仅为功能冒烟测试，不能代替独立检索评测。页面截图在 `reports/retrieval_ui_source.png`。

最终模型选型、跨图身份/时间核对、双方证据对齐和当事方有利性分析仍需后续迭代；当前工作台用于先跑通可追溯的检索与抽取闭环。
