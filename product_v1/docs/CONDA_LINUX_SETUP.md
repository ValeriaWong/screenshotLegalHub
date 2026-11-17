# Conda 环境与 Linux 启动配置记录

验证日期：2026-10-13，Asia/Singapore。当前实测平台是 Windows 11；Linux 使用相同 Python 入口和依赖文件，但本机未取得可用的 Linux 运行环境，不将 Windows 实测记作 Linux 实测。

本页保留新增环境时的历史结果；后续已加入登录、批量上传与模型设置，最新数量为后端 43 / 前端 9 / 浏览器 5，见 [功能报告](../reports/multi-upload-auth-2026-10-13/REPORT.md)。

## 实际创建的环境

| 项目 | 实际配置 |
| --- | --- |
| Conda | `D:\ProgramData\miniconda3\Scripts\conda.exe`，24.1.0 |
| 环境前缀 | `D:\workspace\screenshotLegalHub\product_v1\.conda\screenshotlegal-v1` |
| Python | 3.12.15 |
| Node | 22.23.2，使用 Conda 内的 Node |
| npm | 10.9.8，使用 Conda 内的 npm |
| 通用定义 | [environment.yml](../environment.yml) |
| Python 应用锁 | [backend/requirements.lock](../backend/requirements.lock) |
| 前端依赖锁 | [frontend/package-lock.json](../frontend/package-lock.json) |
| Windows Conda 包精确清单 | [conda-win-64-explicit.txt](../reports/conda-2026-10-13/conda-win-64-explicit.txt) |

本机创建时使用独立前缀和 `--override-channels --channel conda-forge`，依赖缓存通过本次进程的 `CONDA_PKGS_DIRS` 放到 `product_v1/.tools/conda-pkgs`。没有修改用户的全局 `.condarc`、既有环境或 NVM 默认版本。目录 `.conda/`、`.tools/` 均忽略提交。

环境文件按 Python 3.12 / Node 22 主次版本约束，跨平台安装的补丁版本可能不同，报告记录实际解析版本。Windows 精确清单只用于 `win-64`，不能在 Linux 直接使用。迁移到 Linux 时复制产品源码与依赖文件，然后重新创建环境；本项目的 editable 安装也需重新执行。

## 完整 Linux 流程

安装 Conda 后，按 [README 的 Linux 部分](../README.md) 执行。核心流程在 `product_v1/` 中为：

```bash
source "$(conda info --base)/etc/profile.d/conda.sh"
conda env create --prefix ./.conda/screenshotlegal-v1 --file environment.yml
conda activate "$PWD/.conda/screenshotlegal-v1"
python scripts/conda_workspace.py setup
python scripts/conda_workspace.py seed
python scripts/conda_workspace.py test --report-dir reports/latest
```

`backend` 和 `frontend` 子命令分别在两个激活该环境的终端中启动。页面为 `http://127.0.0.1:18431`；后端为 `http://127.0.0.1:18430`，Swagger 位于 `/docs`。

不使用 shell 激活时，也可从 `product_v1/` 执行：

```bash
conda run --no-capture-output --prefix ./.conda/screenshotlegal-v1 \
  python scripts/conda_workspace.py backend
```

Linux 首次安装完成后，按同样方式运行测试，在 Linux 上生成自己的报告。原有 `bootstrap.ps1`、`dev-*.ps1`、`test.ps1`、`verify.ps1` 仍是 Windows venv 工作流，不作为 Conda/Linux 的入口。

## 本次实测的配置要点

### Conda 不在当前 PowerShell PATH

当前 `Get-Command conda` 找不到命令，但本机确实安装了 Miniconda。使用上述 `conda.exe` 绝对路径和 `conda run` 完成创建、安装、测试与启动验证，无需修改 PowerShell Profile。Linux 的 `conda activate` 依赖 shell 初始化，文档中显式 source `conda.sh`。

### Python 与 Node 必须来自同一新环境

本机默认 Python 3.9 与旧 NVM Node 不符合本产品配置。新入口检测 `sys.prefix/conda-meta`、Python 3.12、Node 22，并要求 Node 路径位于当前 Conda 前缀。漏激活或 PATH 混用时直接失败，不悄悄转回 venv 或全局 Node。

Windows 的 npm 入口是 `.cmd`，Linux 常为符号链接。入口解析对应的 `npm-cli.js`，再用 Conda 的 Node 执行，避免 shell 参数转义和 Windows 批处理差异。本次实际安装、Vitest、lint 和构建均走这条路径。

### 环境创建不会自动安装应用

`environment.yml` 安装 Python、pip、setuptools、Node；`setup` 再安装锁定的应用依赖、以 editable 模式安装 `backend`，执行 `npm ci` 和数据库迁移。缺少 editable 安装会导致找不到 `screenshotlegal`；缺少迁移会导致接口查询表失败。

editable 安装采用 `--no-deps --no-build-isolation`，依赖已通过锁文件安装，构建所需 setuptools 来自 Conda。`setup` 不依赖原来的 uv 或 `backend/.venv`。

### 测试与实际案件数据

后端现有测试通过临时数据库夹具运行。真实启动验证也单独设置临时 `DATA_DIR`，执行迁移、创建合成 Demo、启动两个服务和验证代理，结束后清理临时数据及本次服务。普通 `setup` / `seed` / `backend` 命令则使用 `.env` 与默认 `data/` 配置。

`test` 子命令显式关闭真实模型和外发；服务启动子命令保留用户的模型配置。测试报告以 UTC+08:00 时间记录，不依赖 Windows 是否具备 IANA 时区数据库。

### 已观察到的依赖提示

后端 21 项测试通过，存在 1 条 Starlette TestClient 对 `httpx` 的弃用提示。前端安装有 `whatwg-encoding` 的弃用提示，未影响安装、组件测试或构建。本轮保留原依赖锁，没有为消除提示而升级应用依赖；`pip check` 返回 `No broken requirements found.`。

## 测试与启动证据

- [可读测试报告](../reports/conda-2026-10-13/REPORT.md)与[机器可读汇总](../reports/conda-2026-10-13/summary.json)：后端 21/21、前端 4/4，类型、lint/架构检查和构建通过。
- [后端 JUnit](../reports/conda-2026-10-13/backend-unit.xml)、[前端 JUnit](../reports/conda-2026-10-13/frontend-unit.xml)：原始测试明细。
- [启动验证](../reports/conda-2026-10-13/startup-smoke.json)：后端 `/health`、`/docs`、前端 `/`、代理 `/v1/health`、`/v1/cases` 均返回 200，迁移与 Demo 命令返回 0。

测试入口会保存各步骤日志，并在任一检查失败、缺少有效 JUnit、超时或没有收集到单元测试时返回非零退出码。`reports/latest/` 是可重复覆盖的本地输出，带日期的本次报告另行保留。

本轮验证范围不含浏览器 E2E、收费模型或原生 Linux 实测。上一轮代码审查的四个功能问题没有在本次环境与文档任务中修改。
