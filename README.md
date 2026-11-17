# screenshotLegalHub

电子证据工作台、截图数据构建与研究评测工作区。本文按 **2026-11-17 的源码**整理；历史测试、数据数量及专业认证状态以各自有日期的记录为准，本次未重新运行产品或模型评测。

## 当前架构

| 部分 | 职责 | 入口与文档 |
| --- | --- | --- |
| `product_v1` | 当前 FastAPI + React/TypeScript 产品；账户、案件、证据、分析 DAG、证明矩阵、审核，以及文档和研究工作流 | [产品说明](product_v1/README.md)；API 18430、前端 18431 |
| `agentic` | 独立 Python 文本证据分析包；Planning → Facts → Assessment → Gaps → Synthesis，含 Tool、Review、预算与报告 | [包说明](agentic/README.md)；CLI/SDK，可选示例 HTTP 18440 |
| `legalhub` + `blocks/retriever/web` | 旧 Python 工作台与原生浏览器界面；检索、转录、问答、时间轴和法律批注 | `python -m legalhub.app serve --port 18420`；[历史指南](docs/ai_docs_center/LEGACY_GUIDE.md) |
| `blocks`、`tools`、`configs/v3`、`paper` | 数据整理、合成截图、质量检查、校准、方法复现和论文；部分工具依赖旧包或本地资产 | [文档入口](docs/README.md)、[论文入口](paper/README.md) |

[当前架构与依赖边界](docs/architecture.md) · [历史重构建议](docs/architecture/REFACTOR_PROPOSAL.md) · [提交安全与本地资产范围](docs/REPOSITORY_SAFETY.md)

`product_v1` 的用户工作台 `/`、生成台 `/studio.html`、审核台 `/review.html`、评测台 `/evaluation.html` 和完整控制台 `/console.html` 共用前端工程、FastAPI 与账户体系，尚未独立部署。`agentic` 没有接入产品 Runtime，输入为调用方已转写文本。

## 环境与启动

- 旧线沿用根 `requirements.txt`；产品后端按 `product_v1/backend/pyproject.toml` 和 `requirements.lock` 使用 Python 3.12+，前端按 `package.json`/`package-lock.json` 使用 Node 22。
- 产品环境定义与可复现入口为 [environment.yml](product_v1/environment.yml)、[conda_workspace.py](product_v1/scripts/conda_workspace.py)；完整安装、迁移与启动步骤见[产品 README](product_v1/README.md)。`agentic` 独立安装和接入见其 README。
- 持续运行的本地服务按工作区约定使用 PM2，启动前核实环境、cwd、现有条目与端口；本次整理未启动、重启或停止服务。
- **监听范围取决于启动入口。** 当前产品 Vite 开发配置绑定 `0.0.0.0`，后端 `Settings.host` 默认也是 `0.0.0.0`，部分脚本显式覆盖为回环地址。上述端口是源码约定，不是本次健康检查结果。

旧线、产品与独立包分别维护配置。根 `configs/models.local.yaml` 不控制产品用户模型；产品凭据及其加密主密钥位于运行数据目录，不进入 Git。

## 研究与验收边界

V2/V3 数据、人工复核与历史结果见 [V3 交接](docs/v3.0.0/CALIBRATION_HANDOFF.md)、[历史进度](docs/ai_docs_center/PROGRESS.md)和[研究产品边界](docs/products/PRODUCT_BOUNDARIES.md)。这些日期化记录不代表本次重新验收。ProofGraph、规则 Review 或程序测试通过不等于材料真实或法律专业认证完成；当前用户工作台的 PPT 功能仍为模拟预览。

源码仓库排除原始证据、数据库、密钥、模型权重、环境、下载的上游代码和运行报告。历史文档中的本地资产链接可能在全新 clone 中不可用；重现实验需另行准备资产，不应把缺失材料视为已发布数据集。

## 提交前检查

```powershell
node tools/check_git_secrets.mjs --worktree
# git add 后检查实际索引内容（包括未改动的已跟踪文件）
node tools/check_git_secrets.mjs --staged
git diff --cached --check
```

扫描器只输出文件位置与规则；已核实的合成安全测试值使用精确摘要例外。扫描不能替代人工审阅。历史 [2026-10-24 工作区说明](docs/architecture/WORKSPACE_SNAPSHOT_2026-10-24.md)和[早期重启记录](docs/RESTART_ARCHITECTURE.md)保留供追溯。
