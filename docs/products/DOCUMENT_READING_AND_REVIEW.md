# LabelU 核对工作区与 MinerU 资料阅读：实现及修改指南

日期：2026-10-25，Asia/Singapore。本轮实现以本地内网试用为目标。解析、人工审核和模型分析分别记录，原件不随答案或批注修改。

## 先在哪里使用

- 数据审核台 /review.html?section=benchmark：选择任务后点击“核对原图与答案”，工作区出现在任务列表前并取得焦点。左侧原图，右侧问题、目标答案与审核信息。
- 用户工作台 /：选择案件 → 概览 →“打开资料工作区”。可以上传多份不同格式的资料，也可以从已有案件原件添加。
- PDF 点击“解析下一段”每次最多 3 页。解析完成的块可搜索、逐段阅读；点击条目或模型引用，右侧定位原页及坐标区域。
- 批注键入时缓存于当前浏览器，点击“保存批注与阅读位置”后保存到服务器。重新打开案件可继续上次保存位置。
- 模型分析需选择自己的模型并单独点击。当前段默认最多 5 块；它使用已有的请求授权开关，不自动启用模型或外发权限。

## 这些能力为什么能工作

“支持很多文件格式”“渐进式处理”“定位原文”不是同一个算法。对应三个设计：统一结构协议、按范围处理与缓存、贯穿流程的来源坐标。

### 1. 混合格式如何进入同一条流程

MinerUParser._prepare_input 读取文件、识别后缀并准备源上下文；PDF 的页范围会转换为实际保留页索引。_run_analysis 委托统一 doc_analyze 入口，按格式与解析档位分发。Office 等原生格式由 DocVortex 解析；不是所有格式都先转 PDF。源码入口：
[MinerUParser](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/parser/mineru_parser.py)。

本轮真实 PPTX 测试还发现：幻灯片要点输出为 list_items，而不是 text。适配器若只读 text 会漏掉金额，本项目已在 normalized 中补上该类型，并增加回归测试。扩展新块类型时，应先看真实原始结构。

