# ScreenshotLegal Product v1

> 2026-11-17 源码核验：当前五个页面入口共用前后端和账户体系，`agentic` 尚未接入；[当前总架构](../docs/architecture.md)区分源码事实与历史验收。当前 Vite 开发配置及后端 Settings 的默认 host 为 `0.0.0.0`，实际监听由启动入口决定；下文旧版本“仅回环”描述不能覆盖当前配置。以下测试与运行记录均保留原日期，本次未重新运行。长期本地服务按工作区约定交由 PM2 管理。

## 截图审核与合成修正包（2026-11-06）

审核、生成、评测和管理控制台采用方案 PDF 的 Pack 3 样式。审核入口新增 A/B 独立面板，明确来源等级、保留原始多模态 JSON、区分原文支持与合理模拟，并支持完整导出、原子恢复和独立锁定。用户工作台入口保持原样。

[操作、数据范围与恢复规则](docs/SCREENSHOT_REVIEW_PANEL.md) · [验证报告与界面预览](reports/screenshot-panel-2026-11-06/REPORT.md)

原 KIE/VQA、导入与发布工作区移至 [完整数据审核工作区](http://127.0.0.1:18431/review.html?view=library)。

## 原图核对与资料整理（2026-10-25）

审核台的“核对原图与答案”进入并排核对工作区，支持缩放、坐标编辑与撤销、LabelU 单任务矩形交换。用户工作台在“概览 → 打开资料工作区”提供本地 MinerU PDF/Office 解析、分页续读、批注草稿与原文定位。扫描件 OCR 尚未部署。

[机制、源码调用链和修改指南](../docs/products/DOCUMENT_READING_AND_REVIEW.md)。本机隔离解析环境已安装；其他机器运行 scripts/setup-documents.ps1，不改变后端环境。

## 三个研究产品 MVP（2026-10-24）

审核页现支持图片坐标框点击编辑、默认锁定/解锁拖拽、保存重渲染、判决书侧栏和独立评论；生成台可读取同源审核评论迭代。[操作说明](../docs/products/REVIEW_CANVAS.md)。

- [数据审核台](http://127.0.0.1:18431/review.html)：导入、纠正、草稿、真实重渲染、人工/模型质量记录与质量 Prompt、固定版本发布。
- [合成生成台](http://127.0.0.1:18431/studio.html)：生成 Prompt Markdown 迭代、批次与产物、按批次/Prompt 读取质量结果对比。
- [评测台](http://127.0.0.1:18431/evaluation.html)：固定发布版本、多模型/多模式任务、逐题错误、指标与关联重试。

沿用下方启动命令。研究库独立初始化；首次使用从审核台“导入与发布”选择已有 V2/V3 批次。原用户工作台与案件数据保持兼容。[使用与数据恢复说明](../docs/products/RESEARCH_MVP.md) · [验证报告](reports/research-products-mvp-2026-10-24/REPORT.md)


## 当前入口：用户工作台 MVP（2026-10-24）

默认页面 http://127.0.0.1:18431/ 现在只包含概览、编辑、证据时间线、模拟生成 PPT。编辑支持案件名称/工作摘要/备注、浏览器本地草稿恢复和保存版本冲突检查；时间线可直接展示已导入证据，无需先运行分析。PPT 当前明确返回模拟状态，不生成真实文件。

旧完整控制台保留在 http://127.0.0.1:18431/console.html ，下方历史证明矩阵、模型设置、审核和 DAG 操作均可在此进入。

[四个独立产品的当前边界与实施状态](../docs/products/PRODUCT_BOUNDARIES.md) · [本轮 MVP 验证](reports/user-workbench-mvp-2026-10-24/REPORT.md)


> 2026-10-24：全仓库案件已实际导入本机运行库，admin可见2687条案件/版本记录（原有5+新增2682），重跑新增0。刷新 http://127.0.0.1:18431 后可查看总数并按标题/描述、案号、round、来源和状态搜索。[全量清单与审计](../reports/admin_case_inventory_20261024/README.md) · [同步命令](docs/MIGRATION.md)。计数含原文与历史版本，不代表专业认证数。

> 2026-10-22离线复核：后端43/43、前端9/9、TypeScript/ESLint/UI架构检查通过；未重跑浏览器或真实模型。[综合进度及日志](../docs/ai_docs_center/PROGRESS.md) · [问题/缺口](../docs/ai_docs_center/README.md)。下文10月13日的启动、浏览器和构建记录保留为历史验收。

独立的电子证据法律工作台。原仓库、旧 `legalhub`、Benchmark、历史报告均不属于本产品运行时依赖。

采用简约浅色界面；业务功能、UI 适配组件、设计 tokens、图标与动效分开。后续替换 UI 库或增加视差滚动，不需要修改领域模型或业务 API。

## 已使用的本地环境

- Windows 11 专业版 10.0.22621。
- **Conda 环境：`screenshotlegal-v1`**，本机前缀为 `D:\workspace\screenshotLegalHub\product_v1\.conda\screenshotlegal-v1`；定义见 [environment.yml](environment.yml)。本轮实测 **Python 3.12.15 / Node 22.23.2 / npm 10.9.8**，均来自同一个 Conda 环境。
- 本机 Conda：`D:\ProgramData\miniconda3\Scripts\conda.exe`（24.1.0）。环境及依赖缓存独立存放于产品目录，不修改旧环境。
- 保留原有 **Python 3.12.13 venv：`backend/.venv`**；原 uv 运行时位于 `.tools/python/`，原 PowerShell 脚本使用 NVM 的 **Node 22.14.0 / npm 10.9.2**。
- SQLite + SQLAlchemy 2 + Alembic；FastAPI；React + TypeScript + Vite + TanStack Query。
- Python 精确版本在 `backend/requirements.lock`；前端在 `frontend/package-lock.json`。

## 本次新增：批量证据、登录与模型设置

- **证据**：一次选择多张 PNG/JPEG/WebP 聊天截图，按文件显示成功、重复或失败，支持只重试失败文件。默认每批 50 个文件、每个 20 MiB、每批总量 100 MiB；同案相同内容复用已有证据。
- **用户**：首次打开创建管理员；管理员在“用户”页添加账号、调整管理员/普通用户权限、停用账号。登录会话默认 8 小时，可修改个人资料和密码。首次管理员自动接管升级前没有所有者的案件。
- **案件协作**：案件默认归创建者所有；在概览的“案件协作权限”中按用户名授权“仅查看”或“可编辑”。管理员可以管理全部案件；普通用户只能访问自己的或获授权的案件。
- **模型设置**：添加多个 OpenAI 兼容模型，填写基础地址、模型标识与 API Key；支持编辑、删除、默认模型和连通性测试。模型及 Key 按用户隔离，Key 加密存储且不回显。识别前须启用请求授权，在证据页选择视觉模型；连接测试只发送短文本。
- **格式扩展**：图片自动校验、读取尺寸并生成独立证据；PDF/UTF-8 文本可批量保存原件。ZIP 自动展开、PDF 分页/OCR 尚未启用；格式处理器与存储、上传接口分离，后续在导入流水线扩展。详见 [批量导入与账户配置](docs/INGESTION_ACCOUNTS_MODELS.md)。

本次 Conda 实测：**后端 43 项、前端 9 项、Chromium 5 项全部通过**，包含双用户权限与模拟服务连接成功/失败流程；类型、lint/架构检查和构建通过。见 [本次功能测试报告](reports/multi-upload-auth-2026-10-13/REPORT.md)。没有调用收费模型。

**升级已有安装**：先执行 `python scripts/conda_workspace.py setup` 安装新增依赖和迁移，然后重启前后端。本机已完成依赖更新和迁移，确认无运行中的分析后刷新了开发后端；原地址 `http://127.0.0.1:18431` 已能访问新接口，首次打开创建管理员即可。本次浏览器测试使用独立的 19430/19431/19432 端口和数据库。

## 启动（Linux / Bash，Conda）

先安装 Conda，并确保 `conda` 命令可用。以下命令在 `product_v1/` 执行；环境第一次创建和依赖安装需要联网。`environment.yml` 使用 conda-forge 的 Python 3.12、Node 22、pip 和 setuptools，Python 应用依赖仍按 `backend/requirements.lock` 安装。

```bash
cd /path/to/screenshotLegalHub/product_v1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda env create --prefix ./.conda/screenshotlegal-v1 --file environment.yml
conda activate "$PWD/.conda/screenshotlegal-v1"
python scripts/conda_workspace.py setup
python scripts/conda_workspace.py seed
```

`setup` 安装后端和前端依赖并执行 Alembic 迁移；`seed` 创建合成演示案件。已有环境时跳过 `conda env create`。原生 Conda 环境文件不能跨系统复制，应在 Linux 上按定义重新创建。

在两个终端分别启动，每个终端都先切换目录并激活环境：

```bash
# 终端 1：后端
cd /path/to/screenshotLegalHub/product_v1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$PWD/.conda/screenshotlegal-v1"
python scripts/conda_workspace.py backend
```

```bash
# 终端 2：前端
cd /path/to/screenshotLegalHub/product_v1
source "$(conda info --base)/etc/profile.d/conda.sh"
conda activate "$PWD/.conda/screenshotlegal-v1"
python scripts/conda_workspace.py frontend
```

页面：**http://127.0.0.1:18431**；API：**http://127.0.0.1:18430/docs**。按 Ctrl+C 停止各自终端中的服务。

也可以使用已激活 Conda 环境中的原生命令：

```bash
# 在 product_v1/ 中执行后端命令
python -m alembic -c backend/alembic.ini upgrade head
python -m screenshotlegal.cli.seed
python -m uvicorn screenshotlegal.api.main:app --host 127.0.0.1 --port 18430
# 前端在另一终端执行
cd frontend
npm run dev
```

## 启动（PowerShell，Conda）

以下命令在 `product_v1/` 执行。本机无需修改 PowerShell Profile，使用 `conda run` 即可；其他机器请把 `$CondaExe` 替换成自己的 Conda 可执行文件路径，或直接使用可用的 `conda` 命令。

```powershell
cd D:\workspace\screenshotLegalHub\product_v1
$CondaExe = 'D:\ProgramData\miniconda3\Scripts\conda.exe'
# 首次创建；本机已经创建，重复使用时跳过这一行
& $CondaExe env create --prefix .\.conda\screenshotlegal-v1 --file environment.yml
& $CondaExe run --no-capture-output --prefix .\.conda\screenshotlegal-v1 python scripts/conda_workspace.py setup
& $CondaExe run --no-capture-output --prefix .\.conda\screenshotlegal-v1 python scripts/conda_workspace.py seed
```

在两个终端中分别执行（均从 `product_v1/` 开始；每个终端先定义 `$CondaExe`）：

```powershell
$CondaExe = 'D:\ProgramData\miniconda3\Scripts\conda.exe'
& $CondaExe run --no-capture-output --prefix .\.conda\screenshotlegal-v1 python scripts/conda_workspace.py backend
```

```powershell
$CondaExe = 'D:\ProgramData\miniconda3\Scripts\conda.exe'
& $CondaExe run --no-capture-output --prefix .\.conda\screenshotlegal-v1 python scripts/conda_workspace.py frontend
```

## 单元测试与报告（Conda）

测试入口会运行后端 pytest、前端 Vitest，以及 TypeScript、lint/架构边界检查、生产构建。即使某一步失败，也继续收集其余结果；最终失败时返回非零退出码。测试模式关闭真实模型和证据外发。

```bash
# Linux：在 product_v1/ 中激活上述 Conda 环境后执行
python scripts/conda_workspace.py test --report-dir reports/latest
```

```powershell
# Windows：在 product_v1/ 中执行
$CondaExe = 'D:\ProgramData\miniconda3\Scripts\conda.exe'
& $CondaExe run --no-capture-output --prefix .\.conda\screenshotlegal-v1 python scripts/conda_workspace.py test --report-dir reports/latest
```

每次生成 `REPORT.md`、`summary.json`、后端/前端 JUnit XML 和逐项日志，位置为 `reports/latest/`（不提交）。使用不同的 `--report-dir` 可保留某次结果。

新增环境时 **2026-10-13（Asia/Singapore）** 的历史实测见 [Conda 测试报告](reports/conda-2026-10-13/REPORT.md)；环境配置和启动说明见 [Conda / Linux 配置记录](docs/CONDA_LINUX_SETUP.md)。下列 21/4 数量属于环境初始化时的版本，当前新增功能及更完整的测试见本文开头报告。本轮运行平台为 Windows，Linux 命令使用同一跨平台入口，但没有原生 Linux 测试结果。

- 后端单元测试：**21 / 21 通过**；前端组件单元测试：**4 / 4 通过**，无失败、无跳过。
- TypeScript、lint、UI 架构检查、生产构建及 `pip check` 全部通过。
- 真实启动验证：迁移、合成 Demo、后端健康接口/API 文档、前端页面和 API 代理全部通过；原始记录见 [startup-smoke.json](reports/conda-2026-10-13/startup-smoke.json)。验证使用临时数据目录，结束后清理验证服务。

## 启动（PowerShell，原有 venv）

在仓库根目录执行。首次初始化需要 uv、Node 22，以及下载依赖的网络；初始化后无 Key Demo 和测试无需模型网络调用。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\product_v1\scripts\bootstrap.ps1
```

在两个终端分别执行：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\product_v1\scripts\dev-backend.ps1
```

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\product_v1\scripts\dev-frontend.ps1
```

访问 **http://127.0.0.1:18431**，API 文档 **http://127.0.0.1:18430/docs**。端口固定为 18430 / 18431，默认仅监听回环地址。

进入合成案件，点击“证明矩阵”→“查看引用”可以打开原图并高亮原图像素 bbox。进入“人工审核”可确认、编辑、拒绝或暂缓；进入“运行详情”可编译计划、启动新运行，并批准 compile-review / critical-finding 关卡。刷新后先从 SSE `state-snapshot` 恢复数据库状态。历史运行与审核记录保留。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\product_v1\scripts\seed-demo.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\product_v1\scripts\test.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\product_v1\scripts\verify.ps1
```

`verify.ps1` 包含后端测试、前端类型/lint/架构检查、组件测试、生产构建、Chromium E2E 与 axe 无障碍 smoke。E2E 使用独立的测试端口和 `.tools/e2e-data/run-*` 数据目录，自动启动并清理测试服务，不复用开发服务；测试数据保留供排查。所有脚本失败都会非零退出。

## 手动命令

以下命令在 `product_v1/` 执行，均使用本目录 venv：

```powershell
& .\backend\.venv\Scripts\python.exe -m alembic -c .\backend\alembic.ini upgrade head
& .\backend\.venv\Scripts\python.exe -m screenshotlegal.cli.seed
& .\backend\.venv\Scripts\python.exe -m uvicorn screenshotlegal.api.main:app --host 127.0.0.1 --port 18430
```

前端命令在 `frontend/` 执行且需要 Node 22：`npm ci`、`npm run dev`、`npm run build`。

## 上传自己的证据

登录 → 新建案件 → 一次选择多张聊天截图，也可选择 PDF/文本。上传会校验 MIME、大小和 SHA256，安全文件名由内容哈希生成；批量结果逐项显示，坏文件不会阻止其余文件，重复内容不新增证据。图片是本版的完整 Viewer 目标；PDF 可预览，PDF 专业解析和 ZIP 解压属于后续版本。

默认 Mock 不会为真实上传编造消息。人工转录文件是以 Evidence ID 为键的 JSON 对象，在“证据”页导入：

```json
{
  "ev.<上传返回的ID>": [
    {"text":"图片中可见的原文","speaker":"unknown","timestamp":null,"event_type":"other","bbox":[30,130,690,220],"coordinate_space":"pixels"}
  ]
}
```

`bbox` 使用原图像素；`normalized_1000` 必须明确声明，系统只转换一次。没有完整日期时使用 null，不补造日期。完成转录后在“运行详情”确认案由并编译、运行。

## 可选视觉模型

在“模型设置”添加服务：填写 HTTPS 基础地址（通常含 `/v1`）、模型标识与 API Key，确认是否支持图片，并显式勾选允许模型请求。保存后可以测试连通性，识别不需要重启后端；在证据页勾选“使用已配置视觉模型”并选择配置即可处理案件中所有截图，PDF/文本不会发送给视觉模型。仅回环服务允许 HTTP。每位登录用户使用自己的模型设置，网页请求不使用旧 `.env` 中的共享模型 Key。

Key 密文位于 SQLite，主密钥位于 `data/.credentials/model-master.key`，备份必须包含两者。API 只返回是否已保存 Key；编辑时留空保留已有 Key。模型调用记录 provider/model/run/evidence IDs，不记录 Key 或供应商响应正文。本轮验证**没有调用收费模型**，连通性和图片转录用模拟 HTTP 与本地模拟服务验证。

法律 Matter Pack 和 Authority 均明确标记 draft/unreviewed 或 unverified。确定性内置 Skills 用于可审计的线索整理与完整 Demo；关键词支持关系不代表事实已证明，不提供胜诉概率。正式专业化还需要专家校验规则与更强的分析 Skills。

## 文档

- [架构与模块边界](docs/ARCHITECTURE.md)、[运行时](docs/RUNTIME.md)、[Schema](docs/SCHEMA.md)、[API](docs/API.md)
- [Matter Pack 编写](docs/MATTER_PACK_AUTHORING.md)、[Skills](docs/SKILLS.md)、[插件信任](docs/PLUGIN_TRUST.md)
- [UI 替换与动效边界](docs/DESIGN_SYSTEM.md)、[Holmes 参考边界](docs/HOLMES_REFERENCE.md)
- [配置与实际踩坑](docs/TROUBLESHOOTING.md)、[本地运行验证](docs/LOCAL_RUN_VERIFICATION.md)
- [Conda / Linux 配置记录](docs/CONDA_LINUX_SETUP.md)、[2026-10-13 Conda 测试报告](reports/conda-2026-10-13/REPORT.md)
- [批量导入、账户与模型扩展](docs/INGESTION_ACCOUNTS_MODELS.md)、[本次功能测试报告](reports/multi-upload-auth-2026-10-13/REPORT.md)
- [验收映射](docs/ACCEPTANCE.md)、[实现报告](docs/IMPLEMENTATION_REPORT.md)、[迁移](docs/MIGRATION.md)、[安全](docs/SECURITY.md)

运行数据位于 `data/`，原图与 SQLite 都在新目录内；不包含真实证据或密钥。独立迁移时复制此目录的源码、Matter Packs、fixtures、profiles 和锁文件即可，运行数据按需单独备份。
