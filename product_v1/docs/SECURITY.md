# 本地安全边界

默认监听127.0.0.1，已加入登录、管理员/普通用户和案件 owner/viewer/editor 授权。脚本仍固定回环绑定。会话为 HttpOnly/SameSite=Lax Cookie，服务端保存 token 哈希和到期时间；密码用随机盐 scrypt 散列，不存明文。远程部署需要 TLS，设置 SESSION_SECURE_COOKIE=true 与正确的 TRUSTED_ORIGINS，并配置服务器数据目录访问控制。

上传限制默认每文件20MiB、每批50个/100MiB，允许已登记 MIME。图片解码/verify 并核对 MIME；PDF 核对签名；文本校验 UTF-8。文件名仅显示，存储由 UUID case + SHA256 扩展名构成；路径 resolve 后校验根目录。下载必须经过登录、案件权限和已登记 case/evidence ID，读取时重算 SHA256。原文件不覆盖，篡改使读取/分析失败；ZIP 解压当前未启用。

截图中的指令属于证据文本，不执行。感知保留可见原文和明确坐标，不推断身份、完整日期或法律效果。未知坐标协议拒绝。来源必须属于运行固化的证据集合。

网页模型按用户配置，必须显式允许请求；模型 ID 不能跨用户使用，即使管理员也不能读取其他用户的模型配置。外部地址要求 HTTPS，仅回环本地服务允许 HTTP。Key 以 Fernet 密文保存，主密钥在忽略提交的 data/.credentials/model-master.key。接口不返回 Key/密文，校验错误移除原始输入；网络错误不返回供应商响应正文。测试连接只发送短文本，不发送案件；截图识别在用户主动选择后外发所选图片，记录 egress audit。离线适配器的旧环境开关仍默认 false。

第三方 Python 默认不加载，无 OS 沙箱承诺。CORS 和带 Origin 的写请求使用 TRUSTED_ORIGINS 名单；不接受通配。原图、检索、历史运行和 SSE 均检查案件权限，SSE 中也重新检查会话。工作台和数据目录包含敏感案件时应使用服务器磁盘访问控制与加密备份；数据库与主密钥须一同备份。data/.env 均被 .gitignore 排除。
