# API

开发地址 `http://127.0.0.1:18430`；交互文档 `/docs`，Schema `/openapi.json`。业务前缀 `/v1`，health/version 另提供根路径便于健康检查。

除 health/version、`auth/status`、`auth/setup`、`auth/login` 外，业务接口需要登录 Cookie；未登录 401，无权访问的外案 404，仅查看者写操作 403。写请求检查 Origin。登录 Cookie 为 HttpOnly/SameSite=Lax，默认 8 小时。

Auth：GET `/auth/status`、POST `/auth/setup`（仅首个管理员）、POST `/auth/login`、GET `/auth/me`、POST `/auth/logout`、POST `/auth/password`。初始化/添加账号传 username/password/display_name；登录传 username/password；改密码传 current_password/new_password。

用户资料：GET/PUT `/user`（display_name/organization）。管理员账号管理：GET/POST `/users`，PUT `/users/{username}`（role=admin/member，enabled）。案件协作：GET/PUT `/cases/{id}/members`，写入 `{username, role: viewer|editor|remove}`，仅所有者/管理员可管理。

模型：GET/POST `/settings/models`、PUT/DELETE `/settings/models/{id}`、PUT `/settings/default-model`（model_id 或 null）、POST `/settings/models/{id}/test`。添加配置传 name/base_url/model_name/api_key/supports_vision/allow_external_egress；编辑 api_key 留空保留原值。返回仅包含 has_api_key，不返回密钥或密文。测试返回 success/message/latency_ms，连接失败仍返回 200 + success=false；外用户模型 ID 返回 404。

批量 Evidence：POST multipart `/cases/{id}/evidence/batch`，多个 `files` 字段；返回 results 数组（index/filename/status/evidence/error）和 uploaded/duplicates/failed 数量。逐文件 status 为 uploaded/duplicate/failed，部分失败仍返回 200；数量超限 413。原有单文件接口保留。GET `/evidence/formats` 返回当前格式及配额。

Case：POST/GET `/cases`，GET `/cases/{id}`。Evidence：POST multipart / GET `/cases/{id}/evidence`，GET `/cases/{id}/evidence/{evidence_id}/file`，GET `/cases/{id}/source-refs`。文件读取只接受当前案件的已登记证据 ID，并验证 SHA256。

Perception：POST `/cases/{id}/perception/runs`，body `{adapter: mock|manual|openai-compatible, fixtures: {evidenceId: [rows]}, model_id?: string, evidence_ids?: string[]}`。模型属于当前用户，未指定 model_id 使用该用户默认模型；视觉模式只处理图片，跳过 PDF/文本。默认 mock 对真实上传返回无转录提示，不伪造消息。检索 GET `/cases/{id}/search?q=...` 返回当前有效消息与 SourceRef IDs；重识别保留历史版本。

Plan：GET `/cases/{id}/matter-candidates`；PUT `/matter-selection` 确认 Pack/version；POST `/analysis/compile` 可传 overrides；GET `/case-plan`。Run：POST/GET `/analysis/runs`；GET `/runs/{run_id}`；GET `/runs/{run_id}/events`；POST `/runs/{run_id}/review-gates/{gate_id}`，action=approve/reject。

结果：GET `/cases/{id}/proof-graph`（可指定历史 run_id）、`proof-matrix`、`timeline`、`claims`、`contradictions`、`gaps`、`strategy`。Review：POST/GET `/cases/{id}/reviews`；POST 必须传 target_id、action、output_digest，编辑需 text。未知资源404，输入/状态冲突409，权限403，Schema 校验422。

GET `/matter-packs`、`/skills` 返回 registry 元数据。POST `/demo` 幂等加载合成案件，无模型 Key。禁止 Benchmark 访问内置 Skill/OCR 实现，外部 Adapter 应通过上述稳定接口配置输入和读取输出。

更新接口后运行 `tools/export_openapi.py` 和 `frontend/npm run generate:api`，提交生成的 TS 类型。不要修改 `src/api/schema.d.ts`。

Evidence Core 补充接口：GET `/cases/{id}/parties`；POST/GET `/cases/{id}/reconciliations`（至少两个不同的当前案件 SourceRef，保存对照关系与理由）；GET `/cases/{id}/lawyer-assessments`（Review 同事务追加对应律师评估记录）。这些结构不依赖微信来源类型。
