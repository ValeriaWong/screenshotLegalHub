# 数据契约

领域模型在 `backend/src/screenshotlegal/domain/`；OpenAPI 导出由 `tools/export_openapi.py` 完成，前端 `src/api/schema.d.ts` 由 openapi-typescript 生成，禁止手动维护第二份业务接口。

EvidenceItem：case、MIME、SHA256、storage_path、原图尺寸。Message：可见原文、speaker、显式日期、event_type 和 SourceRef IDs。SourceRef：evidence/image/message/page、原图 bbox、raw_bbox/coordinate_space 和 quote。感知标准化验证引用闭环与坐标，不推测未知协议。

MatterManifest：版本、司法辖区、领域、review/legal status 和 required_capabilities。Claims YAML：Claim → Element → FactQuestionTemplate、burden、expected_evidence、signals、authority IDs、defenses。Pattern 是实践线索，单独标识 legal_rule=false。Authority 保存来源 URL/摘要/有效期/核验状态，本轮全部 unverified。

CasePlan/PlanNode：解析后的 Skill/version/digest、依赖、Stage、input selectors、output targets 和 retry policy。Entity 为能力输出共享 envelope：id/kind/title、业务 status、review_status、source_refs、details 和 provenance/digest。details 中表达 claim_id/element_id/fact_id、证据关系、缺口、策略引用等。

关系枚举：supports/contradicts/context/identity/timeline。强度：strong/medium/weak/unknown，非胜诉概率。业务与审核状态独立。AI 默认 unreviewed；ReviewDecision 追加保存 action、text、reviewer、run、reviewed_output_digest 和时间。

ProofMatrixRow 由服务器投影：claim/element/fact/burden/supporting/contradicting/gaps/strength。前端只渲染，不推导法律关系。ProofGraph 包含 entities 和关系边；历史 run_id 查询保持历史输入与结果。

Party 将身份核验状态与姓名分开。Reconciliation 保存至少两条来源的相同消息/重叠/不同/未解决对照关系；服务校验当前案件来源闭环并追加保存。LawyerAssessment 与 ReviewDecision 同事务追加，记录人的评估，不写回原模型结果。

## 2026-10-23迁移兼容

SourceRef.evidence_page允许正整数或null。null表示原始证据页码未知，不能默认显示为第1页；input顺序不冒充原始页码。已有数据保留原值。API/OpenAPI与前端类型同步；见[MIGRATION](MIGRATION.md)与[回归报告](../../reports/v3.0.0/import_atomicity_20261023_001/README.md)。
