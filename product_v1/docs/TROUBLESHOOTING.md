# 实际遇到的配置与踩坑

只记录本轮实际观察的问题。

下列 venv 记录来自最初的 2026-10-08 验证。2026-10-13 新增并实测了独立 Conda 环境，当前配置与 Linux 命令见 [CONDA_LINUX_SETUP.md](CONDA_LINUX_SETUP.md)；旧记录中的“不使用 Conda”仅描述当时的运行方式。

## 终端默认初始化失败

- Symptom：执行工具返回 setup refresh/helper_unknown_error。
- Root cause：默认受限进程启动失败，尚未进入仓库命令。
- Fix：使用经审核允许的本地执行通道；没有修改仓库权限或绕过文件边界。
- Final configuration：所有操作限定 product_v1；启动脚本可在用户 PowerShell 正常运行。

## PowerShell Profile 报错与中文乱码

- Symptom：generate-shell-completion 包解析失败，Invoke-Expression 空字符串；中文文档显示乱码。
- Root cause：登录 shell 加载了用户 Profile，Windows PowerShell 默认文本编码不为 UTF-8。
- Fix：用 NoProfile/非登录 shell；读取指定 UTF8，设置 PYTHONUTF8=1。
- Final configuration：README 使用 `powershell -NoProfile`；脚本设置 Python UTF-8，不修改用户 Profile。

## 默认环境版本与规格不符

- Symptom：默认 python 指向3.9，py 默认3.11；node 默认20.19.3。
- Root cause：本机多套历史解释器与 NVM 默认版本。
- Fix：本目录安装 Python3.12.13 + backend/.venv；脚本从 NVM 选择已有22.14.0。
- Final configuration：不使用 Conda，不切换全局 NVM、不激活旧环境；用 venv Python 绝对路径。

## uv venv 没有 pip / 跨磁盘 hardlink 回退

- Symptom：`python -m pip freeze` 报 No module named pip；uv 提示不能 hardlink。
- Root cause：uv venv 默认不 seed pip；缓存与工作区跨盘。
- Fix：改用 `uv pip freeze/sync/install --python`；设置 UV_LINK_MODE=copy。
- Final configuration：bootstrap 使用 uv 管理 venv，运行服务不依赖 pip。

## 继承了关闭 Node TLS 校验的环境变量

- Symptom：首次 npm install 提示 NODE_TLS_REJECT_UNAUTHORIZED=0。
- Root cause：宿主进程继承的既有环境变量，非项目设置。
- Fix：后续安装在当前进程移除该变量并成功下载浏览器。
- Final configuration：bootstrap 不保留此不安全值，未改用户系统配置。

## OpenAPI 默认字段的 TS 类型不一致

- Symptom：测试对象缺少 SourceRef 默认字段、ReviewRequest reviewer 等，typecheck 失败。
- Root cause：生成类型对输出 default fields 使用完整结构；手写测试 fixture 过简。
- Fix：按生成契约补全测试与请求字段。
- Final configuration：schema.d.ts 单源生成；typecheck 通过。

## 损坏图片上传抛出未处理异常

- Symptom：Pillow UnidentifiedImageError 导致后端测试失败。
- Root cause：图片解码异常未映射为领域校验错误。
- Fix：捕获损坏图片/解码/超大像素异常并转 ValueError。
- Final configuration：API 返回规范409；MIME、大小、哈希和原图验证保留。

## Playwright 在 Windows 不能启动相对路径命令

- Symptom：`'..' is not recognized as an internal or external command`。
- Root cause：Windows cmd 解析 `../backend/...` 命令路径失败。
- Fix：配置用 path.resolve 生成绝对 Python 路径并加引号。
- Final configuration：Playwright 可实际启动两个服务。

## E2E 选中了隐藏 option

- Symptom：断言案件标题可见失败，locator 命中 select 内 option。
- Root cause：同名文字同时出现在案件选择框和页面标题。
- Fix：定位 `.eyebrow` 页面标题；采用语义 role 定位交互。
- Final configuration：桌面流程继续检查来源、人审、关卡和重连。

## PowerShell 参数数组传递

- Symptom：bootstrap 的 Python -c 校验出现 IndentationError。
- Root cause：位置参数与数组 splatting 经过包装函数时未保持预期原生参数边界。
- Fix：全部统一为命名参数 `-Executable` / `-Arguments`；版本检查使用 --version。
- Final configuration：实际 bootstrap 已非零失败过，修正后完整成功，不忽略命令退出码。

## 双语字典更新缺失中文键

- Symptom：中英文键一致性组件测试失败。
- Root cause：Windows PowerShell 管道传递源码时，默认编码影响含中文的文本替换。
- Fix：写入使用明确 UTF-8；补齐中文 reviewNotice 键。
- Final configuration：字典键匹配测试通过，不依赖控制台默认编码。

## axe 发现真实无障碍问题

- Symptom：导航编号对比度4.1低于4.5，滚动 pre 不能键盘聚焦。
- Root cause：导航编号透明度降低了实际对比度；滚动详情缺少 tabindex。
- Fix：导航编号使用完整语义前景色；滚动代码区、DAG、矩阵容器加入键盘聚焦。
- Final configuration：保留 axe serious/critical 检查阈值，修复界面而不关闭检查。

## 早期演示 Party 字段的兼容读取

- Symptom：启动脚本后的逐接口 smoke 中 parties 返回500，其他核心接口200。
- Root cause：开发早期合成记录用 status 保存身份审核状态，新领域契约使用 identity_status，响应严格校验拒绝旧字段。
- Fix：读取投影兼容这两个字段，返回统一 Party Schema；不改写历史记录。
- Final configuration：补充旧字段形状的 API 回归断言，再次检查实际本地服务。
