# KIE / VQA 字段映射规格

2026-10-24。版本kie-vqa-mapping.v1，可供实施评审，未接入生产接口。以下目标字段是拟扩展契约，不表示当前API已支持。主源为用户指定目录；[审计](../../reports/kie_vqa_migration_20261024/REPORT.md)和[机器映射](../../reports/kie_vqa_migration_20261024/field_mapping.json)保存来源。

## 19类标签覆盖

| 旧标签 | 条数 | 新字段（拟） | 答案类型与限制 |
|---|---:|---|---|
| `attitude` | 950 | `region.attitude_legacy` | categorical；positive/joke/negative/nothing/non_legal；含义待量表确认 |
| `classify` | 1176 | `image.classification` | categorical；四类截图标签；不等同于证据可采性 |
| `speaker_comment_attitude` | 64 | `region.reply_attitude` | categorical；other/accept/rebuttal，与attitude分开 |
| `nickname` | 1708 | `region.speaker_local_ref` | identity；内部avator编号与昵称分开；不得统一按左右改金标 |
| `case` | 1174 | `image.case_analysis_reference` | open_text；旧参考分析待范围和专业复核 |
| `evidence` | 1174 | `image.evidence_form` | categorical；is_evidence/not_evidence；保留规范截图证据形式口径 |
| `group_chat_or_private_chat` | 1174 | `image.chat_type` | categorical；private_chat/group_chat |
| `show_real_identity` | 462 | `region.identity_visibility` | categorical；shown/unshown；不自动认证实名 |
| `legal_relationship` | 462 | `region.legal_relationship_reference` | open_text；需明确允许背景和法律范围 |
| `legal_intent` | 704 | `region.legal_intent_reference` | open_text；与动作/法律分析分别评价 |
| `legal_analysis` | 787 | `region.legal_analysis_reference` | open_text；专业量表与规则来源未齐备时不自动给法律正确分 |
| `action_analysis` | 166 | `region.action_analysis_reference` | open_text；转账行为解释与金额抽取分开 |
| `amount` | 249 | `region.amount_raw` | amount；保存原值；未知不转0；数值与币种分别建模 |
| `speaker` | 683 | `region.speaker_raw` | identity；可见昵称/内部编号/真实身份分别保存 |
| `file_name` | 13 | `region.file_name` | filename；保留扩展名、大小写与Unicode原文 |
| `evidence_` | 13 | `region.file_evidence_type_legacy` | categorical；原值todo/photo，语义待核；不与evidence合并 |
| `evidence_content` | 13 | `region.file_evidence_content` | open_text；与文件名和类型分开 |
| `speaker_avator` | 30 | `region.avatar_reference_raw` | identity；内部编号、头像标签和显示名混用，待身份映射复核 |
| `bug_report` | 29 | `quality.comment.body` | review_note；保留为审核意见，不默认当模型答题目标 |

共11,031属性行。bug_report的29条是审核意见，默认不作为模型答题目标，但来源和处置记录保留。evidence与evidence_、attitude与speaker_comment_attitude保持不同命名空间。未明确语义的字段结构映射可先完成，正式评分保持禁用。

## 结构及运行字段映射

