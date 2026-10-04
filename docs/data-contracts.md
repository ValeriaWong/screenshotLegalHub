# 数据与运行契约

本文件定义新代码之间的交接。历史文件继续放在 `projects/`，来源文件名、索引和 SHA256 必须保留。

## 评测任务

`blocks/evaluator/artifacts/datasets/<digest>/tasks.jsonl` 每行包含 `id, track, case_id, images, image_hashes, prompt, answer, label, source, source_sha256, source_index`。`case_id` 当前只是文件名前缀，尚未验证为真实案号。供应商只接收 prompt 和图片，不能接收 answer。运行绑定 dataset digest、模型配置与 prompt digest。

现有八条 track：截图分类、证据形式、群聊/私聊、单图案由开放问答、案件多图开放问答、案件案由选择、原始辅助文本消息题、仅图片和人工区域定位的消息题。不同 track 单独出分。开放题 Exact match 和文本重合值不能代替法律正确性评分。旧框的 IoU 是历史抽取匹配质量，不能把 IoU 未通过题全部扔掉再声称是全量结果。

## 证据软件交接（检索与评测同步开发）

| 对象 | 必需字段 | 约束 |
|---|---|---|
| Case | case_id, mode, jurisdiction, client_party_id | mode 为 judge / lawyer，中文和英文适用法分别指定 |
| EvidenceImage | image_id, sha256, file, evidence_page, submitted_by, conversation_id | 页码来自上传清单，跨会话顺序不能只按文件名推断 |
| Message | message_id, speaker_local_id, speaker_party_id, text, timestamp_raw, timestamp_normalized, time_precision, image_id, bbox | 原文和规范化内容分开，身份无法确定时不强行合并 |
| SourceRef | image_id, evidence_page, bbox, message_id, quote | 每句话及意思表示可回到原截图区域 |
| Event | event_id, event_type, main_intent, actors, time_interval, source_refs, supporting_message_ids | 单个事件可以引用多张图、多条消息；不确定时间保留区间或 unknown |
| Reconciliation | overlap_candidates, confirmed_message_links, gaps, conflicts, submission_refs | 法官模式可对齐双方截图；缺失内容只报告缺口，不能补造“原始聊天” |
| LawyerAssessment | event_id, client_party_id, favorable, adverse, neutral, rationale, source_refs | 有利性是相对指定一方的判断；提供工作视图筛选和不利标注，原图与完整记录仍可追溯 |
| ExportRow | event_id, time, speaker, main_intent, quote, evidence_pages, source_refs, favorability, review_status | Excel 来源可多值，禁止只写一个页码而丢失其它证据来源 |

retrieve 的原始需求仍需核对用户项目上下文。案件内部检索应按人物、时间、事件和关键词查找相关消息/图片并返回来源；归档《证据理解流程图》还明确包含类案检索和请求权基础（法条），须保留在需求核对中，不能默认排除出 v1。外部检索须通过独立 adapter 返回可追溯来源。

2026-10-04 用户明确：retrieve 使用代码完成，不依赖模型，并与评测同步开发。当前实现为本地 SQLite FTS5/BM25、原文匹配和显式同义词词典，查询不发模型请求。模型只向检索模块交付结构化消息/事件；其输出须保留未复核状态。检索可覆盖案件内资料、已归档类案文书及已导入的公布版本法条，不借模型生成搜索答案。

索引校验 image SHA256、原图像素 bbox、案件范围、引文与被引用消息转录的对应关系；这属于结构校验，不能证明转录文字或事件解释与图像事实一致。历史模型预测、真实新模型抽取、人工复核记录必须明确区分。缺少年月日的时间不自动补全；日期过滤排除日期未知记录，并在界面说明。跨图头像不自动合并为真实身份，原图页码未知时保留 null。

抽取运行须明确坐标协议：默认 `pixels`，可显式选择 `normalized_1000`。后者先校验 0–1000 原始框，再按原图宽高转换一次；SourceRef 中 bbox 始终为原图像素，另保留 raw_bbox 和 raw_bbox_coordinate_space。禁止从数值范围猜测旧输出的坐标协议。上下文窗口限于同图、同 origin_type 和同一抽取 run_id，避免混合不同版本的转录。

评测字段 evidence 的原问题是“规范的聊天截图证据形式”，独立于 classify 的法律意义。不得把它直接替换为内容相关性、真实性或法院采信结论。旧 nickname 属性在头像标注中可能是按人工标注顺序登记的内部 ID，与旧 KIE 的“右侧 avatar_0”约定存在不一致，不应用统一左右规则替换原金标。

## v2 合成数据

判决文件与引用片段 → 事实约束图 → 多角色聊天 → 固定视口渲染 → 题目与最小证据集合 → 人工审核 → 冻结数据版本。每条消息保留 `origin_type`：verbatim_quote / judgment_paraphrase / synthetic_completion。判决原文引文保留 source document、页码或段落及原文，不能把判决结论混入仅凭截图作答的 prompt。

同一判决、衍生聊天、同源截图、近似改写必须属于同一 split。测试集冻结后不用于挑选生成 prompt 或评分 prompt。迭代用开发集与新候选池，发布新的 benchmark 版本后才能比较跨版本结果。

第一轮独立产物位于 `datasets/v2.0.0/round_001/`。`curated.json` 是查看入口，`draft.json / critique.json / revised.json / final.json / curation.json` 保留迭代链。跨技术分段的逐字引用允许 `source_id + source_end_id + source_char_span`，程序须验证该引用仍是完整原文中的连续子串。不能用任意省略号拼接源文。

`questions.review.json` 绑定候选题的消息、图片页码及 bbox，图数和会话数仅为候选证据集统计。`minimal_set_status` 保留未经验证或全记录缺失检查的限制，不能将局部引用当作全局“没有证据”的证明。`tasks.image_only.json` 不含答案、判决和隐藏事实账本，但其问题仍是待审核的开发候选。固定视口预览采用本地聊天 UI，保留合成水印，页脚仅使用不透露案由的散列 ID。

## 运行产物

每次运行保存配置快照（剔除密钥）、数据和 prompt 摘要、输入清单、输出、异常、供应商返回的模型名、token usage、延迟、时间。请求失败和格式错误纳入计划任务分母。费用需供应商价格或账单实测，不能从模型名字猜价。云端与本地均经模型 adapter，本地模式需要正在服务的视觉模型。
