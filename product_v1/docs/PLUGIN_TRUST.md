# 插件信任

默认 trust=external_untrusted，不执行、不动态导入。builtin 可在允许的权限集合内执行；trusted 还必须列入 SKILL_ALLOWLIST。没有自动下载 Python 插件的流程。

权限必须显式声明 network、filesystem_read、filesystem_write、model、retrieval、authority_search。Settings.allowed_permissions 默认为 retrieval；任一请求权限超出策略直接 PermissionError，并拒绝编译/执行。

信任与权限是 policy enforcement + audit，不是操作系统隔离。不可信代码不能因为声明 side_effects=false 就获得执行权。外部 Marketplace 和真正 OS sandbox 不属于 v1。