不同引擎最后提供共享结构：页、按阅读顺序组织的块、文本/表格/公式/图片类型，以及可获得的几何信息。Markdown 是输出视图；仅保存 Markdown 会丢失一部分定位信息。官方 [输出契约](https://opendatalab.github.io/MinerU/reference/output_files/) 区分 MiddleJson、Structured Content、Content List 和保存产物。

版本必须明确。本轮隔离运行 MinerU 4.0.12 + DocVortex 0.6.1。4.x 的 MiddleJson 通过 schema=docvortex.middle、schema_version=2.0 标识。旧 pdf_info/_backend 格式属于另一代协议，不能简单改版本号后混用。本项目消费渲染出的 Content List V1，并保留本窗口原始 MiddleJson 供后续升级。

### 2. 长文档为什么可以渐进处理

PDF 可以显式传 page_range。一次只解析所需范围，保留原始 page_idx，避免把第 4 页误标为新结果的第 1 页。Office 原生格式当前通常整体解析，然后按结构块分段阅读；两者的处理粒度不同。
[SDK 与页范围说明](https://opendatalab.github.io/MinerU/usage/sdk_api/)。

MinerU 的 Doclib 在解析器外增加文件身份、任务、页范围覆盖和缓存层。可顺着 ParseService.request_parse → acquire_task → process_doc 阅读，并检查 page_range_covered/page_range_uncovered。已有范围可复用，缺失范围另建任务。
[ParseService 源码](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/doclib/services/parse_svc.py)。

“解析”产出结构块；“分析”需要上层模型或人工处理。本项目把它们拆开：先提交页段，再读取当前块、写批注或调用选定模型。不会将未解析后续页默认为已分析，也不会在恢复时自动重发可能计费的模型请求。

### 3. 原文为什么可以准确回跳

定位需要稳定的文件身份、页、块，必要时加字符偏移。MinerU Doclib 的定位器包括文档短 ID、tier、page、block、char；它的定位页/块编号从 1 开始。
[locators.py](https://github.com/opendatalab/MinerU/blob/b7f3dd0c5f6e6d66a298239ffd02b328b873918e/mineru/doclib/locators.py)。

本项目独立使用 document:{本案文档 ID}/page:{1 基页码}/block:{0 基全局块序号}，并绑定原件 SHA256 和解析器版本。它不是 MinerU Doclib 定位器，不能直接互传。

PDF 的预览来自同一份已校验 SHA256 的原件。Content List V1 的 bbox 是 0–1000 归一化坐标；页面 SVG 使用相同坐标系覆盖实际页图，缩放时不再次换算。没有可靠 bbox 的块只定位到页，不伪造框。Office 当前只承诺逻辑单元与结构块定位，不承诺 Word/Excel 打印页上的像素位置。

### 4. LabelU 的哪些机制被采用

LabelU 的工作模式是“任务/样本 → 原图 → 标注图形与属性 → 修改/审核 → 结果”。[图像标注指南](https://opendatalab.github.io/labelU/en/guide/annotation/image) 展示画框、选中结果、修改标签、撤销等操作。

LabelU-Kit 将矩形的数据和交互图形分开。RectData 的核心为像素 x、y、width、height；图形负责绘制与交互，业务数据负责属性和保存。
[Rect.annotation.ts](https://github.com/opendatalab/labelU-Kit/blob/eb0e5c183003211e489a462424dfe25e33c3e97e/packages/image/src/annotations/Rect.annotation.ts)。

本项目沿用这个分离方式，现有 React/SVG 画布继续使用自己的组件；没有嵌入完整 LabelU 平台。支持矩形缩放查看、拖拽/角点调整、数值坐标输入、坐标撤销/重做、显隐旧框，以及单任务矩形交换。

交换文件 schema 为 screenshotlegal.labelu-rect.v1，annotations 内的几何字段采用 LabelU-Kit 矩形形式。外层附带本项目任务与原图哈希。它不是通用 LabelU 项目备份导入器；历史 LabelU 全项目迁移仍走已有 Benchmark 导入流程。多框/多边形等扩展需要单独实现转换器，不会静默丢弃。

## 本项目端到端流程

~~~mermaid
flowchart TD
    A[上传资料 / 从案件原件添加] --> B[格式校验 + SHA256 + 原件保留]
    B --> C[文档记录 pending]
    C --> D[领取一个解析窗口的租约]
    D --> E[隔离 Python: MinerUParser / 本地文本读取]
    E --> F[原始结构与 Content List 缓存]
    F --> G[同一事务写入不可变块和页进度]
    G --> H[分段阅读 / 搜索已解析块]
    H --> I[点击块: 原页预览 + 坐标高亮]
    H --> J[本机草稿 → 显式保存批注与阅读位置]
    H --> K[显式调用所选模型]
    K --> L[验证所有引用属于当前窗口]
    L --> M[保存分析及来源快照]
~~~

### 接口与职责

| 文件 | 负责什么 | 后续改动入口 |
| --- | --- | --- |
| backend/src/screenshotlegal/api/documents.py | HTTP 参数、案件路由、上传、解析窗口、批注、分析 | 改请求大小/窗口参数、增加 API 能力 |
| backend/src/screenshotlegal/documents/service.py | 格式校验、来源校验、块归一化、解析推进、分析引用验证 | 改格式列表、块字段、分析规则 |
| backend/src/screenshotlegal/documents/store.py | 独立 SQLite、不可变块、进度、批注版本、分析记录 | 改索引/查询、历史策略、存储后端 |
| backend/src/screenshotlegal/documents/adapter.py | 解析端口、隔离解释器、超时、窗口产物缓存 | 接新 MinerU 版本/独立服务 |
| scripts/document_worker.py | 真正调用 MinerU、Content List 输出、PDF 原页渲染 | 改 tier、parse_mode、模型和渲染配置 |
| frontend/src/features/workbench/DocumentWorkbench.tsx | 资料列表、搜索、逐段阅读、引用选择、原页高亮、批注草稿 | 改阅读交互、段大小、模型分析入口 |
| frontend/src/features/research/RegionCanvas.tsx | 原图坐标与交互 | 改标注工具、选框、快捷键 |
| frontend/src/features/research/labelu.ts | 矩形几何的导入导出及原图身份检查 | 扩展 LabelU 数据适配器 |
| frontend/src/features/research/BenchmarkPanel.tsx | 任务选择、答案/审核版本、原有本地与服务器草稿 | 改审核用例和问题/答案编辑 |

API 的案件权限继续由现有 access middleware 校验；文档存储查询也携带 case_id。用户工作台数据没有写入研究数据集数据库。

### 可持久化的数据

data/documents/ 下包含：

- originals/：按 SHA256 保存的原件。
- documents.sqlite3：文档状态、不可变结构块、批注 revision、分析记录。
- cache/{document_id}/：按解析版本与窗口参数索引的结果；包含原始 MiddleJson 与 V1 内容。
- previews/{document_id}/：原 PDF 页图缓存，可重新生成。

SQLite 使用 WAL/FULL 提交；窗口内的块与 parsed_pages 在同一事务中提交。解析产物先写临时文件、flush/fsync，再原子替换。中断后已提交页保留；当前窗口租约 240 秒，到期后可重新领取。一个窗口处理超时 180 秒。它是可重试的本地页段流程，尚未作为分布式 worker 集群验收。

批注带 expected_revision，冲突返回 409 并保留本地草稿。浏览器草稿按用户、案件、文档隔离；服务器批注与阅读位置是案件协作数据。

模型分析保存模型 ID/实际模型名称、文档 SHA256、解析协议、块 ID、输入哈希、指令与结果。引用必须属于本次输入；这只能确认来源范围，不能证明模型概括一定忠实。异常结果保留待确认状态，系统不自动重新调用。

## 怎样有针对性地修改

### 想把 PDF 每批 3 页改为 5 页

1. DocumentWorkbench 的 parse-next 请求 pages 改成 5，并改按钮文案。
2. API 的 Window 范围当前允许 1–10，不必同时改变服务层。
3. 用 7 页合成 PDF 检查进度应为 5 → 7；第二个窗口中的第一块应保留第 6 页，而不是第 1 页。
4. 缓存键包含窗口参数，不能用 3 页旧窗口冒充 5 页产物。

### 想加入扫描件 OCR 或复杂公式/表格识别

1. 在隔离环境准备对应 MinerU OCR/VLM 权重与运行时；先用授权的合成样本验证。
2. 修改 document_worker.py 的 tier/parse_mode/image_analysis；当前固定 flash/txt/False，图片只保留原件，不声称已经 OCR。
3. 调整 adapter.py 的 PIN，为新解析策略创建新文档解析版本；不要覆盖已有引用对应的块序号。
4. 增加扫描 PDF、旋转页、公式、跨页表格的样本与坐标回跳检查。
5. 如接远端解析服务，将上传授权、网络错误和服务任务 ID 放在新 Adapter 中。不要把密钥写入任务或日志。

### 想改逐段分析方法

在 Documents.analyze 修改系统指令与输出校验；用户可在页面修改本段分析要求。当前输入仅当前起点的最多 5 块，合计超过 30,000 字符会要求缩小范围。若要加入跨段总结，应明确保存上段结论及其引用，再由新任务消费，避免把模型生成内容当作原文。

### 想增加标注类型

在独立转换器中定义坐标单位、图形结构和版本。当前内部参考框为 xyxy 像素；LabelU 矩形交换为 xywh 像素。转换为 width=x2-x1、height=y2-y1，不受显示缩放影响。导入时要求同一 SHA256、同一尺寸、有效边界；导入后重置图片确认与通过状态，形成待人工审核的草稿。

## 当前支持与边界

| 内容 | 当前行为 |
| --- | --- |
| 带文本层 PDF | 真正调用本地 MinerU Flash，按页段处理，原页图与 bbox 定位 |
| DOCX/XLSX/PPTX | 原生解析为统一结构；逻辑单元、段落和表格；整文件解析后分块阅读 |
| TXT/MD | UTF-8 原文切块，保存字符起止偏移 |
| CSV | 本地 MinerU 原生表格解析 |
| PNG/JPEG/WebP | 原件预览与人工批注；此入口不宣称有 OCR 转录 |
| 扫描 PDF、复杂公式/表格 | 当前 Flash 文本层不构成完整识别承诺，需部署并验证相应引擎 |
| 模型分析 | 已接已有模型配置；仅显式触发，来源范围验证；本轮用替身测试，无外部模型调用 |
| LabelU | 当前任务矩形/答案交换与相应交互；未部署完整 LabelU 服务 |
| 工业使用 | 可在本机/受控内网试点；未做大规模吞吐、旋转/坏页矩阵、分布式恢复与生产环境验收 |

当前沿用单文件 20 MiB 的配置上限。解析环境由 scripts/setup-documents.ps1 创建；固定依赖见 scripts/documents-requirements.txt，实际安装快照见 scripts/documents-requirements.lock。部署到其他操作系统时，按该平台重新解析依赖，Windows 安装快照不保证跨平台通用。

## 验证入口

- backend/tests/test_documents.py：权限、页段恢复、租约、批注冲突、原件完整性、范围外模型引用、表格和查询分页。
- frontend/e2e/benchmark-migration.spec.ts：实际点击核对按钮、画布焦点/缩放、坐标编辑、LabelU 交换、审核保存和发布。
- frontend/e2e/documents.spec.ts：合成 PDF/Word/Excel 的真实本地解析，3→6→7 页进度、批注刷新恢复、原页图片与区域高亮、375px 和横屏布局。
- scripts/make-document-fixtures.py：使用隔离解析环境生成测试资料；不依赖用户案件。

可复跑本地解析检查：用项目 Conda Python 执行 scripts/verify_document_parser.py --output reports/document-parser-local。脚本每次新建合成测试目录，验证五种格式及 PDF 3→6→7 页进度。