| 源字段 | 拟接入对象 | 转换与保留要求 |
|---|---|---|
| `annotations[].id/folder/url/fileName` | `sample.source_ref/asset.source_ref` | 原值保留，文件名与逻辑样本ID、图片sha分开；不据前缀认定真实案号 |
| `annotations[].result` | `annotation.raw_payload_ref` | JSON字符串解析为结构树，保留原始字节哈希与JSON指针；失败隔离 |
| `annotations[].result.annotations[].toolName` | `annotation.tool` | 保留textTool/tagTool/rectTool粒度 |
| `attributes[].image_tail` | `annotation.asset_ref` | 解析上传前缀/文件名/旧dataurl别名；冲突与缺图显式列出 |
| `attributes[].tool/label/answer` | `annotation.attributes_raw + label_mapping` | 不把序列化字符串视为统一答案类型；原始多值回到result核对 |
| `attributes[].x/y/width/height` | `annotation.region.bbox_xyxy` | [x,y,x+w,y+h]；保留浮点原值，验证有限值、正面积与页面尺寸，不自动裁框 |
| `attributes[].order` | `annotation.source_order` | 原标注顺序，不是消息真实时间；与source_row_index共同定位 |
| `structured_info.dialog_name` | `prediction.parsed.dialog_name` | 模型预测；不写入人工金标 |
| `structured_info.conversation[].timestamp` | `prediction.parsed.messages[].timestamp_raw` | 精度与未知状态分开；不补造年月日/分钟 |
| `structured_info.conversation[].speaker` | `prediction.parsed.messages[].speaker_raw` | 保留avatar/avator差异及原值，映射需版本化 |
| `structured_info.conversation[].content` | `prediction.parsed.messages[].text` | 原文与归一化文本分开 |
| `structured_info.conversation[].message_bbox` | `prediction.parsed.messages[].bbox_xyxy` | min_x,min_y,max_x,max_y；非有限、倒置、越界单列 |
| `structured_info.conversation[].image/transfer/file` | `prediction.parsed.messages[].image_description/transfer_raw/file_raw` | 不得像旧IoU匹配视图那样丢失这三个字段 |
| `Qwen_outputs[].main_model/aux_model/mode` | `legacy_attempt.provenance` | 保存主/辅助模型和evidence轨道，不冒充完整新模型快照 |
| `Qwen_outputs[].original_prompt/combined_prompt` | `legacy_attempt.prompt_snapshots` | 原图直答与结构化文本辅助分开；<image>占位符不证明实际发了图片 |
| `Qwen_outputs[].structured_info/api_response` | `legacy_attempt.upstream_prediction/raw_response` | 结构化信息是模型产物；api_response不自动视为已评分VQA结果 |
| `iou_report.structured_json/rects_json/total_rects` | `matching.source_refs/source_denominator` | 保存旧路径及指向文件哈希，绑定实际输入版本 |
| `iou_report.details[].image/label/answer/rect_bbox/orig_image_tail` | `matching.reference_region_ref + raw_context` | 以source row稳定关联；多属性共享物理框，不能当独立检测框 |
| `iou_report.details[].best_iou/best_msg/no_message` | `matching.edges/status` | 旧many-to-one关联；no_message=False且best_msg=null仍可能是零交叠 |
| `questions[].image_tail/label/answer` | `task.source_ref/target_ref` | 全部6333目标按序与旧IoU对应；原答案在审核/评分侧 |
| `questions[].iou/iou_threshold/iou_pass/reason` | `task.legacy_selection_diagnostics` | 0.60阈值与1475通过保留，不能删除4858未通过题 |
| `questions[].matched_message` | `task.legacy_assisted_context` | 模型抽取辅助输入；不能冒充人工转录或纯图片轨道 |
| `questions[].rect_attrs` | `task.legacy_raw_rect_ref` | 当前6333项全为null；回连attributes稳定行与region，不补造旧字段 |
| `questions[].prompt` | `task.legacy_prompt_snapshot` | 现存v1/v2不能逐字重建；原文冻结，另建新版模板 |
| `output/*.timestamp/task_id/task_ids/model/prompt` | `legacy_run.source_time/parent_refs/model_alias/prompt_ref` | 旧时间无时区时保留未知；聚合链不能补造API调用次数 |
| `output/*.items[].image_tail/response/error/meta_review` | `legacy_attempt.asset_alias/raw_response/error/comment` | 每次尝试保留，错误done状态不表示成功；Meta Review是模型意见 |
| `output/checkpoints/*.done.json/*.items.jsonl` | `legacy_run.checkpoint_refs` | 只存历史状态证据，不直接驱动当前worker恢复 |
| `config.yaml.models[].name/model_name/base_url` | `model_config_migration.alias/model_id/endpoint_ref` | 映射现有配置；不自动导入旧默认重跑参数 |
| `config.yaml.models[].api_key` | `model_config_migration.credential_ref` | 禁止复制明文到清单/报告/任务；通过现有密钥存储另建引用 |
| `config.yaml.models[].tpm_limit` | `model_config_migration.rate_policy_raw` | 保留值与未接入状态，当前产品无对应配置时不得假装已生效 |

## 目标对象及版本关系

- TaskSpec：任务类型、源SHA/JSON指针、输入范围、输出schema、Prompt和评分协议、split及上游产物哈希。
- Annotation：逻辑图片/原始字节SHA、样本修订、物理区域、属性原值、语义和审核状态。区域先于属性建模，4,209个候选物理框不冒充消息级金标。
- Prediction：每次模型原始响应及完整解析结构，包括image、transfer、file；不直接覆盖人工messages或金标。
- Match：旧many-to-one关联与新版物理区域匹配分开，保存所有边、未匹配项和参数。
- Score：绑定预测、目标、匹配及评分器哈希，保留逐项指标、原因和人工修订；重评追加新版本。

继续使用现有owner隔离SQLite与审计，不把这些概念对象误称为已建新表。旧source editor/time未知保持unknown；实际迁移者与原作者分别记录。

## 身份、图片和坐标

文件名/旧dataurl仅作别名，逻辑图片ID与内容SHA分别保存；同字节不同逻辑图不能静默删任务，划分时归为同源组。文件名前缀不是已核验真实案号。当前资产验证要求文件位于受管目录，实施时复制确认的字节并校验SHA，不能直接把外部绝对路径塞进当前manifest。

坐标从xywh转为xyxy时保留原浮点和页面尺寸。越界或非有限值单列；本轮唯一严格越界约10^-10像素，仅为舍入量级。新版可按已冻结容差生成有before/after记录的派生坐标，旧IoU回放保持原值。需要旋转/缩放时另建图像版本并记录变换。

旧头像ID不自动按“左/右”改写为实名或昵称；avatar与avator拼写差异、avator-0和avator_0别名必须有版本化规则。金额未知不转0，原文、Decimal值、币种、方向和answer_status分开。未知字段保留原始载荷引用，不能因新schema暂不支持而丢弃。


## 2026-10-24 实施落点

上述逻辑字段已进入新benchmark任务清单，不直接把旧模型输出写入现有Content.messages或Question.gold。实际容器为benchmark.dataset的受管任务JSON：保留target_field、source_ref/source_refs、legacy_raw、asset、region_id和bbox_xyxy。人工修订写入benchmark.annotation（target/question/区域/图片/来源哈希及版本），benchmark.release冻结这些绑定；预测保存在benchmark.history原始档案或benchmark.attempt原始返回/parsed中，匹配和评分写入benchmark.score。

12,201准备行全部保留，29个bug_report转为审核评论，其余12,172为任务。82个补图候选不自动确认身份；身份/attitude/evidence_语义待定时阻断正式通过。人类消息级KIE目标仍待建立，旧450模型结构化输出保持预测身份。[迁移使用与限制](KIE_VQA_MIGRATION.md)。
