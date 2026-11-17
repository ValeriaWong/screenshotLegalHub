# 批量证据导入、账户权限和模型配置

## 当前可以使用的流程

首次打开页面创建管理员；账号使用字母、数字和 `._-`，密码 12–128 字符。初始化只允许一次，历史未归属案件交给首个管理员。之后由管理员在“用户”页创建普通用户或额外管理员。个人资料可修改显示名称与机构，密码修改会结束全部会话。

新案件属于创建者。在案件概览按已有用户名共享，查看者可以查看原件、搜索、结果和历史运行，编辑者还可以上传、识别、分析和审核；分享管理由所有者或管理员完成。管理员可访问全部案件，但不能通过模型接口查看别人的模型配置或 Key。

证据页支持一次选择多个 PNG/JPEG/WebP。服务按选择顺序逐个验证、保存和返回结果，坏文件单独失败，其余继续；同案按内容哈希去重，即使改文件名也复用原记录，保留原始显示名。前端清空 file input 支持再次选择同一文件，并保存失败文件列表用于重试。配额可在 `.env` 设置 `MAX_BATCH_FILES`、`MAX_UPLOAD_BYTES`、`MAX_BATCH_BYTES`。

图片自动读取格式和尺寸，核对 MIME、检查是否可解码；不猜测聊天原文。导入后选择已配置的视觉模型识别全部截图，或导入人工转录。视觉识别跳过 PDF 和文本；`evidence_ids` 可限制调用范围，外案 Evidence ID 会被拒绝。

每张证据具有当前识别选择：改文本、时间、发言人或 bbox 会形成新的不可变记录，新分析与检索只使用当前有效转录。未出现在人工转录 JSON 中的截图保留原选择；显式空列表可清空该截图的当前转录。历史运行固化旧记录，重识别不改写历史。没有匹配到证明关系时也能保留未知事实和证据缺口，不强行生成没有来源的策略。

## 模型设置

每个账号可以添加多个 OpenAI 兼容模型，设置名称、基础 URL、模型标识、API Key、是否支持视觉、是否允许请求，并指定自己的默认模型。支持文本模型配置，但截图页只展示支持视觉的模型。

基础地址示例为 `https://provider.example/v1`，程序追加 `/chat/completions`。普通地址要求 HTTPS；`localhost`、`127.0.0.1`、`::1` 的回环地址可用 HTTP。URL 禁止嵌入账号密码、query 和 fragment。其他协议或供应商专用认证需要扩展 provider，当前不自动兼容。

保存与编辑不发起网络调用。测试连接发送一条简短文本，不附带案件、截图或转录，最长等待 15 秒；页面显示成功/失败和耗时。未勾选允许请求时不调用服务。识别最长等待 90 秒，发送当前案件的截图。Key 留空表示编辑时保留已有值，新建模型必须填写。

SQLite 只保存 Fernet 密文；`data/.credentials/model-master.key` 保存本地加密主密钥，Linux 创建权限为目录 0700 / 文件 0600，Windows 使用数据目录继承的 ACL。API、错误响应、日志和网络审计不返回密钥明文，也不返回密文。保护服务器上的整个数据目录；备份数据库时同时备份主密钥。网页账号隔离不替代服务器磁盘访问控制。

## 代码模块与扩展方式

| 职责 | 模块 |
| --- | --- |
| 账号、密码散列、会话与案件授权 | `application/services/auth.py` |
| HTTP 登录与案件/运行访问检查 | `api/access.py`、`api/accounts.py` |
| 用户模型配置与私有默认选择 | `application/services/preferences.py` |
| 密钥加密 | `infrastructure/model/secrets.py` |
| OpenAI 兼容请求与连接探测 | `infrastructure/model/providers.py` |
| MIME 分派、图片/PDF/文本校验 | `plugins/ingestion/registry.py` |
| 哈希存储与原件验证 | `infrastructure/storage/evidence.py` |
| 批量文件入口与逐项结果 | `api/main.py` 中 `/evidence/batch` |
| 登录、模型设置、用户管理 | `frontend/src/features/auth/`、`features/settings/` |

新增叶子格式时实现 `EvidenceHandler.prepare` 返回 `PreparedEvidence`，注册到 `IngestionRegistry`，声明 MIME/扩展名及验证逻辑；存储和批量接口继续复用。前端从 `/v1/evidence/formats` 获取已启用格式，不硬编码未来格式。

当前 PDF 只校验签名、保存和预览，文本验证 UTF-8；**PDF 分页/识别和 ZIP 解压尚未实现**。ZIP 属于容器展开，应在逐文件导入前加入展开阶段，让展开的每个文件进入同一 registry/storage，再附加父 archive、内部路径与页号等来源元数据。展开阶段需要限制总量/数量/嵌套深度、检查路径和符号链接；格式验证与存储不负责解压。PDF 分页后也复用叶子导入与 SourceRef，保存原 PDF 与页码，避免将派生页面当作无来源的新证据。

## 数据迁移、配置与实测

`0002` 添加用户模型元数据；`0003` 添加账号与会话；`0004` 添加当前转录选择。JSON case 记录新增 owner/members，无须丢弃原数据。先执行 `python scripts/conda_workspace.py setup`，再重启服务。已有管理员后 `seed` 的离线未归属演示不会自动分配，应从已登录页面“打开合成演示”，生成当前账号名下演示案件。

会话采用随机 token，数据库存 token 哈希与到期时间；Cookie 为 HttpOnly/SameSite=Lax，默认 8 小时。登录失败有节流，账号停用、角色调整、密码修改会撤销会话；最后一个启用的管理员不可停用或降级。所有业务 API 要求登录，原图、搜索、历史 Run、SSE 与审核关卡均检查案件权限；SSE 运行时会重新检查会话和权限。客户端退出/会话失效时清空查询缓存并重新加载，避免跨账号保留案件和模型数据。

本地默认 HTTP 可用；远程部署需 HTTPS，设置 `SESSION_SECURE_COOKIE=true`，并用 JSON 数组配置 `TRUSTED_ORIGINS` 为真实前端 Origin。带 Origin 的写请求只接受该名单，不使用宽泛通配。

验证在 Conda Python 3.12.15 / Node 22.23.2 中完成，结果见 [本次报告](../reports/multi-upload-auth-2026-10-13/REPORT.md)。浏览器测试使用专用端口 19430/19431/19432，独立 `.tools/e2e-data/run-*` 数据目录和回环模拟模型，保留测试数据但清理测试服务；验收后确认无正在执行的分析，刷新了开发后端以加载新接口。没有调用收费模型。

本次测试曾从产品根目录直接运行 pytest，未加载 `backend/pyproject.toml` 的 asyncio 配置而失败；改用统一测试入口或从 `backend/` 执行后正常通过。手动测试务必在后端目录运行；统一入口已固定正确工作目录。
