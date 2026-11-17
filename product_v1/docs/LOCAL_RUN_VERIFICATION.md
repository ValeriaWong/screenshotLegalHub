# 本地运行验证

验证日期：2026-10-08（Asia/Singapore）。操作系统 Microsoft Windows 11 专业版10.0.22621。

实际环境：Python3.12.13，后端 `backend/.venv`；第二套全新验证环境 `backend/.venv-clean`。运行时安装位置 `.tools/python/cpython-3.12-windows-x86_64-none/`。Node22.14.0，npm10.9.2，来自当前用户 NVM。未使用 Conda，未修改旧仓库 venv 或全局 NVM 默认版本。

实际安装与迁移：uv 安装 Python3.12；创建全新 venv；安装 pyproject 及测试依赖；导出 requirements.lock；第二个新 venv 按锁文件安装并运行测试成功。随后执行 README 的 `bootstrap.ps1` 完整成功：uv pip sync/install、Alembic upgrade head、导出 OpenAPI、npm ci、生成 TS 类型、安装 Chromium、seed Demo。

实际服务：FastAPI/uvicorn 在127.0.0.1:18430、Vite 在127.0.0.1:18431，由 Playwright 真实启动。访问 `/health`、`/openapi.json`、工作台根页、Proof Matrix、Review、Advanced、Timeline。浏览器调用真实本地 API/SQLite，未使用浏览器拦截假 API。

Demo ID：`0c43aba1-7ae1-4172-b0a5-26180a34ca38`。两张720×640合成图片、四条消息、四个事件、四个待证事实、支持与反证关系、一个矛盾、多条缺口、一条策略，全部可点击原图像素 bbox。E2E 另建隔离的合成案件验证新证据导致审核失效；不会修改任何真实旧案件。

验证结果：

- 后端 pytest 21 passed，覆盖 Matter/digest、Skill/resolver/trust、compiler、projection、retry/idempotency、gates、immutable runs、proof graph/matrix、review stale、FTS、evidence/SHA/bbox、SSE、mocked vision、legacy import 与来源对照。
- 第二套全新 venv 安装的首次测试16 passed；最终源代码在该环境再次验证21 passed。
- 前端 typecheck、ESLint、UI architecture guards 全通过；Vitest 4 passed。
- Vite production build 成功；本地 dist 已生成，未部署线上。
- Playwright 3 passed：完整 Demo/来源/审核/运行/SSE/reload；变更重跑导致 stale 且保留旧运行；390×844移动布局与 reduced motion。
- axe WCAG2A/AA 无 serious/critical。曾发现并修复对比度和可键盘滚动问题，没有屏蔽检查。
- `scripts/verify.ps1` 已实际完成并以0退出；不是只列命令。
- README 的 dev-backend/dev-frontend 脚本已分别真实启动；最终14个核心读取接口与前端根页均HTTP200。机器可读摘要在 artifacts/local-verification.json。

截图在本地 `artifacts/workspace-desktop.png`、`workspace-mobile.png`、`review-stale.png`；调试失败时 Playwright 生成 trace，最终状态在 frontend/test-results/.last-run.json。以上运行产物被 gitignore 排除，源码与锁文件保留。

已知限制：无真实供应商付费调用；视觉适配器通过 MockTransport 测试协议与 egress audit。内置法律分析是保守线索整理；Pack/Authority 未专家核验。PDF只预览，音视频解析、图形 ProofGraph、复杂动效、多用户和生产认证属于P1。服务中断的 RUNNING 标记INTERRUPTED，新建运行重试；不自动重复外部付费调用。当前 Starlette/httpx TestClient 有一条上游弃用提示，测试仍通过，不隐藏提示。
