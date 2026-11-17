# Matter Pack 编写

从 `matterpacks/_template/` 指引开始，参照 `cn/civil/private_lending/1.0.0/` 创建新版本目录。五个 YAML 文件：manifest、claims、patterns、authorities、tests。

manifest 的 id/version 唯一；schema_version=1；status 必须 draft/reviewed/deprecated；未专家审查时 expert_review.status=unreviewed。Claim/Element/FactQuestion IDs 在包内唯一；FactQuestion 必须含 question、burden、expected_evidence、signals、negative_signals、authority_ids。

Authority 必须完整声明来源和核验状态。仅有 URL 或模型生成内容不能设置 verified；source_digest 未记录时保持 unverified。有效期过期不能继续作为已核验依据。

Pack 禁止保存 executor/class、调用数据库/模型、运行 Skill 或包含 UI。新增事项主要编辑数据即可复用通用 Skills。修改规则应新建版本，旧 Run 固化 Pack 内容和摘要；新编译记录新版本与 digest。

Registry 按排序后的 YAML 文件名与原始 bytes 计算 SHA256，任何规则改动都会改变 digest。阅读者应注意格式变动也会改变包摘要。`tests.yaml` 提供领域预期计数/审核状态；后端测试验证 Pack Schema 和演示结果，不代替专家的实质法律审核。
