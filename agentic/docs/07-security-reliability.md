# 安全、可观测性与可靠性

身份由宿主注入不可变 Principal；Run 只允许 owner 访问。内建工具需要 evidence:analyze，模型额外需要 model:invoke。数据来自本次已获授权的 CaseInput，不读取共享案件库；若宿主从其数据库构造输入，应在构造前做资源授权。

Tool 必须在 Registry 注册、在 Skill 声明且满足权限，不能由 Prompt 指定任意工具或代码。输入、参数、输出经过 Schema、JSON 大小与已知凭证模式检查。包含 api_key/password/Authorization 等字段或已知 token 样式的上下文被拒绝；该检查不声称识别所有敏感文本。事件日志只记录 ID、类型与统计，不记录原文/原始异常。报告和 Checkpoint 为有意保留的业务产物，包含输入文本，未默认加密；宿主负责访问权限、备份及保留期限。

模型密钥用 SecretStr 保存于进程配置，不进入模型上下文、版本摘要、Run 或日志。端点仅 HTTPS（环回测试例外），不含用户名/密码/query，禁重定向、禁自动环境代理；输入不能指定端点。只允许显式 egress 配置。HTTP 响应有 1 MB 上限，provider 错误不透传；服务名/模型名等公开配置不应包含秘密。

Prompt 将问题/证据/上游内容声明为不可信数据；模型返回简洁可引用判断，无 shell、无浏览器、无工具选择权限。结构性门禁保护原文、时间、来源、阶段与关键缺证状态。恶意文本不能改变 Core 权限；Prompt 与引用校验不保证语义判断绝对正确，因此模型候选解释需实质复核。

所有 Tool 调用有 operation_key、审计事件、超时和调用预算；同步只读工具使用线程，超时无法强制杀死 Python 线程，扩展中不得用此方式包装危险操作。副作用工具必须 async+idempotent，并由实现方兑现外部幂等；先展示具体参数，再由 run:review 身份批准。批准与实际参数/版本/运行指纹绑定，超时返回 EFFECT_UNCERTAIN，不自动宣称回滚。包内五个分析 Tool 均无外部写入；CLI 输出写入用户指定的本地路径。

模型超时/取消可能已经产生费用；失败没有 usage 时保留保守 Token/费用预留，unsettled_model_calls 明示未结算次数。瞬时网络/429/5xx 最多重试两次，每次重新占用预算。模型协议错误直接失败；引用/语义标注 Review 失败可按 max_repairs 修复。默认模型模式最多 10 次调用，不能无限重试或自我评审。

SQLite Checkpoint 采用独占 worker 锁、revision CAS、Run/Event 同事务和已完成 Tool 缓存。恢复核对身份、版本与 Prompt 指纹，不恢复旧审批。崩溃时预留的执行时间/费用不归零，避免重启绕过预算。单 worker 是明确限制，不宣称分布式锁/多实例一致性。

HTML 只用代码模板渲染模型结构化数据，字符串 HTML 转义、JSON 脚本转义，CSP 限定静态脚本/样式哈希，禁止网络连接和外部资源。来源弹窗用 textContent。鉴权报告路由设置 Cache-Control:no-store。DOM 与注入测试已覆盖；实际浏览器视觉检查因工具无可用浏览器未执行。
