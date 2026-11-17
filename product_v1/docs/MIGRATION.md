# 仓库案件与旧数据迁移

仓库中的数据集文件不会自动出现在产品账户中。产品读取的是 `data/screenshotlegal.sqlite3` 的案件表；admin 可见该库全部案件。全量同步使用 `tools/import_repository_cases.py`，单份旧 corpus 迁移仍使用后文工具。

## 全仓库同步

在仓库根目录执行，使用独立产品的 Python：

```powershell
$py = '.\product_v1\.conda\screenshotlegal-v1\python.exe'
& $py -B -X utf8 product_v1/tools/export_legacy_repository_cases.py --repo-root . --output reports/admin_case_inventory_20261024/legacy-corpora.json
& $py -B -X utf8 product_v1/tools/import_repository_cases.py --legacy-corpus reports/admin_case_inventory_20261024/legacy-corpora.json --report reports/admin_case_inventory_20261024/preflight.json
& $py -B -X utf8 product_v1/tools/import_repository_cases.py --legacy-corpus reports/admin_case_inventory_20261024/legacy-corpora.json --apply --report reports/admin_case_inventory_20261024/import-result.json
```

第一步只读旧数据库及原始文件，导出逐案 corpus，并校验旧 quiz 的图片覆盖；可加 `--check-only` 只检查而不写导出。第二步只预检；第三步才写产品库。默认采用产品 Settings 的 data_dir，可显式传 `--data-dir`。默认 owner 为 admin，必须是已存在且启用的管理员。不要把测试库误当运行库。

同步范围包括 V2/V3 全部子目录、round、pilot、authoring、修订稿、嵌套 JSON/JSONL 候选、原文、历史渲染，以及所选旧库导出。空对话和来源缺口也保留。V3 原生按集合、场景与条件分开；精确内容相同的冻结副本保留别名。原文按精确正文哈希去重，不以案号或数组下标合并。列表数量包含案件档案和版本，不能据此声称独立判决数或已认证样本数。

每个版本的“来源与版本说明.txt”记录原路径、状态和来源关系；仅有原文也会建立档案。没有精确作者版本的历史 render 保留图片与清单，不借用当前对话转录。图片框的 xywh 转为产品 xyxy；未知页码保持 null；布局分钟和合成日期不作为历史发生时间。长消息滚动裁切保留所有原图，全文放在作者对话稿中，不把全文错引到单张局部裁图。

作者对话稿、旧 corpus 及来源说明属于研究档案。旧模型事件保留在档案附件中，不自动变成事实图谱。数据集题目与参考答案继续由原文件维护，不自动写入事实、主张或专业金标。

写入前创建 WAL 一致的 SQLite 备份（data/backups）。每案预检、独立事务写入记录与检索索引；失败只清理该案新文件。确定性 ID 支持重跑；已有人工标题、描述、复核、活动转录和检索记录保留。新增来源别名仅追加来源说明版本。断电遗留目录会报错等待核对，不盲目覆盖。预检检测新增文件、内容/时间变动以及旧导出、旧图变化。

产品页面可按标题、描述、案号、来源路径、round 和状态搜索，并显示可见总数；同步后刷新页面。所有权赋给 admin，普通用户仍需共享授权。

[2026-10-24 全量导入与覆盖报告](../../reports/admin_case_inventory_20261024/README.md)

## 单份旧 corpus 导入

工具 `tools/import_legacy_case.py` 读取导出的legacy corpus JSON，不依赖旧legalhub运行时。输入为images（image_id/file/sha256）和records（message/event、text、source_refs；可带person/timestamp_normalized/event_type）。每次只导入一个case_id；混案文件须先显式按案分开。

从product_v1执行：

```powershell
./.conda/screenshotlegal-v1/python.exe tools/import_legacy_case.py C:/exports/case.json --legacy-root C:/exports --title "导入案件"
```

2026-10-23修复：完整预校验路径、必需SHA256、图片实际编码、边界框、消息及事件引用后才写入。数据库记录和检索索引使用同一事务；后续异常回滚并清理本次新UUID目录，其他案件和原始文件保留。旧图片扩展名与编码可能不同（实测9个.jpg为WebP），迁移器按解码格式验证，保留原名、原字节和哈希。

重复文本按原消息ID及具体位置关联，多个出现位置分别保存，事件不再按文字反查。未知证据页码保存null；API SourceRef现允许null，界面不虚构第1页。非空页码必须为正整数。历史已有第1页不会自动改写。原有时间归一化不能证明真实事件发生时间；导入仍为未复核。

已在临时数据库迁移2案9图81消息16事件，检查哈希、来源、检索及审计JSON/CSV往返，见[迁移回归](../../reports/v3.0.0/import_atomicity_20261023_001/README.md)。审计导出不代表新增产品UI导出。case_law/statute等辅助记录不转为案件事件；本工具迁移图片、消息与事件。

可处理的运行异常不留下半案；进程强杀/断电可能留下未被数据库引用的文件目录。成功导入后再次运行仍会新建案件，本修复不提供成功导入去重。没有批量写入生产案件或删除旧库。

## 同步已有几何标注

完成案件导入后，可运行仓库根目录下的 `product_v1/tools/sync_evidence_regions.py`，默认只预检；`--apply`先备份再追加SourceRef。它按原图SHA256从渲染清单/LabelU恢复框，不借用旧作者转录、不改FTS或人工记录。[坐标恢复与评测说明](../../docs/coordinate-retrieval-evaluation.md)记录实际范围与剩余缺口。
